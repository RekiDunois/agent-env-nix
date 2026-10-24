# Activation-time port: normal independent review

历史审核结论：NOT_READY — [agent-env-nix PR #6](https://github.com/RekiDunois/agent-env-nix/pull/6); base `c368871942435bdc178a1063ce9c677acaf8cabc`; reviewed product head `04f22a464e26207746a619312e80f6d6df6fccf9`. Review date: 2026-10-24. 以下原审核正文保留当时的未执行状态；本轮补测见文末执行更新及当前测试计划。产品和测试代码未变，原审核的设计与范围结论继续适用，不以执行者更新代替审核者结论。

## Current authority, revisions and completeness

The user approved activation-time reading of a devShell port variable and publication of a literal URL, without consumer/factory port plumbing, and subsequently requested two separate plans and normal review. This is normal affected-scope review, not a mechanical fast-merge exemption.

Canonical execution plan: [implementation-plan.md](activation-port-env/implementation-plan.md), split-plan v1. Canonical test plan: [test-plan.md](activation-port-env/test-plan.md), split-plan v1. The old combined path is an index only; no competing plan remains. Both complete documents, executable instructions, retained results and handoffs were independently reviewed. The author does not issue the verdicts below.

The implementation owner verified remote head `04f22a4` has tree `9e7ac8d80d4222afdf0df665fea26fd76373f225`; the reviewer independently read the local tree and confirmed the same value. Local commit `093b9e0` is a snapshot carrier, not the remote product SHA. The working changes contain only the split plan/index and this review. Product and test code are unchanged. The earlier complete source review and applicable results are reused, not inferred from a new documentation SHA.

The review applies the Plan Reviewer Rule, Test Engineer Rule and Project Consensus read for this task. It adds no full regression, live model/service, new testing framework or independent evidence-certification requirement. The reviewer has not run tests, changed product code, submitted an external PR review or merged.

## Execution-plan review

Requirement revision: the approved 2026-10-24 activation-time port request, with the later documentation/normal-review instruction. Plan revision: split-plan v1. Target product revision: `04f22a464e26207746a619312e80f6d6df6fccf9`.

Decision grounding at that product revision:

- `lib/package.nix` owns producer normalization and separate `mcpPortEnv` metadata; `lib/project.nix` collects selected producers into the manifest without mixing metadata into native MCP settings. This is the appropriate owner, rather than consumer or fixture compensation.
- `runtime/config.py` resolves desired values before the existing ownership/conflict checks and commits prepared bytes. This supports literal URL publication and preserves user-edit protection, unequal-source conflict rejection, equal-unowned reuse, snapshot checks and removal behavior.
- `runtime/cached-activate.sh` owns cache comparison. Its fingerprint uses the same resolver as prepare, so an effective port change triggers apply and invalid values cannot silently hit an old success marker. Existing locks, failure invalidation and success publication remain.
- Separate metadata is smaller than changing upstream server schema or adding generic templates/layered consumer overrides. The latter also contradict the approved direction. Only mapped URLs receive the new validation; unmapped values retain their contract.

Relevant unchanged pins in `flake.nix`: nixpkgs `6510408d147d8c5e6d76043e899e9251756f6a75`, agent-skills-nix `2948865044b2af55c8c4e4eb2abda7de79d60f0e`, mcp-servers-nix `31848978eefbca17f1658a55066b1d2aaa43cafc`. The existing host Python uses TOMLKit 0.13.3. No new upstream behavior is assumed by this documentation split.

P1 Requirement & Reality Grounding: PASS.
P2 Solution Validity & Ownership: PASS.
P3 Impact, Safety & Counterexample: PASS.
P4 Executability: PASS.
Gate review completeness: COMPLETE.
Critical assumptions: none for the implementation design.
Unresolved critical design impacts: none.
Required plan modifications: none.
Plan conclusion: APPROVED.

These P1–P4 conclusions reuse the prior approved combined plan because owner, core mechanism, compatibility, lifecycle and failure strategy did not change. This review also checked the full split candidate for omissions or contradictory inherited instructions. The later cloud-installation permission is correctly distinguished from the reported execution-environment failure before installation starts; this review neither revokes permission nor authorizes bypassing that failure. A missing execution result remains a testing gap, not a design assumption presented as proven.

The user's literal-URL behavior and existing configuration protections are the contract. Metadata layout, helper names and fingerprint implementation remain implementation choices; plan approval does not promote them into independent product requirements or prove the implementation works.

## Test-plan and result review

Test design: APPROVED for the unchanged bounded scope. First gate: PASS for the stated required scope, including the already-identified Nix connection evidence. No required goal was removed during the split and no new scenario or framework was added.

Second gate: PASS for the complete split-plan v1 recipe. The existing host commands and results remain reusable. The added concrete Nix recipe fixes product SHA `04f22a4`, clones the verified PR branch into an independent temporary source, runs the existing declaration evaluation target, and constructs one HTTP producer/environment/cached activator through the public Nix constructors. Its separate project, HOME and CODEX_HOME, two inherited port values, structured TOML assertions, saved logs, stop conditions and bounded external-failure retry are specified. The Nix expression was checked against the actual flake/lib entrypoints; no product runtime or manifest is supplied by a stub. This completes steps for the previously identified goal without expanding its scope. Recipe approval is conditional on an operational authorized environment and does not claim a successful Nix execution. Host checks are not rerun merely because this recipe was documented.

Third gate: PASS only for the executed host scope: ConfigEditor 30/30 and cached wrapper 8/8, plus the previously reported shell syntax and diff checks. The final reports were read during the earlier review at `/tmp/agent-env-port-tests.XsTG4Hsd/config-final.log` and `cache-final.log`; initial successful logs remain alongside them. No failed attempt was reported. Product and test code remain unchanged, so these results are reused without rerunning them for a path or documentation SHA change. The recorded diff check is historical evidence for the implementation, not a claim that this newly edited documentation has been tested.

The fixture uses the real resolver and prepared commit but supplies its manifest and installer stub. It is not Nix evaluation/build, actual generated activation, Darwin integration, live MCP or real GC-root evidence. Overall testing is incomplete because the remaining Nix evidence is NOT RUN. This is not an observed product failure.

## Remaining work and merge disposition

1. Nix declaration assertions and actual producer metadata → generated project manifest → packaged cached activator behavior remain NOT RUN. The parent coordinates the execution owner in a working authorized environment or suitable existing CI. That owner can use the now-reviewed concrete recipe in the canonical test plan to exercise the already-defined mapped HTTP case and literal URL update after the environment is operational. If an environment-specific change is necessary, review only its affected preparation/steps before execution. No model/service, broad platform matrix, repeated host suites or new framework is needed merely to close this gap. The reported cloud installation did not begin because its execution environment failed; no successful install or Nix attempt is claimed.
2. The parent must verify the final published documentation head and applicable required checks, approvals and merge constraints. This review does not assert current remote CI or branch-protection status. Unknown/empty checks are not passing evidence.

No confirmed in-scope code blocker was found in the earlier complete diff/call-chain review; this split changes no code. Current `runtime/config.py` SHA-256 remains `9e18d13d690f4a5d01ff7b5bbb383cc1aeaca344ac98d0996314ccfabc5cbb15`. No plan modification remains required. Outstanding completion work is the Nix execution/result and final remote merge-state verification, not redesign of the approved solution.

The plans may be published to the existing draft PR with these explicit limits. NOT_READY is retained; this record neither approves nor authorizes merge.

## 本轮执行更新（2026-10-24）

本地执行工程师已按[完整测试计划](activation-port-env/test-plan.md)补齐原来缺少的 Nix 结果：在 `aarch64-darwin`、Nix 2.34.8 上，固定产品版本 `04f22a4` 的既有声明检查、实际构建及两次真实打包激活均通过，配置中的完整服务器表分别只有端口为 19091 和 19092 的预期地址。产品、测试代码及上游固定版本未改，既有 38 项测试结果复用。

首次求值因沙箱限制无法写入 Nix 缓存数据库，解除该限制后唯一重试通过。首次激活成功后，执行者使用的 `yq` 整表比较命令误判；本地测试工程师将其修订为 `yq` 解析后由 `jq` 精确比较整表，输入及预期不变，专用实现符合性审核确认准备完整后，由本地执行工程师继续执行并通过。原始失败和成功输出均保留在测试计划列明的独立 `/tmp` 目录。

此前“缺少 Nix 执行结果”的事实已被本轮结果取代；上文仍是历史审核记录。本更新只报告实际执行，不签发测试第三关、合并批准或改变 PR 草稿状态。

## 本轮实现符合性审核

专用 `implementation_reviewer` 已完成首次完整审核，结论为**完整**，未发现范围内偏差或待补材料。所审产品及测试版本为 `04f22a464e26207746a619312e80f6d6df6fccf9`，交付工作树基于 `84ba23d481ffd3573d397d53e8b1c71ad47c9398`，包含本轮四份文档修改。

审核覆盖有效计划下的全部产物，包括此前未修改部分：生产者声明及清单传递、配置解析与原有保护、准备后固定提交值、两个激活脚本及缓存打包连接、README、相关测试、两份完整计划、导航及结果记录。审核确认当前产品和测试内容与固定测试源码一致，复用的配置编辑 30/30、缓存包装 8/8 及语法检查有效；新增声明检查、真实构建、19091 到 19092 的打包激活均有通过记录，首次受限及错误比较命令保留。审核期间未运行测试、修改文件或执行 Git 操作。

该结论只确认实现交付完整，不代表测试关口或合并批准。下一步由执行工程师提交、推送并更新 PR；测试结果负责人处理第三关，合并负责人另行审核合并条件。最终追加本段仅记录审核结论，不改变已审实现、步骤和测试结果。
