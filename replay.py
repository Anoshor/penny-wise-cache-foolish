"""E1: trace-driven counterfactual replay of MCP tool-exposure strategies under prefix caching.

For each session (one or more chained real LiveMCPBench trajectories) we rebuild the exact prompt
every strategy would send at every LLM call (ordered segments) and bill it with provider rules:
  cached = longest segment-prefix shared with an earlier prompt in the session (>= provider minimum)
  cost   = R*cached + W*(uncached) + O*output            (normalized: base input price = 1)
History is append-only, so for a given head (tool block) the most recent prompt with that head
has the longest shared prefix -> we keep one prompt per head key (O(n) instead of O(n^2)).
Design rationale: PHASE2_tree_of_thoughts.md.  Output: results/replay.json
"""
import json, random, statistics as st
from pathlib import Path

ROOT = Path(__file__).parent
D = json.load(open(ROOT / "results/traces.json"))
CAT, META, TRACES = D["catalog"], D["meta_tokens"], D["traces"]
FULL, NAMEDESC, SUMM = 0, 1, 2

PRICING = {  # W write, R read, min cacheable tokens (verified 2026-09-19)
    "P1": (1.25, 0.10, 1024),   # Anthropic 5-min TTL; OpenAI GPT-5.6+
    "P2": (1.00, 0.10, 1024),   # OpenAI <= GPT-5.5 (no cache-write fee), e.g. gpt-5-nano
    "P3": (2.00, 0.10, 1024),   # Anthropic 1-hour TTL
    "P4": (1.00, 0.10, 4096),   # Gemini implicit caching (3.8 Flash)
}
O = 5.0                         # output price / input price
UNSTABLE_P = 0.44               # serialization churn observed in bifrost issue #7169
STRATS = ["S0", "S1", "S1u", "S2", "S2r", "S2u", "S3", "S4", "S5"]
NAMES = {"S0": "static, no cache", "S1": "static, cached", "S1u": "static, unstable JSON order",
         "S2": "RAG-prefix per step", "S2r": "RAG-prefix per request", "S2u": "RAG-prefix sticky union",
         "S3": "summaries + tail schemas", "S4": "discovery, append-only", "S5": "name+desc + append"}
DISCOVERY = {"S4", "S5"}


def tok(keys, col):
    return sum(CAT[k][col] for k in keys if k in CAT)


def session(tasks):
    """Chain tasks into one conversation. 'U' marks a new user request."""
    ev = []
    for t in tasks:
        rs = [e[2] for e in t["events"] if e[0] == "R"]
        ev.append(["U", t["question_tokens"], rs[0] if rs else [], sorted({k for r in rs for k in r})])
        ev += t["events"]
    return dict(id="+".join(t["task_id"][:8] for t in tasks), sys_tokens=tasks[0]["sys_tokens"], events=ev)


def pick_catalog(sess, n):
    need = {k for e in sess["events"] if e[0] == "R" for k in e[2]}
    need |= {k for e in sess["events"] if e[0] == "A" for k in e[3]}
    need &= CAT.keys()
    rest = sorted(CAT.keys() - need)
    random.Random(sess["id"]).shuffle(rest)
    return need | set(rest[:max(0, n - len(need))])


def prompts(sess, s, catalog):
    """Yield (segments, output_tokens) per LLM call; segment = (key, tokens)."""
    rng = random.Random(sess["id"] + s)
    head = {"S0": ("tools", "ALL"), "S1": ("tools", "ALL"), "S3": ("summ", "ALL"),
            "S4": ("meta",), "S5": ("nd", "ALL")}.get(s)
    head_tok = {"S0": tok(catalog, FULL), "S1": tok(catalog, FULL), "S3": tok(catalog, SUMM),
                "S4": META, "S5": tok(catalog, NAMEDESC)}.get(s)
    sys = [(("sys",), sess["sys_tokens"])]
    hist, cur, req, sticky, loaded, version = [], [], [], set(), set(), 0
    for i, e in enumerate(sess["events"]):
        kind = e[0]
        if kind == "U":
            hist.append((("h", i), e[1]))
            cur, req = e[2], e[3]
            sticky |= set(e[2])
            continue
        if kind == "R":
            cur = e[2]
            sticky |= set(e[2])
            if s == "S4":
                hist.append((("h", i), e[1]))
            elif s == "S5":                        # newly discovered schemas injected at the end
                new = [k for k in e[2] if k not in loaded]
                loaded |= set(new)
                hist.append((("h", i), tok(new, FULL) + 20))
            continue
        if kind == "T":
            hist.append((("h", i), e[1]))
            continue
        if e[2] and s not in DISCOVERY:           # route-only call exists only with discovery
            continue
        if s == "S1u":
            version += rng.random() < UNSTABLE_P
            h = [(("tools", "ALL", version), tok(catalog, FULL))]
        elif s == "S2":
            h = [(("tools", tuple(cur)), tok(cur, FULL))]
        elif s == "S2r":
            h = [(("tools", tuple(req)), tok(req, FULL))]
        elif s == "S2u":
            h = [(("tools", tuple(sorted(sticky))), tok(sticky, FULL))]
        else:
            h = [(head, head_tok)]
        tail = [(("tail", i), tok(cur, FULL))] if s == "S3" else []
        yield h + sys + hist + tail, e[1]
        hist.append((("h", i), e[1]))


