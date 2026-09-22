"""Analytical cost model: tool-exposure strategies under prefix-cache pricing.

Normalized: base uncached input price = 1.0 per token. Output tokens are
identical across strategies and excluded. Expected cost uses q = probability the
retrieved tool set changes between consecutive turns.

Cache semantics (Anthropic/OpenAI style): prefix order tools -> system -> messages;
any change at position i invalidates everything after i. At turn t the previous
turn's full input is read from cache (price R) and only new tokens are written (W).
"""
from itertools import product

W, R = 1.25, 0.10          # cache write / read multipliers (Anthropic 5-min TTL; OpenAI GPT-5.6+)
S = 2_000                  # system prompt tokens
D = 400                    # avg tokens per full tool schema (~47.3k/120 tools, Tool Attention testbed)
SUM = 60                   # tokens per compact tool summary (Tool Attention phase 1)
K = 5                      # tools retrieved per turn (Anthropic tool search default)
H = 1_500                  # new tokens per turn (tool call + result + assistant text)


def turns(T, prefix, q=0.0, tail=0, appended=0):
    """Return (normalized_cost, raw_input_tokens) over T turns.

    prefix   : stable tokens at the top of the prompt (tools+system)
    q        : prob. that prefix changes this turn (full miss of prefix + history)
    tail     : per-turn tokens placed after history and replaced every turn
    appended : per-turn tokens appended permanently to history (expected)
    """
    cost = raw = 0.0
    hist = 0.0
    for t in range(1, T + 1):
        inp = prefix + hist + tail + H
        raw += inp
        if t == 1:
            cost += W * inp
        else:
            hit = R * (prefix + hist) + W * (tail + H)
            miss = W * inp
            cost += q * miss + (1 - q) * hit
        hist += H + appended
    return cost, raw


def strategies(N, T, q):
    nocache = sum(S + N * D + t * H for t in range(1, T + 1))
    return {
        "static_nocache": (nocache, nocache),
        "static_cached":  turns(T, S + N * D),
        "rag_prefix":     turns(T, S + K * D, q=q),               # RAG-MCP / MCP-Zero, tools at top
        "summary_tail":   turns(T, S + N * SUM, tail=K * D),      # Tool Attention layout
        "defer_append":   turns(T, S + 300, appended=q * K * D),  # provider tool search (defer_loading)
    }


def breakeven_N(T, q, hi=5_000):
    """Smallest catalog size where rag_prefix becomes cheaper than static_cached."""
    for N in range(1, hi):
        s = strategies(N, T, q)
        if s["rag_prefix"][0] < s["static_cached"][0]:
            return N
    return None


def demo():
    # sanity: with no tool-set churn, retrieving 5 tools never costs more than loading N>=5
    for N, T in product([10, 100], [3, 20]):
        s = strategies(N, T, 0.0)
        assert s["rag_prefix"][0] <= s["static_cached"][0]
    # sanity: single turn -> caching only adds the write premium
    s = strategies(50, 1, 1.0)
    assert abs(s["static_cached"][0] - W * s["static_nocache"][0]) < 1e-6

    names = list(strategies(1, 1, 0))
    print(f"{'N':>4} {'T':>3} {'q':>4} | " + " | ".join(f"{k:>15}" for k in names))
    for N, T, q in product([20, 100, 300], [5, 15, 30], [0.44, 1.0]):
        s = strategies(N, T, q)
        base = s["static_cached"][0]
        cells = [f"{v[0]/base:5.2f}x {v[1]/1e3:5.0f}k" for v in s.values()]
        print(f"{N:>4} {T:>3} {q:>4} | " + " | ".join(cells))
    print("\n(cost relative to static_cached | raw input tokens, thousands)\n")
    for q in (0.2, 0.44, 1.0):
        print(f"q={q}: break-even N (rag_prefix cheaper than static_cached) by T:",
              {T: breakeven_N(T, q) for T in (5, 10, 20, 40)})


if __name__ == "__main__":
    demo()
