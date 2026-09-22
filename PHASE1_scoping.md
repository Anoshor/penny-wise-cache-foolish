# Penny-Wise, Cache-Foolish: Why Token-Optimal MCP Tool Retrieval Isn't Cost-Optimal

**Phase 1: Scoping.** Research question brief, gap confirmation, pilot model, methodology blueprint, first devil's-advocate check.
Pipeline: `academic-pipeline` → Stage 1 `deep-research` (full mode) · Date: 2026-09-19 · Status: **waiting for author confirmation**

---

## 0. Title check

| Query (Google Scholar, 2026-09-19) | Result |
|---|---|
| `Why Token-Optimal MCP Tool Retrieval Isn't Cost-Optimal` | No match |
| `"Token-Optimal" "Cost-Optimal" tool retrieval` | No match |
| `"Penny-Wise, Cache-Foolish"` | No match |

Scholar lags arXiv by a few weeks, so search arXiv again right before submitting.

---

## 1. Correction to the earlier gap claim ⚠️

The first-pass scan said *"no paper counts cost with cached-token pricing."* **That is wrong.** Closer reading found four pieces of work that touch the problem:

| Work | What it does | What it does **not** do |
|---|---|---|
| **Don't Break the Cache** (arXiv 2601.06007) | Real API runs on OpenAI, Anthropic and Google; 500 sessions on DeepResearch Bench; compares four cache-placement strategies; caching saves 41–80% of cost. Qualitatively advises "avoiding dynamic traditional function calling". | Evaluates **no** tool-retrieval method (not RAG-MCP, MCP-Zero, tool search or `defer_loading`). **No analytical cost model or break-even formula.** Fixed tool set. |
| **Tool Attention** (arXiv 2604.21816) | Puts full schemas just before the user message to protect the cache: 84% cache hit rate vs 22% for naive injection. | Cost, latency and success are **projected, not measured**: no live API calls, a synthetic 120-tool testbed, 2024 pricing, no comparison with provider-native tool search. |
| **TokenPilot** (arXiv 2606.17016) | Moves tool definitions later in the prompt to keep the prefix stable. Uses **real** cache-hit fields from the API; saves 56–87% of cost. | One model (GPT-5.4-mini), a general context-management framing, **no head-to-head of MCP retrieval methods**, no break-even analysis. |
| **ReCache** (arXiv 2608.19662) | KV blocks that stay valid when tools are recombined, for self-hosted serving. | Serving-side only. Doesn't apply to API users, who pay provider cache prices. |
| **Provider tool search** (Anthropic and OpenAI `defer_loading`) | Deferred tools are left out of the prefix; discovered tools are expanded inline, which **preserves the cache** (Anthropic docs). | Vendor documentation, not an independent evaluation. No published cost or accuracy comparison against the academic retrievers. |

### Refined gap (what's actually still open)

1. **No closed-form cost model** of MCP tool-exposure strategies under prefix-cache pricing, and no break-even conditions telling you when retrieval pays off.
2. **No measured, multi-provider comparison** of the strategy families on the same MCP benchmark using billed token counts (cache read and write fields): static loading, retrieval into the prefix (RAG-MCP style), tail placement (Tool Attention style), append-only / provider tool search, and code-mode.
3. **No evidence of ranking inversion.** Every retrieval paper (RAG-MCP, MCP-Zero, the 99.6% vector-discovery paper) reports *raw token reduction* as its headline cost metric. Nobody has shown that the method with the fewest tokens can be the most expensive.

The paper is still new, but its claim changes from "nobody considered caching" to **"the field optimizes the wrong metric, and here's the model plus measurements that show when and by how much."**

---

## 2. Pilot result from the analytical model (`cost_model.py`)

The model is deterministic and normalized to an uncached input price of 1.0. It uses Anthropic's multipliers: cache write 1.25×, cache read 0.1× (**verified in the docs; OpenAI GPT-5.6+ uses the same 1.25× / 0.1×**). The other assumptions are 400 tokens per schema, k = 5, 1,500 new tokens per turn, and q = the chance that the retrieved tool set changes between turns.

**Finding A: ranking inversion.** `rag_prefix` always sends the **fewest raw tokens** but is often the **most expensive**:

