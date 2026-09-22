"""Analyze results/live.json (E0/E2/E3) -> results/live_summary.json + printed tables.

H2: replay's predicted input cost vs billed input cost per E2 sequence (MAPE), and whether
    strategy cost ratios (vs S1, same session) agree. Input-only, normalized to uncached price = 1,
    because E2 uses 16-token outputs instead of the recorded assistant outputs.
H4: tool-selection accuracy by candidate count N (Wilson 95% CI).
"""
import json, math, statistics as st
from pathlib import Path
import replay as RP

ROOT = Path(__file__).parent
R_NANO = 0.005 / 0.05                        # gpt-5-nano cached/uncached price ratio


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - h, c + h


def predicted_input_cost(session_id, strat, m=3, n=100):
    sess = next(s for s in RP.sessions(m) if s["id"] == session_id)
    saved, RP.O = RP.O, 0.0
    try:
        return RP.bill(sess, strat, RP.pick_catalog(sess, n), "P2")
    finally:
        RP.O = saved


def main():
    L = json.load(open(ROOT / "results/live.json"))
    out = {"E0": L.get("E0"), "spend_usd": L.get("spend_usd"), "calls": L.get("calls")}
    print("E0:", L.get("E0"))
    rows = L.get("E2", [])
    for r in rows:
        b = r["billed"]
        r["billed_cost"] = (b["input"] - b["cached"]) + R_NANO * b["cached"]
        r["billed_hit"] = b["cached"] / max(b["input"], 1)
        p = predicted_input_cost(r["session"], r["strat"])
        r["pred_cost"], r["pred_hit2"] = p["cost"], p["hit"]
    if rows:
        ape = [abs(r["pred_cost"] - r["billed_cost"]) / r["billed_cost"] for r in rows]
        out["H2_mape"] = st.mean(ape)
        print(f"E2 sequences={len(rows)}  H2 MAPE(pred vs billed input cost) = {st.mean(ape):.1%}")
        by = {}
        for r in rows:
            by.setdefault(r["strat"], []).append(r)
        base = {r["session"]: r for r in by.get("S1", [])}
        out["E2"] = {}
        for s, rs in by.items():
            br = [r["billed_cost"] / base[r["session"]]["billed_cost"] for r in rs if r["session"] in base]
            pr = [r["pred_cost"] / base[r["session"]]["pred_cost"] for r in rs if r["session"] in base]
            out["E2"][s] = dict(n=len(rs), billed_hit=st.mean(r["billed_hit"] for r in rs),
                                pred_hit=st.mean(r["pred_hit2"] for r in rs),
                                billed_ratio=st.mean(br) if br else None, pred_ratio=st.mean(pr) if pr else None)
            e = out["E2"][s]
            print(f"  {s:4} hit billed={e['billed_hit']:.0%} pred={e['pred_hit']:.0%}   "
                  f"cost vs S1 billed={e['billed_ratio']:.2f} pred={e['pred_ratio']:.2f}")
    e3 = L.get("E3", [])
    if e3:
        out["E3"] = {}
        for n in sorted({r["n"] for r in e3}):
            rs = [r for r in e3 if r["n"] == n]
            rs = [r for r in rs if r["ok"] is not None]; k = sum(r["ok"] for r in rs)
            lo, hi = wilson(k, len(rs))
            out["E3"][n] = dict(acc=k / len(rs), lo=lo, hi=hi, n=len(rs))
            print(f"E3 N={n:>3}: accuracy {k}/{len(rs)} = {k / len(rs):.1%}  [{lo:.1%}, {hi:.1%}]")
    json.dump(out, open(ROOT / "results/live_summary.json", "w"), indent=1)
    print(f"spend ${out['spend_usd']:.4f} over {out['calls']} calls")


if __name__ == "__main__":
    main()
