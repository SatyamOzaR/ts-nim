"use client";

import { useState, useRef, useEffect } from "react";
import { PathHighlight, type PathOption } from "./PathHighlight";
import { WelcomeModal } from "./WelcomeModal";
import { FileUploader } from "./FileUploader";
import { BACKEND_URL, apiHeaders } from "../lib/api";

interface ToolResult {
  type: string;
  data: unknown;
}

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  tool_name?: string | null;
  tool_result?: ToolResult | null;
}

function MarkdownText({ text }: { text: string }) {
  const lines = text.split("\n");
  return (
    <div className="whitespace-pre-wrap text-sm space-y-1">
      {lines.map((line, i) => {
        const isBullet = /^[\s]*[-*•]\s+/.test(line);
        const content = isBullet ? line.replace(/^[\s]*[-*•]\s+/, "") : line;
        const rendered = formatInline(content);

        if (isBullet) {
          return (
            <div key={i} className="flex gap-1.5 items-start pl-1">
              <span className="text-zinc-500 mt-0.5">•</span>
              <span>{rendered}</span>
            </div>
          );
        }
        return <div key={i}>{rendered}</div>;
      })}
    </div>
  );
}

function formatInline(text: string): React.ReactNode[] {
  const parts: React.ReactNode[] = [];
  const regex = /(\*\*(.+?)\*\*)|(\*(.+?)\*)|(`(.+?)`)/g;
  let last = 0;
  let match;
  let key = 0;

  while ((match = regex.exec(text)) !== null) {
    if (match.index > last) {
      parts.push(text.slice(last, match.index));
    }
    if (match[2]) {
      parts.push(<strong key={key++} className="font-semibold text-zinc-100">{match[2]}</strong>);
    } else if (match[4]) {
      parts.push(<em key={key++}>{match[4]}</em>);
    } else if (match[6]) {
      parts.push(
        <code key={key++} className="rounded bg-zinc-700 px-1 py-0.5 text-xs font-mono text-indigo-300">
          {match[6]}
        </code>
      );
    }
    last = match.index + match[0].length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts;
}

function CollapsibleResults({ label, children }: { label: string; children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="mt-2">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1 text-xs font-medium text-indigo-400 hover:text-indigo-300 transition-colors"
      >
        <svg
          width="12"
          height="12"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          className={`transition-transform ${open ? "rotate-90" : ""}`}
        >
          <path d="M9 18l6-6-6-6" />
        </svg>
        {label}
      </button>
      {open && <div className="mt-1">{children}</div>}
    </div>
  );
}

function SearchResultCard({ results }: { results: Record<string, unknown>[] }) {
  if (!results?.length) return <p className="text-sm text-zinc-400">No contacts found.</p>;
  return (
    <div className="my-2 space-y-2">
      {results.map((r, i) => (
        <div
          key={i}
          className="rounded-lg border border-zinc-700 bg-zinc-800/50 p-3"
        >
          <div className="flex items-center justify-between">
            <span className="font-medium text-zinc-100">{r.name as string}</span>
            <span className="rounded-full bg-indigo-500/20 px-2 py-0.5 text-xs font-semibold text-indigo-400">
              {(r.strength as number)?.toFixed(2) ?? "N/A"}
            </span>
          </div>
          <div className="mt-0.5 text-xs text-zinc-400">
            {(r.role as string) || "N/A"} @ {(r.company as string) || "N/A"}
          </div>
          {(r.known_by as string[])?.length > 0 && (
            <div className="mt-1 text-xs text-zinc-500">
              Known by: {(r.known_by as string[]).join(", ")}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

interface ScoreData {
  name: string;
  company: string;
  role?: string;
  overall: number;
  recency: number;
  seniority: number;
  interaction_frequency: number;
  shared_connections: number;
  source_diversity: boolean;
  interaction_count?: number;
  last_touch?: string | null;
  known_by?: string[];
}

function ScoreCard({ data }: { data: Record<string, unknown> }) {
  if (!data) return null;
  const d = data as unknown as ScoreData;

  const bars: { label: string; value: number; weight: string; rawLabel: string }[] = [
    { label: "Recency",       value: d.recency,              weight: "25%", rawLabel: d.recency?.toFixed(2) },
    { label: "Seniority",     value: d.seniority,            weight: "25%", rawLabel: d.seniority?.toFixed(2) },
    {
      label: "Shared conns",
      value: d.shared_connections >= 3 ? 1 : d.shared_connections >= 2 ? 0.6 : 0.2,
      weight: "20%",
      rawLabel: String(d.shared_connections),
    },
    {
      label: "Interactions",
      value: d.interaction_frequency,
      weight: "10%",
      rawLabel: d.interaction_frequency >= 1 ? "≥5" : d.interaction_frequency >= 0.5 ? "≥2" : "0",
    },
    {
      label: "Src diversity",
      value: d.source_diversity ? 1 : 0,
      weight: "20%",
      rawLabel: d.source_diversity ? "Yes" : "No",
    },
  ];

  return (
    <div className="my-2 rounded-xl border border-zinc-700 bg-zinc-800/50 p-4">
      <div className="mb-3 flex items-start justify-between gap-2">
        <div>
          <h4 className="text-sm font-semibold text-zinc-100">
            {d.name}
            <span className="ml-1.5 font-normal text-zinc-400">@ {d.company}</span>
          </h4>
          {d.role && <p className="mt-0.5 text-xs text-zinc-500">{d.role}</p>}
        </div>
        <span className="shrink-0 rounded-lg bg-indigo-500/15 px-2.5 py-1 text-base font-bold text-indigo-300">
          {d.overall?.toFixed(2)}
        </span>
      </div>

      <div className="mb-3 h-1.5 w-full overflow-hidden rounded-full bg-zinc-700">
        <div
          className="h-full rounded-full bg-indigo-500 transition-all"
          style={{ width: `${(d.overall ?? 0) * 100}%` }}
        />
      </div>

      <div className="space-y-2">
        {bars.map((b) => (
          <div key={b.label} className="flex items-center gap-2">
            <span className="w-24 shrink-0 text-[11px] text-zinc-400">{b.label}</span>
            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-zinc-700">
              <div
                className="h-full rounded-full bg-zinc-400 transition-all"
                style={{ width: `${(b.value ?? 0) * 100}%` }}
              />
            </div>
            <span className="w-8 shrink-0 text-right text-[11px] text-zinc-500">{b.rawLabel}</span>
            <span className="w-7 shrink-0 text-[10px] text-zinc-600">{b.weight}</span>
          </div>
        ))}
      </div>

      {((d.interaction_count ?? 0) > 0 || d.last_touch) && (
        <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-zinc-700/60 pt-3">
          {(d.interaction_count ?? 0) > 0 && (
            <span className="flex items-center gap-1 text-[11px] text-zinc-400">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" />
              </svg>
              {d.interaction_count} interaction{d.interaction_count !== 1 ? "s" : ""}
            </span>
          )}
          {d.last_touch && (
            <span className="flex items-center gap-1 text-[11px] text-zinc-400">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>
              </svg>
              Last touch: {d.last_touch}
            </span>
          )}
        </div>
      )}

      {d.known_by && d.known_by.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1">
          {d.known_by.map((m) => (
            <span key={m} className="rounded-full bg-indigo-500/10 px-2 py-0.5 text-[11px] text-indigo-400">
              {m}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

export function ChatInterface() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [sourceMember, setSourceMember] = useState("");
  const [loading, setLoading] = useState(false);
  const [showUploader, setShowUploader] = useState(false);
  const [showWelcome, setShowWelcome] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  // Load persisted name on mount; show welcome modal if missing
  useEffect(() => {
    const stored = localStorage.getItem("nim_user_name");
    if (stored) {
      setSourceMember(stored);
    } else {
      setShowWelcome(true);
    }
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const sendMessage = async () => {
    const text = input.trim();
    if (!text || loading) return;

    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: "user",
      content: text,
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const resp = await fetch(`${BACKEND_URL}/api/chat`, {
        method: "POST",
        headers: apiHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({
          message: text,
          history: messages.slice(-10).map((m) => ({
            role: m.role,
            content: m.content,
          })),
          source_member: sourceMember,
        }),
      });

      const data = await resp.json();
      const assistantMsg: Message = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: data.text || "No response",
        tool_name: data.tool_name,
        tool_result: data.tool_result,
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: "Failed to connect to the backend. Is it running?",
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const renderToolResult = (msg: Message) => {
    if (!msg.tool_result) return null;
    const { type, data } = msg.tool_result;

    if (type === "path" && data) {
      if (
        typeof data === "object" &&
        !Array.isArray(data) &&
        Array.isArray((data as { options?: unknown }).options) &&
        (data as { options: unknown[] }).options.length > 0
      ) {
        return (
          <PathHighlight
            options={(data as { options: PathOption[] }).options}
          />
        );
      }
      if (Array.isArray(data) && data.length > 0) {
        return <PathHighlight path={data} />;
      }
    }
    if (type === "search" && Array.isArray(data) && data.length > 0) {
      return <CollapsibleResults label={`${data.length} contact${data.length === 1 ? "" : "s"} found`}>
        <SearchResultCard results={data as Record<string, unknown>[]} />
      </CollapsibleResults>;
    }
    if (type === "score" && data) {
      return <ScoreCard data={data as Record<string, unknown>} />;
    }
    return null;
  };

  return (
    <div className="flex h-full flex-col">
      {/* Slim identity chip — no editable fields */}
      {sourceMember && (
        <div className="flex items-center justify-end gap-2 border-b border-zinc-800 bg-zinc-900/50 px-6 py-1.5">
          <span className="text-xs text-zinc-500">Acting as</span>
          <span className="rounded-full bg-indigo-500/15 px-2.5 py-0.5 text-xs font-medium text-indigo-300">
            {sourceMember}
          </span>
          <button
            onClick={() => setShowWelcome(true)}
            className="text-xs text-zinc-600 hover:text-zinc-400"
          >
            change
          </button>
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-4">
        <div className="mx-auto max-w-3xl space-y-4">
          {messages.length === 0 && (
            <div className="pt-12">
              {/* Header */}
              <div className="mb-8 flex flex-col items-center text-center">
                <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-indigo-600/20">
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-indigo-400">
                    <path d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                    <path d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                  </svg>
                </div>
                <h2 className="text-lg font-semibold text-zinc-200">Network Intelligence</h2>
                <p className="mt-1 text-sm text-zinc-500">Ask anything about your network, or pick a suggestion below.</p>
              </div>

              <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
                {/* Suggested questions */}
                <div>
                  <p className="mb-2.5 text-[11px] font-semibold uppercase tracking-wider text-zinc-600">Try asking</p>
                  <div className="space-y-1.5">
                    {([
                      "Who do we know at Goldman Sachs?",
                      "Find a warm path to the CIO at Barclays",
                      "Who are our strongest relationships?",
                      "Which relationships have gone cold?",
                      "How many contacts does each team member have?",
                      "Who knows both Goldman Sachs and TPG Capital?",
                      "Give me a network health overview",
                      "Who have we added recently?",
                    ] as string[]).map((q) => (
                      <button
                        key={q}
                        onClick={() => setInput(q)}
                        className="block w-full rounded-lg border border-zinc-800 px-3.5 py-2 text-left text-sm text-zinc-400 transition-colors hover:border-indigo-500/50 hover:bg-indigo-500/5 hover:text-zinc-200"
                      >
                        {q}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Tools grid */}
                <div>
                  <p className="mb-2.5 text-[11px] font-semibold uppercase tracking-wider text-zinc-600">Available tools</p>
                  <div className="grid grid-cols-2 gap-2">
                    {([
                      { icon: "🔗", name: "Warm path", desc: "Find the shortest introduction chain to any person across 3 strategies: fewest hops, strongest ties, and most teammate handoffs." },
                      { icon: "🔍", name: "Search network", desc: "Search all contacts by company name and/or role. Returns strength scores and which team members know each contact." },
                      { icon: "📊", name: "Score relationship", desc: "Detailed strength breakdown for a specific contact: recency, seniority, shared connections, interaction frequency, and source diversity." },
                      { icon: "🏆", name: "Top contacts", desc: "Rank all relationships by strength score. Filter by team member. Shows interaction count and last touch date." },
                      { icon: "🧊", name: "Cold relationships", desc: "Surface relationships with no recorded interaction in the last N months — so you can re-engage before they go stale." },
                      { icon: "👥", name: "Team coverage", desc: "Per-member stats: how many contacts each team member owns, average strength, and total interactions logged." },
                      { icon: "🌐", name: "Network health", desc: "Top-level dashboard: total contacts, companies covered, strong vs cold relationships, and deepest coverage by firm." },
                      { icon: "🤝", name: "Mutual connections", desc: "Find people connected to both of two targets — great for bridging two companies or finding common ground." },
                      { icon: "🕒", name: "Recent activity", desc: "List contacts connected or interacted with in the last N days. Filter by team member to see individual activity." },
                    ] as { icon: string; name: string; desc: string }[]).map((tool) => (
                      <div
                        key={tool.name}
                        className="group relative rounded-lg border border-zinc-800 bg-zinc-900/40 px-3 py-2.5 transition-colors hover:border-zinc-600"
                      >
                        <div className="flex items-center gap-2">
                          <span className="text-base leading-none">{tool.icon}</span>
                          <span className="text-xs font-medium text-zinc-300">{tool.name}</span>
                        </div>
                        {/* Tooltip */}
                        <div className="pointer-events-none absolute bottom-full left-0 z-20 mb-2 w-56 rounded-lg border border-zinc-700 bg-zinc-800 p-3 text-[11px] leading-relaxed text-zinc-300 opacity-0 shadow-xl transition-opacity group-hover:opacity-100">
                          <p className="mb-1 font-semibold text-zinc-200">{tool.name}</p>
                          {tool.desc}
                          <div className="absolute -bottom-1.5 left-4 h-3 w-3 rotate-45 border-b border-r border-zinc-700 bg-zinc-800" />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}

          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-[85%] rounded-2xl px-4 py-2.5 ${
                  msg.role === "user"
                    ? "bg-indigo-600 text-white"
                    : "bg-zinc-800 text-zinc-200"
                }`}
              >
                {msg.role === "assistant" ? (
                  <MarkdownText text={msg.content} />
                ) : (
                  <p className="whitespace-pre-wrap text-sm">{msg.content}</p>
                )}
                {msg.role === "assistant" && renderToolResult(msg)}
              </div>
            </div>
          ))}

          {loading && (
            <div className="flex justify-start">
              <div className="rounded-2xl bg-zinc-800 px-4 py-3">
                <div className="flex gap-1">
                  <span className="h-2 w-2 animate-bounce rounded-full bg-zinc-500" />
                  <span className="h-2 w-2 animate-bounce rounded-full bg-zinc-500 [animation-delay:0.1s]" />
                  <span className="h-2 w-2 animate-bounce rounded-full bg-zinc-500 [animation-delay:0.2s]" />
                </div>
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>
      </div>

      {/* Input bar */}
      <div className="border-t border-zinc-800 bg-zinc-900/80 px-6 py-3">
        <div className="mx-auto flex max-w-3xl items-end gap-2">
          {/* + button opens file uploader */}
          <button
            type="button"
            onClick={() => setShowUploader(true)}
            title="Import files"
            className="shrink-0 rounded-xl border border-zinc-700 bg-zinc-800 p-2.5 text-zinc-400 transition-colors hover:border-zinc-500 hover:text-zinc-200"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 5v14M5 12h14" />
            </svg>
          </button>

          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
              }
            }}
            placeholder="Ask about your network..."
            rows={1}
            className="flex-1 resize-none rounded-xl border border-zinc-700 bg-zinc-800 px-4 py-2.5 text-sm text-zinc-100 placeholder-zinc-500 outline-none focus:border-indigo-500"
          />
          <button
            onClick={sendMessage}
            disabled={loading || !input.trim()}
            className="shrink-0 rounded-xl bg-indigo-600 p-2.5 text-white transition-colors hover:bg-indigo-500 disabled:opacity-40"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" />
            </svg>
          </button>
        </div>
      </div>

      {showWelcome && (
        <WelcomeModal
          onConfirm={(name) => {
            setSourceMember(name);
            setShowWelcome(false);
          }}
        />
      )}

      {showUploader && (
        <FileUploader
          memberName={sourceMember}
          onClose={() => setShowUploader(false)}
          onSuccess={(result) => {
            setShowUploader(false);
            const summary = result.summary
              || `Imported ${result.imported} new contacts, merged ${result.merged}.`;
            setMessages((prev) => [
              ...prev,
              {
                id: crypto.randomUUID(),
                role: "assistant",
                content: summary,
              },
            ]);
          }}
        />
      )}
    </div>
  );
}
