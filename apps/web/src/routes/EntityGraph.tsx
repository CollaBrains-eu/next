import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError, getEntityGraph, type EntityGraphOut } from "../lib/api";

const TYPE_COLORS: Record<string, string> = {
  person: "#2563eb",
  organization: "#7c3aed",
  location: "#16a34a",
  other: "#64748b",
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
  const { id } = useParams<{ id: string }>();
  const [graph, setGraph] = useState<EntityGraphOut | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    setGraph(null);
    setError(null);
    getEntityGraph(id)
      .then(setGraph)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load graph"));
  }, [id]);

  if (error) {
    return (
      <div>
        <Link to="/entities" className="text-sm text-ink-2 hover:text-ink">
          ← Back to entities
        </Link>
        <p className="mt-4 text-danger">{error}</p>
      </div>
    );
  }

  if (!graph) return <p className="text-ink-3">Loading…</p>;

  const positions = new Map<string, { x: number; y: number }>();
  positions.set(graph.center.id, CENTER);
  graph.nodes.forEach((node, i) => {
    const angle = (2 * Math.PI * i) / Math.max(graph.nodes.length, 1) - Math.PI / 2;
    positions.set(node.id, {
      x: CENTER.x + RADIUS * Math.cos(angle),
      y: CENTER.y + RADIUS * Math.sin(angle),
    });
  });

  return (
    <div className="flex flex-col gap-4">
      <div>
        <Link to="/entities" className="text-sm text-ink-2 hover:text-ink">
          ← Back to entities
        </Link>
        <h1 className="mt-2 text-2xl font-semibold text-ink">{graph.center.name}</h1>
        <p className="text-sm text-ink-2">
          {graph.center.entity_type} · {graph.nodes.length} direct relationship{graph.nodes.length === 1 ? "" : "s"}
        </p>
      </div>

      {graph.nodes.length === 0 ? (
        <p className="text-ink-3">No known relationships for this entity yet.</p>
      ) : (
        <div className="overflow-x-auto rounded-2xl border border-edge bg-surface">
          <svg width={WIDTH} height={HEIGHT} viewBox={`0 0 ${WIDTH} ${HEIGHT}`}>
            <defs>
              <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                <path d="M0,0 L10,5 L0,10 z" fill="#94a3b8" />
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
                    stroke="#94a3b8"
                    strokeWidth={1.5}
                    markerEnd="url(#arrow)"
                  />
                  <text x={mid.x} y={mid.y} textAnchor="middle" fontSize={10} fill="#64748b" className="select-none">
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
                    <text x={pos.x} y={pos.y + NODE_RADIUS + 14} textAnchor="middle" fontSize={11} fill="#1e293b">
                      {node.name.length > 24 ? `${node.name.slice(0, 24)}…` : node.name}
                    </text>
                  </g>
                </Link>
              );
            })}

            <circle cx={CENTER.x} cy={CENTER.y} r={NODE_RADIUS + 2} fill={nodeColor(graph.center.entity_type)} stroke="#0f172a" strokeWidth={2} />
            <text x={CENTER.x} y={CENTER.y + NODE_RADIUS + 18} textAnchor="middle" fontSize={12} fontWeight={600} fill="#0f172a">
              {graph.center.name}
            </text>
          </svg>
        </div>
      )}
    </div>
  );
}
