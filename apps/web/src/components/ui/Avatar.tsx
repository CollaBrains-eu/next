type Presence = "online" | "away" | "offline";

const PRESENCE_CLASSES: Record<Presence, string> = {
  online: "bg-success",
  away: "bg-warning",
  offline: "bg-ink-3",
};

const PALETTE = ["#6C63FF", "#EC4899", "#F59E0B", "#10B981", "#3B82F6", "#8B5CF6", "#EF4444", "#14B8A6"];

function colorForName(name: string): string {
  let hash = 0;
  for (let i = 0; i < name.length; i++) hash = (hash << 5) - hash + name.charCodeAt(i);
  return PALETTE[Math.abs(hash) % PALETTE.length];
}

function initials(name: string): string {
  const parts = name.trim().split(/\s+/);
  return ((parts[0]?.[0] ?? "") + (parts[1]?.[0] ?? "")).toUpperCase();
}

export function Avatar({
  name,
  presence,
  size = 32,
}: {
  name: string;
  presence?: Presence;
  size?: number;
}) {
  return (
    <span
      className="relative inline-flex shrink-0 items-center justify-center rounded-full border-2 border-surface font-bold text-white"
      style={{ width: size, height: size, backgroundColor: colorForName(name), fontSize: size * 0.36 }}
    >
      {initials(name)}
      {presence && (
        <span
          className={`absolute -bottom-px -right-px h-2.5 w-2.5 rounded-full border-2 border-surface ${PRESENCE_CLASSES[presence]}`}
        />
      )}
    </span>
  );
}

export function AvatarGroup({ names, max = 4 }: { names: string[]; max?: number }) {
  const shown = names.slice(0, max);
  const overflow = names.length - shown.length;
  return (
    <span className="flex">
      {shown.map((name, i) => (
        <span key={name} className={i > 0 ? "-ml-2.5" : ""}>
          <Avatar name={name} />
        </span>
      ))}
      {overflow > 0 && (
        <span
          className="-ml-2.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full border-2 border-surface bg-accent-soft text-xs font-bold text-accent"
        >
          +{overflow}
        </span>
      )}
    </span>
  );
}
