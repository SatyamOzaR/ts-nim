"use client";

import { useState } from "react";

interface PathStep {
  step: number;
  name: string;
  company?: string;
  role?: string;
  is_member?: boolean;
  strength?: number | null;
}

export interface PathOption {
  id: string;
  label: string;
  description?: string;
  path: PathStep[];
}

function PathChain({ path }: { path: PathStep[] }) {
  if (!path || path.length === 0) return null;
  return (
    <div className="flex flex-wrap items-center gap-1">
      {path.map((step, i) => (
        <div key={i} className="flex items-center gap-1">
          {i > 0 && (
            <div className="flex flex-col items-center px-1">
              <svg
                width="24"
                height="16"
                viewBox="0 0 24 16"
                className="text-zinc-500"
              >
                <path
                  d="M0 8h20m0 0l-4-4m4 4l-4 4"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  fill="none"
                />
              </svg>
              {step.strength != null && (
                <span className="text-[10px] font-medium text-indigo-400">
                  {step.strength.toFixed(2)}
                </span>
              )}
            </div>
          )}
          <div
            className={`rounded-lg border px-3 py-2 text-center ${
              step.is_member
                ? "border-indigo-500/50 bg-indigo-500/10"
                : "border-zinc-600 bg-zinc-800"
            }`}
          >
            <div className="text-sm font-medium text-zinc-100">
              {step.name}
              {step.is_member && (
                <span className="ml-1.5 rounded bg-indigo-500/20 px-1 py-0.5 text-[10px] font-semibold text-indigo-400">
                  TEAM
                </span>
              )}
            </div>
            <div className="text-xs text-zinc-400">
              {step.role || "N/A"} {step.company ? `@ ${step.company}` : ""}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

export function PathHighlight({
  path,
  options,
}: {
  path?: PathStep[];
  options?: PathOption[];
}) {
  const list: PathOption[] =
    options && options.length > 0
      ? options
      : path && path.length > 0
        ? [{ id: "default", label: "Warm path", path }]
        : [];

  const [tab, setTab] = useState(0);
  if (list.length === 0) return null;

  const safeTab = Math.min(tab, list.length - 1);
  const current = list[safeTab];

  return (
    <div className="my-2 rounded-xl border border-zinc-700 bg-zinc-800/50 p-4">
      <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-zinc-400">
        Warm introduction paths
      </h4>
      {list.length > 1 && (
        <div className="mb-3 flex flex-wrap gap-1.5">
          {list.map((opt, i) => (
            <button
              key={opt.id}
              type="button"
              onClick={() => setTab(i)}
              className={`rounded-lg border px-2.5 py-1 text-xs font-medium transition-colors ${
                i === safeTab
                  ? "border-indigo-500/60 bg-indigo-500/15 text-indigo-200"
                  : "border-zinc-600 bg-zinc-900/80 text-zinc-400 hover:border-zinc-500 hover:text-zinc-200"
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      )}
      {current.description && (
        <p className="mb-3 text-xs leading-relaxed text-zinc-500">
          {current.description}
        </p>
      )}
      <PathChain path={current.path} />
    </div>
  );
}
