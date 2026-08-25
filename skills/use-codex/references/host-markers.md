# Host markers: what each CLI sets in its own children

Probed 2026-08-25 by running `env | sort` inside each CLI and grepping for
vendor-prefixed variables. Used by the recursion guard in `codex-run.sh` and
`gemini-run.sh` to refuse a dispatch that is already running inside that vendor's
own agent.

The guard's real backstop is `AUTOPILOT_DISPATCH_DEPTH`. These markers are a
nicety: they also catch a nesting that starts outside our runners.

## codex (native `codex exec`)

Confirmed set in the child shell:

| Variable | Example | Always set? |
|---|---|---|
| `CODEX_SESSION_ID` | `01a03a86-8706-7543-94e1-184cafd69a67` | yes |
| `CODEX_THREAD_ID` | same value as session id | yes |
| `CODEX_CI` | `1` | yes under `codex exec` |
| `CODEX_SANDBOX` | `seatbelt` | only when sandboxed |
| `CODEX_SANDBOX_NETWORK_DISABLED` | `1` | only when sandboxed |

Guard on `CODEX_SESSION_ID`. `CODEX_SANDBOX` is absent under
`--dangerously-bypass-approvals-and-sandbox`, so it is not a reliable marker.

No `OPENAI*` or `CHATGPT*` variable is set.

## copilot (`copilot -p`)

This is the live fallback for `codex-run.sh` and the **default** backend for
`gemini-run.sh`, so it is the marker that matters most in practice.

| Variable | Example |
|---|---|
| `COPILOT_CLI` | `1` |
| `COPILOT_AGENT_SESSION_ID` | `10e34f57-17bc-4681-880a-6c26fccaae40` |
| `COPILOT_CLI_BINARY_VERSION` | `1.0.80` |

Guard on `COPILOT_CLI`.

No `GITHUB_*` or `GH_*` variable is set by the CLI itself.

## gemini (native `gemini -p`)

**Not probed - the backend is unavailable.** As of 2026-08-25 the native CLI
(v0.51.0) refuses to authenticate:

```
IneligibleTierError: This client is no longer supported for Gemini Code Assist
for individuals.
```

`gemini-run.sh` prefers the copilot backend, so the Gemini lane is covered by
the `COPILOT_CLI` marker above. Re-probe if `GEMINI_BACKEND=gemini` ever becomes
usable again; until then recursion through native gemini is bounded only by
`AUTOPILOT_DISPATCH_DEPTH`.
