import type { Message } from "../types";

const TYPE_BADGES: Record<string, { label: string; className: string }> = {
  proposal: { label: "💡 PROPOSAL", className: "bg-sky-500/15 text-sky-300 border-sky-500/30" },
  question: { label: "❓ QUESTION", className: "bg-amber-500/15 text-amber-300 border-amber-500/30" },
  answer: { label: "💬 ANSWER", className: "bg-teal-500/15 text-teal-300 border-teal-500/30" },
  challenge: { label: "⚔️ CHALLENGE", className: "bg-rose-500/15 text-rose-300 border-rose-500/30" },
  rebuttal: { label: "🛡 REBUTTAL", className: "bg-orange-500/15 text-orange-300 border-orange-500/30" },
  agreement: { label: "🤝 AGREEMENT", className: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30" },
  observation: { label: "🔭 OBSERVATION", className: "bg-indigo-500/15 text-indigo-300 border-indigo-500/30" },
  vote: { label: "🗳 VOTE", className: "bg-fuchsia-500/15 text-fuchsia-300 border-fuchsia-500/30" },
  system: { label: "⚙ SYSTEM", className: "bg-slate-500/15 text-slate-300 border-slate-500/30" },
  final: { label: "🏁 FINAL REPORT", className: "bg-yellow-400/15 text-yellow-300 border-yellow-400/40" },
  task: { label: "📜 TASK", className: "bg-yellow-500/15 text-yellow-300 border-yellow-500/30" },
  command: { label: "⌘ COMMAND", className: "bg-slate-500/15 text-slate-300 border-slate-500/30" },
};

function timeOf(iso: string): string {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "";
  }
}

export default function MessageBubble({
  message,
  targetName,
}: {
  message: Message;
  targetName?: string;
}) {
  if (message.sender_type === "system") {
    return (
      <div className="my-1 flex justify-center">
        <span className="rounded-full border border-slate-700/60 bg-slate-900/80 px-3 py-1 text-xs text-slate-400">
          {message.content}
        </span>
      </div>
    );
  }

  const badge = TYPE_BADGES[message.message_type] ?? TYPE_BADGES.observation;
  const isKing = message.sender_type === "king";
  const isJudge = message.sender_type === "judge";
  const accent = isKing ? "#f5c542" : isJudge ? "#e2e8f0" : message.agent_color || "#64748b";
  const replyTarget = (message.meta.target_name as string | undefined) ?? targetName;

  return (
    <div className={`my-2 ${isKing ? "ml-auto max-w-[85%]" : "mr-auto max-w-[85%]"}`}>
      <div
        className="rounded-xl border bg-slate-900/70 p-3 shadow"
        style={{ borderColor: `${accent}44`, borderLeft: `3px solid ${accent}` }}
      >
        <div className="mb-1.5 flex flex-wrap items-center gap-2">
          <span className="text-sm font-semibold" style={{ color: accent }}>
            {message.sender_name}
          </span>
          {message.agent_role && !isKing && !isJudge && (
            <span className="text-xs text-slate-500">{message.agent_role}</span>
          )}
          <span className="text-xs text-slate-600">{timeOf(message.created_at)}</span>
          <span className={`ml-auto rounded border px-1.5 py-0.5 text-[10px] font-semibold tracking-wide ${badge.className}`}>
            {badge.label}
          </span>
        </div>
        <div className="message-content text-sm text-slate-300">
          {message.content}
          {message.streaming ? <span className="ml-0.5 animate-pulse text-slate-500">▍</span> : null}
        </div>
        {message.reply_to_id && replyTarget && (
          <div className="mt-2 text-xs text-slate-500">
            ↳ Replying to <span className="text-slate-400">{replyTarget}</span>
          </div>
        )}
      </div>
    </div>
  );
}
