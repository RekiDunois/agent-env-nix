# Scoped test plan for activation simplification

Revision TP2.2-candidate, 2026-10-15. Requirement R3; implementation v0.6-candidate; baseline main 3b08c9e652dd8df5f3c1686347ef671476022335. The original TP2.2 execution and third-gate review are recorded in test-review.md and docs/validation.md. This Darwin-only scope addendum passed independent targeted review on 2026-10-15; it does not change code or rerun tests.

## Current platform acceptance

First-round delivery and testing target only aarch64-darwin. Linux support, Linux builds and a cross-platform matrix are not acceptance gates. Keep existing Linux code and historical run records unchanged as supplementary evidence. Darwin build/runtime checks have NOT RUN, so current Darwin acceptance remains pending; historical TP2.2 Linux PASS is not a Mac PASS. No new execution is authorized by this documentation change.

The required behavior goals T1–T4 below remain unchanged. On an authorized Apple Silicon Mac, the existing runtime-unit/upstream-copy checks and two-example integration are the intended entries; use checks.aarch64-darwin rather than Linux targets. The direct Mac steps below receive only targeted platform review; unchanged T1–T4 scope and prior design/step review are retained.

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

Untouched graph resolution, producer override and MCP normalization tests remain in tests/default.nix but their prior valid results need not be rerun solely because this commit changes. Darwin runtime remains unverified and its acceptance is pending. No Linux or platform-matrix check is required. If an implementation change actually alters an allegedly untouched behavior, report its impact before expanding execution.

## Affected existing assertions

- Replace skill equality/unowned conflict and edited-agent protection expectations with selected replacement. Remove tests whose entire goal is agent alias/legacy/native-global discovery, agent unowned reuse, journal replay/backup recovery, or skill fingerprints. Retain unrelated-sibling checks.
- Split mixed agent/MCP cases so the existing MCP expectation survives and the obsolete agent gate does not. Keep ordinary TOML comparisons and existing unittest assertions; do not build a new oracle.
- Delete test_materialize.py's dependency on Python copy internals; adapt the existing input cases to the actual standard-tool build path. No recursive copy implementation in the tests.
- Adapt existing interruption checks to “nonzero, retained necessary roots, explicit rerun fully recopies selected resources”; do not require backups, old/new replay, completed-operation counters or whole-project transactions.
- Adapt integration's state observations to the minimal inventory/config state/root layout. Add preexisting/edited selected agent to the existing lifecycle rather than creating another test suite. Continue using the same two packages and existing formal bin/agent-env entry.
- Do not duplicate each goal across unit, integration and manual runs. Existing incidental overlap does not create another execution obligation. Preserve still-relevant tests but do not treat the previous count of 54 as an acceptance requirement.

## Current aarch64-darwin execution steps

These are the existing approved checks with the platform and workspace entry changed for an Apple Silicon Mac. This is a targeted platform correction, not a new suite or a reopening of unchanged scope/design reviews. No execution is claimed or newly authorized here. Run only in an authorized Mac checkout; do not run these as Linux delivery gates. Keep unchanged locked inputs and the same two examples. No reinstall, lock update, model, live MCP, six-producer regression or platform matrix.

From the repository root on the authorized Mac:

```bash
set -euo pipefail
repo="$PWD"
run=$(mktemp -d "${TMPDIR:-/tmp}/agent-env-shell-check.XXXXXX")
printf 'repo=%s\nrun=%s\nplatform=aarch64-darwin\n' "$repo" "$run"
nix build --no-update-lock-file --no-link -L \
  "path:$repo#checks.aarch64-darwin.runtime-unit" \
  "path:$repo#checks.aarch64-darwin.upstream-copy" \
  2>&1 | tee "$run/offline.log"
nix build --no-update-lock-file --no-link --print-out-paths \
  "path:$repo#example" > "$run/environment.txt" 2> "$run/build.log"
out=$(cat "$run/environment.txt")
TMPDIR="$run" nix develop --no-update-lock-file "path:$repo" \
  --command bash tests/integration.sh "$out" 2>&1 | tee "$run/integration.log"
```

Expected: runtime-unit and upstream-copy succeed; the existing integration exits 0 with INTEGRATION_PASS. The integration uses isolated project/HOME/CODEX_HOME, replaces selected preexisting/edited files, preserves siblings/settings, and observes actual GC-root registration/release. No service/model or GC deletion runs. No separate unittest replay or full flake check is required. Untouched graph/MCP results remain reusable by impact analysis.

Keep failed integration fixtures and logs. Unit fixtures remain ephemeral with ordinary failure output retained. Stop dependent steps on failure; do not change assertions or delete state to seek PASS. A confirmed external dependency failure allows at most one same-input retry after recovery, with a separate log. Product failures require a fix and relevant impact review. Successful remove releases managed roots. The original Linux commands and attempts are preserved under the historical execution section in docs/validation.md; they are auxiliary evidence only.

## Reporting and failure

Only report actual product/test revisions, goal outcomes (pass, business failure, inconclusive, not run), relevant existing output, reused results and their impact basis. Product assertion failures are not retried to seek a pass or hidden by cleanup. Environment failures are distinguished from product failures. Preserve failed integration fixtures and needed roots; retain ordinary unittest failure reports rather than claiming their temporary directories persist; do not manually erase state to bypass protection. No new collector, JSON proof ledger or upload is required. Any necessary expansion beyond the four goals must return to the parent/user with its concrete reason.

TP2 design/first-gate scope was independently approved; TP2.2 supplies the precise affected entrypoints and commands above for second-gate review without expanding T1–T4. The subsequent third-gate PASS is limited to the recorded historical Linux scope; see test-review.md. Current Darwin acceptance remains pending, with no Darwin run claimed.

TP2.2 revision impact: second-gate findings addressed by forcing existing unsafe/overlap assertions in runtime-unit, restoring the existing generation-switch shell scenario, accurately distinguishing ephemeral unit fixtures from retained integration fixtures, and stating one maximum external retry. T1–T4 scope is unchanged.
