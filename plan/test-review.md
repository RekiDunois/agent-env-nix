# Current platform scope: aarch64-darwin only

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

## Current third-gate result: TP2.2

2026-10-15 independent read-only result review: Third gate PASS; review completeness COMPLETE. Applicable to TP2.2, the approved fixture shebang correction and built za2cmnca1npfb4kv6m1wp44pssrszb1i-agent-environment. T1, T2, T3 and T4 PASS within the specified offline/two-example scope. Final runtime-unit 38/38 and INTEGRATION_PASS are accepted; upstream-copy is reused because the fixture correction did not affect it. The earlier interrupted attempt and 34/38 fixture-failure record remain recorded.

No in-scope result is missing or an unhandled failed test. Darwin runtime, formal Codex eval, live MCP and six-producer regression were not performed and are outside this conclusion. No tests were rerun by the reviewer. This is not merge approval.
