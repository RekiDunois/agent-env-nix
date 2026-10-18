# 共享缓存激活：测试计划 TP1

- Requirement revision：R1，2026-10-18，共享抽取 professor-contact PR #96 的既有缓存自动激活能力；用户要求常规审核与双计划。
- Test plan revision：TP1-candidate；配套[执行计划 IP1](implementation-plan.md)。
- 目标产品和测试实现：agent-env-nix `c20fd73562e24ef288aa222a9e2e56e961f1894b`，基线 `2158e933aab6c845ae1ceb1228458d624f8777d5`。
- Proposed review status: pending。测试设计、第一关必测清单、第二关步骤、第三关结果待正式 reviewer 判定；以下 exit 0 是已有执行事实，不是作者自授关口结论。
- 依据：[Test Engineer Rule](https://app.notion.com/p/3d80101a85f380d8a8f5ce528141e253) 与 [Project Consensus](https://app.notion.com/p/3d60101a85f3815a8c43f271f2b4d91d)。

这是把已提交的简明范围与结果整理为唯一完整测试计划，不倒签事前审批。本轮只修订文档，不执行或重跑任何测试；文档 SHA 变化不使未受影响结果失效。计划不得把现有测试数量反推为需求，也不把旧 PR 的执行义务自动移植为新义务。

## 1. 范围与必测目标

范围依据共享抽取目标和直接改变的成功、失败、兼容行为制定；现有七个测试方法是实现下列目标的手段，数量本身不是验收标准。

### T1：保留缓存入口的成功、失败与路径行为

- 输入/场景：首次与同 key 重入、environment 变化、强制重装；失败升级后回退及失败强制修复；项目符号链接别名/移动；带 CDPATH 的相对路径；不安全 marker、占用锁、缺失/未知参数；help 与换行路径。
- 预期：仅同 environment/物理路径的成功缓存可跳过；升级/force 调用原 apply；失败移除旧成功并可重试；路径指向调用者预期项目；无效状态拒绝且不调用安装器；锁正确清理，help 不安装。
- 检查方式：沿用 `tests/test_cached_activation.py` 的 unittest 断言和 stub 调用记录。它观察包装层，不宣称 stub 等于真实安装。

### T2：共享项目身份不被可执行名称割裂

- 输入/场景：不同命令名对应 A、B 两个 environment，按 A → B → A 调用；同项目锁存在；不同命令名指向同一 environment。
- 预期：A → B → A 三次 apply；共享锁阻止另一名称进入；同 environment 更名仍命中同一缓存；force 再次 apply。
- 检查方式：A/B 切换与共享锁用 T1 同一 unittest 入口中的专用方法；同 environment 的命令更名用 `checks.<system>.cached-activation` 中实际 Nix 打包的 default/custom 入口和调用行数断言。两部分覆盖不同条件，不再另加端到端重复检查。

### T3：公共 Nix 工厂接线及原接口保持

- 输入/场景：`lib.mkCachedActivation` 默认/自定义名称、一个现有 environment；非法名称；原有 project/runtime 与依赖声明。
- 预期：生成固定工具和 environment 的可执行包装器；非法 basename 拒绝；原 `mkProject`、`bin/agent-env apply/remove`、复制与配置保护和 pins 不变。
- 检查方式：已有 `checks.x86_64-linux.cached-activation` 构建并调用实际工厂（安装器是 stub）；`checks.evaluation.drvPath` 的既有断言含非法名称；Darwin 新 check 的 drvPath 求值只核其可求值；不变行为通过当前 diff 和原 owner 文件保持不变确认，复用原结果，不重跑全套 installer 回归。

必测清单不包括：全业务链、模型/MCP 服务、浏览器、Zotero、其他 producer/Study、文件监测、边界穷举、新判定系统或来源认证。现有 Linux 输出只用作离线补充证据，不扩大为 Linux 支持验收。

## 2. 已有执行环境、准备与步骤

下列是现有检查的可执行入口与结果解释，供审核已有结果；本轮不执行。仅后续有明确受影响目标且相应步骤获确认时才运行该目标，不要求把全部命令重跑一遍。

### 环境与隔离

- 已有云端 Linux、Python 3、Bash/GNU coreutils、Nix 2.35.3 与缓存的锁定 inputs；不安装软件、不改 Nix 配置、不用用户 Mac。
- 工作目录为 agent-env-nix 的上述产品/测试内容。原运行目录是 `/workspace/shared/agent-env-cached-activation`；原 Nix 可执行入口 `/workspace/shared/nix-bootstrap/bin/nix`，使用已有隔离 wrapper 与缓存。普通命令中的 `nix` 对应该入口。
- Python 测试自行创建并清理临时项目和 stub；Nix check 使用构建隔离目录。都不接触用户项目或真实服务，不需要账号、模型、浏览器、fixture 服务或新配置。
- 如果今后需要新执行，仅为输出新建仓库外目录 `RUN=$(mktemp -d /tmp/agent-env-cached-check.XXXXXX)`；保留受影响项输出和失败，不采集全环境快照。该未来目录不是本次已有记录的位置。

### 唯一主要运行入口

```sh
nix build --offline --no-write-lock-file --no-link .#checks.x86_64-linux.cached-activation
```

该 check 在固定 Bash/coreutils 下运行 T1/T2 的七个现有方法，再构建并调用两个名称的正式工厂包装器，检查同 environment 缓存、force、marker 和锁清理。成功为命令 exit 0，且 unittest/脚本断言均成立；失败由已有测试报告指出。直接 `python3 tests/test_cached_activation.py -v` 是此前已做的 host 补充检查，不要求在 Nix check 后重复运行。

### 求值与静态检查

```sh
nix eval --offline --no-write-lock-file --raw .#checks.aarch64-darwin.cached-activation.drvPath
nix eval --offline --no-write-lock-file --raw .#checks.x86_64-linux.evaluation.drvPath
```

期望 exit 0 并返回 derivation 路径；第二条强制执行现有 evaluation 断言。它们不构建/运行 Darwin，也不等于真实 installer 或 direnv 集成。原有 shell/Nix parse 与 whitespace 检查仅是实现时已完成的静态辅助，不新增为独立业务验收目标。

### 失败、重试与停止

- 本轮不重试、不执行。后续获准执行时，每个受影响入口只运行一次；当前默认不自动重试外部故障。
- 缺缓存、权限或工具导致无法执行，记录无法判断并停止该项，不安装软件、切换设备、扩大权限或关闭 offline 求通过；若要重试，先确认恢复事实、无重复副作用和同一输入/断言，再由有效步骤补齐最多一次重试及清理方式。
- 断言失败按范围内业务失败或测试接线问题区分，不因结果不满意重新采样；产品交产品负责人，步骤错误交测试计划/执行负责人。修改输入、断言或方法不是同条件重试。
- 不因文档修订、缺少新的 SHA 运行日志或审核偏好要求新执行。已有输出缺失先请求已有记录，不自动判产品失败，也不虚构通过。

## 3. 当前结果与复用

当前结果源自 [c20fd735 原执行记录](https://github.com/RekiDunois/agent-env-nix/blob/c20fd73562e24ef288aa222a9e2e56e961f1894b/plan/cached-activation.md) 及同次运行报告；本次只整理其事实。

- T1：host `python3 tests/test_cached_activation.py -v` 七方法 exit 0；固定工具的 Nix check 内同七方法也成功。沿用后者为主要结果，前者只是已有补充证据，无需重复。
- T2：A → B → A/共享锁断言成功；Nix factory default/custom 共用同 environment 的首次/跳过/force 调用计数分别 1/1/2，marker 存在、锁已清理，check exit 0。
- T3：实际工厂离线 Linux stub 打包/check exit 0；Darwin check drvPath 与 Linux evaluation drvPath 求值 exit 0。原 owner 与 pins 在产品 diff 中未变，未触发原安装器回归执行。
- 静态辅助：`bash -n runtime/cached-activate.sh`、工厂与 `tests/default.nix` 的 Nix parse、`git diff HEAD --check` 均 exit 0。
- 首次 Nix check 因新增测试 fixture 的 Nix 引号错误在构建前退出；修正后原 scoped 命令 exit 0。随后强化 stub 参数检查为显式失败退出，再运行同 scoped check exit 0；没有省略这两次修正的执行背景。
- 最终成功 Nix check 的已有构建日志可通过原环境 `nix log /nix/store/gwf7kwpligyrs1q5avfsy92fspzbhvbj-agent-env-cached-activation-test.drv` 读取。host/求值/静态命令结果在原运行报告中记录，没有另造原始日志文件。

### 未执行与适用边界

新共享导出的 **aarch64-darwin 构建和真实 direnv 激活未执行**。PR #96 原产品 `4d59c05` 的 Darwin build/隔离 direnv 结果是原算法与未改变调用方式的背景，不是当前共享导出的通过结果。本次文档整理不自动安排这两项、扩大必测清单或提供新的执行授权；正式 reviewer 应按上述需求与证据边界判定当前范围，不把求值写成运行通过。

原 shared installer 的记录与测试代码未改；复用依据是本次不改其语义，而非只看旧提交曾通过。没有运行或声称全业务、多仓库或新平台验收通过。当前新 SHA 没有 GitHub workflow/check-run/status 记录；空状态不是 CI 通过或正在运行的证据，也不要求为了补 CI 添加设施。

## 4. 修订影响与交接

TP1 与 IP1 整理旧合并简稿，产品/测试源码和测试预期没有变化。当前变化不使 c20fd735 的范围内结果失效；PR #96 或其他任务的正式关口结论不复制到这里。

下一步：独立测试计划审核者核对本完整候选的目标、范围、步骤与结果适用性，分别记录设计及三个关口实际结论。若目标/检查方式有具体缺口交测试计划 owner；已有执行材料不足先补已有记录；实现偏离交产品 owner。未取得正式结论前保持 pending，不写整体通过/可合并，不自行运行未执行项。
