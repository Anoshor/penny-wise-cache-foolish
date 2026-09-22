# Penny-Wise, Cache-Foolish

When token-optimal MCP tool retrieval isn't cost-optimal: a cost model and trace replay of MCP tool-exposure strategies under provider prompt caching.

**Status (2026-09-23):** preprint **v1.0** done → `paper/main.pdf` (15 pp). Pipeline stages 1–5 complete: scoping, experiments, draft, integrity (76/76 claims verified), simulated review, revision, finalization. Live validation spent $0.58. Blocked on four author decisions (see `PHASE4_revision_log.md`).

## Reproduce (zero API cost)
```bash
python3 -m venv .venv && .venv/bin/pip install matplotlib numpy tiktoken openai
git clone --depth 1 https://github.com/icip-cas/LiveMCPBench.git data/LiveMCPBench
.venv/bin/python extract_traces.py      # real token flows -> results/traces.json
.venv/bin/python replay.py              # E1 replay, 9 strategies x 4 pricing regimes -> results/replay.json
.venv/bin/python breakeven.py           # closed-form rule vs replay -> results/breakeven.json
.venv/bin/python figures.py             # paper/figs/
cd paper && tectonic main.tex           # paper/main.pdf
```

## Live validation (OpenAI gpt-5-nano, hard cap $1.50)
```bash
.venv/bin/python live_validate.py --selfcheck   # offline, fake client
.venv/bin/python live_validate.py               # dry run: plan + worst-case cost
.venv/bin/python live_validate.py --live        # real calls; key read from env only
```

## Files
| File | Purpose |
|---|---|
| `PHASE1_scoping.md` | Research questions, pre-registered hypotheses, method, first devil's-advocate check |
| `PHASE2_tree_of_thoughts.md` | Design decisions and the rejected alternatives |
| `cost_model.py` | Synthetic pilot model (Phase 1) |
| `extract_traces.py`, `replay.py`, `breakeven.py`, `figures.py` | Main zero-cost experiment |
| `live_validate.py` | E0 / E2 / E3 live checks |
| `revision.py` | BM25 retriever, accuracy-coupled cost, disjoint-session intervals |
| `integrity_check.py` | Recomputes every paper number from saved results |
| `PHASE3_review.md`, `PHASE4_revision_log.md` | Simulated peer review and the response to it |

## Data
`results/*.json` are derived from LiveMCPBench (Apache-2.0, https://github.com/icip-cas/LiveMCPBench): token counts and cost replays computed from its released trajectories and tool catalog. The benchmark itself is not redistributed here; the clone command above fetches it.
