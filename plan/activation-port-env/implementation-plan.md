# Activation-time MCP port: implementation plan

Baseline: main `c368871942435bdc178a1063ce9c677acaf8cabc`. Product/reviewed PR revision: `04f22a464e26207746a619312e80f6d6df6fccf9` ([PR #6](https://github.com/RekiDunois/agent-env-nix/pull/6)).

Document revision: split-plan v1, 2026-10-24. The user's latest instruction is “你给拆成两个吧，走正常审核”. This revision separates the two canonical plans without changing product or test code, requirements, or test scope. The previous combined path is navigation only.

## Requirement, solution and preserved behavior

The user approved implementing and opening a PR for shared activation-time port environment support, with a producer declaration and a consumer devShell environment variable. No Codex interpolation, consumer/factory port plumbing, generic template engine, or unrelated consumer conflict repair.

1. Add optional `mkAgentPackage.mcpPortEnv = { serverName = "ENV_NAME"; };`. The existing HTTP server `url` is the default URL. Validate mapping type, shell-style environment variable names, and that every mapping selects an existing HTTP server. Keep metadata separate from upstream mcp-servers-nix and native Codex TOML; carry it through package metadata into the project manifest.
2. During MCP prepare, resolve only mapped URLs. An absent variable retains the default URL. A present variable must be 1–5 ASCII decimal digits representing 1..65535; empty, whitespace, negative, and out-of-range values fail without publishing MCP state/config. Validate the mapped default URL as HTTP(S), with a hostname, no userinfo, and a valid explicit port when present. Replace only the port, retaining scheme, host (including IPv6 brackets), path, query and fragment. All unmapped server values remain unchanged.
3. Feed resolved desired values through the existing ownership/conflict checks. Preserve edited owned definitions, refuse unequal unowned sources, and reuse equal unowned definitions without taking ownership. Commit uses the prepared rendered config and never re-reads the port environment.
4. Add an internal `agent-env cache-key` operation that uses the same desired-value resolver and hashes effective MCP configuration. The cached wrapper includes this digest in its version-2 success marker before comparing the cache, and invokes apply with its unchanged inherited environment. Invalid port inputs fail before skipping. Existing failure invalidation, locking and atomic success publication remain; the cache still does not inspect installed content, and manual edits still require `--force`.
5. Document the producer declaration and devShell variable example. Change only relevant Nix wiring, runtime helpers, tests and this record. Do not change credentials, security settings, user computers or upstream pins. Publication remains a separate authorized action; no automatic merge or deployment.

This is a bounded new interface and persistent activation behavior, not a mechanical fast-merge correction. The user requested normal review on 2026-10-24. Review the complete affected scope under the execution-plan, test-plan and merge rules; do not treat it as a mechanical fast path or add an unrelated test matrix.

## Current state and handoff

Implementation exists at the PR revision above. The original independent review approved execution gates P1–P4; the split revision has now received independent normal-review approval for execution gates P1–P4. This is plan approval, not test execution or merge approval. See the [review record](../activation-port-env-review.md).

The [test plan and retained results](test-plan.md) are the unique source for checks, commands and evidence. Existing host-fixture results remain reusable because this split changes no product or test code. Real Nix evaluation/build and packaged activation wiring remain unexecuted; implementation-plan approval cannot make those results PASS or the PR READY.

The earlier authoring scope did not permit Nix installation. The user subsequently authorized cloud Nix installation; the parent reports the execution environment failed before installation began. This documentation-only revision neither revokes that authorization nor attempts installation or bypasses the environment restriction. Resume the bounded Nix validation only in a working authorized environment, with runnable steps reviewed before execution. The parent coordinates the execution owner and remote PR checks.
