---
name: zhange-multirepo-change
description: Coordinate changes across zhange-base, zhange-app, and zhange-stats. Use when changing shared design-system code, submodule pointers, consumer build configuration, or cross-project release contracts.
---

# Zhange Multi-Repository Changes

## Workflow

1. Read each affected repository's `AGENTS.md` and architecture or engineering guide. Check `git status` and diffs in all three repositories before editing; preserve existing work.
2. Keep repository boundaries intact. Put framework-independent code used by both apps in `zhange-base`; keep page layouts, framework adapters, business state, and runtime-specific code in their owning app.
3. For shared design-system changes, edit only `zhange-base`, regenerate tokens with its documented command, and run `node design-system/scripts/generate-tokens.mjs --check`. Never copy edited shared files into a consumer.
4. Update consumer submodule pointers only to a `zhange-base` commit that consumers can fetch. Do not point a consumer at an uncommitted or unpublished submodule state; if publishing was not authorized, leave the pointer unchanged and report what remains.
5. Verify both consumers independently: submodule checkout, Vite and TypeScript aliases, direct font dependencies, CI checkout settings, release license inclusion, and each repository's applicable tests and build.
6. Review each repository's full diff and run `git diff --check`. Report test commands and results separately by repository, including failures caused by the host platform or unavailable services.

## Boundaries

- `zhange-app` and `zhange-stats` retain independent build, release, and business boundaries.
- `zhange-base` is a Git submodule source, not an npm package or a neighboring-directory dependency.
- The design-token source is `design-system/tokens/tarkov.json`; generated outputs are changed only by `design-system/scripts/generate-tokens.mjs`.
- Shared design-system and consumer rules are maintained in each repository's `AGENTS.md`, `ARCHITECTURE.md`, `docs/engineering-guidelines.md`, and `zhange-base/README.md`. Update the authoritative document when behavior or a boundary changes; keep this skill focused on workflow.
