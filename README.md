# agent-env-nix

A small Nix library for producer-owned agent packages and explicit project-local Codex activation.

It composes two pinned upstreams instead of vendoring them:

- [agent-skills-nix](https://github.com/Kyure-A/agent-skills-nix/tree/2948865044b2af55c8c4e4eb2abda7de79d60f0e) supplies the copy-tree synchronization primitive.
- [mcp-servers-nix](https://github.com/natsukium/mcp-servers-nix/tree/31848978eefbca17f1658a55066b1d2aaa43cafc) supplies server packages, modules, and TOML generation.
- [TOMLKit](https://github.com/python-poetry/tomlkit) edits selected existing TOML tables while preserving unrelated settings and comments.

This repository adds an explicit package/dependency contract, native Codex agent files, and a narrow shell activation layer with MCP-only configuration protection. Codex is the only implemented harness. Existing producer APM/uv workflows are unchanged.

## Try the included example

With Nix flakes enabled, from this repository:

```sh
nix build .#example
mkdir -p /absolute/path/to/example-project
./result/bin/agent-env apply --project /absolute/path/to/example-project
./result/bin/agent-env remove --project /absolute/path/to/example-project
```

The example combines two root packages with a shared dependency. It copies a complete skill (including a script and hidden support file), installs a native example agent, and registers a fixed-path fetch MCP server configuration. Activation does not start that server or a Codex session. The project must already be trusted by Codex; this tool does not change trust.

First-round delivery targets only `aarch64-darwin`. Existing Linux outputs remain in code, but Linux support/builds are not delivery or test gates. The approved T1–T4 Darwin build/runtime checks passed on an Apple Silicon Mac on 2026-10-16 (runtime-unit 38/38, upstream-copy, example build and two-example integration); third-gate test-result review is PASS. Prior Linux runs remain supplementary evidence only. See [validation](docs/validation.md) and [test review](plan/test-review.md) for the exact scope, results and exclusions.

## Cached shell activation

`lib.mkCachedActivation { pkgs; environment; name ? "agent-env-activate"; }`
wraps one existing `mkProject` environment. It extracts the cached wrapper from
[professor-contact PR #96](https://github.com/ScholarWorkflow/professor-contact/pull/96)
without changing `agent-env apply` or `remove`.

```nix
let
  environment = inputs.agent-env.lib.mkProject {
    inherit pkgs;
    roots = [ review otherWorkflow ];
  };
  activate = inputs.agent-env.lib.mkCachedActivation {
    inherit pkgs environment;
    # Optional executable name, e.g. "professor-contact-activate".
  };
in pkgs.mkShell {
  packages = [ activate ];
  shellHook = ''
    "${activate}/bin/agent-env-activate" --project "$PWD" || exit $?
  '';
}
```

With an existing direnv setup, use this as the consumer's devShell and put
`use flake` in its `.envrc`. The consumer's lock file pins its inputs. Call the
Nix-built entrypoint; do not copy the shell implementation into each producer.
The CLI accepts `--project DIRECTORY` (default: current directory), `--force`,
and `--help`. `name` only selects the executable and diagnostic prefix.

The cache key includes the environment store output, physical project path, and
a digest of effective MCP configuration (see [activation-time HTTP port](#activation-time-http-port)).
First use, a changed environment or port, or a moved project invokes the existing
`agent-env apply --project`; an unchanged successful key skips it. All names
share one project marker `.agent-env-applied` and lock `.agent-env-apply.lock`.
A failed apply invalidates the previous success; only successful apply publishes
a marker atomically. Symlink/non-regular markers and newline-containing project
paths are rejected. Relative paths ignore inherited `CDPATH`.

Use **one combined environment per project**: combine multiple roots in
`mkProject` before wrapping. Two separate producer environments are replacements,
not additive installations. Their common marker ensures A → B → A reapplies A;
separate per-producer markers would incorrectly skip it. Renaming a wrapper for
the same environment does not create another cache namespace.

Add `/.agent-env-applied` and `/.agent-env-apply.lock/` to the consumer's
`.gitignore`. Concurrent wrapper calls fail fast; retry after the active call
finishes. After a crash, remove the stale lock directory only after checking no
activation is running. Direct `agent-env apply` / `remove` do not participate in
this lock or update/invalidate the marker: do not run them concurrently with the
wrapper, and use `agent-env-activate --force` afterward to reapply. Manual edits
or deletions of installed files likewise require `--force`; the cache does not
monitor files or bypass the installer's existing configuration protections.
Old producer-specific PR #96 markers are not reused by this shared wrapper.

Offline checks: `python3 tests/test_cached_activation.py -v` using host Bash and
GNU coreutils (macOS's default BSD tools are insufficient). These use a stub
installer, not a real installation. See the [implementation plan](plan/cached-activation/implementation-plan.md) and
[test plan and results](plan/cached-activation/test-plan.md).

## Producer package

A producer owns its package split, business files, instructions, runtimes, and direct dependencies. A package file suitable for `callPackage` looks like:

```nix
{ pkgs, mkAgentPackage, enableHarnesses ? [ "codex" ] }:
mkAgentPackage {
  inherit pkgs enableHarnesses;
  id = "my-workflow-core";
  version = "0.1.0";
  files."skills/review" = ./skills/review;
  exports.skills.review = "skills/review";
  exports.agents.reviewer = {
    description = "Review the current changes.";
    developer_instructions = "Read the review skill and report concrete findings.";
  };
  agentDependencies = [ ];
  runtimePackages = [ pkgs.git ];
  mcp.programs.fetch.enable = true;
}
```

Instantiate it with the shared library and choose project roots:

```nix
let
  review = pkgs.callPackage ./package.nix {
    mkAgentPackage = inputs.agent-env.lib.mkAgentPackage;
  };
  environment = inputs.agent-env.lib.mkProject {
    inherit pkgs;
    roots = [ review ];
  };
in {
  packages.${system}.agent-environment = environment;
}
```

`inputs.agent-env` is this flake, pinned by the consumer's `flake.lock`. This repository is private: remote consumers need their own GitHub read access through existing Nix/Git authentication or an SSH flake input. Do not embed tokens in a flake, package declaration, or store file. A local checkout can be used as a path input. No extra `agentModules` output is required. Multiple roots and recursive explicit `agentDependencies` are supported. Ordinary `runtimePackages` are retained in the closure but never traversed for agent exports.

`files` maps non-overlapping package-relative paths to source files or complete trees. Directory contents, dotfiles, empty directories, and executable bits survive. Internal source-tree links are materialized; escaping/dangling links, top-level symlink roots, cycles, and special files fail. Each exported skill must contain `SKILL.md`. Producers must include every support file their skills need and make their runtime commands Nix-ready; this library does not rewrite business instructions or install packages at runtime.

The result is an ordinary derivation:

- `$out/payload/`: complete declared producer files
- `$out/codex/agents/`: native standalone TOML files
- `$out/agent-env.json`: package metadata with real dependency/runtime references
- `passthru.agentEnv`: composition metadata

## Overrides and collisions

`enableHarnesses` defaults to `[ "codex" ]`. A real override disables that package's projection:

```nix
review.override { enableHarnesses = [ ]; }
```

This does not change its business payload identity or disable its separately declared dependency packages. If the same payload appears through several roots, harness selections are unioned. Unknown harness names fail.

A named upstream MCP module supports its real package/argument override interface:

```nix
review.override {
  mcpOverrides = { lib, ... }: {
    programs.fetch.package = myFixedFetchPackage;
    programs.fetch.args = lib.mkForce [ "--user-agent=MyWorkflow" ];
  };
}
```

When a producer wraps `mkAgentPackage` in its own `callPackage` function, expose any override arguments in that function as well. Custom servers use `mcp.settings.servers.<name>`, including a fixed store executable such as `"${myServer}/bin/server"`.

Different payloads with the same package ID fail. Different packages exporting the same skill name, agent name, or MCP key also fail, even if the definitions happen to match. There is no last-wins merging or version resolver. Dependency cycles report their path.

## Project files and ownership

`agent-env apply --project PATH` creates only selected resources:

- `.agents/skills/<name>/`: complete ordinary files
- `.codex/agents/<name>.toml`: native `name`, `description`, and `developer_instructions`
- Selected `mcp_servers.<name>` tables in `.codex/config.toml`
- `.agent-env-nix/`: deployment-name inventory, MCP state, lock, temporary staging, and Nix GC roots; add this directory to your project's `.gitignore`

Upstream `rsync --delete` runs only in a fresh private staging directory. It never owns the project's whole `.agents/skills` directory. Selected installer-owned skill trees are generated artifacts and replaced wholesale, including any direct edits. Change the producer repository instead. Unrelated sibling skills are untouched.

Every selected skill tree and native agent file is replaced unconditionally, including preexisting same-name content and direct edits. Only those exact leaf paths are replaced; unrelated siblings and the containing skill/agent directories remain untouched. Selection changes and remove clean up only previously recorded export names. A selected leaf symlink is removed without following it; existing directory symlinks in `.agents`, `.agents/skills`, `.codex`, and `.codex/agents` are followed and preserved, including targets outside the project. Dangling links and links to non-directories fail without replacing the link. State/lock paths and `config.toml` itself still cannot be symlinks. The installer does not coordinate different projects sharing one target directory. After manually changing directory links, use the cached activator’s `--force` option (its success cache does not inspect installed content).

MCP configuration has a different policy: existing equal unowned definitions are reused without taking ownership; conflicting unowned definitions fail. Previously generated MCP entries are changed or removed only when their current value is still a recorded generated value. User edits to those entries are preserved and reported.

Nix generates standard shell copy commands for producer payloads and project skill/agent files. Python is used only for the MCP/TOML configuration helper. TOMLKit changes selected MCP tables; model/provider/permissions and unknown unrelated keys remain intact. The whole parsed config snapshot is checked immediately before a temporary file replaces config.toml, so observed concurrent unrelated edits abort rather than being overwritten.

There is no cross-file journal, rollback or whole-project atomicity. An interruption can leave selected files partially updated or temporarily missing. The command reports failure; fix the error and rerun to copy the selected resources again. A small deployment-name inventory and necessary roots remain for retry/remove. MCP-only generated-value bookkeeping preserves configuration ownership across an interrupted config write. A new launcher converts the known prior state format; an old pending journal must first be resolved with the old launcher.

## Configuration scope

For selected MCP keys, activation checks the target and ancestor project config layers, `$CODEX_HOME/config.toml` (default `$HOME/.codex/config.toml`), and `/etc/codex/config.toml`. These additional sources are read-only. Equal inherited MCP definitions avoid redundant project entries; unequal same-name MCP definitions conflict rather than being silently shadowed. Native agent files do not use this conflict scan: selected local files are replaced, without removing or interpreting parent/global agent definitions. File-only environments skip unrelated TOML discovery.

Repeat `--extra-config FILE` for other known file-based sources. Detected unsupported selected profile sources fail safely. Managed/cloud/MDM sources and later session `-c` overrides that are unavailable to this local file workflow are outside its validation guarantee. This is not a full Codex configuration engine.

MCP conversion is deliberately bounded: stdio and streamable HTTP only; no SSE. It converts the upstream generic `headers` field to native `http_headers`, removes generic `type` and transport-inapplicable empty defaults, and validates string arguments/environment values. Unsupported fields fail explicitly. Do not put secrets, `.env` contents, or literal tokens in Nix declarations: store files are readable. Use inherited environment variables and producer-owned secret-reading wrappers instead.

## Runtime lifetime

Before publishing files, activation registers the immutable environment output as an indirect Nix GC root at a stable generation-specific path inside `.agent-env-nix/roots/`. Its closure includes selected packages, fixed runtime packages, MCP configuration, the upstream staging program, and activation tools. Copied store-path strings alone are not treated as GC roots.

Registration failure aborts publication. Old roots remain until replacement completes; failed attempts and preserved/reused configuration keep their needed roots. Legacy reused content can conservatively retain old roots until its references are known to be unnecessary. The tool never runs garbage collection. If you move a project, reactivate it at the new location before removing old root links. Manual deletion of its state/root directory is outside managed retention.

## Development

The commands below target an Apple Silicon Mac; they have not been executed for this revision.

```sh
nix develop
nix build .#checks.aarch64-darwin.runtime-unit .#checks.aarch64-darwin.upstream-copy
```

Tests are local fixtures. They do not migrate consumer repositories, call live MCP services, use credentials, or invoke an AI model. See [requirements](docs/requirements.md), [implementation plan](plan/implementation.md), and [validation](docs/validation.md).

## License

[MIT](LICENSE). Upstream dependencies retain their own licenses; see [third-party notices](THIRD_PARTY_NOTICES.md).



### Activation-time HTTP port

A producer may declare one environment variable name per HTTP MCP server, separately
from its native MCP settings:

```nix
mkAgentPackage {
  # Other package declarations are unchanged.
  mcp.settings.servers.personal-knowledge.url = "http://127.0.0.1:9090/mcp";
  mcpPortEnv.personal-knowledge = "KNOWLEDGE_MCP_PORT";
}
```

The consumer sets the variable in its own `flake.nix` devShell, for example
`KNOWLEDGE_MCP_PORT = "9100";`, before invoking the normal cached activator in
`shellHook`. No port argument is passed through consumer/package factories.
The shared activator resolves it during prepare and writes a literal URL into
`.codex/config.toml`; Codex does not interpolate the variable. The variable only
selects the configured endpoint: the service must separately listen on that port.

An unset variable keeps the declared URL. A set value must contain 1–5 ASCII decimal
digits representing 1..65535; empty or invalid values fail activation. Only the URL
port changes, retaining the host, path, query and fragment. Mapped defaults must
be HTTP(S) URLs with a hostname, no userinfo, and a valid explicit port if present.
Unmapped servers retain their existing behavior. Existing MCP ownership, equal
unowned reuse, conflict and user-edit protections still apply to the resolved URL.

Cached activation includes a hash of the effective MCP configuration, so changing
the port invalidates the cache without rebuilding the package. Equivalent ports
(e.g. `09090` and `9090`) share a cache key. Commit uses the prepared values, not a
second environment read. The cache still does not inspect installed files; after
manual configuration or directory-link edits, use `--force`. The internal
`agent-env cache-key` command reads only producer configuration, not project config,
and does not create project state.


## Optional DSH workspace MCP output

`mkProject { inherit pkgs; roots = [ /* existing producer packages */ ]; dshMcp = true; }`
adds `.dsh/mcp.json` for [lihuabd/dsh-workspace-mcp](https://github.com/lihuabd/dsh-workspace-mcp).
The default is `false`: Codex activation stays enabled and unchanged. This is an
additional MCP projection, **not full DSH native-agent or harness support**;
leave producer `enableHarnesses` at its existing Codex setting. No producer MCP
definitions need to be copied or changed. Use the usual generated `agent-env
apply --project ...` (or existing devShell activation) to write both outputs.

The projection uses the same selected MCP owners and resolves `mcpPortEnv` once
at activation, so both files contain the same concrete HTTP URL/port. For example:

```json
{"mcpServers":{"knowledge":{"type":"http","url":"http://127.0.0.1:9090/mcp"}}}
```

Install/enable the workspace MCP plugin in your own DSH profile separately. The
supported contract here is plugin commit
`4c7996f3306f198179fe500b8d607716ac1d0da8`, default project search paths and
`searchParents: false`. The plugin reads configuration when creating a session;
start a new DSH session after activation changes. Its mounted server namespace
normalizes punctuation/long names; the generated JSON retains the producer keys.

- HTTP `url` and static headers become `type: "http"`, `url`, `headers`.
- Named `env_http_headers` and `bearer_token_env_var` become `${VAR}` / `Bearer ${VAR}`
  references. Stdio `env_vars` similarly become environment references. Activation
  does not read these secret values. Allow the required variable names in the
  plugin profile's `envAllowlist` (or provide profile `env`) and supply values to
  the DSH process. No credential or profile setup is performed by Nix activation.
- Stdio fixed `command`, `args` and explicit `env` are preserved. `cwd` is made
  absolute against the activated project, including the default project cwd,
  because the plugin otherwise interprets it relative to `.dsh/`.
- `enabled = false` becomes `disabled: true`; `tool_timeout_sec` becomes positive
  whole `toolCallTimeoutMs`. Codex `required` and startup timeouts remain Codex-only
  settings: DSH uses its own profile startup/failure policy.
- Codex tool allowlists (including an explicit empty list) and nonempty deny lists cannot be preserved by this plugin and
  cause preflight failure rather than silently expose additional tools. Literal
  `${...}` in fields the plugin expands is also rejected; use the named environment
  fields for intentional references. Conflicting header/environment sources and
  nonrepresentable tool timeouts fail without printing their values.

Existing `.dsh/mcp.json` unrelated keys/servers are preserved. Unequal same-name
or manually edited managed definitions cause a conflict; equal unowned definitions
are reused without claiming ownership. Creating `.dsh/mcp.json` when a project
`.mcp.json` already exists is refused, because the plugin would otherwise silently
hide that fallback. Reconcile existing configuration explicitly first; activation
never deletes or edits `.mcp.json`. Custom plugin search paths/parent lookup and
global profile precedence remain user configuration, not inferred by the exporter.

Turning the option off or running `remove` removes only unchanged owned DSH entries.
It does not remove unrelated entries, the directory, or equivalent unowned entries.
Empty JSON containers may remain. Codex and DSH files are individually atomic,
not a multi-file transaction; a new activation safely reconciles interrupted writes
using the existing generated-value ownership bookkeeping and project lock.
