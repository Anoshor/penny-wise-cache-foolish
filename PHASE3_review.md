# Stage 3: Simulated peer review (full panel)

Manuscript: `paper/main.tex` v0.2 (13 pp) · Target: arXiv cs.SE, journal later · Date: 2026-09-22

> **Panel provenance (required disclosure).** All five seats were executed by one model in one context, with role separation only. This is **not** independent review and gives no evidence of uncorrelated errors. Treat overlapping findings as one source, not five.

---

## Seat 1 — Journal-Fit Reviewer

**Fit.** Appropriate for arXiv cs.SE with a cs.AI cross-list. For a journal, the closest fits are venues that publish focused empirical systems studies; as written it is short for a full journal paper and would need a second benchmark or a second agent to carry one.

**Originality.** The gap is narrow but genuine and is stated honestly: prior work measures caching without retrieval methods (Don't Break the Cache), or projects costs without billing them (Tool Attention), or optimizes context generally (TokenPilot). The closed-form break-even rule is the most transferable contribution and is validated against both replay and billing.

**Significance.** The finding contradicts the headline metric of a whole line of papers, which is worth publishing even in preprint form. The serialization result may be the most immediately useful to practitioners.

**Findings**
- **MAJOR — contribution framing.** Contributions 1 and 3 are research claims; 4 is engineering guidance that partly restates vendor documentation. State explicitly what is new *relative to provider docs*: the docs assert that deferred loading preserves the cache; this paper is the first to quantify the cost of *not* doing so, and to give a break-even condition.
- **MINOR — venue signalling.** Add a one-line scope statement in the introduction: single-agent, API-billed, single-benchmark. Reviewers will otherwise assume broader claims.
- **MINOR — title.** "Penny-Wise, Cache-Foolish" is memorable and the "When…" subtitle now matches the evidence. Keep.

---

## Seat 2 — Reviewer 1 (Methodology)

**MAJOR-1 — Overlapping sessions inflate precision.** Sessions are formed by chaining tasks cyclically so that "each task starts exactly one session"; with m=10, each task therefore appears in ten sessions. The paired bootstrap resamples sessions as if independent, so the reported CIs (e.g., 1.60 [1.56, 1.65]) are too narrow. *Fix:* cluster bootstrap at the task level, or report a cluster-robust interval. The point estimates should survive; the intervals will widen.

**MAJOR-2 — Behaviour invariance is load-bearing, not merely a limitation.** The central number (1.60× at m=10, N=100) assumes the agent behaves identically under every exposure strategy. Section 5.8 now shows this is false in the direction that matters: selection accuracy drops from 71% to 41% as the exposed catalog grows, so a static-exposure agent would make more wrong calls and therefore *more* calls. *Fix:* add a bounded sensitivity analysis that couples E3 accuracy to call count (e.g., each wrong selection costs one extra call plus a retry), and report how the crossover moves. This strengthens the paper: the correction works against static caching, i.e., in the direction the authors already argue.

**MAJOR-3 — S2r is an oracle retriever.** The per-request tool set is the union of the *actual* route results for that task, which no real retriever could know in advance. This inflates both its availability (99.2%) and its cache stability. *Fix:* implement a concrete retriever (BM25 over tool names and descriptions, zero API cost) and re-run S2/S2r with it; report the delta.

**MODERATE-4 — Live validation covers one cell.** E2 tests m=3, N=100, one model, one provider. H2's "within 20% MAPE" is therefore a claim about that cell, not about the grid. Say so in the H2 statement.

**MODERATE-5 — TTL sensitivity is a free parameter.** Expiring the cache on a random 10%/30% of calls is not tied to wall-clock behaviour. Either derive expiry from observed tool-execution durations (if the traces carry timestamps) or present it as an illustrative bound only.

**MINOR-6 — Methods/Results inconsistency.** The methodology paragraph is still headed "Live validation (pending)" and says "with 16 output tokens", while Section 5.8 reports the run that used 64 (the 16-token setting is exactly what produced the zero-usage failure). Fix both.

**MINOR-7 — Report absolute money.** All costs are normalized. Add one anchor, e.g., dollars per 1,000 ten-task sessions at a named list price, so practitioners can size the effect.

---

## Seat 3 — Reviewer 2 (Domain)

**MAJOR-8 — Related work misses the serving-side caching literature.** ReCache is cited, but the broader prefix-caching and KV-reuse literature that motivates provider caching is absent. Add a short paragraph situating API-level prefix caching against serving-side prefix reuse, and state plainly that the paper's contribution is at the billing interface, where practitioners cannot change the serving stack. *Do not cite from memory: search and verify.*

**MODERATE-9 — Tool-selection literature.** The accuracy result (E3) connects to a substantial body of work on tool selection with large tool sets that the paper does not engage. At minimum, acknowledge it and explain why the paper's measurement is narrower (single gold tool, random distractors).

**MODERATE-10 — Cite the protocol, not only the announcement.** The MCP specification, including `tools/list_changed`, is referenced in the Discussion but cited only via the 2024 announcement. Cite the specification version used.

**MINOR-11 — Schema-size context.** The "Smelly descriptions" citation is used for description quality; it is also evidence about schema size, which directly drives the catalog-token term in the model. Make that link explicit.

---

## Seat 4 — Reviewer 3 (Perspective)

**MAJOR-12 — The serialization finding deserves to be a contribution, not a subsection.** A 1.7–4.8× penalty from non-deterministic JSON ordering dwarfs every strategy choice in the paper, and the fix is free. Promote it to the contribution list and the abstract's opening, and consider a short survey of open-source MCP clients and gateways to estimate how many are affected. That survey is zero-cost and would make the paper considerably more useful.

**MODERATE-13 — Give practitioners a decision procedure.** The break-even rule is stated as an inequality. Add a small table or five-line pseudocode: measure h̄ and m, compute the threshold, compare to catalog tokens, pick a layout.

**MODERATE-14 — Missing stakeholders.** The paper addresses client and gateway builders. Two other parties can act on these results: MCP *server* authors (schema verbosity directly sets the catalog term) and *providers* (who could guarantee canonical tool ordering, or bill tool blocks separately). One paragraph each.

**MINOR-15 — Reusable artifact.** The replay harness generalizes beyond this benchmark. Say that explicitly, and state what a user must supply to apply it to their own traces.

---

## Seat 5 — Devil's Advocate

### Strongest counter-argument
The paper's headline rests on a configuration that may be vanishing from practice. Both major providers now ship tool search that appends discovered schemas *after* the prefix precisely to protect the cache, and the paper's own data show that design is robust. So the expensive pattern the paper measures, re-selecting tools *into the prefix* across a long conversation, is one that vendor guidance already tells developers not to use. If practitioners follow the docs, the inversion never happens, and the contribution reduces to a quantification of a known anti-pattern. The paper's counter is that open-source clients still do it (the bifrost issue), but one issue in one gateway is thin evidence for prevalence. **Without evidence of how widespread prefix-resident retrieval actually is, the significance claim is unsupported.**

### Issue list
- **CRITICAL-A — The live data contradict the paper's central ranking, and the paper does not say so.** The Discussion claims placement beats retrieval, and Section 5.4 says S3 is cheapest in every ten-task configuration. But the only *billed* comparison (Table 5, m=3, N=100) puts S2r at 0.70 and S3 at 0.72: retrieval is at least as good as tail placement there, and the replay's predicted ordering (0.53 vs 0.51) does not hold up. The paper must either restrict the placement claim to the replay grid explicitly, or report the live ranking as a qualification in the Discussion. As written, a reader takes an unverified ranking as the paper's main advice.
- **MAJOR-B — H1's window was chosen where the effect lives.** H1 conditions on N ≤ 150 and T ≥ 20, but sessions only reach 20+ calls by synthetic chaining, and N ≤ 150 is the region where static caching is cheap. The pre-registration protects against post-hoc fitting, but not against a window that presupposes the answer. State that H1 tests a *regime*, not the ecosystem.
- **MAJOR-C — E3's gold label is one tool.** "Correct" means matching the first tool the recorded agent executed. Other tools in the catalog may serve the task equally well (three chart servers, several document servers), so the accuracy decline may partly measure ambiguity, not error. Random distractors also misrepresent real catalogs, which cluster by server. Caveat both, and consider scoring "correct server" as a secondary measure.
- **MAJOR-D — The replay's directional error is large where it matters most.** S4 was predicted at 0.66× and billed at 1.08×, a 64% relative error on the strategy that vendors actually ship. The paper reports the aggregate MAPE (17.4%) but not this per-strategy divergence prominently. A reader should be told that the model is least reliable exactly on append-only designs.
- **MINOR-E — "Serialization matters most" overreaches.** It is the largest effect *in this replay* under an assumed 44% churn taken from a single issue report. Present the rate as an illustrative input, not an empirical constant.

### Ignored alternatives
- Cost could be reduced by shrinking schemas (the Smelly-descriptions route) rather than by moving or retrieving them; the paper never compares against that baseline, though its own data (median 137 tokens, max 2,044) suggest the tail is fat.
- Code-execution designs are deferred to future work, yet they are the main competing answer to the same problem.

### Observations (non-defects)
- The pre-registration, the corrected derivation, the discarded anomalous batch and the 68/68 claim reproduction are unusually strong process controls for a preprint. Keep them visible: they are part of the paper's credibility.

---

## Editorial decision

**Decision: MAJOR REVISION.**

One DA-CRITICAL is validated (CRITICAL-A: the live billing result contradicts the ranking stated in the Discussion), which blocks acceptance until resolved. The methodology seat raises two further load-bearing issues (overlapping-session CIs; behaviour invariance now measurably false). None of these threatens the paper's core claim, which is the cost inversion in long sessions with moderate catalogs, and the fixes mostly *strengthen* it.

**Consensus across seats:** the contribution is real and the process is sound; the paper currently over-generalizes from the replay grid to practice.

**Disagreement:** Seat 1 and Seat 4 would accept the serialization result as a headline contribution; the Devil's Advocate considers its 44% churn input too weakly sourced to headline. Resolution: promote the finding, present the rate as an input parameter, and note the single-source provenance.

---

## Revision roadmap

### P0 — required before posting
| # | Item | Source | Effort |
|---|---|---|---|
| 1 | Reconcile the live ranking with the placement claim; restrict "S3 is cheapest" to the replay grid and report S2r ≈ S3 in the billed cell | CRITICAL-A | 1 h (text) |
| 2 | Cluster-bootstrap CIs by task, or report cluster-robust intervals; update every interval | MAJOR-1 | 2 h (code + text) |
| 3 | Fix the Methods/Results inconsistency: "(pending)" heading, 16 vs 64 output tokens | MINOR-6 | 10 min |
| 4 | State per-strategy divergence between predicted and billed, especially S4 (0.66 vs 1.08) | MAJOR-D | 30 min |
| 5 | Scope statement in the introduction and in the H2 claim (one cell, one model, one provider) | MODERATE-4, MINOR | 30 min |

### P1 — strongly recommended
| # | Item | Source | Effort |
|---|---|---|---|
| 6 | Accuracy-coupled cost sensitivity: use E3 accuracies to bound extra calls under static exposure, and show how the crossover moves | MAJOR-2 | 3 h (code) |
| 7 | Replace the oracle retriever with BM25 over names and descriptions; re-run S2/S2r; report the delta | MAJOR-3 | 3 h (code, zero API cost) |
| 8 | Caveat E3's single gold label and random distractors; add "correct server" as a secondary measure | MAJOR-C | 1 h |
| 9 | Promote serialization to a contribution; present 44% as an input; survey open-source MCP clients for canonical ordering | MAJOR-12, MINOR-E | 4 h |
| 10 | Related work: serving-side prefix caching, tool-selection literature; cite the MCP spec version (verify every new citation) | MAJOR-8, MODERATE-9, MODERATE-10 | 2 h |

### P2 — nice to have
| # | Item | Source | Effort |
|---|---|---|---|
| 11 | Decision procedure (table or pseudocode) for practitioners | MODERATE-13 | 1 h |
| 12 | Stakeholder paragraphs for MCP server authors and providers | MODERATE-14 | 1 h |
| 13 | Absolute dollar anchor per 1,000 sessions | MINOR-7 | 20 min |
| 14 | Schema-size baseline: what does trimming descriptions buy, versus moving them | DA alternatives | 3 h |

### Explicitly not recommended
- Adding a second benchmark before posting. It would delay the preprint; state single-benchmark scope instead and keep it as journal-version work.
- Extending to code-execution designs now. Different question, different harness.
