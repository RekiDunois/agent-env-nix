# DSH MCP output — execution record

Requirement R1; execution plan P3; current test recipe T4. Repository base
06a6d1fba76665562b3560cd9976a4767b92aeed, plugin source
4c7996f3306f198179fe500b8d607716ac1d0da8. Local candidate changes accompany this
record. The 2026-10-24 cloud section recorded no Nix or DSH runtime success; the
2026-10-25 local Darwin section below executed the T5 delivery recipe with Nix
2.34.8 and passed. Full DSH harness/tool operation is still not claimed.
Independent Gate3/merge conclusion is separate from this author record.

## Plan review
Independent reviewer reviewed P2 (SHA256
64e55aa6a2ba32b55030ae56437a366bf5e333230d05a1c0dfbb6c1f0fff8bfe): P1–P4 PASS,
Plan conclusion APPROVED. T2 (SHA256
efe2eca41de17fc27faaeef2b4bf10fff3f533245f48af4c0d0f641522f87ec3): Gate1/Gate2 PASS.
These verdicts were supplied by the independent reviewer, not the plan author.
T3 changed only the then-unexecuted T5 recipe as explained in its amendment.
The independent reviewer approved its affected Gate2 correction at SHA256
84c4f8eb08fbe29d7f92465457845321a87833615967a46034e18e0320b2c273.

## Actual host execution, 2026-10-24
Interpreter: existing isolated Python 3.12.14 with tomlkit 0.13.3. No dependency
installation. All projects, HOME and dummy credentials were temporary; no real
MCP service, plugin, browser, model or user configuration was used.
Raw logs: /tmp/agent-env-dsh-test.hKrOpg (ephemeral cloud execution evidence).
Commands were run from the candidate repository using
/workspace/shared/agent-env-nix-venv/bin/python:

- `-m unittest discover -s tests -p test_dsh_mcp.py -v`: attempt 1, exit 0,
  5 tests, framework result OK. Covers normal combined output/default opt-out,
  mapping/explicit limits, unmanaged/equal/conflicting/edited configuration,
  fallback guard, update/disable/remove, interrupted publication retry and cache.
- `-m unittest discover -s tests -p test_activate.py -v`: attempt 1, exit 0,
  30 existing affected config tests, framework result OK.
- `-m unittest discover -s tests -p test_cached_activation.py -v`: attempt 1,
  exit 0, 8 existing affected cache tests, framework result OK.
- Static review then narrowed the fallback guard to new preferred-file creation:
  do not parse an ignored fallback or block removal when not generating output.
  `-m unittest discover -s tests -p test_dsh_mcp.py -k owned_edit_and_fallback -v`:
  attempt 2, exit 0, 1 affected test, framework result OK. The other earlier
  results remain applicable; no test input/assertion was weakened.

- Independent static review identified that an explicitly empty Codex enabled_tools
  allowlist must not turn into unrestricted DSH tools. The predicate, canonical
  plan and existing mapping test inputs were corrected.
  `-m unittest discover -s tests -p test_dsh_mcp.py -k mapping_and_unrepresentable -v`:
  attempt 2, exit 0, 1 affected test, framework result OK. Log:
  dsh-mapping-attempt2.log. This fixes a found defect within the existing no-broadening
  requirement; previous results were not used to claim this missing case passed.

## Local Darwin execution, 2026-10-25

Candidate revision 9b2018da8a40615e5fa1619d5a3d3c68536080c1 (branch
`feat/dsh-mcp-config-output`); host Apple Silicon `Darwin arm64`, Nix 2.34.8.
The formal T5 recipe from test plan T4 ran on this host because Nix is available
locally. All projects, HOME, CODEX_HOME and dummy credentials were temporary; no
real MCP service, plugin, model or user configuration was used.

