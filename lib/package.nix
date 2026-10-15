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
    builtins.match ".*[[:cntrl:]].*" path == null &&
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
  # Generate one bounded validation/copy block per declared entry. Interpolation
  # imports path-valued sources and retains their Nix dependency context.
  copyFiles = lib.concatStringsSep "\n" (lib.mapAttrsToList (relative: source: ''
    source=${lib.escapeShellArg "${source}"}
    destination="$out/payload"/${lib.escapeShellArg relative}
    case "$source" in
      /*) ;;
      *) echo "agent-env-nix: source must be absolute: $source" >&2; exit 1 ;;
    esac
    # A trailing slash or /. must not disguise a top-level symlink.
    while [ "$source" != / ]; do
      case "$source" in
        */) source="''${source%/}" ;;
        */.) source="''${source%/.}"; source="''${source:-/}" ;;
        *) break ;;
      esac
    done
    if [ -L "$source" ]; then
      echo "agent-env-nix: source must be a non-symlink root: $source" >&2
      exit 1
    fi
    links=$(${pkgs.coreutils}/bin/mktemp)
    invalid=$(${pkgs.coreutils}/bin/mktemp)
    ${pkgs.coreutils}/bin/realpath -e -z -- "$source" > "$invalid"
    IFS= read -r -d "" boundary < "$invalid"
    # Enumerate physical links before traversing them; every target must stay
    # inside this entry's declared source boundary, even through other links.
    ${pkgs.findutils}/bin/find -P "$source" -type l -print0 > "$links"
    while IFS= read -r -d "" link; do
      ${pkgs.coreutils}/bin/realpath -e -z -- "$link" > "$invalid"
      IFS= read -r -d "" resolved < "$invalid"
      case "$resolved" in
        "$boundary"|"''${boundary%/}"/*) ;;
        *) echo "agent-env-nix: source link escapes declared tree: $link" >&2; exit 1 ;;
      esac
    done < "$links"
    # find diagnoses traversal cycles. Any remaining non-file/non-directory
    # object (including a dangling link) is invalid; cp never sees such a tree.
    ${pkgs.findutils}/bin/find -L "$source" ! -type f ! -type d -print0 > "$invalid"
    if [ -s "$invalid" ]; then
      echo "agent-env-nix: special or dangling source file is unsupported: $source" >&2
      exit 1
    fi
    ${pkgs.coreutils}/bin/rm -- "$links" "$invalid"
    ${pkgs.coreutils}/bin/mkdir -p -- "$(${pkgs.coreutils}/bin/dirname -- "$destination")"
    ${pkgs.coreutils}/bin/cp -R -L --preserve=mode -- "$source" "$destination"
  '') files);
  payloadManifest = pkgs.writeText "agent-env-package.json" (builtins.toJSON {
    schemaVersion = 1;
    inherit id version skills servers;
    agents = builtins.attrNames agents;
    runtimePackages = map toString runtimePackages;
    dependencies = map (dep: toString dep) agentDependencies;
  });
  result = pkgs.runCommand "${lib.strings.sanitizeDerivationName id}-${lib.strings.sanitizeDerivationName version}" {
    nativeBuildInputs = [ pkgs.coreutils pkgs.findutils ];
    passthru.agentEnv = {
      schemaVersion = 1;
      inherit id version agentDependencies runtimePackages servers;
      enableHarnesses = harnesses;
      exports = { inherit skills agents; };
    };
  } ''
    set -euo pipefail
    mkdir -p "$out/payload" "$out/codex/agents"
    ${copyFiles}
    ${lib.concatStringsSep "\n" (lib.mapAttrsToList (name: relative: ''
      skill="$out/payload"/${lib.escapeShellArg relative}
      if [ ! -d "$skill" ] || [ ! -f "$skill/SKILL.md" ]; then
        echo ${lib.escapeShellArg "agent-env-nix: skill ${name} is missing its directory or SKILL.md: ${relative}"} >&2
        exit 1
      fi
    '') skills)}
    ${lib.concatStringsSep "\n" (lib.mapAttrsToList (name: file: ''
      cp ${file} "$out/codex/agents/${name}.toml"
    '') agentFiles)}
    cp ${payloadManifest} "$out/agent-env.json"
  '';
in
assert checks;
result

