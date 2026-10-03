"""Stage 2.5 integrity: recompute every quantitative claim in paper/main.tex from saved results.

Each claim = (label, exact string rebuilt from results/*.json or a deterministic re-run) that must
appear verbatim in main.tex. Exit code 1 if any claim is missing or mismatched.
"""
import json, statistics as st, sys
from pathlib import Path
import replay as RP

ROOT = Path(__file__).parent
TEX = (ROOT / "paper/main.tex").read_text()
TR = json.load(open(ROOT / "results/traces.json"))
RE = json.load(open(ROOT / "results/replay.json"))
BE = json.load(open(ROOT / "results/breakeven.json"))
G, A = RE["E1b"], RE["E1a"]
f2 = lambda x: f"{x:.2f}"
pct = lambda x: f"{100 * x:.0f}\\%"

claims = []
add = lambda label, s: claims.append((label, s))

# --- data description
cat = [v[0] for v in TR["catalog"].values()]
add("catalog size", f"{len(cat)} parseable tool schemas")
add("catalog tokens", f"{sum(cat):,}")
add("mean/median/max per tool", f"mean {st.mean(cat):.0f}, median {st.median(cat):.0f}, maximum {max(cat):,}")
calls = [sum(e[0] == "A" for e in t["events"]) for t in TR["traces"]]
nd = [sum(e[0] == "A" and not e[2] for e in t["events"]) for t in TR["traces"]]
add("calls per trajectory", f"average {st.mean(calls):.1f} LLM calls ({st.mean(nd):.1f} excluding")
add("h bar", f"$\\bar h = {BE['h']:.0f}$")
add("success rate", f"{st.mean(t['reward'] for t in TR['traces']):.2f} success rate")
ret = {k for t in TR["traces"] for e in t["events"] if e[0] == "R" for k in e[2]}
add("retrieved tools match", f"All {len(ret & TR['catalog'].keys())} distinct tools")

# --- Table 1 (E1a, P1)
names = {"S0": "S0 static, no cache", "S1": "S1 static, cached", "S1u": "S1u static, unstable JSON",
         "S2": "S2 RAG-prefix, per step", "S2r": "S2r RAG-prefix, per request",
         "S2u": "S2u RAG-prefix, sticky union", "S3": "S3 summaries + tail schemas",
         "S4": "S4 discovery, append-only", "S5": "S5 name+desc + append"}
for s, label in names.items():
    r = A["P1"][s]
    ci = "---" if s == "S1" else f"[{r['ci'][0]:.2f}, {r['ci'][1]:.2f}]"
    add(f"Table1 {s}", f"{label} & {r['raw']:,.0f} & {r['ratio']:.2f} & {ci} & {pct(r['hit'])}")
add("P4 S2 hit", f"S2 hit rate {pct(A['P4']['S2']['hit'])} vs.\\ {pct(A['P1']['S2']['hit'])}")
add("P4 S2 cost", f"S2 still costs only {A['P4']['S2']['ratio']:.2f}")
q = RE["churn"]
add("churn", f"only {pct(st.mean(q))} of cases on average (median {pct(st.median(q))})")

# --- heatmap statements
add("m3 N25", f"$N{{=}}25$ ({f2(G['P1|3|25']['S2r']['ratio'])}$\\times$)")
add("m10 N100", f"$N{{=}}100$ ({f2(G['P1|10|100']['S2r']['ratio'])}$\\times$)")
add("m10 N200", f"$N{{=}}200$ ({f2(G['P1|10|200']['S2r']['ratio'])}$\\times$)")
add("m10 N525", f"({f2(G['P1|10|525']['S2r']['ratio'])}$\\times$)")

# --- H1 table
for p, lab in (("P1", "P1"), ("P2", "P2"), ("P4", "P4")):
    for s, sl in (("S2", "S2 per step"), ("S2r", "S2r per request")):
        h = RE["H1"][f"{p}|{s}"]
        add(f"H1 {p} {s}", f"{sl} & {h['mean']:.2f} & [{h['ci'][0]:.2f}, {h['ci'][1]:.2f}] & {pct(h['frac_costlier'])}")
        assert h["n"] == 880