Environment: the repository's own devShell (`nix develop`) provides the
Python 3.14.7 and tomlkit 0.15.0 used below. This differs from the cloud record's
isolated Python 3.12.14/tomlkit 0.13.3. The local `uv` interpreter reported
Python 3.12.13 with tomlkit 0.13.3, and that combination was also run for the
T1–T4 file and the affected config file with the same results; the two hosts
therefore used slightly different patch versions, both satisfying the plan's
tomlkit requirement. The affected cache file needs the devShell's GNU coreutils,
so it was run only there.
Raw logs, delivery outputs and build links were kept outside the repository in a
temporary run directory; they are not committed.

- T1–T4 `-m unittest discover -s tests -p test_dsh_mcp.py -v`: attempt 1, exit 0,
  5 tests, framework result OK.
- Affected config `-m unittest discover -s tests -p test_activate.py -v`: exit 0,
  30 tests, framework result OK.
- Affected cache `-m unittest discover -s tests -p test_cached_activation.py -v`:
  exit 0, 8 tests, framework result OK.
- T5 delivery, exactly the T4 recipe: `nix build .#example-dsh --out-link
  "$run/dsh"` and `nix build .#example --out-link "$run/codex"` both exit 0;
  `nix develop --command bash tests/dsh-integration.sh "$run/dsh" "$run/codex"`
  exit 0 and printed the script's verification line. It observed DSH and Codex
  carrying the same literal `http://127.0.0.1:18080/mcp`, DSH `type: "http"`,
  unchanged fetch command, `cwd` equal to the project root, absent
  `.dsh/mcp.json` for default opt-out, `dshMcp: true` in the built manifest, and
  owned cleanup on remove. Built environments:
  `/nix/store/rp9gvm8hq33bbd3xh46nzvsb810yp8k6-agent-environment-dsh-example` and
  `/nix/store/ic08qr4lj74xxqvxgyg5j4zkcdq3i7fl-agent-environment`.
- `nix flake check`: all checks passed; `evaluation`, `runtime-unit` (57 tests),
  `cached-activation` and `upstream-copy` each exit 0 on this revision.

### Real DSH harness check with a public MCP server

Beyond the output-only scope, one real harness run was made on the same host to
close the earlier "plugin runtime compatibility not verified" gap. It used the
public, unauthenticated, read-only documentation server
`https://developers.openai.com/mcp` (`openai-docs-mcp` 1.0.0), which exposes
`search_openai_docs`, `list_openai_docs`, `fetch_openai_doc`,
`list_api_endpoints` and `get_openapi_spec`. A disposable project contained only
the generated `.dsh/mcp.json` pointing at that URL, and the pinned plugin
`dsh-workspace-mcp` 0.2.1 was installed into a temporary DSH profile; no user
profile, existing project or stored credential value was read, copied or changed.

- Protocol reachability: `initialize` returned HTTP 200 with
  `text/event-stream` and `serverInfo` `openai-docs-mcp` 1.0.0, with the `tools`
  capability.
- Plugin mount through its own `mount.js` and the real `dsh-mcp-client`: the log
  line `starting "openai-docs": streamable-http` was followed by
  `mounted 1 server(s) ... openai-docs`, with no failed server.
- Real MCP client call to `list_api_endpoints`: `isError` was false and the
  result carried real endpoint data.
- Real headless DSH session: the model called
  `mcp__openai-docs__list_api_endpoints` with empty arguments; the tool result
  completed and returned the endpoint listing, and the final message reported
  237 endpoints with the base URL `https://api.openai.com/v1`.

This establishes the chain generated `.dsh/mcp.json` -> plugin mount -> real
remote MCP server -> model-invoked tool with real data for one HTTP server. It
does not establish stdio servers, environment-reference expansion at runtime,
subagent mounting, gateway operation, business MCP services or x86_64-linux.

The local stdio fixture `mcp-server-fetch` was also mounted and its tool was
invoked by the model, but the call failed inside that server while spawning a
helper script with an incompatible host Node runtime. That failure is in the
third-party server's own dependency, not in the generated configuration or the
mount path, and is recorded here rather than counted as a product failure.

