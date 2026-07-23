import { motion, useScroll, useTransform } from "framer-motion";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  Sparkles,
  FileText,
  CheckSquare,
  FolderOpen,
  Brain,
  ArrowDown,
  ChevronRight,
  Check,
  Mail,
  HardDrive,
  Camera,
  Zap,
  Users,
  Headphones,
  Building2,
  ShieldCheck,
  Globe,
} from "lucide-react";
import { useClickOutside } from "../hooks/useClickOutside";
import { useEscapeToClose } from "../hooks/useEscapeToClose";
import { setPendingPlan } from "../lib/pendingPlan";

const SUPPORTED_LANGUAGES = [
  { code: "en", label: "English" },
  { code: "nl", label: "Nederlands" },
  { code: "de", label: "Deutsch" },
];

const LANDING_LANG_STORAGE_KEY = "collabrains_landing_lang";

// Countries where the local language should win over English as the landing default.
const COUNTRY_TO_LANGUAGE: Record<string, string> = {
  DE: "de",
  AT: "de",
  CH: "de",
  NL: "nl",
  BE: "nl",
};

function detectBrowserLanguage(): string {
  const browserCode = navigator.language?.slice(0, 2).toLowerCase();
  return SUPPORTED_LANGUAGES.some((l) => l.code === browserCode) ? browserCode : "en";
}

// Best-effort IP geolocation so a Dutch or German visitor gets their language even when
// their OS/browser is set to English. Falls back silently (caller keeps the browser-language
// guess) if the lookup fails, times out, or is blocked -- this must never break the page.
async function detectLanguageFromIp(): Promise<string | null> {
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 2500);
    const res = await fetch("https://ipapi.co/json/", { signal: controller.signal });
    clearTimeout(timeout);
    if (!res.ok) return null;
    const data = await res.json();
    const country = typeof data?.country_code === "string" ? data.country_code.toUpperCase() : "";
    return COUNTRY_TO_LANGUAGE[country] ?? null;
  } catch {
    return null;
  }
}

function LanguageSwitcher() {
  const { i18n } = useTranslation();
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  useClickOutside(rootRef, open, () => setOpen(false));
  useEscapeToClose(open, () => setOpen(false));

  function selectLanguage(code: string) {
    i18n.changeLanguage(code);
    window.localStorage.setItem(LANDING_LANG_STORAGE_KEY, code);
    setOpen(false);
  }

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-label="Change language"
        className="flex items-center gap-1.5 rounded-full border border-zinc-700 px-3 py-1.5 text-sm text-zinc-300 transition-colors hover:border-zinc-500 hover:text-white"
      >
        <Globe className="h-4 w-4" />
        <span className="uppercase">{i18n.language}</span>
      </button>
      <div
        role="menu"
        className={`absolute right-0 top-[calc(100%+6px)] z-20 min-w-[140px] rounded-xl border border-zinc-700 bg-zinc-900 p-1.5 shadow-xl transition-all duration-150 ${
          open ? "pointer-events-auto translate-y-0 scale-100 opacity-100" : "pointer-events-none -translate-y-1.5 scale-[.97] opacity-0"
        }`}
      >
        {SUPPORTED_LANGUAGES.map((lang) => (
          <button
            key={lang.code}
            role="menuitem"
            type="button"
            onClick={() => selectLanguage(lang.code)}
            className={`block w-full rounded-lg px-2.5 py-2 text-left text-sm transition-colors ${
              i18n.language === lang.code ? "bg-violet-600/20 text-violet-300" : "text-zinc-300 hover:bg-zinc-800 hover:text-white"
            }`}
          >
            {lang.label}
          </button>
        ))}
      </div>
    </div>
  );
}

