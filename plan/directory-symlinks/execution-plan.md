# Directory symlink support: execution plan v1

Review status: independent plan, code and targeted-result review completed in [the review record](../directory-symlinks-review.md); formal PR merge review remains pending. Requirement revision: user decision 2026-10-22 to support writing through user-selected directory symlinks. Baseline: `91861b4f028eda1dbeb41481dcc48cd7c4a60874`. This change supersedes only the parent-directory symlink rejection in the initial plan; it does not reopen unrelated gates or repeat the shared installer's full suite.

## Execution plan

Owner: agent-env-nix shared installer. Current `runtime/activate.sh:safe_path` rejects every link, including user directory layout; `lib/project.nix:copy_current` and `remove_leaf` use that guard. `runtime/config.py:safe_path` also rejects `.codex` ancestors, so changing only the shell check cannot support native agents and MCP configuration.

Change those guards to allow existing directory symlinks at resource parents, preserving their link objects and writing through them. Follow directory ancestors when reading/writing config, but continue to reject a linked config file itself, because atomic replacement would replace that link. Keep shell state/lock checks strict. Dangling links, directory cycles and links to files fail; do not create their missing targets or replace them. Copying and deletion stay at validated selected names, never clear a parent. Selected leaf links remain unlinked without following them. No schema, producer pin, upstream installation, opt-in or whitelist change.

Invariant: links chosen as parent layout survive; selected generated leaves can be replaced; other siblings and hand-edited config stay protected. Config's existing snapshot comparisons and ownership reconciliation are unchanged. The alternative of requiring users to turn links into real directories contradicts the new decision; dropping all path checks would also weaken state and leaf protections unnecessarily.

Compatibility/lifecycle: project lock and cached activation remain project-local and unchanged. Different projects sharing one target are not coordinated, as with preexisting shared-directory use. Do not change links during activation. Cached activation intentionally does not inspect installed content; after manually retargeting a directory link use `--force`. The new environment path naturally invalidates the old success cache. There is no migration or root cleanup; failed operations retain the existing rerun/remove behavior. No user project is touched in this task.

Implementation order: guard changes, update conflicting current documentation, focused tests in the separate [test plan](test-plan.md), independent code review, draft PR. Scope includes only the parent-link behavior and its direct config/leaf implications. Historical review records remain historical, not a current requirement to reject parent links.


The separate [test plan and results](test-plan.md) define the unchanged focused validation.
