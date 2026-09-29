import type { RoomListItem, RoomSnapshot, Message } from "../types";

const BASE = "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(`${resp.status}: ${text.slice(0, 200)}`);
  }
  return resp.json() as Promise<T>;
}

export const api = {
  health: () => request<{ status: string }>("/api/health"),

  providers: () =>
    request<{ providers: Array<{ name: string; live: boolean }>; judge: string }>("/api/providers"),

  listRooms: () => request<{ rooms: RoomListItem[] }>("/api/rooms"),

  createRoom: (name: string) =>
    request<{ id: string }>("/api/rooms", { method: "POST", body: JSON.stringify({ name }) }),

  deleteRoom: (id: string) => request<{ ok: boolean }>(`/api/rooms/${id}`, { method: "DELETE" }),

  snapshot: (roomId: string) => request<RoomSnapshot>(`/api/rooms/${roomId}`),

  messages: (roomId: string) => request<{ messages: Message[] }>(`/api/rooms/${roomId}/messages`),

  chat: (roomId: string, content: string) =>
    request<{ ok: boolean }>(`/api/rooms/${roomId}/chat`, {
      method: "POST",
      body: JSON.stringify({ content }),
    }),

  command: (roomId: string, command: string, args = "") =>
    request<{ ok: boolean }>(`/api/rooms/${roomId}/commands`, {
      method: "POST",
      body: JSON.stringify({ command, args }),
    }),

  reset: (roomId: string) => request<RoomSnapshot>(`/api/rooms/${roomId}/reset`, { method: "POST" }),
};
