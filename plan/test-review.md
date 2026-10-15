# Current third-gate result: TP2.2 aarch64-darwin (2026-10-16)

**Result review: PASS; review completeness: COMPLETE for the approved T1–T4 scope.** Requirement R3; approved TP2.2-candidate steps; product revision `d8629ecb9e89b6c22468d47cff0a7502e60327c4`, Apple Silicon arm64, Nix 2.34.8. The reviewed PR revision before this status-only documentation update was `2b42779db43f1c1395083ce2d21fb9b18ae3c1b8`. Its only commit after the tested product revision updated `docs/validation.md`; product code, test inputs and assertions were unchanged.

This third-gate review checked the approved test plan, direct test entrypoints (`tests/default.nix`, `tests/integration.sh`, and relevant existing unit cases), the accepted platform/path corrections, and the actual-run summary and output locations in [docs/validation.md](../docs/validation.md). Per Test Engineer Rule section 6, results obtained through the approved checks are adopted without requiring raw-log reanalysis or another test run.

| Approved goal | Accepted Darwin result | Basis |
| --- | --- | --- |
| T1, complete standard-tool copying | PASS | `checks.aarch64-darwin.runtime-unit` completed 38/38; `checks.aarch64-darwin.upstream-copy` succeeded. The previously approved static review covers the shell/Python responsibility boundary. |
| T2, selected replacement and bounded cleanup | PASS | The approved two-example integration exited 0 with `INTEGRATION_PASS`; it checked replacement after edits, removal of obsolete selected content, and unrelated sibling preservation. |
| T3, configuration protection | PASS | Relevant existing configuration checks passed within runtime-unit; the integration also checked preservation of unrelated configuration and removal of selected managed keys. |
| T4, failure, rerun, and root lifecycle | PASS | Existing unsafe-path, interruption/rerun, registration-failure, legacy-state, generation-switch checks passed; the integration observed real root registration and release without running garbage-collection deletion. |

The first Darwin invocation stopped before any derivation or test case because the sandbox's default Nix fetcher cache was read-only. This was a pre-execution environment blocker, not a T1–T4 business failure. With the user's explicit elevated authorization, the same approved checks completed using `NIX_CACHE_HOME="$run/nix-cache"` inside the isolated run directory. The initial diagnostic excerpt and successful run logs remain at the location recorded in `docs/validation.md`; no lock update, new test method or changed assertion was introduced.

First gate (T1–T4 required scope): **PASS, unchanged**. Second gate (step executability/scope): **PASS**, including the previously reviewed macOS physical temporary-path correction. Third gate (current Darwin results): **PASS**. The historic Linux third-gate PASS is supplementary and does not substitute for these Mac results. No in-scope target is missing or has an outstanding recorded business failure. The previously accepted case-only rename risk remains an accepted known risk, not a claimed fix or a new test obligation.

This is a test-result review, not new formal test execution, product code review, or permission to merge. Formal Codex eval, live MCP/model calls, six-producer regression, Linux delivery checks, full platform matrix and additional evidence machinery remain outside the approved T1–T4 scope.

# Targeted integration path preparation review, 2026-10-15