// Marketing splash for anonymous visitors at "/" (see App.tsx RootRoute) -- deliberately
// dark/animated, distinct from the light Violet DS app shell authenticated users see.
function GradientOrb({ className, delay = 0 }: { className?: string; delay?: number }) {
  return (
    <motion.div
      animate={{ scale: [1, 1.15, 1], opacity: [0.4, 0.6, 0.4] }}
      transition={{ duration: 8, repeat: Infinity, delay, ease: "easeInOut" }}
      className={`pointer-events-none absolute rounded-full blur-3xl ${className}`}
    />
  );
}

function MagneticButton({ children, onClick, className = "" }: { children: ReactNode; onClick?: () => void; className?: string }) {
  const btnRef = useRef<HTMLButtonElement>(null);

  function handleMouseMove(e: React.MouseEvent<HTMLButtonElement>) {
    const btn = btnRef.current;
    if (!btn) return;
    const rect = btn.getBoundingClientRect();
    const x = (e.clientX - rect.left - rect.width / 2) * 0.25;
    const y = (e.clientY - rect.top - rect.height / 2) * 0.25;
    btn.style.transform = `translate(${x}px, ${y}px)`;
  }

  function handleMouseLeave() {
    if (btnRef.current) btnRef.current.style.transform = "";
  }

  return (
    <button
      ref={btnRef}
      onClick={onClick}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      className={`relative inline-flex items-center gap-2 rounded-full bg-gradient-to-r from-violet-600 to-violet-500 px-7 py-3.5 text-sm font-semibold text-white shadow-lg shadow-violet-600/30 transition-shadow duration-200 hover:shadow-xl hover:shadow-violet-600/40 ${className}`}
    >
      {children}
    </button>
  );
}

