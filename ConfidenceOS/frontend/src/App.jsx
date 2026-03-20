import { useState, useRef, useEffect } from "react";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export default function App() {
  const [messages, setMessages] = useState([
    { role: "assistant", content: "Hi! I'm your local AI assistant. Ask me anything — I can search the knowledge base, query the graph, or just chat." }
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef(null);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  const sendMessage = async () => {
    const text = input.trim();
    if (!text || loading) return;
    const updated = [...messages, { role: "user", content: text }];
    setMessages(updated);
    setInput("");
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: updated }),
      });
      if (!res.ok) throw new Error(`Server error: ${res.status}`);
      const data = await res.json();
      setMessages(prev => [...prev, { role: "assistant", content: data.reply }]);
    } catch (err) {
      setMessages(prev => [...prev, { role: "assistant", content: `Error: ${err.message}` }]);
    } finally {
      setLoading(false);
    }
  };

  const handleKey = e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); } };

  return (
    <div className="flex flex-col h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 px-6 py-4 flex items-center gap-3">
        <div className="w-8 h-8 rounded-full bg-violet-600 flex items-center justify-center text-white text-sm font-medium">AI</div>
        <div>
          <h1 className="font-semibold text-gray-900 text-sm">Local AI Assistant</h1>
          <p className="text-xs text-gray-400">Ollama · Pinecone · AuraDB</p>
        </div>
        <span className="ml-auto inline-flex items-center gap-1.5 text-xs text-green-600">
          <span className="w-1.5 h-1.5 rounded-full bg-green-500 inline-block"></span>
          Local
        </span>
      </header>
      <div className="flex-1 overflow-y-auto px-4 py-6 space-y-4">
        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
            {m.role === "assistant" && (
              <div className="w-7 h-7 rounded-full bg-violet-100 text-violet-700 flex items-center justify-center text-xs font-medium mr-2 mt-1 shrink-0">AI</div>
            )}
            <div className={`max-w-[75%] rounded-2xl px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap ${m.role === "user" ? "bg-violet-600 text-white rounded-tr-sm" : "bg-white border border-gray-200 text-gray-800 rounded-tl-sm shadow-sm"}`}>
              {m.content}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="w-7 h-7 rounded-full bg-violet-100 text-violet-700 flex items-center justify-center text-xs font-medium mr-2 mt-1 shrink-0">AI</div>
            <div className="bg-white border border-gray-200 rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm">
              <span className="flex gap-1">
                <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "0ms" }}/>
                <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "150ms" }}/>
                <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "300ms" }}/>
              </span>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>
      <div className="bg-white border-t border-gray-200 px-4 py-4">
        <div className="flex items-end gap-3 max-w-3xl mx-auto">
          <textarea rows={1} value={input} onChange={e => setInput(e.target.value)} onKeyDown={handleKey} placeholder="Ask me anything… (Enter to send)" className="flex-1 resize-none rounded-xl border border-gray-300 px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-violet-400 focus:border-transparent" style={{ maxHeight: "120px" }}/>
          <button onClick={sendMessage} disabled={!input.trim() || loading} className="bg-violet-600 hover:bg-violet-700 disabled:opacity-40 text-white rounded-xl px-5 py-3 text-sm font-medium transition-colors">Send</button>
        </div>
        <p className="text-center text-xs text-gray-400 mt-2">Shift+Enter for new line · Enter to send</p>
      </div>
    </div>
  );
}
