import { useEffect, useState, type ComponentType } from "react";
import { Link, useSearchParams } from "react-router";
import { useTranslation } from "react-i18next";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import {
  Brain,
  Building2,
  Check,
  ChevronRight,
  FileText,
  Sparkles,
  User,
  Users,
  Workflow,
} from "lucide-react";
import { checkOnboardingToken } from "../lib/api";
import { useAuth } from "../lib/auth";
import { BrandMark } from "../components/BrandMark";
import { Button } from "../components/ui/Button";
import { SkeletonLines } from "../components/ui/Skeleton";
import { Stepper } from "../components/ui/Stepper";

type TokenStatus = "loading" | "valid" | "invalid";

function BrandHeader() {
  return (
    <div className="mb-6 flex items-center justify-center gap-2">
      <BrandMark size={32} />
      <span className="text-lg font-semibold text-ink">
        Collabr
        <span className="bg-clip-text text-transparent" style={{ backgroundImage: "var(--gradient-brand)" }}>
          AI
        </span>
        ns
      </span>
    </div>
  );
}

// The original onboarding surface: an admin invited this person by email,
// they clicked a "welcome, claim your account" link with a one-time token.
// Unrelated to the self-service wizard below -- kept byte-for-byte in
// behavior (existing Onboard.test.tsx pins it).
function ClaimFlow({ token }: { token: string }) {
  const { t } = useTranslation();
  const [status, setStatus] = useState<TokenStatus>("loading");
  const [displayName, setDisplayName] = useState<string | null>(null);

  useEffect(() => {
    checkOnboardingToken(token)
      .then((result) => {
        if (result.valid) {
          setDisplayName(result.display_name);
          setStatus("valid");
        } else {
          setStatus("invalid");
        }
      })
      .catch(() => setStatus("invalid"));
  }, [token]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-page p-4">
      <div className="glass-surface w-full max-w-sm rounded-ds-lg p-6 text-center shadow-raised">
        <BrandHeader />

        {status === "loading" && <SkeletonLines />}

        {status === "valid" && (
          <>
            <h1 className="text-2xl font-semibold text-ink">{t("onboard.welcomeTitle", { name: displayName })}</h1>
            <p className="mt-2 text-sm text-ink-2">{t("onboard.welcomeBody")}</p>
            <Link to="/login" className="mt-6 block">
              <Button className="w-full">{t("onboard.continueToLogin")}</Button>
            </Link>
          </>
        )}

        {status === "invalid" && (
          <>
            <h1 className="text-2xl font-semibold text-ink">{t("onboard.invalidTitle")}</h1>
            <p className="mt-2 text-sm text-ink-2">{t("onboard.invalidBody")}</p>
            <Link to="/login" className="mt-6 block">
              <Button variant="secondary" className="w-full">
                {t("onboard.continueToLogin")}
              </Button>
            </Link>
          </>
        )}
      </div>
    </div>
  );
}

function InvalidLink() {
  const { t } = useTranslation();
  return (
    <div className="flex min-h-screen items-center justify-center bg-page p-4">
      <div className="glass-surface w-full max-w-sm rounded-ds-lg p-6 text-center shadow-raised">
        <BrandHeader />
        <h1 className="text-2xl font-semibold text-ink">{t("onboard.invalidTitle")}</h1>
        <p className="mt-2 text-sm text-ink-2">{t("onboard.invalidBody")}</p>
        <Link to="/login" className="mt-6 block">
          <Button variant="secondary" className="w-full">
            {t("onboard.continueToLogin")}
          </Button>
        </Link>
      </div>
    </div>
  );
}

type WorkspaceType = "personal" | "team" | "organization";
type OrganizeFocus = "documents" | "projects" | "knowledge" | "workflows";

const WORKSPACE_TYPES: { value: WorkspaceType; icon: ComponentType<{ className?: string }>; titleKey: string; descKey: string }[] = [
  { value: "personal", icon: User, titleKey: "onboard.wizardTypePersonal", descKey: "onboard.wizardTypePersonalDesc" },
  { value: "team", icon: Users, titleKey: "onboard.wizardTypeTeam", descKey: "onboard.wizardTypeTeamDesc" },
  { value: "organization", icon: Building2, titleKey: "onboard.wizardTypeOrg", descKey: "onboard.wizardTypeOrgDesc" },
];

const ORGANIZE_FOCUSES: { value: OrganizeFocus; icon: ComponentType<{ className?: string }>; titleKey: string }[] = [
  { value: "documents", icon: FileText, titleKey: "onboard.wizardOrganizeDocuments" },
  { value: "projects", icon: Workflow, titleKey: "onboard.wizardOrganizeProjects" },
  { value: "knowledge", icon: Brain, titleKey: "onboard.wizardOrganizeKnowledge" },
  { value: "workflows", icon: Sparkles, titleKey: "onboard.wizardOrganizeWorkflows" },
];