### Test wiring correction found on this host

The first local run failed before any product assertion in three places, all
from the test harness rather than the product: (1) `tempfile` returns a
`/var/folders/...` path while macOS `/var` is a symlink to `/private/var`, so the
tests' expected paths differed from the runtime's resolved project path;
(2) `tests/test_cached_activation.py` needs GNU coreutils because the generated
wrapper publishes with `mv -T`, and macOS `/bin/mv` is BSD. The temporary-root
mismatch was corrected by resolving the temporary directory in the three
affected test modules (inputs, assertions and expected values unchanged). The
GNU coreutils requirement is documented in README and satisfied by running the
formal commands inside `nix develop`, as the README already instructs; the test
itself was not weakened or skipped.

Original failure output was observed in the terminal before the path correction
and was not written to a file, so that attempt cannot be re-inspected; only the
observation is recorded. The retained `final-cached.log` is the reproducible
bare-host failure from BSD `mv`, and the retained post-fix logs are
`t1-t4-dsh-devshell.log`, `affected-activate-devshell.log` and
`affected-cached-devshell.log`. No product code was changed for these harness
issues.

## Unexecuted
The earlier cloud record below remains historical. On this local host the T5
delivery recipe is now executed and passed; full DSH harness/tool calls, plugin
installation, gateway startup, business MCP calls and x86_64-linux remain outside
this output-only test scope and are not claimed as verified.

The initial T2 Nix-check recipe was corrected before any run: activation must
run after build, outside the build sandbox, and the fetch fixture must use
example.overridden rather than example.base. No failed Nix attempt is omitted.
The cloud record follows; it predates the local execution above.

## Final independent review, 2026-10-24

The independent reviewer supplied these conclusions after inspecting the actual
code and recorded output, without rerunning tests:

- P3 execution plan approved; P1–P4 PASS. Exact plan SHA256:
  5f2d3968307b4309d6bbc0f075f8028ef5278b0d4e95bcb641aef6a4b81cee82.
  That hash is the reviewed P3 text at commit 9428b1c. A later documentation
  commit (1f5de05) reworded the requirement/scope and implementation item 3 to
  state that skills and agents keep the existing paths and that the DSH MCP
  output does not inherit Codex TOML MCP configuration. No owner, mechanism,
  change point or compatibility decision changed; the current file hash is
  c16ba77a2c5c8be1fdbb4f3e72ace3f8ef114666f5633d6d114f72585f80c8a3.
- T4 Gate1/Gate2 PASS. Exact test plan SHA256:
  38363ae7c982c3af9a66c48b2c28a72e615c5922ab912e00b4644f0593007a04.
  That hash is the reviewed T4 text. The 2026-10-25 wiring and environment notes
  appended to the file only record the temporary-root resolution and the T5 host;
  the must-test list, recipes and acceptance conditions are unchanged. The
  current test plan hash is
  76c885d9fbfb552b5bf66670cf147a6240e4146c38d6062ee7e6f39564baa0e5.
- Static implementation and external fixture review: no remaining blocker.
- Gate3 limited result: host T1–T4 PASS, reusing unaffected original results plus
  the scoped fallback and mapping reruns. T5 installed Nix delivery and built
  shell orchestration NOT RUN. Overall acceptance/merge readiness NOT ESTABLISHED.
  Submit as a draft PR with these limits visible.

The empty-allowlist finding was checked against Codex's actual tool filtering
implementation, which retains an explicitly empty allowed set and rejects every
tool: https://github.com/openai/codex/blob/main/codex-rs/codex-mcp/src/tools.rs#L63-L95.

## Status after the local run

The 2026-10-24 reviewer conclusions above refer to the cloud execution, where T5
was NOT RUN. The 2026-10-25 local Darwin execution recorded in this file now
covers T5 delivery and the Nix checks; that earlier NOT RUN statement is history,
not the current status of this revision. Gate3 on the local results and the merge
conclusion remain with the independent reviewer, not this author record.
