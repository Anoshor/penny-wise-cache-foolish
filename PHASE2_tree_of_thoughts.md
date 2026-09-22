# Phase 2: Tree-of-Thoughts design deliberation

Each design decision was developed as a tree: generate branches → score them (Feasibility, Validity, Cost, Novelty; 1–5) → prune → expand the survivor. Branches that were rejected are kept so reviewers can see the alternatives.

---

## Root: how do we get credible Phase-3 evidence with $0 tonight and ≤ $3 later?

| Branch | Idea | F | V | C | N | Verdict |
|---|---|---|---|---|---|---|
| B1 | Wait for the API key, then run full live agents | 1 | 5 | 1 | 3 | ✂️ Pruned: blocks the night, and 70 MCP servers with Docker and third-party keys won't fit in $5 |
| B2 | Full live agent runs on LiveMCPBench | 1 | 5 | 1 | 3 | ✂️ Pruned: same reasons |
| B3 | **Trace-driven counterfactual replay** of the 95 *real* LiveMCPBench trajectories under exact provider cache rules | 5 | 4 | 5 | 4 | ✅ **Selected (main experiment, E1)** |
| B4 | **Prompt replay against a live API**: send each strategy's exact prompt sequence with max_output_tokens=16 and read `cached_tokens` / `cache_write_tokens` | 4 | 5 | 4 | 5 | ✅ **Selected (validation, E2)**. It measures real billing without agent variance and needs no tool execution |
| B5 | Synthetic tasks with mocked tools | 4 | 2 | 4 | 2 | ✂️ Pruned: B3 already has real token flows |

**Why B3 is valid:** cost depends only on the *token-flow shape* (what is in the prompt, in what order, at each call) and the provider's cache rules. Both are observable from recorded traces plus provider documentation. The known weakness, that agent behaviour is held fixed across strategies, is covered by B4 and by E3 below.

---

## B3 expanded: how do we build each strategy's counterfactual prompt?

### B3.1 Which events survive in each strategy?
- **B3.1a** Keep every recorded event for every strategy. ✂️ Pruned: static strategies would carry discovery (`route`) turns that couldn't exist in them.
- **B3.1b** ✅ Static and retrieval-in-prompt strategies **drop the route-only LLM calls and their results**. Discovery strategies (S4, S5) keep them. This gives the same execution path, minus the discovery steps that the strategy makes unnecessary.

### B3.2 What is "the retrieved set" at each call for RAG-prefix (S2)?
- **B3.2a** The latest route result, as an external RAG would produce it. ✅ This is the default; before the first route call, the first route result is used (retrieval from the user query).
- **B3.2b** The union of all route results so far ("sticky"). ✅ Kept as variant **S2u**. It tests the obvious fix: does growing the set monotonically save the cache? Each *addition* still changes the prefix.

### B3.3 Where does each strategy put tool tokens? (prefix order: tools → system → messages)

| ID | Strategy | Prompt layout per call | Represents |
|---|---|---|---|
| S0 | Static-all, no cache | [ALL schemas][sys][history] | Lower bound |
| S1 | Static-all, cached | same, cached | Naive default |
| S2 | RAG-prefix | [schemas(r_t)][sys][history] | RAG-MCP, MCP-Zero |
| S2u | RAG-prefix, union | [schemas(∪r)][sys][history] | "Sticky" fix |
| S3 | Summary + tail | [ALL summaries][sys][history][schemas(r_t)] | Tool Attention |
| S4 | Discovery, append-only | [2 meta-tools][sys][history incl. route results] | Anthropic tool search / MCP-Copilot, **as recorded** |
| S5 | Names+descriptions + appended schemas | [ALL name+desc][sys][history + schemas appended on first discovery] | OpenAI tool search, as documented |

### B3.4 Pricing regimes (all verified 2026-09-19)
| ID | W (write) | R (read) | Min. cacheable | Source |
|---|---|---|---|---|
| P1 | 1.25 | 0.10 | 1024 | Anthropic 5-minute TTL; OpenAI GPT-5.6+ |
| P2 | 1.00 | 0.10 | 1024 | OpenAI ≤ GPT-5.5 (e.g., gpt-5-nano $0.05 / $0.005) |
| P3 | 2.00 | 0.10 | 1024 | Anthropic 1-hour TTL |
| P4 | 1.00 | 0.10 | 4096 | Gemini implicit caching (3.8 Flash $0.75 / $0.075) |

Output tokens are charged at O = 5× the input price. Extra discovery turns produce extra output, so leaving output out would unfairly favour S4 and S5.

### B3.5 Catalog size
- ✅ Sweep N ∈ {25, 50, 100, 200, 525}. Each task's catalog = its needed and retrieved tools + a seeded random sample of the others. This shows the break-even with real schema sizes instead of an assumed 400 tokens.

---

## Accuracy subtree (H4): can we say anything about accuracy for ~$0?

| Branch | Idea | Verdict |
|---|---|---|
| A1 | Ignore accuracy | ✂️ Fatal: the devil's-advocate critique (item 3) says cost without accuracy is meaningless |
| A2 | **Availability proxy from traces**: when the agent executes tool X at call t, was X in S2's retrieved set r_t? | ✅ Zero cost. Measures how often per-turn retrieval would have **hidden** the needed tool |
| A3 | Cite vendor claims ("accuracy degrades past 30–50 tools") | ✅ Motivation only; not treated as evidence |
| A4 | **Tool-selection test (E3)**: for each task's first executed tool, show gpt-5-nano N ∈ {16, 32, 64, 128} candidate tools (the gold tool + distractors) and check whether it picks correctly | ✅ About $0.25. Answers H4 directly. N is capped at 128 by the OpenAI tool limit |

---

## Claim subtree: what should the paper's headline be?

| Branch | Claim | Verdict |
|---|---|---|
| C1 | "Tool retrieval is bad" | ✂️ Overclaims, and is false for large catalogs |
| C2 | "Placement beats retrieval: where tool tokens sit decides cost more than how many there are" | ✅ Primary |
| C3 | "A closed-form break-even model, validated on real traces" | ✅ Secondary: a reusable tool for practitioners |
| C4 | "Raw-token metrics mislead: ranking inversion" | ✅ The hook in the Introduction |

---

## Execution plan that came out of the tree
1. `extract_traces.py`: real token flows (done: 95 tasks, 525 tools, q̄ = 0.36).
2. `replay.py`: E1 counterfactual replay (S0–S5 × P1–P4 × N sweep) plus the A2 availability proxy.
3. `live_validate.py`: E2 prompt replay and E3 tool selection, with a **hard $ cap**, a `--dry-run` default, and a key read only from the environment.
4. `figures.py` → figures in `paper/figs/`.
5. Draft written with the `academic-paper` skill.
