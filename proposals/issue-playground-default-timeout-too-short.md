# Playground: default `ClaudeCodeProvider` timeout (120s) too short for first-compose; small scenarios time out

**Reporter:** RA (bench-runs worktree)
**Surface:** Web playground (any scenario, first run after server start)
**Sha:** `bf68452`
**Severity:** P1 (recurring user-visible "Bricks failed" badge for non-Bricks reasons)
**Labels:** `bug`, `playground`, `provider`, `p1`

---

## Summary

`ClaudeCodeProvider.__init__` defaults `timeout=120` seconds. The web playground inherits this default — there's no override in [`src/bricks/playground/web/routes.py`](src/bricks/playground/web/routes.py) — and small scenarios on a cold prompt-cache exceed 120s during compose. The user sees "Bricks failed" with the error:

```
API call failed: Command '['claude', '-p', '--output-format', 'json', '--model', 'sonnet']'
timed out after 120 seconds
```

This is a transport-layer timeout, not a compose-quality issue. The compose call returns nothing — no DSL is saved, the engine reports `outputs={}` and `tokens_in=0, tokens_out=0`, and the playground UI shows "Bricks failed" while raw LLM (which doesn't go through this provider path the same way, or has lower per-call cost) succeeds.

The bench-runs Track 1 runner already had to override this to 600s ([`tracks/track-1-exploration/run.py`](tracks/track-1-exploration/run.py): `PROVIDER_TIMEOUT_S = 600`) to avoid identical failures during research.

## Reproduction

From the bench-runs worktree at sha `bf68452`:

```bash
.venv/Scripts/python -m bricks.playground.web      # serve on :8742
.venv/Scripts/python runs/playground-replay/replay.py
.venv/Scripts/python -c "
import json
d = json.load(open('runs/playground-replay/custom-example.json'))
print('error:', d['result']['bricks'].get('error',''))
print('outputs:', d['result']['bricks'].get('outputs'))
print('tokens:', d['result']['bricks'].get('tokens'))
print('duration_ms:', d['result']['bricks'].get('duration_ms'))
"
```

Output (excerpt):

```
error: API call failed: Command '['claude', '-p', '--output-format', 'json', '--model', 'sonnet']' timed out after 120 seconds
outputs: {}
tokens: {'in': 0, 'out': 0, 'total': 0}
duration_ms: 120093
```

The `custom-example` scenario is **5 inline product rows** — a trivial filter+aggregate. It still timed out on the first compose. The other three scenarios in the same playback (CRM, ticket, cross-dataset-join) succeeded because their compose calls happened to finish under 120s.

## Root cause

`ClaudeCodeProvider.__init__(timeout=120, ...)` in [`src/bricks/providers/claudecode/provider.py`](src/bricks/providers/claudecode/provider.py). Used directly by `BricksEngine.__init__` in the playground, no override.

Compose latency is variable — sometimes the first compose under cold cache takes 90-150s with the post-#66 expanded brick catalog (stdlib + builtins). 120s sits squarely in the failure-rate band.

## Suggested fix

Two layers:

### 1. Raise the default in `ClaudeCodeProvider`

```diff
- def __init__(self, timeout: int = 120, model: str | None = None) -> None:
+ def __init__(self, timeout: int = 300, model: str | None = None) -> None:
```

300s covers ~99% of observed compose latencies in our bench-runs sweep without making developer-loop failures hang painfully. This is a sensible default for any `claude -p` consumer; a tighter default than 120s mostly hurts.

### 2. Expose a `timeout_seconds` field on the playground `RunRequest`

[`src/bricks/playground/web/schemas.py:90-104`](src/bricks/playground/web/schemas.py#L90):

```python
class RunRequest(BaseModel):
    provider: Literal["anthropic", "openai", "claude_code", "ollama"]
    model: str
    api_key: str | None = None
    task: str
    data: Any
    expected_output: dict[str, Any] | None = None
    compare: bool = False
    timeout_seconds: int = 300   # ← add
```

Threaded through to `_build_provider` in [`routes.py`](src/bricks/playground/web/routes.py). UI can keep a hidden default; advanced users can override per-run.

The first change alone solves the user-reported symptom. The second is "nice to have" for diagnostics.

## Acceptance

- [ ] `ClaudeCodeProvider()` default timeout is at least 300s.
- [ ] Re-running the `custom-example` reproducer above produces non-empty Bricks outputs.
- [ ] No regression in any test that explicitly verifies a 120s default.

## Non-goals

- No change to the actual compose pipeline. This is a transport-layer timeout, not a planning-quality fix.
- No change to other providers (`anthropic`, `openai`, `ollama`) unless they share the same too-tight default — verify and decide separately.
