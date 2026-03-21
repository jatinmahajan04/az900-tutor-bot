const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface QuestionData {
  topic: string;
  question: string;
  options: Record<string, string>;
}

export async function fetchDomains(): Promise<string[]> {
  const res = await fetch(`${API}/session/domains`);
  const data = await res.json();
  return data.domains;
}

export async function startSession(domain: string, userId: string) {
  const res = await fetch(`${API}/session/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ domain, user_id: userId }),
  });
  return res.json(); // { session_id, question: QuestionData, domain }
}

export async function submitAnswer(sessionId: string, answer: string) {
  const res = await fetch(`${API}/session/answer`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, answer }),
  });
  return res.json(); // { is_correct, feedback, explain_prompt }
}

export async function submitExplanation(sessionId: string, explanation: string) {
  const res = await fetch(`${API}/session/explain`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, explanation }),
  });
  return res.json(); // { feedback, next_question_text }
}

export async function skipExplanation(sessionId: string) {
  const res = await fetch(`${API}/session/skip?session_id=${sessionId}`, {
    method: "POST",
  });
  return res.json(); // { next_question_text }
}

export async function sendChat(sessionId: string, message: string) {
  const res = await fetch(`${API}/session/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, answer: message }),
  });
  return res.json(); // { response }
}

export async function getProgress(userId: string) {
  const res = await fetch(`${API}/progress/${userId}`);
  return res.json(); // { overall, breakdown, stats }
}
