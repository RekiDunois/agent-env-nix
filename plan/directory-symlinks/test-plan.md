# Directory symlink support: test plan v1

Requirement revision: user decision 2026-10-22. Baseline: `91861b4f028eda1dbeb41481dcc48cd7c4a60874`. See the separate [execution plan](execution-plan.md) and [independent review](../directory-symlinks-review.md). This file preserves the previously reviewed test scope, recipe and results; splitting the documents adds no test requirement or rerun.

## Test plan and recipe

Only temporary offline fixtures. No real Nix installation, Codex eval, MCP calls, consumer business regression or Mac execution. Existing unittest assertions are sufficient; no new test framework.

1. Directory-parent installation lifecycle: `.agents`, nested `skills`, `.codex`, nested `agents` link to existing external temporary directories (path includes spaces). Apply writes complete selected skill/native-agent output, second apply replaces a modified selected leaf, remove deletes only owned leaves. Assert all four links and unrelated sibling survive. Existing `test_shell_activation.py` fixture uses fake nix-store solely for orchestration.
2. Invalid directory targets: dangling parent link and then a link to a regular file fail, retaining link and target content. Existing selected-leaf-link test confirms that selected leaf replacement still does not traverse its target.
3. Config compatibility: through linked `.codex`, preserve unrelated config and link on apply; a user edit to generated MCP makes remove report a conflict while retaining the edit. Use `test_activate.ConfigTests.test_directory_link_preserves_config_edits_and_link` with existing ConfigEditor fixture.

Preparation: use the candidate activation's fixed Nix Python 3.14.7 with tomlkit through the existing isolated Nix wrapper, plus its available Bash, jq, coreutils, find and flock. Shell checks require `AGENT_ENV_ACTIVATION_SCRIPT` to be the candidate generated example activation script; do not silently substitute an old script. Run the three affected shell methods and the config method directly with unittest. Save output in a fresh `/tmp/agent-env-directory-links-*` directory. If candidate generation is unavailable, record shell execution as not run, not PASS; config tests remain independently executable. No repeated external attempts; a missing dependency blocks only its affected method. Fix code or recipe errors before rerunning the affected method and preserve prior output.

Concrete cloud recipe (after independent plan review):

```sh
cd /workspace/shared/agent-env-symlink-fix
run=$(mktemp -d /tmp/agent-env-directory-links-XXXXXXXX)
printf '%s\n' "$run"
/workspace/shared/nix-bootstrap/bin/nix build --offline --no-link --print-out-paths \
  'path:/workspace/shared/agent-env-symlink-fix#packages.x86_64-linux.default' > "$run/environment" 2> "$run/build.log"
AGENT_ENV_ACTIVATION_SCRIPT="$(cat "$run/environment")/lib/activate.sh" \
/workspace/shared/nix-bootstrap/bin/run /nix/store/zdannjn9d1wpqasggzpwiydrgqzvwh3d-python3-3.14.7-env/bin/python -m unittest -v \
  tests.test_shell_activation.ShellActivationTests.test_directory_links_support_apply_upgrade_remove \
  tests.test_shell_activation.ShellActivationTests.test_invalid_directory_link_is_not_replaced \
  tests.test_shell_activation.ShellActivationTests.test_selected_leaf_symlink_is_replaced_without_following \
  tests.test_activate.ConfigTests.test_directory_link_preserves_config_edits_and_link \
  > "$run/tests.log" 2>&1
```

The existing isolated Nix wrapper supplies its private store and does not install Nix on the host or a user project. Offline example output construction is fixture preparation, not a full `flake check`. If offline construction cannot finish, do not fetch or install new sources; run only the config method with the existing Python and report the shell cases unexecuted.

## Execution record (2026-10-22, cloud Linux)

Independent plan review accepted v1 before execution; the formal reviewer record is separate. Candidate baseline is 91861b4 plus this PR's diff. Offline example construction succeeded, producing `/nix/store/1dyqmbg5nd5xdh1kw6cgxlgfsx51fv6r-agent-environment`; only activation script and example environment derivations rebuilt. No real project installation was performed.

- First test launch: could not execute host virtualenv Python inside the isolated Nix namespace (exit 127), no test methods ran. Recipe corrected to the generated activation's existing fixed Python 3.14.7 + tomlkit path above.
- Second attempt: all three shell methods succeeded. The config method errored because its first draft did not catch the existing, correct `ActivationError` for hand-edited owned config on remove. Product behavior preserved the edit. The test/recipe were corrected to expect that established conflict behavior rather than changing product behavior.
- Third attempt: only the corrected config method reran and succeeded. Prior shell outcomes are reused, not rerun for this assertion/document-only correction.

Current observed results: directory apply/upgrade/remove, invalid link retention, selected-leaf non-traversal, and linked-directory config protection all succeeded in their focused checks. Logs remain outside Git in /tmp/agent-env-directory-links-m3hBaFjZ (`build.log`, `tests.log`, `tests-2.log`, `config-3.log`). No Darwin real-install or full regression claim. Independent result/code review is complete in [the review record](../directory-symlinks-review.md), including Gate 3 PASS for these four methods. That record does not grant formal PR merge approval; the author does not self-approve.
