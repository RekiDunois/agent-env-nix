# Activation-time MCP port environment variable

Baseline: agent-env-nix main `c368871942435bdc178a1063ce9c677acaf8cabc` (2026-10-24).

## Execution plan

The user approved implementing and opening a PR for shared activation-time port environment support, with a producer declaration and a consumer devShell environment variable. No Codex interpolation, consumer/factory port plumbing, generic template engine, or unrelated consumer conflict repair.

1. Add optional `mkAgentPackage.mcpPortEnv = { serverName = "ENV_NAME"; };`. The existing HTTP server `url` is the default URL. Validate mapping type, shell-style environment variable names, and that every mapping selects an existing HTTP server. Keep metadata separate from upstream mcp-servers-nix and native Codex TOML; carry it through package metadata into the project manifest.
2. During MCP prepare, resolve only mapped URLs. An absent variable retains the default URL. A present variable must be ASCII decimal digits representing 1..65535; empty, whitespace, negative, and out-of-range values fail without publishing MCP state/config. Validate the mapped default URL as HTTP(S), with a hostname, no userinfo, and a valid explicit port when present. Replace only the port, retaining scheme, host (including IPv6 brackets), path, query and fragment. All unmapped server values remain unchanged.
3. Feed resolved desired values through the existing ownership/conflict checks. Preserve edited owned definitions, refuse unequal unowned sources, and reuse equal unowned definitions without taking ownership. Commit uses the prepared rendered config and never re-reads the port environment.
4. Add an internal `agent-env cache-key` operation that uses the same desired-value resolver and hashes effective MCP configuration. The cached wrapper includes this digest in its version-2 success marker before comparing the cache, and invokes apply with its unchanged inherited environment. Invalid port inputs fail before skipping. Existing failure invalidation, locking and atomic success publication remain; the cache still does not inspect installed content, and manual edits still require `--force`.
5. Document the producer declaration and devShell variable example. Change only relevant Nix wiring, runtime helpers, tests and this record. Do not change credentials, security settings, user computers, upstream pins, or install Nix. Publish only via the parent's separately authorized draft-PR action.

This is a bounded new interface and persistent activation behavior, not a mechanical fast-merge correction. Use one complete affected-scope review; no automatic merge and no unrelated test matrix.

## Focused test plan

- ConfigEditor tests: absent variable/default, explicit valid ports (including bounds), literal URL and no metadata leakage, IPv6 plus path/query/fragment preservation; invalid values/default declarations fail with config/state unchanged.
- Lifecycle tests: generated URL upgrades on port change; equal unowned reuse and unequal source conflict use resolved values; manual edit protection remains; changing environment after prepare does not alter commit.
- Cached wrapper fixture: exercise real config resolver for fingerprint and prepared config, with only Nix/root/installer mechanics stubbed. Verify same effective URL skips, changed port applies, invalid value fails rather than skips, failed apply removes marker, and existing unmapped wrapper behavior remains.
- Add narrow Nix assertions for declaration acceptance/rejection and metadata isolation. Run only if an existing usable Nix environment is available; no installation. Otherwise record Nix evaluation/build and actual Nix-generated activation integration as NOT RUN, not as passing evidence.
- Run relevant Python tests with already available tomlkit, shell syntax checks, and `git diff --check`. No live MCP/service/model, Darwin installation, real GC-root certification, or full consumer matrix is required by this feature's local fixture scope. Record exact commands, results and limits below before review.

### Executable steps

Use the existing `/workspace/shared/agent-env-nix-venv/bin/python` (tomlkit 0.13.3 verified), from the candidate repository. Create an independent log directory with `mktemp -d /tmp/agent-env-port-tests.XXXXXXXX`. Run that Python with `-m unittest discover -s tests -p test_activate.py -v` and `-m unittest discover -s tests -p test_cached_activation.py -v`, saving each stdout/stderr and exit code. Run `bash -n runtime/activate.sh runtime/cached-activate.sh` and `git diff --check`. No Nix executable is available here; do not install it or run Nix checks. If a tool/fixture launch fails externally, diagnose and retry once only after a concrete repair; if still blocked stop that check and report it as unexecuted. A genuine assertion failure is retained, repaired within scope, and the affected test rerun, without deleting or weakening the assertion.

## Results

Execution design and focused test steps approved by independent reviewer before implementation/testing (2026-10-24).

- Existing Python `/workspace/shared/agent-env-nix-venv/bin/python`, tomlkit 0.13.3.
- `python -m unittest discover -s tests -p test_activate.py -v`: PASS, 30 tests.
- `python -m unittest discover -s tests -p test_cached_activation.py -v`: PASS, 8 tests. The port test runs the real config helper and real prepared commit in a temporary project; installer/root mechanics remain a fixture, not Nix-generated integration.
- `bash -n runtime/activate.sh runtime/cached-activate.sh`: PASS.
- `git diff --check`: PASS.
- Logs: `/tmp/agent-env-port-tests.XsTG4Hsd/{config,cache,shell,diff}.log`; final affected-file reruns in `config-final.log` and `cache-final.log`. No failed attempt. Self-review tightened authority validation and preserved all original non-port URL bytes (including scheme case and empty query/fragment delimiters); the two affected suites were rerun successfully.
- Nix evaluation/build, new Nix assertions, and actual Nix-generated manifest/activation integration: NOT RUN, no available Nix executable. No installation attempted. Darwin/live MCP/real GC-root evidence not claimed.

Scope note: the decimal input grammar is bounded to 1–5 ASCII digits (including leading zeros); this is documented and tested. No credentials, user computer, upstream pin or external repository state changed.
