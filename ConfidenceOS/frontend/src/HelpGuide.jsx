/**
 * HelpGuide.jsx — slide-in help panel triggered by the ? button.
 * Shows mode descriptions, example prompts, tips, and keyboard shortcuts.
 */

const MODES = [
    {
      icon: "💬", title: "General Chat",
      desc: "Open conversation — career advice, interview prep, or anything on your mind.",
      examples: ["What is the STAR method?", "How do I answer 'tell me about yourself'?", "What should I research before an interview?"],
      tip: "Great starting point. The agent searches your knowledge base automatically.",
    },
    {
      icon: "🎤", title: "Mock Interview",
      desc: "Realistic interview practice with live scoring on every answer.",
      examples: ["Start a mock interview for a Senior AI Engineer", "Ask me a behavioral question", "Give me a technical question about machine learning"],
      tip: "Click 🎤 to answer with your voice. Watch the left sidebar for your scores.",
    },
    {
      icon: "🧠", title: "CBT Reframe",
      desc: "Identify and reframe cognitive distortions using CBT techniques.",
      examples: ["I always freeze in interviews", "I'm not qualified enough for this role", "I got rejected — I'm a failure"],
      tip: "Be honest about your fears. The agent will name the distortion and guide you through reframing it.",
    },
    {
      icon: "💰", title: "Negotiation",
      desc: "Salary negotiation coaching grounded in Getting to Yes principles.",
      examples: ["I got an offer for $110k, I wanted $135k", "How do I counter without seeming greedy?", "They said the salary is non-negotiable"],
      tip: "Share the real numbers. The agent uses BATNA and principled negotiation strategies.",
    },
    {
      icon: "⭐", title: "STAR Coach",
      desc: "Structure behavioral answers using Situation-Task-Action-Result.",
      examples: ["Help me answer: tell me about a conflict", "I led a project that failed — how do I talk about it?", "What is my biggest weakness?"],
      tip: "Click any question in the right sidebar to auto-fill the input.",
    },
  ];
  
  const SHORTCUTS = [
    { key: "Enter",        action: "Send message" },
    { key: "Shift+Enter", action: "New line in input" },
    { key: "?",           action: "Toggle this help guide" },
    { key: "🎤 button",   action: "Start/stop voice recording (Mock Interview)" },
  ];
  
  export default function HelpGuide({ onClose }) {
    return (
      <div className="fixed inset-0 z-50 flex justify-end" style={{ fontFamily: "'Courier New', Courier, monospace" }}>
  
        {/* Backdrop */}
        <div className="absolute inset-0 bg-black/70" onClick={onClose} />
  
        {/* Panel */}
        <div className="relative w-full max-w-md bg-zinc-950 border-l border-green-800 flex flex-col overflow-y-auto z-10">
  
          {/* Header */}
          <div className="flex items-center justify-between px-5 py-4 border-b border-green-900 shrink-0">
            <div>
              <h2 className="text-green-400 font-bold text-sm tracking-widest uppercase">Help Guide</h2>
              <p className="text-green-800 text-xs mt-0.5">ConfidenceOS · v2.0</p>
            </div>
            <button onClick={onClose}
              className="text-green-700 hover:text-green-400 text-xl font-mono transition-colors">✕</button>
          </div>
  
          {/* Content */}
          <div className="px-5 py-5 space-y-6 flex-1">
  
            {/* Modes */}
            <div>
              <p className="text-xs text-green-700 tracking-widest uppercase mb-3">&gt; modes</p>
              <div className="space-y-4">
                {MODES.map(m => (
                  <div key={m.title} className="border border-green-900 rounded p-3 hover:border-green-800 transition-colors">
                    <div className="flex items-center gap-2 mb-1.5">
                      <span>{m.icon}</span>
                      <span className="text-green-400 font-bold text-xs tracking-wide">{m.title}</span>
                    </div>
                    <p className="text-green-700 text-xs mb-2 leading-relaxed">{m.desc}</p>
                    <div className="space-y-0.5 mb-2">
                      {m.examples.map(e => (
                        <div key={e} className="text-xs text-green-600 font-mono">→ "{e}"</div>
                      ))}
                    </div>
                    <div className="flex items-start gap-1.5 mt-2 pt-2 border-t border-green-900">
                      <span className="text-green-500 text-xs shrink-0">💡</span>
                      <span className="text-xs text-green-800">{m.tip}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
  
            {/* Scoring */}
            <div>
              <p className="text-xs text-green-700 tracking-widest uppercase mb-3">&gt; scoring (mock interview)</p>
              <div className="space-y-2">
                {[
                  { label: "STAR",      color: "bg-blue-500",   desc: "Did you use Situation, Task, Action, Result structure?" },
                  { label: "Language",  color: "bg-purple-500", desc: "Did you avoid filler words and speak directly?" },
                  { label: "Relevance", color: "bg-yellow-500", desc: "Did you answer the actual question asked?" },
                  { label: "Overall",   color: "bg-green-500",  desc: "Holistic score combining all three factors." },
                ].map(s => (
                  <div key={s.label} className="flex items-start gap-3">
                    <div className={`w-2 h-2 rounded-sm mt-1 shrink-0 ${s.color}`} />
                    <div>
                      <span className="text-xs text-green-400 font-bold">{s.label} </span>
                      <span className="text-xs text-green-700">{s.desc}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
  
            {/* Keyboard shortcuts */}
            <div>
              <p className="text-xs text-green-700 tracking-widest uppercase mb-3">&gt; shortcuts</p>
              <div className="space-y-2">
                {SHORTCUTS.map(s => (
                  <div key={s.key} className="flex items-center justify-between">
                    <span className="text-xs font-mono text-green-400 border border-green-800 px-2 py-0.5 rounded">{s.key}</span>
                    <span className="text-xs text-green-700">{s.action}</span>
                  </div>
                ))}
              </div>
            </div>
  
            {/* Stack */}
            <div>
              <p className="text-xs text-green-700 tracking-widest uppercase mb-3">&gt; tech stack</p>
              <div className="space-y-1.5">
                {[
                  ["LLM",        "Ollama — llama3.2 (local)"],
                  ["Embeddings", "nomic-embed-text (local)"],
                  ["Agent",      "LangGraph"],
                  ["Vector DB",  "Pinecone"],
                  ["Graph DB",   "Neo4j AuraDB"],
                  ["API",        "FastAPI"],
                  ["Logs",       "/tmp/confidenceos/app.log"],
                ].map(([k, v]) => (
                  <div key={k} className="flex gap-3 text-xs font-mono">
                    <span className="text-green-700 w-24 shrink-0">{k}</span>
                    <span className="text-green-500">{v}</span>
                  </div>
                ))}
              </div>
            </div>
  
          </div>
  
          {/* Footer */}
          <div className="px-5 py-4 border-t border-green-900 shrink-0">
            <p className="text-xs text-green-900 font-mono text-center">
              Press ? or click ✕ to close · ConfidenceOS is WIP
            </p>
          </div>
  
        </div>
      </div>
    );
  }