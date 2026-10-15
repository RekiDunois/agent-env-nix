{ lib, mcpServers, normalizeMcp }:
{ pkgs
, id
, version
, files
, agentDependencies ? [ ]
, runtimePackages ? [ ]
, exports ? { }
, mcp ? { }
, mcpOverrides ? { }
, enableHarnesses ? [ "codex" ]
}:
let
  fail = reason: throw "agent-env-nix: package ${id}: ${reason}";
  safeRelative = path: builtins.isString path && path != "" &&
    !(lib.hasPrefix "/" path) && builtins.all
      (part: part != "" && part != "." && part != "..") (lib.splitString "/" path);
  safeName = name: builtins.match "[A-Za-z0-9][A-Za-z0-9_-]*" name != null;
  fileNames = builtins.attrNames files;
  overlapping = lib.any (a: lib.any (b: a != b && lib.hasPrefix "${a}/" b) fileNames) fileNames;
  skills = exports.skills or { };
  agents = exports.agents or { };
  unknownExports = builtins.filter (key: !(builtins.elem key [ "skills" "agents" ])) (builtins.attrNames exports);
  harnesses = lib.unique enableHarnesses;
  checks =
    if !builtins.isString id || id == "" then fail "id must be a nonempty string"
    else if !builtins.isString version || version == "" then fail "version must be a nonempty string"
    else if !builtins.isAttrs files || !builtins.all safeRelative fileNames then fail "files must use safe relative paths"
    else if overlapping then fail "files destinations overlap"
    else if !builtins.isList agentDependencies || !builtins.isList runtimePackages || !builtins.all lib.isDerivation runtimePackages then
      fail "agentDependencies must be a list; runtimePackages must be a list of derivations"
    else if !builtins.isList enableHarnesses || !builtins.all (h: h == "codex") enableHarnesses then fail "only codex is supported; use [] to disable projection"
    else if unknownExports != [ ] then fail "unknown exports: ${lib.concatStringsSep ", " unknownExports}"
    else if !builtins.isAttrs skills || !builtins.all safeName (builtins.attrNames skills) || !builtins.all safeRelative (builtins.attrValues skills) then
      fail "skills must map safe names to safe package-relative directories"
    else if !builtins.isAttrs agents || !builtins.all safeName (builtins.attrNames agents) then fail "invalid agent names"
    else true;
  evaluated = mcpServers.lib.evalModule pkgs {
    imports = [ mcp mcpOverrides ];
    settings.servers = { };
    flavor = "codex";
    format = "toml";
    fileName = "agent-env-upstream-mcp.toml";
  };
  extra = builtins.removeAttrs evaluated.config.settings [ "servers" ];
  servers = if extra != { } then fail "MCP module may set settings.servers only"
    else builtins.seq evaluated.config.configFile
      (lib.mapAttrs (normalizeMcp id) evaluated.config.settings.servers);
  agentFiles = lib.mapAttrs (name: value:
    if !builtins.isAttrs value || builtins.attrNames value != [ "description" "developer_instructions" ] ||
      !builtins.isString value.description || builtins.match "[[:space:]]*" value.description != null ||
      !builtins.isString value.developer_instructions || builtins.match "[[:space:]]*" value.developer_instructions != null then
      fail "agent ${name} must define nonempty description and developer_instructions"
    else (pkgs.formats.toml { }).generate "agent-${name}.toml" ({ inherit name; } // value)
  ) agents;
  # Interpolation imports path-valued sources with their dependency context;
  # plain toString on a path would leave an untracked sandbox-invisible path.
  filesConfig = pkgs.writeText "agent-env-files.json" (builtins.toJSON (lib.mapAttrs (_: source: "${source}") files));
  skillsConfig = pkgs.writeText "agent-env-skill-paths.json" (builtins.toJSON skills);
  payloadManifest = pkgs.writeText "agent-env-package.json" (builtins.toJSON {
    schemaVersion = 1;
    inherit id version skills servers;
    agents = builtins.attrNames agents;
    runtimePackages = map toString runtimePackages;
    dependencies = map (dep: toString dep) agentDependencies;
  });
  result = pkgs.runCommand "${lib.strings.sanitizeDerivationName id}-${lib.strings.sanitizeDerivationName version}" {
    nativeBuildInputs = [ pkgs.python3 ];
    passthru.agentEnv = {
      schemaVersion = 1;
      inherit id version agentDependencies runtimePackages servers;
      enableHarnesses = harnesses;
      exports = { inherit skills agents; };
    };
  } ''
    mkdir -p "$out/payload" "$out/codex/agents"
    ${pkgs.python3}/bin/python ${../runtime/materialize.py} \
      --files ${filesConfig} --skills ${skillsConfig} --output "$out/payload"
    ${lib.concatStringsSep "\n" (lib.mapAttrsToList (name: file: ''
      cp ${file} "$out/codex/agents/${name}.toml"
    '') agentFiles)}
    cp ${payloadManifest} "$out/agent-env.json"
  '';
in
assert checks;
result
