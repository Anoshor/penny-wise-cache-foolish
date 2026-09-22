"""Live validation on OpenAI gpt-5-nano with a HARD spend cap. Default is a dry run (no API calls).

  E0  tool-limit probe : one request with 129 tools (expected 400 error -> not billed)
  E2  billing check    : replay each strategy's exact prompt sequence (max_output_tokens=64) and
                         compare billed cached tokens / cost with replay.py's prediction (H2, MAPE)
  E3  tool selection   : pick the gold tool among N in {16,32,64,128} candidates (H4)

Usage:
  python live_validate.py                 # dry run: prints plan + worst-case cost, spends $0
  python live_validate.py --live          # needs OPENAI_API_KEY in the environment
  python live_validate.py --selfcheck     # offline test against a fake client
Key is read ONLY from the environment. Never commit or paste it.
"""
import argparse, hashlib, json, os, random, re, sys, time
from pathlib import Path
import tiktoken
import replay as RP

ROOT = Path(__file__).parent
MODEL = "gpt-5-nano"
PRICE = dict(inp=0.05, cached=0.005, out=0.40)     # $ per 1M tokens, verified 2026-09-19
CAP_USD = 1.50                                      # hard stop for the whole run
enc = tiktoken.get_encoding("o200k_base")
WORDS = "alpha beta gamma delta record query server status result value index field token cache".split()


def schemas():
    out = {}
    for srv in json.load(open(ROOT / "data/LiveMCPBench/tools/LiveMCPTool/tools.json")):
        for s in (srv.get("tools") or {}).values():
            for t in s.get("tools", []):
                key = f'{s.get("server_name")}/{t["name"]}'
                name = re.sub(r"[^a-zA-Z0-9_-]", "_", key.replace("/", "__"))[:64]
                params = clean(t.get("inputSchema") or {"type": "object", "properties": {}})
                params.setdefault("type", "object")
                params.setdefault("properties", {})
                out[key] = {"type": "function", "name": name,
                            "description": (t.get("description") or "")[:1000], "parameters": params}
    return out


def clean(node):
    """Drop JSON-Schema draft-04 leftovers that OpenAI rejects (boolean exclusiveMin/Max, $schema)."""
    if isinstance(node, dict):
        return {k: clean(v) for k, v in node.items()
                if k != "$schema" and not (k in ("exclusiveMinimum", "exclusiveMaximum") and isinstance(v, bool))}
    if isinstance(node, list):
        return [clean(v) for v in node]
    return node


def validate_catalog(client, sch, chunk=100):
    """Send the catalog in chunks; 400s are not billed and name the bad tool -> drop it and retry."""
    keys, dropped, headers = list(sch), {}, {}
    for i in range(0, len(keys), chunk):
        part = [k for k in keys[i:i + chunk] if k not in dropped]
        while part:
            try:
                raw = client.responses.with_raw_response.create(
                    model=MODEL, input="ok", max_output_tokens=16, store=False,
                    reasoning={"effort": "minimal"}, tools=[sch[k] for k in part], tool_choice="none")
                headers = {h: raw.headers.get(h) for h in ("x-ratelimit-limit-tokens", "x-ratelimit-limit-requests")}
                break
            except Exception as ex:                      # noqa: BLE001
                m = re.search(r"tools\[(\d+)\]", str(ex))
                if not m:
                    raise
                bad = part.pop(int(m.group(1)))
                dropped[bad] = str(ex)[:200]
    for k in dropped:
        sch.pop(k)
    return dropped, headers


class Throttle:
    """Token-bucket pacing to stay under the account's tokens-per-minute limit."""
    def __init__(self, tpm):
        self.tpm, self.window = tpm, []

    def wait(self, tokens):
        now = time.time()
        self.window = [(t, n) for t, n in self.window if now - t < 60]
        while self.window and sum(n for _, n in self.window) + tokens > self.tpm:
            time.sleep(1)
            now = time.time()
            self.window = [(t, n) for t, n in self.window if now - t < 60]
        self.window.append((now, tokens))


