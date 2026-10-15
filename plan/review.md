# Current implementation plan review

Review date: 2026-10-15 UTC.
Scope: independent initial plan review, followed by correction-only re-review of M1/M2 and their direct impacts. No implementation tests or remote writes were performed.

Plan revision: v0.5, `plan/implementation.md`, SHA256 `697ee43beb6fe9ba6502166992375ed955e321f9aae8e8aa94703d603cddb515`.
Requirement revision: R2. The user's generated-skill clarification supersedes installed-skill edit protection; the later request to reuse existing config-update facilities is satisfied by retaining upstream generation plus TOMLKit and a narrow project ownership/update layer.
Target repository revision: `RekiDunois/agent-env-nix@28f11d8f23ca0e2494b960074dcb0c765385d85f`; MIT LICENSE blob `6dab5e0f3d6834389faa196d426e461578332209` remains the preserved baseline.
Relevant upstream/runtime revision:
- Skills: `2948865044b2af55c8c4e4eb2abda7de79d60f0e`.
- MCP: `31848978eefbca17f1658a55066b1d2aaa43cafc`.
- Codex native contract: `6fbd7be1518d259e30e6fef48f05f433d2461a20`; schema blob `7c6da97d0f0a2638ac3c41a96b8bc5e6a4674651`; transport validator blob `c85e7c99b85f8e0b9bcf2a43d8de0c2a986699bd`.
- Proposed nixpkgs: `6510408d147d8c5e6d76043e899e9251756f6a75`.
- Nix 2.35.3 is available in the execution environment; Nix 2.34.9 documentation supplies the cited fixed-root-location semantics. No runtime/build test result is inferred.

## Decision-affecting facts and correction impact

The seven decision-to-source mappings in the historical v0.3 record below remain applicable. The following corrections close its two blockers:

