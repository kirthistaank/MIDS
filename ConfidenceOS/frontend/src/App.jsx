import { useState, useRef, useEffect } from "react";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
const SESSION_ID = "user-" + Math.random().toString(36).slice(2, 9);

const MODE_COLORS = {
  chat:           "bg-zinc-900 text-green-400 border-green-900",
  mock_interview: "bg-zinc-900 text-green-400 border-green-900",
  cbt_reframe:    "bg-zinc-900 text-green-400 border-green-900",
  negotiation:    "bg-zinc-900 text-green-400 border-green-900",
  star_coach:     "bg-zinc-900 text-green-400 border-green-900",
};

const MODE_ACTIVE = {
  chat:           "bg-green-500 text-black border-green-500",
  mock_interview: "bg-green-500 text-black border-green-500",
  cbt_reframe:    "bg-green-500 text-black border-green-500",
  negotiation:    "bg-green-500 text-black border-green-500",
  star_coach:     "bg-green-500 text-black border-green-500",
};

// Parse scores from agent response
function parseScores(text) {
  const scores = { star: null, language: null, relevance: null, overall: null };
  const m = text.match(/---SCORES---[\s\S]*?STAR:\s*(\d+)[\s\S]*?LANGUAGE:\s*(\d+)[\s\S]*?RELEVANCE:\s*(\d+)[\s\S]*?OVERALL:\s*(\d+)/i);
  if (m) {
    scores.star      = parseInt(m[1]);
    scores.language  = parseInt(m[2]);
    scores.relevance = parseInt(m[3]);
    scores.overall   = parseInt(m[4]);
  }
  return scores;
}

// Strip score block from displayed message
function cleanMessage(text) {
  return text
    .replace(/---SCORES---[\s\S]*?OVERALL:\s*\d+/i, "")
    .replace(/---FEEDBACK---/g, "")
    .replace(/---TIPS---/g, "\n💡 Tips:")
    .replace(/---NEXT---/g, "\n❓ Next Question:")
    .trim();
}

