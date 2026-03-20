/**
 * Landing.jsx — ConfidenceOS landing page
 * Inspired by primeintellect.ai — dark, minimal, bold typography
 *
 * Usage: import this in main.jsx and route "/" to Landing, "/app" to App
 */

import { useEffect, useRef } from "react";
import BotIcon from "./BotIcon";

const NAV_LINKS = ["FEATURES", "HOW IT WORKS", "STACK", "ABOUT"];

const FEATURES = [
  {
    num: "01",
    title: "Mock Interview.",
    sub: "Practice with a real AI interviewer and get scored on every answer.",
    desc: "ConfidenceOS asks you real behavioral, situational, and technical questions. After each answer it scores your STAR structure, language confidence, and relevance — then asks the next question.",
  },
  {
    num: "02",
    title: "CBT Reframe.",
    sub: "Identify and reframe the negative thoughts holding you back.",
    desc: "Powered by Cognitive Behavioral Therapy frameworks indexed in the knowledge base. ConfidenceOS detects cognitive distortions in your messages and guides you through evidence-based reframing techniques.",
  },
  {
    num: "03",
    title: "Negotiate.",
    sub: "Walk into salary negotiations with a clear strategy.",
    desc: "Grounded in Principled Negotiation from Getting to Yes. ConfidenceOS helps you understand your BATNA, craft your counter, and role-play the conversation before the real one.",
  },
  {
    num: "04",
    title: "STAR Coach.",
    sub: "Turn rough stories into compelling interview answers.",
    desc: "Guide through the Situation-Task-Action-Result method. ConfidenceOS asks targeted questions to draw out each component, then synthesises your answer into a polished, interview-ready response.",
  },
];

const STACK = [
  { label: "LLM",        value: "Ollama — llama3.2",           note: "Runs locally. Zero API cost." },
  { label: "Embeddings", value: "nomic-embed-text",             note: "768-dim, fully local." },
  { label: "Agent",      value: "LangGraph",                    note: "Multi-step agentic loop." },
  { label: "Vector DB",  value: "Pinecone",                     note: "Semantic document search." },
  { label: "Graph DB",   value: "Neo4j AuraDB",                 note: "Relationship traversal." },
  { label: "Backend",    value: "FastAPI",                      note: "REST API, async." },
  { label: "Frontend",   value: "React + Vite + Tailwind",      note: "No SSR. Fast." },
  { label: "Memory",     value: "LangGraph MemorySaver",        note: "Session persistence." },
];

const HOW_IT_WORKS = [
  { step: "01", title: "Pick a mode",    desc: "Choose from Mock Interview, CBT Reframe, Negotiation, STAR Coach, or open chat." },
  { step: "02", title: "Speak or type",  desc: "Answer using your voice or keyboard. ConfidenceOS transcribes and processes your input." },
  { step: "03", title: "Get scored",     desc: "Receive real-time scores on STAR structure, language confidence, and relevance." },
  { step: "04", title: "Improve",        desc: "Apply the tips, retry the question, and watch your confidence score climb." },
];

