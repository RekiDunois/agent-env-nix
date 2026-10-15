# Current platform scope: aarch64-darwin only

2026-10-15 user clarification: first-round support and acceptance target only aarch64-darwin. Linux support/builds are not delivery or testing gates; existing platform code is unchanged. Prior design and static-code approvals remain valid for unchanged behavior; only platform statements receive this targeted review. Linux execution results and their result-review PASS remain historical supplementary evidence, not Darwin validation. Darwin build/runtime execution has NOT RUN and Darwin acceptance remains pending. This documentation-only addendum passed independent targeted platform review on 2026-10-15; no tests were rerun.

# R3 shell/config simplification validation

Validated on 2026-10-15 in the existing cloud Linux workspace, with Nix 2.35.3 and unchanged locked inputs. Product baseline: main 3b08c9e652dd8df5f3c1686347ef671476022335. This record describes the implementation candidate published with this change; it does not imply merge approval.

## Current scoped results

- T1: PASS. Standard-tool payload builder checks cover complete files, dotfiles, empty directories, executable bits and internal-link materialization, with the existing source-boundary failures. The original unsafe/overlap destination assertions are forced by runtime-unit. The real pinned upstream copy-tree check passed.
- T2: PASS. The existing two-example integration replaced preexisting same-name skill/agent content, removed stale content inside the selected skill, replaced direct edits on repeat apply, and removed recorded exports while retaining unrelated settings/comments/MCP and sibling skill.
- T3: PASS. Existing MCP-only checks cover equal-unowned reuse, conflicting/edited values, source checks, unrelated settings/comments, whole-file snapshots, config interruption bookkeeping and repeat/remove behavior.
- T4: PASS within the existing offline scope. Shell checks cover unsafe destination components, selected leaf symlinks, interrupted copy/full rerun, root registration failure, generation-switch retention/release, and known legacy inventory conversion/unknown state. Integration observed actual indirect GC-root registration and release; no GC deletion was run.
- Final runtime-unit result: 38 tests, all passed. The retained count is a report, not an acceptance requirement. The upstream-copy target and one real integration run also passed.

The built environment was /nix/store/za2cmnca1npfb4kv6m1wp44pssrszb1i-agent-environment. Source hashes: runtime/activate.sh 925ba25cd284def43b39247be186d34542e044d7bdf2c848ed98fcc6032a2be7; runtime/config.py 383785dab2ef6ba00514008c7a3b6eed7e8ee4de4f0da532b0a01aec981a117c. The unchanged producer API/graph/MCP normalization is supported by prior unaffected results plus current construction of the two examples; no blanket graph/platform rerun was required.

## Attempts and correction

An initial attempt was interrupted during authorization clarification; its captured output only showed an official-cache connection warning. After explicit authorization, official cache downloads succeeded and both examples/environment built. In that first completed offline run, upstream-copy passed and 34 of 38 unit checks passed; four shell fixture checks failed because their fake executables used /usr/bin/env, which is absent in the Nix build sandbox. This was test wiring, not a product assertion change.

The fixtures now use the absolute Bash supplied by runtime-unit. Independent second-gate review accepted this narrow correction; the full runtime-unit was rerun (including the root-failure scenario whose earlier apparent success could have been caused by the interpreter error). All 38 passed. The already-passing upstream-copy result was reused, then the two-example integration exited 0 with INTEGRATION_PASS. Original failure output and corrected output were retained separately.

Commands are the exact TP2.2 steps in [test plan](../plan/test-plan.md), with only runtime-unit selected for the fixture correction rerun. Local output directory: /tmp/agent-env-shell-check.OobkKE; logs offline.log, offline-authorized.log, offline-fixture-fixed.log, build.log and integration.log. These are ordinary local execution outputs, not committed raw artifacts. The integration fixture remained under that output directory and successful remove released its managed root.

## Limits

- No formal Codex eval, model invocation, live MCP service, real consumer migration, six-producer regression or user Mac operation.
- No Darwin build/runtime execution; the Linux pass does not imply macOS runtime compatibility.
- No whole-project atomicity or cross-file recovery: failure can leave partial selected files until rerun.
- The config snapshot guard protects observed changes; the existing narrow compare/replace race with arbitrary external editors remains.
- Prior tests below are historical and apply only where their behavior remains unaffected.

