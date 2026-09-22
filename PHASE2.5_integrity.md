# Stage 2.5: Integrity verification (pre-review)

Draft: `paper/main.tex` v0.1 · Date: 2026-09-19 · Verifier: Claude, working to the academic-pipeline integrity protocol

## Verdict: **PASS with 2 warnings.** No block.
None of the 7 failure modes is SUSPECTED. Modes 1, 3, 5 and 6 (the ones that block if evidence is missing) are CLEAR on evidence. Mode 4 carries a warning, and Mode 7 is CLEAR.

---

## A. Numbers (Modes 1, 3, 6)
`integrity_check.py` rebuilds **59 quantitative claims** from the saved results (`results/traces.json`, `replay.json`, `breakeven.json`, `sensitivity_output_price.json`) or from a deterministic re-run, and requires each to appear verbatim in `main.tex`.

| Run | Result | Action |
|---|---|---|
| 1st | 54/58 PASS | 4 numbers had been hand-computed from *rounded* table values: MAPE 7.2→**7.8%**, range 4–10→**4–11%**, P4 error 50→**51%**, gap 0.01→**0.02**. Text corrected to match the data. |
| 2nd | 58/58 PASS | Added the output-price sensitivity claim. |
| 3rd | **59/59 PASS** | |

Earlier Mode-1 catches during development, all fixed before drafting:
- Tool-name regex captured a trailing `\n`, so 0/222 retrieved tools matched the catalog. Caught by an assert; fixed.
- Churn of 0.36 was measured including discovery-only calls; the correct measure is 0.07.
- The break-even formula was off by ~40% because a derivation term was dropped; the exact form was restored. This is a correction, not a tuning step.
- A draft claim that "tail placement is ≤1.02× everywhere" was false under Gemini pricing (1.13×). Corrected.

## B. Citations (Mode 2)
All 22 references were verified against the primary source (arXiv abstract page, official docs or the GitHub issue) for title, authors, date and the specific claim the paper attributes to them.

| Ref | Check |
|---|---|
| RAG-MCP, MCP-Zero, Semantic Discovery, Tool Attention | Quantitative claims (>50%, 98%, 99.6%, 95%) match the abstracts |
| Don't Break the Cache | 41–80% savings; no retrieval methods tested; no cost model: confirmed from full text |
| TokenPilot, ReCache | Scope claims confirmed from full text / abstract |
| LiveMCPBench, MCP-Bench, MCP-Universe, MCP-AgentBench, Smelly, CE-MCP | Titles and authors verified |
| Provider docs (4) + pricing | Multipliers, minimums and prices verified 2026-09-19 |
| bifrost #7169 | "160 of 360 consecutive request pairs (44%)", verified on the issue page |
| oai_limit #2848 | Verified that the issue exists; the limit itself is tested live (E0) |
| **Dropped** | ComplexMCP "prompt billed 12×" claim: the abstract does not support it, so it was removed |

## C. Seven-mode AI research failure checklist

| Mode | Status | Evidence |
|---|---|---|
| 1 Implementation bug | **CLEAR** | 59/59 claims reproduce; self-check asserts in every script; the closed-form rule independently matches the replay (7.8% MAPE P1/P2), which a replay bug would be unlikely to produce |
| 2 Hallucinated citation | **CLEAR** | Section B |
| 3 Hallucinated result | **CLEAR** | Every number traces to a saved JSON file. The live section contains **no numbers**, only a PENDING tag |
| 4 Shortcut reliance | ⚠️ **WARNING** (flag only) | (a) Agent behaviour is held fixed across strategies. (b) Multi-task sessions are synthesized by chaining independent tasks. (c) S2r uses an optimistic retriever. All three are stated in Threats to Validity. The output-price assumption was tested (O=0/5/8) and does not change the winner. **Before Stage 3:** E3 (live accuracy) partly addresses (a); real multi-request conversation traces would address (b) and are future work |
| 5 Bug reframed as insight | **CLEAR** | The inversion was **predicted before any data** (Phase-1 model, pre-registered H1), not discovered after the fact. No "surprisingly"-style phrasing in the draft |
| 6 Methodology fabrication | **CLEAR** (1 fix) | Methods text audited against the code. Fixed "4,000–10,000 resamples" → "4,000" (the final code uses 4,000). Seeds, grid size (17), O=5, the tokenizer and session construction all match the code |
| 7 Frame-lock | **CLEAR** | The frame was actively revised: the single-task data contradicted the Phase-1 headline, so the claim moved from "Why" to "When" rather than the data being bent to fit |

## D. Open items carried to Stage 3
1. Live validation E0/E2/E3 (running now) → fill the PENDING section, then re-run `integrity_check.py` extended to the live numbers.
2. Author decisions: title "Why"→"When", affiliation, COI wording, repository URL.
3. Mode-4 warning: reviewers will likely ask for real multi-request conversation traces.

---

## E. Live-validation addendum (2026-09-22)
- Claim check extended to the live numbers: **68/68 reproduce verbatim**.
- **E0 refuted a cited claim.** 129 and 525 tools were both accepted; the "128-tool limit" citation was removed from the paper.
- **Mode 1 catch (live harness).** `max_output_tokens=16` made gpt-5-nano return `incomplete` with all-zero usage, so the first run silently measured nothing. Fixed (64 tokens + fail-fast assert); the failed run is kept as `results/live_failed_run1.json`.
- **Mode 1/3 catch (E3).** A multi-day, multi-batch E3 collection produced a degenerate 8.6% at N=16 (first tool picked 93/93). Not reproducible in fresh probes; E3 was re-collected in a single batch (71.0/61.3/54.3/40.9%) and the anomaly is reported in the paper as a reproducibility caveat. Old rows kept as `results/live_e3_runA.json`.
- **Bias direction documented.** Billed results favour the non-static strategies less than the replay predicts, so the reported crossover is conservative.
- Live spend: **$0.58** total across all runs.
