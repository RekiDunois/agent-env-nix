# DSH MCP output — execution record

Requirement R1; execution plan P3; current test recipe T4. Repository base
06a6d1fba76665562b3560cd9976a4767b92aeed, plugin source
4c7996f3306f198179fe500b8d607716ac1d0da8. Local candidate changes accompany this
record; final commit is assigned at publication. No Nix or DSH runtime success is
claimed. Independent Gate3/merge conclusion is separate from this author record.

## Plan review
Independent reviewer reviewed P2 (SHA256
64e55aa6a2ba32b55030ae56437a366bf5e333230d05a1c0dfbb6c1f0fff8bfe): P1–P4 PASS,
Plan conclusion APPROVED. T2 (SHA256
efe2eca41de17fc27faaeef2b4bf10fff3f533245f48af4c0d0f641522f87ec3): Gate1/Gate2 PASS.
These verdicts were supplied by the independent reviewer, not the plan author.
T3 changes only the still-unexecuted T5 recipe as explained in its amendment.
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

## Unexecuted
T5 Nix delivery: NOT RUN. No Nix executable is installed in this cloud runtime.
Existing built-script shell orchestration tests: NOT RUN because their
AGENT_ENV_ACTIVATION_SCRIPT prerequisite is unavailable. Host Python tests do
not establish successful Nix evaluation/build or installed activation.

The initial T2 Nix-check recipe was corrected before any run: activation must
run after build, outside the build sandbox, and the fetch fixture must use
example.overridden rather than example.base. No failed Nix attempt is omitted;
none was executed. Full DSH harness/tool calls and Darwin are outside this
output-only test scope, not claimed as verified.

## Final independent review, 2026-10-24

The independent reviewer supplied these conclusions after inspecting the actual
code and recorded output, without rerunning tests:

- P3 execution plan approved; P1–P4 PASS. Exact plan SHA256:
  5f2d3968307b4309d6bbc0f075f8028ef5278b0d4e95bcb641aef6a4b81cee82.
- T4 Gate1/Gate2 PASS. Exact test plan SHA256:
  38363ae7c982c3af9a66c48b2c28a72e615c5922ab912e00b4644f0593007a04.
- Static implementation and external fixture review: no remaining blocker.
- Gate3 limited result: host T1–T4 PASS, reusing unaffected original results plus
  the scoped fallback and mapping reruns. T5 installed Nix delivery and built
  shell orchestration NOT RUN. Overall acceptance/merge readiness NOT ESTABLISHED.
  Submit as a draft PR with these limits visible.

The empty-allowlist finding was checked against Codex's actual tool filtering
implementation, which retains an explicitly empty allowed set and rejects every
tool: https://github.com/openai/codex/blob/main/codex-rs/codex-mcp/src/tools.rs#L63-L95.