def bill(sess, s, catalog, pricing, expire=0.0):
    W, R, MIN = PRICING[pricing]
    nocache = s == "S0"
    last = {}                                     # head key -> last prompt with that head
    cost = raw = cached_sum = calls = 0
    for segs, out in prompts(sess, s, catalog):
        total = sum(t for _, t in segs)
        best, prev = 0, last.get(segs[0][0])
        if prev:
            for a, b in zip(prev, segs):
                if a != b:
                    break
                best += a[1]
        cached = 0 if (nocache or best < MIN) else best
        w = 1.0 if nocache else W
        cost += (1 - expire) * (R * cached + w * (total - cached)) + expire * w * total + O * out
        raw += total
        cached_sum += cached
        calls += 1
        last[segs[0][0]] = segs
    return dict(cost=cost, raw=raw, hit=cached_sum / max(raw, 1), calls=calls)


def sessions(m, seed=7):
    """95 sessions of m chained tasks (each task starts exactly one session; seeded order)."""
    order = list(range(len(TRACES)))
    random.Random(seed).shuffle(order)
    return [session([TRACES[order[(j + k) % len(order)]] for k in range(m)]) for j in range(len(order))]


def run(m=1, n=525, pricing="P1", expire=0.0, strats=STRATS):
    res = {s: [] for s in strats}
    for sess in sessions(m):
        cat = pick_catalog(sess, n)
        for s in strats:
            res[s].append(bill(sess, s, cat, pricing, expire))
    return res


def boot_ci(xs, n=4000, seed=1):
    rng = random.Random(seed)
    ms = sorted(st.mean(rng.choices(xs, k=len(xs))) for _ in range(n))
    return ms[int(0.025 * n)], ms[int(0.975 * n)]


def ratio_stats(res, s, base="S1"):
    r = [a["cost"] / b["cost"] for a, b in zip(res[s], res[base])]
    lo, hi = boot_ci(r)
    return st.mean(r), lo, hi


def availability():
    """A2: share of executed tools present in each retrieval-in-prefix set at that call."""
    out = {}
    for mode in ("S2", "S2r", "S2u"):
        hit = tot = 0
        for t in TRACES:
            rs = [e[2] for e in t["events"] if e[0] == "R"]
            cur, req = (rs[0] if rs else []), sorted({k for r in rs for k in r})
            sticky = set(cur)
            for e in t["events"]:
                if e[0] == "R":
                    cur = e[2]; sticky |= set(cur)
                elif e[0] == "A":
                    pool = {"S2": set(cur), "S2r": set(req), "S2u": sticky}[mode]
                    for k in e[3]:
                        if k in CAT:
                            tot += 1; hit += k in pool
        out[mode] = [hit, tot]
    return out


def churn():
    q = []
    for t in TRACES:
        sets, cur = [], next((e[2] for e in t["events"] if e[0] == "R"), [])
        for e in t["events"]:
            if e[0] == "R":
                cur = e[2]
            elif e[0] == "A" and not e[2]:
                sets.append(tuple(cur))
        if len(sets) > 1:
            q.append(sum(a != b for a, b in zip(sets, sets[1:])) / (len(sets) - 1))
    return q


