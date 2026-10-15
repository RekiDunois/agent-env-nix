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
nix flake check
nix build .#example
mkdir -p /absolute/path/to/example-project
./result/bin/agent-env apply --project /absolute/path/to/example-project
./result/bin/agent-env remove --project /absolute/path/to/example-project
```

The example combines two root packages with a shared dependency. It copies a complete skill (including a script and hidden support file), installs a native example agent, and registers a fixed-path fetch MCP server configuration. Activation does not start that server or a Codex session. The project must already be trusted by Codex; this tool does not change trust.

Initial output systems are `x86_64-linux` and `aarch64-darwin`. See [validation](docs/validation.md) for the exact checks performed and remaining limits.

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

Every selected skill tree and native agent file is replaced unconditionally, including preexisting same-name content and direct edits. Only those exact leaf paths are replaced; unrelated siblings and the containing skill/agent directories remain untouched. Selection changes and remove clean up only previously recorded export names. A selected leaf symlink is removed without following it; symlinked parent directories are rejected.

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

```sh
nix develop
nix build .#checks.x86_64-linux.runtime-unit .#checks.x86_64-linux.upstream-copy
nix flake check
```

Tests are local fixtures. They do not migrate consumer repositories, call live MCP services, use credentials, or invoke an AI model. See [requirements](docs/requirements.md), [implementation plan](plan/implementation.md), and [validation](docs/validation.md).

## License

[MIT](LICENSE). Upstream dependencies retain their own licenses; see [third-party notices](THIRD_PARTY_NOTICES.md).

