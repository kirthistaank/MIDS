/**
 * Onboarding.jsx — first-time welcome screen shown before the chat.
 * Dismissed on "Get Started" click and never shown again (localStorage flag).
 */

import BotIcon from "./BotIcon";

const MODES = [
  {
    icon: "💬", id: "chat",
    title: "General Chat",
    desc: "Ask anything about your job hunt, career, or interview prep.",
    examples: ["What is the STAR method?", "How do I handle gaps in my resume?", "What should I research before an interview?"],
  },
  {
    icon: "🎤", id: "mock_interview",
    title: "Mock Interview",
    desc: "Practice with a realistic AI interviewer. Get scored on every answer.",
    examples: ["Start a mock interview for a Data Scientist role", "Ask me a behavioral question", "Tell me about yourself"],
  },
  {
    icon: "🧠", id: "cbt_reframe",
    title: "CBT Reframe",
    desc: "Reframe negative thoughts using Cognitive Behavioral Therapy.",
    examples: ["I always freeze in interviews", "Nobody will hire me at my age", "I'm not smart enough for this role"],
  },
  {
    icon: "💰", id: "negotiation",
    title: "Negotiation",
    desc: "Coach for salary and offer negotiation using principled strategies.",
    examples: ["I got an offer for $110k, I wanted $135k", "How do I counter without losing the offer?", "They said the budget is fixed"],
  },
  {
    icon: "⭐", id: "star_coach",
    title: "STAR Coach",
    desc: "Craft compelling behavioral answers using the STAR framework.",
    examples: ["Help me answer: tell me about a conflict", "Describe a time you failed", "What is your biggest weakness?"],
  },
];

export default function Onboarding({ onDone }) {
  return (
    <div className="fixed inset-0 z-50 bg-black flex flex-col overflow-y-auto"
      style={{ fontFamily: "'Courier New', Courier, monospace" }}>

      {/* Header */}
      <div className="border-b border-green-900 px-6 py-5 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <a href="/" title="Back to home"><BotIcon size={40} /></a>
          <div>
            <h1 className="text-green-400 font-bold text-lg tracking-widest uppercase">ConfidenceOS</h1>
            <a href="/" className="text-green-800 hover:text-green-500 text-xs tracking-wider transition-colors font-mono">← back to home</a>
          </div>
        </div>
        <button onClick={onDone}
          className="border border-green-600 text-green-400 hover:bg-green-500 hover:text-black font-bold px-5 py-2 text-xs tracking-widest uppercase transition-colors font-mono">
          GET STARTED →
        </button>
      </div>

      {/* Hero */}
      <div className="px-6 py-10 border-b border-green-900 max-w-3xl">
        <div className="text-xs text-green-700 tracking-widest uppercase mb-3 font-mono">
          &gt; system ready
        </div>
        <h2 className="text-2xl font-bold text-green-300 mb-3 leading-tight">
          Your local AI coach for landing the job.
        </h2>
        <p className="text-green-700 text-sm leading-relaxed max-w-xl">
          ConfidenceOS helps you practice interviews, reframe self-doubt, negotiate
          offers, and craft compelling answers — all running locally on your machine.
          No API costs. No data sent anywhere.
        </p>
      </div>

      {/* Mode cards */}
      <div className="px-6 py-8 flex-1">
        <p className="text-xs text-green-700 tracking-widest uppercase mb-5">&gt; available modes</p>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-10">
          {MODES.map(m => (
            <div key={m.id} className="border border-green-900 bg-zinc-950 rounded p-4 hover:border-green-700 transition-colors">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-lg">{m.icon}</span>
                <span className="text-green-400 font-bold text-sm tracking-wide">{m.title}</span>
              </div>
              <p className="text-green-700 text-xs leading-relaxed mb-3">{m.desc}</p>
              <div className="space-y-1">
                <p className="text-green-900 text-xs uppercase tracking-widest mb-1">&gt; try saying</p>
                {m.examples.map(e => (
                  <div key={e} className="text-xs text-green-600 font-mono">"{e}"</div>
                ))}
              </div>
            </div>
          ))}
        </div>

        {/* Quick tips */}
        <div className="border border-green-900 bg-zinc-950 rounded p-5 mb-8 max-w-2xl">
          <p className="text-xs text-green-700 tracking-widest uppercase mb-3">&gt; quick tips</p>
          <ul className="space-y-2">
            {[
              "Switch modes anytime using the pills at the top",
              "In Mock Interview mode, click 🎤 to answer with your voice",
              "Your confidence score builds as you practice — start low, aim for 10",
              "The knowledge base is grounded in CBT and Getting to Yes frameworks",
              "All logs go to /tmp/confidenceos/app.log for debugging",
            ].map(t => (
              <li key={t} className="flex items-start gap-2 text-xs text-green-600">
                <span className="text-green-500 mt-0.5 shrink-0">✓</span>{t}
              </li>
            ))}
          </ul>
        </div>

        {/* CTA */}
        <button onClick={onDone}
          className="bg-green-500 hover:bg-green-400 text-black font-bold px-8 py-3 text-sm tracking-widest uppercase transition-colors">
          GET STARTED →
        </button>
        <p className="text-green-900 text-xs mt-3 font-mono">
          This screen only shows once. Press ? anytime to bring it back.
        </p>
      </div>
    </div>
  );
}