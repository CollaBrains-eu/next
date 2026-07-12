import { motion, useScroll, useTransform } from "framer-motion";
import { useRef, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Sparkles, FileText, CheckSquare, FolderOpen, Brain, ArrowDown, ChevronRight } from "lucide-react";

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
  const { t } = useTranslation();
  const navigate = useNavigate();
  const heroRef = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({ target: heroRef, offset: ["start start", "end start"] });
  const heroY = useTransform(scrollYProgress, [0, 1], [0, -80]);
  const heroOpacity = useTransform(scrollYProgress, [0, 0.7], [1, 0]);

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

  function goToLogin() {
    navigate("/login");
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
        <button
          onClick={goToLogin}
          className="rounded-full border border-zinc-700 px-4 py-1.5 text-sm text-zinc-300 transition-colors hover:border-zinc-500 hover:text-white"
        >
          {t("landing.navLogin")}
        </button>
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
            <MagneticButton onClick={goToLogin}>
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

      <Section>
        <div className="relative mx-auto max-w-2xl overflow-hidden rounded-3xl bg-gradient-to-br from-violet-600 to-violet-800 px-8 py-16 text-center shadow-2xl">
          <GradientOrb className="-top-20 -right-20 h-64 w-64 bg-violet-400/30" />
          <h2 className="relative mb-4 text-3xl font-bold text-white">{t("landing.ctaTitle")}</h2>
          <p className="relative mb-8 text-violet-200">{t("landing.ctaSubtitle")}</p>
          <MagneticButton onClick={goToLogin}>
            {t("landing.ctaPrimary")} <ChevronRight className="h-4 w-4" />
          </MagneticButton>
        </div>
      </Section>

      <footer className="border-t border-zinc-800 px-6 py-8 text-center text-sm text-zinc-500">{t("landing.footer")}</footer>
    </div>
  );
}
