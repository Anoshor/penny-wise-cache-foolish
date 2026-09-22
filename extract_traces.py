"""Extract ordered token events from LiveMCPBench trajectories + real tool-schema sizes.

Input : data/LiveMCPBench (Claude Sonnet 4 + Qwen3-Embedding MCP-Copilot agent, 95 tasks)
Output: results/traces.json
  catalog[key] = [full_schema_tokens, name_desc_tokens, summary_tokens]   key = "server/tool"
  meta_tokens  = tokens of the agent's two meta-tools (route, execute-tool)
  traces[i]    = {task_id, category, reward, sys_tokens, question_tokens, events}
  events       = ordered list of
      ["A", tokens, route_only, executed_keys]   assistant turn (= one LLM call)
      ["R", tokens, retrieved_keys]              route (retrieval) result
      ["T", tokens]                              other tool result
Tokenizer: tiktoken o200k_base (OpenAI); a proxy for other vendors' tokenizers.
"""
import json, re, statistics as st
from pathlib import Path
import tiktoken

ROOT = Path(__file__).parent
LMB = ROOT / "data" / "LiveMCPBench"
enc = tiktoken.get_encoding("o200k_base")
ntok = lambda s: len(enc.encode(s, disallowed_special=()))
MATCH = re.compile(r"server_name: ([^\s\\]+)\\n\s*tool_name: ([^\s\\]+)")


def catalog():
    out = {}
    for srv in json.load(open(LMB / "tools/LiveMCPTool/tools.json")):
        for s in (srv.get("tools") or {}).values():
            for t in s.get("tools", []):
                desc = t.get("description") or ""
                fn = {"type": "function", "name": t["name"], "description": desc,
                      "parameters": t.get("inputSchema") or {}}
                out[f'{s.get("server_name")}/{t["name"]}'] = [
                    ntok(json.dumps(fn)),                  # full schema (static / loaded)
                    ntok(f'{t["name"]}: {desc}'),          # name + description (OpenAI tool search)
                    ntok(f'{t["name"]}: {desc[:120]}'),    # compact summary (Tool Attention)
                ]
    return out


def meta_tokens():
    """The recorded agent's route + execute-tool definitions (mcp_copilot/server.py lines 29-73)."""
    src = (LMB / "baseline/mcp_copilot/server.py").read_text().splitlines()
    return ntok("\n".join(src[28:73]))


def events(task):
    ev = []
    for m in task["messages"][2:]:
        body = m.get("content") if isinstance(m.get("content"), str) else json.dumps(m.get("content"))
        body = body or ""
        if m["role"] == "assistant":
            calls = m.get("tool_calls") or []
            names = [c["function"]["name"] for c in calls]
            executed = []
            for c in calls:
                if c["function"]["name"] != "route":
                    try:
                        a = json.loads(c["function"]["arguments"])
                        executed.append(f'{a.get("server_name")}/{a.get("tool_name")}')
                    except (json.JSONDecodeError, AttributeError):
                        pass
            ev.append(["A", ntok(body) + ntok(json.dumps(calls)),
                       bool(names) and all(n == "route" for n in names), executed])
        else:
            hits = MATCH.findall(body)
            if hits:
                ev.append(["R", ntok(body), sorted({f"{s}/{t}" for s, t in hits})])
            else:
                ev.append(["T", ntok(body)])
    return ev


def main():
    runs = json.load(open(LMB / "evaluator/output/claude-sonnet-4-20250514/"
                                 "claude-sonnet-4-20250514_Qwen3-Embedding-0.6B.json"))
    cat = catalog()
    traces = [dict(task_id=r["task_id"], category=r["category"], reward=r["reward"],
                   sys_tokens=ntok(r["messages"][0]["content"]),
                   question_tokens=ntok(r["messages"][1]["content"]),
                   events=events(r)) for r in runs]
    (ROOT / "results").mkdir(exist_ok=True)
    json.dump({"catalog": cat, "meta_tokens": meta_tokens(), "traces": traces},
              open(ROOT / "results/traces.json", "w"))

    full = [v[0] for v in cat.values()]
    calls = [sum(e[0] == "A" for e in t["events"]) for t in traces]
    retrieved = {k for t in traces for e in t["events"] if e[0] == "R" for k in e[2]}
    print(f"tasks={len(traces)} tools={len(cat)} catalog_tokens={sum(full):,} "
          f"(mean {st.mean(full):.0f}, median {st.median(full):.0f}/tool)  meta={meta_tokens()}")
    print(f"LLM calls/task: mean={st.mean(calls):.1f} median={st.median(calls)} max={max(calls)}")
    print(f"retrieved keys found in catalog: {len(retrieved & cat.keys())}/{len(retrieved)}")
    print(f"success rate={st.mean(t['reward'] for t in traces):.2f}")
    assert len(traces) == 95 and len(retrieved & cat.keys()) / len(retrieved) > 0.8


if __name__ == "__main__":
    main()
