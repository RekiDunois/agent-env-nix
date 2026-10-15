# PR #1 测试计划独立审核记录

审核日期：2026-10-15。审核对象：`plan/test-plan.md`，TP1.1。

- 候选 SHA256：`3b2abc66f22aca0d63e9a9ff0f9b49adeb28269d257c66a425f7a177443dee27`
- 目标产品：`760c1bf60e8ec19d1985660ec5e3276a8ef80b5a`
- 依据：[R2](../docs/requirements.md)、[实施计划 v0.5](implementation.md)、[Test Engineer Rule](https://app.notion.com/p/3d80101a85f380d8a8f5ce528141e253)、[PROJECT_CONSENSUS](https://app.notion.com/p/3d60101a85f3815a8c43f271f2b4d91d)，以及用户确认“你就照着你已经做完的测试写就行，反正那个就算是测够了”。
- 方式：未参与本测试计划编写的独立 reviewer 只读检查完整候选、R2、flake/check/devShell、`tests/default.nix`、`tests/integration.sh`、既有 activation/materialization 入口和 `docs/validation.md`。未修改产品、执行测试或新增目标。

## 第一关：PASS

T1–T6 整理已有两示例、三个 check、真实集成及两平台求值的既定范围，覆盖显式依赖与投影、完整资源与原生配置、项目应用/移除和 GC roots、配置保护、安全失败及平台声明边界。预期与 R2 一致，没有将当前输出自行升级为要求。54 项既有单元集合不拆成新增验收关口；不增加业务回归、模型/live API、真实消费者迁移或通用证明设施。Linux 实际构建/运行与 Darwin 仅求值边界准确。用户认可的已有测试集合即本轮上限。

## 第二关：PASS

完整候选区分历史命令、已有结果复用和仅供后续获授权复现的便携步骤；本轮明确不新增、不重跑。复现说明固定已有 lock、仓库路径与产物，准备独立 `/tmp` 输出，使用一次 flake check 覆盖既有检查集合；integration 不属于 checks，单独通过已有正式 launcher 执行真实 apply/repeat/remove，nix develop 提供 Python/TOMLKit。all-systems 使用 --no-build，不冒称 Darwin 构建通过。有效产物、缓存和旧结果可复用，不强制重建，不重复本地 Python 集合。失败分类、停止后续依赖步骤、恢复后最多一次外部故障重试、隔离状态保留和正式 remove 清理路径明确，未增加额外测试义务。

## 结论与边界

- Review completeness：COMPLETE
- Required modifications：无
- Missing evidence for Gate1/Gate2：无
- 新增测试或重跑要求：无
- 第三关：未审核。本记录不将 T1–T6 或历史结果追认为正式通过，也不作合并结论。已有结果适用性按计划交结果审核负责人直接采用或注明待补，不能因本次文档提交自动要求重跑。

TP1.1 第一关、第二关通过。仅适用于上述精确候选；纯文档提交号变化不使结论失效，语义变化只复核受影响范围。
