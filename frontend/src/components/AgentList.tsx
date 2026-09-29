import { useState } from "react";
import type { AgentView } from "../types";

const STATUS_DOT: Record<string, string> = {
  idle: "bg-emerald-500",
  thinking: "bg-amber-400 animate-pulse",
  speaking: "bg-sky-400 animate-pulse",
  listening: "bg-slate-400",
  debating: "bg-rose-400 animate-pulse",
  waiting: "bg-slate-500",
  error: "bg-red-500",
  offline: "bg-slate-700",
};

export function AgentRow({ agent, onOpen }: { agent: AgentView; onOpen: () => void }) {
  const dot = STATUS_DOT[agent.status] ?? "bg-slate-500";
  return (
    <button
      onClick={onOpen}
      className="flex w-full items-center gap-2.5 rounded-lg border border-transparent px-2.5 py-2 text-left transition hover:border-slate-700 hover:bg-slate-900"
    >
      <span className="relative flex h-8 w-8 items-center justify-center rounded-md text-base" style={{ background: `${agent.color}1f` }}>
        {agent.icon}
        <span className={`absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 rounded-full border border-slate-950 ${dot}`} />
      </span>
      <span className="min-w-0 flex-1">
        <span className="flex items-center gap-1.5">
          <span className="truncate text-sm font-medium text-slate-200">{agent.name}</span>
          {agent.silenced && <span className="text-[10px] text-slate-600">🔇</span>}
        </span>
        <span className="block truncate text-xs text-slate-500">
          {agent.status === "thinking" ? "Thinking…" : agent.status === "speaking" ? "Speaking…" : agent.role_title}
        </span>
      </span>
      <span className="text-xs tabular-nums text-slate-600">{agent.stats.messages}</span>
    </button>
  );
}

export function AgentCardModal({ agent, onClose }: { agent: AgentView; onClose: () => void }) {
  const [confirmSilence, setConfirmSilence] = useState(false);
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" onClick={onClose}>
      <div
        className="w-full max-w-md rounded-2xl border border-slate-700 bg-slate-900 p-5 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-start justify-between">
          <div className="flex items-center gap-3">
            <span
              className="flex h-12 w-12 items-center justify-center rounded-xl text-2xl"
              style={{ background: `${agent.color}22` }}
            >
              {agent.icon}
            </span>
            <div>
              <h3 className="text-lg font-semibold text-slate-100">{agent.name}</h3>
              <p className="text-sm text-slate-500">{agent.role_title}</p>
            </div>
          </div>
          <button onClick={onClose} className="rounded-lg px-2 py-1 text-slate-500 hover:bg-slate-800 hover:text-slate-300">
            ✕
          </button>
        </div>

        <dl className="grid grid-cols-2 gap-3 text-sm">
          <div className="rounded-lg bg-slate-800/60 p-3">
            <dt className="text-xs uppercase tracking-wide text-slate-500">Status</dt>
            <dd className="mt-1 text-slate-200">{agent.status}</dd>
          </div>
          <div className="rounded-lg bg-slate-800/60 p-3">
            <dt className="text-xs uppercase tracking-wide text-slate-500">Provider</dt>
            <dd className="mt-1 text-slate-200">
              {agent.provider}
              {agent.provider !== agent.resolved_provider && (
                <span className="text-slate-500"> → {agent.resolved_provider}</span>
              )}
            </dd>
          </div>
          <div className="rounded-lg bg-slate-800/60 p-3">
            <dt className="text-xs uppercase tracking-wide text-slate-500">Model</dt>
            <dd className="mt-1 truncate text-slate-200">{agent.model || "auto"}</dd>
          </div>
          <div className="rounded-lg bg-slate-800/60 p-3">
            <dt className="text-xs uppercase tracking-wide text-slate-500">Memory</dt>
            <dd className="mt-1 text-slate-200">{agent.memory_enabled ? "Enabled" : "Off"}</dd>
          </div>
        </dl>

        <div className="mt-4">
          <h4 className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-slate-500">Personality</h4>
          <div className="flex flex-wrap gap-1.5">
            {agent.personality.map((p) => (
              <span key={p} className="rounded-full bg-slate-800 px-2.5 py-0.5 text-xs text-slate-300">
                {p}
              </span>
            ))}
          </div>
        </div>

        <div className="mt-4 grid grid-cols-3 gap-3 text-center">
          <div className="rounded-lg bg-slate-800/60 p-2.5">
            <div className="text-lg font-semibold text-slate-100 tabular-nums">{agent.stats.messages}</div>
            <div className="text-[10px] uppercase tracking-wide text-slate-500">Messages</div>
          </div>
          <div className="rounded-lg bg-slate-800/60 p-2.5">
            <div className="text-lg font-semibold text-rose-300 tabular-nums">{agent.stats.challenges}</div>
            <div className="text-[10px] uppercase tracking-wide text-slate-500">Challenges</div>
          </div>
          <div className="rounded-lg bg-slate-800/60 p-2.5">
            <div className="text-lg font-semibold text-emerald-300 tabular-nums">{agent.stats.agreements}</div>
            <div className="text-[10px] uppercase tracking-wide text-slate-500">Agreements</div>
          </div>
        </div>

        <div className="mt-4 rounded-lg bg-slate-800/40 p-3">
          <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">System prompt</h4>
          <p className="max-h-24 overflow-y-auto text-xs leading-relaxed text-slate-400">{agent.system_prompt}</p>
        </div>

        {confirmSilence ? (
          <div className="mt-4 flex gap-2">
            <button
              onClick={() => {
                setConfirmSilence(false);
              }}
              className="flex-1 rounded-lg bg-slate-700 py-2 text-sm text-slate-200 hover:bg-slate-600"
            >
              Cancel
            </button>
          </div>
        ) : (
          <p className="mt-4 text-center text-xs text-slate-600">
            Use commands in the composer to silence or activate this agent
          </p>
        )}
      </div>
    </div>
  );
}
