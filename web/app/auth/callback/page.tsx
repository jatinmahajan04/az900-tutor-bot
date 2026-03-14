"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase";

export default function AuthCallback() {
  const router = useRouter();
  const supabase = createClient();

  useEffect(() => {
    // Supabase puts tokens in the URL hash for magic links (implicit flow).
    // getSession() automatically parses and stores them.
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (session) {
        router.push("/session");
        return;
      }
      // Fallback: PKCE code in query param
      const code = new URLSearchParams(window.location.search).get("code");
      if (code) {
        supabase.auth.exchangeCodeForSession(code).then(({ error }) => {
          router.push(error ? "/auth" : "/session");
        });
      } else {
        router.push("/auth");
      }
    });
  }, []);

  return (
    <div className="flex items-center justify-center min-h-screen">
      <p className="text-gray-500">Signing you in…</p>
    </div>
  );
}
