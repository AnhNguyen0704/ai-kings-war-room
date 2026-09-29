"""Canonical event / state / message-type vocabularies shared by backend and frontend."""


class EventType:
    ROOM_STATE = "room_state"
    AGENT_STATUS = "agent_status"
    MESSAGE_NEW = "message_new"
    MESSAGE_DELTA = "message_delta"
    MESSAGE_COMPLETE = "message_complete"
    DEBATE_PHASE = "debate_phase"
    VOTE_CAST = "vote_cast"
    DECISION = "decision"
    SYSTEM_NOTICE = "system_notice"
    ERROR = "error"
    PONG = "pong"


class RoomState:
    IDLE = "IDLE"
    DISCUSSING = "DISCUSSING"
    DEBATING = "DEBATING"
    VOTING = "VOTING"
    JUDGING = "JUDGING"
    COMPLETED = "COMPLETED"
    ERROR = "ERROR"
    STOPPED = "STOPPED"

    ALL = [IDLE, DISCUSSING, DEBATING, VOTING, JUDGING, COMPLETED, ERROR, STOPPED]


class AgentStatus:
    IDLE = "idle"
    THINKING = "thinking"
    SPEAKING = "speaking"
    LISTENING = "listening"
    DEBATING = "debating"
    WAITING = "waiting"
    ERROR = "error"
    OFFLINE = "offline"

    ALL = [IDLE, THINKING, SPEAKING, LISTENING, DEBATING, WAITING, ERROR, OFFLINE]


class MessageTypes:
    PROPOSAL = "proposal"
    QUESTION = "question"
    ANSWER = "answer"
    CHALLENGE = "challenge"
    REBUTTAL = "rebuttal"
    AGREEMENT = "agreement"
    OBSERVATION = "observation"
    VOTE = "vote"
    SYSTEM = "system"
    FINAL = "final"
    TASK = "task"
    COMMAND = "command"

    AGENT_ONLY = [PROPOSAL, QUESTION, ANSWER, CHALLENGE, REBUTTAL, AGREEMENT, OBSERVATION, VOTE, FINAL]


class DebatePhase:
    PROPOSALS = "proposals"
    DISCUSSION = "discussion"
    VOTING = "voting"
    JUDGING = "judging"
    SYNTHESIS = "synthesis"
    DONE = "done"
