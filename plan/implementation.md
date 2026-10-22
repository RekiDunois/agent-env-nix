# agent-env-nix: narrow shell activation

Directory-parent link behavior is revised by the current [directory symlink plan](directory-symlinks.md), following the user decision of 2026-10-22. Other historical design and result records are unchanged.

- Plan revision: v0.6 with Darwin-only scope addendum (2026-10-15). The original design approval remains valid for unchanged behavior; the platform-scope adjustment passed independent targeted review on 2026-10-15.
- Requirement revision: R3. User messages Sentinel_7d746093b3ec81919129b980200cf634 and Sentinel_440c4ba567d88191817540ed750bfa57 approve unconditional skill/agent replacement, Python only for config, and dropping cross-file recovery in favor of reporting failure and rerunning.
- Target baseline: RekiDunois/agent-env-nix main 3b08c9e652dd8df5f3c1686347ef671476022335. Do not include unmerged PR #2 or modify the six producer repositories.
- This complete candidate replaces v0.5 for implementation. It claims no approval, execution result, or merge readiness. First-round support and acceptance target only aarch64-darwin. Linux support/builds are not delivery or test gates. Existing Linux platform code is retained without a support promise. Darwin execution remains not run; historical Linux results are auxiliary only.

## 1. Authority and scope

The user explicitly said: “首先，skill和agent文件应该无条件替换，它没有什么要保留的东西。我最多能接受配置文件用python脚本来做，单纯把skill放到指定路径，不应该用python”. After the explanation that files would report failure and be fully copied again while config uses a temporary file and replacement, the user approved: “可以，你就按这个改”.

The approved behavior change applies to the selected project's skill roots and native agent files. Replace their entire contents regardless of matching existing content, prior ownership, or local edits. Do not clear the common skills/agents directories or unrelated sibling exports. Python is limited to selected MCP/TOML configuration handling; neither payload materialization nor project copying is implemented in Python. Drop cross-file recovery/backup journals and report partial failure for an explicit rerun.

Preserve complete ordinary-file copies, producer-declared content and runtime dependencies, mkAgentPackage/mkProject interfaces, selected MCP configuration protection, fixed Nix runtime paths and necessary GC retention, and the existing narrow stale-export/remove lifecycle. No business-producer changes, formal eval, model/service calls, credentials, global config writes, trust changes, installations, input updates, registry, downloader, resolver, or new general-purpose copying framework.

