# ADR 0001: Phase 0 architecture decisions

## Status
Accepted

## Context
CollaBrains is being rebuilt from scratch as a privacy-first AI knowledge
platform where AI is the orchestration layer across Web, Admin, and Signal
clients. Phase 0 establishes the monorepo, tooling, and the minimal set of
working services needed as a foundation for later phases.

## Decisions

- **Monorepo tooling**: `uv` workspace for Python (`services/*`, `agents/*`),
  `pnpm` workspace for TypeScript (`apps/*`, `packages/*`). Both support fast,
  reproducible, per-package dependency resolution without a build system as
  heavy as Bazel/Nx.
- **Postgres image**: `pgvector/pgvector:pg16` instead of vanilla Postgres —
  the `embeddings` table needs a vector column from the first migration, and
  swapping images later would mean a data migration for no benefit.
- **Elasticsearch**: single-node, security disabled — dev-only config. Must be
  hardened (TLS, auth) before Phase 6 production readiness.
- **Ollama**: CPU by default; a `gpu` Compose profile adds the NVIDIA device
  reservation so the same file works on this host (OpenVZ container, no GPU)
  and a future GPU host without edits.
- **Paperless-ngx**: given its own SQLite store, sharing only Redis (separate
  DB index) with the rest of the stack — keeps its schema decoupled from the
  app database.
- **Signal**: not wired up in Phase 0. `apps/signal-bot` is a health-check
  stub; the real `signal-cli` container and bot logic land in Phase 3, gated
  behind a `signal` Compose profile until a phone number is provisioned.
- **Auth**: Phase 0 ships a JWT stub (hardcoded test user) in `services/api`.
  Real LDAP binding is Phase 1 scope.
- **Host**: deployed on an OpenVZ-virtualized Ubuntu 24.04 VPS
  (`v78281.1blu.de`), CPU-only, 8 vCPU / 24GB RAM / ~900GB disk. Docker runs
  fine in this OpenVZ container (verified with `docker run hello-world`), but
  this constrains the LLM to CPU inference and rules out GPU-dependent
  features until infra changes.

## Consequences
Everything under `services/` and `agents/` other than `api` is an empty,
typed placeholder in Phase 0 — intentional, to avoid building abstractions
before the phase that needs them.