function Section({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <motion.section
      initial={{ opacity: 0, y: 40 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-100px" }}
      transition={{ duration: 0.7, ease: "easeOut" }}
      className={`relative px-6 py-24 ${className}`}
    >
      {children}
    </motion.section>
  );
}

export default function Landing() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const heroRef = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({ target: heroRef, offset: ["start start", "end start"] });
  const heroY = useTransform(scrollYProgress, [0, 1], [0, -80]);
  const heroOpacity = useTransform(scrollYProgress, [0, 0.7], [1, 0]);

  useEffect(() => {
    const saved = window.localStorage.getItem(LANDING_LANG_STORAGE_KEY);
    if (saved && SUPPORTED_LANGUAGES.some((l) => l.code === saved)) {
      i18n.changeLanguage(saved);
      return;
    }
    i18n.changeLanguage(detectBrowserLanguage());
    let cancelled = false;
    detectLanguageFromIp().then((geoLanguage) => {
      if (!cancelled && geoLanguage) i18n.changeLanguage(geoLanguage);
    });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const FEATURES = [
    { icon: FileText, title: t("landing.featureDocsTitle"), desc: t("landing.featureDocsDesc") },
    { icon: CheckSquare, title: t("landing.featureTasksTitle"), desc: t("landing.featureTasksDesc") },
    { icon: FolderOpen, title: t("landing.featureCasesTitle"), desc: t("landing.featureCasesDesc") },
    { icon: Brain, title: t("landing.featureAiTitle"), desc: t("landing.featureAiDesc") },
  ];

  const PROBLEM_CHIPS = [
    t("landing.problemChipEmail"),
    t("landing.problemChipFiles"),
    t("landing.problemChipChats"),
    t("landing.problemChipMeetings"),
  ];

  const PREMIUM_FEATURES = [
    { icon: Mail, title: t("landing.premiumFeatureEmailTitle"), desc: t("landing.premiumFeatureEmailDesc") },
    { icon: HardDrive, title: t("landing.premiumFeatureDriveTitle"), desc: t("landing.premiumFeatureDriveDesc") },
    { icon: Camera, title: t("landing.premiumFeaturePhotosTitle"), desc: t("landing.premiumFeaturePhotosDesc") },
    { icon: Zap, title: t("landing.premiumFeatureAiTitle"), desc: t("landing.premiumFeatureAiDesc") },
    { icon: Users, title: t("landing.premiumFeatureWorkspacesTitle"), desc: t("landing.premiumFeatureWorkspacesDesc") },
    { icon: Headphones, title: t("landing.premiumFeatureSupportTitle"), desc: t("landing.premiumFeatureSupportDesc") },
  ];

  const PLANS = [
    {
      name: t("landing.planEarlyName"),
      price: t("landing.planEarlyPrice"),
      period: "",
      badge: t("landing.planEarlyBadge"),
      desc: t("landing.planEarlyDesc"),
      features: [t("landing.planEarlyFeature1"), t("landing.planEarlyFeature2"), t("landing.planEarlyFeature3")],
      cta: t("landing.planEarlyCta"),
      highlighted: true,
      // Free tier -- no Stripe plan behind it, just register.
      planId: null,
    },
    {
      name: t("landing.planStarterName"),
      price: t("landing.planStarterPrice"),
      period: t("landing.pricingPeriodMonth"),
      badge: "",
      desc: t("landing.planStarterDesc"),
      features: [t("landing.planStarterFeature1"), t("landing.planStarterFeature2"), t("landing.planStarterFeature3")],
      cta: t("landing.planStarterCta"),
      highlighted: false,
      planId: "starter",
    },
    {
      name: t("landing.planProName"),
      price: t("landing.planProPrice"),
      period: t("landing.pricingPeriodMonth"),
      badge: "",
      desc: t("landing.planProDesc"),
      features: [
        t("landing.planProFeature1"),
        t("landing.planProFeature2"),
        t("landing.planProFeature3"),
        t("landing.planProFeature4"),
      ],
      cta: t("landing.planProCta"),
      highlighted: false,
      planId: "pro",
    },
  ];

  const ENTERPRISE_FEATURES = [
    t("landing.enterpriseFeature1"),
    t("landing.enterpriseFeature2"),
    t("landing.enterpriseFeature3"),
    t("landing.enterpriseFeature4"),
    t("landing.enterpriseFeature5"),
    t("landing.enterpriseFeature6"),
    t("landing.enterpriseFeature7"),
    t("landing.enterpriseFeature8"),
  ];

  const ENTERPRISE_BADGES = [
    { icon: ShieldCheck, label: t("landing.enterpriseBadgeEncrypted") },
    { icon: Headphones, label: t("landing.enterpriseBadgeSupport") },
    { icon: Building2, label: t("landing.enterpriseBadgeRegion") },
  ];

  function goToLogin() {
    navigate("/login");
  }

  // Anonymous visitors evaluating pricing don't have an account yet -- send
  // them to self-service signup (ADR 0074), not the login form. A paid-plan
  // choice is remembered (lib/pendingPlan.ts) so checkout can pick up right
  // where they left off once their account exists.
  function goToRegister(planId?: string | null) {
    if (planId) setPendingPlan(planId);
    navigate("/register");
  }

  return (
    <div className="min-h-screen overflow-x-hidden bg-zinc-950 text-white">
      <nav className="fixed left-0 right-0 top-0 z-50 flex items-center justify-between px-6 py-4">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-violet-600">
            <Sparkles className="h-4 w-4 text-white" />
          </div>
          <span className="font-semibold text-white">CollaBrains</span>
        </div>
        <div className="flex items-center gap-2">
          <LanguageSwitcher />
          <button
            onClick={goToLogin}
            className="rounded-full border border-zinc-700 px-4 py-1.5 text-sm text-zinc-300 transition-colors hover:border-zinc-500 hover:text-white"
          >
            {t("landing.navLogin")}
          </button>
        </div>
      </nav>

      <div ref={heroRef} className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden px-6 text-center">
        <GradientOrb className="-left-20 -top-20 h-96 w-96 bg-violet-600/40" delay={0} />
        <GradientOrb className="-bottom-10 -right-10 h-80 w-80 bg-blue-600/30" delay={3} />
        <GradientOrb className="left-1/4 top-1/3 h-64 w-64 bg-violet-400/20" delay={6} />

        <motion.div style={{ y: heroY, opacity: heroOpacity }} className="relative z-10 max-w-3xl">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
            className="mb-4 inline-flex items-center gap-2 rounded-full border border-violet-500/30 bg-violet-600/10 px-4 py-1.5 text-xs font-medium text-violet-300"
          >
            <Sparkles className="h-3 w-3" /> {t("landing.badge")}
          </motion.div>

          <motion.h1
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.1 }}
            className="mb-6 text-5xl font-bold leading-tight tracking-tight md:text-6xl"
          >
            {t("landing.heroTitleLine1")}{" "}
            <span className="bg-gradient-to-r from-violet-400 to-blue-400 bg-clip-text text-transparent">
              {t("landing.heroTitleHighlight")}
            </span>{" "}
            <br />
            {t("landing.heroTitleLine2")}
          </motion.h1>

          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.2 }}
            className="mx-auto mb-10 max-w-xl text-lg text-zinc-400"
          >
            {t("landing.heroSubtitle")}
          </motion.p>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.3 }}
            className="flex flex-col items-center gap-4 sm:flex-row sm:justify-center"
          >
            <MagneticButton onClick={() => goToRegister()}>
              {t("landing.ctaPrimary")} <ChevronRight className="h-4 w-4" />
            </MagneticButton>
          </motion.div>
        </motion.div>

        <motion.div
          animate={{ y: [0, 8, 0] }}
          transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
          className="absolute bottom-10 left-1/2 -translate-x-1/2"
        >
          <ArrowDown className="h-5 w-5 text-zinc-500" />
        </motion.div>
      </div>

      <Section className="bg-zinc-900">
        <div className="mx-auto max-w-4xl text-center">
          <p className="mb-4 text-xs font-semibold uppercase tracking-widest text-violet-400">{t("landing.problemEyebrow")}</p>
          <h2 className="mb-6 text-3xl font-bold md:text-4xl">
            {t("landing.problemTitle")} <span className="text-zinc-400">{t("landing.problemTitleMuted")}</span>
          </h2>
          <p className="mx-auto mb-12 max-w-2xl text-lg text-zinc-400">{t("landing.problemSubtitle")}</p>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            {PROBLEM_CHIPS.map((item, i) => (
              <motion.div
                key={item}
                initial={{ opacity: 0, scale: 0.8 }}
                whileInView={{ opacity: 1, scale: 1 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.1 }}
                className="flex flex-col items-center gap-2 rounded-xl border border-zinc-700/50 bg-zinc-800/50 px-4 py-5"
              >
                <div className="h-8 w-8 rounded-lg bg-zinc-700" />
                <span className="text-sm text-zinc-300">{item}</span>
              </motion.div>
            ))}
          </div>
        </div>
      </Section>

      <Section>
        <div className="mx-auto max-w-4xl">
          <p className="mb-4 text-center text-xs font-semibold uppercase tracking-widest text-violet-400">{t("landing.solutionEyebrow")}</p>
          <h2 className="mb-12 text-center text-3xl font-bold md:text-4xl">{t("landing.solutionTitle")}</h2>
          <div className="grid gap-6 sm:grid-cols-2">
            {FEATURES.map(({ icon: Icon, title, desc }, i) => (
              <motion.div
                key={title}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.1 }}
                className="rounded-2xl border border-zinc-800 bg-zinc-900/80 p-6 backdrop-blur"
              >
                <div className="mb-4 inline-flex h-10 w-10 items-center justify-center rounded-xl bg-violet-600/20">
                  <Icon className="h-5 w-5 text-violet-400" />
                </div>
                <h3 className="mb-2 font-semibold text-white">{title}</h3>
                <p className="text-sm text-zinc-400">{desc}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </Section>

      <Section className="bg-zinc-900">
        <div className="mx-auto max-w-3xl">
          <p className="mb-4 text-center text-xs font-semibold uppercase tracking-widest text-violet-400">{t("landing.aiDemoEyebrow")}</p>
          <h2 className="mb-12 text-center text-3xl font-bold md:text-4xl">{t("landing.aiDemoTitle")}</h2>
          <div className="rounded-2xl border border-zinc-700 bg-zinc-800/50 p-6 backdrop-blur">
            {[
              { role: "user", text: t("landing.aiDemoQuestion") },
              { role: "assistant", text: t("landing.aiDemoAnswer") },
            ].map((msg, i) => (
              <motion.div
                key={msg.role}
                initial={{ opacity: 0, x: msg.role === "user" ? 20 : -20 }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.3 }}
                className={`mb-3 flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm ${
                    msg.role === "user" ? "rounded-br-sm bg-violet-600 text-white" : "rounded-bl-sm bg-zinc-700 text-zinc-200"
                  }`}
                >
                  {msg.text}
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </Section>

      <Section className="bg-zinc-900">
        <div className="mx-auto max-w-4xl">
          <p className="mb-4 text-center text-xs font-semibold uppercase tracking-widest text-violet-400">{t("landing.premiumEyebrow")}</p>
          <h2 className="mb-12 text-center text-3xl font-bold md:text-4xl">{t("landing.premiumTitle")}</h2>
          <div className="grid gap-6 sm:grid-cols-2 md:grid-cols-3">
            {PREMIUM_FEATURES.map(({ icon: Icon, title, desc }, i) => (
              <motion.div
                key={title}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.1 }}
                className="rounded-2xl border border-zinc-800 bg-zinc-900/80 p-6 backdrop-blur"
              >
                <div className="mb-4 inline-flex h-10 w-10 items-center justify-center rounded-xl bg-violet-600/20">
                  <Icon className="h-5 w-5 text-violet-400" />
                </div>
                <h3 className="mb-2 font-semibold text-white">{title}</h3>
                <p className="text-sm text-zinc-400">{desc}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </Section>

      <Section>
        <div className="mx-auto max-w-5xl">
          <p className="mb-4 text-center text-xs font-semibold uppercase tracking-widest text-violet-400">{t("landing.pricingEyebrow")}</p>
          <h2 className="mb-4 text-center text-3xl font-bold md:text-4xl">{t("landing.pricingTitle")}</h2>
          <p className="mx-auto mb-12 max-w-xl text-center text-lg text-zinc-400">{t("landing.pricingSubtitle")}</p>
          <div className="mb-10 grid gap-6 md:grid-cols-3">
            {PLANS.map((plan, i) => (
              <motion.div
                key={plan.name}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.1 }}
                className={`relative flex flex-col rounded-2xl border p-8 ${
                  plan.highlighted
                    ? "border-violet-500 bg-zinc-800/80 shadow-xl shadow-violet-600/10"
                    : "border-zinc-800 bg-zinc-900/80"
                }`}
              >
                {plan.badge && (
                  <span className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-violet-600 px-3 py-1 text-xs font-semibold text-white">
                    {plan.badge}
                  </span>
                )}
                <h3 className="mb-1 font-semibold text-white">{plan.name}</h3>
                <p className="mb-4 text-sm text-zinc-400">{plan.desc}</p>
                <div className="mb-6 flex items-baseline gap-1">
                  <span className="text-3xl font-bold text-white">{plan.price}</span>
                  {plan.period && <span className="text-sm text-zinc-500">{plan.period}</span>}
                </div>
                <ul className="mb-8 flex-1 space-y-3">
                  {plan.features.map((feature) => (
                    <li key={feature} className="flex items-start gap-2 text-sm text-zinc-300">
                      <Check className="mt-0.5 h-4 w-4 flex-shrink-0 text-violet-400" />
                      {feature}
                    </li>
                  ))}
                </ul>
                {plan.highlighted ? (
                  <MagneticButton onClick={() => goToRegister(plan.planId)} className="w-full justify-center">
                    {plan.cta}
                  </MagneticButton>
                ) : (
                  <button
                    onClick={() => goToRegister(plan.planId)}
                    className="w-full rounded-full border border-zinc-700 px-7 py-3.5 text-sm font-semibold text-white transition-colors hover:border-zinc-500"
                  >
                    {plan.cta}
                  </button>
                )}
              </motion.div>
            ))}
          </div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="overflow-hidden rounded-2xl border-2 border-violet-800/50"
          >
            <div className="bg-gradient-to-r from-indigo-600 to-violet-600 px-6 py-5">
              <div className="mb-1.5 flex items-center gap-2.5">
                <Building2 className="h-5 w-5 text-white" />
                <span className="text-lg font-bold text-white">{t("landing.enterpriseTitle")}</span>
              </div>
              <p className="text-sm leading-relaxed text-indigo-100">{t("landing.enterpriseSubtitle")}</p>
            </div>
            <div className="bg-zinc-900/80 px-6 py-6">
              <div className="mb-5 grid grid-cols-1 gap-2 sm:grid-cols-2">
                {ENTERPRISE_FEATURES.map((feature) => (
                  <div key={feature} className="flex items-start gap-2">
                    <Check className="mt-0.5 h-3.5 w-3.5 flex-shrink-0 text-violet-400" />
                    <span className="text-xs text-zinc-300">{feature}</span>
                  </div>
                ))}
              </div>
              <div className="mb-5 flex flex-wrap gap-2">
                {ENTERPRISE_BADGES.map(({ icon: Icon, label }) => (
                  <span
                    key={label}
                    className="flex items-center gap-1.5 rounded-full border border-violet-800/50 bg-violet-600/10 px-2.5 py-1 text-[11px] font-medium text-violet-300"
                  >
                    <Icon className="h-3 w-3" />
                    {label}
                  </span>
                ))}
              </div>
              <a
                href="mailto:info@collabrains.eu"
                className="inline-flex items-center gap-2 rounded-full border border-zinc-700 px-6 py-3 text-sm font-semibold text-white transition-colors hover:border-zinc-500"
              >
                {t("landing.enterpriseCta")} <ChevronRight className="h-4 w-4" />
              </a>
            </div>
          </motion.div>
        </div>
      </Section>

      <Section>
        <div className="relative mx-auto max-w-2xl overflow-hidden rounded-3xl bg-gradient-to-br from-violet-600 to-violet-800 px-8 py-16 text-center shadow-2xl">
          <GradientOrb className="-top-20 -right-20 h-64 w-64 bg-violet-400/30" />
          <h2 className="relative mb-4 text-3xl font-bold text-white">{t("landing.ctaTitle")}</h2>
          <p className="relative mb-8 text-violet-200">{t("landing.ctaSubtitle")}</p>
          <MagneticButton onClick={() => goToRegister()}>
            {t("landing.ctaPrimary")} <ChevronRight className="h-4 w-4" />
          </MagneticButton>
        </div>
      </Section>

      <footer className="border-t border-zinc-800 px-6 py-8 text-center text-sm text-zinc-500">
        <p>{t("landing.footer")}</p>
        <nav className="mt-3 flex items-center justify-center gap-4">
          <Link to="/privacy" className="hover:text-zinc-300">
            {t("legalDocs.privacy.title")}
          </Link>
          <Link to="/terms" className="hover:text-zinc-300">
            {t("legalDocs.terms.title")}
          </Link>
          <Link to="/cookies" className="hover:text-zinc-300">
            {t("legalDocs.cookies.title")}
          </Link>
          <Link to="/support" className="hover:text-zinc-300">
            {t("support.title")}
          </Link>
          <Link to="/changelog" className="hover:text-zinc-300">
            {t("changelog.title")}
          </Link>
        </nav>
      </footer>
    </div>
  );
}