Rules: [Project Consensus](https://app.notion.com/p/3d60101a85f3815a8c43f271f2b4d91d), [Plan Reviewer Rule](https://app.notion.com/p/3e80101a85f3817a94cbc6eca1a76a5c), [Test Engineer Rule](https://app.notion.com/p/3d80101a85f380d8a8f5ce528141e253). Test scope and steps live in test-plan.md; no implementation approval is a test PASS.

## 2. Decisions and exact evidence

Repository links below use the baseline SHA above:

- Keep Nix API/graph and change only implementation owner → lib/default.nix already exports makeOverridable mkAgentPackage/mkProject; lib/package.nix builds a derivation and lib/project.nix resolves explicit agent dependencies and produces the executable → [library](https://github.com/RekiDunois/agent-env-nix/tree/3b08c9e652dd8df5f3c1686347ef671476022335/lib).
- Remove Python file copying in both phases → package.nix invokes runtime/materialize.py; project.nix wraps runtime/activate.py, whose writable_copy/preflight/publish manage file ownership and journals → [build copying](https://github.com/RekiDunois/agent-env-nix/blob/3b08c9e652dd8df5f3c1686347ef671476022335/runtime/materialize.py), [activation](https://github.com/RekiDunois/agent-env-nix/blob/3b08c9e652dd8df5f3c1686347ef671476022335/runtime/activate.py).
- Reuse upstream only in private staging → pinned agent-skills 2948865044b2af55c8c4e4eb2abda7de79d60f0e lib/targets.nix exposes mkSyncProgram; scripts/sync.sh copy-tree uses rsync -aL --delete and owns its destination as a whole → [target builder](https://github.com/Kyure-A/agent-skills-nix/blob/2948865044b2af55c8c4e4eb2abda7de79d60f0e/lib/targets.nix), [sync](https://github.com/Kyure-A/agent-skills-nix/blob/2948865044b2af55c8c4e4eb2abda7de79d60f0e/scripts/sync.sh). Preserve the existing private staging use; never point it at the shared project skills root.
- Keep MCP evaluation/generation and bounded native mapping → mcp-servers 31848978eefbca17f1658a55066b1d2aaa43cafc lib/default.nix exposes evalModule/mkConfig, while its modules/servers/config.nix generates a new TOML file rather than editing existing user TOML; current lib/mcp.nix already performs bounded transport mapping → preserve these interfaces and TOMLKit editing.
- Keep GC roots → baseline register_root calls nix-store --realise --add-root --indirect; manifests contain real runtime references. [Nix root semantics](https://nix.dev/manual/nix/2.34/command-ref/nix-store/realise.html) root the output closure; copied strings in mutable project files alone do not root it.
- Move process locking out of Python → pinned nixpkgs 6510408d147d8c5e6d76043e899e9251756f6a75 provides [pkgs.flock](https://github.com/NixOS/nixpkgs/blob/6510408d147d8c5e6d76043e899e9251756f6a75/pkgs/by-name/fl/flock/package.nix), the cross-platform flock command with platforms.all. Use it around the shell activation, not a homemade stale-PID lock scheme. Runtime execution on Darwin remains unverified.

All three flake inputs, flake.lock, licenses and notices remain unchanged. Native TOML generation keeps the baseline Codex contract (name, description, developer_instructions). No new Codex precedence claim: replacing a selected local file does not remove same-name definitions in parent/global sources or guarantee which agent a later session chooses.

## 3. Preserved producer contract

mkAgentPackage accepts pkgs, id, version, files, agentDependencies ? [], runtimePackages ? [], exports ? {}, mcp ? {}, mcpOverrides ? {}, enableHarnesses ? ["codex"]. files maps safe non-overlapping package-relative paths to full source files/trees; exports.skills maps names to payload-relative directories; exports.agents maps names to description/developer_instructions. Outputs remain payload/, codex/agents/, agent-env.json and passthru.agentEnv. Keep callPackage/.override, fixed runtime references, and actual dependency references in the output closure.

mkProject accepts pkgs, roots, name ? "agent-environment". Keep explicit agentDependencies traversal, cycle paths, conflicting same-id payload rejection, same-payload harness union, disabled projection, runtimePackages not traversed as exports, and collisions between two selected producers. Existing filesystem content no longer participates in skill/agent collision policy. Project writes still happen only by running the generated executable, never during evaluation/build.

Keep apply/remove --project PATH and --extra-config FILE for compatibility; the generated shell is an implementation of these existing commands, not another distribution CLI. Existing apps.default remains a nix run entry. No implicit shellHook is introduced.

MCP module evaluation, package/argument overrides, inter-producer MCP collision checks and lib/mcp.nix validation remain unchanged: stdio/HTTP, fixed store command, strings for args/env, headers to http_headers, no generic type in Codex output, incompatible nonempty transport fields/unsupported fields rejected. Secrets stay outside store declarations. Producers own their business instructions; no rewriting commands or editing six producer repos.

## 4. Build-time files: fixed shell copying

Replace runtime/materialize.py invocation with Nix-generated shell commands per declared files entry. Use pinned coreutils/findutils/rsync. Do not create a recursive copying implementation: enumerate source links/special objects only for validation, then copy each complete declared source with standard cp/rsync, dereferencing validated internal links. Preserve directory contents, dotfiles, empty directories and executable bits, and validate exported SKILL.md before completing the derivation.

Preserve the existing source boundary contract: reject top-level symlink source roots; reject dangling/escaping links, link cycles and special objects. Shell validation resolves each encountered link against that declared source tree, uses standard find/realpath diagnostics for traversal cycles, and fails before copying if the source is invalid. Nix generates the destination and correctly shell-quotes every source/relative path; existing overlap/path validation stays in Nix. Internal links are materialized by standard copy tools, not retained in payload trees.

Delete runtime/materialize.py once its caller and directly affected checks have moved. Native agent TOML remains generated by pkgs.formats.toml and copied by the Nix builder. No Python is invoked to place payload/skill/agent files.

## 5. Shell project activation

lib/project.nix retains manifest/config generation and upstream skillsInstaller, but produces a shell launcher. A small shell support file may hold argument/path/lifecycle handling; Nix emits the fixed copy commands and declared name lists. All executables have fixed store paths. User input selects the real project root only; it cannot supply arbitrary source paths or shell fragments.

Resolve the project; reject unsafe state components and lexical out-of-project destinations. Hold the project lock via pkgs.flock. A selected leaf symlink is removed as a link, never followed. Existing directory links in .agents, .agents/skills, .codex and .codex/agents are followed and preserved, including outside-project targets; dangling/non-directory links fail. State/lock paths and the config.toml file itself remain link-free. Check roots/names from saved state before using them; never source stored shell code. Normal non-symlink directory/file contents at a selected destination do not create a content conflict.

Under the lock:
1. Validate argument/state compatibility and destination parent paths; ask config helper to preflight only selected/previously managed MCP keys. No agent-config or global-agent discovery gate remains.
2. Stage selected skills with the pinned upstream installer in a fresh private directory, preserving its copy-tree primitive. Remove only its staging marker; do not retain old-tree backups.
3. Register the current environment GC root before any project publication. Preserve prior roots. Before mutating file exports, persist the union of old attempted file names and newly selected names as a small deployment inventory. This is a cleanup list, not a per-operation replay log: no content hashes, backups, completion counters or recovery decisions. A failure leaves the union so a later apply/remove cannot strand a partially installed export outside managed cleanup.
4. For every current skill, delete only its exact selected leaf then use the Nix-generated standard copy command from staging. For every current native agent, replace only its exact named file using standard cp. Make copied files writable without losing executable bits. Remove old recorded export leaves that are no longer selected. Never delete/reconcile the common root or unrelated siblings.
5. Commit the preflighted MCP edit through the config helper; it checks the whole config snapshot again. On success replace the deployment inventory with the exact desired list (empty for remove). On failure exit nonzero, report that files may be partially updated and rerun is required; leave inventory and roots available. No rollback or old/new replay is attempted.
6. Release only roots proven unnecessary after success. If configuration ownership/reuse still requires old closures, retain those roots conservatively and report it. Remove never runs GC or deletes a common project directory.

A fresh remove acts on the inventory of prior selections, not all current package names found in arbitrary project content. A replacement apply cleans only the recorded previous exports no longer desired. This preserves the existing stale-export scope without restoring per-file ownership gates. Recording a name means it was selected for replacement, not that its content merits protection.

## 6. Python configuration boundary

Reduce runtime/activate.py into a config-only helper (rename is internal). Keep existing TOMLKit rendering, automatic project/parent/CODEX_HOME/system file reads, extra-config input, bounded unsupported selected MCP sources, equal unowned MCP reuse, unequal unowned MCP conflicts, and preservation of changed previously generated MCP values. These sources remain read-only except target .codex/config.toml.

Delete all skill/agent copying, signatures, native-agent discovery/alias/legacy-role processing, general publication queues, tree backups, per-object recovery and GC-root operations from Python. With no selected or previously tracked MCP keys, skip config discovery entirely; invalid unrelated TOML must not block a file-only environment.

The helper may keep a small MCP-only state containing ownership, last-generated values and reused sources. It must safely handle interruption between the config replacement and bookkeeping without reintroducing a cross-file transaction engine. Before replacing config, persist only the affected MCP keys' previous/desired generated values. On retry, accept a current value only if it matches a recorded generated alternative; a different user value still conflicts. Preserve the distinction between never-owned equal entries and generated entries. Removal records the absence alternative similarly. After successful publication compact to the last-generated state. This is config-specific ownership bookkeeping, not replay of skill/agent operations, rollback, backups, or a claim that config plus state are atomically committed.

Use the exact bytes parsed as the whole-file optimistic snapshot. Render to a temporary file beside config and compare its complete existence/bytes immediately before os.replace; changed unrelated comments/settings abort the write. Preserve file permissions. Locking serializes this tool, not external editors; a narrow race after comparison remains, as in the baseline. Never overwrite global configuration or conceal conflicting keys.

## 7. State compatibility and closure retention

Prefer simple newline name inventories for shell plus MCP-only JSON for the config helper, instead of translating every old state field into another schema. Read baseline schema-1 state only through a narrowly validated conversion: skill/agent key names become deployment inventory; MCP ownership/reused MCP records become config state; existing registered root links are retained. Equal formerly unowned skill/agent records do not authorize deletion unless their names are selected now. Drop their fingerprints/content protection. Preserve old reused-source roots conservatively rather than guessing which free-form skill text references them.

If an old pending.json exists, do not replay or discard it under the new implementation: report that the previous version must resolve that pending operation first. No real existing installation is migrated in this task. Unknown/corrupt state fails with no project writes. Mark the converted state version explicitly and fail safely if an old launcher later sees new-format state; do not support concurrent mixed-version management.

Root names remain generation-specific and registered at stable paths; never move registered links. A failed registration aborts publication. Retain roots for failed attempts until a successful rerun or supported remove establishes no remaining managed/reused/config-protected references. If reused legacy content cannot be proven independent, retaining its old root is deliberate conservative behavior; do not add scanning, garbage collection, or a root-analysis framework. Moving a project still requires reactivation at its new location.

## 8. Alternatives, invariants and effects

Chosen cause chain: R3 unconditional files → remove file ownership decisions → Nix emits standard shell copy commands → selected leaves are exactly replaced while unrelated parents/siblings remain. Config preservation stays with its existing TOML owner. Fixed closures remain rooted independently of file contents.

Alternative: retain Python orchestration but call cp inside it. It does not meet the user's boundary that Python is only for configuration. Alternative: run upstream rsync directly against the real shared skills directory. Its destination-wide --delete can remove unrelated siblings, so reject that wiring. A new generic shell copying/transaction framework is also unnecessary; use upstream staging and fixed per-export commands.

Invariants and representative counterexamples:
- Selected same-name preexisting or edited file/tree is replaced, including extra stale files; no fingerprint protection blocks it.
- An unrelated sibling cannot enter the cleanup list merely because it exists beside a selected export; parent roots are never deletion targets.
- A selected leaf symlink is unlinked rather than traversed. Directory parents may link outside the project by user choice; only selected leaves there may be replaced or removed.
- Interrupted copies can be incomplete, but names remain discoverable for a full repeat or remove and all possibly needed roots remain.
- An unrelated config edit after preflight cannot be overwritten by a stale rendered file; an edited MCP value cannot become implicitly writable through a bookkeeping retry.
- Simultaneous activations use one project lock; arbitrary editor coordination is not promised.

Intended changes: unconditional skill/agent replacement, standard shell file handling, deletion of cross-file recovery, smaller separated state. Preserved: producer API/graph/overrides, full payload contents, unrelated files/settings, MCP protections, runtime closure retention, existing explicit command. Platform acceptance is narrowed to aarch64-darwin by the latest user clarification. Approved changes supersede prior equal/unowned/native-agent preservation and journal guarantees. Prohibited effects: six-repo edits, whole-root cleanup, global writes, formal/live eval, secrets, input changes, new framework.

Known user-visible tradeoff: after interruption the project may contain partial new/old files until rerun. There is no all-project atomicity, backup restoration or per-object automatic recovery. This is the approved simplification, not an undisclosed defect. No critical unresolved product impact is intentionally deferred; independent review must assess the bounded MCP bookkeeping and schema conversion before implementation.

## 9. Sequence and handoff

First review this complete candidate and test-plan.md independently; only after parent confirmation proceed. Then (1) change build copying while retaining API; (2) extract MCP-only helper; (3) generate thin shell activation, inventory and root lifecycle; (4) revise only directly affected existing tests/README/requirements/validation boundaries; (5) independent code review and separately authorized scoped verification. Do not claim prior activation/materialization results validate changed code. Unaffected graph/MCP normalization results may be reused by impact analysis. No formal eval runs in this task.

The implementation branch must start from current remote main after rechecking it. This candidate snapshot was fetched per file at 3b08c9e; no old workspace additions or unmerged PR #2 files are included. Publishing/PR handoff follows parent authorization; no merge is authorized. Keep LICENSE unchanged. Review verdicts belong in the independent review record, not this author document.