function ChoiceCard({
  icon: Icon,
  title,
  desc,
  selected,
  onClick,
}: {
  icon: ComponentType<{ className?: string }>;
  title: string;
  desc?: string;
  selected: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={selected}
      className={`flex w-full items-center gap-3 rounded-xl border p-3.5 text-left transition-colors duration-fast ${
        selected ? "border-accent bg-accent-soft" : "border-edge bg-surface hover:border-accent/50"
      }`}
    >
      <div
        className={`flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg ${
          selected ? "bg-accent text-white" : "bg-hover text-ink-2"
        }`}
      >
        <Icon className="h-4 w-4" />
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-semibold text-ink">{title}</p>
        {desc && <p className="text-xs text-ink-2">{desc}</p>}
      </div>
      {selected && <Check className="h-4 w-4 flex-shrink-0 text-accent" />}
    </button>
  );
}

// Runs a short, sequential "setting things up" checklist automatically
// (Analyzing goals -> Organizing workspace -> Personalizing AI assistant),
// then calls onDone -- the brief's "AI creates a personalized workspace
// preview" beat. Reduced-motion visitors get the same content near-instantly
// instead of the sequence being skipped, since it's informative, not decoration.
function BuildingStep({ onDone }: { onDone: () => void }) {
  const { t } = useTranslation();
  const prefersReducedMotion = useReducedMotion();
  const [doneCount, setDoneCount] = useState(0);
  const steps = [
    t("onboard.wizardBuildingStep1"),
    t("onboard.wizardBuildingStep2"),
    t("onboard.wizardBuildingStep3"),
  ];
  const stepDelay = prefersReducedMotion ? 150 : 850;

  useEffect(() => {
    if (doneCount >= steps.length) {
      const timer = setTimeout(onDone, stepDelay);
      return () => clearTimeout(timer);
    }
    const timer = setTimeout(() => setDoneCount((c) => c + 1), stepDelay);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [doneCount]);

  return (
    <div className="py-4 text-center">
      <motion.div
        animate={prefersReducedMotion ? undefined : { rotate: 360 }}
        transition={{ duration: 2.5, repeat: Infinity, ease: "linear" }}
        className="mx-auto mb-6 flex h-14 w-14 items-center justify-center rounded-full bg-gradient-brand"
      >
        <Brain className="h-6 w-6 text-white" />
      </motion.div>
      <h2 className="mb-6 text-lg font-semibold text-ink">{t("onboard.wizardBuildingTitle")}</h2>
      <ul className="mx-auto flex max-w-xs flex-col gap-3 text-left">
        {steps.map((label, i) => {
          const complete = i < doneCount;
          const active = i === doneCount;
          return (
            <li key={label} className="flex items-center gap-2.5 text-sm">
              <span
                className={`flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full border-2 ${
                  complete
                    ? "border-accent bg-accent text-white"
                    : active
                      ? "border-accent"
                      : "border-edge"
                }`}
              >
                {complete && <Check className="h-3 w-3" />}
                {active && !complete && !prefersReducedMotion && (
                  <motion.span
                    animate={{ rotate: 360 }}
                    transition={{ duration: 0.8, repeat: Infinity, ease: "linear" }}
                    className="h-2.5 w-2.5 rounded-full border-2 border-accent border-t-transparent"
                  />
                )}
              </span>
              <span className={complete || active ? "text-ink" : "text-ink-3"}>{label}</span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function OnboardWizard({ onComplete }: { onComplete: () => void }) {
  const { t } = useTranslation();
  const { user } = useAuth();
  const [step, setStep] = useState(0);
  const [workspaceType, setWorkspaceType] = useState<WorkspaceType | null>(null);
  const [focus, setFocus] = useState<OrganizeFocus | null>(null);

  const stepLabels = [
    t("onboard.wizardStepWelcome"),
    t("onboard.wizardStepOrganize"),
    t("onboard.wizardStepBuild"),
    t("onboard.wizardStepReady"),
  ];

  const typeLabel = workspaceType
    ? t(WORKSPACE_TYPES.find((w) => w.value === workspaceType)!.titleKey)
    : "";
  const focusLabel = focus ? t(ORGANIZE_FOCUSES.find((f) => f.value === focus)!.titleKey) : "";

  const readyChecklist = [
    t("onboard.wizardReadyChecklistDocs"),
    t("onboard.wizardReadyChecklistAi"),
    t("onboard.wizardReadyChecklistSearch"),
  ];

  return (
    <div className="flex min-h-screen items-center justify-center bg-page p-4">
      <div className="glass-surface w-full max-w-md rounded-ds-lg p-6 shadow-raised sm:p-8">
        <BrandHeader />
        <Stepper steps={stepLabels.map((label) => ({ label }))} currentIndex={step} />

        <div className="mt-6 min-h-[280px]">
          <AnimatePresence mode="wait">
            {step === 0 && (
              <motion.div
                key="welcome"
                initial={{ opacity: 0, x: 24 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -24 }}
                transition={{ duration: 0.25 }}
              >
                <h1 className="mb-1 text-xl font-semibold text-ink">
                  {t("onboard.wizardWelcomeTitle", { name: user?.display_name ?? "" })}
                </h1>
                <p className="mb-5 text-sm text-ink-2">{t("onboard.wizardWelcomeSubtitle")}</p>
                <div className="flex flex-col gap-2.5">
                  {WORKSPACE_TYPES.map(({ value, icon, titleKey, descKey }) => (
                    <ChoiceCard
                      key={value}
                      icon={icon}
                      title={t(titleKey)}
                      desc={t(descKey)}
                      selected={workspaceType === value}
                      onClick={() => setWorkspaceType(value)}
                    />
                  ))}
                </div>
              </motion.div>
            )}

            {step === 1 && (
              <motion.div
                key="organize"
                initial={{ opacity: 0, x: 24 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -24 }}
                transition={{ duration: 0.25 }}
              >
                <h1 className="mb-1 text-xl font-semibold text-ink">{t("onboard.wizardOrganizeTitle")}</h1>
                <p className="mb-5 text-sm text-ink-2">{t("onboard.wizardOrganizeSubtitle")}</p>
                <div className="grid grid-cols-2 gap-2.5">
                  {ORGANIZE_FOCUSES.map(({ value, icon, titleKey }) => (
                    <ChoiceCard
                      key={value}
                      icon={icon}
                      title={t(titleKey)}
                      selected={focus === value}
                      onClick={() => setFocus(value)}
                    />
                  ))}
                </div>
              </motion.div>
            )}

            {step === 2 && (
              <motion.div key="build" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                <BuildingStep onDone={() => setStep(3)} />
              </motion.div>
            )}

            {step === 3 && (
              <motion.div
                key="ready"
                initial={{ opacity: 0, scale: 0.97 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.3 }}
                className="text-center"
              >
                <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-success-soft text-success">
                  <Check className="h-6 w-6" />
                </div>
                <h1 className="mb-1 text-xl font-semibold text-ink">{t("onboard.wizardReadyTitle")}</h1>
                <p className="mb-5 text-sm text-ink-2">
                  {t("onboard.wizardReadySummary", { type: typeLabel, focus: focusLabel.toLowerCase() })}
                </p>
                <ul className="mx-auto mb-6 flex max-w-xs flex-col gap-2 text-left">
                  {readyChecklist.map((label) => (
                    <li key={label} className="flex items-center gap-2 text-sm text-ink-2">
                      <Check className="h-3.5 w-3.5 flex-shrink-0 text-success" />
                      {label}
                    </li>
                  ))}
                </ul>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        <div className="mt-6 flex items-center justify-between gap-3">
          {step > 0 && step < 2 ? (
            <Button variant="ghost" onClick={() => setStep((s) => s - 1)}>
              {t("onboard.wizardBack")}
            </Button>
          ) : (
            <span />
          )}

          {step < 2 && (
            <Button
              onClick={() => setStep((s) => s + 1)}
              disabled={(step === 0 && !workspaceType) || (step === 1 && !focus)}
            >
              {t("onboard.wizardContinue")} <ChevronRight className="ml-1 inline h-4 w-4" />
            </Button>
          )}

          {step === 3 && (
            <Button onClick={onComplete} className="w-full justify-center">
              {t("onboard.wizardEnterWorkspace")} <ChevronRight className="ml-1 inline h-4 w-4" />
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}

// Two unrelated surfaces share this route:
//  - "/onboard?token=..." -- an admin-invited user claiming their account
//    (ClaimFlow, unauthenticated, works with no AuthProvider -- see tests).
//  - The guided self-service wizard, only ever rendered by App.tsx's
//    RootRoute (which passes onComplete) for a freshly-registered,
//    authenticated user -- never reachable by URL alone, so a plain visit to
//    "/onboard" with no token behaves exactly as it always has.
export default function Onboard({ onComplete }: { onComplete?: () => void } = {}) {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token");

  if (token) return <ClaimFlow token={token} />;
  if (onComplete) return <OnboardWizard onComplete={onComplete} />;
  return <InvalidLink />;
}
