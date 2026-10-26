# Harness selection and proxy export — local preparation and check record

Requirement R1; execution plan P3; test plan T5. Baseline
5e92248c98e5753306d31a2ed57d6d4661feb998. This record covers test-asset
preparation and the checks actually run for that preparation. It is not a Gate3
result and not a merge conclusion; the independent reviewer owns those.

## Why this record exists

`review-results.md` recorded every runtime and Nix item as NOT RUN because that
cloud had no Nix executable and no tomlkit. This host provides both, so the
preparation gap named there is now closable. Environment: aarch64-darwin, Darwin
25.6.0, Nix 2.34.8, jq 1.7.1; the system `python3` is 3.9.6 without tomlkit, so
runtime commands use the flake devShell interpreter (3.14.7, tomlkit 0.15.0) that
the repository's own `runtime-unit` check already uses. No dependency was
installed, no user project, HOME, service or credential was touched, and no MCP
server was deployed or activated.

## Test-asset preparation

1. `tests/default.nix` gained the item 1 assertions the test plan requires: a root
   with no MCP of its own depending on `example.overridden` yields
   `mcpHarnesses.fetch == [ "dsh" ]` under a DSH-only root and `[ "codex" ]` under
   the default root, `servers.fetch` still equals the dependency's own definition,
   and separate Codex and DSH roots over the same dependency yield both harnesses
   with `fetch` appearing once and unchanged.
2. `tests/test_shell_activation.py` needed one wiring correction. Its fixture
   replaced `manifest["mcpOwners"]` with `{}` to isolate activation from MCP
   configuration, but the new `mcpHarnesses` field still named `fetch`, so
   `selected_mcp` rejected the fixture manifest. The fixture now clears
   `mcpHarnesses` too. This restores the pre-existing scenarios; it adds no target.

Raw output: `/tmp/agent-env-harness-proxy.vA1uBU` (outside the repository).

## Commands and results

Tested revision `33f26bc0639a19a150a679211c81f96eb8e578f3`; the first pass ran on
the working tree that became `299c9b9`, and the recorded rows below were repeated
from a clean detached checkout of `33f26bc` (`git worktree add /tmp/agent-env-harness-proxy-clean 33f26bc`)
so no row depends on uncommitted state. Attribute names in the approved recipe are
`x86_64-linux`; they were substituted with `aarch64-darwin` because that is the
only system where this host has Nix. Inputs, expectations and observations are
unchanged.

These rows are preparation-time runs by the local test engineer, before Gate 2.
They do not replace the Gate 3 run: after Gate 2 the local execution engineer runs
the same recipe formally and records the result. Raw output:
`/tmp/agent-env-harness-proxy.vA1uBU`.

| Check | Command | Result |
| --- | --- | --- |
| Nix evaluation assertions (item 1, 3) | `nix build .#checks.aarch64-darwin.evaluation --no-link` | exit 0 |
| Example build (item 3) | `nix build .#packages.aarch64-darwin.example --no-link --print-out-paths` | exit 0, output `/nix/store/r01p3aalmc1sd47wwiccqqarcdr9cbbd-agent-environment` |
| Built proxy JSON | `jq -e` proxy predicate from the recipe | exit 0 |
| Built connection JSON | `jq -e` connection predicate from the recipe | exit 0 |
| Focused runtime (item 2) | `nix develop --command python3 -m unittest discover -s tests -p test_dsh_mcp.py -k test_harness_selection_and_owned_cleanup -v` | 1 test, OK |

The two built files matched the recipe's expected values: `mcp-proxy.json` held
only `mcpServers` with a single `fetch` backend at a fixed `/nix/store` path,
`options.disabled` true, and args `["--user-agent=agent-env-nix-example"]`;
`mcp-connections.json` held one `fetch` entry owned by `example-tools` with
`backendSource` `stdio`, `enableHarnesses` `["codex"]`, empty
`requiredEnvironment` and non-empty `manualCompletion`.

## Preparation checks beyond the frozen recipe

These were run to confirm the two prepared assets, not as added test obligations:

- `nix build .#checks.aarch64-darwin.runtime-unit`: first attempt failed 5 of 58
  tests with `invalid manifest MCP harness selection`, all in
  `test_shell_activation`. That is the fixture defect corrected above. After the
  correction the same check ran 58 tests, OK. The same command on a detached
  baseline `5e92248` checkout ran 57 tests, OK; that log is
  `/tmp/baseline-runtime-unit.log` (63 lines, ends `Ran 57 tests … OK`), and the
  repository arithmetic agrees (baseline 30+8+5+7+7, current 30+8+6+7+7). It
  confirms the five failures came from the new manifest field, not from a product
  change.
- `nix build .#checks.aarch64-darwin.cached-activation` (8 tests) and
  `nix build .#checks.aarch64-darwin.upstream-copy`: both exit 0.
- `nix develop --command python3 -m unittest discover -s tests -p test_dsh_mcp.py -v`
  (6 tests) and `... -p test_activate.py -v` (30 tests): both OK.
- `nix flake check --no-build --all-systems`: all checks passed (evaluation only).

The first runtime-unit failure is kept in the record rather than replaced by the
later pass.

## Not covered

No live MCP proxy deployment, gateway merge, Chrome lifecycle, DSH harness runtime,
Codex model evaluation, browser profile or external business service was run; the
plan excludes them. Documentation item 4 was checked by reading the final diff
against P3 and the user requirement: README removes the public `dshMcp` flag in
favour of root `enableHarnesses`, states the migration error, and explains that the
two JSON files are read-only outputs for manual merge with no secret reading and no
service deployment. The `dshMcp` migration error was also evaluated directly: a
project built with `dshMcp = true` fails with
`error: agent-env-nix: replace mkProject.dshMcp with rootPackage.override { enableHarnesses = [ "codex" "dsh" ]; }`
(saved in `/tmp/agent-env-harness-proxy.vA1uBU/dshmcp-migration-error.txt`), and
`builtins.tryEval` reports `success = false`.

## Status

The Nix and runtime items that `review-results.md` listed as NOT RUN now have
preparation-time results on the recorded revision. Gate 2, the formal Gate 3 run by
the local execution engineer, and merge readiness remain with their owners.
