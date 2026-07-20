import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import Card from "./Card";
import EmptyState from "./EmptyState";
import { Button } from "./ui/Button";
import {
  acceptWorkspaceInvitation,
  declineWorkspaceInvitation,
  inviteWorkspaceMember,
  listMyWorkspaceInvitations,
  listMyWorkspaceMembers,
  listWorkspacesSharedWithMe,
  lookupUserByPhone,
  revokeWorkspaceMember,
  updateWorkspaceMemberExport,
  ApiError,
  type WorkspaceMemberOut,
} from "../lib/api";

export function WorkspaceSharing() {
  const { t } = useTranslation();
  const [myMembers, setMyMembers] = useState<WorkspaceMemberOut[] | null>(null);
  const [invitations, setInvitations] = useState<WorkspaceMemberOut[]>([]);
  const [sharedWithMe, setSharedWithMe] = useState<WorkspaceMemberOut[]>([]);
  const [error, setError] = useState<string | null>(null);

  const [invitePhone, setInvitePhone] = useState("");
  const [inviteLookup, setInviteLookup] = useState<
    { id: string; username: string; display_name: string } | null | "not-found"
  >(null);
  const [inviteCanExport, setInviteCanExport] = useState(false);
  const [inviteLoading, setInviteLoading] = useState(false);
  const [inviteError, setInviteError] = useState<string | null>(null);

  function refresh() {
    listMyWorkspaceMembers()
      .then(setMyMembers)
      .catch((err) => setError(err instanceof ApiError ? err.message : t("workspaceSharing.loadError")));
    listMyWorkspaceInvitations().then(setInvitations).catch(() => {});
    listWorkspacesSharedWithMe().then(setSharedWithMe).catch(() => {});
  }

  useEffect(refresh, [t]);

  async function handleLookupPhone() {
    if (!invitePhone.trim()) return;
    setInviteError(null);
    setInviteLoading(true);
    try {
      const found = await lookupUserByPhone(invitePhone.trim());
      setInviteLookup(found ?? "not-found");
    } catch (err) {
      setInviteError(err instanceof ApiError ? err.message : t("workspaceSharing.lookupError"));
    } finally {
      setInviteLoading(false);
    }
  }

  async function handleInvite() {
    if (!inviteLookup || inviteLookup === "not-found") return;
    setInviteLoading(true);
    setInviteError(null);
    try {
      await inviteWorkspaceMember(inviteLookup.id, inviteCanExport);
      setInvitePhone("");
      setInviteLookup(null);
      setInviteCanExport(false);
      refresh();
    } catch (err) {
      setInviteError(err instanceof ApiError ? err.message : t("workspaceSharing.inviteError"));
    } finally {
      setInviteLoading(false);
    }
  }

  async function handleRevoke(memberId: string) {
    try {
      await revokeWorkspaceMember(memberId);
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("workspaceSharing.revokeError"));
    }
  }

  async function handleToggleExport(member: WorkspaceMemberOut) {
    try {
      await updateWorkspaceMemberExport(member.member_id, !member.can_export);
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("workspaceSharing.updateError"));
    }
  }

  async function handleRespond(ownerId: string, accept: boolean) {
    try {
      if (accept) await acceptWorkspaceInvitation(ownerId);
      else await declineWorkspaceInvitation(ownerId);
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("workspaceSharing.respondError"));
    }
  }

  const acceptedMembers = (myMembers ?? []).filter((m) => m.status === "accepted");
  const pendingMembers = (myMembers ?? []).filter((m) => m.status === "pending");
  const atCapacity = acceptedMembers.length + pendingMembers.length >= 2;

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h2 className="text-lg font-semibold text-ink">{t("workspaceSharing.title")}</h2>
        <p className="text-xs text-ink-3">{t("workspaceSharing.description")}</p>
      </div>

      {error && <p className="text-sm text-danger">{error}</p>}

      {invitations.length > 0 && (
        <Card className="flex flex-col gap-2">
          <span className="text-xs font-bold uppercase tracking-wide text-ink-2">
            {t("workspaceSharing.invitationsReceived")}
          </span>
          {invitations.map((inv) => (
            <div key={inv.id} className="flex items-center justify-between gap-3 text-sm text-ink">
              <span className="truncate">{t("workspaceSharing.invitedBy", { name: inv.owner_display_name })}</span>
              <div className="flex shrink-0 gap-2">
                <Button size="sm" onClick={() => handleRespond(inv.owner_id, true)}>
                  {t("workspaceSharing.accept")}
                </Button>
                <Button size="sm" variant="ghost" onClick={() => handleRespond(inv.owner_id, false)}>
                  {t("workspaceSharing.decline")}
                </Button>
              </div>
            </div>
          ))}
        </Card>
      )}

      <Card className="flex flex-col gap-3">
        <span className="text-xs font-bold uppercase tracking-wide text-ink-2">{t("workspaceSharing.myShares")}</span>

        {!atCapacity && (
          <div className="flex flex-col gap-2 rounded-xl border border-edge p-3">
            <div className="flex flex-wrap items-center gap-2">
              <input
                value={invitePhone}
                onChange={(e) => {
                  setInvitePhone(e.target.value);
                  setInviteLookup(null);
                }}
                placeholder={t("workspaceSharing.invitePhonePlaceholder")}
                className="flex-1 rounded-lg border border-edge bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-accent"
              />
              <Button
                size="sm"
                variant="secondary"
                onClick={handleLookupPhone}
                disabled={inviteLoading || !invitePhone.trim()}
              >
                {t("workspaceSharing.lookupAction")}
              </Button>
            </div>
            {inviteLookup === "not-found" && <p className="text-xs text-danger">{t("workspaceSharing.userNotFound")}</p>}
            {inviteLookup && inviteLookup !== "not-found" && (
              <div className="flex flex-wrap items-center gap-3">
                <span className="text-sm text-ink">{inviteLookup.display_name}</span>
                <label className="flex items-center gap-1.5 text-xs text-ink-2">
                  <input
                    type="checkbox"
                    checked={inviteCanExport}
                    onChange={(e) => setInviteCanExport(e.target.checked)}
                  />
                  {t("workspaceSharing.allowExport")}
                </label>
                <Button size="sm" onClick={handleInvite} disabled={inviteLoading}>
                  {t("workspaceSharing.inviteAction")}
                </Button>
              </div>
            )}
            {inviteError && <p className="text-xs text-danger">{inviteError}</p>}
          </div>
        )}
        {atCapacity && <p className="text-xs text-ink-3">{t("workspaceSharing.atCapacity")}</p>}

        {acceptedMembers.length === 0 && pendingMembers.length === 0 ? (
          <EmptyState message={t("workspaceSharing.noShares")} />
        ) : (
          <div className="flex flex-col divide-y divide-edge overflow-hidden rounded-xl border border-edge">
            {[...acceptedMembers, ...pendingMembers].map((m) => (
              <div key={m.id} className="flex items-center justify-between gap-3 px-3 py-2 text-sm text-ink">
                <span className="truncate">{m.member_display_name}</span>
                <div className="flex shrink-0 items-center gap-2">
                  {m.status === "pending" && (
                    <span className="text-xs text-ink-3">{t("workspaceSharing.pending")}</span>
                  )}
                  {m.status === "accepted" && (
                    <label className="flex items-center gap-1.5 text-xs text-ink-2">
                      <input type="checkbox" checked={m.can_export} onChange={() => handleToggleExport(m)} />
                      {t("workspaceSharing.allowExport")}
                    </label>
                  )}
                  <Button size="sm" variant="ghost" onClick={() => handleRevoke(m.member_id)}>
                    {t("common.remove")}
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      {sharedWithMe.length > 0 && (
        <Card className="flex flex-col gap-2">
          <span className="text-xs font-bold uppercase tracking-wide text-ink-2">
            {t("workspaceSharing.sharedWithMe")}
          </span>
          {sharedWithMe.map((s) => (
            <div key={s.id} className="text-sm text-ink">
              {t("workspaceSharing.sharedByName", { name: s.owner_display_name })}
            </div>
          ))}
          <p className="text-xs text-ink-3">{t("workspaceSharing.sharedWithMeHint")}</p>
        </Card>
      )}
    </div>
  );
}
