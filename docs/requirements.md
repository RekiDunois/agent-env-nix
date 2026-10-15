# Build the initial shared Codex agent environment

## Purpose and requirements, R2

The user approved a separate private RekiDunois/agent-env-nix repository to combine agent-skills-nix and mcp-servers-nix with the missing shared behavior, and asked for its code to be prepared. The user created the repository with an MIT LICENSE.

- Producers declare their own complete files, skills, native agents, MCP definitions, direct agent-package dependencies, and fixed runtime dependencies.
- A consumer selects multiple roots. Explicit agent dependencies expand recursively; ordinary runtime dependencies do not become deployed agent packages.
- Package enableHarnesses defaults to [ "codex" ] through callPackage/.override. The first implementation supports only Codex.
- Copy complete regular-file skill trees into the real project's .agents/skills and native agent TOML into .codex/agents, without deployed resource-root symlinks.
- Installed owned skill trees are generated artifacts. Changes belong in their producer repositories; updates replace the selected generated trees as a whole. Preserve unrelated sibling skills.
- Merge only selected MCP keys in .codex/config.toml, preserving unrelated/unknown settings. Detect selected-name conflicts in checked project/parent/global sources; do not silently shadow unequal definitions.
- Reuse equal unowned definitions without ownership. Preserve user edits to owned native-agent/config objects on update/removal.
- Use fixed Nix runtime paths and actual GC roots. Secrets stay outside Nix store declarations.
- Reuse pinned upstream code as dependencies. No real consumer migration, producer business fix, general registry/framework, or additional harness implementation.

Intended platforms are aarch64-darwin and x86_64-linux where selected dependencies support them. Current execution/validation status must be reported separately.

## Canonical implementation plan

The canonical implementation plan is [plan/implementation.md](../plan/implementation.md), approved revision v0.5, SHA256 `697ee43beb6fe9ba6502166992375ed955e321f9aae8e8aa94703d603cddb515`. The [independent plan review](../plan/review.md) records P1–P4 PASS and COMPLETE. Implementation validation is reported separately in [validation.md](validation.md); plan approval alone is not test or merge approval.

The plan records exact upstream revisions, the concrete MCP package/argument override path, agent-versus-runtime dependency semantics, same-payload harness normalization, generated-tree ownership, and selected-key configuration lifecycle. Implementation and testing must remain within this scope and the project rules.

