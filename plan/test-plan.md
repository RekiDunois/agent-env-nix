# PR #1 测试计划与执行步骤

版本：TP1.1（2026-10-15）。目标产品：`760c1bf60e8ec19d1985660ec5e3276a8ef80b5a`，RekiDunois/agent-env-nix PR #1。作者状态：候选，第一关、第二关均待独立审核；第三关未进行。本文件是唯一完整测试计划，步骤也在此文件。`docs/validation.md` 是已有开发验证记录，不是另一份正式计划，也不表示本计划任何关口已经通过。

## 1. 依据、范围与入口

依据已确认的 [R2](../docs/requirements.md)、[实施计划 v0.5](implementation.md)、用户批准的两个小示例，以及 [Test Engineer Rule](https://app.notion.com/p/3d80101a85f380d8a8f5ce528141e253) 和 [PROJECT_CONSENSUS](https://app.notion.com/p/3d60101a85f3815a8c43f271f2b4d91d)。实施计划的独立批准不代替测试批准。

业务输入只使用 `examples/default.nix` 的 `example-base` 与 `example-tools`：前者包含完整 skill、隐藏支持文件、可执行脚本、原生 agent 和固定 runtime；后者显式依赖前者，并声明真实 upstream fetch MCP，使用现有参数 override。项目同时选择这两个根。

仅复用现有检查入口，不增加示例、业务回归、夹具、专用判定器或证据设施：

- `tests/default.nix`：`evaluation`、`runtime-unit`、`upstream-copy`。其中既有 54 项 Python 检查（46 activation、8 materialization）是已有开发检查集合；其内部合成输入和故障注入是检查本次共享行为的既有设施，不是新增业务示例，不逐项建立 54 个验收关口。
- `tests/integration.sh`：真实 Nix/upstream 环境的隔离 apply → repeat apply → remove。它不在 `flake check` 的 checks 集合内，因此与前项分开执行。单元中的假外部程序不充当真实 upstream/Nix 通过证据。
- `nix flake check --no-build --all-systems`：仅检查声明的两平台求值兼容性。

以下清单是本轮验收上限。每项目标指定一个主检查入口；既有集合中的重叠断言不引出额外重复执行义务。不把依赖库自身、其他仓库或所有 Codex 行为纳入验收。不启动 MCP 服务、调用模型或 live API，不使用凭据，不迁移真实 consumer，不改变全局配置或运行垃圾回收。Darwin 仅求值，不把 Linux 结果视为 Darwin 构建或运行通过。

## 2. 必测清单

| 目标 | 输入或场景 | 预期结果 | 检查方式（既有主入口） |
| --- | --- | --- | --- |
| T1 生产者声明、依赖选择和 harness 投影符合 R2 | 两示例同时作为根；已有 `.override` / `callPackage`、禁用投影、同 payload harness 合并和显式依赖求值输入 | 显式 agent 依赖展开且共享包不重复；runtime 不被当成 agent 部署；默认 Codex、空列表禁用、未知 harness 明确拒绝；已选身份或名称冲突不静默接受 | `tests/default.nix` 的 `evaluation` 既有断言；无需新增图遍历或组合测试。 |
| T2 真实 upstream 产物与生产者配置一致 | `example-base` 完整 skill/agent；`example-tools` upstream fetch 与 `--user-agent=agent-env-nix-example` override | 拷贝含隐藏文件及可执行支持脚本，无资源树符号链接；原生 TOML 包含 name/description/developer_instructions；fetch 使用 Nix store 命令及指定参数，Codex 输出不残留 generic type/headers | `tests/default.nix` 的 `upstream-copy` 既有文件、内容、权限、TOML 断言。依赖已有 pinned inputs/flake.lock，不二次验收 upstream。 |
| T3 项目真实安装、重复应用、生成树替换与安全卸载 | 两示例构建环境；`tests/integration.sh` 的隔离项目预置无关设置、注释、MCP 与 sibling skill；apply 后改 owned skill 再 apply，最后 remove | 两包部署；skill/agent 是实际普通文件；fixed MCP 可执行文件存在；重复 apply 替换 owned generated skill 的直接编辑；remove 删除所拥有资源并保留无关设置、注释、MCP、sibling skill；真实 GC root 在 apply 后注册，remove 后 owned root 释放 | 直接运行既有 `tests/integration.sh`，采用其结构化断言、文件检查与 `nix-store --query --roots` 输出；退出 0 且末尾 `INTEGRATION_PASS`。不另做 GC 删除实验或手工重演相同步骤。 |
| T4 选中资源的相等复用、冲突与用户编辑保护符合 R2 | 既有 activation 检查中 equal unowned、unequal project/parent/global definitions、edited owned agent/MCP、未修改的 owned 更新，以及 whole-config snapshot 变化场景 | equal unowned 不转为 owned，移除不删除；选中冲突明确失败且不静默遮蔽；owned agent/MCP 用户编辑保留并报告；未修改对象可更新；无关配置并发变化不被旧快照覆盖；必要 retained roots 保留 | `runtime-unit` 中现有 `test_activate.py` 对这些行为的断言；例如 `test_equal_unowned_resources_remain_unowned_after_apply_remove`、`test_global_conflict_fails_without_masking`、`test_edited_owned_agent_is_preserved_and_root_retained`、`test_edited_owned_mcp_is_preserved`、`test_unrelated_config_edit_between_plan_and_publication_is_preserved`。使用一次既有集合结果，不再以真实集成重做故障组合。 |
| T5 完整资源发布的安全失败行为 | 既有 materialization/activation 检查中的不安全文件路径或链接、无效所选配置、root 注册失败、受中断发布的已记录状态 | 不穿越或跟随不安全目标，不以部分/无效 payload 充当完整资源；root 注册失败不发布；中断后只依据记录的 old/new 状态恢复，冲突编辑保留并报告 | 同一次 `runtime-unit` 的既有断言（`test_materialize.py` 与 `test_activate.py`）；不新增故障类型、组合穷举、重放或来源认证。 |
| T6 声明平台的求值兼容边界准确 | 现有 locked flake 的 `x86_64-linux` 与 `aarch64-darwin` 输出 | 两平台输出可求值；报告只对 Linux 给出实际构建/运行结论，Darwin 仅 eval | 一次 `nix flake check --no-build --all-systems` 的退出结果及平台输出；不安排 Darwin 构建、设备运行或 Codex 会话。 |

上述预期源于 R2 的完整复制、递归依赖、Codex 投影、配置保护与 GC-root 生命周期要求；现有检查只用于落实检查方式，不把当前程序输出反推为预期。

## 3. 按已完成测试整理，不新增或重跑

用户已明确确认：“你就照着你已经做完的测试写就行，反正那个就算是测够了”。因此本轮只整理已完成测试、完成前两关审核，不新增测试或重跑。下文复现步骤是对既有检查的可执行说明，不是新的执行义务。

[既有开发验证](../docs/validation.md) 报告了 Linux flake check（含 54 Python checks）、两例构建、真实 apply/repeat/remove 与 roots，以及 Linux/Darwin 全系统求值。它们是可提交给第三关的已有结果候选，不追认历史正式 Gate，也不要求为了本文件或提交编号改变而重跑。

由结果审核负责人按实际产品、测试与 locked inputs 是否有影响相关目标的变化，直接采用仍适用的已有结果，记录“复用”及来源。无需重新生成 manifest、证明执行身份或逐项认证历史。记录缺失先向持有者索取现成记录，未取得前标待补；不推定失败，也不批准缺失结果。若后续出现具体适用性变化或记录缺失，先报告该问题；本轮不因此自动启动测试。后续获授权确需复现时才使用下述步骤。已有 54 项不另以 `nix develop ... unittest` 重跑；真实 integration 结果不能由单元假程序代替。

当前计划编写没有运行测试，没有给 T1–T6 赋予正式通过结果。第三关须单独判断当前结果适用性、未完成项和已知问题。仅补本计划及审核记录的文档提交不改变产品行为。

## 4. 既有命令与复现说明（本轮不执行）

开发阶段已记录的入口为 `nix flake check`、`nix flake check --no-build --all-systems`、`nix build .#example` 和 `bash tests/integration.sh "$out"`；云环境用已认可 namespace wrapper 与显式 `path:/workspace/shared/agent-env-nix` 引用。另有一次本地 54 项 Python 结果作为已有记录保留，不要求复现该重复入口。开发环境 Nix 2.35.3，Linux；本地 Python 3.12/TOMLKit 0.13.3，pinned Nix runtime Python 3.14.7/TOMLKit 0.15.0。现有产物为 `/nix/store/yc65qkm7xka0b1vqbg0i46jifb1j4i4z-agent-environment`。这些是已执行情况，不把下面带输出保存的便携命令冒称历史原始命令。

### 4.1 前提与准备

- 使用已准备的目标 checkout/源文件目录，进入仓库根目录。产品基准如文件首段，测试入口均为该版本已有文件；若后来仅增加本计划，复用原产品结果。记录实际产品版本和计划版本，不要求重新安装或重建缓存。
- Linux x86_64 主机已有可用 Nix（nix-command、flakes 启用），store/daemon 与间接 GC root 可用；保留原 locked dependencies，必要下载需现有网络权限。不得运行 `nix flake lock`、更新输入或修改 lock 为了通过。
- Bash 与常规 POSIX 工具可用。integration 使用 `nix develop` 提供 pinned Python 及 TOMLKit，因此不依赖用户另外安装 Python 库。已有环境/预检有效时直接复用，不重复安装 Nix。
- 所有新临时产物、实际配置和输出放独立 `/tmp` 目录。integration 自己创建 project、HOME、CODEX_HOME，与真实用户目录隔离；不手工填入生产配置、凭据或补造 skill/agent/MCP。已有系统配置若导致选中项冲突，不修改系统文件绕过它，按受影响项报告。
- 以下命令只适用于正常可用 Nix 环境。若复用已有云环境的已认可 namespace wrapper，继续使用原 wrapper/安装记录，只替换同等 Nix 命令入口，不改产品或增加新基础设施。没有可用 Nix 时标“无法判断”，不擅自安装或改安全设置。

在 Bash 中，从目标仓库根目录进行一次准备（路径以当前目录取得，无需猜测配置）：

```bash
set -euo pipefail
repo="$PWD"
run=$(mktemp -d /tmp/agent-env-pr1.XXXXXX)
export TMPDIR="$run"
printf 'repo=%s\noutput=%s\nplan=TP1.1\n' "$repo" "$run"
```

沿用 `run` 作为本次输出位置。已安装工具版本可引用原记录；首次执行记录 `nix --version` 即可，不要求全环境快照。

### 4.2 T1、T2、T4、T5：一次既有 check 集合

仅在该集合结果需补齐时执行：

```bash
nix flake check --no-update-lock-file -L "path:$repo" \
  2>&1 | tee "$run/flake-check.log"
```

预期退出 0，`evaluation`、`runtime-unit`、`upstream-copy` 通过。Nix 已有效缓存的检查可直接复用，不使用 `--rebuild` 强制重做。集合中的正常路径重叠不要求额外运行。若失败，保留具体既有断言失败/构建错误；按其实际影响报告目标，不能只因集合一个环境故障把所有目标写为业务失败。

### 4.3 T3：取得示例环境并执行一次真实生命周期

如现成环境构建产物仍适用，直接复用其 store path 赋给 `out`；否则使用现有 locked flake 构建：

```bash
nix build --no-update-lock-file "path:$repo#example" --no-link --print-out-paths \
  >"$run/build-out.txt" 2>"$run/build.log"
out=$(cat "$run/build-out.txt")
printf '%s\n' "$out"
```

然后仅在真实生命周期结果需要补齐时运行：

```bash
nix develop --no-update-lock-file "path:$repo" \
  --command bash "$repo/tests/integration.sh" "$out" \
  2>&1 | tee "$run/integration.log"
```

这里 `nix develop` 仅提供脚本所需解释器，不再运行 Python 单元检查。脚本通过 `$TMPDIR` 创建独立 consumer 目录并以构建产物的正式 `bin/agent-env` 安装；不手工复制产品至 consumer。采用脚本已有断言及输出观察 T3。fixture 路径由末尾 `INTEGRATION_PASS` 输出；不另建结果转换器。成功 remove 已释放本次 owned root；保留运行目录供必要检查，不运行全局清理。

### 4.4 T6：仅全系统求值

仅在对应求值结果缺失或受影响时执行：

```bash
nix flake check --no-update-lock-file --no-build --all-systems "path:$repo" \
  2>&1 | tee "$run/all-systems-eval.log"
```

退出 0 表示求值通过。不得写为 Darwin build/runtime 通过。

## 5. 失败、重试和交付

- 每次实际尝试保留命令、实际版本、退出结果和必要输出；通过、业务失败、无法判断、未执行分开。退出失败时停止该步骤后续依赖命令，不能让后续清理或网络错误覆盖已确认业务失败。
- 产品断言失败不自动重试。记录具体期望与实际、受影响目标，交产品负责人；不能改输入、预期、产品保护或切换方法求通过。
- 已确认外部下载/daemon 临时故障，只有恢复条件已成立才允许该受影响步骤最多一次重试（含首次最多两次），保持产品、lock、输入和参数不变；两次都保留。持续受阻即停并标无法判断。不因此重复已经有效通过的其他入口。
- integration 失败可能留有已安装资源和 root：保留失败目录及日志，不手动删除 root、state 或修改其资源。先由执行负责人识别停在哪一步；需要重跑时用上述准备重新分配独立 `/tmp` 目录，原目录保留，不重复对不明状态做业务副作用。原 fixture 的清理待问题明确后通过正式 remove 入口处理，清理不是新增验收通过条件。
- 步骤错误、未覆盖观察点或需要改变检查方式时，停止受影响项，修订本文件并仅复核受影响范围；不重开无关已确认关口。范围外问题报告事实与影响，不自动扩大本次测试。
- 简短执行记录即可：当前产品/测试版本、计划版本、T1–T6 结果或待补项、复用来源、必要输出位置、下一负责人。不强制专用账本、统一 JSON 或上传原始材料。第三关由结果审核负责人给出，作者不自批；合并审核仍独立进行。
