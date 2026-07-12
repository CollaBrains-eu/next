import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ApiError, getEntityGraph, type EntityGraphOut } from "../lib/api";
import EmptyState from "../components/EmptyState";
import { Breadcrumbs } from "../components/ui/Breadcrumbs";
import { SkeletonLines } from "../components/ui/Skeleton";

// Categorical colors distinguishing entity types on the graph -- like
// Avatar's palette, these identify a category and must stay visually
// distinct, so they're not swapped for the shared --accent/--text tokens.
const TYPE_COLORS: Record<string, string> = {
  person: "#2563eb",
  organization: "#7c3aed",
  location: "#16a34a",
  address: "#ea580c",
  other: "#64748b",
};

const TYPE_LABEL_KEYS: Record<string, string> = {
  person: "entities.typePerson",
  organization: "entities.typeOrganization",
  location: "entities.typeLocation",
  address: "entities.typeAddress",
  other: "entities.typeOther",
};

const WIDTH = 700;
const HEIGHT = 480;
const CENTER = { x: WIDTH / 2, y: HEIGHT / 2 };
const RADIUS = 170;
const NODE_RADIUS = 8;

function nodeColor(entityType: string): string {
  return TYPE_COLORS[entityType] ?? TYPE_COLORS.other;
}

export default function EntityGraph() {
  const { t } = useTranslation();
  const { id } = useParams<{ id: string }>();
  const [graph, setGraph] = useState<EntityGraphOut | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    setGraph(null);
    setError(null);
    getEntityGraph(id)
      .then(setGraph)
      .catch((err) => setError(err instanceof ApiError ? err.message : t("entityGraph.loadError")));
  }, [id, t]);

  if (error) {
    return (
      <div>
        <Breadcrumbs items={[{ label: t("nav.entities"), to: "/entities" }, { label: t("entityGraph.breadcrumbError") }]} />
        <p className="text-danger">{error}</p>
      </div>
    );
  }

  if (!graph) return <SkeletonLines className="max-w-md" />;

  const positions = new Map<string, { x: number; y: number }>();
  positions.set(graph.center.id, CENTER);
  graph.nodes.forEach((node, i) => {
    const angle = (2 * Math.PI * i) / Math.max(graph.nodes.length, 1) - Math.PI / 2;
    positions.set(node.id, {
      x: CENTER.x + RADIUS * Math.cos(angle),
      y: CENTER.y + RADIUS * Math.sin(angle),
    });
  });

  const typeLabel = t(TYPE_LABEL_KEYS[graph.center.entity_type] ?? TYPE_LABEL_KEYS.other);

  return (
    <div className="flex flex-col gap-4">
      <div>
        <Breadcrumbs items={[{ label: t("nav.entities"), to: "/entities" }, { label: graph.center.name }]} />
        <h1 className="text-2xl font-semibold text-ink">{graph.center.name}</h1>
        <p className="text-sm text-ink-2">
          {t("entityGraph.relationshipCount", { count: graph.nodes.length, type: typeLabel })}
        </p>
      </div>

      {graph.nodes.length === 0 ? (
        <EmptyState message={t("entityGraph.noRelationships")} />
      ) : (
        <div className="rounded-2xl border border-edge bg-surface">
          <svg width="100%" viewBox={`0 0 ${WIDTH} ${HEIGHT}`} style={{ maxWidth: WIDTH, display: "block" }}>
            <defs>
              <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                <path d="M0,0 L10,5 L0,10 z" fill="var(--text-3)" />
              </marker>
            </defs>

            {graph.edges.map((edge, i) => {
              const from = positions.get(edge.source);
              const to = positions.get(edge.target);
              if (!from || !to) return null;
              const mid = { x: (from.x + to.x) / 2, y: (from.y + to.y) / 2 };
              return (
                <g key={i} style={{ pointerEvents: "none" }}>
                  <line
                    x1={from.x}
                    y1={from.y}
                    x2={to.x}
                    y2={to.y}
                    stroke="var(--text-3)"
                    strokeWidth={1.5}
                    markerEnd="url(#arrow)"
                  />
                  <text x={mid.x} y={mid.y} textAnchor="middle" fontSize={10} fill="var(--text-2)" className="select-none">
                    {edge.relationship_type}
                  </text>
                </g>
              );
            })}

            {graph.nodes.map((node) => {
              const pos = positions.get(node.id)!;
              return (
                <Link key={node.id} to={`/entities/${node.id}`}>
                  <g className="cursor-pointer">
                    <rect
                      x={pos.x - 45}
                      y={pos.y - NODE_RADIUS - 2}
                      width={90}
                      height={NODE_RADIUS + 30}
                      fill="transparent"
                    />
                    <circle cx={pos.x} cy={pos.y} r={NODE_RADIUS} fill={nodeColor(node.entity_type)} />
                    <text x={pos.x} y={pos.y + NODE_RADIUS + 14} textAnchor="middle" fontSize={11} fill="var(--text)">
                      {node.name.length > 24 ? `${node.name.slice(0, 24)}…` : node.name}
                    </text>
                  </g>
                </Link>
              );
            })}

            <circle cx={CENTER.x} cy={CENTER.y} r={NODE_RADIUS + 2} fill={nodeColor(graph.center.entity_type)} stroke="var(--text)" strokeWidth={2} />
            <text x={CENTER.x} y={CENTER.y + NODE_RADIUS + 18} textAnchor="middle" fontSize={12} fontWeight={600} fill="var(--text)">
              {graph.center.name}
            </text>
          </svg>
        </div>
      )}
    </div>
  );
}