THROTTLE = None


def filler(seg_key, n):
    """Deterministic text of ~n tokens, unique per segment (cache only cares about bytes)."""
    rng = random.Random(str(seg_key))
    return " ".join(rng.choice(WORDS) for _ in range(max(1, n)))


class Spend:
    def __init__(self, cap):
        self.cap, self.usd, self.log = cap, 0.0, []

    def add(self, u, tag):
        cached = u["cached"]
        usd = ((u["input"] - cached) * PRICE["inp"] + cached * PRICE["cached"] + u["output"] * PRICE["out"]) / 1e6
        self.usd += usd
        self.log.append(dict(tag=tag, usd=usd, **u))
        if self.usd > self.cap:
            raise SystemExit(f"HARD CAP reached: ${self.usd:.4f} > ${self.cap}")


def call(client, spend, tag, **kw):
    if THROTTLE:
        THROTTLE.wait(len(enc.encode(json.dumps(kw.get("tools", [])) + json.dumps(kw["input"]))))
    r = client.responses.create(model=MODEL, store=False, **kw)
    u = r.usage
    d = getattr(u, "input_tokens_details", None)
    usage = dict(input=u.input_tokens, output=u.output_tokens,
                 cached=getattr(d, "cached_tokens", 0) or 0,
                 cache_write=getattr(d, "cache_write_tokens", 0) or 0)
    spend.add(usage, tag)
    if usage["input"] == 0:                 # gpt-5-nano reports zero usage when output is exhausted early
        raise RuntimeError(f"zero usage reported ({getattr(r, 'status', '?')}); raise max_output_tokens")
    return r, usage


# ---------------- E2: billing check ----------------
E2_STRATS = ("S1", "S2r", "S3", "S4")


def e2_requests(sess, s, catalog, sch):
    """Turn replay.prompts() segments into Responses API requests for strategy s."""
    for segs, _ in RP.prompts(sess, s, catalog):
        tools, text = [], []
        for key, n in segs:
            if key[0] == "tools":
                ks = sorted(catalog) if key[1] == "ALL" else list(key[1])
                tools = [sch[k] for k in ks if k in sch]
            else:
                text.append(filler(key, n))
        yield dict(tools=tools, input=[{"role": "user", "content": "\n".join(text)}])


def e2_plan(sch, n_sessions=10, m=3, n=100):
    plan = []
    for sx in RP.sessions(m)[:n_sessions]:
        cat = RP.pick_catalog(sx, n)
        for s in E2_STRATS:
            plan.append(dict(session=sx["id"], strat=s, reqs=list(e2_requests(sx, s, cat, sch)),
                             pred=RP.bill(sx, s, cat, "P2")))
    return plan


def run_e2(client, spend, plan):
    rows = []
    for p in plan:
        billed = dict(input=0, cached=0, output=0)
        for req in p["reqs"]:
            extra = {"tools": req["tools"], "tool_choice": "none"} if req["tools"] else {}
            _, u = call(client, spend, f"E2 {p['strat']}", input=req["input"], max_output_tokens=64,
                        reasoning={"effort": "minimal"},
                        prompt_cache_key=f"{p['session']}-{p['strat']}", **extra)
            for k in billed:
                billed[k] += u[k]
            time.sleep(0.5)
        rows.append(dict(session=p["session"], strat=p["strat"], billed=billed,
                         pred_raw=p["pred"]["raw"], pred_hit=p["pred"]["hit"]))
    return rows


