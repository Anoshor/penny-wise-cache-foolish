# Stage 4–5: Revision log and finalization

Manuscript: v0.2 → **v1.0** (15 pp) · Date: 2026-09-23 · All 76 quantitative claims verified by `integrity_check.py`

## Response to the review (R = reviewer point, A = action, C = consequence)

| # | Reviewer point | Action | Consequence |
|---|---|---|---|
| **CRITICAL-A** | Live billing contradicts the "placement beats retrieval" ranking | New §5.10 "What the billed data do and do not confirm"; the §5.4 claim is now explicitly scoped to the replay grid; abstract qualified | **Addressed.** The paper no longer presents an unbilled ranking as its main advice |
| **MAJOR-1** | Overlapping sessions make CIs too narrow | Rebuilt the grid from **disjoint** sessions (no task reused); headline CI now 1.60× [1.45, 1.74] | **Addressed.** Claim survives valid inference; intervals widened as predicted |
| **MAJOR-2** | Behaviour invariance is load-bearing | Accuracy-coupled cost model added (§5.9) | **Addressed, and it went against us.** Pricing selection errors *shrinks* the inversion region (S2 1.62→1.38 at N=100; 1.23→0.97 at N=200). Reported as a limit, not as support |
| **MAJOR-3** | S2r uses an oracle retriever | Implemented BM25 over names, descriptions and parameter names | **Addressed, with a striking result.** BM25 top-5 contains the needed tool in only **18.3%** of executions (oracle 99.2%, trace router 64.8%). Cost is unchanged; the paper now states its retrieval costs are generous to retrieval |
| **MAJOR-D** | Per-strategy divergence between predicted and billed | Stated prominently in §5.10 (S4 0.66 predicted vs 1.08 billed, 64% error) | Addressed |
| **MAJOR-12 / MINOR-E** | Promote serialization; 44% is single-sourced | Now contribution 5, with the rate framed as an illustrative input | Addressed |
| **MODERATE-4** | H2 covers one cell | Scope stated in the abstract, Methods and Threats | Addressed |
| **MODERATE-13/14, MINOR-7** | Decision procedure, money anchor, stakeholders | Added to Discussion: threshold procedure (~24 average tools per extra request here); $27.65 / $44.73 / $22.68 per 1,000 ten-task sessions; paragraphs for MCP server authors and providers | Addressed |
| **MINOR-6** | "(pending)" heading, 16 vs 64 output tokens | Fixed | Addressed |
| **MAJOR-B** | H1's window presupposes the regime | Threats now state H1 tests a regime, not the ecosystem | Addressed in text |
| **MAJOR-C** | E3 gold label and random distractors | Stated as a limitation; "correct server" scoring deferred | **Partly addressed** (acknowledged limitation) |
| **MAJOR-8 / MODERATE-9 / MODERATE-10** | Serving-side caching literature, tool-selection literature, cite the MCP spec | **Not done.** Requires searching and verifying new citations; the integrity rule forbids citing from memory | **Open for v1.1** |
| **DA counter-argument** | Prevalence of prefix-resident retrieval is unevidenced | **Not done.** A survey of open-source MCP clients is the right fix | **Open for v1.1** |
| **P2-14** | Schema-trimming baseline | Not done | Open, journal version |

## Stage 5 finalization
- Title banner: **Preprint v1.0**, 2026-09-23.
- 15 pages, 4 figures, 6 tables, 22 references.
- `integrity_check.py`: **76/76** claims recomputed from saved results and matched verbatim.
- Compiles clean with tectonic; no unresolved references.

## Remaining blockers before posting (author only)
1. Title: keep "**When** Token-Optimal…"?
2. Affiliation line: "Independent Researcher"?
3. Competing-interests wording.
4. Public repository URL for the code and data release.

## Recommended for v1.1 (before journal submission)
Related-work paragraphs with verified citations (serving-side caching, tool selection, MCP spec); a survey of open-source MCP clients for prevalence and canonical ordering; "correct server" scoring for E3.
