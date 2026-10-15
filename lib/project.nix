{ lib, agentSkills, mcpServers }:
{ pkgs, roots, name ? "agent-environment" }:
let
  fail = message: throw "agent-env-nix: ${message}";
  metadata = package:
    if builtins.isAttrs package && package ? agentEnv && package.agentEnv.schemaVersion or 0 == 1 then
      package.agentEnv
    else fail "roots and agentDependencies must contain mkAgentPackage results";
  # Inspect the lazy metadata graph before forcing any dependency payload path.
  # This makes a recursive declaration fail with its dependency path, rather
  # than forcing the derivation's serialized recursive references first.
  visit = stack: path: state: package:
    let
      meta = metadata package;
      current = path ++ [ meta.id ];
      trail = lib.concatStringsSep " -> " current;
      children = builtins.foldl' (visit (stack ++ [ meta.id ]) current) state meta.agentDependencies;
      identity = "${package.drvPath}:${package.outputName or "out"}:${package.system}";
      previous = children.${meta.id} or null;
      entry = {
        inherit package identity;
        enableHarnesses = lib.unique ((if previous == null then [ ] else previous.enableHarnesses) ++ meta.enableHarnesses);
        paths = (if previous == null then [ ] else previous.paths) ++ [ trail ];
      };
    in
    if builtins.elem meta.id stack then fail "dependency cycle: ${trail}"
    else if previous != null && previous.identity != identity then
      fail "conflicting package ${meta.id}: version ${previous.package.agentEnv.version} (${previous.package.drvPath}) via ${lib.concatStringsSep "; " previous.paths}, versus version ${meta.version} (${package.drvPath}) via ${trail}"
    else children // { ${meta.id} = entry; };
  graph = if !builtins.isList roots then fail "roots must be a list"
    else builtins.foldl' (visit [ ] [ ]) { } roots;
  selected = builtins.filter (entry: builtins.elem "codex" entry.enableHarnesses) (builtins.attrValues graph);
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
  manifest = pkgs.writeText "${name}-manifest.json" (builtins.toJSON {
    schemaVersion = 1;
    environment = "@AGENT_ENV_OUTPUT@";
    nixStore = "${pkgs.nix}/bin/nix-store";
    skillsInstaller = "${skillsInstaller}/bin/agent-env-stage-skills";
    inherit skills agents;
    mcpConfig = toString mcpConfig;
    mcpOwners = lib.mapAttrs (_: record: record.owner) mcpRecords;
    packages = map (entry: {
      inherit (entry.package.agentEnv) id version;
      inherit (entry) enableHarnesses;
      payload = "${entry.package}/payload";
    }) (builtins.attrValues graph);
  });
in
# Force collision and graph checks even when callers only inspect drvPath.
builtins.deepSeq (builtins.attrNames skills ++ builtins.attrNames agents ++ builtins.attrNames servers)
  (pkgs.runCommand name {
    nativeBuildInputs = [ pkgs.makeWrapper ];
    passthru = {
      inherit graph skills agents servers mcpConfig skillBundle skillsInstaller;
    };
  } ''
    mkdir -p "$out/bin" "$out/lib"
    cp ${../runtime/activate.py} "$out/lib/activate.py"
    substitute ${manifest} "$out/manifest.json" --replace-fail '@AGENT_ENV_OUTPUT@' "$out"
    makeWrapper ${python}/bin/python "$out/bin/agent-env" \
      --add-flags "$out/lib/activate.py --manifest $out/manifest.json"
  '')