## Historical pre-refactor results

# Validation: initial two-package implementation

Validated on 2026-10-15 in the cloud Linux workspace. The repository's original LICENSE is unchanged: Git blob `6dab5e0f3d6834389faa196d426e461578332209`.

## Scope

The user approved two small examples, not a migration or a business regression suite:

1. `example-base`: complete skill directory, hidden support file, executable script, native Codex agent, and a fixed runtime dependency.
2. `example-tools`: explicit dependency on `example-base`, a real upstream fetch MCP module, and a real module-argument override.

The integration selects both roots, so the shared package is deployed once. It does not start the MCP service, contact a live API, use credentials, invoke an AI model, or touch a real consumer repository.

## Passed checks

- A real `flake.lock` was generated with Nix for the three exact input revisions. Both upstream nixpkgs inputs follow the shared pinned nixpkgs input.
- Nix parsing and graph/config evaluation succeeded. Existing evaluation assertions cover package overrides and callPackage, same-payload harness union, recursive/diamond dependencies, cycle and collision failures, disabled projection, and the bounded native MCP normalization.
- `nix flake check` passed on `x86_64-linux`, including genuine upstream copy-tree/config generation and the packaged Python test suite.
- All 54 authored Python unit checks passed both locally and inside the Nix check derivation: 46 activation checks and 8 payload-materialization checks. The activation unit tests use explicit fake external executables for lifecycle fault injection; the integration below uses the real Nix/upstream executables.
- `nix flake check --no-build --all-systems` passed evaluation for `x86_64-linux` and `aarch64-darwin`. This is **not** a Darwin build or runtime pass.
- `nix build .#example` built the real two-package environment, including the upstream fetch package and fixed native MCP configuration.
- The built launcher passed an isolated project apply → repeat apply → remove check. It verified complete regular-file skill copying, executable/hidden support files, native agent TOML, fixed MCP executable, preservation of unrelated comments/settings/MCP entries and a sibling skill, wholesale replacement of an edited owned generated skill, and safe removal.
- Actual `nix-store --query --roots` showed the environment registered at its generation-specific project root. Removal released that owned root. No garbage-collection deletion was run.

The final integrated environment output was `/nix/store/yc65qkm7xka0b1vqbg0i46jifb1j4i4z-agent-environment`. The final reviewed activation source SHA256 is `0f38ddaf696240096cf87473daa200ae6e8b93132779f748d1ba8c01d4c21487`.

## Reproduction

Ordinary checkout commands:

```sh
nix flake lock
nix flake check
nix flake check --no-build --all-systems
nix develop --command python -m unittest discover -s tests -p 'test_*.py' -v
out=$(nix build .#example --no-link --print-out-paths)
bash tests/integration.sh "$out"
```

The cloud run used Nix 2.35.3 through a task-local namespace wrapper, with the equivalent explicit flake reference `path:/workspace/shared/agent-env-nix`. That wrapper only supplies the local `/nix` mapping; the built application and tests are the repository code. The local Python pass used Python 3.12 and TOMLKit 0.13.3; the pinned Nix runtime pass used Python 3.14.7 and TOMLKit 0.15.0.

The integration script creates a temporary fixture, redirects HOME and CODEX_HOME to it, and retains the fixture path for inspection. It runs no service or model. Its generated environment root is removed at the end of a successful run.

## Corrections verified

A real first build caught a source-path context bug; it was fixed with context-preserving Nix interpolation and rebuilt successfully. Independent code review identified six bounded defects in config snapshot pairing, native-agent discovery/equality, untouched-attempt retry, reused-skill root retention, blank native metadata, and MCP path traversal. Those fixes were re-reviewed; all six findings were closed. The final unit/build/integration results above are after those corrections.

## Limits

- No macOS machine was used. Darwin outputs were evaluated only.
- No installed Codex binary/session was exercised. Native compatibility is grounded in the pinned Codex source contract in the implementation plan, with generated TOML checked locally.
- No real workflow repositories or downstream business behavior were tested.
- File-based config checks cannot validate unavailable managed/cloud/MDM sources or later session overrides. The README states that boundary.
- File publication uses atomic rename; skill replacement is journaled across an old-tree backup and a new-tree rename. This is not a whole-project transaction.


