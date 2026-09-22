"""Stage-4 revision analyses (zero API cost) -> results/revision.json

R7  A real BM25 retriever replaces the oracle per-request tool set (reviewer MAJOR-3).
R6  Accuracy-coupled cost: wrong tool selections cost extra calls (reviewer MAJOR-2).
R2  Cluster-valid intervals from DISJOINT sessions, where no task is reused (reviewer MAJOR-1).
"""
import json, math, random, re, statistics as st
from collections import Counter
from pathlib import Path
import replay as RP

ROOT = Path(__file__).parent
LMB = ROOT / "data" / "LiveMCPBench"
K = 5                                   # tools returned per retrieval (the trace router returns 3-5)
E3_ACC = {16: 0.710, 32: 0.613, 64: 0.543, 128: 0.409}      # measured live (results/live_summary.json)
TOK = re.compile(r"[a-z0-9]+")
words = lambda s: TOK.findall(s.lower())


# ---------------------------------------------------------------- R7: BM25 retrieval
def corpus():
    docs = {}
    for srv in json.load(open(LMB / "tools/LiveMCPTool/tools.json")):
        for s in (srv.get("tools") or {}).values():
            for t in s.get("tools", []):
                key = f'{s.get("server_name")}/{t["name"]}'
                props = " ".join((t.get("inputSchema") or {}).get("properties", {}))
                docs[key] = words(f'{s.get("server_name")} {t["name"]} {t.get("description") or ""} {props}')
    return docs


class BM25:
    def __init__(self, docs, k1=1.5, b=0.75):
        self.docs, self.k1, self.b = docs, k1, b
        self.len = {k: len(v) for k, v in docs.items()}
        self.avg = st.mean(self.len.values())
        self.tf = {k: Counter(v) for k, v in docs.items()}
        df = Counter(t for v in docs.values() for t in set(v))
        self.idf = {t: math.log(1 + (len(docs) - n + 0.5) / (n + 0.5)) for t, n in df.items()}

    def top(self, query, k=K):
        q = words(query)
        out = []
        for key, tf in self.tf.items():
            dl = self.len[key]
            out.append((sum(self.idf.get(t, 0) * tf[t] * (self.k1 + 1) /
                            (tf[t] + self.k1 * (1 - self.b + self.b * dl / self.avg))
                            for t in q if t in tf), key))
        return [k_ for _, k_ in sorted(out, reverse=True)[:k]]


def bm25_sets():
    """Per-task BM25 top-K over the catalog, queried with the user's request (RAG-MCP style)."""
    idx = BM25(corpus())
    qs = {r["task_id"]: r["Question"] for r in json.load(open(LMB / "annotated_data/all_annotations.json"))}
    sets, hit, tot = {}, 0, 0
    for t in RP.TRACES:
        got = idx.top(qs[t["task_id"]])
        sets[t["task_id"]] = got
        used = {k for e in t["events"] if e[0] == "A" for k in e[3] if k in RP.CAT}
        tot += len(used)
        hit += len(used & set(got))
    return sets, hit, tot


def task_order(seed=7):
    order = list(range(len(RP.TRACES)))
    random.Random(seed).shuffle(order)
    return order


def sessions_with(m, sets=None, disjoint=False):
    """Sessions built like replay.sessions(); if sets is given, per-request tool sets come from it."""
    order = task_order()
    groups = ([[order[j + k] for k in range(m)] for j in range(0, len(order) - m + 1, m)] if disjoint
              else [[order[(j + k) % len(order)] for k in range(m)] for j in range(len(order))])
    out = []
    for g in groups:
        tasks = [RP.TRACES[i] for i in g]
        sess = RP.session(tasks)
        if sets:
            it = iter(tasks)
            sess["events"] = [["U", e[1], sets[next(it)["task_id"]], sets[tasks[i]["task_id"]]]
                              if False else e for i, e in enumerate(sess["events"])]
            k = 0
            for e in sess["events"]:
                if e[0] == "U":
                    e[2] = e[3] = sets[tasks[k]["task_id"]]
                    k += 1
        out.append(sess)
    return out


# ---------------------------------------------------------------- R6: accuracy coupling
def acc(nvis):
    """Selection accuracy with nvis visible full schemas: log-linear interpolation of the E3 points."""
    xs = [(math.log(k), v) for k, v in sorted(E3_ACC.items())]
    x = math.log(max(nvis, 2))
    if x <= xs[0][0]:
        return xs[0][1]
    for (x0, y0), (x1, y1) in zip(xs, xs[1:]):
        if x <= x1:
            return y0 + (x - x0) / (x1 - x0) * (y1 - y0)
    slope = (xs[-1][1] - xs[-2][1]) / (xs[-1][0] - xs[-2][0])          # extrapolated beyond N=128
    return max(0.05, xs[-1][1] + slope * (x - xs[-1][0]))