Addresses [review comment 6199828186](https://github.com/RekiDunois/agent-env-nix/pull/3#issuecomment-6199828186) against d33b35bf0319be0320a3eca64165da30ef307fca. Immediately after mktemp, tests/integration.sh now canonicalizes its existing temporary directory with `base=$(cd "$base" && pwd -P)`. HOME, CODEX_HOME, project and the GC-root assertion then use the same physical path, avoiding false failures from macOS /var versus /private/var aliases.

Independent targeted static review of path preparation: PASS. The reviewer read the full integration script; the subshell does not change the caller's working directory, and failure still stops execution under set -e. This is one fixture-preparation line, with no product change, new test, changed assertion or expansion of T1–T4. Unaffected reviews and historical Linux evidence remain reusable. No tests were run or rerun for this correction. aarch64-darwin build/runtime acceptance remains NOT RUN; this is not a test-result PASS or merge approval.

# Historical platform-scope note (2026-10-15, before Darwin execution)

2026-10-15 user clarification: first-round support and acceptance target only aarch64-darwin. Linux support/builds are not delivery or testing gates; existing platform code is unchanged. Prior design and static-code approvals remain valid for unchanged behavior; only platform statements receive this targeted review. Linux execution results and their result-review PASS remain historical supplementary evidence, not Darwin validation. Darwin build/runtime execution has NOT RUN and Darwin acceptance remains pending. This documentation-only addendum passed independent targeted platform review on 2026-10-15; no tests were rerun.

# Current second-gate result: TP2.2

Independent reviewer on 2026-10-15: Second gate PASS; review completeness COMPLETE. Reviewed TP2.2-candidate SHA256 209140a01102593d2c8affc2cbb385ca614a9a68435edcc9d9bf73331d39b70c. The four TP2.1 step findings were closed: explicitly forced original path checks, restored original generation-switch scenario, accurate unit versus integration fixture retention, and a maximum one external retry. No scope expansion; no tests executed by reviewer. The incidental duplicate boolean check output was removed by the implementer. Third gate remains not performed pending execution.

## Prior design/scope record (superseded step status below)

# Independent scoped test-plan review

Date: 2026-10-15. Independent read-only reviewer, not the candidate author; no tests executed.

Test revision: TP2-candidate
SHA256: 274e73c23064f9856e9d03840175e9c895d1a2cd8e6f4fb95c86dba9668f6f75
Requirement: R3
Implementation: v0.6-candidate
Baseline: main 3b08c9e652dd8df5f3c1686347ef671476022335

Design review: PASS
First gate, required scope: PASS
Review completeness: COMPLETE
Second gate: PENDING exact post-implementation entrypoints, commands and execution instructions; not approved in this review.
Third gate: NOT PERFORMED; new results do not exist.

T1–T4 cover directly changed full copying, unconditional selected replacement/stale cleanup, MCP protection and failure/closure behavior. Scope remains the two existing business examples and directly related existing offline checks. No platform matrix, six-producer regression, formal eval, custom evaluator or provenance proof is added.

The complete candidate and existing entrypoints/assertions were reviewed. Obsolete agent ownership/discovery and cross-file recovery expectations must be replaced/removed. The historical 54-test count is not an acceptance requirement. Unaffected results can be reused through impact analysis. No execution is authorized merely by this design/scope approval.

Required modifications: none for design/first gate. Before any execution, fill in precise final commands and obtain the second-gate review within the approved scope. Parent confirmation remains required before implementation proceeds.

## Fixture correction after authorized first run

The first completed run passed upstream-copy and 34 of 38 unit checks; four shell fixtures failed due to /usr/bin/env absence in the Nix sandbox. The independent reviewer verified the sole fixture fix: fake executables use the already supplied Bash absolute path. tests/test_shell_activation.py SHA256 413ce13911d0669223003a4551993f394ed1a7524339233167a7a971aef948fc. Second-gate conclusion remains PASS, completeness COMPLETE. The reviewer agreed to rerun runtime-unit (not the already-passing upstream-copy) and then the approved integration. This was a wiring correction, not an altered expected result or scope expansion.

## Historical third-gate result: TP2.2 Linux execution (2026-10-15)

2026-10-15 independent read-only result review: Third gate PASS; review completeness COMPLETE. Applicable to TP2.2, the approved fixture shebang correction and built za2cmnca1npfb4kv6m1wp44pssrszb1i-agent-environment. T1, T2, T3 and T4 PASS within the specified offline/two-example scope. Final runtime-unit 38/38 and INTEGRATION_PASS are accepted; upstream-copy is reused because the fixture correction did not affect it. The earlier interrupted attempt and 34/38 fixture-failure record remain recorded.

No in-scope result is missing or an unhandled failed test. Darwin runtime, formal Codex eval, live MCP and six-producer regression were not performed and are outside this conclusion. No tests were rerun by the reviewer. This is not merge approval.
