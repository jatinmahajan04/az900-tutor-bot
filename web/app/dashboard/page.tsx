"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getProgress } from "@/lib/api";
import { createClient } from "@/lib/supabase";

const DOMAINS = [
  "Cloud Concepts",
  "Azure Architecture and Services",
  "Azure Management and Governance",
];

export default function DashboardPage() {
  const router = useRouter();
  const supabase = createClient();
  const [data, setData] = useState<{ overall: number; breakdown: Record<string, number> } | null>(null);
  const [userId, setUserId] = useState<string | null>(null);

  function loadProgress(uid: string) {
    setData(null);
    getProgress(uid).then(setData);
  }

  useEffect(() => {
    supabase.auth.getUser().then(({ data: authData }) => {
      if (!authData.user) { router.push("/auth"); return; }
      setUserId(authData.user.id);
      getProgress(authData.user.id).then(setData);
    });
  }, []);

  if (!data) {
    return (
      <div className="flex items-center justify-center min-h-screen text-gray-400">
        Loading your progress...
      </div>
    );
  }

  return (
    <div className="max-w-xl mx-auto px-4 py-10">
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-2xl font-bold">Your Progress</h1>
        <div className="flex gap-3 items-center">
          {userId && (
            <button
              onClick={() => loadProgress(userId)}
              className="text-sm text-gray-400 hover:text-blue-600"
            >
              ↻ Refresh
            </button>
          )}
          <button
            onClick={() => router.push("/session")}
            className="text-sm text-azure-500 hover:underline"
          >
            ← Back to study
          </button>
        </div>
      </div>

      {/* Overall score */}
      <div className="bg-white border border-gray-200 rounded-2xl p-6 mb-6 text-center">
        <div className="text-5xl font-bold text-azure-500">{data.overall}%</div>
        <div className="text-gray-500 mt-1">Overall Readiness</div>
        {data.overall >= 80 && (
          <div className="mt-3 text-green-600 font-medium">
            You're ready to book your exam! 🎉
          </div>
        )}
        {data.overall < 80 && data.overall > 0 && (
          <div className="mt-3 text-gray-400 text-sm">
            Target: 80% to be exam-ready
          </div>
        )}
      </div>

      {/* Domain breakdown */}
      <div className="space-y-4">
        {DOMAINS.map((domain) => {
          const pct = data.breakdown[domain];
          return (
            <div key={domain} className="bg-white border border-gray-200 rounded-xl p-4">
              <div className="flex justify-between mb-2">
                <span className="text-sm font-medium">{domain}</span>
                <span className="text-sm text-gray-500">
                  {pct !== undefined ? `${pct}%` : "No data yet"}
                </span>
              </div>
              <div className="h-2 bg-gray-100 rounded-full">
                {pct !== undefined && (
                  <div
                    className={`h-2 rounded-full transition-all ${
                      pct >= 80 ? "bg-green-500" : pct >= 50 ? "bg-azure-500" : "bg-red-400"
                    }`}
                    style={{ width: `${pct}%` }}
                  />
                )}
              </div>
            </div>
          );
        })}
      </div>

      {Object.keys(data.breakdown).length === 0 && (
        <p className="text-center text-gray-400 mt-8">
          Answer some questions to see your progress here.
        </p>
      )}
    </div>
  );
}
