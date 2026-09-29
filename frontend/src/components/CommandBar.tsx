import { useState } from "react";
import { useRoomStore } from "../stores/roomStore";

export default function CommandBar() {
  const { sendChat, runCommand, roomState, wsConnected } = useRoomStore();
  const [text, setText] = useState("");
  const debateActive = ["DISCUSSING", "DEBATING", "VOTING", "JUDGING"].includes(roomState);

  const submit = () => {
    if (!text.trim()) return;
    void sendChat(text);
    setText("");
  };

  return (
    <footer className="border-t border-slate-800 bg-slate-950/90 p-3">
      <div className="mb-2 flex flex-wrap gap-1.5">
        <ActionButton
          label="⚔️ Debate"
          title="Run the full debate on the text in the composer"
          disabled={debateActive || !text.trim()}
          onClick={() => {
            void runCommand("debate", text);
            setText("");
          }}
        />
        <ActionButton label="⏹ Stop" disabled={!debateActive} onClick={() => void runCommand("stop")} />
        <ActionButton label="🗳 Vote" disabled={!debateActive} onClick={() => void runCommand("vote")} />
        <ActionButton label="⚖ Judge" disabled={!debateActive} onClick={() => void runCommand("judge")} />
        <ActionButton
          label="♻ Reset"
          onClick={() => {
            if (window.confirm("Reset this room? All messages and memory will be cleared.")) void runCommand("reset");
          }}
        />
      </div>
      <div className="flex items-center gap-2">
        <span className="text-xl">👑</span>
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submit()}
          placeholder={debateActive ? "Debate in progress — commands only (e.g. /stop)…" : "Command the Council… (Enter = full debate, /ask for quick answers)"}
          className="min-w-0 flex-1 rounded-xl border border-slate-700 bg-slate-900 px-4 py-2.5 text-sm text-slate-200 placeholder:text-slate-600 focus:border-amber-500/60 focus:outline-none"
        />
        <button
          onClick={submit}
          disabled={!text.trim()}
          className="rounded-xl bg-amber-500 px-5 py-2.5 text-sm font-bold text-slate-950 transition hover:bg-amber-400 disabled:cursor-not-allowed disabled:opacity-40"
        >
          SEND
        </button>
      </div>
      {!wsConnected && <p className="mt-1.5 text-[11px] text-red-400">⚠ Realtime connection lost — retrying…</p>}
    </footer>
  );
}

function ActionButton({
  label,
  onClick,
  disabled,
  title,
}: {
  label: string;
  onClick: () => void;
  disabled?: boolean;
  title?: string;
}) {
  return (
    <button
      title={title}
      onClick={onClick}
      disabled={disabled}
      className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-1.5 text-xs font-medium text-slate-300 transition hover:border-amber-500/50 hover:text-amber-300 disabled:cursor-not-allowed disabled:opacity-35"
    >
      {label}
    </button>
  );
}