| N tools | Turns | q | rag_prefix raw tokens | rag_prefix cost vs static_cached |
|---|---|---|---|---|
| 100 | 30 | 1.0 | **818k** (vs 1,958k) | **3.45× more expensive** |
| 20 | 30 | 1.0 | 818k (vs 998k) | **6.27×**, worse than **not caching at all** (6.12×) |
| 100 | 15 | 0.44 | 240k (vs 810k) | 1.05× (break-even) |

**Why:** the cache prefix runs tools → system → messages. Every time the tool set changes, **the whole conversation history** gets re-written at the 1.25× write price, not just the tool block. The saving grows linearly with catalog size; the penalty grows with history length, so it compounds over turns.

**Finding B: the break-even catalog size grows with conversation length.**

| q | T=5 | T=10 | T=20 | T=40 |
|---|---|---|---|---|
| 0.2 | 16 | 33 | 71 | 154 |
| 0.44 (the churn rate observed in the bifrost issue) | 29 | 66 | **150** | 331 |
| 1.0 (re-retrieve every turn) | 60 | 144 | 335 | 746 |

Below these catalog sizes, **loading every tool and caching it is cheaper than retrieving.**

**Finding C: placement matters more than retrieval.** `defer_append` (provider tool search) and `summary_tail` (Tool Attention) win in almost every cell: 0.07–0.57× static cost at N ≥ 100. The exception is `defer_append` with small catalogs and long sessions (N=20, T=30, q=1: 1.34×), because appended definitions pile up in the history.

> **Suggested one-line thesis:** *Retrieval decides **how many** tool tokens you send; cache placement decides **how much you pay** for them. The field optimized the first and ignored the second.*

The model's limits (tested empirically in Phase 3): constant tokens per turn, no cache expiry (TTL), no minimum cacheable length, output tokens excluded, **accuracy not modelled**.

---

## 3. Research Question Brief

**Main RQ.** Under current provider prefix-cache pricing, how do MCP tool-exposure strategies compare on *billed cost per successful task*, and under what conditions (catalog size N, session length T, tool-set churn q) does token-minimizing retrieval become cost-dominated?

| Sub-RQ | Question | Answered by |
|---|---|---|
| **RQ1** | Does ranking inversion (fewest tokens ≠ lowest cost) happen with **real billing** across providers? | Live runs, usage fields |
| **RQ2** | How accurately does a closed-form model predict measured cost, and what are the break-even conditions? | Model vs measured; mean absolute percentage error (MAPE) |
| **RQ3** | What does the cost–accuracy Pareto frontier look like? Do cache-aware placements (tail, append-only, provider tool search) dominate? | Success rate vs $/task |

### FINER score

| Criterion | Score (1–5) | Note |
|---|---|---|
| Feasible | 5 | API calls only, public benchmark, no GPU |
| Interesting | 5 | Counter-intuitive, affects every MCP deployment |
| Novel | 4 | Gap confirmed but narrow; Don't Break the Cache and TokenPilot are close neighbours and must be cited up front |
| Ethical | 5 | No human subjects or private data |
| Relevant | 5 | Direct cost guidance for practitioners and protocol designers |

### Scope
- **In scope:** MCP tool definitions in API-served models; Anthropic, OpenAI and Google pricing; single-agent multi-turn sessions.
- **Out of scope:** self-hosted KV serving (ReCache), tool-output compression, multi-agent systems, security.

---

## 4. Hypotheses (pre-registered before any live run)

- **H1:** For N ≤ 150 and T ≥ 20, `rag_prefix` has a higher billed cost per task than `static_cached` on at least 2 of 3 providers.
- **H2:** The analytical model predicts measured per-session cost within 20% MAPE once q is set from observed churn.
- **H3:** Cache-aware placement (`summary_tail`, `defer_append`) is on the cost–accuracy Pareto frontier for N ≥ 100.
- **H4:** `static_cached` loses accuracy relative to retrieval as N grows. This is the counter-force that stops "just load everything" from being the answer; if H4 fails, the paper's advice gets simpler.

---

## 5. Methodology Blueprint

**Paradigm:** positivist, quantitative. **Design:** controlled comparative experiment plus analytical model validation.

### 5.1 Strategies (independent variable)

