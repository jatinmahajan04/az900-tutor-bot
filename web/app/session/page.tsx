"use client";
import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { fetchDomains, startSession, submitAnswer, submitExplanation, skipExplanation, sendChat } from "@/lib/api";
import { createClient } from "@/lib/supabase";

type Stage = "pick-domain" | "question" | "explain" | "ready";

interface Message {
  role: "tutor" | "user";
  text: string;
}

export default function SessionPage() {
  const router = useRouter();
  const supabase = createClient();

  async function handleLogout() {
    await supabase.auth.signOut();
    router.push("/auth");
  }
  const [userId, setUserId] = useState<string | null>(null);
  const [domains, setDomains] = useState<string[]>([]);
  const [domain, setDomain] = useState("");
  const [sessionId, setSessionId] = useState("");
  const [stage, setStage] = useState<Stage>("pick-domain");
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [pendingQuestion, setPendingQuestion] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetchDomains().then(setDomains);
    supabase.auth.getUser().then(({ data }) => {
      if (data.user) setUserId(data.user.id);
      else router.push("/auth");
    });
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  function addMessage(role: "tutor" | "user", text: string) {
    setMessages((prev) => [...prev, { role, text }]);
  }

  async function handleDomainSelect(d: string) {
    setDomain(d);
    setLoading(true);
    addMessage("tutor", `Starting your ${d} session…`);
    const data = await startSession(d, userId || "anonymous");
    setSessionId(data.session_id);
    addMessage("tutor", data.question_text + "\n\nReply with A, B, C, or D.");
    setStage("question");
    setLoading(false);
  }

  function isSessionError(data: any) {
    return data?.detail === "Session not found or expired";
  }

  function handleSessionExpired() {
    addMessage("tutor", "⚠️ Your session expired (server restarted). Please pick a domain to start a new session.");
    setStage("pick-domain");
    setSessionId("");
    setDomain("");
    setMessages([]);
  }

  async function handleAnswer() {
    const answer = input.trim().toUpperCase();
    if (!answer || !["A", "B", "C", "D"].includes(answer)) return;
    setInput("");
    addMessage("user", answer);
    setLoading(true);

    const data = await submitAnswer(sessionId, answer);
    if (isSessionError(data)) { handleSessionExpired(); setLoading(false); return; }
    const prefix = data.is_correct ? "✅ Correct!" : "❌ Not quite.";
    addMessage("tutor", `${prefix}\n\n${data.feedback}`);
    addMessage("tutor", data.explain_prompt);
    setStage("explain");
    setLoading(false);
  }

  async function handleExplain() {
    const explanation = input.trim();
    if (!explanation) return;
    setInput("");
    addMessage("user", explanation);
    setLoading(true);

    const data = await submitExplanation(sessionId, explanation);
    if (isSessionError(data)) { handleSessionExpired(); setLoading(false); return; }
    addMessage("tutor", data.feedback);
    addMessage("tutor", "When you're ready, pick your next move below.");
    setPendingQuestion(data.next_question_text);
    setStage("ready");
    setLoading(false);
  }

  async function handleSkip() {
    setLoading(true);
    addMessage("user", "(skipped explanation)");
    const data = await skipExplanation(sessionId);
    addMessage("tutor", "No problem. When you're ready, pick your next move below.");
    setPendingQuestion(data.next_question_text);
    setStage("ready");
    setLoading(false);
  }

  function handleNextQuestion() {
    addMessage("tutor", pendingQuestion + "\n\nReply with A, B, C, or D.");
    setPendingQuestion("");
    setStage("question");
  }

  function handleChangeTopic() {
    setStage("pick-domain");
    setMessages([]);
    setSessionId("");
    setDomain("");
    setPendingQuestion("");
  }

  async function handleFollowup() {
    const message = input.trim();
    if (!message) return;
    setInput("");
    addMessage("user", message);
    setLoading(true);
    const data = await sendChat(sessionId, message);
    if (data?.detail === "Chat limit reached for this question") {
      addMessage("tutor", "You've used your 2 follow-ups for this question. Answer the next one to continue.");
    } else {
      addMessage("tutor", data.response);
    }
    setLoading(false);
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (stage === "question") handleAnswer();
    else if (stage === "explain") handleExplain();
    else if (stage === "ready") handleFollowup();
  }

  return (
    <div className="flex flex-col h-screen max-w-2xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b bg-white">
        <button onClick={handleChangeTopic} className="font-semibold text-blue-600 hover:text-blue-800">AZ-900 Tutor</button>
        {domain && <span className="text-sm text-gray-500">{domain}</span>}
        <div className="flex gap-3">
          <button onClick={() => router.push("/dashboard")} className="text-sm text-gray-500 hover:text-blue-600">
            Progress
          </button>
          <button onClick={handleLogout} className="text-sm text-gray-400 hover:text-red-500">
            Logout
          </button>
        </div>
      </div>

      {/* Domain picker */}
      {stage === "pick-domain" && (
        <div className="flex-1 flex flex-col items-center justify-center gap-4 p-6">
          <h2 className="text-xl font-semibold">Choose a domain to study</h2>
          {domains.map((d) => (
            <button
              key={d}
              onClick={() => handleDomainSelect(d)}
              disabled={!userId}
              className="w-full max-w-sm bg-white border border-gray-200 hover:border-blue-500 hover:text-blue-600 rounded-lg px-6 py-4 text-left font-medium transition-colors disabled:opacity-50"
            >
              {d}
            </button>
          ))}
        </div>
      )}

      {/* Chat */}
      {stage !== "pick-domain" && (
        <>
          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {messages.map((m, i) => (
              <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                <div
                  className={`max-w-[80%] px-4 py-3 rounded-2xl text-sm whitespace-pre-wrap leading-relaxed ${
                    m.role === "user"
                      ? "bg-blue-600 text-white rounded-br-sm"
                      : "bg-white border border-gray-200 rounded-bl-sm"
                  }`}
                >
                  {m.text}
                </div>
              </div>
            ))}
            {loading && (
              <div className="flex justify-start">
                <div className="bg-white border border-gray-200 rounded-2xl rounded-bl-sm px-4 py-3 text-gray-400 text-sm">
                  Thinking…
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {/* Bottom controls */}
          <div className="border-t bg-white p-3">
            {stage === "ready" && (
              <div className="flex gap-2 mb-2">
                <button
                  onClick={handleNextQuestion}
                  className="flex-1 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium py-2 rounded-lg transition-colors"
                >
                  Next question →
                </button>
                <button
                  onClick={handleChangeTopic}
                  className="flex-1 bg-white border border-gray-300 hover:border-blue-500 hover:text-blue-600 text-sm font-medium py-2 rounded-lg transition-colors"
                >
                  Change topic
                </button>
              </div>
            )}

            {stage === "explain" && (
              <button
                onClick={handleSkip}
                className="w-full text-center text-sm text-gray-400 hover:text-gray-600 mb-2"
              >
                Skip — I'll move on
              </button>
            )}

            <form onSubmit={handleSubmit} className="flex gap-2">
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder={
                  stage === "question" ? "Type A, B, C, or D…" :
                  stage === "explain" ? "Type your explanation…" :
                  "Ask a follow-up question…"
                }
                className="flex-1 border border-gray-300 rounded-lg px-4 py-2 text-sm focus:outline-none focus:border-blue-500"
                disabled={loading}
              />
              <button
                type="submit"
                disabled={loading || !input.trim()}
                className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-200 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
              >
                Send
              </button>
            </form>
          </div>
        </>
      )}
    </div>
  );
}
