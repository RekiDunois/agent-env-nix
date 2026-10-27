{ lib, agentSkills, mcpServers }:
{ pkgs, roots, name ? "agent-environment", dshMcp ? null }:
let
  fail = message: throw "agent-env-nix: ${message}";
  metadata = package:
    if builtins.isAttrs package && package ? agentEnv && package.agentEnv.schemaVersion or 0 == 1 then
      package.agentEnv
    else fail "roots and agentDependencies must contain mkAgentPackage results";
  # Inspect the lazy metadata graph before forcing any dependency payload path.
  # This makes a recursive declaration fail with its dependency path, rather
  # than forcing the derivation's serialized recursive references first.
  visit = harnesses: stack: path: state: package:
    let
      meta = metadata package;
      current = path ++ [ meta.id ];
      trail = lib.concatStringsSep " -> " current;
      children = builtins.foldl' (visit harnesses (stack ++ [ meta.id ]) current) state meta.agentDependencies;
      identity = "${package.drvPath}:${package.outputName or "out"}:${package.system}";
      previous = children.${meta.id} or null;
      entry = {
        inherit package identity;
        enableHarnesses = lib.unique ((if previous == null then [ ] else previous.enableHarnesses) ++ harnesses);
        paths = (if previous == null then [ ] else previous.paths) ++ [ trail ];
      };
    in
    if builtins.elem meta.id stack then fail "dependency cycle: ${trail}"
    else if previous != null && previous.identity != identity then
      fail "conflicting package ${meta.id}: version ${previous.package.agentEnv.version} (${previous.package.drvPath}) via ${lib.concatStringsSep "; " previous.paths}, versus version ${meta.version} (${package.drvPath}) via ${trail}"
    else children // { ${meta.id} = entry; };
  graph = if !builtins.isList roots then fail "roots must be a list"
    else builtins.foldl' (state: package: visit (metadata package).enableHarnesses [ ] [ ] state package) { } roots;
  selected = builtins.filter (entry: entry.enableHarnesses != [ ]) (builtins.attrValues graph);
  collect = kind: getValues:
    builtins.foldl' (acc: entry:
      let owner = entry.package.agentEnv.id;
      in lib.foldlAttrs (result: exportName: value:
        if builtins.hasAttr exportName result then
          fail "${kind} export ${exportName} collides between ${result.${exportName}.owner} and ${owner}"
        else result // { ${exportName} = { inherit owner value; package = entry.package; }; }
      ) acc (getValues entry.package)
    ) { } selected;
  skillRecords = collect "skill" (package: package.agentEnv.exports.skills);
  agentRecords = collect "agent" (package: package.agentEnv.exports.agents);
  mcpRecords = collect "MCP" (package: package.agentEnv.servers);
  skills = lib.mapAttrs (_: record: {
    inherit (record) owner;
    source = "${record.package}/payload/${record.value}";
  }) skillRecords;
  agents = lib.mapAttrs (agentName: record: {
    inherit (record) owner;
    source = "${record.package}/codex/agents/${agentName}.toml";
  }) agentRecords;
  servers = lib.mapAttrs (_: record: record.value) mcpRecords;
  mcpHarnesses = lib.mapAttrs (_: record: graph.${record.owner}.enableHarnesses) mcpRecords;
  explicitBackends = collect "proxy backend" (package: package.agentEnv.proxyBackends or { });
  proxyBackends = lib.mapAttrs (serverName: record:
    if builtins.hasAttr serverName explicitBackends then explicitBackends.${serverName}.value
    else (builtins.intersectAttrs { command = null; args = null; env = null; } record.value)
      // { options.disabled = true; }
  ) (lib.filterAttrs (serverName: record: builtins.hasAttr serverName explicitBackends || record.value ? command) mcpRecords);
  proxyConfig = pkgs.writeText "${name}-mcp-proxy.json" (builtins.toJSON { mcpServers = proxyBackends; });
  connections = lib.mapAttrs (serverName: record: {
    inherit (record) owner;
    client = record.value;
    enableHarnesses = mcpHarnesses.${serverName};
    backendSource = if builtins.hasAttr serverName explicitBackends then "explicit"
      else if record.value ? command then "stdio" else "none";
    requiredEnvironment = record.value.env_vars or [ ];
    manualCompletion = if builtins.hasAttr serverName explicitBackends then
      [ "Review producer backend environment and enable only after operator configuration." ]
      else if record.value ? command then [
        "Disabled draft: supply requiredEnvironment in the proxy process/config; no secrets were read."
        "Review original client cwd and client-specific policy; these fields are not translated into the backend fragment."
      ] else [ "Existing HTTP connection only; no backend command inferred or service redeployed." ];
  }) mcpRecords;
  connectionsFile = pkgs.writeText "${name}-mcp-connections.json" (builtins.toJSON connections);
  mcpConfig = mcpServers.lib.mkConfig pkgs {
    flavor = "codex";
    format = "toml";
    fileName = "agent-env-codex-mcp.toml";
    settings.servers = servers;
  };
  skillBundle = pkgs.runCommand "${name}-skills" { } ''
    mkdir -p "$out"
    ${lib.concatStringsSep "\n" (lib.mapAttrsToList (skillName: record: ''
      ln -s ${lib.escapeShellArg record.source} "$out/${skillName}"
    '') skills)}
  '';
  skillsInstaller = agentSkills.lib.agent-skills.mkSyncProgram {
    inherit pkgs;
    bundle = skillBundle;
    mode = "local";
    programName = "agent-env-stage-skills";
    allowOverrides = false;
    excludePatterns = [ ];
    targets.codex = { enable = true; dest = "skills"; structure = "copy-tree"; };
  };
  python = pkgs.python3.withPackages (ps: [ ps.tomlkit ]);
  activation = pkgs.writeText "${name}-activate.sh" (''
    environment=@AGENT_ENV_OUTPUT@
    manifest=@AGENT_ENV_OUTPUT@/manifest.json
    proxy_config=${proxyConfig}
    connections_file=${connectionsFile}
    config_helper=@AGENT_ENV_OUTPUT@/lib/config.py
    python_bin=${python}/bin/python
    nix_store=${pkgs.nix}/bin/nix-store
    skills_installer=${skillsInstaller}/bin/agent-env-stage-skills
    copy_current() {
      ${lib.concatStringsSep "\n" (lib.mapAttrsToList (skillName: _: ''
        safe_path "$project/.agents/skills" true
        mkdir -p -- "$project/.agents/skills"
        remove_leaf "$project/.agents/skills" ${lib.escapeShellArg skillName}
        cp -a -- "$work/upstream/skills/${skillName}" "$project/.agents/skills/${skillName}"
        chmod -R u+w -- "$project/.agents/skills/${skillName}"
      '') skills)}
      ${lib.concatStringsSep "\n" (lib.mapAttrsToList (agentName: record: ''
        safe_path "$project/.codex/agents" true
        mkdir -p -- "$project/.codex/agents"
        remove_leaf "$project/.codex/agents" ${lib.escapeShellArg "${agentName}.toml"}
        cp -- ${lib.escapeShellArg record.source} "$project/.codex/agents/${agentName}.toml"
        chmod u+w -- "$project/.codex/agents/${agentName}.toml"
      '') agents)}
      :
    }
  '' + builtins.readFile ../runtime/activate.sh);
  manifest = pkgs.writeText "${name}-manifest.json" (builtins.toJSON {
    schemaVersion = 1;
    environment = "@AGENT_ENV_OUTPUT@";
    nixStore = "${pkgs.nix}/bin/nix-store";
    skillsInstaller = "${skillsInstaller}/bin/agent-env-stage-skills";
    inherit skills agents mcpHarnesses;
    dshMcp = lib.any (harnesses: builtins.elem "dsh" harnesses) (builtins.attrValues mcpHarnesses);
    mcpConfig = toString mcpConfig;
    mcpPortEnv = lib.foldlAttrs (acc: serverName: record:
      acc // lib.optionalAttrs (builtins.hasAttr serverName (record.package.agentEnv.mcpPortEnv or { })) {
        ${serverName} = record.package.agentEnv.mcpPortEnv.${serverName};
      }) { } mcpRecords;
    mcpOwners = lib.mapAttrs (_: record: record.owner) mcpRecords;
    packages = map (entry: {
      inherit (entry.package.agentEnv) id version;
      inherit (entry) enableHarnesses;
      payload = "${entry.package}/payload";
    }) (builtins.attrValues graph);
  });
