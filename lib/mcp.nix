{ lib }:
owner: name: value:
let
  fail = reason: throw "agent-env-nix: package ${owner}, MCP ${name}: ${reason}";
  allowed = [
    "command" "args" "env" "env_vars" "cwd" "url" "headers"
    "http_headers" "env_http_headers" "bearer_token_env_var" "type"
    "enabled" "required" "startup_timeout_sec" "startup_timeout_ms"
    "tool_timeout_sec" "enabled_tools" "disabled_tools"
  ];
  raw = if builtins.isAttrs value then value else fail "expected a server attribute set";
  unknown = builtins.filter (key: !(builtins.elem key allowed)) (builtins.attrNames raw);
  present = key: builtins.hasAttr key raw && raw.${key} != null;
  nonempty = key: present key && raw.${key} != { } && raw.${key} != [ ] && raw.${key} != "";
  hasCommand = present "command";
  hasUrl = present "url";
  safeCommand = builtins.isString (raw.command or null) &&
    lib.hasPrefix "${builtins.storeDir}/" raw.command &&
    builtins.getContext raw.command != { } &&
    builtins.all (part: part != "" && part != "." && part != "..")
      (lib.tail (lib.splitString "/" raw.command));
  transport = if hasCommand && !hasUrl then "stdio"
    else if hasUrl && !hasCommand then "http"
    else fail "set exactly one of command or url";
  strings = [ "command" "url" "cwd" "bearer_token_env_var" ];
  lists = [ "args" "env_vars" "enabled_tools" "disabled_tools" ];
  maps = [ "env" "headers" "http_headers" "env_http_headers" ];
  badString = builtins.filter (key: present key &&
    !(builtins.isString raw.${key} && raw.${key} != "")) strings;
  badList = builtins.filter (key: present key &&
    !(builtins.isList raw.${key} && builtins.all builtins.isString raw.${key})) lists;
  badMap = builtins.filter (key: present key &&
    !(builtins.isAttrs raw.${key} && builtins.all builtins.isString (builtins.attrValues raw.${key}))) maps;
  badBool = builtins.filter (key: present key && !builtins.isBool raw.${key}) [ "enabled" "required" ];
  badNumber = builtins.filter (key: present key &&
    !((builtins.isInt raw.${key} || builtins.isFloat raw.${key}) && raw.${key} >= 0))
    [ "startup_timeout_sec" "startup_timeout_ms" "tool_timeout_sec" ];
  forbidden = if transport == "http" then [ "args" "env" "env_vars" "cwd" ]
    else [ "headers" "http_headers" "env_http_headers" "bearer_token_env_var" ];
  badTransport = builtins.filter nonempty forbidden;
  checked =
    if unknown != [ ] then fail "unsupported field(s): ${lib.concatStringsSep ", " unknown}"
    else if badString ++ badList ++ badMap ++ badBool ++ badNumber != [ ] then
      fail "invalid value type for ${lib.concatStringsSep ", " (badString ++ badList ++ badMap ++ badBool ++ badNumber)}"
    else if present "startup_timeout_ms" && !builtins.isInt raw.startup_timeout_ms then fail "startup_timeout_ms must be an integer"
    else if present "startup_timeout_ms" && present "startup_timeout_sec" then fail "choose one startup timeout unit"
    else if present "type" && raw.type != transport then fail "type must agree with command (stdio) or url (http); sse is unsupported"
    else if hasCommand && !safeCommand then
      fail "command must reference a fixed Nix store executable (use a package interpolation)"
    else if badTransport != [ ] then fail "${transport} does not support ${lib.concatStringsSep ", " badTransport}"
    else if transport == "http" && nonempty "headers" && nonempty "http_headers" && raw.headers != raw.http_headers then
      fail "headers and http_headers disagree"
    else true;
  omitted = [ "type" "headers" ] ++ forbidden;
  native = lib.filterAttrs (key: val: !(builtins.elem key omitted) && val != null) raw;
in
assert checked;
native // lib.optionalAttrs (transport == "http" && nonempty "headers") {
  http_headers = raw.headers;
}
