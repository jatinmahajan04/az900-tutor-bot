"use client";
import { useRouter } from "next/navigation";

export default function LandingPage() {
  const router = useRouter();

  return (
    <main className="flex flex-col items-center justify-center min-h-screen px-4 text-center">
      <div className="max-w-2xl">
        <h1 className="text-4xl font-bold text-gray-900 mb-4 leading-tight">
          Stop watching videos.<br />
          <span className="text-azure-500">Your AZ-900 tutor makes you think.</span>
        </h1>

        <p className="text-lg text-gray-600 mb-8">
          Scenario-based questions, Socratic feedback, and an explain-it-back
          mechanic that actually builds understanding — not just recognition.
        </p>

        <ul className="text-left text-gray-700 mb-10 space-y-3 max-w-md mx-auto">
          <li className="flex gap-2">
            <span className="text-azure-500 font-bold">✓</span>
            Real exam scenarios, not memorisation drills
          </li>
          <li className="flex gap-2">
            <span className="text-azure-500 font-bold">✓</span>
            Tutor explains <em>why</em> you got it wrong
          </li>
          <li className="flex gap-2">
            <span className="text-azure-500 font-bold">✓</span>
            Tracks your weak domains and focuses there
          </li>
        </ul>

        <button
          onClick={() => router.push("/session")}
          className="bg-azure-500 hover:bg-azure-600 text-white font-semibold px-8 py-4 rounded-lg text-lg transition-colors"
        >
          Start Studying Free →
        </button>
      </div>
    </main>
  );
}
