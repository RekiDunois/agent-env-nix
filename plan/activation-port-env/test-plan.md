# Activation-time MCP port: test plan

Baseline: main `c368871942435bdc178a1063ce9c677acaf8cabc`. Product/reviewed PR revision: `04f22a464e26207746a619312e80f6d6df6fccf9` ([PR #6](https://github.com/RekiDunois/agent-env-nix/pull/6)).

Document revision: split-plan v1 with execution results, 2026-10-24. The user requested separate plans and normal review, then authorized completing the existing tests and pushing the results to PR #6. Product and test code, requirements and test scope remain unchanged. The previous combined path is navigation only.

## Required scope and checks

- ConfigEditor tests: absent variable/default, explicit valid ports (including bounds), literal URL and no metadata leakage, IPv6 plus path/query/fragment preservation; invalid values/default declarations fail with config/state unchanged.
- Lifecycle tests: generated URL upgrades on port change; equal unowned reuse and unequal source conflict use resolved values; manual edit protection remains; changing environment after prepare does not alter commit.
- Cached wrapper fixture: exercise real config resolver for fingerprint and prepared config, with only Nix/root/installer mechanics stubbed. Verify same effective URL skips, changed port applies, invalid value fails rather than skips, failed apply removes marker, and existing unmapped wrapper behavior remains.
- Run the existing narrow Nix assertions for declaration acceptance/rejection and metadata isolation, then build and exercise the actual Nix-generated activator through the recipe below. The historical cloud environment was blocked; the current execution uses the already-installed local Nix. Results and failed attempts are recorded below.
- Run relevant Python tests with already available tomlkit, shell syntax checks, and `git diff --check`. No live MCP/service/model, Darwin installation, real GC-root certification, or full consumer matrix is required by this feature's local fixture scope. Record exact commands, results and limits below before review.

### Executable steps

本轮复用下文已通过的 30 项配置编辑测试、8 项缓存包装测试及原有语法检查结果；产品和这些测试代码均未变化，不重新安装或重跑。下段保留原执行环境和命令，作为既有记录。

Use the existing `/workspace/shared/agent-env-nix-venv/bin/python` (tomlkit 0.13.3 verified), from the candidate repository. Create an independent log directory with `mktemp -d /tmp/agent-env-port-tests.XXXXXXXX`. Run that Python with `-m unittest discover -s tests -p test_activate.py -v` and `-m unittest discover -s tests -p test_cached_activation.py -v`, saving each stdout/stderr and exit code. Run `bash -n runtime/activate.sh runtime/cached-activate.sh` and `git diff --check`. No Nix executable is currently available here; the blocked environment has not executed installation or Nix checks. This document-only revision does not attempt either. If a tool/fixture launch fails externally, diagnose and retry once only after a concrete repair; if still blocked stop that check and report it as unexecuted. A genuine assertion failure is retained, repaired within scope, and the affected test rerun, without deleting or weakening the assertion.

### Outstanding Nix checks: executable recipe

Run this only after a working, authorized Nix environment is available. It uses the existing flake inputs and public constructors, not copied runtime code or a new framework. GitHub access must already be authorized; stop on authentication or dependency-fetch failure rather than changing credentials. The selected product revision below is the unchanged product/test code already published in PR #6. A docs-only successor does not invalidate this result.

Preparation and build, from any directory outside the producer checkout:

```bash
set -euo pipefail
revision=04f22a464e26207746a619312e80f6d6df6fccf9
run=$(mktemp -d /tmp/agent-env-port-nix.XXXXXXXX)
export PORT_TEST_RUN="$run" PORT_TEST_REVISION="$revision"
printf '%s\n' "$run"  # Retain this directory and all attempts.
command -v nix
nix --version > "$run/nix-version.txt"
git clone --branch feat/activation-mcp-port-env --single-branch \
  https://github.com/RekiDunois/agent-env-nix.git "$run/source" \
  > "$run/clone.log" 2>&1
git -C "$run/source" checkout --detach "$revision" >> "$run/clone.log" 2>&1
test "$(git -C "$run/source" rev-parse HEAD)" = "$revision"
test -z "$(git -C "$run/source" status --porcelain)"
export PORT_TEST_FLAKE="git+file://$run/source?rev=$revision"
system=$(nix --extra-experimental-features 'nix-command flakes' \
  eval --impure --raw --expr builtins.currentSystem)
printf '%s\n' "$system" > "$run/system.txt"
case "$system" in x86_64-linux|aarch64-darwin) ;; *) echo 'Unsupported test system'; exit 1;; esac
nix --extra-experimental-features 'nix-command flakes' build \
  "$PORT_TEST_FLAKE#checks.$system.evaluation" --no-link \
  > "$run/evaluation.log" 2>&1
cat > "$run/fixture.nix" <<'NIX'
let
  flake = builtins.getFlake (builtins.getEnv "PORT_TEST_FLAKE");
  pkgs = flake.inputs.nixpkgs.legacyPackages.${builtins.currentSystem};
  producer = flake.lib.mkAgentPackage {
    inherit pkgs;
    id = "activation-port-check";
    version = "1";
    files = { };
    mcp.settings.servers.portcheck.url = "http://127.0.0.1:19090/mcp";
    mcpPortEnv.portcheck = "AGENT_ENV_TEST_PORT";
  };
  environment = flake.lib.mkProject { inherit pkgs; roots = [ producer ]; };
  activation = flake.lib.mkCachedActivation { inherit pkgs environment; };
in pkgs.symlinkJoin {
  name = "activation-port-check-tools";
  paths = [ activation pkgs.python3 ];
}
NIX
nix --extra-experimental-features 'nix-command flakes' build --impure \
  --file "$run/fixture.nix" --out-link "$run/tools" \
  > "$run/build.log" 2>&1
readlink "$run/tools" > "$run/output.txt"
```

Continue in the same shell. Test execution reuses that built output and creates an isolated project, HOME and CODEX_HOME. No service is launched or network port bound. The helper remains the real Nix-generated packaged activator; no manifest, installer or runtime stub is supplied.

```bash
mkdir "$run/project" "$run/home"
export HOME="$run/home" CODEX_HOME="$run/home/.codex"
export AGENT_ENV_TEST_PORT=19091
"$run/tools/bin/agent-env-activate" --project "$run/project" \
  > "$run/activate-19091.log" 2>&1
{
  yq -p toml -o json '.' "$run/project/.codex/config.toml" \
    | jq -e '.mcp_servers.portcheck == {"url":"http://127.0.0.1:19091/mcp"}'
} > "$run/check-19091.log" 2>&1
cp "$run/project/.codex/config.toml" "$run/config-19091.toml"
export AGENT_ENV_TEST_PORT=19092
"$run/tools/bin/agent-env-activate" --project "$run/project" \
  > "$run/activate-19092.log" 2>&1
{
  yq -p toml -o json '.' "$run/project/.codex/config.toml" \
    | jq -e '.mcp_servers.portcheck == {"url":"http://127.0.0.1:19092/mcp"}'
} > "$run/check-19092.log" 2>&1
cp "$run/project/.codex/config.toml" "$run/config-19092.toml"
```

本机等价步骤修订：先用 `yq` 解析 TOML，再用 `jq` 比较 `portcheck` 整张表；两个预期仍严格只有原定的 `url` 字段，分别为端口 19091 和 19092。原计划的 Python 断言不再使用。本机最初直接用 `yq` 比较两张表时，即使实际内容正确也返回失败，因此停止受影响步骤，保留原失败，不改变输入、预期、产品或检查范围。

本机准备复用本地执行工程师的已有预检：`yq` 版本 4.54.1、`uv` 版本 0.12.22、Nix 版本 2.34.8，平台 `aarch64-darwin`。此次只修订解析命令与继续位置，不重新安装依赖或运行正式用例。

本次继续使用 `/tmp/agent-env-port-nix.zahAY7C8` 中的固定产品版本、源码、构建输出、隔离项目及用户目录，不重新克隆、构建或首次激活。原始 `evaluation.log`、`evaluation-retry.log`、`build.log`、`activate-19091.log` 和误判的 `check-19091.log` 均保留。以下恢复步骤经专用实现符合性审核确认准备完整后，由本地执行工程师亲自运行，结果见本轮记录：

```bash
set -euo pipefail
run=/tmp/agent-env-port-nix.zahAY7C8
export PORT_TEST_RUN="$run"
export HOME="$run/home" CODEX_HOME="$run/home/.codex"
{
  yq -p toml -o json '.' "$run/project/.codex/config.toml" \
    | jq -e '.mcp_servers.portcheck == {"url":"http://127.0.0.1:19091/mcp"}'
} > "$run/check-19091-revised.log" 2>&1
cp "$run/project/.codex/config.toml" "$run/config-19091.toml"
export AGENT_ENV_TEST_PORT=19092
"$run/tools/bin/agent-env-activate" --project "$run/project" \
  > "$run/activate-19092.log" 2>&1
{
  yq -p toml -o json '.' "$run/project/.codex/config.toml" \
    | jq -e '.mcp_servers.portcheck == {"url":"http://127.0.0.1:19092/mcp"}'
} > "$run/check-19092.log" 2>&1
cp "$run/project/.codex/config.toml" "$run/config-19092.toml"
```

Expected evidence is successful existing declaration evaluation, a successful fixture build, and the two exact structured URL assertions. This checks the outstanding Nix wiring, not another broad regression of the already passed host cases. The fixture is rooted only in its independent `/tmp` directory; leave its logs/output/project in place for review, without touching production or user config.

Stop at the first failed preparation, build, activation or assertion and record the command, exit code and log. An external fetch/environment failure permits at most one retry of the failed stage after an identified repair, keeping revision, expression, inputs and assertions unchanged and saving retry logs under a new suffix. Do not retry authorization denial or the known command-before-start environment failure without a restored authorized environment. For a genuine assertion failure, retain the result and stop for diagnosis; do not alter expected output to obtain PASS. No extra model/service or host-suite rerun is part of this recipe.

## Retained host results

Execution design and focused test steps approved by independent reviewer before implementation/testing (2026-10-24).

- Existing Python `/workspace/shared/agent-env-nix-venv/bin/python`, tomlkit 0.13.3.
- `python -m unittest discover -s tests -p test_activate.py -v`: PASS, 30 tests.
- `python -m unittest discover -s tests -p test_cached_activation.py -v`: PASS, 8 tests. The port test runs the real config helper and real prepared commit in a temporary project; installer/root mechanics remain a fixture, not Nix-generated integration.
- `bash -n runtime/activate.sh runtime/cached-activate.sh`: PASS.
- `git diff --check`: PASS.
- Logs: `/tmp/agent-env-port-tests.XsTG4Hsd/{config,cache,shell,diff}.log`; final affected-file reruns in `config-final.log` and `cache-final.log`. No failed attempt. Self-review tightened authority validation and preserved all original non-port URL bytes (including scheme case and empty query/fragment delimiters); the two affected suites were rerun successfully.
- 历史状态：此前 Nix 求值、构建及生成清单到打包激活器的验证未执行；云端授权安装在命令开始前受阻。本轮补齐结果见下节，不将历史未执行记录改写成已执行。

Scope note: the decimal input grammar is bounded to 1–5 ASCII digits (including leading zeros); this is documented and tested. During the recorded local implementation/test run, no credentials, user computer, upstream pin or external repository state changed; the candidate was subsequently published as PR #6.

## 本轮 Nix 执行结果（2026-10-24）

角色：本地执行工程师。产品及测试版本：`04f22a464e26207746a619312e80f6d6df6fccf9`；本轮工作树基于文档后继 `84ba23d481ffd3573d397d53e8b1c71ad47c9398`，已确认两者的 `lib/`、`runtime/`、`tests/`、`flake.nix`、`flake.lock` 和 README 无差异。本轮不修改产品和测试代码，不改变上游固定版本。

环境：`aarch64-darwin`，Nix 2.34.8，`yq` 4.54.1，`jq` 1.8.2。原始输出、固定源码、实际配置和产物保留在 `/tmp/agent-env-port-nix.zahAY7C8`。项目、HOME 和 CODEX_HOME 均位于该目录内；未启动服务、绑定端口或连接模型。

| 项目 | 实际命令或操作 | 结果 | 原始记录 |
| --- | --- | --- | --- |
| 固定源码准备 | 按上述命令克隆 PR 分支，切到 `04f22a4`，确认提交和干净状态 | 通过，退出码 0 | `clone.log` |
| 声明检查首次尝试 | `nix --extra-experimental-features 'nix-command flakes' build "$PORT_TEST_FLAKE#checks.aarch64-darwin.evaluation" --no-link` | 环境受阻，退出码 1；Nix 缓存数据库只读，尚未执行产品检查 | `evaluation.log` |
| 声明检查唯一重试 | 解除沙箱对现有 Nix 缓存的写入限制后，运行同一版本和命令 | 通过，退出码 0；包含声明接受、拒绝和元数据隔离断言 | `evaluation-retry.log` |
| 真实构建 | `nix --extra-experimental-features 'nix-command flakes' build --impure --file "$run/fixture.nix" --out-link "$run/tools"` | 通过，退出码 0 | `build.log`、`output.txt` |
| 首次打包激活 | 设 `AGENT_ENV_TEST_PORT=19091` 后运行 `"$run/tools/bin/agent-env-activate" --project "$run/project"` | 激活通过，退出码 0 | `activate-19091.log` |
| 原检查命令 | `yq -p toml -e` 直接比较完整服务器表 | 检查步骤错误，退出码 1；实际配置正确，未计为产品失败或通过 | `check-19091.log` |
| 修订后检查首次配置 | `yq -p toml -o json` 解析，再由 `jq -e` 按上述精确整表预期比较 | 通过，退出码 0，地址为 `http://127.0.0.1:19091/mcp`；未重复激活 | `check-19091-revised.log`、`config-19091.toml` |
| 端口变更 | 设 `AGENT_ENV_TEST_PORT=19092` 后运行同一打包入口，并按上述命令比较整表 | 激活及检查均通过，退出码 0，地址为 `http://127.0.0.1:19092/mcp` | `activate-19092.log`、`check-19092.log`、`config-19092.toml` |

构建输出为 `/nix/store/b5pa978w8hvvhvr595vich7m6bmazzn7-activation-port-check-tools`。恢复执行整体退出码为 0。两次激活使用同一真实 Nix 生成产物及同一隔离项目，输入和预期未放宽；首次错误比较保留，修订仅恢复解析方式。不重新安装，不重跑无关测试。

本轮实际补齐了生产者端口声明到项目清单、配置解析及打包缓存激活器的连接验证。配置编辑 30 项、缓存包装 8 项和已有语法检查继续复用上述有效记录。本次交付的 `git diff --check` 由提交前检查确认。既定必测项均已有适用通过结果；未发现范围内产品缺陷。此记录属于执行结果，不自行签发测试第三关或合并批准。

## Gate status and remaining work

The [independent review](../activation-port-env-review.md) records the previous first-gate scope approval, second-gate host-fixture recipe approval, and third-gate PASS limited to the executed 30 ConfigEditor and 8 cached-wrapper tests. This split does not reopen unaffected checks or rerun them solely because document paths or commit IDs change. The independent normal-review update approves this split-plan design and first-gate scope; approval is recorded in the linked review, not issued by the author.

Nix declaration assertions and the actual generated metadata → manifest → packaged cached activator connection now have the executed results above. The original first- and second-gate approvals remain applicable: the parser correction preserves the same complete-table assertion and both expected URLs. The dedicated preparation reviewer checked the corrected recipe without running tests or issuing a test-gate verdict. No live MCP/model, platform matrix, or extra testing framework is added.

本轮测试执行已完成，产品代码无需修复。下一负责人：测试结果审核负责人按现有范围确认第三关，随后由合并审核负责人处理 PR 的合并条件；执行工程师提交并推送本轮记录。此前因 Nix 未执行而保留的测试缺口已经补齐，草稿状态和正式合并结论不由本记录改变。