def coupled(sess, strat, cat, pricing="P1"):
    """Billed cost plus the expected cost of one extra call per wrong tool selection."""
    b = RP.bill(sess, strat, cat, pricing)
    a = acc(len(cat) if strat in ("S0", "S1", "S1u") else K)
    execs = sum(len(e[3]) for e in sess["events"] if e[0] == "A")
    return b["cost"] + execs * (1 - a) * b["cost"] / max(b["calls"], 1), a


def boot(vals, n=4000, seed=1):
    rng = random.Random(seed)
    ms = sorted(st.mean(rng.choices(vals, k=len(vals))) for _ in range(n))
    return st.mean(vals), ms[int(0.025 * n)], ms[int(0.975 * n)]


def main():
    out = {}

    # R7 -------------------------------------------------------------
    sets, hit, tot = bm25_sets()
    out["bm25"] = dict(k=K, availability=hit / tot, hit=hit, tot=tot)
    print(f"R7 BM25 top-{K} availability: {hit}/{tot} = {hit / tot:.1%} "
          f"(oracle per-request 99.2%, per-step trace retriever 64.8%)")
    out["bm25_cost"] = {}
    for m, n in ((1, 100), (3, 100), (10, 100), (10, 25)):
        oracle = RP.sessions(m)
        real = sessions_with(m, sets)
        r_o, r_b = [], []
        for so, sb in zip(oracle, real):
            cat = RP.pick_catalog(so, n)
            base = RP.bill(so, "S1", cat, "P1")["cost"]
            r_o.append(RP.bill(so, "S2r", cat, "P1")["cost"] / base)
            r_b.append(RP.bill(sb, "S2r", cat, "P1")["cost"] / base)
        out["bm25_cost"][f"m={m},N={n}"] = dict(oracle=st.mean(r_o), bm25=st.mean(r_b))
        print(f"   m={m:>2} N={n:>3}: S2r oracle={st.mean(r_o):.2f}x  BM25={st.mean(r_b):.2f}x")

    # R2 -------------------------------------------------------------
    print("\nR2 cluster-valid intervals (disjoint sessions, no task reused):")
    out["disjoint"] = {}
    for m, n in ((10, 100), (10, 25), (5, 100), (3, 100)):
        dj = sessions_with(m, disjoint=True)
        for s in ("S2", "S2r", "S3", "S4"):
            rs = []
            for sx in dj:
                cat = RP.pick_catalog(sx, n)
                rs.append(RP.bill(sx, s, cat, "P1")["cost"] / RP.bill(sx, "S1", cat, "P1")["cost"])
            mu, lo, hi = boot(rs)
            out["disjoint"][f"{s}|m={m}|N={n}"] = dict(mean=mu, lo=lo, hi=hi, sessions=len(rs))
            if s in ("S2", "S3"):
                print(f"   m={m:>2} N={n:>3} {s:4}: {mu:.2f}x [{lo:.2f}, {hi:.2f}]  ({len(rs)} disjoint sessions)")

    # R6 -------------------------------------------------------------
    print("\nR6 accuracy-coupled cost (each wrong selection adds one call):")
    out["coupled"] = {}
    for m, n in ((10, 25), (10, 100), (10, 200), (3, 100)):
        sess = RP.sessions(m)
        agg = {}
        for s in ("S1", "S2", "S2r", "S3", "S4"):
            c = b = 0.0
            for sx in sess:
                cat = RP.pick_catalog(sx, n)
                cc, a = coupled(sx, s, cat)
                c += cc
                b += RP.bill(sx, s, cat, "P1")["cost"]
            agg[s] = (c, b, a)
        row = {s: dict(plain=agg[s][1] / agg["S1"][1], coupled=agg[s][0] / agg["S1"][0], acc=agg[s][2])
               for s in agg}
        out["coupled"][f"m={m},N={n}"] = row
        print(f"   m={m:>2} N={n:>3} (static accuracy {row['S1']['acc']:.0%}): " +
              "  ".join(f"{s} {row[s]['plain']:.2f}->{row[s]['coupled']:.2f}" for s in ("S2", "S2r", "S3", "S4")))
    json.dump(out, open(ROOT / "results/revision.json", "w"), indent=1)


def selfcheck():
    assert abs(acc(16) - 0.710) < 1e-9 and acc(200) < acc(128) < acc(16)
    s = sessions_with(3, disjoint=True)
    ids = [t for sx in s for t in sx["id"].split("+")]
    assert len(ids) == len(set(ids)), "disjoint sessions must not reuse a task"
    assert len(sessions_with(10, disjoint=True)) == 9


if __name__ == "__main__":
    selfcheck()
    main()
