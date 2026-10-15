# Build the initial shared Codex agent environment

## Purpose and requirements, R3

The user approved a separate private RekiDunois/agent-env-nix repository to combine agent-skills-nix and mcp-servers-nix with the missing shared behavior, and asked for its code to be prepared. The user created the repository with an MIT LICENSE.

- Producers declare their own complete files, skills, native agents, MCP definitions, direct agent-package dependencies, and fixed runtime dependencies.
- A consumer selects multiple roots. Explicit agent dependencies expand recursively; ordinary runtime dependencies do not become deployed agent packages.
- Package enableHarnesses defaults to [ "codex" ] through callPackage/.override. The first implementation supports only Codex.
- Copy complete regular-file skill trees into the real project's .agents/skills and native agent TOML into .codex/agents, without deployed resource-root symlinks.
- Selected skill trees and native agent files are unconditionally replaced as complete leaves, including existing same-name resources and direct edits. Preserve unrelated siblings and containing roots. Nix generates standard shell copy commands in both build and activation phases; Python is only for MCP configuration.
- Merge only selected MCP keys in .codex/config.toml, preserving unrelated/unknown settings. Detect selected-name conflicts in checked project/parent/global sources; do not silently shadow unequal definitions.
- Reuse equal unowned MCP definitions without ownership and preserve edits to generated MCP values. Skill/agent files have no content ownership or edit-protection gate. Keep only selected-name cleanup scope for revoked exports and removal. No cross-file recovery journal; partial failure is reported and fixed by rerunning, while config uses a guarded single-file replacement.
- Use fixed Nix runtime paths and actual GC roots. Secrets stay outside Nix store declarations.
- Reuse pinned upstream code as dependencies. No real consumer migration, producer business fix, general registry/framework, or additional harness implementation.

First-round support and acceptance target only aarch64-darwin, per the user clarification on 2026-10-15. Linux support/builds are not delivery or test gates; existing platform code remains unchanged. Historical Linux results are supplementary evidence. On 2026-10-16 the authorized Apple Silicon Mac run passed the approved T1–T4 checks (runtime-unit 38/38, upstream-copy, example build and two-example integration); third-gate result review is PASS for that scoped Darwin evidence. See [validation](validation.md) and [test review](../plan/test-review.md). This is not a merge approval.

## Canonical implementation plan

The canonical implementation plan is [plan/implementation.md](../plan/implementation.md), revision v0.6-candidate; [independent review](../plan/review.md) approves its R3 design. The exact latest user clarification and approval are recorded in that plan. [Test plan](../plan/test-plan.md) covers only affected existing offline checks and the same two examples; formal eval is outside this change. Plan approval is not an implementation, test or merge verdict.
