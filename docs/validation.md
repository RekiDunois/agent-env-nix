# Validation: initial two-package implementation

Validated on 2026-10-15 in the cloud Linux workspace. The repository's original LICENSE is unchanged: Git blob `6dab5e0f3d6834389faa196d426e461578332209`.

## Scope

The user approved two small examples, not a migration or a business regression suite:

1. `example-base`: complete skill directory, hidden support file, executable script, native Codex agent, and a fixed runtime dependency.
2. `example-tools`: explicit dependency on `example-base`, a real upstream fetch MCP module, and a real module-argument override.

The integration selects both roots, so the shared package is deployed once. It does not start the MCP service, contact a live API, use credentials, invoke an AI model, or touch a real consumer repository.

## Passed checks

- A real `flake.lock` was generated with Nix for the three exact input revisions. Both upstream nixpkgs inputs follow the shared pinned nixpkgs input.
- Nix parsing and graph/config evaluation succeeded. Existing evaluation assertions cover package overrides and callPackage, same-payload harness union, recursive/diamond dependencies, cycle and collision failures, disabled projection, and the bounded native MCP normalization.
- `nix flake check` passed on `x86_64-linux`, including genuine upstream copy-tree/config generation and the packaged Python test suite.
- All 54 authored Python unit checks passed both locally and inside the Nix check derivation: 46 activation checks and 8 payload-materialization checks. The activation unit tests use explicit fake external executables for lifecycle fault injection; the integration below uses the real Nix/upstream executables.
- `nix flake check --no-build --all-systems` passed evaluation for `x86_64-linux` and `aarch64-darwin`. This is **not** a Darwin build or runtime pass.
- `nix build .#example` built the real two-package environment, including the upstream fetch package and fixed native MCP configuration.
- The built launcher passed an isolated project apply → repeat apply → remove check. It verified complete regular-file skill copying, executable/hidden support files, native agent TOML, fixed MCP executable, preservation of unrelated comments/settings/MCP entries and a sibling skill, wholesale replacement of an edited owned generated skill, and safe removal.
- Actual `nix-store --query --roots` showed the environment registered at its generation-specific project root. Removal released that owned root. No garbage-collection deletion was run.

The final integrated environment output was `/nix/store/yc65qkm7xka0b1vqbg0i46jifb1j4i4z-agent-environment`. The final reviewed activation source SHA256 is `0f38ddaf696240096cf87473daa200ae6e8b93132779f748d1ba8c01d4c21487`.

## Reproduction

Ordinary checkout commands:

```sh
nix flake lock
nix flake check
nix flake check --no-build --all-systems
nix develop --command python -m unittest discover -s tests -p 'test_*.py' -v
out=$(nix build .#example --no-link --print-out-paths)
bash tests/integration.sh "$out"
```

The cloud run used Nix 2.35.3 through a task-local namespace wrapper, with the equivalent explicit flake reference `path:/workspace/shared/agent-env-nix`. That wrapper only supplies the local `/nix` mapping; the built application and tests are the repository code. The local Python pass used Python 3.12 and TOMLKit 0.13.3; the pinned Nix runtime pass used Python 3.14.7 and TOMLKit 0.15.0.

The integration script creates a temporary fixture, redirects HOME and CODEX_HOME to it, and retains the fixture path for inspection. It runs no service or model. Its generated environment root is removed at the end of a successful run.

## Corrections verified

A real first build caught a source-path context bug; it was fixed with context-preserving Nix interpolation and rebuilt successfully. Independent code review identified six bounded defects in config snapshot pairing, native-agent discovery/equality, untouched-attempt retry, reused-skill root retention, blank native metadata, and MCP path traversal. Those fixes were re-reviewed; all six findings were closed. The final unit/build/integration results above are after those corrections.

## Limits

- No macOS machine was used. Darwin outputs were evaluated only.
- No installed Codex binary/session was exercised. Native compatibility is grounded in the pinned Codex source contract in the implementation plan, with generated TOML checked locally.
- No real workflow repositories or downstream business behavior were tested.
- File-based config checks cannot validate unavailable managed/cloud/MDM sources or later session overrides. The README states that boundary.
- File publication uses atomic rename; skill replacement is journaled across an old-tree backup and a new-tree rename. This is not a whole-project transaction.
