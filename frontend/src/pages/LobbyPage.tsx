import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../services/api";
import type { RoomListItem } from "../types";

const STATE_STYLES: Record<string, string> = {
  IDLE: "text-slate-400",
  DISCUSSING: "text-sky-300",
  DEBATING: "text-rose-300",
  VOTING: "text-fuchsia-300",
  JUDGING: "text-amber-300",
  COMPLETED: "text-emerald-300",
  ERROR: "text-red-300",
  STOPPED: "text-slate-500",
};

export default function LobbyPage() {
  const [rooms, setRooms] = useState<RoomListItem[]>([]);
  const [name, setName] = useState("");
  const [providers, setProviders] = useState<Array<{ name: string; live: boolean }>>([]);
  const navigate = useNavigate();

  const refresh = () => {
    api.listRooms().then((d) => setRooms(d.rooms)).catch(() => setRooms([]));
  };

  useEffect(() => {
    refresh();
    api.providers().then((d) => setProviders(d.providers)).catch(() => undefined);
  }, []);

  const create = async () => {
    const room = await api.createRoom(name.trim() || "New War Room");
    navigate(`/rooms/${room.id}`);
  };

  return (
    <div className="grid-lines min-h-screen">
      <header className="mx-auto flex max-w-4xl items-center justify-between px-6 pt-10">
        <h1 className="text-3xl font-black tracking-tight text-amber-300">
          👑 AI KING'S WAR ROOM
        </h1>
        <span className="text-xs text-slate-500">Multi-agent council · realtime</span>
      </header>

      <main className="mx-auto max-w-4xl px-6 pb-16">
        <p className="mt-3 max-w-2xl text-sm leading-relaxed text-slate-400">
          You are the King. GPT, Claude, Gemini, Grok and Kimi are your council — they propose,
          challenge, rebut, vote, and a Judge synthesises the final report. The final word is always yours.
        </p>

        <div className="mt-6 flex flex-wrap items-center gap-2">
          {providers.map((p) => (
            <span
              key={p.name}
              className={`rounded-full border px-2.5 py-1 text-xs font-mono ${
                p.name === "mock" || p.live
                  ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
                  : "border-slate-700 bg-slate-900 text-slate-500"
              }`}
              title={p.live ? `${p.name}: API key detected` : `${p.name}: no API key — Mock Provider will stand in`}
            >
              {p.live ? "●" : "○"} {p.name}
            </span>
          ))}
        </div>

        <div className="mt-8 flex gap-2">
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && create()}
            placeholder="New war room name…"
            className="min-w-0 flex-1 rounded-xl border border-slate-700 bg-slate-900 px-4 py-3 text-sm focus:border-amber-500/60 focus:outline-none"
          />
          <button
            onClick={create}
            className="rounded-xl bg-amber-500 px-6 py-3 text-sm font-bold text-slate-950 hover:bg-amber-400"
          >
            + CREATE ROOM
          </button>
        </div>

        <h2 className="mt-10 text-xs font-semibold uppercase tracking-widest text-slate-500">Your rooms</h2>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          {rooms.map((room) => (
            <Link
              key={room.id}
              to={`/rooms/${room.id}`}
              className="group rounded-xl border border-slate-800 bg-slate-900/70 p-4 transition hover:border-amber-500/50"
            >
              <div className="flex items-center justify-between">
                <span className="font-semibold text-slate-100 group-hover:text-amber-300">{room.name}</span>
                <span className={`text-xs font-bold ${STATE_STYLES[room.state]}`}>{room.state}</span>
              </div>
              <p className="mt-1 text-xs text-slate-500">
                {room.agent_count} agents · {room.message_count} messages
              </p>
            </Link>
          ))}
          {rooms.length === 0 && <p className="text-sm text-slate-600">No rooms yet. Create the first one.</p>}
        </div>
      </main>
    </div>
  );
}
