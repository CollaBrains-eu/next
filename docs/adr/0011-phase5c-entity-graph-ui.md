# ADR 0011: Phase 5c — Entity Graph Visualization

## Status
Accepted

## Context
Phase 4 built `GET /entities` (search/list) and `GET /entities/{id}/graph`
(one-hop neighborhood: the entity itself, its direct neighbors, and the
edges between them — see ADR 0008). There is no "whole graph" endpoint,
and adding one is out of scope here per the same "expose what already
exists" discipline used in Phase 5b — the one-hop shape was a deliberate
Phase 4 design choice, not an oversight.

## Decision: an entity explorer, not a global force-directed graph
Because the only graph data available is always "one center entity plus
its direct neighbors," a general force-directed layout (d3-force,
react-flow, etc.) would be solving a problem that doesn't exist here —
there's never more than a handful of nodes in view at once, and the
shape is inherently hub-and-spoke, not an arbitrary mesh. Instead:

- **`/entities` (new route)**: a searchable, type-filterable list backed
  by `GET /entities?q=&entity_type=`. Each row links to that entity's
  graph view.
- **`/entities/:id` (new route)**: fetches `GET /entities/{id}/graph` and
  renders it as a hand-written SVG radial layout — the center entity in
  the middle, its neighbors placed evenly around a circle, edges drawn
  as labeled lines between them. Clicking any neighbor node navigates to
  `/entities/{neighborId}`, re-fetching and re-centering the graph there
  — this is how multi-hop exploration works without the backend ever
  returning more than one hop at a time. No new npm dependency: for a
  bounded-size hub-and-spoke layout, `Math.cos`/`Math.sin` around a
  circle is simpler and lighter than pulling in a graph-layout library,
  consistent with this project's pattern of avoiding infrastructure
  beyond what's needed (Postgres-native search over Elasticsearch,
  in-process triggers over Celery, hand-written API types over codegen).

## Why not more
No document→entities endpoint exists yet (`GET /documents/{id}` doesn't
return which entities were extracted from it), so the Document Detail
page doesn't get an "entities in this document" panel in 5c — adding
that endpoint is a backend change, not frontend work, and isn't needed
to make the existing entity/graph endpoints usable. Zoom/pan and
force-directed physics are deferred until the graph data itself supports
more than one hop at a time; they'd add complexity without adding
capability today.
