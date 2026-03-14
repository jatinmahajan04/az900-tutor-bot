"use client";
import { useState } from "react";
import { createClient } from "@/lib/supabase";

export default function AuthPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const supabase = createClient();

  async function sendLink(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    const { error } = await supabase.auth.signInWithOtp({
      email,
      options: {
        shouldCreateUser: true,
        emailRedirectTo: `${window.location.origin}/auth/callback`,
      },
    });
    if (error) {
      setError(error.message);
    } else {
      setSent(true);
    }
    setLoading(false);
  }

  if (sent) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen px-4">
        <div className="w-full max-w-sm text-center">
          <h1 className="text-2xl font-bold mb-2">Check your email</h1>
          <p className="text-gray-500 text-sm mb-6">
            We sent a magic link to <strong>{email}</strong>.<br />
            Click it to sign in.
          </p>
          <button
            onClick={() => { setSent(false); setEmail(""); }}
            className="text-sm text-gray-500 hover:text-gray-700"
          >
            Use a different email
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center min-h-screen px-4">
      <div className="w-full max-w-sm">
        <h1 className="text-2xl font-bold mb-2 text-center">Sign in to AZ-900 Tutor</h1>
        <p className="text-gray-500 text-center mb-8 text-sm">
          No password needed — we'll email you a sign-in link.
        </p>
        <form onSubmit={sendLink} className="space-y-4">
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
            required
            className="w-full border border-gray-300 rounded-lg px-4 py-3 text-sm focus:outline-none focus:border-blue-500"
          />
          {error && <p className="text-red-500 text-sm">{error}</p>}
          <button
            type="submit"
            disabled={loading || !email}
            className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-200 text-white font-semibold py-3 rounded-lg transition-colors"
          >
            {loading ? "Sending..." : "Send Link"}
          </button>
        </form>
      </div>
    </div>
  );
}
