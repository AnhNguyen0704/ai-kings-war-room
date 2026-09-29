import { useEffect, useState } from "react";
import { useRoomStore } from "../stores/roomStore";

const PHASES = ["proposals", "discussion", "voting", "judging", "synthesis"] as const;

const STATE_STYLES: Record<string, string> = {
  IDLE: "bg-slate-700/40 text-slate-300",
  DISCUSSING: "bg-sky-500/20 text-sky-300",
  DEBATING: "bg-rose-500/20 text-rose-300 animate-pulse",
  VOTING: "bg-fuchsia-500/20 text-fuchsia-300",
  JUDGING: "bg-amber-500/20 text-amber-300 animate-pulse",
  COMPLETED: "bg-emerald-500/20 text-emerald-300",
  ERROR: "bg-red-500/20 text-red-300",
  STOPPED: "bg-slate-600/40 text-slate-400",
};

interface MemoryRow {
  id: string;
  kind: string;
  content: string;
}

export default function StatePanel() {
  const { roomState, phase, round, messages, agents, roomId, decision } = useRoomStore();
  const [tab, setTab] = useState<"state" | "log" | "memory">("state");
  const [memories, setMemories] = useState<MemoryRow[]>([]);

  useEffect(() => {
    if (tab === "memory" && roomId) {
      fetch(`/api/rooms/${roomId}/memories`)
        .then((r) => r.json())
        .then((d) => setMemories(d.memories ?? []))
        .catch(() => setMemories([]));
    }
  }, [tab, roomId, messages.length]);

  const thinking = agents.find((a) => a.status === "thinking" || a.status === "speaking");
  const currentPhaseIdx = phase ? PHASES.indexOf(phase as (typeof PHASES)[number]) : -1;

  return (
    <aside className="hidden w-72 shrink-0 flex-col border-l border-slate-800 bg-slate-950/60 xl:flex">
      <div className="flex border-b border-slate-800 text-xs">
        {(["state", "log", "memory"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`flex-1 py-2.5 font-semibold uppercase tracking-wide transition ${
              tab === t ? "bg-slate-900 text-amber-300" : "text-slate-500 hover:text-slate-300"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto p-3">
        {tab === "state" && (
          <div className="space-y-4">
            <div>
              <h4 className="mb-1.5 text-[10px] font-semibold uppercase tracking-widest text-slate-500">Room state</h4>
              <span className={`inline-block rounded-md px-2.5 py-1 text-sm font-bold ${STATE_STYLES[roomState] ?? STATE_STYLES.IDLE}`}>
                {roomState}
              </span>
            </div>

            <div>
              <h4 className="mb-2 text-[10px] font-semibold uppercase tracking-widest text-slate-500">Debate flow</h4>
              <ol className="space-y-1.5">
                {PHASES.map((p, i) => {
                  const active = currentPhaseIdx === i;
                  const done = currentPhaseIdx > i || roomState === "COMPLETED";
                  return (
                    <li
                      key={p}
                      className={`flex items-center gap-2 rounded-md px-2 py-1 text-xs ${
                        active ? "bg-slate-800 text-amber-300" : done ? "text-slate-400" : "text-slate-600"
                      }`}
                    >
                      <span className={`h-1.5 w-1.5 rounded-full ${active ? "bg-amber-400 animate-pulse" : done ? "bg-emerald-500" : "bg-slate-700"}`} />
                      {p}
                      {active && round > 0 && <span className="ml-auto text-slate-500">round {round}</span>}
                    </li>
                  );
                })}
              </ol>
            </div>

            <div className="grid grid-cols-2 gap-2 text-center">
              <div className="rounded-lg bg-slate-900 p-2.5">
                <div className="text-lg font-bold tabular-nums text-slate-100">{messages.length}</div>
                <div className="text-[10px] uppercase tracking-wide text-slate-500">Messages</div>
              </div>
              <div className="rounded-lg bg-slate-900 p-2.5">
                <div className="text-lg font-bold tabular-nums text-slate-100">{agents.filter((a) => !a.silenced).length}</div>
                <div className="text-[10px] uppercase tracking-wide text-slate-500">Active agents</div>
              </div>
            </div>

            {thinking && (
              <div className="flex items-center gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-200">
                <span className="h-2 w-2 animate-ping rounded-full bg-amber-400" />
                {thinking.name} is {thinking.status}…
              </div>
            )}

            {decision && (
              <div className="rounded-lg border border-yellow-400/30 bg-yellow-400/5 p-3">
                <h4 className="mb-1 text-[10px] font-semibold uppercase tracking-widest text-yellow-300">Last verdict</h4>
                <p className="line-clamp-4 text-xs leading-relaxed text-slate-300">{decision.decision}</p>
                <p className="mt-1.5 text-[10px] text-slate-500">confidence {Math.round(decision.confidence * 100)}%</p>
              </div>
            )}
          </div>
        )}

        {tab === "memory" && (
          <div className="space-y-2">
            {memories.length === 0 && <p className="text-xs text-slate-600">No shared memory yet. Win a debate first.</p>}
            {memories.map((m) => (
              <div key={m.id} className="rounded-lg border border-slate-800 bg-slate-900 p-2.5 text-xs text-slate-300">
                <span className="mb-1 block text-[10px] uppercase tracking-wide text-slate-500">{m.kind}</span>
                {m.content}
              </div>
            ))}
          </div>
        )}

        {tab === "log" && <EventLog />}
      </div>
    </aside>
  );
}

function EventLog() {
  const { roomId, messages } = useRoomStore();
  const [events, setEvents] = useState<Array<{ id: number; event_type: string; created_at: string }>>([]);

  useEffect(() => {
    if (!roomId) return;
    fetch(`/api/rooms/${roomId}/events?limit=80`)
      .then((r) => r.json())
      .then((d) => setEvents(d.events ?? []))
      .catch(() => setEvents([]));
  }, [roomId, messages.length]);

  return (
    <div className="space-y-1 font-mono text-[11px] leading-relaxed">
      {events.length === 0 && <p className="text-slate-600">No events recorded.</p>}
      {events.map((e) => (
        <div key={e.id} className="text-slate-500">
          <span className="text-slate-600">[{new Date(e.created_at).toLocaleTimeString()}]</span>{" "}
          <span className="text-sky-400">{e.event_type}</span>
        </div>
      ))}
    </div>
  );
}
