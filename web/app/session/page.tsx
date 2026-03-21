"use client";
import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { fetchDomains, startSession, submitAnswer, submitExplanation, skipExplanation, sendChat, QuestionData } from "@/lib/api";
import { createClient } from "@/lib/supabase";

type Stage = "pick-domain" | "question" | "explain" | "ready";

interface Message {
  role: "tutor" | "user";
  text: string;
}

const OPTION_KEYS = ["A", "B", "C", "D"] as const;

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
  const [currentQuestion, setCurrentQuestion] = useState<QuestionData | null>(null);
  const [pendingQuestion, setPendingQuestion] = useState<QuestionData | null>(null);
  const [selectedOption, setSelectedOption] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [questionNumber, setQuestionNumber] = useState(0);
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
  }, [messages, loading, stage]);

  function addMessage(role: "tutor" | "user", text: string) {
    setMessages((prev) => [...prev, { role, text }]);
  }

  async function handleDomainSelect(d: string) {
    setDomain(d);
    setLoading(true);
    const data = await startSession(d, userId || "anonymous");
    setSessionId(data.session_id);
    setCurrentQuestion(data.question);
    setQuestionNumber(1);
    setStage("question");
    setLoading(false);
  }

  function isSessionError(data: any) {
    return data?.detail === "Session not found or expired";
  }

  function handleSessionExpired() {
    addMessage("tutor", "Your session expired (server restarted). Please pick a domain to start a new session.");
    setStage("pick-domain");
    setSessionId("");
    setDomain("");
    setMessages([]);
    setCurrentQuestion(null);
    setPendingQuestion(null);
  }

  async function handleOptionSelect(option: string) {
    if (loading || selectedOption) return;
    setSelectedOption(option);
    addMessage("user", option);
    setLoading(true);

    const data = await submitAnswer(sessionId, option);
    if (isSessionError(data)) { handleSessionExpired(); setLoading(false); setSelectedOption(null); return; }

    const prefix = data.is_correct ? "✅ Correct!" : "❌ Not quite.";
    addMessage("tutor", `${prefix}\n\n${data.feedback}`);
    addMessage("tutor", data.explain_prompt);
    setCurrentQuestion(null);
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
    if (data?.detail === "Interaction limit reached for this question") {
      addMessage("tutor", "You've reached the limit for this question. Click 'Next question' to continue.");
      setLoading(false); return;
    }
    addMessage("tutor", data.feedback);
    setPendingQuestion(data.next_question);
    setStage("ready");
    setLoading(false);
  }

  async function handleSkip() {
    setLoading(true);
    addMessage("user", "(skipped explanation)");
    const data = await skipExplanation(sessionId);
    addMessage("tutor", "No problem. Click 'Next question' whenever you're ready.");
    setPendingQuestion(data.next_question);
    setStage("ready");
    setLoading(false);
  }

  function handleNextQuestion() {
    setCurrentQuestion(pendingQuestion);
    setPendingQuestion(null);
    setSelectedOption(null);
    setQuestionNumber((n) => n + 1);
    setStage("question");
  }

  function handleChangeTopic() {
    setStage("pick-domain");
    setMessages([]);
    setSessionId("");
    setDomain("");
    setCurrentQuestion(null);
    setPendingQuestion(null);
    setSelectedOption(null);
    setQuestionNumber(0);
  }

  async function handleFollowup() {
    const message = input.trim();
    if (!message) return;
    setInput("");
    addMessage("user", message);
    setLoading(true);
    const data = await sendChat(sessionId, message);
    if (data?.detail === "Interaction limit reached for this question") {
      addMessage("tutor", "You've reached the limit for this question. Click 'Next question' to continue.");
    } else {
      addMessage("tutor", data.response);
    }
    setLoading(false);
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (stage === "explain") handleExplain();
    else if (stage === "ready") handleFollowup();
  }

  return (
    <div className="flex flex-col h-screen max-w-2xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b bg-white">
        <button onClick={handleChangeTopic} className="font-semibold text-azure-500 hover:text-azure-600">
          AZ-900 Tutor
        </button>
        {domain && (
          <span className="text-xs font-medium text-gray-400 bg-gray-100 px-2 py-1 rounded-full">
            {domain}
          </span>
        )}
        <div className="flex gap-3">
          <button onClick={() => router.push("/dashboard")} className="text-sm text-gray-500 hover:text-azure-500">
            Progress
          </button>
          <button onClick={handleLogout} className="text-sm text-gray-400 hover:text-red-500">
            Logout
          </button>
        </div>
      </div>

      {/* Domain picker */}
      {stage === "pick-domain" && (
        <div className="flex-1 flex flex-col items-center justify-center gap-3 p-6">
          <h2 className="text-xl font-semibold text-gray-800 mb-2">Choose a domain to study</h2>
          {domains.map((d) => (
            <button
              key={d}
              onClick={() => handleDomainSelect(d)}
              disabled={!userId || loading}
              className="w-full max-w-sm bg-white border border-gray-200 hover:border-azure-500 hover:text-azure-500 rounded-xl px-6 py-4 text-left font-medium transition-colors disabled:opacity-50"
            >
              {d}
            </button>
          ))}
          {loading && <p className="text-sm text-gray-400 mt-2">Loading question…</p>}
        </div>
      )}

      {/* Chat + question area */}
      {stage !== "pick-domain" && (
        <>
          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {/* Chat messages */}
            {messages.map((m, i) => (
              <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                <div
                  className={`max-w-[80%] px-4 py-3 rounded-2xl text-sm whitespace-pre-wrap leading-relaxed ${
                    m.role === "user"
                      ? "bg-azure-500 text-white rounded-br-sm"
                      : "bg-white border border-gray-200 rounded-bl-sm text-gray-800"
                  }`}
                >
                  {m.text}
                </div>
              </div>
            ))}

            {/* Loading indicator */}
            {loading && (
              <div className="flex justify-start">
                <div className="bg-white border border-gray-200 rounded-2xl rounded-bl-sm px-4 py-3 text-gray-400 text-sm">
                  Thinking…
                </div>
              </div>
            )}

            {/* Question card */}
            {stage === "question" && currentQuestion && !loading && (
              <div className="bg-white border border-gray-200 rounded-2xl p-4 space-y-3">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-medium text-azure-500 bg-azure-50 px-2 py-0.5 rounded-full">
                    {currentQuestion.topic}
                  </span>
                  <span className="text-xs text-gray-400">Q{questionNumber}</span>
                </div>
                <p className="text-sm text-gray-800 leading-relaxed font-medium">
                  {currentQuestion.question}
                </p>
                <div className="space-y-2 pt-1">
                  {OPTION_KEYS.map((key) => {
                    const text = currentQuestion.options[key];
                    if (!text) return null;
                    return (
                      <button
                        key={key}
                        onClick={() => handleOptionSelect(key)}
                        disabled={!!selectedOption || loading}
                        className={`w-full text-left px-4 py-3 rounded-xl border text-sm transition-colors ${
                          selectedOption === key
                            ? "border-azure-500 bg-azure-50 text-azure-600 font-medium"
                            : "border-gray-200 bg-gray-50 hover:border-azure-400 hover:bg-azure-50 text-gray-700"
                        } disabled:cursor-default`}
                      >
                        <span className="font-semibold mr-2">{key}.</span>
                        {text}
                      </button>
                    );
                  })}
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
                  className="flex-1 bg-azure-500 hover:bg-azure-600 text-white text-sm font-medium py-2 rounded-lg transition-colors"
                >
                  Next question →
                </button>
                <button
                  onClick={handleChangeTopic}
                  className="flex-1 bg-white border border-gray-300 hover:border-azure-500 hover:text-azure-500 text-sm font-medium py-2 rounded-lg transition-colors"
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

            {(stage === "explain" || stage === "ready") && (
              <form onSubmit={handleSubmit} className="flex gap-2">
                <input
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder={
                    stage === "explain"
                      ? "Explain it in your own words…"
                      : "Ask a follow-up question…"
                  }
                  className="flex-1 border border-gray-300 rounded-lg px-4 py-2 text-sm focus:outline-none focus:border-azure-500"
                  disabled={loading}
                  autoFocus={stage === "explain"}
                />
                <button
                  type="submit"
                  disabled={loading || !input.trim()}
                  className="bg-azure-500 hover:bg-azure-600 disabled:bg-gray-200 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
                >
                  Send
                </button>
              </form>
            )}
          </div>
        </>
      )}
    </div>
  );
}
