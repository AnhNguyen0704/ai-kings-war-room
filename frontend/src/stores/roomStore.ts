import { create } from "zustand";
import type { AgentView, DecisionView, Message, RoomEvent, RoomState } from "../types";
import { api } from "../services/api";

interface RoomStore {
  roomId: string | null;
  roomName: string;
  roomState: RoomState;
  phase: string | null;
  round: number;
  messages: Message[];
  agents: AgentView[];
  decision: DecisionView | null;
  wsConnected: boolean;
  connecting: boolean;
  error: string | null;

  connect: (roomId: string) => Promise<void>;
  disconnect: () => void;
  sendChat: (content: string) => Promise<void>;
  runCommand: (command: string, args?: string) => Promise<void>;
  clear: () => void;
}

let ws: WebSocket | null = null;
let reconnectTimer: number | null = null;
let currentRoom: string | null = null;

export const useRoomStore = create<RoomStore>((set, get) => ({
  roomId: null,
  roomName: "",
  roomState: "IDLE",
  phase: null,
  round: 0,
  messages: [],
  agents: [],
  decision: null,
  wsConnected: false,
  connecting: false,
  error: null,

  connect: async (roomId: string) => {
    get().disconnect();
    currentRoom = roomId;
    set({ connecting: true, roomId, messages: [], agents: [], decision: null, error: null });
    try {
      const snap = await api.snapshot(roomId);
      const history = await api.messages(roomId);
      set({
        roomName: snap.room.name,
        roomState: snap.room.state,
        agents: snap.agents,
        decision: snap.decision,
        messages: history.messages,
        connecting: false,
      });
    } catch (err) {
      set({ error: String(err), connecting: false });
      return;
    }
    openSocket(roomId, set, get);
  },

  disconnect: () => {
    currentRoom = null;
    if (reconnectTimer !== null) {
      window.clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    if (ws) {
      ws.onclose = null;
      ws.close();
      ws = null;
    }
    set({ wsConnected: false });
  },

  sendChat: async (content: string) => {
    const roomId = get().roomId;
    if (!roomId || !content.trim()) return;
    try {
      await api.chat(roomId, content.trim());
    } catch (err) {
      set({ error: String(err) });
    }
  },

  runCommand: async (command: string, args = "") => {
    const roomId = get().roomId;
    if (!roomId) return;
    try {
      await api.command(roomId, command, args);
    } catch (err) {
      set({ error: String(err) });
    }
  },

  clear: () => {
    get().disconnect();
    set({ roomId: null, roomName: "", messages: [], agents: [], decision: null, roomState: "IDLE", phase: null, round: 0 });
  },
}));

type SetState = (partial: Partial<RoomStore> | ((s: RoomStore) => Partial<RoomStore>)) => void;
type GetState = () => RoomStore;

function openSocket(roomId: string, set: SetState, get: GetState) {
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  const url = `${proto}://${window.location.host}/ws/rooms/${roomId}`;
  ws = new WebSocket(url);

  ws.onopen = () => set({ wsConnected: true });

  ws.onmessage = (evt) => {
    try {
      const event = JSON.parse(evt.data) as RoomEvent;
      handleEvent(event, set, get);
    } catch {
      /* ignore malformed frames */
    }
  };

  ws.onclose = () => {
    set({ wsConnected: false });
    if (currentRoom === roomId && reconnectTimer === null) {
      reconnectTimer = window.setTimeout(() => {
        reconnectTimer = null;
        if (currentRoom === roomId) openSocket(roomId, set, get);
      }, 1500);
    }
  };

  ws.onerror = () => ws?.close();
}

function handleEvent(event: RoomEvent, set: SetState, get: GetState) {
  const data = event.data ?? {};
  switch (event.event) {
    case "message_new": {
      const incoming = data as unknown as Message;
      set((s) => {
        if (s.messages.some((m) => m.id === incoming.id)) return {};
        return { messages: [...s.messages, incoming] };
      });
      break;
    }
    case "message_delta": {
      const { id, delta } = data;
      set((s) => ({
        messages: s.messages.map((m) => (m.id === id ? { ...m, content: m.content + delta } : m)),
      }));
      break;
    }
    case "message_complete": {
      const { id, content, message_type } = data;
      set((s) => ({
        messages: s.messages.map((m) =>
          m.id === id
            ? { ...m, content: content ?? m.content, message_type: (message_type as Message["message_type"]) ?? m.message_type, streaming: false }
            : m,
        ),
      }));
      break;
    }
    case "agent_status": {
      const { agent_id, status, silenced } = data;
      set((s) => ({
        agents: s.agents.map((a) =>
          a.id === agent_id ? { ...a, status: status ?? a.status, silenced: silenced ?? a.silenced } : a,
        ),
      }));
      break;
    }
    case "room_state": {
      set({ roomState: (data.state as RoomState) ?? get().roomState });
      if (data.state === "COMPLETED" || data.state === "IDLE") {
        // IDLE after a reset: full resync including the message list.
        refreshSnapshot(set, get, { resyncMessages: data.state === "IDLE" });
      }
      break;
    }
    case "debate_phase": {
      set({ phase: data.phase ?? null, round: data.round ?? 0 });
      break;
    }
    case "decision": {
      refreshSnapshot(set, get);
      break;
    }
    case "system_notice":
    case "vote_cast": {
      // informational; snapshot refresh keeps stats accurate
      refreshSnapshot(set, get);
      break;
    }
    case "error": {
      set({ error: (data.message as string) ?? "unknown error" });
      break;
    }
    default:
      break;
  }
}

let refreshTimer: number | null = null;
function refreshSnapshot(set: SetState, get: GetState, opts?: { resyncMessages?: boolean }) {
  // Debounce: many events land in quick succession during a debate.
  if (refreshTimer !== null) return;
  refreshTimer = window.setTimeout(async () => {
    refreshTimer = null;
    const roomId = get().roomId;
    if (!roomId) return;
    try {
      const snap = await api.snapshot(roomId);
      set((s) => ({
        agents: snap.agents,
        decision: snap.decision ?? s.decision,
        roomName: snap.room.name,
      }));
      if (opts?.resyncMessages) {
        const history = await api.messages(roomId);
        set({ messages: history.messages });
      }
    } catch {
      /* stale room */
    }
  }, 400);
}