function ScoreBar({ label, value, color }) {
  const pct = value !== null ? (value / 10) * 100 : 0;
  return (
    <div className="mb-3">
      <div className="flex justify-between items-center mb-1">
        <span className="text-xs font-mono text-green-600 uppercase tracking-wider">{label}</span>
        <span className="text-xs font-mono text-green-400">{value !== null ? `${value}/10` : "--"}</span>
      </div>
      <div className="w-full bg-zinc-800 rounded-none h-1.5">
        <div className={`h-1.5 transition-all duration-700 ${color}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function ScoreSidebar({ scores, questionCount }) {
  const overall = scores.overall;
  const color = overall === null ? "text-green-900"
    : overall >= 8 ? "text-green-400"
    : overall >= 5 ? "text-yellow-400"
    : "text-red-500";

  return (
    <div className="w-56 shrink-0 border-r border-green-900 bg-zinc-950 flex flex-col px-5 py-6 hidden lg:flex">
      {/* Big score */}
      <div className="text-center mb-6">
        <div className="text-xs font-mono text-green-700 uppercase tracking-widest mb-1">Overall</div>
        <div className={`font-mono font-bold transition-all duration-500 ${color}`}
          style={{ fontSize: overall !== null ? "72px" : "48px", lineHeight: 1 }}>
          {overall !== null ? overall : "--"}
        </div>
        <div className="text-xs font-mono text-green-800 mt-1">/ 10</div>
      </div>

      {/* Sub scores */}
      <div className="mb-6">
        <ScoreBar label="STAR"      value={scores.star}      color="bg-blue-500" />
        <ScoreBar label="Language"  value={scores.language}  color="bg-purple-500" />
        <ScoreBar label="Relevance" value={scores.relevance} color="bg-yellow-500" />
      </div>

      {/* Grade */}
      <div className="border border-green-900 rounded p-3 text-center mb-6">
        <div className="text-xs font-mono text-green-700 mb-1">Grade</div>
        <div className="text-2xl font-bold font-mono text-green-400">
          {overall === null ? "—"
            : overall >= 9 ? "A+"
            : overall >= 8 ? "A"
            : overall >= 7 ? "B+"
            : overall >= 6 ? "B"
            : overall >= 5 ? "C"
            : "D"}
        </div>
      </div>

      {/* Question count */}
      <div className="mt-auto">
        <div className="text-xs font-mono text-green-800 uppercase tracking-widest mb-2">Questions</div>
        <div className="text-2xl font-bold font-mono text-green-600">{questionCount}</div>
        <div className="text-xs font-mono text-green-900 mt-1">answered</div>
      </div>
    </div>
  );
}

export default function App() {
  const [messages, setMessages] = useState([
    { role: "assistant", content: "> SYSTEM BOOT...\n> ConfidenceOS v2.0 initialised ✓\n> Knowledge base connected ✓\n> LLM ready ✓\n\nHi! I'm ConfidenceOS, your interview confidence coach 👋\n\nI can help you practice interviews, reframe negative thoughts, coach salary negotiation, or just chat about your job hunt.\n\nPick a mode above to get started, or just tell me what's on your mind!" }
  ]);
  const [input, setInput]             = useState("");
  const [loading, setLoading]         = useState(false);
  const [mode, setMode]               = useState("chat");
  const [modes, setModes]             = useState([]);
  const [confidence, setConfidence]   = useState(2);
  const [recording, setRecording]     = useState(false);
  const [transcript, setTranscript]   = useState("");
  const [audioSupported, setAudioSupported] = useState(false);
  const [scores, setScores]           = useState({ star: null, language: null, relevance: null, overall: null });
  const [questionCount, setQuestionCount] = useState(0);

  const bottomRef    = useRef(null);
  const recognitionRef = useRef(null);

  // Check browser speech support
  useEffect(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    setAudioSupported(!!SpeechRecognition);
  }, []);

  useEffect(() => {
    fetch(`${API_URL}/modes`)
      .then(r => r.json())
      .then(d => setModes(d.modes))
      .catch(() => {});
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // ── Voice recording ────────────────────────────────────────────────────────
  const toggleRecording = () => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) return;

    if (recording) {
      recognitionRef.current?.stop();
      setRecording(false);
      return;
    }

    const rec = new SpeechRecognition();
    rec.continuous     = true;
    rec.interimResults = true;
    rec.lang           = "en-US";

    let finalTranscript = "";

    rec.onresult = (e) => {
      let interim = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const t = e.results[i][0].transcript;
        if (e.results[i].isFinal) finalTranscript += t + " ";
        else interim = t;
      }
      setTranscript(finalTranscript + interim);
      setInput(finalTranscript + interim);
    };

    rec.onerror = () => { setRecording(false); };
    rec.onend   = () => { setRecording(false); };

    recognitionRef.current = rec;
    rec.start();
    setRecording(true);
    setTranscript("");
  };

  // ── Mode switch ────────────────────────────────────────────────────────────
  const switchMode = async (newMode) => {
    setMode(newMode);
    if (newMode === "mock_interview") {
      setScores({ star: null, language: null, relevance: null, overall: null });
      setQuestionCount(0);
    }
    await fetch(`${API_URL}/mode`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: SESSION_ID, mode: newMode }),
    });
    const modeInfo = modes.find(m => m.id === newMode);
    if (modeInfo) {
      setMessages(prev => [...prev, {
        role: "assistant",
        content: `> MODE SWITCH: ${modeInfo.label} ${modeInfo.icon}\n> ${modeInfo.description}\n> Ready.`
      }]);
    }
  };

  // ── Send message ───────────────────────────────────────────────────────────
  const sendMessage = async () => {
    const text = input.trim();
    if (!text || loading) return;

    // Stop recording if active
    if (recording) { recognitionRef.current?.stop(); setRecording(false); }

    const updated = [...messages, { role: "user", content: text }];
    setMessages(updated);
    setInput("");
    setTranscript("");
    setLoading(true);

    try {
      const res = await fetch(`${API_URL}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: updated, session_id: SESSION_ID, mode }),
      });
      if (!res.ok) throw new Error(`Server error: ${res.status}`);
      const data = await res.json();

      // Parse scores if in mock interview mode
      if (mode === "mock_interview") {
        const parsed = parseScores(data.reply);
        if (parsed.overall !== null) {
          setScores(parsed);
          setQuestionCount(c => c + 1);
          setConfidence(parsed.overall / 10 * 10);
        }
      }

      const cleaned = mode === "mock_interview" ? cleanMessage(data.reply) : data.reply;
      setMessages(prev => [...prev, { role: "assistant", content: cleaned }]);

    } catch (err) {
      setMessages(prev => [...prev, { role: "assistant", content: `> ERROR: ${err.message}` }]);
    } finally {
      setLoading(false);
    }
  };

  const handleKey = e => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  };

  const currentMode = modes.find(m => m.id === mode);

  return (
    <div className="flex flex-col h-screen bg-black text-green-400" style={{ fontFamily: "'Courier New', Courier, monospace" }}>

      {/* Header */}
      <header className="bg-zinc-950 border-b border-green-800 px-4 py-3">
        <div className="max-w-7xl mx-auto flex items-center justify-between w-full">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 border border-green-500 flex items-center justify-center text-green-400 text-sm font-bold shrink-0 bg-black">C</div>
            <div className="text-left">
              <h1 className="font-bold text-green-400 text-sm tracking-widest uppercase">ConfidenceOS — Interview Coach</h1>
              <p className="text-xs text-green-700">Ollama · Pinecone · AuraDB · CBT + GTY</p>
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <span className="text-xs text-green-700 hidden sm:block font-mono">CONF_SCORE</span>
            <div className="flex gap-0.5">
              {[...Array(10)].map((_, i) => (
                <div key={i} className={`w-2 h-4 transition-colors ${i < Math.round(confidence) ? "bg-green-500" : "bg-zinc-800 border border-zinc-700"}`} />
              ))}
            </div>
            <span className="text-xs font-bold text-green-400 w-6 font-mono">{Math.round(confidence)}</span>
          </div>
        </div>
        <div className="max-w-7xl mx-auto mt-2 flex gap-1.5 overflow-x-auto pb-1 justify-center">
          {modes.map(m => (
            <button key={m.id} onClick={() => switchMode(m.id)}
              className={`shrink-0 px-3 py-1.5 rounded text-xs font-mono font-medium border transition-all tracking-wide ${mode === m.id ? MODE_ACTIVE[m.id] : MODE_COLORS[m.id]}`}>
              {m.icon} {m.label}
            </button>
          ))}
        </div>
      </header>

      {/* Mode banner */}
      {currentMode && (
        <div className="text-center text-xs py-1.5 px-4 bg-zinc-950 text-green-700 border-b border-green-900 font-mono">
          &gt; {currentMode.icon} <span className="text-green-500">[{currentMode.label.toUpperCase()}]</span> — {currentMode.description}
          {mode === "mock_interview" && audioSupported && (
            <span className="ml-3 text-green-800">· 🎤 voice input enabled</span>
          )}
        </div>
      )}

      {/* Main content */}
      <div className="flex-1 overflow-hidden flex">

        {/* Score sidebar — mock interview only */}
        {mode === "mock_interview" && (
          <ScoreSidebar scores={scores} questionCount={questionCount} />
        )}

        {/* Messages */}
        <div className={`flex flex-col overflow-y-auto px-4 py-6 ${mode === "star_coach" ? "flex-1" : "w-full"}`}>
          <div className="max-w-3xl mx-auto w-full space-y-4">
            {messages.map((m, i) => (
              <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                {m.role === "assistant" && (
                  <div className="w-7 h-7 border border-green-700 text-green-500 flex items-center justify-center text-xs font-bold mr-2 mt-1 shrink-0 font-mono bg-black">C</div>
                )}
                <div className={`max-w-[80%] rounded px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap font-mono
                  ${m.role === "user"
                    ? "bg-zinc-900 text-green-300 border border-green-700 rounded-tr-none"
                    : "bg-zinc-950 border border-green-900 text-green-400 rounded-tl-none"
                  }`}>
                  {m.content}
                </div>
              </div>
            ))}

            {loading && (
              <div className="flex justify-start">
                <div className="w-7 h-7 border border-green-700 text-green-500 flex items-center justify-center text-xs font-bold mr-2 mt-1 shrink-0 font-mono bg-black">C</div>
                <div className="bg-zinc-950 border border-green-900 rounded px-4 py-3">
                  <span className="text-green-500 font-mono text-sm animate-pulse">▋ processing...</span>
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>
        </div>

        {/* STAR Coach sidebar */}
        {mode === "star_coach" && (
          <div className="w-72 shrink-0 border-l border-green-900 bg-zinc-950 overflow-y-auto px-5 py-6 hidden lg:block font-mono">
            <h2 className="font-bold text-green-400 text-sm mb-1 tracking-widest">&gt; STAR_COACH.exe</h2>
            <p className="text-xs text-green-700 mb-5 leading-relaxed">
              Craft compelling behavioral interview answers using the STAR framework.
            </p>
            <div className="space-y-3 mb-6">
              {[
                { letter: "S", label: "Situation", desc: "Set the scene. Give context — where, when, what was happening." },
                { letter: "T", label: "Task",      desc: "Your specific responsibility. What were YOU accountable for?" },
                { letter: "A", label: "Action",    desc: "What did YOU do? Use 'I', not 'we'. Be specific and concrete." },
                { letter: "R", label: "Result",    desc: "What was the outcome? Quantify if possible. What did you learn?" },
              ].map(({ letter, label, desc }) => (
                <div key={letter} className="border border-green-900 rounded px-3 py-2.5 bg-zinc-900">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-bold text-green-300 text-sm">[{letter}]</span>
                    <span className="font-medium text-xs text-green-500">{label}</span>
                  </div>
                  <p className="text-xs text-green-700 leading-relaxed">{desc}</p>
                </div>
              ))}
            </div>
            <div className="mb-6">
              <h3 className="text-green-700 text-xs uppercase tracking-widest mb-2">&gt; common_errors</h3>
              <ul className="space-y-1.5">
                {["Saying 'we' instead of 'I'", "No measurable result", "Too much situation, too little action", "Vague actions — be specific", "Forgetting what you learned"].map(m => (
                  <li key={m} className="flex items-start gap-1.5 text-xs text-green-800">
                    <span className="text-red-600 mt-0.5">✕</span>{m}
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <h3 className="text-green-700 text-xs uppercase tracking-widest mb-2">&gt; sample_queries</h3>
              <ul className="space-y-1.5">
                {["Tell me about a conflict you handled", "Describe a time you failed", "When did you show leadership?", "Tell me about a tight deadline", "Describe working with a difficult person"].map(q => (
                  <li key={q} onClick={() => setInput(q)}
                    className="text-xs text-green-600 hover:text-green-400 cursor-pointer hover:underline leading-relaxed">
                    &gt; {q}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        )}
      </div>

      {/* Quick prompts */}
      <div className="bg-zinc-950 border-t border-green-900 px-4 pt-2">
        <div className="max-w-3xl mx-auto flex gap-2 overflow-x-auto pb-2">
          {mode === "mock_interview" && ["Start mock interview", "Behavioral question", "Tell me about yourself"].map(p => (
            <button key={p} onClick={() => setInput(p)}
              className="shrink-0 text-xs bg-black text-green-500 border border-green-800 rounded px-3 py-1 hover:border-green-500 hover:text-green-300 transition-colors font-mono">{p}</button>
          ))}
          {mode === "cbt_reframe" && ["I'm terrible at interviews", "I always mess up", "Nobody will hire me"].map(p => (
            <button key={p} onClick={() => setInput(p)}
              className="shrink-0 text-xs bg-black text-green-500 border border-green-800 rounded px-3 py-1 hover:border-green-500 hover:text-green-300 transition-colors font-mono">{p}</button>
          ))}
          {mode === "negotiation" && ["I got an offer", "How do I negotiate salary?", "They said no to my counter"].map(p => (
            <button key={p} onClick={() => setInput(p)}
              className="shrink-0 text-xs bg-black text-green-500 border border-green-800 rounded px-3 py-1 hover:border-green-500 hover:text-green-300 transition-colors font-mono">{p}</button>
          ))}
          {mode === "star_coach" && ["Tell me about a conflict", "Describe a failure", "What is your weakness?"].map(p => (
            <button key={p} onClick={() => setInput(p)}
              className="shrink-0 text-xs bg-black text-green-500 border border-green-800 rounded px-3 py-1 hover:border-green-500 hover:text-green-300 transition-colors font-mono">{p}</button>
          ))}
        </div>
      </div>

      {/* Input */}
      <div className="bg-zinc-950 border-t border-green-900 px-4 pb-4 pt-2">
        <div className="max-w-3xl mx-auto flex items-end gap-3">

          {/* Mic button — mock interview only */}
          {mode === "mock_interview" && audioSupported && (
            <button onClick={toggleRecording}
              className={`shrink-0 w-11 h-11 rounded border font-mono text-lg transition-all ${
                recording
                  ? "border-red-500 text-red-400 bg-red-950 animate-pulse"
                  : "border-green-700 text-green-500 bg-black hover:border-green-400"
              }`}
              title={recording ? "Click to stop recording" : "Click to start recording"}>
              {recording ? "⏹" : "🎤"}
            </button>
          )}

          {/* Input box */}
          <div className="flex-1 flex items-end gap-2 border border-green-800 rounded bg-black px-3 py-2 focus-within:border-green-500 transition-colors">
            <span className="text-green-600 text-sm font-mono pb-1 shrink-0">&gt;</span>
            <textarea rows={1} value={input} onChange={e => setInput(e.target.value)}
              onKeyDown={handleKey}
              placeholder={
                recording ? "listening... speak now" :
                mode === "mock_interview" ? "type or use 🎤 to answer..." :
                mode === "cbt_reframe"    ? "share what's on your mind..." :
                mode === "negotiation"    ? "describe your offer situation..." :
                mode === "star_coach"     ? "share your story..." :
                "type your message..."
              }
              className="flex-1 resize-none bg-transparent text-green-300 placeholder-green-900 text-sm font-mono focus:outline-none"
              style={{ maxHeight: "120px" }}
            />
            {recording && (
              <span className="text-red-400 animate-pulse text-xs font-mono shrink-0 pb-1">● REC</span>
            )}
          </div>

          <button onClick={sendMessage} disabled={!input.trim() || loading}
            className="bg-green-600 hover:bg-green-500 disabled:opacity-30 text-black rounded px-5 py-3 text-sm font-bold font-mono transition-colors shrink-0 tracking-widest">
            RUN
          </button>
        </div>

        {/* Recording hint */}
        {mode === "mock_interview" && audioSupported && (
          <p className="text-center text-xs text-green-900 mt-2 font-mono">
            {recording ? "> recording in progress — click ⏹ to stop" : "> click 🎤 to answer with voice · enter to run"}
          </p>
        )}
        {mode !== "mock_interview" && (
          <p className="text-center text-xs text-green-900 mt-2 font-mono">shift+enter for newline · enter to run</p>
        )}
      </div>

    </div>
  );
}