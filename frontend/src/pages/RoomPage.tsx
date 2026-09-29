import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useRoomStore } from "../stores/roomStore";
import { AgentCardModal, AgentRow } from "../components/AgentList";
import MessageBubble from "../components/MessageBubble";
import StatePanel from "../components/StatePanel";
import CommandBar from "../components/CommandBar";
import type { Message } from "../types";

export default function RoomPage() {
  const { roomId = "" } = useParams();
  const { roomName, roomState, messages, agents, connect, disconnect, wsConnected, error } = useRoomStore();
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    void connect(roomId);
    return () => disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [roomId]);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages]);

  const agentById = new Map(agents.map((a) => [a.id, a]));
  const nameOfReply = (m: Message) => {
    if (!m.reply_to_id) return undefined;
    const target = messages.find((x) => x.id === m.reply_to_id);
    return target?.sender_name;
  };

  return (
    <div className="grid-lines flex h-screen flex-col">
      <header className="flex items-center gap-3 border-b border-slate-800 bg-slate-950/90 px-4 py-3">
        <Link to="/" className="text-xl transition hover:scale-110" title="Back to lobby">
          👑
        </Link>
        <div className="min-w-0">
          <h1 className="truncate text-sm font-bold tracking-wide text-amber-300">
            {roomName || "War Room"}
          </h1>
          <p className="text-[11px] text-slate-500">
            {agents.filter((a) => !a.silenced).length} AGENTS ONLINE · STATE: {roomState}
          </p>
        </div>
        <span
          className={`ml-auto flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-mono ${
            wsConnected
              ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
              : "border-red-500/30 bg-red-500/10 text-red-300"
          }`}
        >
          {wsConnected ? "● LIVE" : "○ OFFLINE"}
        </span>
      </header>

      {error && (
        <div className="border-b border-red-500/30 bg-red-500/10 px-4 py-1.5 text-xs text-red-300">{error}</div>
      )}

      <div className="flex min-h-0 flex-1">
        <aside className="hidden w-60 shrink-0 flex-col border-r border-slate-800 bg-slate-950/60 md:flex">
          <h2 className="border-b border-slate-800 px-3 py-2.5 text-[10px] font-semibold uppercase tracking-widest text-slate-500">
            Council
          </h2>
          <div className="min-h-0 flex-1 overflow-y-auto p-1.5">
            {agents.map((agent) => (
              <AgentRow key={agent.id} agent={agent} onOpen={() => setSelectedAgent(agent.id)} />
            ))}
          </div>
        </aside>

        <main ref={scrollRef} className="min-w-0 flex-1 overflow-y-auto px-4 py-3">
          {messages.length === 0 && (
            <div className="mt-16 text-center text-sm text-slate-600">
              <p className="text-4xl">👑</p>
              <p className="mt-3">Type a task below — the council will debate it and the Judge will report.</p>
              <p className="mt-1 text-xs text-slate-700">Try: “PostgreSQL hay MongoDB cho hệ thống Multi-Agent?”</p>
            </div>
          )}
          {messages.map((m) => (
            <MessageBubble key={m.id} message={m} targetName={nameOfReply(m)} />
          ))}
        </main>

        <StatePanel />
      </div>

      <CommandBar />

      {selectedAgent && (() => {
        const agent = agentById.get(selectedAgent);
        return agent ? <AgentCardModal agent={agent} onClose={() => setSelectedAgent(null)} /> : null;
      })()}
    </div>
  );
}
