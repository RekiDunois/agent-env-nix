# Harness selection and proxy export — test plan
Requirement R1 and execution P3 in execution-plan.md. Test T4 (Gate 2 generated-file verification clarified from T3; Gate 1 scope unchanged); proposed review status pending. Baseline 5e92248c98e5753306d31a2ed57d6d4661feb998.

## Required scope (Gate 1 candidate)
1. Root harness choice controls transitive MCP selection: default Codex, DSH-only with necessary dependency, and a shared dependency reached by separate Codex/DSH roots. Check existing tests/default.nix assertions for effective graph, unchanged payload drvPath, exported manifest ownership/selection and proxy output data. Empty selection has no projected exports. No other harness matrix.
2. Runtime activation projects a mixed selected MCP set to the correct Codex/DSH files. One focused unittest in existing DSH test module uses literal HTTP and fixed stdio fixtures, parses resulting files, then changes selection to verify unchanged owned entries removed while unrelated entries survive. Existing DSH conflict/edit/fallback checks are reused rather than rerunning the full installer suite. Cache-key selection change is checked in the same runtime module.
3. Explicit producer backend metadata and existing ordinary stdio yield fixed-path mcp-proxy.json (explicit wins, inferred stdio stays disabled with complete original client details/manual-completion information); independent HTTP-only entry stays solely in connection metadata. Existing Nix evaluation assertions check valid backend map and rejection of a non-fixed command or unowned backend name. No live proxy deployment is required for serialization; no Chrome lifecycle repetition.
4. README examples and migration error accurately remove the public flag and explain shared file/plugin limits, no auto-deployment or secret reading. Static diff review is sufficient.

## Recipe (Gate 2 candidate)
Working directory is this repository snapshot; raw output in a new /tmp/agent-env-harness-proxy. No user project, HOME, service or network credential changes. Check python3 and import tomlkit availability. If unavailable, record runtime item unable to judge rather than installing an undeclared environment dependency.
The focused runtime command after Gate2 is `python3 -m unittest discover -s tests -p test_dsh_mcp.py -k test_harness_selection_and_owned_cleanup -v`. It checks mixed selection, cache change and owned cleanup without rerunning the existing mapping suite. Existing broader DSH mapping/protection results are reused from plan/dsh-mcp-output/results.md because those mapping/protection mechanisms are unchanged. This cloud has no tomlkit, so record the command NOT RUN rather than install dependencies or claim a pass.
Nix-required items run on the declared x86_64-linux system with `nix` and `jq` available. The existing `tests/default.nix` assertions check transitive selections, explicit backend precedence, disabled inferred stdio, HTTP-only exclusion and invalid backend input. Build the existing `example` package once to inspect the actual two JSON files written by `lib/project.nix`; this example covers physical file delivery and the stdio output, while the existing evaluation assertions cover the explicit-backend and HTTP-only fixture. It does not deploy or activate an MCP server.

Run from the exact tested repository snapshot after Gate 2 approval (no product or fixture modifications):

```sh
set -euo pipefail
run=$(mktemp -d /tmp/agent-env-harness-proxy.XXXXXX)
nix build .#checks.x86_64-linux.evaluation --no-link \
  > "$run/nix-evaluation.log" 2>&1
environment=$(nix build .#packages.x86_64-linux.example \
  --no-link --print-out-paths 2> "$run/nix-example-build.log")
printf '%s\n' "$environment" > "$run/environment-path.txt"
test -f "$environment/mcp-proxy.json"
test -f "$environment/mcp-connections.json"
jq -e '
  (keys == ["mcpServers"])
  and ((.mcpServers | keys) == ["fetch"])
  and (.mcpServers.fetch.options.disabled == true)
  and (.mcpServers.fetch.command | startswith("/nix/store/"))
  and (.mcpServers.fetch.args == ["--user-agent=agent-env-nix-example"])
' "$environment/mcp-proxy.json" > "$run/proxy-check.txt"
jq -e '
  (keys == ["fetch"])
  and (.fetch.owner == "example-tools")
  and (.fetch.backendSource == "stdio")
  and (.fetch.enableHarnesses == ["codex"])
  and (.fetch.client.command | startswith("/nix/store/"))
  and (.fetch.client.args == ["--user-agent=agent-env-nix-example"])
  and (.fetch.requiredEnvironment == [])
  and ((.fetch.manualCompletion | length) > 0)
' "$environment/mcp-connections.json" > "$run/connections-check.txt"
```

Expected: the evaluation and example build succeed; both JSON files exist and parse; the proxy has one fixed-store-path `fetch` backend with `disabled: true`, and connection metadata retains the original `fetch` client, owner, selected harness, backend source and manual-completion notes. The `jq` checks return exit status 0. Record the tested SHA, system, both commands and their statuses, the generated environment path and the check outputs under `$run`. Do not copy the built files into the repository or user configuration.

If Nix or jq is unavailable, mark only these Nix-required items NOT RUN with the missing prerequisite and continue independent checks; do not install dependencies or claim that static review proves file delivery. This cloud currently has no Nix executable. Do not rerun old shared installer gates as part of this plan.
For documentation inspect the final diff against P3 and user requirements. No full workflow, Codex eval, DSH agent runtime, browser profile/startup, Darwin run or external MCP business regression is added.

## Failures and results
No automatic repeat after product assertion failure. Fix product and rerun only the affected approved check; record first failure. Environment availability failures stop that item, continue independent checks; a recovered prerequisite permits one affected retry with same inputs/expectations, recording both. Any recipe or expected-output change is reviewed for affected scope first. Report pass, business failure, unable to judge or not run with exact candidate/commands and minimal output. Reviewer owns Gate conclusions; author cannot declare APPROVED or overall PASS. Current environment limits may leave Draft PR unready for merge.
