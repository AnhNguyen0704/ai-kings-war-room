export type RoomState =
  | "IDLE"
  | "DISCUSSING"
  | "DEBATING"
  | "VOTING"
  | "JUDGING"
  | "COMPLETED"
  | "ERROR"
  | "STOPPED";

export type MessageType =
  | "proposal"
  | "question"
  | "answer"
  | "challenge"
  | "rebuttal"
  | "agreement"
  | "observation"
  | "vote"
  | "system"
  | "final"
  | "task"
  | "command";

export interface Message {
  id: string;
  sender_type: "king" | "agent" | "system" | "judge";
  agent_id: string | null;
  sender_name: string;
  agent_color: string;
  agent_role: string;
  message_type: MessageType;
  content: string;
  reply_to_id: string | null;
  meta: Record<string, unknown>;
  created_at: string;
  streaming?: boolean;
}

export interface AgentStats {
  messages: number;
  challenges: number;
  agreements: number;
}

export interface AgentView {
  id: string;
  name: string;
  icon: string;
  color: string;
  role: string;
  role_title: string;
  personality: string[];
  system_prompt: string;
  behavior: Record<string, number>;
  provider: string;
  model: string;
  resolved_provider: string;
  memory_enabled: boolean;
  active: boolean;
  silenced: boolean;
  status: string;
  stats: AgentStats;
}

export interface DecisionView {
  id: string;
  debate_id: string;
  decision: string;
  reasoning: string[];
  confidence: number;
  open_questions: string[];
  dissenting_views: Array<{ agent: string; view: string }>;
  created_at: string;
}

export interface RoomSnapshot {
  room: { id: string; name: string; state: RoomState; created_at: string };
  agents: AgentView[];
  message_count: number;
  decision: DecisionView | null;
  debate: { active: boolean; phase: string | null; round: number };
}

export interface RoomListItem {
  id: string;
  name: string;
  state: RoomState;
  message_count: number;
  agent_count: number;
}

export interface RoomEvent {
  event: string;
  room_id: string;
  data: Record<string, unknown> & {
    state?: RoomState;
    id?: string;
    delta?: string;
    content?: string;
    message_type?: MessageType;
    agent_id?: string;
    name?: string;
    status?: string;
    silenced?: boolean;
    phase?: string;
    round?: number;
    notice?: string;
    message?: string;
  };
}