- M1: §4 now explicitly initializes `settings.servers = {}`, evaluates the pinned upstream, validates a bounded supported record surface, normalizes generic fields into Codex-native names, removes transport-inapplicable empty fields, and rejects incompatible nonempty fields before generation. This is grounded in both the pinned [Codex schema](https://github.com/openai/codex/blob/6fbd7be1518d259e30e6fef48f05f433d2461a20/codex-rs/core/config.schema.json) and [TryFrom<RawMcpServerConfig> transport validator](https://github.com/openai/codex/blob/6fbd7be1518d259e30e6fef48f05f433d2461a20/codex-rs/config/src/mcp_types.rs). The latter rejects incompatible fields based on presence even when empty: HTTP output therefore omits args/env/env_vars/cwd, and stdio output omits http_headers/env_http_headers. Native generation still reuses upstream `mkConfig`; this does not create a second MCP implementation.
- M2: §6 now guards the complete bytes/existence snapshot used to render config.toml, including on removal. A detected unrelated edit, comment change, creation, or deletion aborts that write; retry reads and renders the current full document. Selected-key ownership remains separate from this whole-file publication guard. The limitation to optimistic checking, rather than a transaction against arbitrary external writers, is explicit.
- The platform-source clarification is supported by pinned [loader/mod.rs](https://github.com/openai/codex/blob/6fbd7be1518d259e30e6fef48f05f433d2461a20/codex-rs/config/src/loader/mod.rs): both intended Unix platforms use /etc/codex/config.toml. No new Darwin execution claim is made.
- Existing config update alternatives were checked by the parallel source investigation. At Codex `3bae578af33e43268e7bc2d6d5d0266f704bb554`, [CLI MCP add/remove](https://github.com/openai/codex/blob/3bae578af33e43268e7bc2d6d5d0266f704bb554/codex-rs/cli/src/mcp_cmd.rs) acts on user/CODEX_HOME configuration; [app-server config writes](https://github.com/openai/codex/blob/3bae578af33e43268e7bc2d6d5d0266f704bb554/codex-rs/app-server/src/config_manager_service.rs) reject non-user config targets. [TOMLKit](https://github.com/python-poetry/tomlkit) supplies preserving structured editing and is already used by the pinned upstream's [format library](https://github.com/natsukium/mcp-servers-nix/blob/31848978eefbca17f1658a55066b1d2aaa43cafc/lib/formats.nix). Retaining it with a thin project-specific policy closes the reuse question without changing the approved owner or adding a parser framework.

The v0.4-to-v0.5 transport clarification finishes M1; it is not an additional blocker or test expansion. An early conversational v0.4 approval preceded that final transport-presence source check and is superseded by this exact-hash formal record. No formal v0.4 approval was issued.

## Gate decisions

P1 Requirement & Reality Grounding: PASS
P2 Solution Validity & Ownership: PASS
P3 Impact, Safety & Counterexample: PASS
P4 Executability: PASS
Gate review completeness: COMPLETE

- P1: User authority, target baseline, upstream APIs, native schema, transport constraints, and GC-root behavior are mapped to exact sources. There is no remaining decision-affecting unverified assumption.
- P2: The producer-owned package graph, upstream private copy staging, narrow Codex adapter, selected-key merge, and rooted runtime closure form a complete causal path. Both corrections remain in the shared integration owner.
- P3: The design preserves unrelated skills/settings and unowned equal definitions, protects owned native-agent/config edits, intentionally replaces owned generated skills, and prevents the identified stale-document loss. Native transport output and retained-root lifecycle are covered by the frozen design.
- P4: Interfaces, ownership, change points, order, conflict behavior, partial-failure handling, cleanup, intended platforms, and bounded native compatibility are sufficiently specified. Core decisions are not deferred to implementation.

Critical assumptions: N/A.
Unresolved impacts: N/A blocking or critical. Nix lock/build execution, actual Codex runtime validation, and Darwin execution remain unverified deliverable status, not claimed successes.
Approved behavior changes: The new explicitly invoked shared Nix-to-Codex workflow; source-authoritative replacement/removal of owned generated skill trees, per the user's explicit later instruction.
Reused prior Plan Gate PASS: No prior whole-gate PASS existed. The completed v0.3 review's unaffected decisions are reused across P1–P4: target/license, scope/ownership, package graph and harness normalization, resource materialization, native-agent identity, unowned reuse, path safety, GC-root retention, alternatives, and implementation sequence. v0.4/v0.5 touch only M1/M2 and directly related source/compatibility details.
Required modifications: N/A. M1 and M2 are closed.
Missing evidence for PARTIAL review: N/A.

Plan conclusion: APPROVED

## Implementation handoff and authority boundary

Implement the exact v0.5 candidate above. Producers retain business-file, dependency, wrapper, and native-agent semantics; the shared library owns graph composition, Codex projection, selected-key policy, and project lifecycle. Keep LICENSE unchanged. Preserve unrelated project/global configuration, existing producer installation paths, secrets, and external services. Do not migrate consumers or implement additional harnesses under this plan.

Normative authority remains the user-approved behaviors and the pinned Codex/native interfaces. State layout, helper names, manifest representation, private staging, and journals are internal design choices; plan approval does not promote them into independent product requirements.

The resolved manifest, actual copied resources, selected MCP entries, conflict diagnostics, owned/reused state, and GC roots are the intended observable surfaces. This review adds no test matrix, parser, evidence collector, runtime certification, or downstream business smoke requirement. APPROVED means suitable to implement; it does not mean implementation correct, tests passed, or ready to merge.

---

# Historical initial review of v0.3 (superseded)



Review date: 2026-10-15 UTC.
Reviewer scope: independent static review of the complete initial shared-library plan; no implementation tests, remote comments, or remote writes were performed.

Plan revision: v0.3, `plan/implementation.md`, SHA256 `4c079e2f0148a5b3e63239a0cc2525ae6e7707ece22bdb8037d3d3d305f8fd2d`.
Requirement revision: R2, recorded in the plan and `initial-requirements-issue.md`; includes the user's later explicit instruction that installed owned skill trees are generated and should be replaced from their producer.
Target repository revision: `RekiDunois/agent-env-nix@28f11d8f23ca0e2494b960074dcb0c765385d85f`; the independently inspected tree contains only MIT LICENSE, blob `6dab5e0f3d6834389faa196d426e461578332209`.
Relevant upstream/runtime revision:
- `Kyure-A/agent-skills-nix@2948865044b2af55c8c4e4eb2abda7de79d60f0e`.
- `natsukium/mcp-servers-nix@31848978eefbca17f1658a55066b1d2aaa43cafc`.
- `openai/codex@6fbd7be1518d259e30e6fef48f05f433d2461a20`; config schema blob `7c6da97d0f0a2638ac3c41a96b8bc5e6a4674651`.
- Proposed nixpkgs `6510408d147d8c5e6d76043e899e9251756f6a75`.
- Nix reference manual 2.34.9 for GC-root semantics. The parent reports Nix 2.35.3 is now installed in the execution environment; no Nix build or runtime validation result is inferred from that report.

## Decision-affecting facts

1. Separate shared owner, producer-owned declarations, recursive agent dependencies, actual copied project resources, Codex-first package harness selection, and preservation of existing configuration derive from the user-approved scope. The subsequent instruction “.agents/skills里不应该直接改动。直接替换repo里的东西是正确做法” supersedes earlier proposed edit guards for owned generated skill contents only. Native-agent/config protection and unrelated skill ownership remain unchanged.

2. Reusing upstream copy materialization only in private staging is supported by [skills targets.nix](https://github.com/Kyure-A/agent-skills-nix/blob/2948865044b2af55c8c4e4eb2abda7de79d60f0e/lib/targets.nix) and [sync.sh](https://github.com/Kyure-A/agent-skills-nix/blob/2948865044b2af55c8c4e4eb2abda7de79d60f0e/scripts/sync.sh). `mkSyncProgram` exposes local mode, explicit targets and disabled destination overrides; copy-tree invokes recursive copying with deletion and link materialization. Applying that primitive to the shared real skill parent would delete unrelated skills, whereas the proposed private staging plus selected-root publication avoids that error.

3. Reusing MCP evaluation/generation rather than its project symlink installation is supported by [MCP lib/default.nix](https://github.com/natsukium/mcp-servers-nix/blob/31848978eefbca17f1658a55066b1d2aaa43cafc/lib/default.nix), [servers/config.nix](https://github.com/natsukium/mcp-servers-nix/blob/31848978eefbca17f1658a55066b1d2aaa43cafc/modules/servers/config.nix), and [flake-parts.nix](https://github.com/natsukium/mcp-servers-nix/blob/31848978eefbca17f1658a55066b1d2aaa43cafc/modules/flake-parts.nix). The generated Codex flavor renames the top-level server table but otherwise passes generic server records through. Its named modules emit `headers`, optionally `type`, and allow boolean/integer arguments and environment values.

4. Those generic records are not already valid for the pinned Codex runtime contract. [RawMcpServerConfig in config.schema.json](https://github.com/openai/codex/blob/6fbd7be1518d259e30e6fef48f05f433d2461a20/codex-rs/core/config.schema.json) disallows additional properties, supports `http_headers`/`env_http_headers`, has no generic `headers` or `type` field, and requires string `args` items and `env` values. This directly affects the proposed adapter boundary, not merely optional validation.

5. Standalone native-agent output and name-based collision checks are supported by the pinned [agent loader](https://github.com/openai/codex/blob/6fbd7be1518d259e30e6fef48f05f433d2461a20/codex-rs/agent-roles/src/loader.rs) and [official native-agent documentation](https://learn.chatgpt.com/docs/agent-configuration/subagents). The loader reads both declared roles and discovered agent files, and role identity is not inferred only from filenames.

6. Read-only config-source inspection and an explicitly bounded file-based compatibility guarantee are consistent with the pinned [loader README](https://github.com/openai/codex/blob/6fbd7be1518d259e30e6fef48f05f433d2461a20/codex-rs/config/src/loader/README.md). The exact Unix system-file path, covering both intended platforms, is `/etc/codex/config.toml` in [loader/mod.rs](https://github.com/openai/codex/blob/6fbd7be1518d259e30e6fef48f05f433d2461a20/codex-rs/config/src/loader/mod.rs). Managed/profile/session sources are distinct from that file-based scope; no complete effective-runtime validation is claimed.

7. Fixed generation-root locations and retained old roots are supported by the [Nix 2.34.9 realisation/root documentation](https://nix.dev/manual/nix/2.34/command-ref/nix-store/realise.html). Registered indirect roots cannot be renamed as if registration followed the new path. Merely copying a store path into project text does not retain the store closure.

## Gate decisions

P1 Requirement & Reality Grounding: NEEDS_MODIFICATION
P2 Solution Validity & Ownership: NEEDS_MODIFICATION
P3 Impact, Safety & Counterexample: NEEDS_MODIFICATION
P4 Executability: NEEDS_MODIFICATION
Gate review completeness: COMPLETE

P1–P2 are blocked by the direct, unnormalized generic MCP-to-Codex transfer in §4. P3 is blocked by that invalid native configuration and the stale full-document write described below. P4 requires the missing native adaptation and full-document concurrency failure strategy to be frozen rather than left for the implementer to decide.

All other independently decidable parts were reviewed: the license-only baseline, bounded repository scope, producer/library ownership, dependency versus runtime separation, repeated payload/harness normalization, complete copied resource trees, generated-skill supersession, unowned reuse, declared native-agent identity, selected-key updates/removal, path boundaries, fixed roots, partial-failure retention, alternatives, implementation order, and non-expansion of tests. No additional blocker was found in that reviewed scope.

Critical assumptions: The assumption that the upstream Codex flavor already emits the pinned Codex native record schema is contradicted by the inspected sources; close it through required modification M1.
Unresolved impacts: M1 can make ordinary named-MCP output unreadable by Codex; M2 can lose unrelated user configuration. Both are critical and blocking.
Approved behavior changes: New explicitly invoked shared Nix-to-Codex activation, and full replacement/removal of owned generated skill trees per the user's later instruction. Existing unrelated configuration, unrelated skill roots, and existing producer installation routes remain preserved.
Reused prior Plan Gate PASS: N/A. This is the first complete gate review; v0.1–v0.2 were not formally approved.

## Required modifications

### M1 — Freeze the actual Codex MCP record adapter

Gates: P1, P2, P3, P4.
Location: §4, with corresponding source and handoff descriptions.
Owner: plan owner; implementation remains owned by this shared library.

Problem: The proposed `evalModule → config.settings.servers → mkConfig` path retains generic upstream fields. For example, even a simple enabled named stdio program emits `headers = {}`, which is absent from the pinned Codex supported-field schema. An explicit transport can also emit `type`; argument/environment types are broader upstream than Codex accepts. A configuration labeled flavor=codex is therefore not enough to establish native compatibility.

Minimum change: Define a narrow normalization/validation step at this adapter boundary, grounded in the pinned Codex schema and relevant transport contract. Freeze how generic headers/transport fields are mapped, removed, or rejected, and how unsupported values and incompatible types fail before project mutation. Preserve already-supported Codex custom fields rather than inventing another MCP implementation. Make the empty `settings.servers = {}` base explicit so skill-only packages and empty selections do not depend on an unstated absent-attribute behavior. No new test matrix or general schema framework is requested.

### M2 — Prevent stale full-file config replacement

Gates: P3, P4.
Location: §5 selected-key preservation and §6 concurrency/write strategy.
Owner: plan owner and activation owner.

Problem: The plan renders a complete TOML document but says to recheck only selected content immediately before replacing it. If an editor changes an unrelated setting after the initial read, the selected MCP keys can remain unchanged while the stale rendered document overwrites that new unrelated setting. The per-project installer lock does not protect against an arbitrary editor, as the plan itself acknowledges.

Minimum change: Guard the whole config-file snapshot from which the replacement was rendered, or re-read/re-render from the newly observed full document while preserving unrelated changes and rejecting conflicting modifications. Define detected-change failure/retry behavior without forcing rollback over user content. This is a safety condition on one shared-file write, not a request for all-project transactions, a new collector, or additional test obligations.

Missing evidence for PARTIAL review: N/A.

Plan conclusion: NEEDS_MODIFICATION

## Revision handling and handoff

After both corrections are merged into one canonical revision, re-review only M1, M2, and their direct effects on native compatibility, preservation, and failure/lifecycle behavior. Other reviewed decisions remain reusable unless the candidate introduces an actual semantic change.

Plan approval, once obtained, will mean the design is suitable to implement. It will not establish correct implementation, passing tests, a verified Codex binary version, Darwin execution, or merge readiness. Product contracts derive from the user and pinned native interfaces; the selected state format, helper boundaries, and journals remain internal design.

