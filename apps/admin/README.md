# admin

Control Center: user management, AI usage/cost monitoring, service health, bug reports. Phase 22.

Implemented inside `apps/web` (`src/routes/AdminDashboard.tsx`, role-gated
by `src/components/AdminRoute.tsx`) and `services/api`
(`api/admin_router.py`/`api/admin_service.py`), not as a separate
deployable — one React app and one backend, same "smallest safe slice"
reasoning as every other stub in this tree (see `services/ai-gateway/README.md`).
This stub stays in place as a placeholder for a future split, e.g. if a
dedicated ops team ever needs its own deploy cadence for this surface.