## Historical TP2.2 Linux execution steps (auxiliary evidence only)

The following records the already completed authorized cloud run. These Linux commands are retained for provenance, not prescribed as a current delivery/test gate or a request to rerun. They cannot establish Darwin compatibility.

The parent authorized affected offline verification after independent code review and this step review. Formal Codex eval remains excluded; no model, MCP service, six-producer business test or platform matrix is run. That preparation preceded the recorded execution; current results are in docs/validation.md.

Use the existing official task-local Nix 2.35.3 installation documented at /workspace/shared/nix-bootstrap/README.txt, including its already approved namespace wrapper. No reinstall, security-setting change or lock update. The current candidate root is /workspace/shared/agent-env-nix-simplify. All output and fixture files go in a new /tmp run directory. Example artifacts may use valid Nix caches; changed derivations cannot reuse old activation PASS.

From this cloud shell, prepare once:

```bash
set -euo pipefail
repo=/workspace/shared/agent-env-nix-simplify
run=$(mktemp -d /tmp/agent-env-shell-check.XXXXXX)
printf 'repo=%s\nrun=%s\nplan=TP2.2\n' "$repo" "$run"
```

### T1, T3, T4: directly affected existing offline checks

```bash
/workspace/shared/nix-bootstrap/bin/nix build --no-update-lock-file --no-link -L \
  "path:$repo#checks.x86_64-linux.runtime-unit" \
  "path:$repo#checks.x86_64-linux.upstream-copy" \
  2>&1 | tee "$run/offline.log"
```

The runtime-unit target supplies the pinned Python/TOMLKit and standard tools, the actual generated materialization builder template, and the built shell activation script. Existing test_materialize.py inputs exercise that builder; test_activate.py now checks only config; test_shell_activation.py relocates directly affected preexisting shell failure/lifecycle scenarios. Its fake nix-store tests orchestration only, while integration below checks actual roots. Source sentinel substitution is test fixture wiring, not another copy engine. Expected: both derivations succeed and unittest reports no failures. No separate unittest replay and no blanket full flake check is required. Unchanged graph/MCP normalization assertions retain prior evidence; the two existing unsafe/overlap build-contract assertions moved to Nix are explicitly forced by runtime-unit, so selecting that target covers them without rerunning checks.evaluation.

### T2 and real closure lifecycle: one existing two-example integration

Obtain the environment output (reuse the same cached build from runtime-unit):

```bash
/workspace/shared/nix-bootstrap/bin/nix build --no-update-lock-file --no-link \
  --print-out-paths "path:$repo#example" > "$run/environment.txt" 2> "$run/build.log"
out=$(cat "$run/environment.txt")
```

Run the existing integration in the already approved namespace, with pinned Python provided by the existing devShell:

```bash
/workspace/shared/nix-bootstrap/bin/run bash -c \
  'set -euo pipefail; export TMPDIR="$1"; cd "$2"; nix develop --no-update-lock-file "path:$2" --command bash tests/integration.sh "$3"' \
  bash "$run" "$repo" "$out" 2>&1 | tee "$run/integration.log"
```

The script creates isolated project/HOME/CODEX_HOME, prepopulates same-name files, checks full replacement and unrelated settings/siblings, edits the selected skill and agent and reapplies, then removes and observes actual roots. Expected exit 0 and its existing INTEGRATION_PASS marker. No agent service/model invocation and no GC deletion. The output path under /nix/store is accessed only inside the approved namespace; do not invent host-store symlinks.

Successful existing remove releases its managed roots. Integration failure fixtures and logs remain for diagnosis; do not delete their state/root links manually or change assertions to get a pass. Existing unittest fixtures are temporary and are cleaned after each case, including failures; their standard assertion/error report is the retained diagnostic output. This plan does not promise retained unit fixture directories or require new collection machinery. A command failure stops its dependent commands. For a confirmed external dependency/network fault, only after its recovery allow at most one additional same-input attempt (two total); keep each attempt log separately; do not rerun product assertion failures without a code/step fix and impact review. No already-passing unrelated checks are repeated.

