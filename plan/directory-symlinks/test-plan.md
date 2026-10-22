# 目录符号链接测试计划 v2.1

修订日期：2026-10-22。需求为用户当日确认的目录符号链接支持，基础版本为 `91861b4f028eda1dbeb41481dcc48cd7c4a60874`；产品代码继续沿用 PR #5 的 `0e916fab4859e9a98b64aef736b329399ee3ee86`。v2.1 在计划提交 `995f0a608b0f564bd24891f9f6ef854f88f1e64a` 上，仅将配置保护方法的异常断言限定为 `owned value was edited`；测试版本为包含该修改的本提交。业务目标、输入、预期及运行入口不变。参见[执行计划](execution-plan.md)、[既有独立审核](../directory-symlinks-review.md)和[本轮修订审核](test-plan-review.md)。

## 当前范围和关口

依据[测试工程师规则](https://app.notion.com/p/3d80101a85f380d8a8f5ce528141e253)、[项目共识](https://app.notion.com/p/3d60101a85f3815a8c43f271f2b4d91d)及[正式平台需求](../../docs/requirements.md)，正式验收平台为 `aarch64-darwin`。本次修订落实 [PR 第二关审核指出的步骤缺口](https://github.com/RekiDunois/agent-env-nix/pull/5#issuecomment-6340314121)，不改变已通过第一关的 4 项清单。旧审核中“不要求苹果电脑执行”的说法仅保留为历史记录；当前平台与步骤以本文件为准。

| 业务目标 | 输入或场景 | 预期结果 | 唯一检查入口 |
| --- | --- | --- | --- |
| 目录链接的安装、更新、删除 | `.agents`、`.agents/skills`、`.codex`、`.codex/agents` 指向项目外现存临时目录，路径含空格；安装后修改选中叶子，再安装和删除 | 完整写入选中技能与代理文件；再次安装替换选中叶子；删除只清理已记录叶子；4 个目录链接和无关文件保留 | `ShellActivationTests.test_directory_links_support_apply_upgrade_remove` |
| 无效目录链接保留 | 父链接先指向不存在的目标，再指向普通文件 | 激活失败，不替换链接、不创建缺失目标、不修改普通文件 | `ShellActivationTests.test_invalid_directory_link_is_not_replaced` |
| 选中叶子链接不被跟随 | 选中技能叶子为指向外部目录的链接 | 替换链接并安装选中技能，外部目标文件保留 | `ShellActivationTests.test_selected_leaf_symlink_is_replaced_without_following` |
| 链接目录内的配置编辑保护 | `.codex` 指向外部目录；安装后编辑已生成的 MCP 配置，再删除 | 安装保留目录链接及无关配置；删除报告既有冲突，保留用户编辑和链接 | `ConfigTests.test_directory_link_preserves_config_edits_and_link` |

前三个方法位于 `tests/test_shell_activation.py`，第四个位于 `tests/test_activate.py`。采用现有测试断言；模拟的 `nix-store` 只检查激活流程，不证明真实垃圾回收根。已有 Linux 4 项通过及其审核继续有效，作为补充证据；2026-10-16 的旧苹果电脑结果不证明本次改动。当前苹果电脑配置保护方法通过，前三项因示例构建失败未执行，详见下方本地执行记录；第三关待结果审核者处理。

按[最新审核更正](https://github.com/RekiDunois/agent-env-nix/pull/5#issuecomment-6341116262)，第四项沿用同类测试的 `assertRaisesRegex`，确认删除失败来自用户编辑已生成配置。旧 Linux 配置方法结果只覆盖旧断言；收紧后的断言已在本轮苹果电脑执行中通过。其余 3 项既有 Linux 结果不受影响。不追加已撤回的重复链接断言或强制恢复分支；现有配置备用入口仍是可用步骤，不是准备失败后的通过前提。

## 苹果电脑准备和执行步骤

由本地测试工程师在已有 Nix 的苹果芯片电脑上，从本 PR 工作树根目录执行。保留 `flake.lock` 和现有存储缓存，不安装 Nix、不更新依赖。`repo` 取当前目录，`run` 是仓库外的输出目录；不要将示例项目安装到用户项目。

使用仓库 `tests/default.nix` 中 `runtime-unit` 的构建环境提供固定 Python、TOMLKit、Bash、coreutils、findutils、gnugrep、jq、flock。`nix develop` 只进入该环境，不执行其全套构建阶段；只运行下列 4 个方法。宿主的 `uv` 用于启动该环境的 Python，不下载解释器或额外依赖。命令没有模型、评估服务或外部 MCP 调用。

先在同一个 Bash 会话准备（`bash --noprofile --norc`）：

```bash
set -euo pipefail
repo="$PWD"
run=$(mktemp -d /tmp/agent-env-directory-links-darwin.XXXXXXXX)
printf 'repo=%s\nrun=%s\nplatform=aarch64-darwin\n' "$repo" "$run"
test "$(uname -s)" = Darwin
test "$(uname -m)" = arm64
nix --version > "$run/tools.log"
uv --version >> "$run/tools.log"
uv_runner=$(command -v uv)
git rev-parse HEAD > "$run/revision.txt"
export NIX_CACHE_HOME="$run/nix-cache"
export UV_CACHE_DIR="$run/uv-cache"
export PYTHONDONTWRITEBYTECODE=1
mkdir -p "$NIX_CACHE_HOME" "$UV_CACHE_DIR" "$run/fixtures"
```

在上述准备后构建当前示例输出。构建是取得本次生成的激活脚本所需准备，不是新增业务用例。正常预计 1–5 分钟，单次最多等待 10 分钟；执行者用运行工具的会话等待和超时功能控制，不安装额外超时工具。

```bash
environment=
if nix build --offline --no-update-lock-file --no-link --print-out-paths \
  "path:$repo#packages.aarch64-darwin.default" \
  > "$run/environment.txt" 2> "$run/build.log"; then
  printf 'build_exit=0\n' > "$run/build-status.txt"
  environment=$(cat "$run/environment.txt")
  test -f "$environment/lib/activate.sh"
else
  build_status=$?
  printf 'build_exit=%s\n' "$build_status" > "$run/build-status.txt"
  printf 'Build failed; skip shell methods and use the config-only steps.\n'
fi
```

只有构建成功、`environment` 非空且脚本存在时才执行下列命令；否则直接跳到配置方法的备用步骤，仍沿用当前会话的 `repo`、`run` 和 `uv_runner`。`AGENT_ENV_ACTIVATION_SCRIPT` 指向刚生成的脚本，不代入旧版本。测试内部各自建立临时项目、主目录和配置目录；在进入 Nix 环境后设置 `TMPDIR`，将它们置于本次输出目录下。当前测试会在每个方法结束时清理自己的临时目录，包括失败时；保留标准断言报告，不要求保留已清理目录或增加采集工具。

```bash
nix develop --offline --no-update-lock-file \
  "path:$repo#checks.aarch64-darwin.runtime-unit" \
  --command bash --noprofile --norc -c '
    set -euo pipefail
    cd "$1"
    export TMPDIR="$3/fixtures"
    export AGENT_ENV_ACTIVATION_SCRIPT="$4/lib/activate.sh"
    python --version
    test_python=$(command -v python)
    exec "$2" run --offline --no-project --no-config --no-sync \
      --no-managed-python --no-python-downloads --python "$test_python" \
      "$test_python" -m unittest -v \
      tests.test_shell_activation.ShellActivationTests.test_directory_links_support_apply_upgrade_remove \
      tests.test_shell_activation.ShellActivationTests.test_invalid_directory_link_is_not_replaced \
      tests.test_shell_activation.ShellActivationTests.test_selected_leaf_symlink_is_replaced_without_following \
      tests.test_activate.ConfigTests.test_directory_link_preserves_config_edits_and_link
  ' bash "$repo" "$uv_runner" "$run" "$environment" > "$run/tests.log" 2>&1
```

预计准备环境和测试共 1–5 分钟，单次最多 10 分钟。命令退出码为 0 且测试报告 4 个方法均通过，才记该次 4 项通过。断言失败记对应业务失败；解释器、依赖或环境启动错误记无法判断，未开始的方法记未执行。不要以构建成功或环境就绪代替业务结果。

若示例构建失败，停止依赖它的 3 个方法；第四项不依赖生成脚本，可单独使用现有开发环境执行一次（仅在第四项尚未运行时使用，不与上面的成功运行重复）：

```bash
nix develop --offline --no-update-lock-file "path:$repo" \
  --command bash --noprofile --norc -c '
    set -euo pipefail
    cd "$1"
    export TMPDIR="$3/fixtures"
    python --version
    test_python=$(command -v python)
    exec "$2" run --offline --no-project --no-config --no-sync \
      --no-managed-python --no-python-downloads --python "$test_python" \
      "$test_python" -m unittest -v \
      tests.test_activate.ConfigTests.test_directory_link_preserves_config_edits_and_link
  ' bash "$repo" "$uv_runner" "$run" > "$run/config-only.log" 2>&1
```

### 失败处理、结果保存与交接

- 默认每项一次，无自动重试。缓存缺失、权限不足或依赖不可用时，保留退出码和对应日志，停止受影响项；不下载新源、不改锁文件、不扩大权限求通过。需要权限的实际操作由执行者按环境审批要求处理。
- 只有已确认外部故障恢复、输入与断言不变且没有重复业务副作用时，允许受影响命令再尝试一次，总计最多两次。先说明恢复事实，使用新的输出目录和全新临时测试状态；保留第一次日志，不清除或覆盖它。没有恢复事实时停止，不连续重跑。
- 断言失败不因结果不满意重试。产品问题交产品实现负责人，步骤问题交测试计划工程师；修订后先核对影响，只复验受影响项，继续采用未受影响结果。已确认的业务失败不被之后的环境或清理错误覆盖。
- 正式记录写入本文件：实际产品和测试提交、计划 v2.1、工具版本、运行目录、实际命令及退出码、4 项结果、复用来源和未完成项。固定依赖由同版本 `flake.lock` 与上述环境入口说明，不采集全环境快照。原始输出保存在仓库外，入库记录只保留必要脱敏摘要。
- v2.1 准备阶段仅修正测试断言和同步记录，未构建或正式执行。其后本地执行情况见下节；结果取得后由结果审核者完成第三关。本次不要求全仓回归、真实用户安装或 Linux 重跑。

## 本地执行记录（2026-10-22，苹果芯片平台）

执行角色：本地执行工程师。完整执行计划为 v1，测试计划为 v2.1；产品代码版本为 `0e916fab4859e9a98b64aef736b329399ee3ee86`，实际工作树及测试版本为 `b2abbd2cf761fe612f1ccd148886552e4b4df8aa`。两版本之间只有计划文档及配置保护断言修正，产品代码与固定依赖没有变化。本轮只增加执行记录，不修改产品或测试。

实际平台为 `Darwin arm64`，Nix 为 `2.34.8`，uv 为 `0.12.22`，备用入口的固定 Python 为 `3.14.7`。依赖沿用该提交的 `flake.lock`。独立输出目录为 `/tmp/agent-env-directory-links-darwin.jg8KUuWd`；原始输出及临时缓存均在仓库外，不入库。

准备按上文执行，`repo` 为独立 PR 工作树当前目录，`run` 为上述目录。构建的实际命令为：

```bash
nix build --offline --no-update-lock-file --no-link --print-out-paths \
  "path:$repo#packages.aarch64-darwin.default" \
  > "$run/environment.txt" 2> "$run/build.log"
```

北京时间 21:14 开始，21:15 结束，退出码为 **1**。日志列出 1187 个待构建依赖；首个明确失败为固定依赖 `bmake-20260313.tar.gz`，下载地址返回 HTTP 404，随后示例环境因依赖失败而未生成。尽管使用 `--offline`，Nix 的依赖构建仍尝试下载该源文件；执行者没有另行下载、更新依赖或重跑构建。此为环境准备失败，不能判断前三项业务结果；4 方法主命令未启动。

随后执行上文完整的配置方法备用命令：`nix develop --offline --no-update-lock-file "path:$repo"`，在其固定环境内经 `uv run --offline --no-project --no-config --no-sync --no-managed-python --no-python-downloads --python "$test_python" "$test_python" -m unittest -v tests.test_activate.ConfigTests.test_directory_link_preserves_config_edits_and_link` 启动。内层 Bash、参数、`TMPDIR`、隔离和输出重定向均沿用上文备用步骤，输出保存为 `config-only.log`。21:15 执行完成，退出码 **0**，标准报告为 `Ran 1 test`、`OK`，没有业务失败或重试。

| 必测项 | 本轮苹果电脑结果 | 依据与未完成原因 |
| --- | --- | --- |
| 目录链接安装、更新、删除 | 未执行；当前无法判断 | 示例激活脚本构建失败，依赖它的方法未启动 |
| 无效目录链接保留 | 未执行；当前无法判断 | 同上 |
| 选中叶子链接不被跟随 | 未执行；当前无法判断 | 同上 |
| 链接目录内配置编辑保护 | 通过 | 备用方法退出 0，收紧后的异常文字断言及原有保留断言均通过 |

构建状态见 `build-status.txt`，配置方法状态见 `config-status.txt`，工具和版本见 `tools.log`、`revision.txt`。配置方法在自己的临时项目、主目录和配置目录中运行，结束后按原测试清理；没有安装到用户项目。既有 Linux 三项 shell 方法结果直接复用为补充证据；旧配置方法结果仍只覆盖旧断言，本轮苹果电脑结果覆盖当前断言。

未完成项为苹果电脑前三项。缺失依赖尚无恢复事实，不满足原步骤的重试条件；不更新锁文件、不改用旧激活脚本、不扩大测试范围。下一负责人为环境准备负责人，先恢复固定依赖的可用性；本地执行工程师随后只执行未完成的三项，已通过配置方法不因记录提交变化重跑。第三关与 merge 审核仍由相应审核负责人处理，本记录不作关口批准。

实现符合性审核由专用 `implementation_reviewer` 只读完成，覆盖完整执行与测试计划、全部相关产品及测试产物和必要调用连接，包括未修改部分。结论为**部分完成**：未发现需修改的产品代码问题；配置保护通过，前三项因构建失败未执行，停止重试符合计划。其唯一非阻断文字建议已落实，将旧“本轮未执行”明确为 v2.1 准备阶段。此为待审交付，不代表第三关或 merge 批准。

## 历史 v1 计划和云端步骤（保留记录，不是当前执行要求）

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