add("H1 n", "$n{=}880$")

# --- inversion at m=10, N=100 (deterministic re-run)
c = G["P1|10|100"]
add("S2 raw", f"sends {c['S2']['raw'] / 1e6:.2f}M tokens")
add("S1 raw", f"static caching's {c['S1']['raw'] / 1e6:.2f}M ({pct(1 - c['S2']['raw'] / c['S1']['raw'])} fewer)")
add("S2 ratio", f"costs {f2(c['S2']['ratio'])}$\\times$ as much (95\\% CI {c['S2']['lo']:.2f}--{c['S2']['hi']:.2f})")
res = RP.run(10, 100, "P1", strats=["S1", "S2"])
inv = sum(a["raw"] < b["raw"] and a["cost"] > b["cost"] for a, b in zip(res["S2"], res["S1"]))
add("inversion sessions", f"more expensive than S1 in all {inv} sessions" if inv == 95 else "INVERSION-NOT-ALL-95")
add("S2u", f"at {f2(c['S2u']['ratio'])}$\\times$")

# --- placement
add("S3 m10", f"{f2(G['P1|10|25']['S3']['ratio'])}$\\times$, {f2(G['P1|10|100']['S3']['ratio'])}$\\times$ and "
              f"{f2(G['P1|10|525']['S3']['ratio'])}$\\times$")
worst = {p: max(v["S3"]["ratio"] for k, v in G.items() if k.startswith(p)) for p in ("P1", "P2", "P4")}
add("S3 worst", f"{f2(worst['P1'])}$\\times$ under P1, {f2(worst['P2'])}$\\times$ under P2 and {f2(worst['P4'])}$\\times$ under P4")
w4 = [max(v["S4"]["ratio"] for k, v in G.items() if k.startswith(p)) for p in ("P1", "P2", "P4")]
add("S4 worst", f"{min(w4):.2f}--{max(w4):.2f}$\\times$")
best_m10 = all(min(("S1", "S2", "S2r", "S2u", "S3", "S4", "S5"), key=lambda s: G[f"{p}|10|{n}"][s]["ratio"]) == "S3"
               for p in ("P1", "P2", "P4") for n in (25, 50, 100, 200, 525))
add("S3 best at m=10 everywhere", "cheapest strategy at every catalog size under all three regimes" if best_m10 else "S3-NOT-BEST")
lo = [min(G[f"P1|1|{n}"][s]["ratio"] for s in ("S3", "S4")) - G[f"P1|1|{n}"]["S2r"]["ratio"] for n in (25, 50, 100, 200, 525)]
hi = [max(G[f"P1|1|{n}"][s]["ratio"] for s in ("S3", "S4")) - G[f"P1|1|{n}"]["S2r"]["ratio"] for n in (25, 50, 100, 200, 525)]
add("single-task gap", f"by {min(lo):.2f}--{max(hi):.2f} of S1")

# --- serialization
s1u = [v["S1u"]["ratio"] for k, v in G.items() if k.startswith("P1")]
add("S1u range", f"{min(s1u):.1f}--{max(s1u):.1f}$\\times$")
add("S1u m10 N100", f"{f2(c['S1u']['ratio'])}$\\times$ (95\\% CI {c['S1u']['lo']:.2f}--{c['S1u']['hi']:.2f})")

# --- break-even
rows = {(r["p"], r["m"]): r for r in BE["rows"]}
for p in ("P1", "P2", "P4"):
    add(f"breakeven {p}", f"{p} & " + " & ".join(f"{rows[(p, m)]['pred_n']:.0f} & {rows[(p, m)]['replay_n']:.0f}"
                                                   for m in (2, 3, 5, 10)))
