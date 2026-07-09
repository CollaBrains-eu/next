import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { approveEntity, bulkReviewEntities, listEntities, rejectEntity, type EntityOut } from "../lib/api";
import { Button } from "../components/ui/Button";

export default function EntityReview() {
  const [queue, setQueue] = useState<EntityOut[] | null>(null);
  const [index, setIndex] = useState(0);

  useEffect(() => {
    listEntities(undefined, undefined, "pending_review").then(setQueue);
  }, []);

  const current = queue?.[index];

  async function handleApprove() {
    if (!current) return;
    await approveEntity(current.id);
    setIndex((i) => i + 1);
  }

  async function handleReject() {
    if (!current) return;
    await rejectEntity(current.id);
    setIndex((i) => i + 1);
  }

  async function handleApproveAll() {
    if (!queue) return;
    const remaining = queue.slice(index);
    if (remaining.length === 0) return;
    await bulkReviewEntities(remaining.map((e) => ({ entity_id: e.id, action: "approve" as const })));
    setQueue([]);
    setIndex(0);
  }

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (!current) return;
      if (e.key === "j" || e.key === "ArrowRight") handleApprove();
      if (e.key === "k" || e.key === "ArrowLeft") handleReject();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  });

  if (queue === null) return <p className="text-ink-3">Loading…</p>;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <Link to="/entities" className="text-sm text-ink-2 hover:text-ink">
            ← Back to entities
          </Link>
          <h1 className="mt-2 text-2xl font-semibold text-ink">Review entities</h1>
        </div>
        {queue.length > 0 && (
          <Button variant="secondary" size="sm" onClick={handleApproveAll}>
            Approve all
          </Button>
        )}
      </div>

      {!current ? (
        <p className="text-ink-3">Nothing to review</p>
      ) : (
        <div className="flex flex-col gap-4 rounded-2xl border border-edge bg-surface p-6">
          <p className="text-sm text-ink-3">
            {index + 1} of {queue.length}
          </p>
          <div>
            <p className="text-lg font-semibold text-ink">{current.name}</p>
            <p className="text-sm text-ink-2">{current.entity_type}</p>
          </div>
          <div className="flex gap-2">
            <Button variant="danger" onClick={handleReject}>
              Reject
            </Button>
            <Button variant="primary" onClick={handleApprove}>
              Approve
            </Button>
          </div>
          <p className="text-xs text-ink-3">Keyboard: J or → to approve, K or ← to reject</p>
        </div>
      )}
    </div>
  );
}
