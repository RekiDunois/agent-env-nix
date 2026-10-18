{ pkgs, environment, name ? "agent-env-activate" }:

# name changes only the executable/diagnostics, never the project cache or lock.
assert pkgs.lib.assertMsg
  (builtins.isString name && builtins.match "[a-zA-Z0-9][a-zA-Z0-9._-]*" name != null)
  "mkCachedActivation: name must be a nonempty executable basename";
pkgs.runCommand name { } ''
  mkdir -p "$out/bin"
  substitute ${../runtime/cached-activate.sh} "$out/bin/${name}" \
    --replace-fail '@bash@' '${pkgs.bash}' \
    --replace-fail '@coreutils@' '${pkgs.coreutils}' \
    --replace-fail '@environment@' '${environment}' \
    --replace-fail '@name@' '${name}'
  chmod 0555 "$out/bin/${name}"
''
