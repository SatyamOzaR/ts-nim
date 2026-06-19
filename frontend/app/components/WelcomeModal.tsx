"use client";

import { useState } from "react";

interface WelcomeModalProps {
  onConfirm: (name: string) => void;
}

export function WelcomeModal({ onConfirm }: WelcomeModalProps) {
  const [name, setName] = useState("");
  const [error, setError] = useState(false);

  const handleSubmit = () => {
    const trimmed = name.trim();
    if (!trimmed) {
      setError(true);
      return;
    }
    localStorage.setItem("nim_user_name", trimmed);
    onConfirm(trimmed);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-zinc-950/90 backdrop-blur-sm">
      <div className="w-full max-w-sm rounded-2xl border border-zinc-700 bg-zinc-900 p-8 shadow-2xl">
        <div className="mb-6 flex justify-center">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-indigo-600/20">
            <svg
              width="28"
              height="28"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
              className="text-indigo-400"
            >
              <path d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              <path d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
            </svg>
          </div>
        </div>

        <h2 className="mb-1 text-center text-xl font-semibold text-zinc-100">
          Welcome to Network Intelligence
        </h2>
        <p className="mb-6 text-center text-sm text-zinc-500">
          Enter your name to get started. This helps the assistant find warm paths from your network.
        </p>

        <div className="space-y-4">
          <div>
            <label className="mb-1.5 block text-xs font-medium text-zinc-400">
              Your full name
            </label>
            <input
              type="text"
              value={name}
              autoFocus
              onChange={(e) => {
                setName(e.target.value);
                setError(false);
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleSubmit();
              }}
              placeholder="e.g. Paras Mehta"
              className={`w-full rounded-lg border px-3 py-2.5 text-sm text-zinc-100 placeholder-zinc-500 outline-none transition-colors ${
                error
                  ? "border-red-500/70 bg-zinc-800 focus:border-red-500"
                  : "border-zinc-700 bg-zinc-800 focus:border-indigo-500"
              }`}
            />
            {error && (
              <p className="mt-1 text-xs text-red-400">Please enter your name to continue.</p>
            )}
          </div>

          <button
            onClick={handleSubmit}
            className="w-full rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-indigo-500"
          >
            Get started
          </button>
        </div>
      </div>
    </div>
  );
}
