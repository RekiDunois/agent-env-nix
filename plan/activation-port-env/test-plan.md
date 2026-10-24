# Activation-time MCP port: test plan

Baseline: main `c368871942435bdc178a1063ce9c677acaf8cabc`. Product/reviewed PR revision: `04f22a464e26207746a619312e80f6d6df6fccf9` ([PR #6](https://github.com/RekiDunois/agent-env-nix/pull/6)).

Document revision: split-plan v1, 2026-10-24. The user's latest instruction is “你给拆成两个吧，走正常审核”. This revision separates the two canonical plans without changing product or test code, requirements, or test scope. The previous combined path is navigation only.

## Required scope and checks

- ConfigEditor tests: absent variable/default, explicit valid ports (including bounds), literal URL and no metadata leakage, IPv6 plus path/query/fragment preservation; invalid values/default declarations fail with config/state unchanged.
- Lifecycle tests: generated URL upgrades on port change; equal unowned reuse and unequal source conflict use resolved values; manual edit protection remains; changing environment after prepare does not alter commit.
- Cached wrapper fixture: exercise real config resolver for fingerprint and prepared config, with only Nix/root/installer mechanics stubbed. Verify same effective URL skips, changed port applies, invalid value fails rather than skips, failed apply removes marker, and existing unmapped wrapper behavior remains.
- Add narrow Nix assertions for declaration acceptance/rejection and metadata isolation. Execution requires a working authorized Nix environment. Cloud installation was later authorized, but the environment is currently blocked before installation starts. Otherwise record Nix evaluation/build and actual Nix-generated activation integration as NOT RUN, not as passing evidence.
- Run relevant Python tests with already available tomlkit, shell syntax checks, and `git diff --check`. No live MCP/service/model, Darwin installation, real GC-root certification, or full consumer matrix is required by this feature's local fixture scope. Record exact commands, results and limits below before review.

### Executable steps

Use the existing `/workspace/shared/agent-env-nix-venv/bin/python` (tomlkit 0.13.3 verified), from the candidate repository. Create an independent log directory with `mktemp -d /tmp/agent-env-port-tests.XXXXXXXX`. Run that Python with `-m unittest discover -s tests -p test_activate.py -v` and `-m unittest discover -s tests -p test_cached_activation.py -v`, saving each stdout/stderr and exit code. Run `bash -n runtime/activate.sh runtime/cached-activate.sh` and `git diff --check`. No Nix executable is currently available here; the blocked environment has not executed installation or Nix checks. This document-only revision does not attempt either. If a tool/fixture launch fails externally, diagnose and retry once only after a concrete repair; if still blocked stop that check and report it as unexecuted. A genuine assertion failure is retained, repaired within scope, and the affected test rerun, without deleting or weakening the assertion.

### Outstanding Nix checks: executable recipe (NOT RUN)

Run this only after a working, authorized Nix environment is available. It uses the existing flake inputs and public constructors, not copied runtime code or a new framework. GitHub access must already be authorized; stop on authentication or dependency-fetch failure rather than changing credentials. The selected product revision below is the unchanged product/test code already published in PR #6. A docs-only successor does not invalidate this result.

Preparation and build, from any directory outside the producer checkout:

```bash
set -euo pipefail
revision=04f22a464e26207746a619312e80f6d6df6fccf9
run=$(mktemp -d /tmp/agent-env-port-nix.XXXXXXXX)
export PORT_TEST_RUN="$run" PORT_TEST_REVISION="$revision"
printf '%s\n' "$run"  # Retain this directory and all attempts.
command -v nix
nix --version > "$run/nix-version.txt"
git clone --branch feat/activation-mcp-port-env --single-branch \
  https://github.com/RekiDunois/agent-env-nix.git "$run/source" \
  > "$run/clone.log" 2>&1
git -C "$run/source" checkout --detach "$revision" >> "$run/clone.log" 2>&1
test "$(git -C "$run/source" rev-parse HEAD)" = "$revision"
test -z "$(git -C "$run/source" status --porcelain)"
export PORT_TEST_FLAKE="git+file://$run/source?rev=$revision"
system=$(nix --extra-experimental-features 'nix-command flakes' \
  eval --impure --raw --expr builtins.currentSystem)
printf '%s\n' "$system" > "$run/system.txt"
case "$system" in x86_64-linux|aarch64-darwin) ;; *) echo 'Unsupported test system'; exit 1;; esac
nix --extra-experimental-features 'nix-command flakes' build \
  "$PORT_TEST_FLAKE#checks.$system.evaluation" --no-link \
  > "$run/evaluation.log" 2>&1
cat > "$run/fixture.nix" <<'NIX'
let
  flake = builtins.getFlake (builtins.getEnv "PORT_TEST_FLAKE");
  pkgs = flake.inputs.nixpkgs.legacyPackages.${builtins.currentSystem};
  producer = flake.lib.mkAgentPackage {
    inherit pkgs;
    id = "activation-port-check";
    version = "1";
    files = { };
    mcp.settings.servers.portcheck.url = "http://127.0.0.1:19090/mcp";
    mcpPortEnv.portcheck = "AGENT_ENV_TEST_PORT";
  };
  environment = flake.lib.mkProject { inherit pkgs; roots = [ producer ]; };
  activation = flake.lib.mkCachedActivation { inherit pkgs environment; };
in pkgs.symlinkJoin {
  name = "activation-port-check-tools";
  paths = [ activation pkgs.python3 ];
}
NIX
nix --extra-experimental-features 'nix-command flakes' build --impure \
  --file "$run/fixture.nix" --out-link "$run/tools" \
  > "$run/build.log" 2>&1
readlink "$run/tools" > "$run/output.txt"
```

Continue in the same shell. Test execution reuses that built output and creates an isolated project, HOME and CODEX_HOME. No service is launched or network port bound. The helper remains the real Nix-generated packaged activator; no manifest, installer or runtime stub is supplied.

```bash
mkdir "$run/project" "$run/home"
export HOME="$run/home" CODEX_HOME="$run/home/.codex"
export AGENT_ENV_TEST_PORT=19091
"$run/tools/bin/agent-env-activate" --project "$run/project" \
  > "$run/activate-19091.log" 2>&1
"$run/tools/bin/python3" - <<'PY' > "$run/check-19091.log" 2>&1
import os, pathlib, tomllib
p = pathlib.Path(os.environ['PORT_TEST_RUN']) / 'project/.codex/config.toml'
with p.open('rb') as f:
    server = tomllib.load(f)['mcp_servers']['portcheck']
assert server == {'url': 'http://127.0.0.1:19091/mcp'}, server
print('PASS: first literal URL')
PY
export AGENT_ENV_TEST_PORT=19092
"$run/tools/bin/agent-env-activate" --project "$run/project" \
  > "$run/activate-19092.log" 2>&1
"$run/tools/bin/python3" - <<'PY' > "$run/check-19092.log" 2>&1
import os, pathlib, tomllib
p = pathlib.Path(os.environ['PORT_TEST_RUN']) / 'project/.codex/config.toml'
with p.open('rb') as f:
    server = tomllib.load(f)['mcp_servers']['portcheck']
assert server == {'url': 'http://127.0.0.1:19092/mcp'}, server
print('PASS: changed port reached literal URL through cached activator')
PY
```

Expected evidence is successful existing declaration evaluation, a successful fixture build, and the two exact structured URL assertions. This checks the outstanding Nix wiring, not another broad regression of the already passed host cases. The fixture is rooted only in its independent `/tmp` directory; leave its logs/output/project in place for review, without touching production or user config.

Stop at the first failed preparation, build, activation or assertion and record the command, exit code and log. An external fetch/environment failure permits at most one retry of the failed stage after an identified repair, keeping revision, expression, inputs and assertions unchanged and saving retry logs under a new suffix. Do not retry authorization denial or the known command-before-start environment failure without a restored authorized environment. For a genuine assertion failure, retain the result and stop for diagnosis; do not alter expected output to obtain PASS. No extra model/service or host-suite rerun is part of this recipe.

## Retained results

Execution design and focused test steps approved by independent reviewer before implementation/testing (2026-10-24).

- Existing Python `/workspace/shared/agent-env-nix-venv/bin/python`, tomlkit 0.13.3.
- `python -m unittest discover -s tests -p test_activate.py -v`: PASS, 30 tests.
- `python -m unittest discover -s tests -p test_cached_activation.py -v`: PASS, 8 tests. The port test runs the real config helper and real prepared commit in a temporary project; installer/root mechanics remain a fixture, not Nix-generated integration.
- `bash -n runtime/activate.sh runtime/cached-activate.sh`: PASS.
- `git diff --check`: PASS.
- Logs: `/tmp/agent-env-port-tests.XsTG4Hsd/{config,cache,shell,diff}.log`; final affected-file reruns in `config-final.log` and `cache-final.log`. No failed attempt. Self-review tightened authority validation and preserved all original non-port URL bytes (including scheme case and empty query/fragment delimiters); the two affected suites were rerun successfully.
- Nix evaluation/build, new Nix assertions, and actual Nix-generated manifest/activation integration: NOT RUN, no available Nix executable. The test author did not attempt installation; the parent later reported an authorized installation could not start because the execution environment failed before the command ran. Darwin/live MCP/real GC-root evidence not claimed.

Scope note: the decimal input grammar is bounded to 1–5 ASCII digits (including leading zeros); this is documented and tested. During the recorded local implementation/test run, no credentials, user computer, upstream pin or external repository state changed; the candidate was subsequently published as PR #6.

## Gate status and remaining work

The [independent review](../activation-port-env-review.md) records the previous first-gate scope approval, second-gate host-fixture recipe approval, and third-gate PASS limited to the executed 30 ConfigEditor and 8 cached-wrapper tests. This split does not reopen unaffected checks or rerun them solely because document paths or commit IDs change. The independent normal-review update approves this split-plan design and first-gate scope; approval is recorded in the linked review, not issued by the author.

Nix declaration assertions and the actual generated metadata → manifest → packaged cached activator connection remain NOT RUN, not a product failure and not a host-fixture PASS. The existing goal is to exercise one mapped HTTP environment through the supported packaged activator and observe the literal URL update when its port changes. No live MCP/model, platform matrix, or extra testing framework is added.

The parent coordinates an execution owner once an authorized environment can run Nix. The concrete Nix recipe above received second-gate approval in the linked independent normal review. Execution remains conditional on a working authorized environment; second-gate approval is not Nix execution or third-gate PASS. The missing Nix result remains outstanding. Until the remaining evidence and applicable remote merge constraints are resolved, the feature remains NOT_READY.
