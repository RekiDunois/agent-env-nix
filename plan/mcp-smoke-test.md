# Shared installation → Codex MCP smoke test

Revision: R3 (2026-10-15). Proposed review status: pending.
Formal test execution: pending user-prepared local environment. This document is the single
plan and recipe for the separate MCP test PR; it does not reopen PR #1.

## Requirement and baseline

Test only the existing shared install path producing project configuration,
followed by real Codex loading it and initializing/discovering its MCP tools.
Reuse `example-base` plus `example-tools` through `.#example`. No downstream
producer inventory, business regression, new harness, platform matrix, or
additional MCP transport is in scope.

- Product baseline: `3b08c9e652dd8df5f3c1686347ef671476022335` (merged PR #1;
  current remote main checked on 2026-10-15).
- Existing 54 Linux checks and two-package build/apply/remove results remain
  valid: [initial validation](../docs/validation.md). Do not repeat them merely
  because this recipe or its PR head changes.
- Fixture recipe: [skills-test-fixtures PR #43](https://github.com/RekiDunois/skills-test-fixtures/pull/43),
  head `ada38c523e1be64e193fef3669dc4af351a3a68e`,
  [wiring §7 and §7.2](https://github.com/RekiDunois/skills-test-fixtures/blob/ada38c523e1be64e193fef3669dc4af351a3a68e/docs/codex-opencode-smoke-wiring.md).
- [PR5 reference recipe](https://github.com/ScholarWorkflow/knowledge-tools/blob/01ae5bea11ef9839aa6fb9cfc230c5de74c450c6/tests/PR5-TEST-RECIPE.md#L214-L246)
  and [eval mapping](https://github.com/RekiDunois/eval-server/blob/3fdfa9387140cfc2e2aa3af415f85015f79706d2/docs/appserver-migration.md).
- Scope/evidence rules: [Test Engineer Rule](https://app.notion.com/p/3d80101a85f380d8a8f5ce528141e253)
  and [Project Consensus](https://app.notion.com/p/3d60101a85f3815a8c43f271f2b4d91d).

## Implementation choice and ownership

Add only this bounded opt-in recipe. `mkAgentPackage`/`mkProject`, the example
packages, generated MCP configuration, flake lock and runtime code stay unchanged.
The real example already selects the upstream fetch server with the real override
`--user-agent=agent-env-nix-example`. Its executable is a fixed Nix store path;
`runtimePackages` retention does not automatically populate PATH.

The installer owns generating and merging the MCP entry. Codex owns project
configuration loading, initialization and discovery. The existing eval service
owns starting the Codex thread. This recipe must not compensate for a product
failure by writing another MCP command, using a fake server, or starting the
server directly. A standalone MCP handshake would miss the Codex-loading part
of the requirement, so it is not the selected alternative.

Use fixture model/reasoning defaults before `agent-env apply`. Never copy a
fixture config over the generated file, or replace its `mcp_servers.fetch` table.
No new common parser, evidence ledger or service is proposed.

## Single required case

Input: one disposable consumer outside this repository and its worktrees,
installed with the existing two-package example; one existing-eval request.

Expected result: Codex reads that consumer's installed configuration, initializes
the fetch MCP server, and completes a minimal read-only `fetch.fetch` call to
`https://www.rfc-editor.org/rfc/rfc2606.txt`, with `max_length=200`. This ordinary
public static document contains no user data. The single call is connection/tool
availability evidence using the existing fixture adapter, not a test of fetching
business content. No content sentinel, extraction accuracy, agent delegation,
private site, downstream workflow or broader network matrix is tested.

Check the installed `mcp_servers.fetch.command` and `args` using a TOML parser,
then the actual runtime initialization/discovery evidence from this request.
The configuration file alone, HTTP 200, top-level `passed`, or model-written
claims are not runtime success. A server `ready` event alone does not prove the
required named tool was discovered.

## Local execution requirements

The user prepares the existing local eval environment. This PR does not configure,
inspect or troubleshoot eval. Run where that existing service normally reads the
consumer and its Nix store. Use its existing credentials without extracting or
copying them. Required existing commands are Nix, direnv, jq, yq (TOML input), curl and Python
3.11+; public network access to the static RFC document is a runtime condition.
Do not install software, start/restart services or alter credentials/security
settings as part of this recipe. Let normal commands report an actual missing
dependency; no separate environment-certification or discovery preflight is added.

Reuse fixture §7.2 directly: in one thread, the final startup status for `fetch`
is `ready` and a completed `mcpToolCall` for server `fetch`, tool `fetch` has
`status=completed` and `error=null`. Use the shipped parser and its matching
contract. Do not combine ready and tool-call events across threads, treat an
app-scoped ready as thread-scoped, or add a tool-catalog parser. A tool result
containing an actual server/fetch error does not establish the successful call.

This recipe does not authorize reading the eval global config or trust list.
Under PR #43, explicit `--sandbox workspace-write --cd` lets the runtime handle
trust and project loading. Unknown pre-existing trust is not a blocker. Known
explicit untrusted/projectless/managed-policy restrictions or an actual runtime
error are handled as observed; never bypass them. Runtime may persist project
trust, so use only an authorized disposable consumer/service. Do not promise
that `--ephemeral` makes trust changes temporary.

## Preparation recipe (after review, in the user-prepared local environment)

Run in the selected existing eval environment, from the product checkout. The
executor supplies the existing configured workspace path and a compatible
already-built example output, reusing initial validation when applicable. If no
compatible output exists on this machine, obtain it with
`EXAMPLE_OUT=$(nix build .#example --no-link --print-out-paths)` from the current
product checkout. This is setup for this case, not a repeat full regression.
`FIXTURES` is a checkout of the fixture revision above. These are operational
inputs, not values to guess or discover by scanning credentials/global config.

```bash
set -euo pipefail
: "${EVAL_WORKSPACE:?existing configured workspace required}"
: "${EXAMPLE_OUT:?existing compatible example output required}"
: "${FIXTURES:?fixture checkout required}"
PRODUCT_SHA=$(git rev-parse HEAD)
FIXTURE_SHA=$(git -C "$FIXTURES" rev-parse HEAD)
RUN_ROOT=$(mktemp -d /tmp/agent-env-mcp.XXXXXXXX)
CONSUMER="$RUN_ROOT/consumer"
mkdir -p "$CONSUMER/.codex" "$RUN_ROOT/results"
git -C "$CONSUMER" init -q
cp "$FIXTURES/configs/codex-consumer.toml" "$CONSUMER/.codex/config.toml"
printf 'product=%s\nfixtures=%s\nexample=%s\nconsumer=%s\n' \
  "$PRODUCT_SHA" "$FIXTURE_SHA" "$EXAMPLE_OUT" "$CONSUMER" \
  > "$RUN_ROOT/results/inputs.txt"
"$EXAMPLE_OUT/bin/agent-env" apply --project "$CONSUMER" \
  > "$RUN_ROOT/results/apply.stdout" 2> "$RUN_ROOT/results/apply.stderr"
yq -p=toml -o=json '.' "$CONSUMER/.codex/config.toml" | jq -e '
  (.mcp_servers.fetch.command | startswith("/nix/store/")) and
  .mcp_servers.fetch.args == ["--user-agent=agent-env-nix-example"]
' > "$RUN_ROOT/results/config-check.json"
EVAL_PORT=$(direnv exec "$EVAL_WORKSPACE" sh -c 'printf "%s" "$EVAL_PORT"')
test -n "$EVAL_PORT"
```

The template's historical pretrust comment does not supersede PR #43 §7.
Do not use `tests/integration.sh` as this live setup: its intentionally invalid
model/unrelated fake MCP and redirected HOME/CODEX_HOME are offline fixtures.
Do not copy those settings into this case. The fixture model and reasoning are
runtime inputs, not product acceptance conditions. No model/reasoning/MCP/environment/
approval CLI override is added.

## Request recipe

The prompt requests one minimal native MCP call. It is not itself evidence.
Do not use shell, curl or another tool to substitute for the installed MCP call.

```bash
PROMPT='Use the configured fetch MCP server to call its fetch tool once with url https://www.rfc-editor.org/rfc/rfc2606.txt and max_length 200. Do not use shell commands, browse with another tool, read project files, edit files, delegate, or call any other MCP tool. If the MCP call is unavailable or fails, report that and stop without retrying.'
set -- --json --ephemeral --skip-git-repo-check \
  --sandbox workspace-write --cd "$CONSUMER" -- "$PROMPT"
COMMAND=$(jq -rRn --args '$ARGS.positional | map(@sh) | join(" ")' -- "$@")
jq -n --arg command "$COMMAND" '{command:$command,timeout:300}' \
  > "$RUN_ROOT/request.json"
set +e
curl --silent --show-error --max-time 330 \
  --header 'Content-Type: application/json' \
  --data-binary "@$RUN_ROOT/request.json" \
  --output "$RUN_ROOT/response.json" --write-out '%{http_code}' \
  "http://127.0.0.1:$EVAL_PORT/eval" > "$RUN_ROOT/results/http.txt" \
  2> "$RUN_ROOT/results/curl.stderr"
CURL_EXIT=$?
set -e
printf '%s\n' "$CURL_EXIT" > "$RUN_ROOT/results/curl.exit"
```

`COMMAND` is arguments for the existing eval API, not an executable shell
command. No direct `codex` invocation, new eval service, profile fallback,
manual trust edit, or attempt to bypass a runtime denial is allowed.

## Existing fixture adapter and inspection

Only after transport succeeds and HTTP status is 200, consume the response with
its existing adapter (no custom parser, replay suite or new schema):

```bash
test "$CURL_EXIT" -eq 0
test "$(cat "$RUN_ROOT/results/http.txt")" = 200
python3 "$FIXTURES/scripts/parse_codex_eval_evidence.py" \
  --contract "$FIXTURES/configs/codex-eval-adapter-contract.json" \
  --eval-response "$RUN_ROOT/response.json" \
  --expected-mcp-server fetch --expected-mcp-tool fetch=fetch \
  --output "$RUN_ROOT/results/mcp-evidence.json"
jq '{fixture_status, mcp_observation, problems}' \
  "$RUN_ROOT/results/mcp-evidence.json"
```

Inspect the adapter's same-thread `success_thread_ids`/`threads` evidence and the
actual matched call arguments/result. Confirm the requested public URL was used
and the result is not an MCP/server error. Do not require exact page text or a
fixed output schema for the fetched document. The shared-installation result is passed only
when the installed configuration check and the bounded successful native MCP
observation both hold. Fixture readiness alone is not the shared-installation verdict.
A prompt requests one call; follow fixture §7.2's existing count semantics rather
than adding an exact-count test gate. Do not issue another eval to seek success.

## Results, failure and cleanup

Use four outcomes: passed, product failure, unable to judge, not run. Record
actual product/fixture revision, commands, response version, necessary runtime
output and the result. Keep response/private paths outside Git; commit only a
short sanitized result. Do not publish model prose as discovery evidence.

An actual installation-generated command/configuration defect is a product
failure when supported by its output, including an incorrect generated executable
path or MCP entry that prevents loading or initialization. Service, provider or
model failure is unable to judge. A filesystem mismatch or missing required MCP
observation is unable to judge only when caused by the external execution or
observation environment; do not use that label to hide a demonstrated shared
installation defect. If the cause remains unclear, record the actual failure
and what is unresolved without assigning an unsupported product verdict.
Automatic retries: zero. Preserve any attempt; change a faulty recipe before
another approved attempt, and never sample repeatedly to seek a pass.

Once the request is terminal, release only this consumer's owned installation
using `"$EXAMPLE_OUT/bin/agent-env" remove --project "$CONSUMER"`; retain the
run directory for result review. Do not run GC, delete global trust, or change
service credentials/configuration. A timeout leaves runtime completion uncertain;
report it before cleanup rather than removing paths an active thread may use.

Current result: pending local execution; no formal test has been run. First/second/third test gates remain pending as
applicable; this candidate does not assert runtime compatibility or merge readiness.
