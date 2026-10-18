# 共享缓存激活：执行计划 IP1

- Requirement revision：R1，2026-10-18，用户要求把 professor-contact PR #96 的既有缓存自动激活实现抽到 agent-env-nix，并在此仓库提交 PR；随后明确本任务走常规审核、须有独立执行计划和测试计划。
- Plan revision：IP1-candidate；Proposed review status: pending。
- 目标：RekiDunois/agent-env-nix [PR #4](https://github.com/RekiDunois/agent-env-nix/pull/4)。基线 `2158e933aab6c845ae1ceb1228458d624f8777d5`；当前产品 `c20fd73562e24ef288aa222a9e2e56e961f1894b`。
- 来源：ScholarWorkflow/professor-contact [PR #96](https://github.com/ScholarWorkflow/professor-contact/pull/96)，head `47a7fe0831418178871d29218e2dc26be9c6119a`，其中产品 `4d59c0556de113cee554e8879236c9cc378ec826` 未变。
- 规则：[Plan Reviewer Rule](https://app.notion.com/p/3e80101a85f3817a94cbc6eca1a76a5c)、[Project Consensus](https://app.notion.com/p/3d60101a85f3815a8c43f271f2b4d91d)。测试目标、步骤和结果只由配套[测试计划 TP1](test-plan.md)维护。

本文件是对已提交实现的完整待审方案整理，不倒签实施前批准。此前候选代码只读检查不是 P1–P4 正式结论；作者不自授 APPROVED。本次整理只改文档，不改产品或测试代码，不运行测试。

## 1. 正式需求、边界与非目标

正式目标是共享既有缓存包装能力，让 producer/consumer 调用共享 Nix 工厂，避免每个 producer 复制同一脚本；保留 PR #96 的 CLI 和成功缓存行为。仍由一个组合 environment 安装一个项目。多个 roots 先交给 `mkProject` 组合，再包装一次。

- intended_change：新增 `lib.mkCachedActivation { pkgs; environment; name ? "agent-env-activate"; }` 和通用脚本；允许定制可执行名称；缓存和锁按项目统一，不能按 producer 名各自维护。
- preserved_behavior：`--project DIRECTORY`、默认当前目录、`--force`、`--help`；environment store 输出加项目物理路径的成功缓存；失败失效、原子写成功、fail-fast 锁及 CDPATH 修正。原有 `agent-env apply/remove`、复制与配置保护、依赖 pins 和平台范围不变。
- approved_behavior_change：用户授权把 PR #96 包装能力放到共享库；通用命名和共享项目状态是实现此抽取的设计选择，不将所有内部细节升级为新产品要求。
- prohibited_side_effect：不改 contact/Study；不改共享安装器；不新增文件监测、业务框架、服务启动、全链回归或自动合并；不使用用户 Mac/真实项目，不安装新软件。

## 2. 事实与关键决策

以下源码是描述性依据，正式目标来自上节需求；源码现状不会自行增加验收要求。

1. **独立工厂包装已有 environment，而非改 installer。** 基线 [lib/project.nix](https://github.com/RekiDunois/agent-env-nix/blob/2158e933aab6c845ae1ceb1228458d624f8777d5/lib/project.nix) 的 `mkProject` 生成 `bin/agent-env`；[runtime/activate.sh](https://github.com/RekiDunois/agent-env-nix/blob/2158e933aab6c845ae1ceb1228458d624f8777d5/runtime/activate.sh) 已负责 apply/remove、资源替换和状态，配置保护交给 `runtime/config.py`。故缓存只决定是否调用正式 apply，不复制或改变安装逻辑。
2. **沿用已存在的缓存算法和 CLI。** 来源产品的 [nix/activate.sh](https://github.com/ScholarWorkflow/professor-contact/blob/4d59c0556de113cee554e8879236c9cc378ec826/nix/activate.sh) 和 [nix/activate.nix](https://github.com/ScholarWorkflow/professor-contact/blob/4d59c0556de113cee554e8879236c9cc378ec826/nix/activate.nix) 直接给出物理路径、environment 输出、锁、失效和成功发布过程；抽取仅改变共享模块位置、名称参数和项目状态名称。
3. **所有名称共享一份项目成功记录和锁。** 基线 installer 按项目维护所选资源，后一次 environment apply 替换选择并清理旧选择。若 A、B 包装器各有标记，A → B → A 会误信 A 的旧成功而跳过；共享记录会看到 B 的 environment，重新 apply A。`name` 因此只用于可执行文件及诊断，不参与状态身份。
4. **直接 apply/remove 不改动缓存语义。** 基线 installer 不读写新包装层标记；当前 [runtime/cached-activate.sh](https://github.com/RekiDunois/agent-env-nix/blob/c20fd73562e24ef288aa222a9e2e56e961f1894b/runtime/cached-activate.sh) 只调用 apply。故直接调用或手工删改后必须显式 `--force`，且不得与包装器并发；此次不增加监听或跨入口锁改造。

因果链：producer 专用脚本重复 → 缓存实际只依赖 environment 和项目 → 把脚本与打包工厂放到共享 owner → 调用者传组合 environment 和可选名称 → 复用原能力并避免多 producer 状态造成假命中。

## 3. Ownership 与方案取舍

共享库拥有通用包装器、参数校验、项目缓存/锁和诊断；现有 installer 继续拥有资源、MCP 配置保护、安装状态和 GC roots。Producer 仍拥有 agent 包及其业务依赖；consumer 拥有 roots 选择、项目路径和 devShell/direnv 调用。测试 stub 只观察调用，不代替正式安装能力或补偿其缺陷。

选择独立工厂：调用者可保留专用命令名，原 environment 接口和 direct apply/remove 完全不变。现实替代是给 `mkProject`/`agent-env` 内置缓存或增加新子命令，但会扩大现有命令语义和锁生命周期修改面；本次不选。继续在每个 producer 复制脚本也能运行，但不满足共享抽取目标。

## 4. 冻结的实现与实施顺序

1. 新增 `runtime/cached-activate.sh`，由来源脚本抽取。保留解析、路径规范化、失败处理和成功发布顺序；采用 `.agent-env-applied`、`.agent-env-apply.lock`。
2. 新增 `lib/cached-activation.nix` 并从 `lib/default.nix` 导出工厂。接收 `pkgs` 与有 `bin/agent-env` 的 environment 输出；默认名称 `agent-env-activate`。名称限制为安全可执行 basename，打包固定 Bash/coreutils/environment，避免 PATH 漂移或 shell 注入。输出 `$out/bin/<name>`。
3. 项目状态：marker 内容为 `v1`、environment 输出、物理路径。先取得项目锁再检查缓存；需 apply 时删除旧 marker；仅 apply 成功后，从锁目录同文件系统原子替换 marker。失败退出保留无成功标记状态；正常退出/可捕获信号清理锁。无法捕获的崩溃可能留锁，确认无运行者后人工删除。
4. README 提供组合 roots、工厂和 shellHook 用法，并传播失败退出码；说明 `.gitignore`、direct apply/remove、`--force`、缓存不扫描文件及旧 producer 标记不迁移。
5. 测试代码仅覆盖配套计划所述直接变化；按该计划记录已经执行的检查和未执行边界。实现与测试计划分别交独立审核者；只有有具体影响的修正才触发对应复核，不因文档 SHA 变化重跑。

本轮产品已处于上述实现状态；此次交付只把原合并简稿整理成两个唯一完整计划，旧路径仅保留索引。

## 5. Invariants、风险与代表性反例

- 成功缓存只代表最近一次包装器成功 apply 的 environment/物理项目；A → B → A 必须重新调用，不能使用按名称分割的旧成功记录。
- 失败升级或强制修复不能留下可命中的旧 marker；因此失败后回退也重试。原子性仅覆盖 marker 发布，不宣称整个 installer 事务回滚。
- 包装器同项目互斥包含缓存检查；锁已存在立即失败。direct apply/remove 不在这个包装锁 contract 内，文档明确串行使用和强制修复，不暗示跨入口统一互斥。
- 符号链接项目别名解析为同一物理路径；移动项目改变 key。相对 `--project` 先锚定调用者目录， inherited CDPATH 不能把安装重定向到另一个同名目录。
- symlink/非普通 marker、换行路径和未知参数失败；拒绝而不是猜测或修改目标。路径有空格受支持。
- 手工修改或删除安装文件、直接 remove 后仍可能命中旧 marker；这是已声明缓存边界，使用 `--force` 重跑原有受保护 apply。新包装器忽略旧 `.professor-contact-*` 标记，首次调用正常 apply；无需迁移/删除旧状态，也不在此次修改其他仓库。

上述反例用于静态检查方案，不自动增加测试。Critical assumptions：未识别出核心方案依赖的未验证事实；新 Darwin 构建/真实 direnv 未执行是测试证据边界，不能写成已验证。Unresolved impacts：当前未识别出未说明的语义影响；若后续发现实际 contract 冲突，交需求负责人而非临时改范围。

## 6. 交接

IP1 是唯一完整执行计划；TP1 是唯一完整测试计划。实现方案 P1–P4、测试设计/三个关口和合并审核均待对应 reviewer 给正式记录，不复制先前代码候选检查或 PR #96 的批准。下一步由执行计划审核者与测试计划审核者分别审当前候选；产品 owner 只处理具体范围内问题。此文档修订不授予执行新测试或合并的权限。
