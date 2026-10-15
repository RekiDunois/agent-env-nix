# Current platform scope: aarch64-darwin only

2026-10-15 user clarification: first-round support and acceptance target only aarch64-darwin. Linux support/builds are not delivery or testing gates; existing platform code is unchanged. Prior design and static-code approvals remain valid for unchanged behavior; only platform statements receive this targeted review. Linux execution results and their result-review PASS remain historical supplementary evidence, not Darwin validation. Darwin build/runtime execution has NOT RUN and Darwin acceptance remains pending. This documentation-only addendum passed independent targeted platform review on 2026-10-15; no tests were rerun.

# Independent static code review

2026-10-15, R3 / implementation v0.6. Baseline main 3b08c9e652dd8df5f3c1686347ef671476022335. Independent reviewer did not edit or execute the product.

Initial complete review found three blockers: legacy JSON key/record validation after lossy line conversion; canonical project paths losing trailing newlines through command substitution; nonprivate state/invalid root objects rejected only after publication. The implementer moved exact JSON/raw inventory/type/permission/root validation before publication and uses NUL-delimited realpath. Follow-up identified the related incomplete-last-inventory-line/NUL ambiguity; full-file validation now rejects it before concatenation or cleanup.

Final reviewed runtime/activate.sh SHA256: 925ba25cd284def43b39247be186d34542e044d7bdf2c848ed98fcc6032a2be7.
Final static conclusion: PASS; reported blockers closed, review completeness COMPLETE. No additional blocker in the reviewed direct Nix/build/shell/config call chain. No native-agent content protection or cross-file recovery was restored.

This is static code review only, not executed-test PASS, Darwin runtime validation, or merge approval. Scoped execution status is separate in docs/validation.md.