export default function Landing() {
  const canvasRef = useRef(null);

  // Subtle animated dot grid background
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    let w = canvas.width  = window.innerWidth;
    let h = canvas.height = window.innerHeight;

    const resize = () => { w = canvas.width = window.innerWidth; h = canvas.height = window.innerHeight; };
    window.addEventListener("resize", resize);

    const dots = Array.from({ length: 120 }, () => ({
      x: Math.random() * w, y: Math.random() * h,
      r: Math.random() * 1.2 + 0.3,
      a: Math.random() * 0.4 + 0.05,
      dy: Math.random() * 0.15 + 0.05,
    }));

    let animId;
    const draw = () => {
      ctx.clearRect(0, 0, w, h);
      dots.forEach(d => {
        ctx.beginPath();
        ctx.arc(d.x, d.y, d.r, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(74,222,128,${d.a})`;
        ctx.fill();
        d.y -= d.dy;
        if (d.y < -5) { d.y = h + 5; d.x = Math.random() * w; }
      });
      animId = requestAnimationFrame(draw);
    };
    draw();
    return () => { window.removeEventListener("resize", resize); cancelAnimationFrame(animId); };
  }, []);

  return (
    <div style={{ fontFamily: "'Inter', system-ui, sans-serif" }}
      className="min-h-screen bg-black text-white overflow-x-hidden">

      {/* Animated canvas background */}
      <canvas ref={canvasRef} className="fixed inset-0 pointer-events-none opacity-30" style={{ zIndex: 0 }} />

      {/* ── NAV ─────────────────────────────────────────────────────────── */}
      <nav className="fixed top-0 left-0 right-0 z-50 border-b border-white/10 bg-black/80 backdrop-blur-sm">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <BotIcon size={28} />
            <span className="text-sm font-semibold tracking-widest uppercase text-white">ConfidenceOS</span>
          </div>
          <div className="hidden md:flex items-center gap-8">
            {NAV_LINKS.map(l => (
              <a key={l} href={`#${l.toLowerCase().replace(" ", "-")}`}
                className="text-xs text-white/50 hover:text-white transition-colors tracking-widest">{l}</a>
            ))}
          </div>
          <a href="/app"
            className="flex items-center gap-2 border border-green-500 text-green-400 text-xs font-semibold px-4 py-2 hover:bg-green-500 hover:text-black transition-all tracking-widest uppercase">
            LAUNCH APP →
          </a>
        </div>
      </nav>

      {/* ── HERO ────────────────────────────────────────────────────────── */}
      <section className="relative z-10 min-h-screen flex flex-col items-center justify-center text-center px-6 pt-20">
        <div className="mb-6 inline-flex items-center gap-2 border border-white/10 px-4 py-1.5 text-xs text-white/40 tracking-widest uppercase">
          <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse inline-block"></span>
          Local · Private · Free
        </div>

        <h1 className="text-5xl md:text-7xl lg:text-8xl font-bold tracking-tight leading-none mb-6 max-w-5xl">
          The AI Coach That<br />
          <span className="text-transparent bg-clip-text"
            style={{ backgroundImage: "linear-gradient(90deg, #4ade80, #22d3ee)" }}>
            Builds Confidence.
          </span>
        </h1>

        <p className="text-white/50 text-lg md:text-xl max-w-2xl mb-10 leading-relaxed">
          Practice interviews, reframe self-doubt, negotiate offers, and craft
          compelling answers — powered by a local LLM, RAG, and a knowledge graph.
          Runs entirely on your machine.
        </p>

        <div className="flex items-center gap-4">
          <a href="/app"
            className="flex items-center gap-2 bg-green-500 text-black text-sm font-bold px-6 py-3 hover:bg-green-400 transition-colors tracking-widest uppercase">
            GET STARTED →
          </a>
          <a href="#how-it-works"
            className="text-sm text-white/40 hover:text-white transition-colors tracking-widest uppercase border border-white/10 px-6 py-3 hover:border-white/30"
            onClick={e => { e.preventDefault(); document.getElementById('how-it-works')?.scrollIntoView({ behavior: 'smooth' }); }}>
            HOW IT WORKS
          </a>
        </div>

        {/* Scroll indicator */}
        <div className="absolute bottom-10 left-1/2 -translate-x-1/2 flex flex-col items-center gap-2 text-white/20">
          <span className="text-xs tracking-widest">SCROLL</span>
          <div className="w-px h-8 bg-gradient-to-b from-white/20 to-transparent"></div>
        </div>
      </section>

      {/* ── FEATURES ────────────────────────────────────────────────────── */}
      <section id="features" className="relative z-10 border-t border-white/10 py-24 px-6">
        <div className="max-w-6xl mx-auto">
          <div className="mb-16">
            <p className="text-xs text-white/30 tracking-widest uppercase mb-3 font-mono">Features</p>
            <h2 className="text-3xl md:text-4xl font-bold">
              Four modes.<br />One mission.
            </h2>
          </div>

          <div className="space-y-0">
            {FEATURES.map((f, i) => (
              <div key={f.num}
                className="group border-t border-white/10 py-10 grid grid-cols-1 md:grid-cols-12 gap-6 hover:border-green-500/30 transition-colors cursor-default">
                <div className="md:col-span-1">
                  <span className="text-xs font-mono text-white/20 group-hover:text-green-500 transition-colors">{f.num}</span>
                </div>
                <div className="md:col-span-4">
                  <h3 className="text-xl font-bold text-white group-hover:text-green-400 transition-colors">{f.title}</h3>
                  <p className="text-white/40 text-sm mt-1">{f.sub}</p>
                </div>
                <div className="md:col-span-7">
                  <p className="text-white/50 leading-relaxed">{f.desc}</p>
                </div>
              </div>
            ))}
            <div className="border-t border-white/10"></div>
          </div>
        </div>
      </section>

      {/* ── HOW IT WORKS ────────────────────────────────────────────────── */}
      <section id="how-it-works" className="relative z-10 border-t border-white/10 py-24 px-6 bg-white/[0.02]">
        <div className="max-w-6xl mx-auto">
          <div className="mb-16">
            <p className="text-xs text-white/30 tracking-widest uppercase mb-3 font-mono">How It Works</p>
            <h2 className="text-3xl md:text-4xl font-bold">Four steps to a better interview.</h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {HOW_IT_WORKS.map(s => (
              <div key={s.step} className="border border-white/10 p-6 hover:border-green-500/30 transition-colors">
                <div className="text-xs font-mono text-green-500 mb-4">{s.step}</div>
                <h3 className="text-lg font-bold mb-2">{s.title}</h3>
                <p className="text-white/40 text-sm leading-relaxed">{s.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── TECH STACK ──────────────────────────────────────────────────── */}
      <section id="stack" className="relative z-10 border-t border-white/10 py-24 px-6">
        <div className="max-w-6xl mx-auto">
          <div className="mb-16">
            <p className="text-xs text-white/30 tracking-widest uppercase mb-3 font-mono">Stack</p>
            <h2 className="text-3xl md:text-4xl font-bold">
              Production-grade.<br />Runs on your laptop.
            </h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-0">
            {STACK.map((s, i) => (
              <div key={s.label}
                className={`flex items-center justify-between py-5 px-4 border-t border-white/10 hover:bg-white/[0.02] transition-colors
                  ${i % 2 === 0 ? "md:border-r md:border-white/10" : ""}`}>
                <div>
                  <span className="text-xs font-mono text-white/30 uppercase tracking-widest block mb-1">{s.label}</span>
                  <span className="text-white font-medium">{s.value}</span>
                </div>
                <span className="text-xs text-white/25 font-mono text-right max-w-[140px]">{s.note}</span>
              </div>
            ))}
            <div className="border-t border-white/10 md:col-span-2"></div>
          </div>
        </div>
      </section>

      {/* ── ABOUT / CTA ─────────────────────────────────────────────────── */}
      <section id="about" className="relative z-10 border-t border-white/10 py-24 px-6 bg-white/[0.02]">
        <div className="max-w-6xl mx-auto grid grid-cols-1 md:grid-cols-2 gap-16 items-center">
          <div>
            <p className="text-xs text-white/30 tracking-widest uppercase mb-3 font-mono">About</p>
            <h2 className="text-3xl md:text-4xl font-bold mb-6">
              Built by a job seeker,<br />for job seekers.
            </h2>
            <p className="text-white/50 leading-relaxed mb-4">
              Landing a great job is not just about skills — it is about showing up
              with clarity and confidence. ConfidenceOS combines CBT, principled
              negotiation, and agentic AI into a single coaching tool.
            </p>
            <p className="text-white/50 leading-relaxed">
              Runs entirely locally. No subscriptions. No data sent to third parties.
              Your conversations stay on your machine.
            </p>
          </div>
          <div className="border border-white/10 p-8">
            <h3 className="text-xl font-bold mb-6">Start practicing today.</h3>
            <ul className="space-y-3 mb-8">
              {["Zero API cost — runs on Ollama", "Voice input for realistic practice", "Live confidence scoring", "CBT + negotiation knowledge base"].map(f => (
                <li key={f} className="flex items-center gap-3 text-sm text-white/60">
                  <span className="text-green-500 font-mono">✓</span>{f}
                </li>
              ))}
            </ul>
            <a href="/app"
              className="w-full flex items-center justify-center gap-2 bg-green-500 text-black text-sm font-bold py-3 hover:bg-green-400 transition-colors tracking-widest uppercase">
              LAUNCH CONFIDENCEOS →
            </a>
          </div>
        </div>
      </section>

      {/* ── CREDITS / DEVELOPER NOTES ───────────────────────────────────── */}
      <section className="relative z-10 border-t border-white/10 py-16 px-6">
        <div className="max-w-6xl mx-auto">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-10">

            {/* Built by */}
            <div>
              <p className="text-xs text-white/30 tracking-widest uppercase mb-4 font-mono">Built by</p>
              <p className="text-white font-semibold mb-1">Kirthi</p>
              <p className="text-white/40 text-sm leading-relaxed">
                Senior AI Engineer & Data Scientist. Built ConfidenceOS as a portfolio project
                to demonstrate end-to-end agentic AI system design.
              </p>
              <div className="flex gap-3 mt-4">
                <a href="https://github.com/kirthistaank/MIDS" target="_blank" rel="noreferrer"
                  className="text-xs text-white/30 hover:text-white transition-colors font-mono tracking-widest">
                  GITHUB →
                </a>
                <a href="https://linkedin.com/in/kirthishanbhag" target="_blank" rel="noreferrer"
                  className="text-xs text-white/30 hover:text-white transition-colors font-mono tracking-widest">
                  LINKEDIN →
                </a>
              </div>
            </div>

            {/* Developer notes */}
            <div>
              <p className="text-xs text-white/30 tracking-widest uppercase mb-4 font-mono">Developer notes</p>
              <ul className="space-y-2">
                {[
                  "All LLM inference runs locally via Ollama — zero API costs",
                  "Prompts are fully decoupled in prompts.py — edit without touching logic",
                  "Logs rotate at 128MB, max 3 files, at /tmp/confidenceos/",
                  "RAG retrieval traces logged per chunk for full observability",
                  "Voice input uses Web Speech API — Chrome/Edge only",
                ].map(n => (
                  <li key={n} className="flex items-start gap-2 text-xs text-white/40">
                    <span className="text-white/20 shrink-0 font-mono mt-0.5">//</span>{n}
                  </li>
                ))}
              </ul>
            </div>

            {/* Open source */}
            <div>
              <p className="text-xs text-white/30 tracking-widest uppercase mb-4 font-mono">Open source</p>
              <p className="text-white/40 text-sm leading-relaxed mb-4">
                ConfidenceOS is open source under the MIT License.
                Contributions, feedback, and forks are welcome.
              </p>
              <ul className="space-y-2">
                {[
                  { label: "License",     value: "MIT" },
                  { label: "Version",     value: "2.0.0" },
                  { label: "Status",      value: "Work in Progress" },
                  { label: "Issues",      value: "GitHub Issues" },
                ].map(({ label, value }) => (
                  <li key={label} className="flex gap-3 text-xs font-mono">
                    <span className="text-white/20 w-20 shrink-0">{label}</span>
                    <span className="text-white/50">{value}</span>
                  </li>
                ))}
              </ul>
              <a href="https://github.com" target="_blank" rel="noreferrer"
                className="inline-flex items-center gap-2 mt-5 border border-white/20 text-white/50 hover:text-white hover:border-white/40 text-xs font-mono px-4 py-2 transition-colors tracking-widest uppercase">
                VIEW ON GITHUB →
              </a>
            </div>

          </div>
        </div>
      </section>

      {/* ── FOOTER ──────────────────────────────────────────────────────── */}
      <footer className="relative z-10 border-t border-white/10 py-8 px-6">
        <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <BotIcon size={20} />
            <span className="text-xs text-white/20 tracking-widest uppercase">ConfidenceOS</span>
          </div>
          <p className="text-xs text-white/20 font-mono">
            Local · Private · Open Source · WIP
          </p>
          <p className="text-xs text-white/20">
            Built with LangGraph · Pinecone · Neo4j · Ollama
          </p>
        </div>
      </footer>

    </div>
  );
}