def main():
    out = {"names": NAMES}
    # E1a: single-task sessions, full catalog, every pricing regime
    for p in PRICING:
        res = run(1, 525, p)
        print(f"\n=== E1a single task | N=525 | {p} ===")
        rows = {}
        for s in STRATS:
            mu, lo, hi = ratio_stats(res, s)
            rows[s] = dict(raw=st.mean(r["raw"] for r in res[s]), ratio=mu, ci=[lo, hi],
                           hit=st.mean(r["hit"] for r in res[s]), calls=st.mean(r["calls"] for r in res[s]))
            print(f"{s:4} {NAMES[s]:28} raw={rows[s]['raw']:9,.0f} cost={mu:5.2f}x [{lo:.2f},{hi:.2f}] "
                  f"hit={rows[s]['hit']:.0%} calls={rows[s]['calls']:.1f}")
        out.setdefault("E1a", {})[p] = rows

    # E1b: session length x catalog size (P1, P2, P4)
    grid = {}
    for p in ("P1", "P2", "P4"):
        for m in (1, 2, 3, 5, 10):
            for n in (25, 50, 100, 200, 525):
                res = run(m, n, p)
                cell = {s: dict(zip(("ratio", "lo", "hi"), ratio_stats(res, s)),
                                raw=st.mean(r["raw"] for r in res[s]),
                                cost=st.mean(r["cost"] for r in res[s])) for s in STRATS}
                cell["calls_S1"] = st.mean(r["calls"] for r in res["S1"])
                cell["inversion_S2r"] = sum(a["raw"] < b["raw"] and a["cost"] > b["cost"]
                                            for a, b in zip(res["S2r"], res["S1"]))
                grid[f"{p}|{m}|{n}"] = cell
        print(f"\n=== E1b {p}: cost of S2r (RAG per request) / S1 (static cached) ===")
        print("  m\\N " + "".join(f"{n:>9}" for n in (25, 50, 100, 200, 525)) + "   calls")
        for m in (1, 2, 3, 5, 10):
            cells = [grid[f"{p}|{m}|{n}"] for n in (25, 50, 100, 200, 525)]
            print(f"{m:>5} " + "".join(f"{c['S2r']['ratio']:9.2f}" for c in cells) + f"   {cells[0]['calls_S1']:.0f}")
    out["E1b"] = grid

    # H1 (pre-registered): N<=150, T>=20 calls -> S2 (and S2r) costlier than S1 on >=2 of 3 regimes?
    print("\n=== H1: sessions with >=20 LLM calls, N in {25,50,100,150} ===")
    h1 = {}
    for p in ("P1", "P2", "P4"):
        for s in ("S2", "S2r"):
            ratios = []
            for n in (25, 50, 100, 150):
                for m in (3, 5, 10):
                    res = run(m, n, p, strats=["S1", s])
                    ratios += [a["cost"] / b["cost"] for a, b in zip(res[s], res["S1"]) if b["calls"] >= 20]
            lo, hi = boot_ci(ratios)
            frac = sum(r > 1 for r in ratios) / len(ratios)
            h1[f"{p}|{s}"] = dict(mean=st.mean(ratios), ci=[lo, hi], frac_costlier=frac, n=len(ratios))
            print(f"{p} {s:4}: mean {st.mean(ratios):.2f}x [{lo:.2f},{hi:.2f}]  costlier in {frac:.0%} of {len(ratios)}")
    out["H1"] = h1

    # TTL expiry sensitivity (single task, N=525, P1)
    for e in (0.0, 0.1, 0.3):
        res = run(1, 525, "P1", expire=e)
        m = {s: st.mean(r["cost"] for r in res[s]) for s in STRATS}
        out.setdefault("ttl", {})[e] = m
        print(f"expire={e}: " + " ".join(f"{s}={m[s] / m['S1']:.2f}" for s in STRATS))

    out["availability"] = availability()
    for k, (h, t) in out["availability"].items():
        print(f"availability {k:4}: {h}/{t} = {h / t:.1%}")
    q = churn()
    out["churn"] = q
    print(f"per-step churn q (single task, non-discovery calls): mean={st.mean(q):.2f} median={st.median(q):.2f}")
    json.dump(out, open(ROOT / "results/replay.json", "w"), indent=1)


def selfcheck():
    sess = session([TRACES[0]])
    cat = pick_catalog(sess, 525)
    s0, s1 = bill(sess, "S0", cat, "P1"), bill(sess, "S1", cat, "P1")
    assert s0["raw"] == s1["raw"] and s1["cost"] < s0["cost"] and s0["hit"] == 0
    tiny = dict(id="x", sys_tokens=100, events=[["A", 10, False, []]])
    W = PRICING["P1"][0]
    assert bill(tiny, "S1", cat, "P1")["cost"] == W * (tok(cat, FULL) + 100) + O * 10
    # chaining two identical-prefix sessions must never make static-cached cheaper per call than 1 task
    two = session([TRACES[0], TRACES[1]])
    assert bill(two, "S1", pick_catalog(two, 525), "P1")["calls"] > s1["calls"]


if __name__ == "__main__":
    selfcheck()
    main()
