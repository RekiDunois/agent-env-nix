# Shared cached activation extraction

2026-10-18, candidate implementation and scoped execution record. This is not a
formal plan approval, result-review decision, or merge approval.

## Scope and execution plan

- Base: agent-env-nix `2158e933aab6c845ae1ceb1228458d624f8777d5`.
- Source: [professor-contact PR #96](https://github.com/ScholarWorkflow/professor-contact/pull/96),
  head `47a7fe0831418178871d29218e2dc26be9c6119a`, unchanged product
  `4d59c0556de113cee554e8879236c9cc378ec826`.
- Extract its wrapper into `runtime/cached-activate.sh` and expose
  `lib.mkCachedActivation { pkgs; environment; name ? "agent-env-activate"; }`.
  Keep `--project`, default working directory, `--force`, `--help`, physical-path
  key, CDPATH correction, failure invalidation, atomic marker and fail-fast lock.
- Replace producer-specific state with one shared project marker/lock regardless
  of executable name. Require callers to compose roots into one environment;
  changing environments replaces the installed selection, not an additive merge.
- Preserve `lib/project.nix`, `runtime/activate.sh`, config protection, existing
  apply/remove semantics, input pins and platform scope. No contact/Study edits.
- Document direct apply/remove and manual-edit cache boundaries, forced repair,
  stale-lock recovery and consumer devShell/direnv usage.

## Test plan and actual results

Only the extraction and changed wiring need new checks. Run from the repository
root; Nix commands below used the already installed Nix 2.35.3 with local cached
inputs on the cloud Linux machine. No software installation or user's Mac use.

1. `python3 tests/test_cached_activation.py -v`: exit 0, seven offline stub
   methods. Covers first/skip/upgrade/force, failed upgrade/rollback/force,
   symlink alias/move, CDPATH relative paths, marker/lock/argument refusal,
   help/newline refusal, and differently named A → B → A/shared-lock behavior.
2. `bash -n runtime/cached-activate.sh`, Nix parse of the factory, and
   `git diff --check`: exit 0. Final publication repeats whitespace/parse checks.
3. `nix build --offline --no-write-lock-file --no-link .#checks.x86_64-linux.cached-activation`:
   exit 0. Builds the actual factory with a stub installer, runs the seven
   methods under pinned tools, checks default/custom executable names share a
   cache for the same environment, and checks forced reapply and lock cleanup.
   This is supplementary Linux wrapper/packaging evidence, not Darwin acceptance.
4. `nix eval --offline --no-write-lock-file --raw .#checks.aarch64-darwin.cached-activation.drvPath`:
   exit 0; evaluation only. Existing evaluation assertions, including rejection
   of an unsafe executable name, were evaluated via the x86_64-linux
   `checks.evaluation.drvPath` (exit 0).

The first packaging attempt caught a Nix test-fixture quoting typo before any
build ran; it was corrected and the identical scoped command then completed.

## Reuse and limits

PR #96's recorded Darwin build and isolated real direnv activation apply to its
original product only. Its cache algorithm and the shared installer's unchanged
behavior are relevant prior evidence; they do not demonstrate that this new
shared export was built or activated on Darwin. The current new factory's
Darwin build and real direnv integration have NOT RUN. No full business/model,
MCP service, browser, Zotero, or multi-repository regression was run or claimed.
Existing installer tests/results remain unchanged; this extraction adds no
installer behavior or filesystem-monitoring requirement.