# ---------------- E3: tool-selection accuracy ----------------
def e3_plan(sch, sizes=(16, 32, 64, 128), seed=3):
    items = []
    for t in RP.TRACES:
        gold = next((k for e in t["events"] if e[0] == "A" for k in e[3] if k in sch), None)
        if not gold:
            continue
        others = sorted(set(sch) - {gold})
        random.Random(f"{t['task_id']}-{seed}").shuffle(others)
        for n in sizes:
            cands = [gold] + others[:n - 1]
            random.Random(f"{t['task_id']}-{n}").shuffle(cands)
            items.append(dict(task=t["task_id"], n=n, gold=sch[gold]["name"], tools=[sch[k] for k in cands]))
    return items


def run_e3(client, spend, items, questions):
    rows, part = [], ROOT / "results/live_e3_partial.json"
    if part.exists():                       # resume after a crash: skip what is already measured
        rows = json.load(open(part))
        rows = [r for r in rows if r["ok"] is not None or "invalid_prompt" in (r.get("error") or "")]
        done = {(r["task"], r["n"]) for r in rows}
        items = [it for it in items if (it["task"], it["n"]) not in done]
        print(f"E3 resume: {len(rows)} done, {len(items)} left")
    for i, it in enumerate(items):
        try:
            r, u = call(client, spend, f"E3 N={it['n']}", tools=it["tools"], tool_choice="required",
                        max_output_tokens=400, reasoning={"effort": "minimal"},
                        input=[{"role": "user", "content": questions[it["task"]]}])
        except Exception as ex:             # noqa: BLE001 - policy false positives, transient network
            if not any(k in str(ex).lower() for k in ("invalid_prompt", "connection", "timed out", "timeout", "rate limit")):
                raise
            rows.append(dict(task=it["task"], n=it["n"], gold=it["gold"], picked=None, ok=None,
                             error=str(ex)[:120]))
            json.dump(rows, open(part, "w"))
            continue
        picked = next((o.name for o in r.output if getattr(o, "type", "") == "function_call"), None)
        rows.append(dict(task=it["task"], n=it["n"], gold=it["gold"], picked=picked, ok=picked == it["gold"]))
        if i % 20 == 0:
            json.dump(rows, open(part, "w"))
        time.sleep(0.3)
    json.dump(rows, open(part, "w"))
    return rows


def questions():
    runs = json.load(open(ROOT / "data/LiveMCPBench/annotated_data/all_annotations.json"))
    return {r["task_id"]: r["Question"] for r in runs}


def worst_case_usd(plan, items):
    ntok = lambda req: sum(len(enc.encode(json.dumps(t))) for t in req.get("tools", [])) + \
        sum(len(enc.encode(m["content"])) for m in req["input"])
    e2 = sum(ntok(r) for p in plan for r in p["reqs"])
    e3 = sum(ntok(dict(tools=it["tools"], input=[{"content": "x" * 200}])) for it in items)
    out = sum(len(p["reqs"]) for p in plan) * 64 + len(items) * 400
    return (e2 + e3) * PRICE["inp"] / 1e6 + out * PRICE["out"] / 1e6, e2, e3


