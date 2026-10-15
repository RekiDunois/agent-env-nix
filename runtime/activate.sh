# Loaded after fixed Nix-generated paths and copy_current() in the built script.
set -euo pipefail
umask 077

die() { printf 'agent-env: %s\n' "$*" >&2; exit 1; }
usage() { printf 'usage: agent-env apply|remove --project PATH [--extra-config FILE]\n' >&2; exit 2; }
action=${1:-}; [ "$#" -gt 0 ] && shift
case "$action" in apply|remove) ;; *) usage ;; esac
project_arg=
extra=()
while [ "$#" -gt 0 ]; do
  case "$1" in
    --project) [ "$#" -ge 2 ] || usage; project_arg=$2; shift 2 ;;
    --extra-config) [ "$#" -ge 2 ] || usage; extra+=(--extra-config "$2"); shift 2 ;;
    *) usage ;;
  esac
done
[ -n "$project_arg" ] && [ -d "$project_arg" ] || die 'project must be an existing directory'
IFS= read -r -d '' project < <(realpath -e -z -- "$project_arg") || die 'cannot resolve project directory'
state_dir="$project/.agent-env-nix"

# The project itself is canonical; all managed parent components must be real.
safe_path() {
  local target=$1 current=$project relative component
  case "$target" in "$project"/*) relative=${target#"$project"/} ;; *) die "path outside project: $target" ;; esac
  while [ -n "$relative" ]; do
    component=${relative%%/*}
    [ -n "$component" ] && [ "$component" != . ] && [ "$component" != .. ] || die 'unsafe path component'
    current="$current/$component"
    [ ! -L "$current" ] || die "symlinked managed component: $current"
    if [ "$relative" = "$component" ]; then break; fi
    [ ! -e "$current" ] || [ -d "$current" ] || die "non-directory parent: $current"
    relative=${relative#*/}
  done
}
valid_name() { [[ $1 =~ ^[A-Za-z0-9][A-Za-z0-9_.-]*$ ]] && [ "$1" != . ] && [ "$1" != .. ]; }
check_names() {
  # Validate raw inventory bytes before line parsing: no NUL, partial last line,
  # or delimiter injection can turn one recorded name into another cleanup path.
  jq -e -Rs '
    . == "" or (endswith("\n") and
      (split("\n")[:-1] | all(.[]; test("\\A[A-Za-z0-9][A-Za-z0-9_.-]*\\z"))))
  ' "$1" >/dev/null || die "invalid export inventory: $1"
}