| ID | Strategy | Stands for |
|---|---|---|
| S0 | Static, all tools, no cache | Lower bound (cache disabled) |
| S1 | Static, all tools, cached | Naive production default |
| S2 | Per-turn top-k retrieval in the prefix | RAG-MCP / MCP-Zero family |
| S3 | Summaries in prefix + full schemas at the tail | Tool Attention layout |
| S4 | Provider-native tool search (`defer_loading`) | Anthropic / OpenAI |
| S5 *(optional)* | Code-mode | Anthropic "code execution with MCP" pattern |

### 5.2 Benchmark
- **Primary:** LiveMCPBench (95 tasks, 70 servers, 527 tools). It has a large catalog, which is what this paper needs.
- **Fallback:** MCP-Bench (arXiv 2508.20453), if too many LiveMCPBench servers need paid API keys.
- **Catalog-size sweep:** subsample the tool pool to N ∈ {20, 50, 100, 250, 527}. Every task's gold tools always stay in the pool.

### 5.3 Models: one lower-cost model per provider
- Anthropic (Haiku or Sonnet tier), OpenAI (a GPT-5.6+ mini tier, 0.1× cache read), Google (Flash tier; cached price $0.075/M vs $0.75/M on Gemini 3.8 Flash, verified 2026-09-19).
- Exact model IDs are fixed at the Phase 2 pilot and recorded with their prices on the run date.

