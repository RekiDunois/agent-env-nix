# Activation-time port review

NOT_READY — `RekiDunois/agent-env-nix`; base `c368871942435bdc178a1063ce9c677acaf8cabc`; candidate working tree reviewed on 2026-10-24, before remote PR/head publication. Local baseline snapshot commit `9b1c65452025788740a8c82807ae06624adf171b` is not a remote product revision.

## Scope and plan conclusion

Independent read-only review covered the complete candidate diff in README, package/project Nix wiring, config and activation runtime, both changed Python test files, Nix assertions, and `activation-port-env.md`, plus the existing normalization, ownership, snapshot, and cache call chains. The reviewer did not run tests, modify product code, approve a PR, or merge.

This is a bounded new producer API and persistent activation behavior, not a mechanical fast-merge correction. The review remains one affected-scope review without a full regression matrix or additional test framework.

Requirement: the user's 2026-10-24 approved direction is to read the devShell variable during activation and write a resolved literal URL, with producer declaration and without consumer/factory port plumbing.

Plan revision: `plan/activation-port-env.md`, current complete candidate. P1 Requirement & Reality Grounding: PASS. P2 Solution Validity & Ownership: PASS. P3 Impact, Safety & Counterexample: PASS. P4 Executability: PASS. Gate review completeness: COMPLETE. Plan conclusion: APPROVED. No critical plan assumption or unresolved impact remains.

The baseline `lib/package.nix` owns producer normalization and metadata; `lib/project.nix` constructs the native MCP config and project manifest; `runtime/config.py` prepares desired values before ownership/conflict checks and commits prepared bytes; `runtime/cached-activate.sh` owns the skip decision. These sources support the selected change points. Separate `mcpPortEnv` metadata avoids changing upstream server schema or emitting non-native Codex fields. A generic template or layered consumer override is unnecessary and outside the approved direction.

## Implementation and test-result review

No confirmed in-scope code blocker was found. Mapped URLs alone receive strict validation. The environment changes only their port; original non-port URL text is retained. The same resolver feeds cache identity and prepare. Commit retains prepared values. Existing selected-name ownership, equal-unowned reuse, unequal-source conflicts, user-edit protection, removal, and snapshot publication remain in the existing paths. Metadata is separate from native MCP settings.

The focused test design and first/second test gates were reviewed before execution. The reported final host-Python results are accepted for that scope: ConfigEditor 30/30 and cached-wrapper 8/8 PASS, including literal publication, port changes, invalid input, and existing protection behavior. The author also reports shell syntax and diff checks PASS. Final logs are `/tmp/agent-env-port-tests.XsTG4Hsd/config-final.log` and `cache-final.log`; initial successful logs remain alongside them. No failed attempt is reported. The reviewer read the final reports and did not rerun tests.

Third-gate conclusion: the executed host-fixture scope passes. This is not a Nix evaluation, Nix build, Darwin integration, live MCP, or real GC-root pass. No live model/service or broad consumer regression is requested.

## Outstanding evidence and merge state

- Nix declaration assertions and the actual Nix-generated producer metadata → project manifest → packaged cache-key/apply connection are NOT RUN. The host fixture explicitly supplies its manifest and installer stub, so it cannot prove this changed Nix connection. This is missing evidence, not a demonstrated code defect. The next execution owner, coordinated by the parent, should use an already authorized working Nix environment or suitable existing CI to check the changed declarations and one mapped HTTP environment through its packaged cached activator, observing a literal URL change after a port change. Do not install or change environments merely under this review, bypass the reported environment restriction, or add a new framework/full regression/model test.
- Remote PR head, required checks, approvals, and mergeability were not yet available for this pre-publication review. The parent must verify the published head and applicable repository constraints before any READY conclusion. No empty or unknown CI state is treated as passing.

Core candidate fingerprint for `runtime/config.py`: SHA-256 `9e18d13d690f4a5d01ff7b5bbb383cc1aeaca344ac98d0996314ccfabc5cbb15`. Later documentation-only edits do not invalidate the unchanged code or host-test conclusions. Product changes require only affected-scope re-review.

Draft PR publication can accurately carry these limits. This record does not approve or authorize merge.