safe_path "$state_dir"
[ ! -e "$state_dir" ] || [ -d "$state_dir" ] || die 'state path is not a directory'
mkdir -p -- "$state_dir"
permissions=$(stat -c %a -- "$state_dir")
(( (8#$permissions & 077) == 0 )) || die 'state directory must be private (mode 0700)'
safe_path "$state_dir/lock"
[ ! -e "$state_dir/lock" ] || [ -f "$state_dir/lock" ] || die 'lock is not a regular file'
exec 9>"$state_dir/lock"
flock -x 9
for path in state.json skills.list agents.list mcp-state.json roots staging pending.json; do safe_path "$state_dir/$path"; done
[ ! -e "$state_dir/pending.json" ] || die 'old pending publication exists; resolve it with the previous agent-env version first'
for file in state.json skills.list agents.list mcp-state.json; do
  [ ! -e "$state_dir/$file" ] || [ -f "$state_dir/$file" ] || die "state file is not regular: $file"
done
for directory in roots staging; do
  [ ! -e "$state_dir/$directory" ] || [ -d "$state_dir/$directory" ] || die "state directory is invalid: $directory"
done
mkdir -p -- "$state_dir/roots" "$state_dir/staging"
shopt -s nullglob dotglob
for root in "$state_dir/roots/"*; do
  [ -L "$root" ] || die "unexpected root object retained: $root"
  IFS= read -r -d '' root_target < <(readlink -z -- "$root") || die 'cannot read root link'
  [[ $root_target =~ ^/nix/store/[a-z0-9]{32}-[A-Za-z0-9+._?=-]+$ ]] || die "unexpected root target retained: $root"
  [[ ${root##*/} =~ ^([0-9a-f]{32}|[a-z0-9]{32}-[A-Za-z0-9+._?=-]+)$ ]] || die 'invalid root name'
done
for kind in skills agents; do
  [ ! -e "$state_dir/$kind.list" ] || check_names "$state_dir/$kind.list"
done
work=$(mktemp -d "$state_dir/staging/attempt.XXXXXXXX")
cleanup() {
  status=$?
  trap - EXIT
  if [ -d "$work" ] && [ ! -L "$work" ]; then chmod -R u+w -- "$work" 2>/dev/null || :; rm -rf -- "$work"; fi
  if [ "$status" -ne 0 ]; then printf 'agent-env: failed; selected files may be partially updated. Roots and deployment names are retained; fix the error and rerun.\n' >&2; fi
  exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# Only a selected leaf is destructive. Never follow it or clear its parent.
remove_leaf() {
  local parent=$1 name=$2 target
  valid_name "$name" || die 'unsafe selected export name'
  safe_path "$parent"
  target="$parent/$name"
  if [ -L "$target" ]; then rm -- "$target"
  elif [ -d "$target" ]; then
    # find does not follow internal links, and chmod is limited to real objects.
    find -P "$target" -type d -exec chmod u+rwx -- {} +
    find -P "$target" -type f -exec chmod u+rw -- {} +
    rm -rf -- "$target"
  elif [ -e "$target" ]; then rm -- "$target"
  fi
}

# Schema-1 migration extracts known fields once, without replaying old journals.
if [ -e "$state_dir/state.json" ]; then
  version=$(jq -er '.schemaVersion' "$state_dir/state.json")
  case "$version" in
    1)
      jq -e '
        def name: type=="string" and test("\\A[A-Za-z0-9][A-Za-z0-9_.-]*\\z") and .!="." and .!="..";
        def exports: type=="object" and all(to_entries[]; (.key|name) and (.value|type)=="object" and (.value.owner|type)=="string");
        .schemaVersion==1 and (.skills|exports) and (.agents|exports) and (.mcp|exports) and
        all(.mcp[]; (.value|type)=="object") and
        (.reused|type)=="array" and all(.reused[];
          type=="object" and (.kind=="skill" or .kind=="agent" or .kind=="mcp") and
          (.name|name) and (.source|type)=="string" and (.source|startswith("/"))) and
        (.roots|type)=="array" and all(.roots[];
          type=="object" and (.name|type)=="string" and (.name|test("\\A[0-9a-f]{32}\\z")) and
          (.environment|type)=="string" and (.environment|test("\\A/nix/store/[a-z0-9]{32}-[A-Za-z0-9+._?=-]+\\z")))
      ' "$state_dir/state.json" >/dev/null || die 'invalid legacy state'
      # Root identities in schema 1 are hashes of their exact environment path.
      while IFS=$'\t' read -r root_name root_environment; do
        expected=$(printf %s "$root_environment" | sha256sum)
        [ "$root_name" = "${expected:0:32}" ] || die 'invalid legacy root identity'
      done < <(jq -r '.roots[] | [.name,.environment] | @tsv' "$state_dir/state.json")
      for kind in skills agents; do
        jq -r --arg k "$kind" '.[$k] | keys[]' "$state_dir/state.json" > "$work/$kind.old"
        check_names "$work/$kind.old"
        if [ -e "$state_dir/$kind.list" ]; then
          [ -f "$state_dir/$kind.list" ] || die 'deployment inventory must be a regular file'
          cat "$state_dir/$kind.list" >> "$work/$kind.old"
        fi
        sort -u "$work/$kind.old" > "$work/$kind.list"
        check_names "$work/$kind.list"
        mv -- "$work/$kind.list" "$state_dir/$kind.list"
      done
      if [ ! -e "$state_dir/mcp-state.json" ]; then
        jq '{schemaVersion:2,mcp:.mcp,reused:[.reused[]|select(.kind=="mcp")],retainRoots:(.reused|length>0)}' "$state_dir/state.json" > "$work/mcp-state.json"
        mv -- "$work/mcp-state.json" "$state_dir/mcp-state.json"
      fi
      ;;
    2) jq -e ' . == {schemaVersion:2} ' "$state_dir/state.json" >/dev/null || die 'invalid deployment state marker' ;;
    *) die 'unsupported deployment state schema' ;;
  esac
elif [ -e "$state_dir/skills.list" ] || [ -e "$state_dir/agents.list" ]; then
  die 'deployment inventory exists without its schema marker'
fi
printf '{"schemaVersion":2}\n' > "$work/state.json"
mv -- "$work/state.json" "$state_dir/state.json"
for kind in skills agents; do
  if [ ! -e "$state_dir/$kind.list" ]; then : > "$state_dir/$kind.list"; fi
  [ -f "$state_dir/$kind.list" ] || die 'deployment inventory must be a regular file'
  check_names "$state_dir/$kind.list"
  if [ "$action" = apply ]; then jq -r --arg k "$kind" '.[$k] | keys[]' "$manifest" > "$work/$kind.desired"
  else : > "$work/$kind.desired"; fi
  check_names "$work/$kind.desired"
done
for parent in "$project/.agents/skills" "$project/.codex/agents"; do safe_path "$parent"; done

config_args=(--manifest "$manifest" --project "$project" --state "$state_dir/mcp-state.json" --prepared "$work/config.json" --action "$action" "${extra[@]}")
"$python_bin" "$config_helper" prepare "${config_args[@]}"

current_root=
if [ "$action" = apply ]; then
  mkdir -- "$work/upstream"
  AGENT_SKILLS_ROOT="$work/upstream" AGENT_SKILLS_QUIET=1 AGENT_SKILLS_FORCE= "$skills_installer"
  rm -f -- "$work/upstream/skills/.agent-skills-managed.json"
  current_root="$state_dir/roots/$(basename -- "$environment")"
  if [ -e "$current_root" ] || [ -L "$current_root" ]; then
    [ -L "$current_root" ] && [ "$(readlink -- "$current_root")" = "$environment" ] || die 'unexpected current root object'
  fi
  "$nix_store" --realise "$environment" --add-root "$current_root" --indirect >/dev/null
  [ -L "$current_root" ] && [ "$(readlink -- "$current_root")" = "$environment" ] || die 'Nix did not create the expected GC root'
fi

# A conservative name inventory is sufficient for rerun/remove; no operation log.
for kind in skills agents; do
  cat "$state_dir/$kind.list" "$work/$kind.desired" | sort -u > "$work/$kind.union"
  cp -- "$work/$kind.union" "$work/$kind.next"
  mv -- "$work/$kind.next" "$state_dir/$kind.list"
done
if [ "$action" = apply ]; then copy_current; fi
for kind in skills agents; do
  if [ "$kind" = skills ]; then parent="$project/.agents/skills"; suffix=; else parent="$project/.codex/agents"; suffix=.toml; fi
  while IFS= read -r name; do
    if ! grep -Fxq -- "$name" "$work/$kind.desired"; then remove_leaf "$parent" "$name$suffix"; fi
  done < "$work/$kind.union"
done
root_policy=$("$python_bin" "$config_helper" commit "${config_args[@]}")
case "$root_policy" in retain-roots|release-roots) ;; *) die 'invalid config root-retention result' ;; esac
for kind in skills agents; do mv -- "$work/$kind.desired" "$state_dir/$kind.list"; done
if [ "$root_policy" = release-roots ]; then
  shopt -s nullglob dotglob
  for root in "$state_dir/roots/"*; do
    [ "$root" = "$current_root" ] && continue
    [ -L "$root" ] || die "unexpected root object retained: $root"
    case "$(readlink -- "$root")" in /nix/store/*) rm -- "$root" ;; *) die "unexpected root link retained: $root" ;; esac
  done
else
  printf 'agent-env: retained previous GC roots for preserved configuration or legacy reused content.\n'
fi
printf 'agent-env: %s completed.\n' "$action"
