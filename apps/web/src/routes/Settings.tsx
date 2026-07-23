import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { AddressHistory } from "../components/AddressHistory";
import Card from "../components/Card";
import { PasskeySettings } from "../components/PasskeySettings";
import { WorkspaceSharing } from "../components/WorkspaceSharing";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Combobox, type ComboboxOption } from "../components/ui/Combobox";
import {
  ApiError,
  createCheckoutSession,
  createPortalSession,
  getOrganization,
  getPreferences,
  getSubscription,
  inviteOrganizationMember,
  listOrganizationInvitations,
  listOrganizationMembers,
  renameOrganization,
  revokeOrganizationInvitation,
  setOrganizationPolicies,
  setPreferences,
  type InvitationOut,
  type OrganizationMemberOut,
  type SubscriptionOut,
} from "../lib/api";
import { syncLanguage } from "../lib/auth";
import { toDateFormatPrefs, type DateFormat, type TimeFormat } from "../lib/dateFormat";
import { setDateFormatPrefs } from "../hooks/useDateFormat";
import { useToast } from "../lib/toast";

// The full goal-type vocabulary planning_engine.build_steps() recognizes --
// APPROVAL_REQUIRED_GOALS is only the *default* subset of these that
// require approval, not the set of choices an org can pick from.
const GOAL_TYPES = [
  "summarize_case",
  "analyze_new_upload",
  "draft_legal_document",
  "prepare_objection",
  "draft_communication",
  "organize_document_collection",
  "generate_timeline",
];

