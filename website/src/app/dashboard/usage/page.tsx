"use client";

import { useEffect, useState, useCallback } from "react";
import { fetchApi } from "@/lib/api";
import {
  BarChart3, Clock, Cpu, Calendar, ChevronRight,
  X, Zap, MessageSquare, Hash, Timer, Building2,
} from "lucide-react";

interface SessionInfo {
  session_id: string;
  status: string;
  started_at: string;
  ended_at: string | null;
  duration_seconds: number;
  company: string;
  model: string;
  llm_calls: number;
  total_tokens: number;
}

function formatDuration(seconds: number): string {
  if (!seconds || seconds < 1) return "—";
  if (seconds < 60) return `${seconds}s`;
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  if (m < 60) return s > 0 ? `${m}m ${s}s` : `${m}m`;
  const h = Math.floor(m / 60);
  return `${h}h ${m % 60}m`;
}

function formatDate(iso: string): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short", day: "numeric", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

function formatDateShort(iso: string): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short", day: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    active: "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20",
    completed: "bg-[rgba(255,255,255,0.05)] text-[var(--text-muted)] border border-[var(--border)]",
    expired: "bg-red-500/10 text-red-400 border border-red-500/20",
  };
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${styles[status] ?? styles.completed}`}>
      {status}
    </span>
  );
}

function ModelBadge({ model }: { model: string }) {
  if (!model) return <span className="text-[var(--text-muted)]">—</span>;
  const isAnthropic = model.includes("claude");
  const color = isAnthropic ? "text-[#f59e0b]" : "text-[var(--cyan)]";
  const short = model.replace("claude-", "").replace("-4-5", "").replace("gpt-", "").replace("-turbo", "");
  return (
    <div className="flex items-center gap-1.5">
      <Cpu className={`w-3.5 h-3.5 ${color}`} />
      <span className="text-white text-xs font-mono">{short}</span>
    </div>
  );
}

// ── Session Detail Panel ──────────────────────────────────────────────────────

function SessionDetailPanel({
  session,
  onClose,
}: {
  session: SessionInfo;
  onClose: () => void;
}) {
  const stats = [
    {
      icon: <Timer className="w-4 h-4 text-[var(--cyan)]" />,
      label: "Duration",
      value: formatDuration(session.duration_seconds),
    },
    {
      icon: <Zap className="w-4 h-4 text-[#f59e0b]" />,
      label: "AI Calls",
      value: session.llm_calls.toString(),
    },
    {
      icon: <Hash className="w-4 h-4 text-purple-400" />,
      label: "Total Tokens",
      value: session.total_tokens > 0 ? session.total_tokens.toLocaleString() : "—",
    },
    {
      icon: <MessageSquare className="w-4 h-4 text-emerald-400" />,
      label: "Status",
      value: session.status,
    },
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="w-full max-w-lg bg-[var(--card-bg)] border border-[var(--border)] rounded-2xl shadow-2xl overflow-hidden animate-in slide-in-from-bottom-4 duration-200">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--border)]">
          <div>
            <h2 className="text-white font-semibold text-lg">Session Details</h2>
            <p className="text-[var(--text-muted)] text-xs mt-0.5">
              {formatDate(session.started_at)}
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-[var(--text-muted)] hover:text-white hover:bg-[rgba(255,255,255,0.08)] transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Body */}
        <div className="px-6 py-5 space-y-5">
          {/* Company */}
          {session.company && (
            <div className="flex items-center gap-3 p-3 rounded-xl bg-[rgba(255,255,255,0.03)] border border-[var(--border)]">
              <Building2 className="w-4 h-4 text-[var(--cyan)] shrink-0" />
              <div>
                <p className="text-[var(--text-muted)] text-xs">Company / Context</p>
                <p className="text-white font-medium text-sm mt-0.5">{session.company}</p>
              </div>
            </div>
          )}

          {/* Model */}
          <div className="flex items-center gap-3 p-3 rounded-xl bg-[rgba(255,255,255,0.03)] border border-[var(--border)]">
            <Cpu className="w-4 h-4 text-[var(--cyan)] shrink-0" />
            <div>
              <p className="text-[var(--text-muted)] text-xs">AI Model</p>
              <p className="text-white font-medium text-sm mt-0.5">{session.model || "—"}</p>
            </div>
          </div>

          {/* Stats grid */}
          <div className="grid grid-cols-2 gap-3">
            {stats.map((s) => (
              <div key={s.label} className="p-3 rounded-xl bg-[rgba(255,255,255,0.03)] border border-[var(--border)]">
                <div className="flex items-center gap-2 mb-1.5">
                  {s.icon}
                  <span className="text-[var(--text-muted)] text-xs">{s.label}</span>
                </div>
                <p className="text-white font-semibold text-base font-mono">{s.value}</p>
              </div>
            ))}
          </div>

          {/* Time range */}
          <div className="p-3 rounded-xl bg-[rgba(255,255,255,0.03)] border border-[var(--border)]">
            <div className="flex items-center gap-2 mb-2">
              <Calendar className="w-4 h-4 text-[var(--cyan)]" />
              <span className="text-[var(--text-muted)] text-xs">Time Range</span>
            </div>
            <div className="flex items-center gap-2 text-sm">
              <span className="text-white">{formatDateShort(session.started_at)}</span>
              {session.ended_at && (
                <>
                  <ChevronRight className="w-3.5 h-3.5 text-[var(--text-muted)]" />
                  <span className="text-white">{formatDateShort(session.ended_at)}</span>
                </>
              )}
            </div>
          </div>

          {/* Session ID */}
          <div className="flex items-center justify-between p-3 rounded-xl bg-[rgba(255,255,255,0.02)] border border-[var(--border)]">
            <span className="text-[var(--text-muted)] text-xs">Session ID</span>
            <span className="text-[var(--text-muted)] text-xs font-mono">
              {session.session_id.slice(0, 8)}…{session.session_id.slice(-4)}
            </span>
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-[var(--border)] flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-lg bg-[rgba(255,255,255,0.06)] hover:bg-[rgba(255,255,255,0.10)] text-[var(--text-secondary)] text-sm font-medium transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function UsagePage() {
  const [sessions, setSessions] = useState<SessionInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<SessionInfo | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  useEffect(() => {
    fetchApi("/sessions/history?limit=50")
      .then((data) => setSessions(data.sessions || []))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const handleRowClick = useCallback(async (s: SessionInfo) => {
    // Optimistically show with data we already have, then fetch full detail
    setSelected(s);
    setDetailLoading(true);
    try {
      const detail = await fetchApi(`/sessions/${s.session_id}`);
      setSelected(detail);
    } catch {
      // Keep the optimistic data if detail fetch fails
    } finally {
      setDetailLoading(false);
    }
  }, []);

  // Summary stats
  const totalSessions = sessions.length;
  const totalDuration = sessions.reduce((a, s) => a + (s.duration_seconds || 0), 0);
  const totalLlmCalls = sessions.reduce((a, s) => a + (s.llm_calls || 0), 0);
  const totalTokens = sessions.reduce((a, s) => a + (s.total_tokens || 0), 0);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-white mb-2 flex items-center gap-3">
          <BarChart3 className="w-8 h-8 text-[var(--cyan)]" />
          Usage History
        </h1>
        <p className="text-[var(--text-secondary)]">
          Review your past interview sessions. Click any row to see details.
        </p>
      </div>

      {/* Summary cards */}
      {!loading && sessions.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          {[
            { label: "Sessions", value: totalSessions.toString(), icon: <BarChart3 className="w-4 h-4 text-[var(--cyan)]" /> },
            { label: "Total Time", value: formatDuration(totalDuration), icon: <Clock className="w-4 h-4 text-[#f59e0b]" /> },
            { label: "AI Calls", value: totalLlmCalls.toString(), icon: <Zap className="w-4 h-4 text-purple-400" /> },
            { label: "Tokens Used", value: totalTokens > 0 ? totalTokens.toLocaleString() : "—", icon: <Hash className="w-4 h-4 text-emerald-400" /> },
          ].map((card) => (
            <div key={card.label} className="p-4 rounded-xl border border-[var(--border)] bg-[var(--card-bg)]">
              <div className="flex items-center gap-2 mb-2">
                {card.icon}
                <span className="text-[var(--text-muted)] text-xs font-medium uppercase tracking-wider">{card.label}</span>
              </div>
              <p className="text-white text-2xl font-bold font-mono">{card.value}</p>
            </div>
          ))}
        </div>
      )}

      {/* Table */}
      {loading ? (
        <div className="flex justify-center py-16">
          <div className="w-8 h-8 border-4 border-[var(--cyan)] border-t-transparent rounded-full animate-spin" />
        </div>
      ) : sessions.length === 0 ? (
        <div className="text-center py-16 text-[var(--text-muted)]">
          <BarChart3 className="w-12 h-12 mx-auto mb-4 opacity-30" />
          <p className="text-lg font-medium">No sessions yet</p>
          <p className="text-sm mt-1">Your interview sessions will appear here once you start using GlassNote.</p>
        </div>
      ) : (
        <div className="rounded-xl border border-[var(--border)] overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-[rgba(255,255,255,0.03)] border-b border-[var(--border)]">
                <th className="text-left px-4 py-3 text-[var(--text-muted)] font-medium text-xs uppercase tracking-wider">Date</th>
                <th className="text-left px-4 py-3 text-[var(--text-muted)] font-medium text-xs uppercase tracking-wider hidden sm:table-cell">Company</th>
                <th className="text-left px-4 py-3 text-[var(--text-muted)] font-medium text-xs uppercase tracking-wider">Duration</th>
                <th className="text-left px-4 py-3 text-[var(--text-muted)] font-medium text-xs uppercase tracking-wider hidden md:table-cell">Model</th>
                <th className="text-left px-4 py-3 text-[var(--text-muted)] font-medium text-xs uppercase tracking-wider hidden md:table-cell">AI Calls</th>
                <th className="text-left px-4 py-3 text-[var(--text-muted)] font-medium text-xs uppercase tracking-wider">Status</th>
                <th className="px-4 py-3 w-8" />
              </tr>
            </thead>
            <tbody>
              {sessions.map((s) => (
                <tr
                  key={s.session_id}
                  onClick={() => handleRowClick(s)}
                  className="border-b border-[var(--border)] hover:bg-[rgba(255,255,255,0.04)] transition-colors cursor-pointer group"
                >
                  <td className="px-4 py-3 text-[var(--text-secondary)]">
                    <div className="flex items-center gap-2">
                      <Calendar className="w-3.5 h-3.5 text-[var(--text-muted)] shrink-0" />
                      <span className="text-xs">{formatDateShort(s.started_at)}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3 hidden sm:table-cell">
                    {s.company ? (
                      <div className="flex items-center gap-1.5">
                        <Building2 className="w-3.5 h-3.5 text-[var(--text-muted)] shrink-0" />
                        <span className="text-white text-xs truncate max-w-[120px]">{s.company}</span>
                      </div>
                    ) : (
                      <span className="text-[var(--text-muted)] text-xs">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-white font-mono text-xs">
                    <div className="flex items-center gap-1.5">
                      <Clock className="w-3.5 h-3.5 text-[var(--text-muted)] shrink-0" />
                      {formatDuration(s.duration_seconds)}
                    </div>
                  </td>
                  <td className="px-4 py-3 hidden md:table-cell">
                    <ModelBadge model={s.model} />
                  </td>
                  <td className="px-4 py-3 text-white font-mono text-xs hidden md:table-cell">
                    <div className="flex items-center gap-1.5">
                      <Zap className="w-3.5 h-3.5 text-[var(--text-muted)] shrink-0" />
                      {s.llm_calls}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={s.status} />
                  </td>
                  <td className="px-4 py-3">
                    <ChevronRight className="w-4 h-4 text-[var(--text-muted)] group-hover:text-[var(--cyan)] transition-colors" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Detail panel */}
      {selected && (
        <SessionDetailPanel
          session={selected}
          onClose={() => setSelected(null)}
        />
      )}

      {/* Detail loading overlay (subtle) */}
      {detailLoading && selected && (
        <div className="fixed bottom-6 right-6 z-[60] flex items-center gap-2 px-4 py-2 rounded-full bg-[var(--card-bg)] border border-[var(--border)] shadow-lg text-sm text-[var(--text-secondary)]">
          <div className="w-3.5 h-3.5 border-2 border-[var(--cyan)] border-t-transparent rounded-full animate-spin" />
          Loading details…
        </div>
      )}
    </div>
  );
}