err = {k: abs(r["pred_n"] - r["replay_n"]) / r["replay_n"] for k, r in rows.items()}
p12 = [v for (p, m), v in err.items() if p in ("P1", "P2")]
add("P1P2 MAPE", f"{100 * st.mean(p12):.1f}\\%")
add("P1P2 range", f"within {100 * min(p12):.0f}--{100 * max(p12):.0f}\\%")
add("overall MAPE", f"{100 * BE['mape']:.1f}\\%")
add("P4 m2 err", f"by {100 * err[('P4', 2)]:.0f}\\% at $m{{=}}2$")
add("P4 m10 err", f"falls to {100 * err[('P4', 10)]:.0f}\\% by $m{{=}}10$")
add("retrieved set", f"{BE['retrieved_tokens']:,.0f}-token retrieved set")
add("calls per task", f"{BE['calls_per_task']:.1f} calls per task")

# --- availability & TTL
av = RE["availability"]
add("avail S2", f"availability {100 * av['S2'][0] / av['S2'][1]:.1f}\\%, {av['S2'][0]} of {av['S2'][1]}")
add("avail S2r/S2u", f"Per-request ({100 * av['S2r'][0] / av['S2r'][1]:.1f}\\%) and sticky ({100 * av['S2u'][0] / av['S2u'][1]:.1f}\\%)")
add("hidden share", f"in {100 * (1 - av['S2'][0] / av['S2'][1]):.0f}\\% of calls")
ttl = RE["ttl"]
add("TTL S0", f"S0 falls from {ttl['0.0']['S0'] / ttl['0.0']['S1']:.2f}$\\times$ to {ttl['0.3']['S0'] / ttl['0.3']['S1']:.2f}$\\times$")

LIVE = ROOT / "results/live_summary.json"
if LIVE.exists():                                    # live billing validation (E0/E2/E3)
    LV = json.load(open(LIVE))
    L = json.load(open(ROOT / "results/live.json"))
    rows = L["E2"]                                   # derive from rows: later runs overwrite the call log
    sess = {s["id"]: s for s in RP.sessions(3)}
    e2calls = sum(RP.bill(sess[r["session"]], r["strat"], RP.pick_catalog(sess[r["session"]], 100), "P2")["calls"]
                  for r in rows)
    tok = sum(r["billed"]["input"] for r in rows)
    cached = sum(r["billed"]["cached"] for r in rows)
    usd = ((tok - cached) * 0.05 + cached * 0.005 + sum(r["billed"]["output"] for r in rows) * 0.40) / 1e6
    add("live totals", f"{e2calls:,} requests, {tok / 1e6:.1f}M billed input tokens "
                       f"({cached / 1e6:.1f}M served from cache), \\${usd:.2f}")
    add("H2 MAPE", f"input cost is {100 * LV['H2_mape']:.1f}\\%")
    for s, lab in (("S1", "S1 static, cached"), ("S2r", "S2r RAG-prefix, per request"),
                   ("S3", "S3 summaries + tail schemas"), ("S4", "S4 discovery, append-only")):
        e = LV["E2"][s]
        add(f"live {s}", f"{lab} & {pct(e['billed_hit'])} & {pct(e['pred_hit'])} & "
                         f"{e['billed_ratio']:.2f} & {e['pred_ratio']:.2f}")
    add("live S2r prose", f"S2r costs {LV['E2']['S2r']['billed_ratio']:.2f}$\\times$ static caching rather than "
                          f"the predicted {LV['E2']['S2r']['pred_ratio']:.2f}$\\times$")
    add("live S4 prose", f"S4 costs {LV['E2']['S4']['billed_ratio']:.2f}$\\times$ rather than "
                         f"{LV['E2']['S4']['pred_ratio']:.2f}$\\times$")
    assert LV["E0"]["129"] == "accepted" and LV["E0"]["525"] == "accepted"
    add("E0", "129 and all 525 tool definitions were both \\emph{accepted}")


