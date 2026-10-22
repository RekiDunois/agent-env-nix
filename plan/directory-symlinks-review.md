# Directory symlink support: independent review

Date: 2026-10-22. Reviewer: independent review agent, not the plan/code author. No tests were executed by this reviewer; no repository comment or merge action was performed.

Requirement revision: user's 2026-10-22 decision to support writing through user-chosen directory symlinks. Target: RekiDunois/agent-env-nix. Upstream baseline: `91861b4f028eda1dbeb41481dcc48cd7c4a60874`; local baseline snapshot: `65a0675`. Candidate: working-tree diff plus the then-combined `plan/directory-symlinks.md` v1 (now split into [execution plan](directory-symlinks/execution-plan.md) and [test plan](directory-symlinks/test-plan.md)), including its concrete offline recipe. Plan content SHA-256 at review: `abd5951255e94e66a65a98e0ee40c72945d56fbae419fd2c86ffeea796c602b5`.

Authority: Plan Reviewer Rule (2026-10-09), Test Engineer Rule (2026-10-09), Project Consensus (2026-10-19), and Merge Reviewer Rule (2026-10-09), read from their current referenced Notion pages. The user's newer directory-layout decision supersedes the old parent-symlink rejection, not the selected-leaf replacement or unrelated-file protection requirements.

## Execution plan

- P1 Requirement & Reality Grounding: PASS. The baseline shell guard and Python ancestor guard actually reject the reported layout. The current requirement, baseline and superseded decision are identified.
- P2 Solution Validity & Ownership: PASS. The shared installer is the owner; both generated shell copy calls and config helper are covered. No producer workaround, opt-in, whitelist or alternate installer is introduced.
- P3 Impact, Safety & Counterexample: PASS. Existing directory-link parents may point outside the project and remain links. Destructive operations remain restricted to validated selected leaf names. A selected leaf link is unlinked, not followed. State/lock checks stay strict. Config file links remain rejected, while directory ancestors are followed; existing ownership and snapshot checks are unchanged. Cross-project shared-target coordination and concurrent user retargeting are not newly promised. Cached activation retargeting requires the existing `--force` route.
- P4 Executability: PASS. Change points, failure behavior, lifecycle, documentation correction and preparation order are concrete. No schema change or user-project migration is needed.
- Gate review completeness: COMPLETE.
- Critical assumptions / unresolved impacts: none blocking within the stated scope.
- Required modifications: none.
- Plan conclusion: APPROVED.

This approves the current solution for implementation. It neither retroactively certifies the author's prior preparation sequence nor grants tests PASS or merge readiness.

## Test plan (initial review, before execution)

- Gate 1, required list: APPROVED. Directory-parent apply/upgrade/remove, invalid parent targets, selected-leaf non-traversal, and config preservation are directly affected behavior. No full regression, consumer workflow, external service, Darwin run or new test framework is required.
- Gate 2, executable steps: APPROVED. The recipe builds the candidate example offline with the existing isolated Nix wrapper and selects exactly three shell methods and one ConfigEditor method. It identifies the candidate activation script, temporary output directory, existing tools and offline-failure fallback. The fake nix-store is explicitly only orchestration coverage, not real GC-root evidence.
- Gate 3: NOT RUN. Execution and current-version results remain the execution owner's next step. Do not treat this record as test PASS. If offline preparation fails, retain that result and report the shell cases unexecuted; the config method remains independently executable.

## Static candidate implementation review

Reviewed the full diff in README.md, lib/project.nix, plan/implementation.md, runtime/activate.sh, runtime/config.py, tests/test_activate.py and tests/test_shell_activation.py, plus the relevant callers and unchanged config commit/state/cached-activation boundaries. No scope or implementation blocker found. The shell uses directory-following only for resource parents; state paths retain the default strict guard. Python still rejects a symlink at the final file and the state-directory commit check. Copy/remove preserves parent links and unrelated siblings under the supported stable-layout assumption.

Initial merge conclusion: NOT_READY solely because the required new test results have not yet been executed/reviewed and this is an unpublished working-tree candidate, not a final PR head. This is not a request for more tests. After execution, review Gate 3 and map the final diff to this candidate; only semantic changes need affected-scope re-review.


## Targeted result and final candidate review (2026-10-22)

The execution plan and production code are unchanged from the initial review. The current plan additionally records actual attempts and clarifies the existing hand-edited MCP conflict behavior. The test now expects `ActivationError` on remove and still asserts that the link and user edit survive. This corrects a test implementation mistake: the unchanged `ConfigEditor.prepare` explicitly rejects an edited owned MCP entry, and the preexisting `test_edited_owned_mcp_is_preserved` expects that same conflict. No product protection was weakened. The recipe now uses the candidate activation's already available Python 3.14.7 environment rather than the host virtualenv unavailable inside the namespace. These changes do not increase the required test scope. The implementation-plan cross-reference is documentation only.

Independent result review read the actual records in `/tmp/agent-env-directory-links-m3hBaFjZ`:

- `build.log` and `environment`: offline example output constructed at `/nix/store/1dyqmbg5nd5xdh1kw6cgxlgfsx51fv6r-agent-environment`.
- `tests.log`: initial launch failed before methods ran because the host virtualenv executable was unavailable; retained, not classified as product failure.
- `tests-2.log`: all three shell methods passed; config method raised the existing owned-value-edit conflict. This failed attempt is retained.
- `config-3.log`: corrected config method passed. Only this method reran; the unchanged shell methods retain their observed results.

Test Gate 1: APPROVED, unchanged scope.
Test Gate 2: APPROVED for the corrected fixed-Python recipe and conflict assertion.
Test Gate 3: PASS for all four required methods on this candidate. The reviewer did not run or rerun tests. This is Linux fixture evidence only, not Darwin real-install or real GC-root evidence.

Current candidate static review completeness: COMPLETE. Required code changes: none. No target-mapping, migration, target-registration or user-confirmation framework was added; resource directory symlinks are ordinary filesystem paths after the existing guard accepts them. Initial Plan P1–P4 approval remains applicable. Candidate plan SHA-256 at this result review: `7605944e374b28a6439395cdb1fc2a6800973ac99c224d33d3b3fa60900cbb1b`.

The candidate is suitable to publish as a draft PR. A final merge verdict is deferred until the published head/base are identified and mapped to this reviewed diff; no further test is requested solely for publication or SHA changes. This record does not authorize merging.

## Document structure update

The execution plan and test plan now occupy [separate execution](directory-symlinks/execution-plan.md) and [test](directory-symlinks/test-plan.md) files, as required by the user. The former combined path is navigation only. The preceding approvals and result review refer to the unchanged substantive candidate; this structure-only move does not constitute new approval and does not require rerunning tests. Historical plan hashes above identify the reviewed combined document, not the split files. Formal PR merge review remains pending.

### Independent structure-only re-review

The independent reviewer checked the separated execution and test files on 2026-10-22. The user's latest explicit instruction requires two files and supersedes the earlier same-file presentation decision. Both plans retain their previously reviewed substantive scope; the test file retains the recipe, all attempts and current results. The former combined file is navigation only, and the implementation-plan and review links resolve to the separate files. No product or test implementation changed. Previous Plan P1–P4 approval and Test Gates 1–3 remain applicable; no expanded test or rerun is required. The structure-only update is suitable for publication. Formal PR merge review remains separate.