def main(live, client=None, cap=CAP_USD, n_sessions=10, sizes=(16, 32, 64, 128), only="all"):
    global THROTTLE
    sch, out = schemas(), {}
    if live and client is None:
        if not os.environ.get("OPENAI_API_KEY"):
            sys.exit("OPENAI_API_KEY not set in environment.")
        from openai import OpenAI
        client = OpenAI(max_retries=10)
    if live and not isinstance(client, FakeClient):   # drop schemas the API rejects (unbilled 400s)
        out["dropped_tools"], out["ratelimit"] = validate_catalog(client, sch)
        tpm = int(out["ratelimit"].get("x-ratelimit-limit-tokens") or 200_000)
        THROTTLE = Throttle(int(tpm * 0.8))
        print(f"catalog: {len(sch)} valid, dropped {len(out['dropped_tools'])}; rate limit {out['ratelimit']}")
    plan, items = e2_plan(sch, n_sessions), e3_plan(sch, sizes)
    usd, e2, e3 = worst_case_usd(plan, items)
    print(f"model={MODEL}  E2: {len(plan)} sequences, {sum(len(p['reqs']) for p in plan)} calls, {e2:,} tokens  "
          f"E3: {len(items)} calls, {e3:,} tokens")
    print(f"worst case (no cache hits at all): ${usd:.3f}   hard cap: ${cap}")
    if usd > cap:
        sys.exit("Plan exceeds cap even in the worst case - shrink n_sessions/sizes.")
    if not live:
        print("dry run only - nothing sent. Re-run with --live after setting OPENAI_API_KEY.")
        return None
    spend = Spend(cap)
    out["E0"] = {}
    for k in (129, len(sch)):              # E0: reported 128-tool limit (rejections are not billed)
        try:
            client.responses.create(model=MODEL, input="hi", max_output_tokens=64, store=False,
                                    reasoning={"effort": "minimal"}, tools=list(sch.values())[:k], tool_choice="none")
            out["E0"][k] = "accepted"
        except Exception as ex:            # noqa: BLE001 - record whatever the API says
            out["E0"][k] = f"rejected: {str(ex)[:300]}"
    try:
        if only in ("all", "e2"):
            out["E2"] = run_e2(client, spend, plan)
        elif (ROOT / "results/live.json").exists():     # keep earlier E2 measurements
            prev = json.load(open(ROOT / "results/live.json"))
            out["E2"], out["E0"] = prev.get("E2", []), prev.get("E0", out["E0"])
        if only in ("all", "e3"):
            out["E3"] = run_e3(client, spend, items, questions())
    finally:                               # keep whatever was measured, even on crash or cap
        out["spend_usd"], out["calls"], out["log"] = spend.usd, len(spend.log), spend.log
        if not isinstance(client, FakeClient):
            json.dump(out, open(ROOT / "results/live.json", "w"), indent=1)
        print(f"spent ${spend.usd:.4f} over {len(spend.log)} calls")
    return out


# ---------------- offline self-check ----------------
class FakeClient:
    """Mimics OpenAI prefix caching: cached = longest previously-seen prefix, >=1024 tokens, 128-token blocks."""
    def __init__(self):
        self.seen = set()
        self.responses = self

    def create(self, model, input, max_output_tokens, store, tools=None, **kw):
        if tools and len(tools) > 128:
            raise ValueError("Invalid 'tools': array too long. Expected maximum length 128")
        ids = enc.encode(json.dumps(tools or []) + json.dumps(input))
        h = lambda b: hashlib.sha1(str(ids[:b * 128]).encode()).hexdigest()
        cached = next((b * 128 for b in range(len(ids) // 128, 7, -1) if h(b) in self.seen), 0)
        self.seen |= {h(b) for b in range(8, len(ids) // 128 + 1)}
        name = (tools or [{"name": None}])[0]["name"]
        D = type("D", (), dict(cached_tokens=cached, cache_write_tokens=0))
        U = type("U", (), dict(input_tokens=len(ids), output_tokens=8, input_tokens_details=D))
        O = type("O", (), dict(type="function_call", name=name))
        return type("R", (), dict(usage=U, output=[O]))


def selfcheck():
    out = main(live=True, client=FakeClient(), cap=10.0, n_sessions=2, sizes=(16,))
    assert out["E0"][129].startswith("rejected")
    s1 = [r for r in out["E2"] if r["strat"] == "S1"]
    assert all(r["billed"]["cached"] > 0 for r in s1), "static prefix must hit cache"
    assert len(out["E3"]) > 50 and out["spend_usd"] < 10
    try:
        Spend(0.0).add(dict(input=10**6, cached=0, output=0), "x")
        raise AssertionError("cap not enforced")
    except SystemExit:
        pass
    print("selfcheck ok")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--selfcheck", action="store_true")
    ap.add_argument("--only", choices=("all", "e2", "e3"), default="all")
    a = ap.parse_args()
    selfcheck() if a.selfcheck else main(a.live, only=a.only)