### 5.4 Metrics
- **Cost:** taken from the usage fields in API responses (Anthropic: `cache_creation_input_tokens`, `cache_read_input_tokens`, `input_tokens`; the OpenAI and Google equivalents) multiplied by the list price on the run date. **Never estimated.**
- **Raw tokens** (what earlier papers report), to show the inversion.
- **Success rate** (the benchmark's judge), **$ per successful task**, time to first token (TTFT), cache hit rate, and observed churn q.

### 5.5 Cheap-by-design protocol
1. **Pilot:** 10 tasks × 6 strategies × 1 model to calibrate token counts, q and cost per session.
2. **Main:** 95 tasks × 5 strategies × 3 providers × 2 repeats, at one catalog size (N=527).
3. **N-sweep, offline:** replay recorded traces through the analytical model at each N instead of re-running live. Only S1 and S2 are checked live at N ∈ {20, 100} for validation. This saves roughly 70% of the budget.

### 5.6 Analysis
- Paired per-task differences, with 10k-resample bootstrap confidence intervals, on $/task and success.
- Pareto frontier plot for each provider.
- Model fit: MAPE between predicted and billed cost per session (H2).
- Sensitivity: q, TTL (inserting delays longer than 5 minutes), and the provider's minimum cacheable token count.

### 5.7 Threats to validity
- **Internal:** API nondeterminism and cache routing variance → 2 repeats, report variance. Provider-side changes during the run → timestamped logs, run everything within one week.
- **External:** one benchmark → the analytical model generalizes the results; say so plainly.
- **Construct:** list prices ≠ enterprise-discounted prices → report tokens by type so readers can reprice.
- **Obsolescence:** pricing changes → the model takes the multipliers W and R as parameters; the break-even formula stays useful even if prices change.

### 5.8 Budget: an order-of-magnitude estimate, to confirm at the pilot
About 1,900 live sessions. Assuming lower-cost model tiers and around 300k raw input tokens per session with caching, expect **roughly $200–500 in total**. The pilot (under about $20) will replace this guess with a measured figure before any large spend.

---

## 6. Devil's Advocate: Checkpoint 1

| # | Challenge | Severity | Response |
|---|---|---|---|
| 1 | "Providers already fixed this with `defer_loading`, so it's a solved problem." | **Major** | Partly true, and it becomes a *finding*: the paper supplies the independent evidence and cost model that vendor docs don't have. Most open-source MCP clients and gateways (the bifrost issue shows this) still churn the prefix. |
| 2 | "Don't Break the Cache already said to avoid dynamic tools." | **Major** | It said so without measuring or modelling it. We add retrieval methods, break-even conditions and accuracy. Cite it prominently in the Introduction as the direct motivation. |
| 3 | "Cost without accuracy is meaningless: static-all may fail tasks." | **Major** | That's why H4, RQ3 and the $/successful-task metric exist. The report must show the Pareto frontier, not cost alone. |
| 4 | "Constant tokens per turn and no TTL in the model." | Minor | Phase 3 checks the model against billed costs (H2); TTL sensitivity is in 5.6. |
| 5 | "One benchmark." | Minor | Keep MCP-Bench as a second benchmark if the budget allows; otherwise list it as a limitation. |
| 6 | Conflict of interest: the author works on an agentic AI platform. | Minor | Use no employer data, systems or internal findings. Write as an individual researcher using public benchmarks only, and add a COI statement. |

**Verdict: PASS with revisions.** No critical issues. Items 1–3 must be addressed in the Introduction and Related Work, not left as limitations.

---

## 7. Full paper breakdown: who does what

| Phase | What | Claude does | **You do** | Time |
|---|---|---|---|---|
| **1 Scoping** ✅ | RQs, gap, model, method | Everything in this document | **Approve (5 min)** | done |
| 2 Investigation | Verified bibliography, full literature matrix, harness design | Search, verify every citation, write the harness code (benchmark runner, 6 strategies, usage logger) | Add API keys to `.env`, approve the ~$20 pilot | 1–2 days |
| 3 Experiments | Pilot, then the main run | Run everything, log the usage fields, compute statistics and plots | Approve the main budget after seeing the pilot cost | about 1 week of mostly unattended runs |
| 4 Writing | Full draft (IMRaD) | `academic-paper` skill writes the draft, figures and tables | Read the draft; fix anything that doesn't sound like you | 2–3 days |
| 4.5 Integrity | Citation, claim and data check | `integrity_verification_agent` | Nothing | hours |
| 5 Review | Simulated peer review with 5 reviewers | `academic-paper-reviewer` | Choose which points to accept | 1 day |
| 6 Revise + finalize | Revision, LaTeX, PDF | Revision + LaTeX build | Final read, submit to arXiv (**you press submit**) | 1–2 days |

**Your total hands-on time is about 4–6 hours spread over 2–3 weeks.** Almost all of it is reading and approving.

---

## 8. Decisions needed from you

1. **Budget:** OK with about $20 for the pilot now, then a main-run budget decided from the measured pilot cost?
2. **Providers:** all three (Anthropic, OpenAI, Google), or only the ones you already have keys for?
3. **Target:** arXiv preprint first (recommended, since it's the fastest way to put a date on the finding), then pick a journal or workshop after reviews.

---

## 9. Bibliography: verification status

**Verified this session (full text or abstract fetched):**
- Don't Break the Cache: An Evaluation of Prompt Caching for Long-Horizon Agentic Tasks. arXiv:2601.06007. https://arxiv.org/abs/2601.06007
- Tool Attention Is All You Need: Dynamic Tool Gating and Lazy Schema Loading… arXiv:2604.21816. https://arxiv.org/abs/2604.21816
- TokenPilot: Cache-Efficient Context Management for LLM Agents. arXiv:2606.17016. https://arxiv.org/abs/2606.17016
- Fang, Wei, Hu & Shen (2026). ReCache: Efficient KV Cache Reuse and Compression for Tool-Augmented LLM Agents. arXiv:2608.19662. https://arxiv.org/abs/2608.19662
- Anthropic. Prompt caching (docs). https://platform.claude.com/docs/en/build-with-claude/prompt-caching
- Anthropic. Tool search tool (docs). https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-search-tool
- OpenAI. Prompt caching (docs). https://developers.openai.com/api/docs/guides/prompt-caching
- Google. Gemini API pricing. https://ai.google.dev/gemini-api/docs/pricing

**Found in search, full verification pending in Phase 2** (no reference goes into the paper until verified):
- RAG-MCP, arXiv:2505.03275 · MCP-Zero, arXiv:2506.01056 · Semantic Tool Discovery, arXiv:2603.20313
- LiveMCPBench (icip-cas.github.io/LiveMCPBench) · MCP-Bench, arXiv:2508.20453 · MCP-Universe, arXiv:2508.14704
- ComplexMCP, arXiv:2605.10787 · MCP-AgentBench, arXiv:2509.09734 · MCP Tool Descriptions Are Smelly!, arXiv:2602.14878
- OpenAI tool search docs (developers.openai.com/api/docs/guides/tools-tool-search) · bifrost issue #7169 (github.com/maximhq/bifrost/issues/7169)

---

*AI disclosure: Claude (Anthropic) did the literature search, analytical modelling and drafting in this phase, using the academic-research-skills pipeline. The author is responsible for every claim and decision.*