in
assert lib.assertMsg (dshMcp == null) "agent-env-nix: replace mkProject.dshMcp with rootPackage.override { enableHarnesses = [ \"codex\" \"dsh\" ]; }";
# Force collision and graph checks even when callers only inspect drvPath.
builtins.deepSeq (builtins.attrNames skills ++ builtins.attrNames agents ++ builtins.attrNames servers ++ builtins.attrNames proxyBackends)
  (pkgs.runCommand name {
    nativeBuildInputs = [ pkgs.makeWrapper ];
    passthru = {
      inherit graph skills agents servers mcpConfig mcpHarnesses proxyBackends proxyConfig connections skillBundle skillsInstaller;
    };
  } ''
    mkdir -p "$out/bin" "$out/lib"
    cp ${proxyConfig} "$out/mcp-proxy.json"
    cp ${connectionsFile} "$out/mcp-connections.json"
    cp ${../runtime/config.py} "$out/lib/config.py"
    substitute ${activation} "$out/lib/activate.sh" --replace-fail '@AGENT_ENV_OUTPUT@' "$out"
    substitute ${manifest} "$out/manifest.json" --replace-fail '@AGENT_ENV_OUTPUT@' "$out"
    makeWrapper ${pkgs.bash}/bin/bash "$out/bin/agent-env" \
      --prefix PATH : ${lib.makeBinPath [ pkgs.coreutils pkgs.findutils pkgs.gnugrep pkgs.jq pkgs.flock ]} \
      --add-flags "$out/lib/activate.sh"
  '')




