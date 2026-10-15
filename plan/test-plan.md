# Scoped test plan for activation simplification

Revision TP2.2-candidate, 2026-10-15. Requirement R3; implementation v0.6-candidate; baseline main 3b08c9e652dd8df5f3c1686347ef671476022335. Proposed review status: pending. This is a plan and affected-test revision proposal only; no tests or formal eval have been run for this change.

## Authority and scope

Follow [Test Engineer Rule](https://app.notion.com/p/3d80101a85f380d8a8f5ce528141e253) and [Project Consensus](https://app.notion.com/p/3d60101a85f3815a8c43f271f2b4d91d). The user approved the two existing examples and now changed file replacement/Python/journal semantics. Retain only checks needed for these changed behaviors and existing configuration/closure safety. Do not add examples, six-producer regression, formal Codex eval, MCP service calls, model runs, endpoints, credentials, platform matrix, custom evaluators, collectors or general failure-injection infrastructure. PR #2 recipes are not imported.

Only example-base and example-tools remain business examples. Existing offline synthetic unit checks can be adapted to the new entrypoints; their previous Python implementation is not the normative contract. Deleted semantics must have their assertions removed, not be preserved as gates against R3. No approval is inferred from old test counts.

## Required goals and primary existing entry

| Goal | Input / scene | Expected result | Existing primary check |
| --- | --- | --- | --- |
| T1 Complete standard-tool copying | Existing complete-tree/dotfile/executable/empty directory/internal-link fixtures and the two existing examples | Ordinary complete files and permissions survive; payload/project copying uses shell commands, Python only config | Adapt existing materialization checks to the shell builder; retain upstream-copy assertions. Static code review checks the language boundary, without a new runtime tracing tool. |
| T2 Unconditional selected files and bounded cleanup | Existing integration example, preexisting selected skill/agent, repeated apply after direct edits, previous exports removed from selection, then remove | Selected skill trees and agent files are entirely replaced regardless of prior content; obsolete recorded exports removed; unrelated sibling and containing roots untouched | Revise existing tests/integration.sh and adapt existing relevant activation checks; one primary integration lifecycle, no extra business examples. |
| T3 Config protection remains | Existing MCP equal-unowned, unequal/edited keys, automatic/extra config source, unrelated comments/settings, whole-file snapshot checks | Only selected managed MCP keys change; equal unowned entries stay unowned; conflicting user values and unrelated concurrent edits are preserved; file-only activation does not audit unrelated config | Retain relevant existing test_activate.py cases against config-only helper; discard native-agent discovery/conflict expectations. |
| T4 Failure and lifecycle match simplification | Existing unsafe-path/source fixtures, root-registration failure, interrupted copy/config update and generation/remove fixtures | Unsafe paths do not escape project; root failure publishes nothing; interrupted file work fails and full rerun converges without journal; required closure roots remain until safe cleanup; clean remove releases unneeded roots | Adapt directly corresponding existing offline checks and integration root observations, without new fault types or combination matrix. State migration behavior is covered by adapting the existing schema/state fixture rather than a new migration harness. |

Untouched graph resolution, producer override and MCP normalization tests remain in tests/default.nix but their prior valid results need not be rerun solely because this commit changes. Darwin runtime remains unverified. No new platform check is required. If an implementation change actually alters an allegedly untouched behavior, report its impact before expanding execution.

## Affected existing assertions

- Replace skill equality/unowned conflict and edited-agent protection expectations with selected replacement. Remove tests whose entire goal is agent alias/legacy/native-global discovery, agent unowned reuse, journal replay/backup recovery, or skill fingerprints. Retain unrelated-sibling checks.
- Split mixed agent/MCP cases so the existing MCP expectation survives and the obsolete agent gate does not. Keep ordinary TOML comparisons and existing unittest assertions; do not build a new oracle.
- Delete test_materialize.py's dependency on Python copy internals; adapt the existing input cases to the actual standard-tool build path. No recursive copy implementation in the tests.
- Adapt existing interruption checks to “nonzero, retained necessary roots, explicit rerun fully recopies selected resources”; do not require backups, old/new replay, completed-operation counters or whole-project transactions.
- Adapt integration's state observations to the minimal inventory/config state/root layout. Add preexisting/edited selected agent to the existing lifecycle rather than creating another test suite. Continue using the same two packages and existing formal bin/agent-env entry.
- Do not duplicate each goal across unit, integration and manual runs. Existing incidental overlap does not create another execution obligation. Preserve still-relevant tests but do not treat the previous count of 54 as an acceptance requirement.

## Preparation and exact scoped execution steps

The parent authorized affected offline verification after independent code review and this step review. Formal Codex eval remains excluded; no model, MCP service, six-producer business test or platform matrix is run. Implementation preparation itself has run no tests.

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

## Reporting and failure

Only report actual product/test revisions, goal outcomes (pass, business failure, inconclusive, not run), relevant existing output, reused results and their impact basis. Product assertion failures are not retried to seek a pass or hidden by cleanup. Environment failures are distinguished from product failures. Preserve failed integration fixtures and needed roots; retain ordinary unittest failure reports rather than claiming their temporary directories persist; do not manually erase state to bypass protection. No new collector, JSON proof ledger or upload is required. Any necessary expansion beyond the four goals must return to the parent/user with its concrete reason.

TP2 design/first-gate scope was independently approved; TP2.2 supplies the precise affected entrypoints and commands above for second-gate review without expanding T1–T4. Result review remains not performed. No test PASS is claimed before execution.

TP2.2 revision impact: second-gate findings addressed by forcing existing unsafe/overlap assertions in runtime-unit, restoring the existing generation-switch shell scenario, accurately distinguishing ephemeral unit fixtures from retained integration fixtures, and stating one maximum external retry. T1–T4 scope is unchanged.
