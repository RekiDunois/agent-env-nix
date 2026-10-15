{ pkgs, agentLib, example }:
let
  lib = pkgs.lib;
  python = pkgs.python3.withPackages (ps: [ ps.tomlkit ]);
  succeeds = value: (builtins.tryEval (builtins.deepSeq value true)).success;
  empty = extra: agentLib.mkAgentPackage ({
    inherit pkgs;
    id = "test-empty";
    version = "1";
    files = { };
  } // extra);
  graphOf = roots: (agentLib.mkProject { inherit pkgs roots; }).graph;
  disabled = example.base.override { enableHarnesses = [ ]; };
  called = pkgs.callPackage
    ({ pkgs, mkAgentPackage, enableHarnesses ? [ "codex" ] }:
      mkAgentPackage {
        inherit pkgs enableHarnesses;
        id = "call-package-example";
        version = "1";
        files = { };
      }) { mkAgentPackage = agentLib.mkAgentPackage; };
  diamond = empty { id = "diamond"; agentDependencies = [ example.base ]; };
  other = empty { id = "other"; agentDependencies = [ example.base ]; };
  cycle = rec {
    first = empty { id = "cycle-first"; agentDependencies = [ second ]; };
    second = empty { id = "cycle-second"; agentDependencies = [ first ]; };
  };
  remote = empty { mcp.settings.servers.remote = {
    type = "http";
    url = "https://example.invalid/mcp";
    args = [ ];
    env = { };
    env_vars = [ ];
    headers = { Accept = "application/json"; };
  }; };
  stdio = empty { mcp.settings.servers.local = {
    command = "${pkgs.hello}/bin/hello";
    headers = { };
    http_headers = { };
    env_http_headers = { };
  }; };
  collision = example.base.override { id = "second-exporter"; };
  evaluation =
    assert example.base.drvPath == disabled.drvPath;
    assert (called.override { enableHarnesses = [ ]; }).agentEnv.enableHarnesses == [ ];
    assert called.drvPath == (called.override { enableHarnesses = [ ]; }).drvPath;
    assert (graphOf [ disabled example.base ]).example-base.enableHarnesses == [ "codex" ];
    assert builtins.length (builtins.attrNames (graphOf [ diamond other ])) == 3;
    assert builtins.attrNames example.disabledProject.skills == [ ];
    assert (graphOf [ ]) == { };
    assert !succeeds (graphOf [ cycle.first ]);
    assert !succeeds (graphOf [ example.base (example.base.override { version = "2"; }) ]);
    assert !succeeds (graphOf [ (empty { agentDependencies = [ pkgs.hello ]; }) ]);
    assert !succeeds (empty { enableHarnesses = [ "claude" ]; }).drvPath;
    assert !succeeds (agentLib.mkProject { inherit pkgs; roots = [ example.base collision ]; }).drvPath;
    assert remote.agentEnv.servers.remote == {
      url = "https://example.invalid/mcp";
      http_headers = { Accept = "application/json"; };
    };
    assert stdio.agentEnv.servers.local == { command = "${pkgs.hello}/bin/hello"; };
    assert !succeeds (empty { mcp.settings.servers.bad = { command = "${pkgs.hello}/bin/hello"; args = [ 1 ]; }; }).agentEnv.servers;
    assert !succeeds (empty { mcp.settings.servers.bad = { url = "https://example.invalid"; type = "sse"; }; }).agentEnv.servers;
    assert !succeeds (empty { mcp.settings.servers.bad = { command = "/usr/bin/server"; }; }).agentEnv.servers;
    assert !succeeds (empty { mcp.settings.servers.bad = { command = "${pkgs.hello}/../../../usr/bin/server"; }; }).agentEnv.servers;
    assert !succeeds (empty { exports.agents.blank = { description = "  \t\n"; developer_instructions = "Read."; }; }).drvPath;
    assert !succeeds (empty { exports.agents.blank = { description = "Reader"; developer_instructions = "  \t\n"; }; }).drvPath;
    assert !succeeds (empty { mcp.settings.model = "unexpected"; }).agentEnv.servers;
    true;
in
{
  evaluation = assert evaluation; pkgs.runCommand "agent-env-evaluation" { } ''touch "$out"'';

  runtime-unit = pkgs.runCommand "agent-env-runtime-unit" { nativeBuildInputs = [ python ]; } ''
    cp -R ${../runtime} runtime
    cp -R ${../tests} tests
    chmod -R u+w runtime tests
    python -m unittest discover -s tests -p 'test_*.py' -v
    touch "$out"
  '';

  upstream-copy = pkgs.runCommand "agent-env-upstream-copy" { nativeBuildInputs = [ python ]; } ''
    export HOME="$TMPDIR/home"
    mkdir -p "$HOME" stage
    export AGENT_SKILLS_ROOT="$PWD/stage"
    ${example.project.skillsInstaller}/bin/agent-env-stage-skills
    test -f stage/skills/example/SKILL.md
    test -f stage/skills/example/.example-data
    test -x stage/skills/example/scripts/hello.sh
    test -z "$(find stage/skills/example -type l -print -quit)"
    cmp ${example.base}/payload/skills/example/.example-data stage/skills/example/.example-data
    stage/skills/example/scripts/hello.sh | grep -F 'Hello from the copied example skill.'
    python - <<'PY'
    import pathlib, tomllib
    role = tomllib.loads(pathlib.Path('${example.base}/codex/agents/example.toml').read_text())
    assert set(role) == {'name', 'description', 'developer_instructions'}
    assert role['name'] == 'example'
    config = tomllib.loads(pathlib.Path('${example.project.mcpConfig}').read_text())
    assert config['mcp_servers']['fetch']['command'].startswith('/nix/store/')
    assert config['mcp_servers']['fetch']['args'] == ['--user-agent=agent-env-nix-example']
    assert 'headers' not in config['mcp_servers']['fetch']
    assert 'type' not in config['mcp_servers']['fetch']
    PY
    touch "$out"
  '';
}