export default function Settings() {
  const { t } = useTranslation();
  const [language, setLanguage] = useState("");
  const [dateFormat, setDateFormat] = useState<DateFormat>("eu");
  const [timeFormat, setTimeFormat] = useState<TimeFormat>("h24");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const languageOptions = [
    { value: "", label: t("settings.noPreference") },
    { value: "English", label: "English" },
    { value: "Nederlands", label: "Nederlands" },
    { value: "Deutsch", label: "Deutsch" },
  ];

  const dateFormatOptions: { value: DateFormat; label: string }[] = [
    { value: "eu", label: t("settings.dateFormatEu") },
    { value: "us", label: t("settings.dateFormatUs") },
    { value: "iso", label: t("settings.dateFormatIso") },
  ];

  const timeFormatOptions: { value: TimeFormat; label: string }[] = [
    { value: "h24", label: t("settings.timeFormatH24") },
    { value: "h12", label: t("settings.timeFormatH12") },
  ];

  useEffect(() => {
    getPreferences()
      .then((prefs) => {
        setLanguage(prefs.preferred_language ?? "");
        const parsed = toDateFormatPrefs(prefs.date_format, prefs.time_format);
        setDateFormat(parsed.dateFormat);
        setTimeFormat(parsed.timeFormat);
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : t("settings.loadError")))
      .finally(() => setLoading(false));
  }, [t]);

  async function handleSave() {
    setSaving(true);
    setSaved(false);
    setError(null);
    try {
      await setPreferences({ preferredLanguage: language || null, dateFormat, timeFormat });
      syncLanguage(language || null);
      setDateFormatPrefs({ dateFormat, timeFormat });
      setSaved(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("settings.saveError"));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold text-ink">{t("settings.title")}</h1>

      <Card className="flex max-w-md flex-col gap-3">
        <div>
          <label className="text-sm font-medium text-ink" htmlFor="preferred-language">
            {t("settings.preferredLanguage")}
          </label>
          <p className="text-xs text-ink-3">{t("settings.preferredLanguageHint")}</p>
        </div>
        {loading ? (
          <p className="text-sm text-ink-3">{t("common.loading")}</p>
        ) : (
          <>
            <select
              id="preferred-language"
              value={language}
              onChange={(e) => {
                setLanguage(e.target.value);
                setSaved(false);
              }}
              className="rounded-xl border border-edge bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-accent focus:ring-2 focus:ring-accent-soft"
            >
              {languageOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>

            <div>
              <label className="text-sm font-medium text-ink" htmlFor="date-format">
                {t("settings.dateFormat")}
              </label>
              <select
                id="date-format"
                value={dateFormat}
                onChange={(e) => {
                  setDateFormat(e.target.value as DateFormat);
                  setSaved(false);
                }}
                className="mt-1 w-full rounded-xl border border-edge bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-accent focus:ring-2 focus:ring-accent-soft"
              >
                {dateFormatOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="text-sm font-medium text-ink" htmlFor="time-format">
                {t("settings.timeFormat")}
              </label>
              <select
                id="time-format"
                value={timeFormat}
                onChange={(e) => {
                  setTimeFormat(e.target.value as TimeFormat);
                  setSaved(false);
                }}
                className="mt-1 w-full rounded-xl border border-edge bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-accent focus:ring-2 focus:ring-accent-soft"
              >
                {timeFormatOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>
          </>
        )}
        {error && <p className="text-sm text-danger">{error}</p>}
        {saved && <p className="text-sm text-success">{t("settings.saved")}</p>}
        <Button onClick={handleSave} disabled={loading || saving} className="self-start">
          {t("settings.save")}
        </Button>
      </Card>

      <PasskeySettings />

      <div className="flex flex-col gap-2">
        <div>
          <h2 className="text-lg font-semibold text-ink">{t("addressHistory.title")}</h2>
          <p className="text-xs text-ink-3">{t("addressHistory.description")}</p>
        </div>
        <AddressHistory />
      </div>

      <OrganizationSection />

      <BillingSection />

      <WorkspaceSharing />
    </div>
  );
}

function OrganizationSection() {
  const { t } = useTranslation();
  const { showToast } = useToast();

  const [name, setName] = useState("");
  const [isOrgAdmin, setIsOrgAdmin] = useState(false);
  const [approvalRequiredGoals, setApprovalRequiredGoals] = useState<ComboboxOption[]>([]);
  const [members, setMembers] = useState<OrganizationMemberOut[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [invitations, setInvitations] = useState<InvitationOut[] | null>(null);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviting, setInviting] = useState(false);
  const [inviteError, setInviteError] = useState<string | null>(null);

  const goalOptions: ComboboxOption[] = GOAL_TYPES.map((id) => ({ id, label: t(`settings.orgGoalType.${id}`) }));

  useEffect(() => {
    Promise.all([getOrganization(), listOrganizationMembers()])
      .then(([org, memberList]) => {
        setName(org.name);
        setIsOrgAdmin(org.is_org_admin);
        const approved = org.policies.approval_required_goals;
        const selectedIds = Array.isArray(approved) ? approved.filter((id): id is string => typeof id === "string") : [];
        setApprovalRequiredGoals(goalOptions.filter((option) => selectedIds.includes(option.id)));
        setMembers(memberList);
        if (org.is_org_admin) {
          return listOrganizationInvitations().then(setInvitations);
        }
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : t("settings.orgLoadError")))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleSave() {
    setSaving(true);
    setSaved(false);
    setError(null);
    try {
      await renameOrganization(name);
      await setOrganizationPolicies({ approval_required_goals: approvalRequiredGoals.map((o) => o.id) });
      setSaved(true);
      showToast(t("settings.orgSaved"));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("settings.orgSaveError"));
    } finally {
      setSaving(false);
    }
  }

  async function handleInvite() {
    setInviting(true);
    setInviteError(null);
    try {
      const invitation = await inviteOrganizationMember(inviteEmail);
      setInvitations((prev) => [...(prev ?? []).filter((i) => i.id !== invitation.id), invitation]);
      setInviteEmail("");
      showToast(t("settings.orgInviteSent"));
    } catch (err) {
      setInviteError(err instanceof ApiError ? err.message : t("settings.orgInviteError"));
    } finally {
      setInviting(false);
    }
  }

  async function handleRevoke(id: string) {
    try {
      await revokeOrganizationInvitation(id);
      setInvitations((prev) => (prev ?? []).filter((i) => i.id !== id));
    } catch (err) {
      setInviteError(err instanceof ApiError ? err.message : t("settings.orgInviteError"));
    }
  }

  return (
    <Card className="flex max-w-md flex-col gap-3">
      <h2 className="text-lg font-semibold text-ink">{t("settings.orgTitle")}</h2>

      {loading ? (
        <p className="text-sm text-ink-3">{t("common.loading")}</p>
      ) : (
        <>
          <div>
            <label className="text-sm font-medium text-ink" htmlFor="org-name">
              {t("settings.orgNameLabel")}
            </label>
            {isOrgAdmin ? (
              <input
                id="org-name"
                value={name}
                onChange={(e) => {
                  setName(e.target.value);
                  setSaved(false);
                }}
                className="mt-1 w-full rounded-xl border border-edge bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-accent focus:ring-2 focus:ring-accent-soft"
              />
            ) : (
              <p className="mt-1 text-sm text-ink">{name}</p>
            )}
          </div>

          {isOrgAdmin && (
            <div>
              <label className="text-sm font-medium text-ink">{t("settings.orgApprovalRequiredLabel")}</label>
              <p className="mb-1 text-xs text-ink-3">{t("settings.orgApprovalRequiredHint")}</p>
              <Combobox
                options={goalOptions}
                selected={approvalRequiredGoals}
                onChange={(next) => {
                  setApprovalRequiredGoals(next);
                  setSaved(false);
                }}
                placeholder={t("settings.orgApprovalRequiredPlaceholder")}
              />
            </div>
          )}

          <div>
            <span className="text-sm font-medium text-ink">{t("settings.orgMembersLabel")}</span>
            <ul className="mt-1 flex flex-col gap-1.5">
              {members?.map((member) => (
                <li key={member.id} className="flex items-center justify-between gap-2 text-sm text-ink">
                  <span>
                    {member.display_name} <span className="text-ink-3">({member.username})</span>
                  </span>
                  <Badge variant={member.role === "admin" ? "warning" : "default"}>{member.role}</Badge>
                </li>
              ))}
            </ul>
          </div>

          {isOrgAdmin && (
            <div>
              <label className="text-sm font-medium text-ink" htmlFor="org-invite-email">
                {t("settings.orgInviteLabel")}
              </label>
              <div className="mt-1 flex gap-2">
                <input
                  id="org-invite-email"
                  type="email"
                  value={inviteEmail}
                  onChange={(e) => setInviteEmail(e.target.value)}
                  placeholder={t("settings.orgInvitePlaceholder")}
                  className="flex-1 rounded-xl border border-edge bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-accent focus:ring-2 focus:ring-accent-soft"
                />
                <Button onClick={handleInvite} disabled={inviting || !inviteEmail} className="shrink-0">
                  {inviting ? t("settings.orgInviteSubmitting") : t("settings.orgInviteButton")}
                </Button>
              </div>
              {inviteError && <p className="mt-1 text-sm text-danger">{inviteError}</p>}

              {invitations && invitations.length > 0 && (
                <ul className="mt-3 flex flex-col gap-1.5">
                  {invitations.map((invitation) => (
                    <li key={invitation.id} className="flex items-center justify-between gap-2 text-sm text-ink">
                      <span>{invitation.email}</span>
                      <Button variant="ghost" size="sm" onClick={() => handleRevoke(invitation.id)}>
                        {t("settings.orgRevokeInvitation")}
                      </Button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}

          {error && <p className="text-sm text-danger">{error}</p>}
          {saved && <p className="text-sm text-success">{t("settings.saved")}</p>}
          {isOrgAdmin && (
            <Button onClick={handleSave} disabled={saving} className="self-start">
              {t("settings.save")}
            </Button>
          )}
        </>
      )}
    </Card>
  );
}

function BillingSection() {
  const { t } = useTranslation();
  const [searchParams, setSearchParams] = useSearchParams();
  const [isOrgAdmin, setIsOrgAdmin] = useState(false);
  const [subscription, setSubscription] = useState<SubscriptionOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [redirecting, setRedirecting] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const autoCheckoutTriggered = useRef(false);

  useEffect(() => {
    Promise.all([getOrganization(), getSubscription()])
      .then(([org, sub]) => {
        setIsOrgAdmin(org.is_org_admin);
        setSubscription(sub);
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : t("settings.billingLoadError")))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Picks up a plan chosen on Landing.tsx's pricing cards before the visitor
  // had an account (ADR 0074, lib/pendingPlan.ts) -- VerifyEmail.tsx routes
  // here with ?checkout=<plan> right after signup completes, so the user
  // lands straight in Stripe Checkout instead of having to re-pick the plan.
  useEffect(() => {
    const checkoutPlan = searchParams.get("checkout");
    if (!checkoutPlan || loading || !isOrgAdmin || autoCheckoutTriggered.current) return;
    autoCheckoutTriggered.current = true;
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.delete("checkout");
      return next;
    });
    handleCheckout(checkoutPlan);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loading, isOrgAdmin, searchParams]);

  async function handleCheckout(plan: string) {
    setRedirecting(plan);
    setError(null);
    try {
      window.location.href = await createCheckoutSession(plan);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("settings.billingCheckoutError"));
      setRedirecting(null);
    }
  }

  async function handleManageBilling() {
    setRedirecting("portal");
    setError(null);
    try {
      window.location.href = await createPortalSession();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("settings.billingPortalError"));
      setRedirecting(null);
    }
  }

  const hasActivePlan = Boolean(subscription?.plan && subscription.status && subscription.status !== "canceled");

  return (
    <Card className="flex max-w-md flex-col gap-3">
      <h2 className="text-lg font-semibold text-ink">{t("settings.billingTitle")}</h2>

      {loading ? (
        <p className="text-sm text-ink-3">{t("common.loading")}</p>
      ) : (
        <>
          {hasActivePlan ? (
            <div className="flex items-center justify-between gap-2 text-sm text-ink">
              <span>{t("settings.billingCurrentPlan", { plan: subscription?.plan })}</span>
              <Badge variant={subscription?.status === "active" ? "success" : "warning"}>
                {subscription?.status}
              </Badge>
            </div>
          ) : (
            <p className="text-sm text-ink-2">{t("settings.billingNoPlan")}</p>
          )}

          {error && <p className="text-sm text-danger">{error}</p>}

          {isOrgAdmin && (
            <div className="flex flex-wrap gap-2">
              <Button onClick={() => handleCheckout("starter")} disabled={redirecting !== null} variant="secondary">
                {redirecting === "starter" ? t("settings.billingRedirecting") : t("settings.billingChooseStarter")}
              </Button>
              <Button onClick={() => handleCheckout("pro")} disabled={redirecting !== null}>
                {redirecting === "pro" ? t("settings.billingRedirecting") : t("settings.billingChoosePro")}
              </Button>
              {hasActivePlan && (
                <Button onClick={handleManageBilling} disabled={redirecting !== null} variant="ghost">
                  {redirecting === "portal" ? t("settings.billingRedirecting") : t("settings.billingManage")}
                </Button>
              )}
            </div>
          )}
        </>
      )}
    </Card>
  );
}