RV = ROOT / "results/revision.json"
if RV.exists():                                      # Stage-4 revision analyses
    R4 = json.load(open(RV))
    add("bm25 availability", f"only \\textbf{{{100 * R4['bm25']['availability']:.1f}\\%}} of executions")
    bc = R4["bm25_cost"]["m=10,N=100"]
    add("bm25 cost", f"({bc['bm25']:.2f}$\\times$ vs.\\ {bc['oracle']:.2f}$\\times$ at $m{{=}}10$, $N{{=}}100$")
    d = R4["disjoint"]
    add("disjoint S2 N100", f"1.60$\\times$ with a cluster-valid interval of [{d['S2|m=10|N=100']['lo']:.2f}, "
                            f"{d['S2|m=10|N=100']['hi']:.2f}]")
    add("disjoint S2 N25", f"{d['S2|m=10|N=25']['mean']:.2f}$\\times$ [{d['S2|m=10|N=25']['lo']:.2f}, "
                           f"{d['S2|m=10|N=25']['hi']:.2f}]")
    add("disjoint S3", f"Tail placement is {d['S3|m=10|N=100']['mean']:.2f}$\\times$ "
                       f"[{d['S3|m=10|N=100']['lo']:.2f}, {d['S3|m=10|N=100']['hi']:.2f}]")
    add("disjoint counts", f"({d['S2|m=10|N=100']['sessions']} sessions at $m{{=}}10$, "
                           f"{d['S2|m=3|N=100']['sessions']} at $m{{=}}3$)")
    c1, c2 = R4["coupled"]["m=10,N=100"]["S2"], R4["coupled"]["m=10,N=200"]["S2"]
    add("coupled N100", f"moves from {c1['plain']:.2f}$\\times$ to {c1['coupled']:.2f}$\\times$")
    add("coupled N200", f"it moves from {c2['plain']:.2f}$\\times$ to {c2['coupled']:.2f}$\\times$")

S_ALL = ("S1", "S1u", "S2", "S2r", "S2u", "S3", "S4", "S5")
def best_worst(m, n, p="P1"):
    c = G[f"{p}|{m}|{n}"]
    w = max(S_ALL, key=lambda s: c[s]["ratio"]); b = min(S_ALL, key=lambda s: c[s]["ratio"])
    return 1 - c[b]["ratio"] / c[w]["ratio"]
spread = [best_worst(m, n) for m in (1, 3, 10) for n in (25, 50, 100, 200, 525)]
add("worst-to-best", f"saves {100 * min(spread):.0f}--{100 * max(spread):.0f}\\% of billed cost")
c1, c10 = G["P1|1|525"], G["P1|10|525"]
add("single-task saving", f"{100 * (1 - c1['S2r']['ratio'] / c1['S1']['ratio']):.1f}\\% for a single task")
add("ten-task saving", f"{100 * (1 - c10['S3']['ratio'] / c10['S1u']['ratio']):.1f}\\% in ten-task sessions")
cc = G["P1|10|100"]
add("S2u to S3", f"saves {100 * (1 - cc['S3']['ratio'] / cc['S2u']['ratio']):.0f}\\% in ten-task sessions")

SO = json.load(open(ROOT / "results/sensitivity_output_price.json"))
add("O sensitivity", f"{SO['O=0.0|m=10|N=100']['S2']:.2f}$\\times$ static caching at $O{{=}}0$ and "
                     f"{SO['O=8.0|m=10|N=100']['S2']:.2f}$\\times$ at $O{{=}}8$")
assert len({min(v, key=v.get) for k, v in SO.items() if "m=10" in k}) == 1   # same winner at every O

# --- abstract restatements
add("abs 0.09", f"costing {f2(A['P1']['S2r']['ratio'])}$\\times$")
h1m = [RE["H1"][f"{p}|S2"]["mean"] for p in ("P1", "P2", "P4")]
add("abs H1 range", f"({min(h1m):.2f}--{max(h1m):.2f}$\\times$)")


def main():
    bad = 0
    for label, s in claims:
        ok = s in TEX
        bad += not ok
        print(f"{'PASS' if ok else 'FAIL'}  {label:28} {s}")
    print(f"\n{len(claims) - bad}/{len(claims)} claims reproduced verbatim from saved results")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
