"""Closed-form break-even vs trace replay.

Rule (derived in paper Sec. 3): per-request retrieval (S2r) beats static-cached (S1) iff
    catalog_tokens - retrieved_tokens  >  (W - R) * h * T * (m - 1) / (2 * (R*T + W - R))
                                       ~= (W - R) / (2R) * h * (m - 1)          for large T
h = tokens appended to history per LLM call (ratio of totals), T = LLM calls per session,
m = tasks per session.
We compare the predicted break-even catalog size N* with the replay's (log-interpolated) N*.
"""
import json, math, statistics as st
from pathlib import Path
import replay as RP

ROOT = Path(__file__).parent
GRID = (10, 15, 20, 25, 30, 40, 50, 60, 80, 100, 125, 150, 200, 250, 300, 400, 525)


def h_bar():
    """Mean tokens appended per non-discovery LLM call (user msg + tool results + assistant output)."""
    calls = added = 0
    for t in RP.TRACES:
        calls += sum(1 for e in t["events"] if e[0] == "A" and not e[2])
        added += t["question_tokens"] + sum(e[1] for e in t["events"]
                                            if e[0] == "T" or (e[0] == "A" and not e[2]))
    return added / calls, calls / len(RP.TRACES)


def retrieved_tokens():
    return st.mean(RP.tok({k for e in t["events"] if e[0] == "R" for k in e[2]}, RP.FULL) for t in RP.TRACES)


def catalog_tokens(n):
    return st.mean(RP.tok(RP.pick_catalog(s, n), RP.FULL) for s in RP.sessions(1))


def replay_breakeven(m, p):
    prev = None
    for n in GRID:
        res = RP.run(m, n, p, strats=["S1", "S2r"])
        r = st.mean(a["cost"] / b["cost"] for a, b in zip(res["S2r"], res["S1"]))
        if r < 1:
            if prev is None:
                return n
            n0, r0 = prev                                 # log-linear interpolation to ratio = 1
            f = math.log(r0) / (math.log(r0) - math.log(r))
            return math.exp(math.log(n0) + f * (math.log(n) - math.log(n0)))
        prev = (n, r)
    return None


def main():
    (h, c), b = h_bar(), retrieved_tokens()
    cat = sorted((n, catalog_tokens(n)) for n in GRID)

    def tokens_to_n(x):                                   # invert catalog_tokens(n) by interpolation
        for (n0, c0), (n1, c1) in zip(cat, cat[1:]):
            if c0 <= x <= c1:
                return n0 + (x - c0) / (c1 - c0) * (n1 - n0)
        return None

    print(f"h={h:.0f} tokens/call  calls/task={c:.1f}  retrieved set={b:.0f} tokens")
    rows = []
    for p in ("P1", "P2", "P4"):
        W, R, _ = RP.PRICING[p]
        for m in (2, 3, 5, 10):
            T = c * m
            pred_tok = b + (W - R) * h * T * (m - 1) / (2 * (R * T + W - R))
            pred_n, obs_n = tokens_to_n(pred_tok), replay_breakeven(m, p)
            rows.append(dict(p=p, m=m, pred_tokens=pred_tok, pred_n=pred_n, replay_n=obs_n))
            fmt = lambda x: f"{x:6.0f}" if x else "   n/a"
            print(f"{p} m={m:>2}: predicted N*={fmt(pred_n)} ({pred_tok:,.0f} tok)   replay N*={fmt(obs_n)}")
    ok = [r for r in rows if r["pred_n"] and r["replay_n"]]
    mape = st.mean(abs(r["pred_n"] - r["replay_n"]) / r["replay_n"] for r in ok)
    print(f"MAPE(predicted vs replay break-even N) over {len(ok)} cells = {mape:.1%}")
    json.dump(dict(h=h, calls_per_task=c, retrieved_tokens=b, rows=rows, mape=mape),
              open(ROOT / "results/breakeven.json", "w"), indent=1)


if __name__ == "__main__":
    main()
