# 共享安装的 Codex MCP 冒烟测试

R7（2026-10-16），候选待复核。第一关范围复用 R5；非临时会话、审批配置及其直接影响的第二关步骤仍待复核；第三关已执行并通过。

## 目标、范围和依据

唯一必测项：通过共享库正式安装现有两示例后，真实 Codex 从消费者项目配置启动 fetch MCP，并完成一次最小只读工具调用。复用 `example-base`、`example-tools` 和现有 fixture 解析器；不修改产品、不测试下游业务、不增加平台或 transport 矩阵。

- 产品基线为已合并 PR #1 的 `3b08c9e652dd8df5f3c1686347ef671476022335`。本 PR 只改配方，文档提交变化不要求重建产品或重跑已有 54 项 Linux 检查及两示例验证，结果继续引用 [validation](../docs/validation.md)。
- 遵守 [Test Engineer Rule](https://app.notion.com/p/3d80101a85f380d8a8f5ce528141e253) 与 [Project Consensus](https://app.notion.com/p/3d60101a85f3815a8c43f271f2b4d91d)。
- 采用 [fixtures PR43](https://github.com/RekiDunois/skills-test-fixtures/pull/43) 的 `ada38c523e1be64e193fef3669dc4af351a3a68e` 版本：[接线 §7、§7.2](https://github.com/RekiDunois/skills-test-fixtures/blob/ada38c523e1be64e193fef3669dc4af351a3a68e/docs/codex-opencode-smoke-wiring.md)。使用 producer 启动配方；按用户本轮要求去掉 `--ephemeral`，并使用同版本的 [审批配置模板](https://github.com/RekiDunois/skills-test-fixtures/blob/ada38c523e1be64e193fef3669dc4af351a3a68e/configs/codex-approval-consumer.toml)。仅复用模板的运行配置，不引入 approval fixture 的冻结 writer、manifest 或审批探针。

输入为一个仓库及 worktree 外的干净消费者。通过条件是安装生成 fetch 配置，随后既有 adapter 确认同一线程的 fetch 最终 startup 为 ready，且 fetch=fetch 调用 completed、error=null，实际返回非错误结果。仅 HTTP 200、模型自述、配置文件存在或 fixture readiness 不算通过。

最小请求目标为公开静态文档 `https://www.rfc-editor.org/rfc/rfc2606.txt`，`max_length=200`；只用它证明工具可用，不要求正文内容、解析质量或固定输出格式。网络/模型故障据实记为无法判断，不增加网页业务回归。

## 准备（本地测试工程师执行）

在已有 `direnv` 工作区的同一个 shell 顺序运行以下代码；用户已负责准备既有 eval，本配方不配置、检查或重启服务。端口按共识从 `direnv exec .` 获取，不要求填写 eval 目录。

所需现有工具为 Nix、direnv、gh、jq、yq（支持 TOML）、curl 和 Python 3.11+。直接执行正常命令，缺依赖或访问失败时保留实际错误并停止受影响项；不新增权限、来源或环境认证。

macOS 的 `/tmp` 会解析到 `/private/tmp`。临时根目录使用物理路径；若 shell 已有 `CODEX_HOME`，仅在本地 `agent-env apply` 子进程中将同一目录转成物理路径，避免安装器把 `/tmp` 软链接判为不安全。不要改指其他目录；这不改变 eval 服务或请求环境。

优先复用本地工程师已有的该 fixture revision 资产：若已有 checkout/资产目录，工程师可将 `FIXTURES` 指向它并引用已有准备记录，不让用户另行寻找路径。未指定时，下面代码自动把所需三个文件放入固定版本的共享缓存；只下载缺失文件。缓存是不可变资产，本轮配置、消费者和输出均放在独占 `/tmp` 目录，使用 `config/`、`consumers/`、`output/` 布局。fetch 不依赖 Zotero/Chrome，因此不执行它们的共享资产准备或启动脚本。

```bash
set -euo pipefail
EVAL_PORT=$(direnv exec . sh -c 'printf "%s" "$EVAL_PORT"')
test -n "$EVAL_PORT"
PRODUCT_SHA=3b08c9e652dd8df5f3c1686347ef671476022335
FIXTURE_SHA=ada38c523e1be64e193fef3669dc4af351a3a68e
RUN_ROOT=$(mktemp -d /tmp/agent-env-mcp.XXXXXXXX)
RUN_ROOT=$(cd -P "$RUN_ROOT" && pwd -P)
CONSUMER="$RUN_ROOT/consumers/example"
mkdir -p "$RUN_ROOT/config" "$RUN_ROOT/output" "$CONSUMER/.codex"
if [ -z "${FIXTURES:-}" ]; then
  FIXTURES="${XDG_CACHE_HOME:-$HOME/.cache}/agent-env-nix/skills-test-fixtures/$FIXTURE_SHA"
  mkdir -p "$FIXTURES/configs" "$FIXTURES/scripts"
  for file in configs/codex-approval-consumer.toml \
    configs/codex-eval-adapter-contract.json \
    scripts/parse_codex_eval_evidence.py; do
    if [ ! -f "$FIXTURES/$file" ]; then
      gh api -H 'Accept: application/vnd.github.raw+json' \
        "repos/RekiDunois/skills-test-fixtures/contents/$file?ref=$FIXTURE_SHA" \
        > "$RUN_ROOT/config/fixture-download"
      mv "$RUN_ROOT/config/fixture-download" "$FIXTURES/$file"
    fi
  done
fi
EXAMPLE_OUT=$(nix build "github:RekiDunois/agent-env-nix/$PRODUCT_SHA#example" \
  --no-link --print-out-paths 2> "$RUN_ROOT/output/build.stderr")
cp "$FIXTURES/configs/codex-approval-consumer.toml" "$CONSUMER/.codex/config.toml"
(
  if [ -n "${CODEX_HOME:-}" ]; then
    CODEX_HOME=$(cd -P "$CODEX_HOME" && pwd -P)
    export CODEX_HOME
  fi
  "$EXAMPLE_OUT/bin/agent-env" apply --project "$CONSUMER"
) > "$RUN_ROOT/output/apply.stdout" 2> "$RUN_ROOT/output/apply.stderr"
yq -p=toml -o=json '.mcp_servers.fetch' "$CONSUMER/.codex/config.toml" \
  > "$RUN_ROOT/output/installed-fetch.json"
printf 'product=%s\nfixtures=%s\nfixture_path=%s\nexample=%s\nconsumer=%s\n' \
  "$PRODUCT_SHA" "$FIXTURE_SHA" "$FIXTURES" "$EXAMPLE_OUT" "$CONSUMER" \
  > "$RUN_ROOT/output/inputs.txt"
```

从安装输出确认 apply 成功，并查看 `installed-fetch.json` 中正式生成的 Nix store `command` 和示例参数 `--user-agent=agent-env-nix-example`。先复制 fixture 的模型与审批配置再 apply，不能用通用模板覆盖生成的 MCP。gpt-6-luna/low 是运行输入，不是本产品验收门槛。审批配置来自该固定模板：`approval_policy = "on-request"` 允许 runtime 按需请求审批，`approvals_reviewer = "auto_review"` 指定自动审核者；这不等于审批必然通过，不改变 `workspace-write` 边界，也不保证网络或 MCP 可达。

用户确认本轮“提权”指需要时交给自动审批器审批。由 runtime 按受支持的流程发起必要的权限请求，交 `auto_review` 审核；不扩大整个会话的 sandbox，不额外开放网络，不向原生 fetch MCP 参数添加 shell/exec 的 `sandbox_permissions`，也不增加 shell 探针或审批验证用例。实际拒绝或权限不可用时保留错误并停止受影响项，不替审批器作决定。

以上是首次准备；Nix 自动复用有效输出。后续仅修订配方或记录时，保留仍有效的资产、构建及消费者，引用原准备记录，不从头安装。若实际安装错误，修产品或正式安装入口，不手工补 MCP entry。不要使用离线 `tests/integration.sh` 的假模型、假 MCP、HOME/CODEX_HOME 设置。

## 一次真实请求

沿用 §7 的显式 sandbox/cd 和逐参数编码。模型、推理、审批、MCP及环境设置来自项目配置；不查 eval 全局配置/trust 表、不手工修改 trust，也不直接执行 Codex。本轮不传 `--ephemeral`，使用默认持久会话；runtime 仍可能持久化此测试消费者的 trust。实际 untrusted、managed-policy 或加载错误据实处理，不绕过。

```bash
PROMPT='Use the configured fetch MCP server to call its fetch tool once with url https://www.rfc-editor.org/rfc/rfc2606.txt and max_length 200. Do not use shell commands, browse with another tool, read project files, edit files, delegate, or call any other MCP tool. If the MCP call is unavailable or fails, report that and stop without retrying.'
set -- --json --skip-git-repo-check \
  --sandbox workspace-write --cd "$CONSUMER" -- "$PROMPT"
COMMAND=$(jq -rRn --args '$ARGS.positional | map(@sh) | join(" ")' -- "$@")
jq -n --arg command "$COMMAND" '{command:$command,timeout:300}' \
  > "$RUN_ROOT/config/request.json"
set +e
curl --silent --show-error --max-time 330 \
  --header 'Content-Type: application/json' \
  --data-binary "@$RUN_ROOT/config/request.json" \
  --output "$RUN_ROOT/output/response.json" --write-out '%{http_code}' \
  "http://127.0.0.1:$EVAL_PORT/eval" > "$RUN_ROOT/output/http.txt" \
  2> "$RUN_ROOT/output/curl.stderr"
CURL_EXIT=$?
set -e
printf '%s\n' "$CURL_EXIT" > "$RUN_ROOT/output/curl.exit"
```

传输成功且 HTTP 为 200 后，直接消费已有 adapter，不重写字段解析或构建另一套判定器：

```bash
test "$CURL_EXIT" -eq 0
test "$(cat "$RUN_ROOT/output/http.txt")" = 200
python3 "$FIXTURES/scripts/parse_codex_eval_evidence.py" \
  --contract "$FIXTURES/configs/codex-eval-adapter-contract.json" \
  --eval-response "$RUN_ROOT/output/response.json" \
  --expected-mcp-server fetch --expected-mcp-tool fetch=fetch \
  --output "$RUN_ROOT/output/mcp-evidence.json"
jq '{fixture_status, mcp_observation, problems}' "$RUN_ROOT/output/mcp-evidence.json"
jq '{version, termination_reason: .output.termination_reason}' \
  "$RUN_ROOT/output/response.json"
```

采用 adapter 的同线程 `success_thread_ids`/`threads` 结果，查看对应调用的 URL 和非错误结果。不能把其他线程或 app-scoped 的 ready 拼成通过。沿用 §7.2 的计数语义，不另设恰好一次的验收门；不再次发送 eval 寻找成功。

## 结果和结束

仅记录当前产品/配方/fixture 版本、实际命令、Codex 响应版本、必要输出和通过／业务失败／无法判断／未执行。旧检查直接引用；私有路径、实际配置和原始响应留在本轮目录，不提交 Git。

R7 本轮结果：**通过**。产品 SHA 为 `3b08c9e652dd8df5f3c1686347ef671476022335`，fixture SHA 为 `ada38c523e1be64e193fef3669dc4af351a3a68e`。Codex 响应版本为 `codex-cli 0.162.0-alpha.17.2`；实际命令与 prompt 使用本节的一次请求配方，未传 `--ephemeral` 或模型 CLI override。curl exit 为 0、HTTP 为 200，响应 termination 为 `completed`。既有 adapter 输出 `fixture_status=FIXTURE_READY`；同一线程 fetch 最终 startup 为 `ready`，`fetch=fetch` 调用 completed 1 次、`error=null`，返回非错误文本内容。macOS 物理路径规范化后，正式安装成功。完整请求、响应及临时配置仅保存在本轮外部临时目录，不提交 Git。

自动重试为零。服务、网络、provider、模型或外部观察故障记为无法判断；已证明的安装生成错误（如错误的 MCP command/entry）记为产品失败，不能用外部环境标签掩盖。原因不明则保留错误及未决点，不臆断产品回归。步骤确有错误时先修订确认，原尝试保留。

请求已终止后用 `"$EXAMPLE_OUT/bin/agent-env" remove --project "$CONSUMER"` 释放本消费者的安装和 GC root，保留运行记录及共享资产。若传输超时、运行是否终止不明，先报告并保留消费者；不删除仍可能使用的路径、不停止服务、不修改全局 trust、不运行 GC。
