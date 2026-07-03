import Svg, { Circle, G, Line, Rect, Text as SvgText } from "react-native-svg";
import type { EntityGraphOut, GraphNode } from "../lib/api";

const TYPE_COLORS: Record<string, string> = {
  person: "#2563eb",
  organization: "#7c3aed",
  location: "#16a34a",
  other: "#64748b",
};

const WIDTH = 350;
const HEIGHT = 400;
const CENTER = { x: WIDTH / 2, y: HEIGHT / 2 };
const RADIUS = 130;
const NODE_RADIUS = 8;

function nodeColor(entityType: string): string {
  return TYPE_COLORS[entityType] ?? TYPE_COLORS.other;
}

export function EntityGraph({ graph, onSelectNode }: { graph: EntityGraphOut; onSelectNode: (id: string) => void }) {
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
    <Svg width={WIDTH} height={HEIGHT}>
      {graph.edges.map((edge, i) => {
        const from = positions.get(edge.source);
        const to = positions.get(edge.target);
        if (!from || !to) return null;
        const mid = { x: (from.x + to.x) / 2, y: (from.y + to.y) / 2 };
        return (
          <G key={i}>
            <Line x1={from.x} y1={from.y} x2={to.x} y2={to.y} stroke="#94a3b8" strokeWidth={1.5} />
            <SvgText x={mid.x} y={mid.y} fontSize={9} fill="#64748b" textAnchor="middle">
              {edge.relationship_type}
            </SvgText>
          </G>
        );
      })}

      {graph.nodes.map((node: GraphNode) => {
        const pos = positions.get(node.id)!;
        return (
          <G key={node.id} onPress={() => onSelectNode(node.id)}>
            {/* Transparent hit-target covering the circle + label together, built in
                from the start per ADR 0016 -- SVG hit-testing is per-painted-shape,
                not per-bounding-box, so the gap between the circle and its label
                below it would otherwise be an unclickable dead zone (found and fixed
                on the web version in Phase 5c; touch targets are coarser than a
                mouse, so the same problem is at least as likely here). */}
            <Rect x={pos.x - 45} y={pos.y - NODE_RADIUS - 2} width={90} height={NODE_RADIUS + 30} fill="transparent" />
            <Circle cx={pos.x} cy={pos.y} r={NODE_RADIUS} fill={nodeColor(node.entity_type)} />
            <SvgText x={pos.x} y={pos.y + NODE_RADIUS + 14} fontSize={10} fill="#1e293b" textAnchor="middle">
              {node.name.length > 20 ? `${node.name.slice(0, 20)}…` : node.name}
            </SvgText>
          </G>
        );
      })}

      <Circle cx={CENTER.x} cy={CENTER.y} r={NODE_RADIUS + 2} fill={nodeColor(graph.center.entity_type)} stroke="#0f172a" strokeWidth={2} />
      <SvgText x={CENTER.x} y={CENTER.y + NODE_RADIUS + 18} fontSize={11} fontWeight="600" fill="#0f172a" textAnchor="middle">
        {graph.center.name}
      </SvgText>
    </Svg>
  );
}
