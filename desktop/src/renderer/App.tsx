import {
  Activity,
  BarChart3,
  Bell,
  BellOff,
  Clock3,
  Copy,
  Cpu,
  Database,
  Download,
  Mic,
  MicOff,
  Play,
  Pencil,
  RefreshCw,
  SearchCheck,
  Save,
  Send,
  Settings,
  ShieldCheck,
  SlidersHorizontal,
  Square,
  Trash2,
  Volume2,
  VolumeX,
  Zap
} from "lucide-react";
import { FormEvent, useEffect, useRef, useState } from "react";
import { Live2DAvatar, type Live2DStatus } from "./Live2DAvatar";

type Role = "user" | "assistant" | "system";

type Message = {
  role: Role;
  content: string;
};

type MemoryHit = {
  id: number;
  kind: string;
  content: string;
  score: number;
};

type MemoryCardItem = {
  id: number;
  kind: string;
  content: string;
  importance: number;
  confidence: number;
  source_message_id?: number | null;
  created_at: string;
  updated_at: string;
};

type MemoryCardSection = {
  kind: string;
  title: string;
  items: MemoryCardItem[];
};

type MemoryCard = {
  title: string;
  session_id: string;
  generated_at: string;
  memory_count: number;
  conversation_count: number;
  latest_message_at?: string | null;
  summary: string;
  sections: MemoryCardSection[];
  markdown: string;
};

type MemoryCardExportFormat = "markdown" | "json";

type MemoryCardExport = {
  format: MemoryCardExportFormat;
  filename: string;
  content: string;
  mime_type: string;
};

type MemoryDeactivationResult = {
  id: number;
  deactivated: boolean;
  reason: string;
  memory?: MemoryCardItem | null;
};

type MemoryUpdateResult = {
  id: number;
  updated: boolean;
  reason: string;
  memory?: MemoryCardItem | null;
};

type MemoryCardSnapshotSummary = {
  id: number;
  session_id: string;
  label?: string | null;
  memory_count: number;
  conversation_count: number;
  summary: string;
  generated_at: string;
  created_at: string;
};

type MemoryCardSnapshot = MemoryCardSnapshotSummary & {
  card: MemoryCard;
  markdown: string;
};

type MemoryCardDiffItem = {
  kind: string;
  content: string;
  id?: number | null;
};

type MemoryCardDiffSection = {
  kind: string;
  title: string;
  added: MemoryCardDiffItem[];
  removed: MemoryCardDiffItem[];
};

type MemoryCardComparison = {
  snapshot: MemoryCardSnapshot;
  current: MemoryCard;
  diff: {
    added_count: number;
    removed_count: number;
    unchanged_count: number;
    sections: MemoryCardDiffSection[];
  };
};

type MemoryReflectionTheme = {
  kind: string;
  title: string;
  count: number;
  headline: string;
  evidence: string[];
  next_focus: string;
};

type MemoryReflectionSummary = {
  title: string;
  session_id: string;
  generated_at: string;
  memory_count: number;
  conversation_count: number;
  sample_ready: boolean;
  readiness: string;
  summary: string;
  themes: MemoryReflectionTheme[];
  next_questions: string[];
  markdown: string;
};

type MemoryDecision = {
  candidate: {
    kind: string;
    content: string;
    importance: number;
    confidence: number;
    method: string;
    reason: string;
  };
  accepted: boolean;
  reason: string;
  memory_id?: number;
  audit_id?: number;
};

type MemoryAuditItem = {
  id: number;
  source_message_id: number;
  method: string;
  raw_text: string;
  candidate: MemoryDecision["candidate"] | null;
  accepted: boolean;
  decision?: "accepted" | "pending" | "rejected";
  reason: string;
  memory_id?: number | null;
  created_at: string;
};

type MemoryAuditApprovalResult = {
  approved: boolean;
  memory_id?: number | null;
  reason?: string;
  audit?: MemoryAuditItem;
};

type MemoryAuditCandidatePatch = Pick<
  MemoryDecision["candidate"],
  "kind" | "content" | "importance" | "confidence"
>;

type MemoryAuditRejectionResult = {
  rejected: boolean;
  reason?: string;
  audit?: MemoryAuditItem;
};

type MemoryAuditBatchResult = {
  action: "approve" | "reject";
  requested_count: number;
  ok_count: number;
  items: Array<{
    audit_id: number;
    ok: boolean;
    result?: MemoryAuditApprovalResult | MemoryAuditRejectionResult;
    status_code?: number;
    detail?: unknown;
  }>;
};

type MemoryAuditQuery = {
  limit?: number;
  offset?: number;
  decision?: "accepted" | "pending" | "rejected";
  q?: string;
};

type MemoryAuditListResult = {
  items: MemoryAuditItem[];
  limit: number;
  offset: number;
  decision?: "accepted" | "pending" | "rejected" | null;
  q?: string | null;
};

type MemoryExtraction = {
  method: string;
  error?: string | null;
  decisions: MemoryDecision[];
};

type ChatResult = {
  reply: string;
  memories: MemoryHit[];
  memory_extraction: MemoryExtraction;
  evaluation_event_id?: number;
  first_delta_ms?: number | null;
  latency_ms: number;
};

type StreamMeta = {
  memories: MemoryHit[];
  message_ids?: {
    user?: number;
  };
};

type StreamHandlers = {
  onMeta?: (meta: StreamMeta) => void;
  onDelta: (text: string) => void;
  onDone?: (result: ChatResult) => void;
};

type HeartbeatOptions = {
  enabled?: boolean;
  force?: boolean;
  source?: string;
};

type HeartbeatResult = {
  id?: number;
  evaluation_event_id?: number;
  fired: boolean;
  reason: string;
  message?: string;
  source?: string;
  last_activity_at?: string | null;
};

type ActivityEventRequest = {
  activity_type: string;
  source?: string | null;
  intensity?: number;
  note?: string | null;
};

type ActivePanel = "control" | "memory" | "debug";
type ActiveMemoryView = "card" | "reflection" | "hits" | "audit" | "versions";
type ActiveSpeechMode = "reply" | "stream" | "replay";
type SpeechPlaybackMode = ActiveSpeechMode | "idle";
type AvatarMode = "idle" | "thinking" | "listening" | "speaking" | "interrupted";
type LipSyncSource = "none" | "text" | "audio";
type AvatarTelemetryChannel = "system" | "external" | "external_text_fallback";

type AppConfig = {
  version: string;
  node?: NodeStatus["node"];
  llm: {
    configured: boolean;
    base_url?: string | null;
    model: string;
    chat_completions_url?: string | null;
  };
  memory_extraction_mode: string;
  tts: {
    configured: boolean;
    base_url?: string | null;
    mode: string;
    synthesize_url?: string | null;
    health_url?: string | null;
  };
  stt: {
    configured: boolean;
    base_url?: string | null;
    model: string;
    transcriptions_url?: string | null;
    health_url?: string | null;
  };
  heartbeat: {
    quiet_hours_start: number;
    quiet_hours_end: number;
    cooldown_minutes: number;
    activity_grace_minutes?: number;
  };
  db_path: string;
};

type NodeStatus = {
  node: {
    name: string;
    role: string;
    db_path: string;
    peer_base_url?: string | null;
    peer_timeout_seconds?: number;
    llm_configured: boolean;
    tts_configured: boolean;
    stt_configured: boolean;
  };
  memory_write_policy: {
    primary: string;
    offline_behavior: string;
    local_writes_enabled: boolean;
    peer_writes_configured: boolean;
    peer_base_url?: string | null;
    migration_ready: boolean;
    note: string;
  };
  inference_route_policy: {
    primary: string;
    node_role: string;
    local_llm_configured: boolean;
    peer_base_url?: string | null;
    peer_inference_configured: boolean;
    auto_delegates_chat: boolean;
    note: string;
  };
  peer: {
    configured: boolean;
    available: boolean;
    base_url?: string | null;
    health_url?: string | null;
    status?: string | null;
    version?: string | null;
    error?: string;
  };
};

type PeerScanRole = "mac_home" | "pc_inference";

type PeerScanResult = {
  index: number;
  base_url: string;
  health: boolean;
  status: boolean;
  role: string | null;
  node_name: string | null;
  error: string | null;
};

type PeerScanSummary = {
  preferred_role: PeerScanRole;
  best: PeerScanResult | null;
  results: PeerScanResult[];
  checked_at: string;
};

type PeerConfigApplyResult = {
  applied: boolean;
  key?: string;
  value?: string;
  env_file?: string;
  backup_file?: string;
  reason?: string;
};

type NodeAlert = {
  level: "ok" | "warning" | "muted";
  title: string;
  detail: string;
};

type STTResult = {
  configured: boolean;
  text: string;
  model?: string;
  language?: string | null;
  duration?: number | null;
  latency_ms?: number | null;
  error?: string;
  status_code?: number | null;
};

type STTStatus = {
  configured: boolean;
  available: boolean;
  base_url?: string | null;
  model?: string;
  health_url?: string | null;
  error?: string;
  detail?: {
    status?: string;
    model?: string;
    device?: string;
    compute_type?: string;
    language?: string | null;
    model_loaded?: boolean;
    ffmpeg_path?: string | null;
  };
};

type TTSStatus = {
  configured: boolean;
  available: boolean;
  base_url?: string | null;
  mode: string;
  synthesize_url?: string | null;
  health_url?: string | null;
  health_supported?: boolean;
  error?: string;
  detail?: Record<string, unknown> | null;
};

type TTSResult = {
  configured: boolean;
  status: string;
  text: string;
  audio_url?: string | null;
  audio_base64?: string | null;
  content_type?: string | null;
  latency_ms?: number | null;
  model?: string | null;
  error?: string;
};

type EvaluationEvent = {
  id: number;
  event_type: "chat" | "heartbeat" | string;
  session_id?: string | null;
  source?: string | null;
  latency_ms?: number | null;
  memory_hit_count: number;
  memory_hit_ids: number[];
  created_memory_ids: number[];
  heartbeat_event_id?: number | null;
  fired?: boolean | null;
  reason?: string | null;
  payload: Record<string, unknown>;
  created_at: string;
};

type EvaluationRecordRequest = {
  event_type: string;
  session_id?: string | null;
  source?: string | null;
  latency_ms?: number | null;
  reason?: string | null;
  payload?: Record<string, unknown>;
};

type LipSyncTelemetry = {
  runId: number;
  mode: SpeechPlaybackMode;
  channel: AvatarTelemetryChannel;
  source: Exclude<LipSyncSource, "none">;
  startedAt: number;
  lastSampleAt: number;
  samples: number;
  activeSamples: number;
  maxMouthLevel: number;
};

type EvaluationSummary = {
  chat: {
    count: number;
    avg_latency_ms: number | null;
    p95_latency_ms: number | null;
    memory_hit_rate: number | null;
    avg_memory_hits: number | null;
  };
  heartbeat: {
    count: number;
    fired_count: number;
    blocked_count: number;
    fired_rate: number | null;
    latest_reason: string | null;
  };
  avatar?: {
    count: number;
    voice_start_count: number;
    avg_first_play_ms: number | null;
    lip_sync_count: number;
    avg_mouth_active_ms: number | null;
    avg_mouth_active_ratio: number | null;
    interrupt_count: number;
    avg_interrupt_to_silent_ms: number | null;
  };
  recent_events: EvaluationEvent[];
};

type InferencePrewarmResult = {
  ok: boolean;
  reply: string;
  latency_ms: number;
  llm_model: string;
  llm_configured: boolean;
};

type KanojoApi = {
  chat: (text: string) => Promise<ChatResult>;
  heartbeat: (options?: HeartbeatOptions) => Promise<HeartbeatResult>;
  health: () => Promise<{ status: string; version: string }>;
  config: () => Promise<AppConfig>;
  nodeStatus: () => Promise<NodeStatus>;
  peerScan: (preferredRole: PeerScanRole, candidates?: string[]) => Promise<PeerScanSummary>;
  prewarmInference: () => Promise<InferencePrewarmResult>;
  sttStatus: () => Promise<STTStatus>;
  ttsStatus: () => Promise<TTSStatus>;
  memoryCard: () => Promise<MemoryCard>;
  memoryCardReflection: () => Promise<MemoryReflectionSummary>;
  memoryCardExport: (format: MemoryCardExportFormat) => Promise<MemoryCardExport>;
  updateMemory: (
    memoryId: number,
    patch: Partial<Pick<MemoryCardItem, "content" | "importance" | "confidence">>
  ) => Promise<MemoryUpdateResult>;
  deactivateMemory: (memoryId: number) => Promise<MemoryDeactivationResult>;
  memoryAudits: (query?: MemoryAuditQuery) => Promise<MemoryAuditListResult>;
  approveMemoryAudit: (
    auditId: number,
    candidate?: MemoryAuditCandidatePatch
  ) => Promise<MemoryAuditApprovalResult>;
  rejectMemoryAudit: (auditId: number, reason?: string) => Promise<MemoryAuditRejectionResult>;
  batchMemoryAudits: (
    auditIds: number[],
    action: "approve" | "reject",
    reason?: string
  ) => Promise<MemoryAuditBatchResult>;
  memoryCardSnapshots: () => Promise<{ items: MemoryCardSnapshotSummary[] }>;
  createMemoryCardSnapshot: (label?: string) => Promise<MemoryCardSnapshot>;
  memoryCardSnapshotCompare: (snapshotId: number) => Promise<MemoryCardComparison>;
  evaluationSummary: () => Promise<EvaluationSummary>;
  evaluationEvents: (limit?: number) => Promise<{ items: EvaluationEvent[] }>;
  recordEvaluation: (event: EvaluationRecordRequest) => Promise<{ id: number }>;
  recordActivity: (event: ActivityEventRequest) => Promise<{ id: number }>;
  notify?: (title: string, body: string) => Promise<{ delivered: boolean; reason?: string }>;
  applyPeerConfig: (peerBaseUrl: string) => Promise<PeerConfigApplyResult>;
};

declare global {
  interface Window {
    kanojoApi?: KanojoApi;
  }
}

const backendBaseUrl = "http://127.0.0.1:8787";
const peerScanTimeoutMs = 3000;
const defaultPeerScanCandidates = [
  "http://kanojo-mac.local:8787",
  "http://kanojo-mac-alt.local:8787",
  "http://kanojo-mac.local:8787",
  "http://kanojo-pc.local:8787",
  "http://kanojo-pc-alt.local:8787"
];

const browserBackendApi: KanojoApi = {
  chat: async (text: string) => {
    const response = await fetch(`${backendBaseUrl}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, session_id: "default", speak: false })
    });
    if (!response.ok) {
      throw new Error(`Chat request failed: ${response.status}`);
    }
    return response.json();
  },
  heartbeat: async (options?: HeartbeatOptions) => {
    const response = await fetch(`${backendBaseUrl}/heartbeat/tick`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        enabled: options?.enabled ?? true,
        force: options?.force ?? false,
        source: options?.source ?? "manual"
      })
    });
    if (!response.ok) {
      throw new Error(`Heartbeat request failed: ${response.status}`);
    }
    return response.json();
  },
  health: async () => {
    const response = await fetch(`${backendBaseUrl}/health`);
    if (!response.ok) {
      throw new Error(`Health request failed: ${response.status}`);
    }
    return response.json();
  },
  config: async () => {
    const response = await fetch(`${backendBaseUrl}/config`);
    if (!response.ok) {
      throw new Error(`Config request failed: ${response.status}`);
    }
    return response.json();
  },
  nodeStatus: async () => {
    const response = await fetch(`${backendBaseUrl}/node/status`);
    if (!response.ok) {
      throw new Error(`Node status request failed: ${response.status}`);
    }
    return response.json();
  },
  peerScan: async (preferredRole, candidates = defaultPeerScanCandidates) =>
    scanPeerCandidates(preferredRole, candidates, peerScanTimeoutMs),
  prewarmInference: async () => {
    const response = await fetch(`${backendBaseUrl}/node/inference/prewarm`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: "预热 PC 推理节点" })
    });
    if (!response.ok) {
      throw new Error(`Inference prewarm request failed: ${response.status}`);
    }
    return response.json();
  },
  sttStatus: async () => {
    const response = await fetch(`${backendBaseUrl}/stt/status`);
    if (!response.ok) {
      throw new Error(`STT status request failed: ${response.status}`);
    }
    return response.json();
  },
  ttsStatus: async () => {
    const response = await fetch(`${backendBaseUrl}/tts/status`);
    if (!response.ok) {
      throw new Error(`TTS status request failed: ${response.status}`);
    }
    return response.json();
  },
  memoryCard: async () => {
    const response = await fetch(`${backendBaseUrl}/memory-card?session_id=default`);
    if (!response.ok) {
      throw new Error(`Memory card request failed: ${response.status}`);
    }
    return response.json();
  },
  memoryCardReflection: async () => {
    const response = await fetch(`${backendBaseUrl}/memory-card/reflection?session_id=default`);
    if (!response.ok) {
      throw new Error(`Memory card reflection request failed: ${response.status}`);
    }
    return response.json();
  },
  memoryCardExport: async (format: MemoryCardExportFormat) => fetchMemoryCardExport(format),
  updateMemory: async (memoryId, patch) => {
    const response = await fetch(`${backendBaseUrl}/memories/${memoryId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(patch)
    });
    if (!response.ok) {
      throw new Error(`Memory update request failed: ${response.status}`);
    }
    return response.json();
  },
  deactivateMemory: async (memoryId: number) => {
    const response = await fetch(`${backendBaseUrl}/memories/${memoryId}`, {
      method: "DELETE"
    });
    if (!response.ok) {
      throw new Error(`Memory deactivate request failed: ${response.status}`);
    }
    return response.json();
  },
  memoryAudits: async (query = {}) => {
    const params = new URLSearchParams();
    params.set("limit", String(query.limit ?? 20));
    params.set("offset", String(query.offset ?? 0));
    if (query.decision) {
      params.set("decision", query.decision);
    }
    if (query.q?.trim()) {
      params.set("q", query.q.trim());
    }
    const response = await fetch(`${backendBaseUrl}/memory-audits?${params.toString()}`);
    if (!response.ok) {
      throw new Error(`Memory audits request failed: ${response.status}`);
    }
    return response.json();
  },
  approveMemoryAudit: async (auditId: number, candidate?: MemoryAuditCandidatePatch) => {
    const response = await fetch(`${backendBaseUrl}/memory-audits/${auditId}/approve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(candidate ? { candidate } : {})
    });
    if (!response.ok) {
      throw new Error(`Memory audit approval failed: ${response.status}`);
    }
    return response.json();
  },
  rejectMemoryAudit: async (auditId: number, reason = "rejected manually") => {
    const response = await fetch(`${backendBaseUrl}/memory-audits/${auditId}/reject`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reason })
    });
    if (!response.ok) {
      throw new Error(`Memory audit rejection failed: ${response.status}`);
    }
    return response.json();
  },
  batchMemoryAudits: async (auditIds, action, reason) => {
    const response = await fetch(`${backendBaseUrl}/memory-audits/batch`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ audit_ids: auditIds, action, reason })
    });
    if (!response.ok) {
      throw new Error(`Memory audit batch request failed: ${response.status}`);
    }
    return response.json();
  },
  memoryCardSnapshots: async () => {
    const response = await fetch(`${backendBaseUrl}/memory-card/snapshots?session_id=default`);
    if (!response.ok) {
      throw new Error(`Memory card snapshots request failed: ${response.status}`);
    }
    return response.json();
  },
  createMemoryCardSnapshot: async (label?: string) => {
    const response = await fetch(`${backendBaseUrl}/memory-card/snapshots`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: "default", label: label || null })
    });
    if (!response.ok) {
      throw new Error(`Memory card snapshot request failed: ${response.status}`);
    }
    return response.json();
  },
  memoryCardSnapshotCompare: async (snapshotId: number) => {
    const response = await fetch(`${backendBaseUrl}/memory-card/snapshots/${snapshotId}/compare`);
    if (!response.ok) {
      throw new Error(`Memory card snapshot compare failed: ${response.status}`);
    }
    return response.json();
  },
  evaluationSummary: async () => {
    const response = await fetch(`${backendBaseUrl}/evaluation/summary`);
    if (!response.ok) {
      throw new Error(`Evaluation summary request failed: ${response.status}`);
    }
    return response.json();
  },
  evaluationEvents: async (limit = 20) => {
    const response = await fetch(`${backendBaseUrl}/evaluation/events?limit=${limit}`);
    if (!response.ok) {
      throw new Error(`Evaluation events request failed: ${response.status}`);
    }
    return response.json();
  },
  recordEvaluation: async (event: EvaluationRecordRequest) => {
    const response = await fetch(`${backendBaseUrl}/evaluation/events`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(event)
    });
    if (!response.ok) {
      throw new Error(`Evaluation event request failed: ${response.status}`);
    }
    return response.json();
  },
  recordActivity: async (event: ActivityEventRequest) => {
    const response = await fetch(`${backendBaseUrl}/activity/events`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(event)
    });
    if (!response.ok) {
      throw new Error(`Activity event request failed: ${response.status}`);
    }
    return response.json();
  },
  notify: async (title: string, body: string) => notifyViaBrowser(title, body),
  applyPeerConfig: async (peerBaseUrl: string) => ({
    applied: false,
    reason: "desktop bridge unavailable",
    value: peerBaseUrl
  })
};

export default function App() {
  const api = window.kanojoApi ?? browserBackendApi;
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Message[]>([
    { role: "system", content: "P5.5 活动感知已接入。桌面活动只进入主动心跳判断,不会直接触发通知。" }
  ]);
  const [memories, setMemories] = useState<MemoryHit[]>([]);
  const [extraction, setExtraction] = useState<MemoryExtraction | null>(null);
  const [latency, setLatency] = useState<number | null>(null);
  const [status, setStatus] = useState("checking");
  const [busy, setBusy] = useState(false);
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [notificationState, setNotificationState] = useState("checking");
  const [speechEnabled, setSpeechEnabled] = useState(false);
  const [speechSupported, setSpeechSupported] = useState(false);
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([]);
  const [selectedVoiceName, setSelectedVoiceName] = useState("");
  const [speechRate, setSpeechRate] = useState(1);
  const [speaking, setSpeaking] = useState(false);
  const [voiceActive, setVoiceActive] = useState(false);
  const [ttsLatency, setTtsLatency] = useState<number | null>(null);
  const [ttsStatus, setTtsStatus] = useState("语音待机");
  const [ttsServiceStatus, setTtsServiceStatus] = useState<TTSStatus | null>(null);
  const [speechQueueSize, setSpeechQueueSize] = useState(0);
  const [speechSegmentCount, setSpeechSegmentCount] = useState(0);
  const [speechPlaybackMode, setSpeechPlaybackMode] = useState<SpeechPlaybackMode>("idle");
  const [speechInterruptCount, setSpeechInterruptCount] = useState(0);
  const [lastAssistantText, setLastAssistantText] = useState("");
  const [sttSupported, setSttSupported] = useState(false);
  const [recording, setRecording] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const [sttStatus, setSttStatus] = useState("语音输入待机");
  const [sttServiceStatus, setSttServiceStatus] = useState<STTStatus | null>(null);
  const [heartbeatEnabled, setHeartbeatEnabled] = useState(true);
  const [heartbeatIntervalSeconds, setHeartbeatIntervalSeconds] = useState(60);
  const [lastHeartbeat, setLastHeartbeat] = useState<HeartbeatResult | null>(null);
  const [lastHeartbeatAt, setLastHeartbeatAt] = useState<string | null>(null);
  const [lastActivitySignal, setLastActivitySignal] = useState("未上报");
  const [showDebugLogs, setShowDebugLogs] = useState(false);
  const [activePanel, setActivePanel] = useState<ActivePanel>("control");
  const [activeMemoryView, setActiveMemoryView] = useState<ActiveMemoryView>("card");
  const [memoryCard, setMemoryCard] = useState<MemoryCard | null>(null);
  const [memoryCardStatus, setMemoryCardStatus] = useState("未刷新");
  const [memoryCardExportStatus, setMemoryCardExportStatus] = useState("未导出");
  const [memoryEditStatus, setMemoryEditStatus] = useState("未编辑");
  const [deletingMemoryId, setDeletingMemoryId] = useState<number | null>(null);
  const [memoryReflection, setMemoryReflection] = useState<MemoryReflectionSummary | null>(null);
  const [memoryReflectionStatus, setMemoryReflectionStatus] = useState("未刷新");
  const [memoryAudits, setMemoryAudits] = useState<MemoryAuditItem[]>([]);
  const [memoryAuditStatus, setMemoryAuditStatus] = useState("未刷新");
  const [memoryAuditFilter, setMemoryAuditFilter] = useState<"all" | "pending" | "accepted" | "rejected">(
    "all"
  );
  const [memoryAuditSearch, setMemoryAuditSearch] = useState("");
  const [memoryAuditHasMore, setMemoryAuditHasMore] = useState(false);
  const [approvingAuditId, setApprovingAuditId] = useState<number | null>(null);
  const [rejectingAuditId, setRejectingAuditId] = useState<number | null>(null);
  const [selectedAuditIds, setSelectedAuditIds] = useState<number[]>([]);
  const [auditDrafts, setAuditDrafts] = useState<Record<number, string>>({});
  const [batchAuditBusy, setBatchAuditBusy] = useState(false);
  const [memoryCardSnapshots, setMemoryCardSnapshots] = useState<MemoryCardSnapshotSummary[]>([]);
  const [memoryCardComparison, setMemoryCardComparison] = useState<MemoryCardComparison | null>(
    null
  );
  const [memoryCardVersionStatus, setMemoryCardVersionStatus] = useState("未刷新");
  const [evaluationSummary, setEvaluationSummary] = useState<EvaluationSummary | null>(null);
  const [evaluationEvents, setEvaluationEvents] = useState<EvaluationEvent[]>([]);
  const [evaluationStatus, setEvaluationStatus] = useState("未刷新");
  const [nodeStatus, setNodeStatus] = useState<NodeStatus | null>(null);
  const [nodeStatusText, setNodeStatusText] = useState("未刷新");
  const [peerScan, setPeerScan] = useState<PeerScanSummary | null>(null);
  const [peerScanStatus, setPeerScanStatus] = useState("未诊断");
  const [peerScanBusy, setPeerScanBusy] = useState(false);
  const [peerConfigStatus, setPeerConfigStatus] = useState("未写入");
  const [peerConfigBusy, setPeerConfigBusy] = useState(false);
  const [prewarmStatus, setPrewarmStatus] = useState("未预热");
  const [prewarmBusy, setPrewarmBusy] = useState(false);
  const [avatarMouthLevel, setAvatarMouthLevel] = useState(0);
  const [avatarBlinking, setAvatarBlinking] = useState(false);
  const [lipSyncSource, setLipSyncSource] = useState<LipSyncSource>("none");
  const [live2dStatus, setLive2dStatus] = useState<Live2DStatus>("loading");
  const heartbeatBusyRef = useRef(false);
  const messageListRef = useRef<HTMLDivElement | null>(null);
  const speechRunIdRef = useRef(0);
  const currentUtteranceRef = useRef<SpeechSynthesisUtterance | null>(null);
  const currentAudioRef = useRef<HTMLAudioElement | null>(null);
  const currentAudioUrlRef = useRef<string | null>(null);
  const lipSyncAnimationRef = useRef<number | null>(null);
  const lipSyncIntervalRef = useRef<number | null>(null);
  const lipSyncSourceRef = useRef<LipSyncSource>("none");
  const avatarMouthLevelRef = useRef(0);
  const lipSyncTelemetryRef = useRef<LipSyncTelemetry | null>(null);
  const lipSyncAudioContextRef = useRef<AudioContext | null>(null);
  const lipSyncAudioSourceRef = useRef<MediaElementAudioSourceNode | null>(null);
  const lipSyncAnalyserRef = useRef<AnalyserNode | null>(null);
  const ttsAbortControllerRef = useRef<AbortController | null>(null);
  const speechSegmentBusyRef = useRef(false);
  const speechQueueRef = useRef<string[]>([]);
  const streamSpeechBufferRef = useRef("");
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const lastActivitySentAtRef = useRef(0);
  const avatarMode: AvatarMode = voiceActive
    ? "speaking"
    : recording
      ? "listening"
      : busy || transcribing || speechQueueSize > 0 || speaking
        ? "thinking"
        : /打断|停止|中断/.test(ttsStatus)
          ? "interrupted"
          : "idle";
  const lipSyncLive2DValue = avatarMouthLevel / 3;
  const nodeAlert = summarizeNodeAlert(nodeStatus);
  const nodeActionHint = summarizeNodeActionHint(nodeStatus);

  const refreshSttStatus = async (fallbackConfigured = config?.stt.configured ?? false) => {
    try {
      const result = await api.sttStatus();
      setSttServiceStatus(result);
      setSttStatus(formatSttServiceStatus(result));
      return result;
    } catch (error) {
      const message = error instanceof Error ? error.message : "STT status failed";
      const result: STTStatus = {
        configured: fallbackConfigured,
        available: false,
        error: message
      };
      setSttServiceStatus(result);
      setSttStatus(`STT 状态检查失败: ${message}`);
      return result;
    }
  };

  const refreshTtsStatus = async (fallbackConfigured = config?.tts.configured ?? false) => {
    try {
      const result = await api.ttsStatus();
      setTtsServiceStatus(result);
      if (!speechIsActive()) {
        setTtsStatus(formatTtsServiceStatus(result, speechSupported));
      }
      return result;
    } catch (error) {
      const message = error instanceof Error ? error.message : "TTS status failed";
      const result: TTSStatus = {
        configured: fallbackConfigured,
        available: false,
        mode: fallbackConfigured ? "external" : "desktop_speech_fallback",
        error: message
      };
      setTtsServiceStatus(result);
      if (!speechIsActive()) {
        setTtsStatus(`TTS 状态检查失败: ${message}`);
      }
      return result;
    }
  };

  const refreshMemoryCard = async () => {
    try {
      const card = await api.memoryCard();
      setMemoryCard(card);
      setMemoryCardStatus(`已刷新 ${new Date().toLocaleTimeString()}`);
    } catch (error) {
      const message = error instanceof Error ? error.message : "memory card failed";
      setMemoryCardStatus(message);
    }
  };

  const refreshMemoryReflection = async () => {
    try {
      const result = await api.memoryCardReflection();
      setMemoryReflection(result);
      setMemoryReflectionStatus(`已刷新 ${new Date().toLocaleTimeString()}`);
    } catch (error) {
      const message = error instanceof Error ? error.message : "memory reflection failed";
      setMemoryReflectionStatus(message);
    }
  };

  const copyMemoryCardMarkdown = async () => {
    try {
      const result = await api.memoryCardExport("markdown");
      await copyTextToClipboard(result.content);
      setMemoryCardExportStatus(`已复制 Markdown ${new Date().toLocaleTimeString()}`);
    } catch (error) {
      const message = error instanceof Error ? error.message : "copy memory card failed";
      setMemoryCardExportStatus(message);
    }
  };

  const downloadMemoryCard = async (format: MemoryCardExportFormat) => {
    try {
      const result = await api.memoryCardExport(format);
      downloadTextFile(result);
      setMemoryCardExportStatus(`已导出 ${format.toUpperCase()} ${new Date().toLocaleTimeString()}`);
    } catch (error) {
      const message = error instanceof Error ? error.message : "export memory card failed";
      setMemoryCardExportStatus(message);
    }
  };

  const deactivateMemory = async (item: MemoryCardItem) => {
    const confirmed = window.confirm(`停用这条长期记忆?\n\n${item.content}`);
    if (!confirmed) {
      return;
    }
    setDeletingMemoryId(item.id);
    setMemoryEditStatus(`正在停用 #${item.id}`);
    try {
      const result = await api.deactivateMemory(item.id);
      setMemoryEditStatus(
        result.deactivated ? `已停用 #${item.id}` : `未停用 #${item.id}: ${result.reason}`
      );
      await Promise.all([refreshMemoryCard(), refreshMemoryReflection()]);
    } catch (error) {
      const message = error instanceof Error ? error.message : "deactivate memory failed";
      setMemoryEditStatus(message);
    } finally {
      setDeletingMemoryId(null);
    }
  };

  const editMemoryContent = async (item: MemoryCardItem) => {
    const content = window.prompt("编辑长期记忆", item.content)?.trim();
    if (!content || content === item.content) {
      return;
    }
    setMemoryEditStatus(`正在编辑 #${item.id}`);
    try {
      const result = await api.updateMemory(item.id, { content });
      setMemoryEditStatus(result.updated ? `已编辑 #${item.id}` : `未编辑 #${item.id}: ${result.reason}`);
      await Promise.all([refreshMemoryCard(), refreshMemoryReflection()]);
    } catch (error) {
      const message = error instanceof Error ? error.message : "update memory failed";
      setMemoryEditStatus(message);
    }
  };

  const reduceMemoryWeight = async (item: MemoryCardItem) => {
    setMemoryEditStatus(`正在降权 #${item.id}`);
    try {
      const result = await api.updateMemory(item.id, {
        importance: Math.max(0.1, Math.round(item.importance * 50) / 100),
        confidence: Math.min(item.confidence, 0.6)
      });
      setMemoryEditStatus(result.updated ? `已降权 #${item.id}` : `未降权 #${item.id}: ${result.reason}`);
      await Promise.all([refreshMemoryCard(), refreshMemoryReflection()]);
    } catch (error) {
      const message = error instanceof Error ? error.message : "reduce memory weight failed";
      setMemoryEditStatus(message);
    }
  };

  const refreshMemoryCardSnapshots = async () => {
    try {
      const result = await api.memoryCardSnapshots();
      setMemoryCardSnapshots(result.items);
      setMemoryCardVersionStatus(`已刷新 ${new Date().toLocaleTimeString()}`);
    } catch (error) {
      const message = error instanceof Error ? error.message : "memory card snapshots failed";
      setMemoryCardVersionStatus(message);
    }
  };

  const compareMemoryCardSnapshot = async (snapshotId: number) => {
    try {
      const comparison = await api.memoryCardSnapshotCompare(snapshotId);
      setMemoryCardComparison(comparison);
      setMemoryCardVersionStatus(`已对比 #${snapshotId} ${new Date().toLocaleTimeString()}`);
    } catch (error) {
      const message = error instanceof Error ? error.message : "memory card compare failed";
      setMemoryCardVersionStatus(message);
    }
  };

  const createMemoryCardSnapshot = async () => {
    try {
      const label = `节点 ${new Date().toLocaleString()}`;
      const snapshot = await api.createMemoryCardSnapshot(label);
      await refreshMemoryCardSnapshots();
      await compareMemoryCardSnapshot(snapshot.id);
      setActiveMemoryView("versions");
      setMemoryCardVersionStatus(`已保存 #${snapshot.id} ${new Date().toLocaleTimeString()}`);
    } catch (error) {
      const message = error instanceof Error ? error.message : "create snapshot failed";
      setMemoryCardVersionStatus(message);
    }
  };

  const refreshMemoryAudits = async (append = false) => {
    try {
      const result = await api.memoryAudits({
        limit: 20,
        offset: append ? memoryAudits.length : 0,
        decision: memoryAuditFilter === "all" ? undefined : memoryAuditFilter,
        q: memoryAuditSearch.trim() || undefined
      });
      const nextItems = append ? [...memoryAudits, ...result.items] : result.items;
      setMemoryAudits(nextItems);
      setMemoryAuditHasMore(result.items.length >= result.limit);
      setSelectedAuditIds((ids) =>
        ids.filter((id) =>
          nextItems.some((audit) => audit.id === id && audit.decision === "pending")
        )
      );
      setAuditDrafts((drafts) => {
        const next = { ...drafts };
        const itemIds = new Set(nextItems.map((audit) => audit.id));
        for (const audit of nextItems) {
          if (audit.candidate && next[audit.id] === undefined) {
            next[audit.id] = audit.candidate.content;
          }
        }
        for (const id of Object.keys(next)) {
          if (!itemIds.has(Number(id))) {
            delete next[Number(id)];
          }
        }
        return next;
      });
      setMemoryAuditStatus(`${append ? "已加载" : "已刷新"} ${new Date().toLocaleTimeString()}`);
    } catch (error) {
      const message = error instanceof Error ? error.message : "memory audits failed";
      setMemoryAuditStatus(message);
    }
  };

  const updateAuditDraft = (auditId: number, content: string) => {
    setAuditDrafts((drafts) => ({ ...drafts, [auditId]: content }));
  };

  const toggleAuditSelection = (auditId: number, selected: boolean) => {
    setSelectedAuditIds((ids) =>
      selected ? Array.from(new Set([...ids, auditId])) : ids.filter((id) => id !== auditId)
    );
  };

  const editedAuditCandidate = (audit: MemoryAuditItem): MemoryAuditCandidatePatch | undefined => {
    const draftContent = auditDrafts[audit.id]?.trim();
    if (!audit.candidate || !draftContent || draftContent === audit.candidate.content) {
      return undefined;
    }
    return {
      kind: audit.candidate.kind,
      content: draftContent,
      importance: audit.candidate.importance,
      confidence: audit.candidate.confidence
    };
  };

  const approveMemoryAudit = async (audit: MemoryAuditItem) => {
    setApprovingAuditId(audit.id);
    setMemoryAuditStatus(`正在批准 #${audit.id}`);
    try {
      const result = await api.approveMemoryAudit(audit.id, editedAuditCandidate(audit));
      setMemoryAuditStatus(
        result.approved ? `已批准 #${audit.id} -> 记忆 #${result.memory_id}` : `未批准 #${audit.id}`
      );
      await Promise.all([refreshMemoryAudits(), refreshMemoryCard(), refreshMemoryReflection()]);
    } catch (error) {
      const message = error instanceof Error ? error.message : "approve memory audit failed";
      setMemoryAuditStatus(message);
    } finally {
      setApprovingAuditId(null);
    }
  };

  const rejectMemoryAudit = async (audit: MemoryAuditItem) => {
    setRejectingAuditId(audit.id);
    setMemoryAuditStatus(`正在拒绝 #${audit.id}`);
    try {
      const result = await api.rejectMemoryAudit(audit.id, "rejected manually");
      setMemoryAuditStatus(result.rejected ? `已拒绝 #${audit.id}` : `未拒绝 #${audit.id}`);
      await refreshMemoryAudits();
    } catch (error) {
      const message = error instanceof Error ? error.message : "reject memory audit failed";
      setMemoryAuditStatus(message);
    } finally {
      setRejectingAuditId(null);
    }
  };

  const batchMemoryAudits = async (action: "approve" | "reject") => {
    if (selectedAuditIds.length === 0) {
      setMemoryAuditStatus("未选择审计项");
      return;
    }
    setBatchAuditBusy(true);
    setMemoryAuditStatus(action === "approve" ? "批量批准中" : "批量拒绝中");
    try {
      let okCount = 0;
      if (action === "approve") {
        const selectedAudits = memoryAudits.filter((audit) => selectedAuditIds.includes(audit.id));
        for (const audit of selectedAudits) {
          const result = await api.approveMemoryAudit(audit.id, editedAuditCandidate(audit));
          if (result.approved) {
            okCount += 1;
          }
        }
      } else {
        const result = await api.batchMemoryAudits(
          selectedAuditIds,
          "reject",
          "batch rejected manually"
        );
        okCount = result.ok_count;
      }
      setMemoryAuditStatus(
        `${action === "approve" ? "批量批准" : "批量拒绝"} ${okCount}/${selectedAuditIds.length}`
      );
      setSelectedAuditIds([]);
      await Promise.all([refreshMemoryAudits(), refreshMemoryCard(), refreshMemoryReflection()]);
    } catch (error) {
      const message = error instanceof Error ? error.message : "batch memory audit failed";
      setMemoryAuditStatus(message);
    } finally {
      setBatchAuditBusy(false);
    }
  };

  const refreshEvaluation = async () => {
    try {
      const [summary, events] = await Promise.all([
        api.evaluationSummary(),
        api.evaluationEvents(8)
      ]);
      setEvaluationSummary(summary);
      setEvaluationEvents(events.items);
      setEvaluationStatus(`已刷新 ${new Date().toLocaleTimeString()}`);
    } catch (error) {
      const message = error instanceof Error ? error.message : "evaluation failed";
      setEvaluationStatus(message);
    }
  };

  const refreshNodeStatus = async () => {
    try {
      const result = await api.nodeStatus();
      setNodeStatus(result);
      setNodeStatusText(`已刷新 ${new Date().toLocaleTimeString()}`);
    } catch (error) {
      const message = error instanceof Error ? error.message : "node status failed";
      setNodeStatusText(message);
    }
  };

  const diagnosePeerCandidates = async () => {
    const role = preferredPeerRole(nodeStatus);
    setPeerScanBusy(true);
    setPeerScanStatus("诊断中");
    try {
      const result = await api.peerScan(role, buildPeerScanCandidates(nodeStatus));
      setPeerScan(result);
      setPeerScanStatus(formatPeerScanStatus(result));
    } catch (error) {
      const message = error instanceof Error ? error.message : "peer scan failed";
      setPeerScanStatus(message);
    } finally {
      setPeerScanBusy(false);
    }
  };

  const applyRecommendedPeerConfig = async () => {
    const peerBaseUrl = peerScan?.best?.base_url;
    if (!peerBaseUrl) {
      setPeerConfigStatus("没有可写入的推荐地址");
      return;
    }
    const confirmed = window.confirm(
      `将 KANOJO_PEER_BASE_URL 写入本机 backend/.env:\n${peerBaseUrl}\n\n写入后需要重启后端。`
    );
    if (!confirmed) {
      return;
    }
    setPeerConfigBusy(true);
    setPeerConfigStatus("写入中");
    try {
      const result = await api.applyPeerConfig(peerBaseUrl);
      setPeerConfigStatus(
        result.applied
          ? `已写入 ${result.env_file ?? "backend/.env"}`
          : `未写入: ${result.reason ?? "unknown"}`
      );
    } catch (error) {
      const message = error instanceof Error ? error.message : "apply peer config failed";
      setPeerConfigStatus(message);
    } finally {
      setPeerConfigBusy(false);
    }
  };

  const prewarmInference = async () => {
    setPrewarmBusy(true);
    setPrewarmStatus("预热中");
    try {
      const result = await api.prewarmInference();
      setPrewarmStatus(`${result.llm_model} · ${formatMs(result.latency_ms)}`);
      await refreshNodeStatus();
    } catch (error) {
      const message = error instanceof Error ? error.message : "prewarm failed";
      setPrewarmStatus(message);
    } finally {
      setPrewarmBusy(false);
    }
  };

  useEffect(() => {
    api.health()
      .then((result) => {
        const bridge = window.kanojoApi ? "preload" : "direct";
        setStatus(`${result.status} · ${result.version} · ${bridge}`);
      })
      .catch((error) => {
        const message = error instanceof Error ? error.message : "offline";
        setStatus(`offline · ${message}`);
      });
    api.config()
      .then((result) => {
        setConfig(result);
        if (result.tts.configured) {
          setTtsStatus("正在检查 TTS 服务");
          void refreshTtsStatus(result.tts.configured);
        } else {
          setTtsServiceStatus({
            configured: false,
            available: speechSupported,
            mode: "desktop_speech_fallback"
          });
        }
        if (!result.stt.configured) {
          setSttStatus("STT 未配置");
          setSttServiceStatus({ configured: false, available: false });
        } else {
          setSttStatus("正在检查 STT 服务");
          void refreshSttStatus(result.stt.configured);
        }
      })
      .catch(() => {
        setConfig(null);
        setTtsStatus("后端配置不可用");
        setSttStatus("后端配置不可用");
      });
    void refreshEvaluation();
    void refreshNodeStatus();
    void refreshMemoryCard();
    void refreshMemoryReflection();
    void refreshMemoryCardSnapshots();
    setNotificationState(readNotificationState());
    setSttSupported(
      typeof navigator.mediaDevices?.getUserMedia === "function" && "MediaRecorder" in window
    );
  }, []);

  useEffect(() => {
    if (activePanel === "memory") {
      void refreshMemoryCard();
      void refreshMemoryReflection();
      void refreshMemoryCardSnapshots();
      void refreshMemoryAudits();
    } else if (activePanel === "debug") {
      void refreshEvaluation();
      void refreshNodeStatus();
    }
  }, [activePanel]);

  useEffect(() => {
    const intervalId = window.setInterval(() => {
      void refreshNodeStatus();
    }, 30_000);
    return () => window.clearInterval(intervalId);
  }, []);

  useEffect(() => {
    if (!("speechSynthesis" in window)) {
      setSpeechSupported(false);
      return;
    }
    setSpeechSupported(true);
    const loadVoices = () => {
      const available = window.speechSynthesis.getVoices();
      setVoices(available);
      if (!selectedVoiceName && available.length > 0) {
        const preferred =
          available.find((voice) => voice.lang.toLowerCase().startsWith("zh")) ??
          available.find((voice) => /chinese|huihui|xiaoxiao|yaoyao/i.test(voice.name)) ??
          available[0];
        setSelectedVoiceName(preferred.name);
      }
    };
    loadVoices();
    window.speechSynthesis.onvoiceschanged = loadVoices;
    return () => {
      window.speechSynthesis.onvoiceschanged = null;
      interruptSpeech("语音已关闭", false);
    };
  }, [selectedVoiceName]);

  useEffect(() => {
    return () => {
      mediaRecorderRef.current?.stop();
      mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
    };
  }, []);

  useEffect(() => {
    messageListRef.current?.scrollTo({
      top: messageListRef.current.scrollHeight,
      behavior: "smooth"
    });
  }, [messages]);

  useEffect(() => {
    const intervalId = window.setInterval(() => {
      setAvatarBlinking(true);
      window.setTimeout(() => setAvatarBlinking(false), 130);
    }, 4200);
    return () => window.clearInterval(intervalId);
  }, []);

  useEffect(() => () => stopLipSync(false, "component_unmount"), []);

  useEffect(() => {
    recordDesktopActivity(
      document.visibilityState === "visible" ? "app_visible" : "app_hidden",
      0.7,
      0
    );
    const handleInputActivity = () => recordDesktopActivity("user_input", 0.9, 60_000);
    const handleVisibility = () =>
      recordDesktopActivity(
        document.visibilityState === "visible" ? "app_visible" : "app_hidden",
        0.7,
        0
      );
    const handleFocus = () => recordDesktopActivity("active", 0.8, 0);
    const handleBlur = () => recordDesktopActivity("idle", 0.2, 0);
    window.addEventListener("pointerdown", handleInputActivity);
    window.addEventListener("keydown", handleInputActivity);
    document.addEventListener("visibilitychange", handleVisibility);
    window.addEventListener("focus", handleFocus);
    window.addEventListener("blur", handleBlur);
    return () => {
      window.removeEventListener("pointerdown", handleInputActivity);
      window.removeEventListener("keydown", handleInputActivity);
      document.removeEventListener("visibilitychange", handleVisibility);
      window.removeEventListener("focus", handleFocus);
      window.removeEventListener("blur", handleBlur);
    };
  }, []);

  useEffect(() => {
    if (!heartbeatEnabled) {
      return;
    }
    const intervalId = window.setInterval(() => {
      void runHeartbeat("scheduler");
    }, heartbeatIntervalSeconds * 1000);
    return () => window.clearInterval(intervalId);
  }, [heartbeatEnabled, heartbeatIntervalSeconds]);

  const ttsPlaybackSupported = () => speechSupported || config?.tts.configured === true;

  const externalTtsPreferred = () => config?.tts.configured === true;

  const recordAvatarEvaluation = (event: EvaluationRecordRequest) => {
    void api
      .recordEvaluation({
        source: "desktop_live2d",
        session_id: "default",
        ...event
      })
      .then(() => {
        if (activePanel === "debug") {
          void refreshEvaluation();
        }
      })
      .catch((error) => {
        const message = error instanceof Error ? error.message : "avatar evaluation failed";
        setEvaluationStatus(message);
      });
  };

  const finishLipSyncTelemetry = (reason: string) => {
    const telemetry = lipSyncTelemetryRef.current;
    if (!telemetry) return;
    lipSyncTelemetryRef.current = null;
    const endedAt = performance.now();
    const durationMs = Math.max(0, Math.round(endedAt - telemetry.startedAt));
    const sampleIntervalMs =
      telemetry.samples > 1 ? durationMs / Math.max(telemetry.samples - 1, 1) : 0;
    const activeMs = Math.round(telemetry.activeSamples * sampleIntervalMs);
    const activeRatio =
      telemetry.samples > 0 ? Math.round((telemetry.activeSamples / telemetry.samples) * 1000) / 1000 : 0;

    recordAvatarEvaluation({
      event_type: "avatar_lip_sync",
      latency_ms: durationMs,
      reason,
      payload: {
        run_id: telemetry.runId,
        mode: telemetry.mode,
        channel: telemetry.channel,
        source: telemetry.source,
        duration_ms: durationMs,
        active_ms: activeMs,
        active_ratio: activeRatio,
        sample_count: telemetry.samples,
        active_sample_count: telemetry.activeSamples,
        max_mouth_level: telemetry.maxMouthLevel,
        avatar_mode: avatarMode,
        live2d_status: live2dStatus
      }
    });
  };

  const beginLipSyncTelemetry = (
    source: Exclude<LipSyncSource, "none">,
    runId: number,
    channel: AvatarTelemetryChannel,
    mode: SpeechPlaybackMode
  ) => {
    finishLipSyncTelemetry("replaced");
    const now = performance.now();
    lipSyncTelemetryRef.current = {
      runId,
      mode,
      channel,
      source,
      startedAt: now,
      lastSampleAt: now,
      samples: 0,
      activeSamples: 0,
      maxMouthLevel: 0
    };
  };

  const sampleLipSyncLevel = (level: number) => {
    const telemetry = lipSyncTelemetryRef.current;
    if (!telemetry) return;
    telemetry.lastSampleAt = performance.now();
    telemetry.samples += 1;
    if (level > 0) {
      telemetry.activeSamples += 1;
    }
    telemetry.maxMouthLevel = Math.max(telemetry.maxMouthLevel, level);
  };

  const setTrackedLipSyncSource = (source: LipSyncSource) => {
    lipSyncSourceRef.current = source;
    setLipSyncSource(source);
  };

  const setTrackedAvatarMouthLevel = (level: number) => {
    avatarMouthLevelRef.current = level;
    sampleLipSyncLevel(level);
    setAvatarMouthLevel(level);
  };

  const recordAvatarVoiceStart = (
    latencyMs: number,
    channel: AvatarTelemetryChannel,
    mode: ActiveSpeechMode,
    textLength: number,
    runId: number
  ) => {
    recordAvatarEvaluation({
      event_type: "avatar_voice_start",
      latency_ms: latencyMs,
      payload: {
        run_id: runId,
        mode,
        channel,
        text_length: textLength,
        speech_rate: speechRate,
        avatar_mode: avatarMode,
        live2d_status: live2dStatus
      }
    });
  };

  const stopLipSync = (resetState = true, reason = "stopped") => {
    finishLipSyncTelemetry(reason);
    if (lipSyncAnimationRef.current !== null) {
      window.cancelAnimationFrame(lipSyncAnimationRef.current);
      lipSyncAnimationRef.current = null;
    }
    if (lipSyncIntervalRef.current !== null) {
      window.clearInterval(lipSyncIntervalRef.current);
      lipSyncIntervalRef.current = null;
    }
    if (lipSyncAudioSourceRef.current) {
      try {
        lipSyncAudioSourceRef.current.disconnect();
      } catch {
        // The node may already be detached after an interrupted playback.
      }
      lipSyncAudioSourceRef.current = null;
    }
    if (lipSyncAnalyserRef.current) {
      try {
        lipSyncAnalyserRef.current.disconnect();
      } catch {
        // The node may already be detached after an interrupted playback.
      }
      lipSyncAnalyserRef.current = null;
    }
    const context = lipSyncAudioContextRef.current;
    lipSyncAudioContextRef.current = null;
    if (context && context.state !== "closed") {
      void context.close().catch(() => undefined);
    }
    if (resetState) {
      setTrackedLipSyncSource("none");
      setTrackedAvatarMouthLevel(0);
    }
  };

  const startTextLipSync = (
    text: string,
    runId: number,
    options: {
      channel?: AvatarTelemetryChannel;
      isSourceActive?: () => boolean;
      mode?: SpeechPlaybackMode;
    } = {}
  ) => {
    const isSourceActive = options.isSourceActive ?? (() => Boolean(currentUtteranceRef.current));
    const channel = options.channel ?? "system";
    const mode = options.mode ?? speechPlaybackMode;
    stopLipSync(true, "text_lip_sync_replaced");
    if (runId !== speechRunIdRef.current) return;
    const units = Array.from(text.trim() || " ");
    const intervalMs = Math.max(70, Math.min(140, Math.round(110 / Math.max(speechRate, 0.5))));
    let index = 0;
    setTrackedLipSyncSource("text");
    beginLipSyncTelemetry("text", runId, channel, mode);
    lipSyncIntervalRef.current = window.setInterval(() => {
      if (runId !== speechRunIdRef.current || !isSourceActive()) {
        stopLipSync(true, "text_lip_sync_inactive");
        return;
      }
      const unit = units[index % units.length] ?? " ";
      const codePoint = unit.codePointAt(0) ?? index;
      const isPause = /\s|[,.!?;:，。！？、；：]/.test(unit);
      setTrackedAvatarMouthLevel(isPause ? 0 : 1 + ((codePoint + index) % 3));
      index += 1;
    }, intervalMs);
  };

  const startAudioLipSync = (
    audio: HTMLAudioElement,
    fallbackText: string,
    runId: number,
    mode: SpeechPlaybackMode
  ) => {
    stopLipSync(true, "audio_lip_sync_replaced");
    if (runId !== speechRunIdRef.current) return;
    const AudioContextClass =
      window.AudioContext ??
      (window as Window & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!AudioContextClass) {
      startTextLipSync(fallbackText, runId, {
        channel: "external_text_fallback",
        isSourceActive: () => audio === currentAudioRef.current && !audio.ended,
        mode
      });
      return;
    }

    try {
      const context = new AudioContextClass();
      const analyser = context.createAnalyser();
      const source = context.createMediaElementSource(audio);
      analyser.fftSize = 256;
      analyser.smoothingTimeConstant = 0.45;
      source.connect(analyser);
      analyser.connect(context.destination);
      lipSyncAudioContextRef.current = context;
      lipSyncAudioSourceRef.current = source;
      lipSyncAnalyserRef.current = analyser;
      setTrackedLipSyncSource("audio");
      beginLipSyncTelemetry("audio", runId, "external", mode);
      void context.resume().catch(() => undefined);

      const samples = new Uint8Array(analyser.fftSize);
      const update = () => {
        if (
          runId !== speechRunIdRef.current ||
          audio !== currentAudioRef.current ||
          audio.paused ||
          audio.ended
        ) {
          stopLipSync(true, "audio_lip_sync_inactive");
          return;
        }
        analyser.getByteTimeDomainData(samples);
        let sum = 0;
        for (const sample of samples) {
          const centered = (sample - 128) / 128;
          sum += centered * centered;
        }
        const rms = Math.sqrt(sum / samples.length);
        const level = rms < 0.018 ? 0 : rms < 0.055 ? 1 : rms < 0.12 ? 2 : 3;
        setTrackedAvatarMouthLevel(level);
        lipSyncAnimationRef.current = window.requestAnimationFrame(update);
      };
      update();
    } catch {
      startTextLipSync(fallbackText, runId, {
        channel: "external_text_fallback",
        isSourceActive: () => audio === currentAudioRef.current && !audio.ended,
        mode
      });
    }
  };

  const cleanupCurrentAudio = (reason = "audio_cleanup") => {
    stopLipSync(true, reason);
    if (currentAudioRef.current) {
      currentAudioRef.current.pause();
      currentAudioRef.current.src = "";
      currentAudioRef.current.load();
      currentAudioRef.current = null;
    }
    if (currentAudioUrlRef.current) {
      URL.revokeObjectURL(currentAudioUrlRef.current);
      currentAudioUrlRef.current = null;
    }
  };

  const speechIsActive = () => {
    return Boolean(
      currentUtteranceRef.current ||
        currentAudioRef.current ||
        speechSegmentBusyRef.current ||
        ttsAbortControllerRef.current ||
        speechQueueRef.current.length > 0 ||
        ("speechSynthesis" in window &&
          (window.speechSynthesis.speaking || window.speechSynthesis.pending))
    );
  };

  const interruptSpeech = (reason = "已停止播放", countInterrupt = true) => {
    const hadSpeech = speechIsActive();
    const interruptedAt = performance.now();
    const interruptedRunId = speechRunIdRef.current;
    const mouthLevelBefore = avatarMouthLevelRef.current;
    const lipSyncSourceBefore = lipSyncSourceRef.current;
    const playbackModeBefore = speechPlaybackMode;
    speechRunIdRef.current += 1;
    currentUtteranceRef.current = null;
    speechSegmentBusyRef.current = false;
    speechQueueRef.current = [];
    streamSpeechBufferRef.current = "";
    ttsAbortControllerRef.current?.abort();
    ttsAbortControllerRef.current = null;
    cleanupCurrentAudio("interrupt");
    if ("speechSynthesis" in window) {
      window.speechSynthesis.cancel();
    }
    setSpeaking(false);
    setVoiceActive(false);
    setSpeechQueueSize(0);
    setSpeechPlaybackMode("idle");
    setTtsStatus(reason);
    if (countInterrupt && hadSpeech) {
      setSpeechInterruptCount((count) => count + 1);
      recordAvatarEvaluation({
        event_type: "avatar_interrupt",
        latency_ms: Math.round(performance.now() - interruptedAt),
        reason,
        payload: {
          run_id: interruptedRunId,
          playback_mode: playbackModeBefore,
          mouth_level_before: mouthLevelBefore,
          lip_sync_source_before: lipSyncSourceBefore,
          avatar_mode: avatarMode,
          live2d_status: live2dStatus
        }
      });
    }
  };

  const stopSpeech = () => {
    if (!ttsPlaybackSupported()) return;
    interruptSpeech("已停止播放");
  };

  const speakText = (text: string, mode: ActiveSpeechMode = "reply") => {
    if (!ttsPlaybackSupported() || !text.trim()) return;
    startSpeechPlayback(splitSpeechSegments(text, true).segments, mode);
  };

  const startSpeechPlayback = (segments: string[], mode: ActiveSpeechMode) => {
    if (!ttsPlaybackSupported()) return;
    const cleanSegments = normalizeSpeechSegments(segments);
    if (cleanSegments.length === 0) return;
    speechRunIdRef.current += 1;
    const runId = speechRunIdRef.current;
    if ("speechSynthesis" in window) {
      window.speechSynthesis.cancel();
    }
    ttsAbortControllerRef.current?.abort();
    ttsAbortControllerRef.current = null;
    cleanupCurrentAudio("playback_replaced");
    currentUtteranceRef.current = null;
    speechSegmentBusyRef.current = false;
    speechQueueRef.current = cleanSegments;
    streamSpeechBufferRef.current = "";
    setSpeechQueueSize(cleanSegments.length);
    setSpeechSegmentCount(0);
    setSpeechPlaybackMode(mode);
    setSpeaking(true);
    setVoiceActive(false);
    setTtsLatency(null);
    setTtsStatus(mode === "stream" ? "等待首句播放" : "准备播放");
    window.setTimeout(() => drainSpeechQueue(runId, mode), 0);
  };

  const enqueueSpeechSegments = (segments: string[], mode: ActiveSpeechMode) => {
    if (!ttsPlaybackSupported()) return;
    const cleanSegments = normalizeSpeechSegments(segments);
    if (cleanSegments.length === 0) return;
    const runId = speechRunIdRef.current;
    speechQueueRef.current.push(...cleanSegments);
    setSpeechQueueSize(speechQueueRef.current.length);
    setSpeechPlaybackMode(mode);
    if (
      !speechSegmentBusyRef.current &&
      !currentUtteranceRef.current &&
      !currentAudioRef.current &&
      (!("speechSynthesis" in window) || !window.speechSynthesis.speaking)
    ) {
      drainSpeechQueue(runId, mode);
    }
  };

  const beginStreamingSpeech = () => {
    if (!speechEnabled || !ttsPlaybackSupported()) return false;
    speechRunIdRef.current += 1;
    const runId = speechRunIdRef.current;
    if ("speechSynthesis" in window) {
      window.speechSynthesis.cancel();
    }
    ttsAbortControllerRef.current?.abort();
    ttsAbortControllerRef.current = null;
    cleanupCurrentAudio("stream_replaced");
    currentUtteranceRef.current = null;
    speechSegmentBusyRef.current = false;
    speechQueueRef.current = [];
    streamSpeechBufferRef.current = "";
    setSpeaking(false);
    setVoiceActive(false);
    setSpeechQueueSize(0);
    setSpeechSegmentCount(0);
    setSpeechPlaybackMode("stream");
    setTtsLatency(null);
    setTtsStatus("等待回复首句");
    return runId > 0;
  };

  const enqueueStreamingSpeechDelta = (chunk: string) => {
    if (!speechEnabled || !ttsPlaybackSupported() || !chunk) return;
    streamSpeechBufferRef.current += chunk;
    const { segments, rest } = splitSpeechSegments(streamSpeechBufferRef.current, false);
    streamSpeechBufferRef.current = rest;
    enqueueSpeechSegments(segments, "stream");
  };

  const finishStreamingSpeech = () => {
    if (!speechEnabled || !ttsPlaybackSupported()) return;
    const { segments } = splitSpeechSegments(streamSpeechBufferRef.current, true);
    streamSpeechBufferRef.current = "";
    enqueueSpeechSegments(segments, "stream");
    if (!currentUtteranceRef.current && !currentAudioRef.current && speechQueueRef.current.length === 0) {
      setSpeechPlaybackMode("idle");
      setSpeaking(false);
      setVoiceActive(false);
      setTtsStatus("播放完成");
    }
  };

  const drainSpeechQueue = (runId: number, mode: ActiveSpeechMode) => {
    if (!ttsPlaybackSupported()) return;
    if (
      runId !== speechRunIdRef.current ||
      currentUtteranceRef.current ||
      currentAudioRef.current ||
      speechSegmentBusyRef.current
    ) {
      return;
    }
    const text = speechQueueRef.current.shift();
    setSpeechQueueSize(speechQueueRef.current.length);
    if (!text) {
      setSpeaking(false);
      setSpeechPlaybackMode("idle");
      stopLipSync(true, "queue_empty");
      setTtsStatus(mode === "stream" ? "流式播放完成" : "播放完成");
      return;
    }

    speechSegmentBusyRef.current = true;
    if (externalTtsPreferred()) {
      void playExternalSpeechSegment(text, runId, mode);
      return;
    }
    playSystemSpeechSegment(text, runId, mode);
  };

  const playSystemSpeechSegment = (text: string, runId: number, mode: ActiveSpeechMode) => {
    if (!speechSupported || !("speechSynthesis" in window)) {
      speechSegmentBusyRef.current = false;
      setSpeaking(false);
      setVoiceActive(false);
      stopLipSync(true, "system_speech_unavailable");
      setTtsStatus("系统语音不可用");
      return;
    }
    const utterance = new SpeechSynthesisUtterance(text);
    currentUtteranceRef.current = utterance;
    const selectedVoice = voices.find((voice) => voice.name === selectedVoiceName);
    if (selectedVoice) {
      utterance.voice = selectedVoice;
      utterance.lang = selectedVoice.lang;
    } else {
      utterance.lang = "zh-CN";
    }
    utterance.rate = speechRate;
    utterance.pitch = 1;
    utterance.volume = 1;

    const startedAt = performance.now();
    utterance.onstart = () => {
      if (runId !== speechRunIdRef.current) return;
      setSpeaking(true);
      setVoiceActive(true);
      const firstPlayMs = Math.round(performance.now() - startedAt);
      startTextLipSync(text, runId, { channel: "system", mode });
      recordAvatarVoiceStart(firstPlayMs, "system", mode, text.length, runId);
      setTtsStatus(`${mode === "stream" ? "流式播放中" : "播放中"} · ${text.length} 字`);
      setTtsLatency((current) => current ?? firstPlayMs);
    };
    utterance.onend = () => {
      if (runId !== speechRunIdRef.current) return;
      currentUtteranceRef.current = null;
      speechSegmentBusyRef.current = false;
      setVoiceActive(false);
      stopLipSync(true, "system_speech_ended");
      setSpeechSegmentCount((count) => count + 1);
      if (speechQueueRef.current.length > 0) {
        window.setTimeout(() => drainSpeechQueue(runId, mode), 0);
        return;
      }
      setSpeaking(false);
      setVoiceActive(false);
      setSpeechPlaybackMode("idle");
      setTtsStatus(mode === "stream" ? "流式播放完成" : "播放完成");
    };
    utterance.onerror = () => {
      if (runId !== speechRunIdRef.current) return;
      currentUtteranceRef.current = null;
      speechSegmentBusyRef.current = false;
      speechQueueRef.current = [];
      setSpeaking(false);
      setVoiceActive(false);
      stopLipSync(true, "system_speech_error");
      setSpeechQueueSize(0);
      setSpeechPlaybackMode("idle");
      setTtsStatus("播放中断");
    };
    setSpeaking(true);
    window.speechSynthesis.speak(utterance);
  };

  const playExternalSpeechSegment = async (text: string, runId: number, mode: ActiveSpeechMode) => {
    const startedAt = performance.now();
    const controller = new AbortController();
    ttsAbortControllerRef.current = controller;
    setSpeaking(true);
    setVoiceActive(false);
    stopLipSync(true, "external_tts_synth_start");
    setTtsStatus(`${mode === "stream" ? "外部 TTS 合成中" : "TTS 合成中"} · ${text.length} 字`);
    try {
      const result = await synthesizeTts(text, controller.signal);
      if (runId !== speechRunIdRef.current) return;
      ttsAbortControllerRef.current = null;
      if (!result.configured) {
        speechSegmentBusyRef.current = false;
        playSystemSpeechSegment(text, runId, mode);
        return;
      }
      if (result.error || result.status === "error") {
        throw new Error(result.error ?? "TTS service failed.");
      }
      const audioSource = ttsResultToAudioSource(result);
      if (!audioSource) {
        throw new Error("TTS service returned no playable audio.");
      }
      const audio = new Audio(audioSource.url);
      if (audioSource.revoke) {
        currentAudioUrlRef.current = audioSource.url;
      }
      currentAudioRef.current = audio;
      audio.onplaying = () => {
        if (runId !== speechRunIdRef.current) return;
        setVoiceActive(true);
        const firstPlayMs = Math.round(performance.now() - startedAt);
        startAudioLipSync(audio, text, runId, mode);
        recordAvatarVoiceStart(firstPlayMs, "external", mode, text.length, runId);
        setTtsLatency((current) => current ?? firstPlayMs);
        setTtsStatus(`${mode === "stream" ? "外部 TTS 播放中" : "TTS 播放中"} · ${text.length} 字`);
      };
      audio.onended = () => {
        if (runId !== speechRunIdRef.current) return;
        cleanupCurrentAudio("external_audio_ended");
        speechSegmentBusyRef.current = false;
        setVoiceActive(false);
        setSpeechSegmentCount((count) => count + 1);
        if (speechQueueRef.current.length > 0) {
          window.setTimeout(() => drainSpeechQueue(runId, mode), 0);
          return;
        }
        setSpeaking(false);
        setSpeechPlaybackMode("idle");
        setTtsStatus(mode === "stream" ? "外部 TTS 流式播放完成" : "外部 TTS 播放完成");
      };
      audio.onerror = () => {
        if (runId !== speechRunIdRef.current) return;
        cleanupCurrentAudio("external_audio_error");
        speechSegmentBusyRef.current = false;
        setSpeaking(false);
        setVoiceActive(false);
        setSpeechQueueSize(0);
        setSpeechPlaybackMode("idle");
        setTtsStatus("外部 TTS 播放失败");
      };
      await audio.play();
    } catch (error) {
      if (runId !== speechRunIdRef.current) return;
      ttsAbortControllerRef.current = null;
      cleanupCurrentAudio("external_tts_error");
      speechSegmentBusyRef.current = false;
      setVoiceActive(false);
      const message = error instanceof Error ? error.message : "外部 TTS 失败";
      if (speechSupported) {
        setTtsStatus(`外部 TTS 失败, 使用系统语音: ${message}`);
        playSystemSpeechSegment(text, runId, mode);
        return;
      }
      speechQueueRef.current = [];
      setSpeaking(false);
      setVoiceActive(false);
      setSpeechQueueSize(0);
      setSpeechPlaybackMode("idle");
      setTtsStatus(message);
    }
  };

  const ensureSttReady = async () => {
    if (config?.stt.configured === false) {
      setSttStatus("STT 未配置");
      return false;
    }
    const status = await refreshSttStatus(config?.stt.configured ?? true);
    if (!status.configured) {
      setSttStatus(status.error ?? "STT 未配置");
      return false;
    }
    if (!status.available) {
      setSttStatus(status.error ? `STT 服务未连接: ${status.error}` : "STT 服务未连接");
      return false;
    }
    return true;
  };

  const startRecording = async () => {
    if (!sttSupported || recording || transcribing || busy) return;
    try {
      if (speechIsActive()) {
        interruptSpeech("录音已打断语音");
      }
      const ready = await ensureSttReady();
      if (!ready) return;
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mimeType = chooseRecordingMimeType();
      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      audioChunksRef.current = [];
      mediaStreamRef.current = stream;
      mediaRecorderRef.current = recorder;
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };
      recorder.onstop = () => {
        const blob = new Blob(audioChunksRef.current, {
          type: recorder.mimeType || "audio/webm"
        });
        stream.getTracks().forEach((track) => track.stop());
        mediaStreamRef.current = null;
        mediaRecorderRef.current = null;
        void transcribeRecording(blob);
      };
      recorder.start();
      setRecording(true);
      setSttStatus("正在录音");
    } catch (error) {
      const message = error instanceof Error ? error.message : "麦克风不可用";
      setSttStatus(message);
    }
  };

  const stopRecording = () => {
    if (!recording || !mediaRecorderRef.current) return;
    setRecording(false);
    setTranscribing(true);
    setSttStatus("正在转写");
    mediaRecorderRef.current.stop();
  };

  const toggleRecording = async () => {
    if (recording) {
      stopRecording();
      return;
    }
    await startRecording();
  };

  const transcribeRecording = async (blob: Blob) => {
    try {
      if (blob.size === 0) {
        setSttStatus("没有录到音频");
        return;
      }
      const result = await transcribeAudio(blob);
      if (!result.configured) {
        setSttStatus(result.error ?? "STT 未配置");
        return;
      }
      if (result.error) {
        setSttStatus(result.error);
        return;
      }
      if (!result.text.trim()) {
        setSttStatus("未识别到文字");
        return;
      }
      setInput(result.text.trim());
      setSttStatus(formatSttResultStatus(result));
    } catch (error) {
      const message = error instanceof Error ? error.message : "转写失败";
      setSttStatus(message);
    } finally {
      setTranscribing(false);
    }
  };

  const updateLastAssistantMessage = (content: string) => {
    setMessages((current) => {
      const next = [...current];
      for (let index = next.length - 1; index >= 0; index -= 1) {
        if (next[index].role === "assistant") {
          next[index] = { ...next[index], content };
          break;
        }
      }
      return next;
    });
  };

  const applyChatResult = (result: ChatResult) => {
    setMemories(result.memories ?? []);
    setExtraction(result.memory_extraction ?? null);
    setLatency(result.latency_ms);
    setLastAssistantText(result.reply);
    setActiveMemoryView(nextMemoryView(result));
    void refreshMemoryCard();
    void refreshMemoryReflection();
    void refreshEvaluation();
    if (speechEnabled) {
      speakText(result.reply, "reply");
    }
  };

  const applyStreamChatResult = (result: ChatResult, speechWasStreamed: boolean) => {
    setMemories(result.memories ?? []);
    setExtraction(result.memory_extraction ?? null);
    setLatency(result.latency_ms);
    setLastAssistantText(result.reply);
    setActiveMemoryView(nextMemoryView(result));
    void refreshMemoryCard();
    void refreshMemoryReflection();
    void refreshEvaluation();
    if (speechWasStreamed) {
      finishStreamingSpeech();
    } else if (speechEnabled) {
      speakText(result.reply, "reply");
    }
  };

  const handleInputChange = (value: string) => {
    if (value.trim() && value !== input && speechIsActive()) {
      interruptSpeech("输入已打断语音");
    }
    setInput(value);
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const text = input.trim();
    if (!text || busy) return;

    if (speechIsActive()) {
      interruptSpeech("新消息已打断语音");
    }
    setBusy(true);
    setInput("");
    setMessages((current) => [
      ...current,
      { role: "user", content: text },
      { role: "assistant", content: "正在生成..." }
    ]);
    let streamedText = "";
    const speechWasStreamed = beginStreamingSpeech();
    try {
      await streamChatRequest(text, {
        onMeta: (meta) => setMemories(meta.memories ?? []),
        onDelta: (chunk) => {
          streamedText += chunk;
          updateLastAssistantMessage(streamedText);
          if (speechWasStreamed) {
            enqueueStreamingSpeechDelta(chunk);
          }
        },
        onDone: (result) => {
          updateLastAssistantMessage(result.reply);
          applyStreamChatResult(result, speechWasStreamed);
        }
      });
    } catch (error) {
      if (speechWasStreamed) {
        finishStreamingSpeech();
      }
      if (!streamedText) {
        try {
          updateLastAssistantMessage("正在切换到普通回复...");
          const result = await api.chat(text);
          updateLastAssistantMessage(result.reply);
          applyChatResult(result);
        } catch (fallbackError) {
          updateLastAssistantMessage("请求失败");
          setMessages((current) => [
            ...current,
            {
              role: "system",
              content: fallbackError instanceof Error ? fallbackError.message : "请求失败"
            }
          ]);
        }
      } else {
        setMessages((current) => [
          ...current,
          { role: "system", content: error instanceof Error ? error.message : "流式回复中断" }
        ]);
      }
    } finally {
      setBusy(false);
    }
  };

  const sendDesktopNotification = async (title: string, body: string) => {
    const notifier = window.kanojoApi?.notify ?? browserBackendApi.notify;
    return notifier?.(title, body);
  };

  const runHeartbeat = async (source: "manual" | "scheduler" | "forced") => {
    if (heartbeatBusyRef.current) return;
    heartbeatBusyRef.current = true;
    try {
      const result = await api.heartbeat({
        enabled: heartbeatEnabled || source === "forced",
        force: source === "forced",
        source
      });
      setLastHeartbeat(result);
      setLastHeartbeatAt(new Date().toLocaleTimeString());
      void refreshEvaluation();
      const content = result.fired
        ? `主动触发: ${result.message ?? ""}`
        : `未触发: ${result.reason}`;
      if (result.fired || showDebugLogs) {
        setMessages((current) => [...current, { role: "system", content }]);
      }
      if (result.fired && result.message) {
        const notification = await sendDesktopNotification("AI Memory Card", result.message);
        setNotificationState(readNotificationState());
        if (notification && !notification.delivered && showDebugLogs) {
          setMessages((current) => [
            ...current,
            { role: "system", content: `通知未送达: ${notification.reason ?? "unknown"}` }
          ]);
        }
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "heartbeat failed";
      if (showDebugLogs) {
        setMessages((current) => [...current, { role: "system", content: `心跳失败: ${message}` }]);
      }
    } finally {
      heartbeatBusyRef.current = false;
    }
  };

  const tickHeartbeat = async () => {
    await runHeartbeat("manual");
  };

  const forceHeartbeat = async () => {
    await runHeartbeat("forced");
  };

  const recordDesktopActivity = (
    activityType: string,
    intensity = 1,
    throttleMs = 60_000
  ) => {
    const now = Date.now();
    if (throttleMs > 0 && now - lastActivitySentAtRef.current < throttleMs) {
      return;
    }
    lastActivitySentAtRef.current = now;
    setLastActivitySignal(`${activityType} · ${new Date().toLocaleTimeString()}`);
    void api
      .recordActivity({
        activity_type: activityType,
        source: "desktop",
        intensity,
        note: document.visibilityState
      })
      .catch((error) => {
        if (showDebugLogs) {
          const message = error instanceof Error ? error.message : "activity event failed";
          setMessages((current) => [...current, { role: "system", content: `活动上报失败: ${message}` }]);
        }
      });
  };

  return (
    <main className="shell">
      <aside className="sidebar">
        <div className="sidebar-header">
          <h1>AI Memory Card</h1>
          <p>桌面陪伴代理 · P5.5</p>
        </div>

        <section className="status-panel">
          <div className="status-line">
            <Activity size={18} />
            <span>{status}</span>
          </div>
          <div className="status-metrics">
            <span>
              <Database size={14} />
              {latency === null ? "未请求" : `${latency} ms`}
            </span>
            <span title={nodeStatus?.node.name ?? config?.node?.name ?? "unknown"}>
              {nodeStatus?.node.role ?? config?.node?.role ?? "节点未知"}
            </span>
            <span title={nodeStatus?.memory_write_policy.note ?? "写入策略未刷新"}>
              写入 {nodeStatus?.memory_write_policy.primary ?? "unknown"}
            </span>
          </div>
          <div className={`node-alert ${nodeAlert.level}`} title={nodeAlert.detail}>
            <span>{nodeAlert.title}</span>
            <strong>{nodeAlert.detail}</strong>
          </div>
        </section>

        <nav className="panel-tabs" aria-label="侧栏面板">
          <button
            className={activePanel === "control" ? "active" : ""}
            onClick={() => setActivePanel("control")}
            type="button"
          >
            <Settings size={16} />
            <span>控制</span>
          </button>
          <button
            className={activePanel === "memory" ? "active" : ""}
            onClick={() => setActivePanel("memory")}
            type="button"
          >
            <Database size={16} />
            <span>记忆</span>
          </button>
          <button
            className={activePanel === "debug" ? "active" : ""}
            onClick={() => setActivePanel("debug")}
            type="button"
          >
            <Activity size={16} />
            <span>调试</span>
          </button>
        </nav>

        <div className="sidebar-panel">
          {activePanel === "control" ? (
            <>
              <section className="settings-panel">
                <div className="panel-title-row">
                  <h2>运行设置</h2>
                  <ShieldCheck size={16} />
                </div>
                <div className="setting-row">
                  <span>
                    <Cpu size={14} />
                    模型
                  </span>
                  <strong title={config?.llm.model ?? "unknown"}>{config?.llm.model ?? "unknown"}</strong>
                </div>
                <div className="setting-row">
                  <span>LLM</span>
                  <strong>{config?.llm.configured ? "Ollama / local" : "mock"}</strong>
                </div>
                <div className="setting-row">
                  <span>记忆抽取</span>
                  <strong>{config?.memory_extraction_mode ?? "unknown"}</strong>
                </div>
                <div className="setting-row">
                  <span>通知权限</span>
                  <strong>{notificationState}</strong>
                </div>
                <div className="setting-row">
                  <span>STT</span>
                  <strong>{config?.stt.configured ? config.stt.model : "未配置"}</strong>
                </div>
                <div className="setting-row">
                  <span>冷却</span>
                  <strong>{config ? `${config.heartbeat.cooldown_minutes} 分钟` : "unknown"}</strong>
                </div>
              </section>

              <section className="tts-panel">
                <div className="panel-title-row">
                  <h2>语音输出</h2>
                  <label className="toggle">
                    <input
                      checked={speechEnabled}
                      disabled={!ttsPlaybackSupported()}
                      onChange={(event) => {
                        setSpeechEnabled(event.target.checked);
                        if (!event.target.checked) {
                          stopSpeech();
                        }
                      }}
                      type="checkbox"
                    />
                    <span>{speechEnabled ? <Volume2 size={15} /> : <VolumeX size={15} />}</span>
                  </label>
                </div>

                <label className="field-label" htmlFor="voice-select">
                  <Volume2 size={15} />
                  <span>声音</span>
                </label>
                <select
                  disabled={!speechSupported || voices.length === 0}
                  id="voice-select"
                  onChange={(event) => setSelectedVoiceName(event.target.value)}
                  value={selectedVoiceName}
                >
                  {voices.length === 0 ? (
                    <option value="">无可用系统语音</option>
                  ) : (
                    voices.map((voice) => (
                      <option key={`${voice.name}-${voice.lang}`} value={voice.name}>
                        {voice.name} · {voice.lang}
                      </option>
                    ))
                  )}
                </select>

                <label className="field-label" htmlFor="speech-rate">
                  <Clock3 size={15} />
                  <span>语速 {speechRate.toFixed(1)}x</span>
                </label>
                <input
                  className="range-input"
                  disabled={!speechSupported}
                  id="speech-rate"
                  max={1.4}
                  min={0.7}
                  onChange={(event) => setSpeechRate(Number(event.target.value))}
                  step={0.1}
                  type="range"
                  value={speechRate}
                />

                <div className="heartbeat-state">
                  <span>{ttsPlaybackSupported() ? ttsStatus : "语音输出不可用"}</span>
                  <strong className={speaking || speechQueueSize > 0 ? "accepted" : "rejected"}>
                    {speaking || speechQueueSize > 0 ? "播放中" : "待机"}
                  </strong>
                </div>
                <p>
                  {ttsLatency === null ? "尚未播放" : `首音延迟约 ${ttsLatency} ms`}
                  {speechPlaybackMode !== "idle" ? ` · ${formatSpeechMode(speechPlaybackMode)}` : ""}
                  {speechSegmentCount > 0 ? ` · 已播 ${speechSegmentCount} 段` : ""}
                  {speechQueueSize > 0 ? ` · 队列 ${speechQueueSize} 段` : ""}
                  {speechInterruptCount > 0 ? ` · 已打断 ${speechInterruptCount} 次` : ""}
                </p>

                <div className="button-row">
                  <button
                    className="secondary-button"
                    disabled={!lastAssistantText || !ttsPlaybackSupported()}
                    onClick={() => speakText(lastAssistantText, "replay")}
                    type="button"
                  >
                    <Play size={17} />
                    <span>重播</span>
                  </button>
                  <button
                    className="secondary-button danger"
                    disabled={!ttsPlaybackSupported() || (!speaking && speechQueueSize === 0)}
                    onClick={stopSpeech}
                    type="button"
                  >
                    <Square size={17} />
                    <span>停止</span>
                  </button>
                </div>
              </section>

              <section className="heartbeat-panel">
                <div className="panel-title-row">
                  <h2>主动心跳</h2>
                  <label className="toggle">
                    <input
                      checked={heartbeatEnabled}
                      onChange={(event) => setHeartbeatEnabled(event.target.checked)}
                      type="checkbox"
                    />
                    <span>{heartbeatEnabled ? <Bell size={15} /> : <BellOff size={15} />}</span>
                  </label>
                </div>

                <label className="field-label" htmlFor="heartbeat-interval">
                  <Clock3 size={15} />
                  <span>检查间隔</span>
                </label>
                <select
                  id="heartbeat-interval"
                  onChange={(event) => setHeartbeatIntervalSeconds(Number(event.target.value))}
                  value={heartbeatIntervalSeconds}
                >
                  <option value={30}>30 秒</option>
                  <option value={60}>60 秒</option>
                  <option value={180}>3 分钟</option>
                  <option value={300}>5 分钟</option>
                </select>

                <div className="heartbeat-state">
                  <span>{lastHeartbeatAt ? `最近: ${lastHeartbeatAt}` : "尚未检查"}</span>
                  <strong className={lastHeartbeat?.fired ? "accepted" : "rejected"}>
                    {lastHeartbeat ? (lastHeartbeat.fired ? "已触发" : "未触发") : "待机"}
                  </strong>
                </div>
                {lastHeartbeat ? <p>{lastHeartbeat.reason}</p> : null}
                <p>活动信号: {lastActivitySignal}</p>

                <div className="button-row">
                  <button className="secondary-button" onClick={tickHeartbeat} type="button">
                    <Settings size={17} />
                    <span>检查</span>
                  </button>
                  <button className="secondary-button accent" onClick={forceHeartbeat} type="button">
                    <Zap size={17} />
                    <span>通知</span>
                  </button>
                </div>
              </section>
            </>
          ) : null}

          {activePanel === "memory" ? (
            <>
              <nav className="memory-view-tabs" aria-label="记忆页视图">
                <button
                  className={activeMemoryView === "card" ? "active" : ""}
                  onClick={() => setActiveMemoryView("card")}
                  type="button"
                >
                  <Database size={15} />
                  <span>名片</span>
                  <strong>{memoryCard?.memory_count ?? 0}</strong>
                </button>
                <button
                  className={activeMemoryView === "reflection" ? "active" : ""}
                  onClick={() => setActiveMemoryView("reflection")}
                  type="button"
                >
                  <SearchCheck size={15} />
                  <span>反思</span>
                  <strong>{memoryReflection?.sample_ready ? "OK" : "草"}</strong>
                </button>
                <button
                  className={activeMemoryView === "hits" ? "active" : ""}
                  onClick={() => setActiveMemoryView("hits")}
                  type="button"
                >
                  <Database size={15} />
                  <span>命中</span>
                  <strong>{memories.length}</strong>
                </button>
                <button
                  className={activeMemoryView === "audit" ? "active" : ""}
                  onClick={() => setActiveMemoryView("audit")}
                  type="button"
                >
                  <Activity size={15} />
                  <span>审计</span>
                  <strong>{extraction?.decisions.length ?? 0}</strong>
                </button>
                <button
                  className={activeMemoryView === "versions" ? "active" : ""}
                  onClick={() => setActiveMemoryView("versions")}
                  type="button"
                >
                  <Clock3 size={15} />
                  <span>版本</span>
                  <strong>{memoryCardSnapshots.length}</strong>
                </button>
              </nav>

              {activeMemoryView === "card" ? (
                <section className="memory-card-panel">
                  <div className="panel-title-row">
                    <h2>记忆名片</h2>
                    <button
                      aria-label="刷新记忆名片"
                      className="icon-button"
                      onClick={() => void refreshMemoryCard()}
                      title="刷新记忆名片"
                      type="button"
                    >
                      <RefreshCw size={15} />
                    </button>
                  </div>
                  <p className="memory-card-summary">
                    {memoryCard?.summary ?? "正在整理长期记忆"}
                  </p>
                  <div className="memory-card-meta">
                    <span>{memoryCard?.memory_count ?? 0} 条长期记忆</span>
                    <span>{memoryCard?.conversation_count ?? 0} 条消息</span>
                  </div>
                  <div className="memory-card-actions">
                    <button
                      aria-label="复制记忆名片 Markdown"
                      className="secondary-button"
                      disabled={!memoryCard}
                      onClick={() => void copyMemoryCardMarkdown()}
                      title="复制记忆名片 Markdown"
                      type="button"
                    >
                      <Copy size={15} />
                      <span>复制</span>
                    </button>
                    <button
                      aria-label="下载记忆名片 Markdown"
                      className="secondary-button"
                      disabled={!memoryCard}
                      onClick={() => void downloadMemoryCard("markdown")}
                      title="下载记忆名片 Markdown"
                      type="button"
                    >
                      <Download size={15} />
                      <span>MD</span>
                    </button>
                    <button
                      aria-label="下载记忆名片 JSON"
                      className="secondary-button accent"
                      disabled={!memoryCard}
                      onClick={() => void downloadMemoryCard("json")}
                      title="下载记忆名片 JSON"
                      type="button"
                    >
                      <Download size={15} />
                      <span>JSON</span>
                    </button>
                  </div>
                  <div className="memory-card-sections">
                    {(memoryCard?.sections ?? []).map((section) => (
                      <article className="memory-card-section" key={section.kind}>
                        <h3>{section.title}</h3>
                        {section.items.length === 0 ? (
                          <p className="empty">暂无</p>
                        ) : (
                          section.items.map((item) => (
                            <div className="memory-card-entry" key={item.id}>
                              <p title={`${item.importance}/${item.confidence}`}>{item.content}</p>
                              <button
                                aria-label={`编辑记忆 ${item.id}`}
                                className="icon-button"
                                onClick={() => void editMemoryContent(item)}
                                title="编辑这条长期记忆"
                                type="button"
                              >
                                <Pencil size={14} />
                              </button>
                              <button
                                aria-label={`降权记忆 ${item.id}`}
                                className="icon-button"
                                onClick={() => void reduceMemoryWeight(item)}
                                title="降低这条记忆的重要性"
                                type="button"
                              >
                                <SlidersHorizontal size={14} />
                              </button>
                              <button
                                aria-label={`停用记忆 ${item.id}`}
                                className="icon-button danger"
                                disabled={deletingMemoryId === item.id}
                                onClick={() => void deactivateMemory(item)}
                                title="停用这条长期记忆"
                                type="button"
                              >
                                <Trash2 size={14} />
                              </button>
                            </div>
                          ))
                        )}
                      </article>
                    ))}
                  </div>
                  <p className="evaluation-status">
                    {memoryCardStatus} · {memoryCardExportStatus} · {memoryEditStatus}
                  </p>
                </section>
              ) : null}

              {activeMemoryView === "reflection" ? (
                <section className="reflection-panel memory-view-panel">
                  <div className="panel-title-row">
                    <h2>反思摘要</h2>
                    <button
                      aria-label="刷新反思摘要"
                      className="icon-button"
                      onClick={() => void refreshMemoryReflection()}
                      title="刷新反思摘要"
                      type="button"
                    >
                      <RefreshCw size={15} />
                    </button>
                  </div>
                  <div className="reflection-readiness">
                    <span>{memoryReflection?.readiness ?? "未生成"}</span>
                    <strong>{memoryReflection?.memory_count ?? 0} 条记忆</strong>
                  </div>
                  <p className="memory-card-summary">
                    {memoryReflection?.summary ?? "正在整理反思摘要"}
                  </p>
                  <div className="reflection-theme-list">
                    {(memoryReflection?.themes ?? []).map((theme) => (
                      <article className="reflection-theme" key={theme.kind}>
                        <div>
                          <h3>{theme.title}</h3>
                          <span>{theme.count} 条</span>
                        </div>
                        <p>{theme.headline}</p>
                        <small>{theme.next_focus}</small>
                        {theme.evidence.length ? (
                          <ul>
                            {theme.evidence.map((item) => (
                              <li key={`${theme.kind}-${item}`}>{item}</li>
                            ))}
                          </ul>
                        ) : null}
                      </article>
                    ))}
                  </div>
                  <div className="reflection-questions">
                    <h3>待验证</h3>
                    {(memoryReflection?.next_questions ?? ["暂无待验证问题"]).map((question) => (
                      <p key={question}>{question}</p>
                    ))}
                  </div>
                  <p className="evaluation-status">{memoryReflectionStatus}</p>
                </section>
              ) : null}

              {activeMemoryView === "hits" ? (
                <section className="memory-panel memory-view-panel">
                  <h2>命中记忆</h2>
                  {memories.length === 0 ? (
                    <p className="empty">本轮暂无命中。发送一句和长期记忆相关的话后会显示检索结果。</p>
                  ) : (
                    memories.map((memory) => (
                      <article className="memory-item" key={memory.id}>
                        <span>{memory.kind}</span>
                        <strong>{memory.score.toFixed(2)}</strong>
                        <p>{memory.content}</p>
                      </article>
                    ))
                  )}
                </section>
              ) : null}

              {activeMemoryView === "audit" ? (
                <section className="audit-panel memory-view-panel">
                  <div className="panel-title-row">
                    <h2>记忆审计</h2>
                    <button
                      aria-label="刷新记忆审计"
                      className="icon-button"
                      onClick={() => void refreshMemoryAudits()}
                      title="刷新记忆审计"
                      type="button"
                    >
                      <RefreshCw size={15} />
                    </button>
                  </div>
                  {!extraction ? (
                    <p className="empty">本轮暂无审计。发送一句话后会显示抽取方法、候选记忆和接受/拒绝理由。</p>
                  ) : (
                    <>
                      <div className="audit-method">
                        <span>{extraction.method}</span>
                        {extraction.error ? <strong>fallback</strong> : null}
                      </div>
                      {extraction.decisions.length === 0 ? (
                        <p className="empty">本轮未提取长期记忆</p>
                      ) : (
                        extraction.decisions.map((decision) => (
                          <article className="audit-item" key={decision.audit_id ?? decision.candidate.content}>
                            <span className={decision.accepted ? "accepted" : "rejected"}>
                              {decision.accepted ? "accepted" : "rejected"}
                            </span>
                            <strong>{decision.candidate.kind}</strong>
                            <p>{decision.candidate.content}</p>
                            <small>{decision.reason}</small>
                          </article>
                        ))
                      )}
                    </>
                  )}
                  <div className="audit-history">
                    <h3>最近审计</h3>
                    <div className="audit-filter-row">
                      <select
                        onChange={(event) =>
                          setMemoryAuditFilter(event.target.value as typeof memoryAuditFilter)
                        }
                        value={memoryAuditFilter}
                      >
                        <option value="all">全部</option>
                        <option value="pending">待确认</option>
                        <option value="accepted">已写入</option>
                        <option value="rejected">已拒绝</option>
                      </select>
                      <input
                        onChange={(event) => setMemoryAuditSearch(event.target.value)}
                        onKeyDown={(event) => {
                          if (event.key === "Enter") {
                            void refreshMemoryAudits();
                          }
                        }}
                        placeholder="搜索审计"
                        value={memoryAuditSearch}
                      />
                      <button
                        className="text-button"
                        onClick={() => void refreshMemoryAudits()}
                        type="button"
                      >
                        <SearchCheck size={13} />
                        <span>查询</span>
                      </button>
                    </div>
                    <div className="audit-batch-row">
                      <button
                        className="text-button"
                        disabled={selectedAuditIds.length === 0 || batchAuditBusy}
                        onClick={() => void batchMemoryAudits("approve")}
                        type="button"
                      >
                        <ShieldCheck size={13} />
                        <span>批量批准</span>
                      </button>
                      <button
                        className="text-button danger"
                        disabled={selectedAuditIds.length === 0 || batchAuditBusy}
                        onClick={() => void batchMemoryAudits("reject")}
                        type="button"
                      >
                        <Trash2 size={13} />
                        <span>批量拒绝</span>
                      </button>
                    </div>
                    {memoryAudits.length === 0 ? (
                      <p className="empty">暂无审计记录</p>
                    ) : (
                      memoryAudits.map((audit) => {
                        const decision =
                          audit.decision ?? (audit.accepted || audit.memory_id ? "accepted" : "pending");
                        const pending = decision === "pending" && Boolean(audit.candidate);
                        return (
                          <article className="audit-item" key={audit.id}>
                            <span className={decision}>
                              {decision}
                            </span>
                            <strong>{audit.candidate?.kind ?? audit.method}</strong>
                            {pending ? (
                              <label className="audit-select">
                                <input
                                  checked={selectedAuditIds.includes(audit.id)}
                                  onChange={(event) =>
                                    toggleAuditSelection(audit.id, event.target.checked)
                                  }
                                  type="checkbox"
                                />
                                <em>选择</em>
                              </label>
                            ) : null}
                            {pending && audit.candidate ? (
                              <textarea
                                className="audit-edit"
                                onChange={(event) => updateAuditDraft(audit.id, event.target.value)}
                                rows={3}
                                value={auditDrafts[audit.id] ?? audit.candidate.content}
                              />
                            ) : (
                              <p>{audit.candidate?.content ?? audit.reason}</p>
                            )}
                            <small>{audit.reason}</small>
                            {pending ? (
                              <div className="audit-actions">
                                <button
                                  className="text-button"
                                  disabled={
                                    approvingAuditId === audit.id ||
                                    rejectingAuditId === audit.id ||
                                    batchAuditBusy
                                  }
                                  onClick={() => void approveMemoryAudit(audit)}
                                  type="button"
                                >
                                  {approvingAuditId === audit.id ? "批准中" : "批准写入"}
                                </button>
                                <button
                                  className="text-button danger"
                                  disabled={
                                    approvingAuditId === audit.id ||
                                    rejectingAuditId === audit.id ||
                                    batchAuditBusy
                                  }
                                  onClick={() => void rejectMemoryAudit(audit)}
                                  type="button"
                                >
                                  {rejectingAuditId === audit.id ? "拒绝中" : "拒绝"}
                                </button>
                              </div>
                            ) : null}
                          </article>
                        );
                      })
                    )}
                    {memoryAuditHasMore ? (
                      <button
                        className="text-button audit-more-button"
                        onClick={() => void refreshMemoryAudits(true)}
                        type="button"
                      >
                        加载更多
                      </button>
                    ) : null}
                    <p className="evaluation-status">{memoryAuditStatus}</p>
                  </div>
                </section>
              ) : null}

              {activeMemoryView === "versions" ? (
                <section className="snapshot-panel memory-view-panel">
                  <div className="panel-title-row">
                    <h2>名片版本</h2>
                    <div className="icon-button-row">
                      <button
                        aria-label="刷新名片版本"
                        className="icon-button"
                        onClick={() => void refreshMemoryCardSnapshots()}
                        title="刷新名片版本"
                        type="button"
                      >
                        <RefreshCw size={15} />
                      </button>
                      <button
                        aria-label="保存当前名片快照"
                        className="icon-button accent"
                        onClick={() => void createMemoryCardSnapshot()}
                        title="保存当前名片快照"
                        type="button"
                      >
                        <Save size={15} />
                      </button>
                    </div>
                  </div>

                  <div className="snapshot-list">
                    {memoryCardSnapshots.length === 0 ? (
                      <p className="empty">暂无版本快照</p>
                    ) : (
                      memoryCardSnapshots.map((snapshot) => (
                        <article
                          className={
                            memoryCardComparison?.snapshot.id === snapshot.id
                              ? "snapshot-item active"
                              : "snapshot-item"
                          }
                          key={snapshot.id}
                        >
                          <div>
                            <span>#{snapshot.id}</span>
                            <strong>{snapshot.label ?? "手动快照"}</strong>
                          </div>
                          <small>{formatSnapshotTime(snapshot.created_at)}</small>
                          <p>{snapshot.summary}</p>
                          <div className="snapshot-meta">
                            <span>{snapshot.memory_count} 条记忆</span>
                            <span>{snapshot.conversation_count} 条消息</span>
                            <button
                              className="text-button"
                              onClick={() => void compareMemoryCardSnapshot(snapshot.id)}
                              type="button"
                            >
                              对比
                            </button>
                          </div>
                        </article>
                      ))
                    )}
                  </div>

                  {memoryCardComparison ? (
                    <div className="snapshot-diff">
                      <div className="snapshot-diff-summary">
                        <span>新增 {memoryCardComparison.diff.added_count}</span>
                        <span>移除 {memoryCardComparison.diff.removed_count}</span>
                        <span>不变 {memoryCardComparison.diff.unchanged_count}</span>
                      </div>
                      {memoryCardComparison.diff.added_count === 0 &&
                      memoryCardComparison.diff.removed_count === 0 ? (
                        <p className="empty">当前名片与该快照一致</p>
                      ) : (
                        memoryCardComparison.diff.sections.map((section) =>
                          section.added.length || section.removed.length ? (
                            <article className="snapshot-diff-section" key={section.kind}>
                              <h3>{section.title}</h3>
                              {section.added.map((item) => (
                                <p className="added" key={`added-${section.kind}-${item.content}`}>
                                  + {item.content}
                                </p>
                              ))}
                              {section.removed.map((item) => (
                                <p className="removed" key={`removed-${section.kind}-${item.content}`}>
                                  - {item.content}
                                </p>
                              ))}
                            </article>
                          ) : null
                        )
                      )}
                    </div>
                  ) : null}
                  <p className="evaluation-status">{memoryCardVersionStatus}</p>
                </section>
              ) : null}
            </>
          ) : null}

          {activePanel === "debug" ? (
            <>
              <section className="evaluation-panel">
                <div className="panel-title-row">
                  <h2>评测埋点</h2>
                  <button
                    aria-label="刷新评测数据"
                    className="icon-button"
                    onClick={() => void refreshEvaluation()}
                    title="刷新评测数据"
                    type="button"
                  >
                    <RefreshCw size={15} />
                  </button>
                </div>
                <div className="metric-grid">
                  <div>
                    <span>对话</span>
                    <strong>{evaluationSummary?.chat.count ?? 0}</strong>
                  </div>
                  <div>
                    <span>平均延迟</span>
                    <strong>{formatMs(evaluationSummary?.chat.avg_latency_ms)}</strong>
                  </div>
                  <div>
                    <span>P95</span>
                    <strong>{formatMs(evaluationSummary?.chat.p95_latency_ms)}</strong>
                  </div>
                  <div>
                    <span>命中率</span>
                    <strong>{formatRate(evaluationSummary?.chat.memory_hit_rate)}</strong>
                  </div>
                  <div>
                    <span>心跳</span>
                    <strong>{evaluationSummary?.heartbeat.count ?? 0}</strong>
                  </div>
                  <div>
                    <span>触发率</span>
                    <strong>{formatRate(evaluationSummary?.heartbeat.fired_rate)}</strong>
                  </div>
                  <div>
                    <span>首播</span>
                    <strong>{formatMs(evaluationSummary?.avatar?.avg_first_play_ms)}</strong>
                  </div>
                  <div>
                    <span>口型</span>
                    <strong>{formatMs(evaluationSummary?.avatar?.avg_mouth_active_ms)}</strong>
                  </div>
                  <div>
                    <span>活跃率</span>
                    <strong>{formatRate(evaluationSummary?.avatar?.avg_mouth_active_ratio)}</strong>
                  </div>
                  <div>
                    <span>闭嘴</span>
                    <strong>{formatMs(evaluationSummary?.avatar?.avg_interrupt_to_silent_ms)}</strong>
                  </div>
                </div>
                <p className="evaluation-status">{evaluationStatus}</p>
                <div className="event-list">
                  {evaluationEvents.length === 0 ? (
                    <p className="empty">暂无评测事件</p>
                  ) : (
                    evaluationEvents.map((event) => (
                      <article className="event-item" key={event.id}>
                        <span>
                          <BarChart3 size={13} />
                          {formatEventType(event.event_type)}
                        </span>
                        <strong>{formatEventMetric(event)}</strong>
                        <p>{formatEventReason(event)}</p>
                      </article>
                    ))
                  )}
                </div>
              </section>

              <section className="settings-panel">
                <div className="panel-title-row">
                  <h2>运行细节</h2>
                  <ShieldCheck size={16} />
                </div>
                <div className="setting-row">
                  <span>后端</span>
                  <strong title={status}>{status}</strong>
                </div>
                <div className="setting-row">
                  <span>LLM 地址</span>
                  <strong title={config?.llm.chat_completions_url ?? "unknown"}>
                    {config?.llm.chat_completions_url ?? "unknown"}
                  </strong>
                </div>
                <div className="setting-row">
                  <span>TTS 模式</span>
                  <strong>{config?.tts.mode ?? "desktop speech"}</strong>
                </div>
                <div className="setting-row">
                  <span>TTS 状态</span>
                  <strong title={ttsServiceStatus?.error ?? ttsStatus}>
                    {formatTtsDebugStatus(ttsServiceStatus, speechSupported)}
                  </strong>
                </div>
                <div className="setting-row">
                  <span>STT 地址</span>
                  <strong title={config?.stt.transcriptions_url ?? "unknown"}>
                    {config?.stt.transcriptions_url ?? "unknown"}
                  </strong>
                </div>
                <div className="setting-row">
                  <span>STT 状态</span>
                  <strong title={sttServiceStatus?.error ?? sttStatus}>
                    {sttServiceStatus?.available ? "可用" : sttServiceStatus?.configured ? "未连接" : "未配置"}
                  </strong>
                </div>
                <div className="setting-row">
                  <span>数据库</span>
                  <strong title={config?.db_path ?? "unknown"}>{config?.db_path ?? "unknown"}</strong>
                </div>
              </section>

              <section className="settings-panel">
                <div className="panel-title-row">
                  <h2>节点拓扑</h2>
                  <button
                    aria-label="刷新节点状态"
                    className="icon-button"
                    onClick={() => void refreshNodeStatus()}
                    title="刷新节点状态"
                    type="button"
                  >
                    <RefreshCw size={15} />
                  </button>
                </div>
                <div className="setting-row">
                  <span>当前节点</span>
                  <strong title={nodeStatus?.node.name ?? "unknown"}>
                    {nodeStatus ? `${nodeStatus.node.name} / ${nodeStatus.node.role}` : "unknown"}
                  </strong>
                </div>
                <div className="setting-row">
                  <span>Peer</span>
                  <strong title={nodeStatus?.peer.error ?? nodeStatus?.peer.base_url ?? "未配置"}>
                    {nodeStatus?.peer.available
                      ? "可用"
                      : nodeStatus?.peer.configured
                        ? "不可用"
                        : "未配置"}
                  </strong>
                </div>
                <div className="setting-row">
                  <span>写入目标</span>
                  <strong title={nodeStatus?.memory_write_policy.note ?? "unknown"}>
                    {nodeStatus?.memory_write_policy.primary ?? "unknown"}
                  </strong>
                </div>
                <div className="setting-row">
                  <span>离线策略</span>
                  <strong>{nodeStatus?.memory_write_policy.offline_behavior ?? "unknown"}</strong>
                </div>
                <div className="setting-row">
                  <span>迁移状态</span>
                  <strong
                    className={
                      nodeStatus?.memory_write_policy.migration_ready ? "accepted" : "rejected"
                    }
                  >
                    {nodeStatus?.memory_write_policy.migration_ready ? "就绪" : "未就绪"}
                  </strong>
                </div>
                <div className="setting-row">
                  <span>推理路由</span>
                  <strong title={nodeStatus?.inference_route_policy.note ?? "unknown"}>
                    {nodeStatus?.inference_route_policy.primary ?? "unknown"}
                  </strong>
                </div>
                <div className="setting-row">
                  <span>Peer 超时</span>
                  <strong>{nodeStatus?.node.peer_timeout_seconds ?? "unknown"}s</strong>
                </div>
                <div className="setting-row">
                  <span>诊断目标</span>
                  <strong>{preferredPeerRole(nodeStatus)}</strong>
                </div>
                <div className="setting-row">
                  <span>扫描结果</span>
                  <strong title={peerScanStatus}>{peerScanStatus}</strong>
                </div>
                <div className="setting-row">
                  <span>配置写入</span>
                  <strong title={peerConfigStatus}>{peerConfigStatus}</strong>
                </div>
                <div className="setting-row">
                  <span>预热</span>
                  <strong title={prewarmStatus}>{prewarmStatus}</strong>
                </div>
                <div className="button-row">
                  <button
                    className="secondary-button"
                    disabled={peerScanBusy}
                    onClick={() => void diagnosePeerCandidates()}
                    type="button"
                  >
                    <SearchCheck size={17} />
                    <span>{peerScanBusy ? "诊断中" : "一键诊断"}</span>
                  </button>
                  <button
                    className="secondary-button"
                    disabled={!peerScan?.best || peerConfigBusy}
                    onClick={() => void applyRecommendedPeerConfig()}
                    type="button"
                  >
                    <Save size={17} />
                    <span>{peerConfigBusy ? "写入中" : "写入配置"}</span>
                  </button>
                  <button
                    className="secondary-button accent"
                    disabled={prewarmBusy}
                    onClick={() => void prewarmInference()}
                    type="button"
                  >
                    <Zap size={17} />
                    <span>{prewarmBusy ? "预热中" : "预热推理"}</span>
                  </button>
                </div>
                <p className="evaluation-status">{nodeStatusText}</p>
                {peerScan ? (
                  <div className="peer-scan-list">
                    {peerScan.results.map((item) => (
                      <div
                        className={`peer-scan-item ${item.health && item.status ? "ok" : "muted"}`}
                        key={item.base_url}
                        title={item.error ?? item.base_url}
                      >
                        <span>{item.base_url}</span>
                        <strong>{formatPeerScanResult(item)}</strong>
                      </div>
                    ))}
                  </div>
                ) : null}
                {nodeActionHint ? <p className="node-action-hint">{nodeActionHint}</p> : null}
              </section>

              <section className="heartbeat-panel">
                <div className="panel-title-row">
                  <h2>调试日志</h2>
                  <label className="debug-toggle inline">
                    <input
                      checked={showDebugLogs}
                      onChange={(event) => setShowDebugLogs(event.target.checked)}
                      type="checkbox"
                    />
                    <span>显示</span>
                  </label>
                </div>
                <div className="heartbeat-state">
                  <span>{lastHeartbeatAt ? `最近: ${lastHeartbeatAt}` : "尚未检查"}</span>
                  <strong className={lastHeartbeat?.fired ? "accepted" : "rejected"}>
                    {lastHeartbeat ? (lastHeartbeat.fired ? "已触发" : "未触发") : "待机"}
                  </strong>
                </div>
                <p>
                  {lastHeartbeat?.reason ?? "打开后会把未触发、通知失败等诊断信息写入对话流。"}
                  {` · 活动信号 ${lastActivitySignal}`}
                </p>
              </section>
            </>
          ) : null}

        </div>
      </aside>

      <section className="conversation">
        <section className={`avatar-stage ${avatarMode}`} aria-label="companion avatar">
          <Live2DAvatar
            blinking={avatarBlinking}
            fallbackMouthLevel={avatarMouthLevel}
            mode={avatarMode}
            mouthOpenY={lipSyncLive2DValue}
            onStatusChange={setLive2dStatus}
          />
          <div className="avatar-readout">
            <span>{formatAvatarMode(avatarMode)}</span>
            <strong>
              {voiceActive
                ? `lip ${lipSyncSource}`
                : live2dStatus === "ready"
                  ? "live2d"
                  : live2dStatus}
            </strong>
            <p>
              {formatAvatarDetail(avatarMode, ttsStatus, sttStatus)} · ParamMouthOpenY{" "}
              {lipSyncLive2DValue.toFixed(2)}
            </p>
          </div>
        </section>

        <div className="message-list" ref={messageListRef}>
          {messages.map((message, index) => (
            <article className={`message ${message.role}`} key={`${message.role}-${index}`}>
              <span>{message.role}</span>
              <p>{message.content}</p>
            </article>
          ))}
        </div>

        <form className="composer" onSubmit={submit}>
          <button
            aria-label={recording ? "stop recording" : "start recording"}
            className={recording ? "mic-button recording" : "mic-button"}
            disabled={!sttSupported || busy || transcribing || config?.stt.configured === false}
            onClick={() => void toggleRecording()}
            title={
              !sttSupported
                ? "当前环境不支持录音"
                : config?.stt.configured === false
                  ? "STT 未配置"
                  : sttStatus
            }
            type="button"
          >
            {recording ? <MicOff size={18} /> : <Mic size={18} />}
          </button>
          <input
            aria-label="message"
            disabled={busy || recording || transcribing}
            onChange={(event) => handleInputChange(event.target.value)}
            placeholder="输入一句话,测试记忆写入和检索"
            value={input}
          />
          <button aria-label="send" disabled={busy || !input.trim()} type="submit">
            <Send size={18} />
          </button>
          <p className={recording ? "composer-status recording" : "composer-status"}>
            {sttSupported ? sttStatus : "当前环境不支持录音"}
          </p>
        </form>
      </section>
    </main>
  );
}

async function fetchMemoryCardExport(format: MemoryCardExportFormat): Promise<MemoryCardExport> {
  const response = await fetch(
    `${backendBaseUrl}/memory-card/export?session_id=default&format=${format}`
  );
  if (!response.ok) {
    throw new Error(`Memory card export failed: ${response.status}`);
  }
  const content = await response.text();
  return {
    format,
    filename:
      filenameFromContentDisposition(response.headers.get("content-disposition")) ??
      defaultMemoryCardExportFilename(format),
    content,
    mime_type: response.headers.get("content-type") ?? defaultMemoryCardMimeType(format)
  };
}

function filenameFromContentDisposition(value: string | null) {
  const match = value?.match(/filename="?([^";]+)"?/i);
  return match?.[1] ?? null;
}

function defaultMemoryCardExportFilename(format: MemoryCardExportFormat) {
  return format === "json" ? "kanojo_memory_card_default.json" : "kanojo_memory_card_default.md";
}

function defaultMemoryCardMimeType(format: MemoryCardExportFormat) {
  return format === "json" ? "application/json;charset=utf-8" : "text/markdown;charset=utf-8";
}

function nextMemoryView(result: ChatResult): ActiveMemoryView {
  if (result.memory_extraction?.decisions.length) {
    return "audit";
  }
  if (result.memories?.length) {
    return "hits";
  }
  return "card";
}

async function copyTextToClipboard(text: string) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }
  const textArea = document.createElement("textarea");
  textArea.value = text;
  textArea.setAttribute("readonly", "true");
  textArea.style.position = "fixed";
  textArea.style.left = "-9999px";
  document.body.appendChild(textArea);
  textArea.select();
  const copied = document.execCommand("copy");
  document.body.removeChild(textArea);
  if (!copied) {
    throw new Error("Clipboard is unavailable");
  }
}

function preferredPeerRole(status: NodeStatus | null): PeerScanRole {
  return status?.node.role === "mac_home" ? "pc_inference" : "mac_home";
}

function buildPeerScanCandidates(status: NodeStatus | null) {
  return uniquePeerCandidates([
    status?.peer.base_url,
    status?.memory_write_policy.peer_base_url,
    status?.inference_route_policy.peer_base_url,
    status?.node.peer_base_url,
    ...defaultPeerScanCandidates
  ]);
}

function uniquePeerCandidates(candidates: Array<string | null | undefined>) {
  const seen = new Set<string>();
  const result: string[] = [];
  for (const candidate of candidates) {
    const normalized = normalizePeerCandidate(candidate);
    if (!normalized || seen.has(normalized)) {
      continue;
    }
    seen.add(normalized);
    result.push(normalized);
  }
  return result;
}

function normalizePeerCandidate(candidate: string | null | undefined) {
  return candidate?.trim().replace(/\/+$/, "") ?? "";
}

async function scanPeerCandidates(
  preferredRole: PeerScanRole,
  candidates: string[],
  timeoutMs: number
): Promise<PeerScanSummary> {
  const results = await Promise.all(
    uniquePeerCandidates(candidates).map(async (candidate, index) => {
      const item: PeerScanResult = {
        index,
        base_url: candidate,
        health: false,
        status: false,
        role: null,
        node_name: null,
        error: null
      };
      try {
        const health = await fetchJsonWithTimeout<{ status?: string }>(
          `${candidate}/health`,
          timeoutMs
        );
        item.health = health.status === "ok";
        const status = await fetchJsonWithTimeout<NodeStatus>(`${candidate}/node/status`, timeoutMs);
        item.status = true;
        item.role = status.node?.role ?? null;
        item.node_name = status.node?.name ?? null;
      } catch (error) {
        item.error = formatErrorMessage(error);
      }
      return item;
    })
  );

  const roleOrder =
    preferredRole === "pc_inference" ? ["pc_inference", "mac_home"] : ["mac_home", "pc_inference"];
  const available = results.filter((item) => item.health && item.status);
  const best =
    available.sort((left, right) => {
      const leftRank = roleOrder.indexOf(left.role ?? "");
      const rightRank = roleOrder.indexOf(right.role ?? "");
      return (
        (leftRank < 0 ? 99 : leftRank) - (rightRank < 0 ? 99 : rightRank) ||
        left.index - right.index
      );
    })[0] ?? null;

  return {
    preferred_role: preferredRole,
    best,
    results,
    checked_at: new Date().toISOString()
  };
}

async function fetchJsonWithTimeout<T>(url: string, timeoutMs: number): Promise<T> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(url, { signal: controller.signal });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    return response.json();
  } finally {
    window.clearTimeout(timeout);
  }
}

function formatErrorMessage(error: unknown) {
  if (error instanceof DOMException && error.name === "AbortError") {
    return "timeout";
  }
  return error instanceof Error ? error.message : "unreachable";
}

function downloadTextFile(result: MemoryCardExport) {
  const blob = new Blob([result.content], { type: result.mime_type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = result.filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

async function notifyViaBrowser(title: string, body: string) {
  if (!("Notification" in window)) {
    return { delivered: false, reason: "browser notifications unsupported" };
  }
  if (Notification.permission === "default") {
    await Notification.requestPermission();
  }
  if (Notification.permission !== "granted") {
    return { delivered: false, reason: `permission ${Notification.permission}` };
  }
  new Notification(title, { body });
  return { delivered: true };
}

function readNotificationState() {
  if (!("Notification" in window)) {
    return "unsupported";
  }
  return Notification.permission;
}

function formatMs(value: number | null | undefined) {
  return value === null || value === undefined ? "无" : `${value} ms`;
}

function formatPeerScanStatus(scan: PeerScanSummary | null) {
  if (!scan) {
    return "未诊断";
  }
  if (!scan.best) {
    return `未找到 ${scan.preferred_role}`;
  }
  return `${scan.best.role ?? "unknown"} · ${scan.best.base_url}`;
}

function formatPeerScanResult(item: PeerScanResult) {
  if (item.health && item.status) {
    return `${item.role ?? "unknown"} / ${item.node_name ?? "unknown"}`;
  }
  return item.error ?? "不可用";
}

function summarizeNodeAlert(status: NodeStatus | null): NodeAlert {
  if (!status) {
    return {
      level: "muted",
      title: "节点未刷新",
      detail: "等待拓扑状态"
    };
  }
  if (status.peer.configured && !status.peer.available) {
    return {
      level: "warning",
      title: "Peer 不可用",
      detail: status.peer.error ?? status.peer.base_url ?? "检查对端后端"
    };
  }
  if (status.memory_write_policy.primary === "peer" && !status.memory_write_policy.migration_ready) {
    return {
      level: "warning",
      title: "写回未就绪",
      detail: status.memory_write_policy.note
    };
  }
  if (
    status.node.role === "mac_home" &&
    status.inference_route_policy.primary === "auto" &&
    status.inference_route_policy.peer_inference_configured &&
    status.peer.available
  ) {
    return {
      level: "ok",
      title: "Mac 委托 PC",
      detail: "peer 推理可用"
    };
  }
  if (status.node.role === "pc_inference" && status.node.llm_configured) {
    return {
      level: status.peer.available ? "ok" : "muted",
      title: "PC 推理节点",
      detail: status.peer.available ? "记忆写回可用" : "本地推理可用"
    };
  }
  return {
    level: "muted",
    title: status.node.role,
    detail: status.inference_route_policy.note
  };
}

function summarizeNodeActionHint(status: NodeStatus | null) {
  if (!status) {
    return "先刷新节点状态,确认后端已启动。";
  }
  if (status.peer.configured && !status.peer.available) {
    if (status.node.role === "mac_home") {
      return "Mac peer 不可用时,先检查 PC 后端是否监听 0.0.0.0:8787、Windows 防火墙是否放行。";
    }
    return "PC peer 不可用时,先检查 Mac 后端 launchd 是否运行、Mac 8787 是否可从 PC 访问。";
  }
  if (status.memory_write_policy.primary === "peer" && !status.memory_write_policy.migration_ready) {
    return "写回未就绪时,检查 KANOJO_PEER_BASE_URL、KANOJO_MEMORY_PRIMARY=peer 和离线策略。";
  }
  if (
    status.node.role === "mac_home" &&
    status.inference_route_policy.primary === "auto" &&
    status.peer.available
  ) {
    return "演示前建议预热 PC peer,避免本地模型冷启动导致首次回退。";
  }
  if (status.node.role === "pc_inference" && status.peer.available) {
    return "当前 PC 可本地推理并写回 Mac,演示前可运行双机冒烟确认 Mac 委托链路。";
  }
  return "";
}

function formatRate(value: number | null | undefined) {
  return value === null || value === undefined ? "无" : `${Math.round(value * 100)}%`;
}

function formatSnapshotTime(value: string) {
  return new Date(value).toLocaleString([], {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  });
}

function payloadNumber(event: EvaluationEvent, key: string) {
  const value = event.payload[key];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function payloadText(event: EvaluationEvent, key: string) {
  const value = event.payload[key];
  return typeof value === "string" ? value : null;
}

function formatEventType(eventType: string) {
  const names: Record<string, string> = {
    chat: "对话",
    heartbeat: "心跳",
    avatar_voice_start: "形象首播",
    avatar_lip_sync: "口型活动",
    avatar_interrupt: "打断闭嘴"
  };
  return names[eventType] ?? eventType;
}

function formatEventMetric(event: EvaluationEvent) {
  if (event.event_type === "chat") {
    return `${formatMs(event.latency_ms)} · ${event.memory_hit_count} 条`;
  }
  if (event.event_type === "heartbeat") {
    return event.fired ? "已触发" : "未触发";
  }
  if (event.event_type === "avatar_voice_start") {
    return `${formatMs(event.latency_ms)} · 首播`;
  }
  if (event.event_type === "avatar_lip_sync") {
    return `${formatMs(payloadNumber(event, "active_ms"))} · ${formatRate(payloadNumber(event, "active_ratio"))}`;
  }
  if (event.event_type === "avatar_interrupt") {
    return `${formatMs(event.latency_ms)} · 闭嘴`;
  }
  return `#${event.id}`;
}

function formatEventReason(event: EvaluationEvent) {
  const time = new Date(event.created_at).toLocaleTimeString();
  if (event.event_type === "chat") {
    return `${time} · 新增记忆 ${event.created_memory_ids.length} 条`;
  }
  if (event.event_type === "avatar_voice_start") {
    const mode = payloadText(event, "mode") ?? "unknown";
    const channel = payloadText(event, "channel") ?? "unknown";
    const avatarModeLabel = payloadText(event, "avatar_mode") ?? "unknown";
    const textLength = payloadNumber(event, "text_length");
    return `${time} · ${mode} / ${channel} · ${avatarModeLabel} · ${textLength ?? 0} 字`;
  }
  if (event.event_type === "avatar_lip_sync") {
    const source = payloadText(event, "source") ?? "unknown";
    const channel = payloadText(event, "channel") ?? "unknown";
    const avatarModeLabel = payloadText(event, "avatar_mode") ?? "unknown";
    const maxLevel = payloadNumber(event, "max_mouth_level") ?? 0;
    return `${time} · ${source} / ${channel} · ${avatarModeLabel} · 峰值 ${maxLevel}`;
  }
  if (event.event_type === "avatar_interrupt") {
    const source = payloadText(event, "lip_sync_source_before") ?? "none";
    const mouthLevel = payloadNumber(event, "mouth_level_before") ?? 0;
    const avatarModeLabel = payloadText(event, "avatar_mode") ?? "unknown";
    return `${time} · ${event.reason ?? "无理由"} · ${avatarModeLabel} · ${source} / ${mouthLevel}`;
  }
  return `${time} · ${event.reason ?? "无理由"}`;
}

function formatAvatarMode(mode: AvatarMode) {
  if (mode === "speaking") return "说话中";
  if (mode === "listening") return "聆听中";
  if (mode === "thinking") return "思考中";
  if (mode === "interrupted") return "已打断";
  return "待机";
}

function formatAvatarDetail(mode: AvatarMode, ttsStatus: string, sttStatus: string) {
  if (mode === "listening") return sttStatus;
  if (mode === "thinking") return ttsStatus.includes("合成") ? ttsStatus : "正在处理当前回合";
  if (mode === "speaking") return ttsStatus;
  if (mode === "interrupted") return ttsStatus;
  return "等待下一次交互";
}

function formatTtsServiceStatus(status: TTSStatus, systemSpeechSupported: boolean) {
  if (!status.configured) {
    return systemSpeechSupported ? "系统语音待机" : "TTS 未配置";
  }
  if (!status.available) {
    return status.error ? `外部 TTS 未连接: ${status.error}` : "外部 TTS 未连接";
  }
  return status.health_supported === false ? "外部 TTS 待机 · 未提供 health" : "外部 TTS 待机";
}

function formatTtsDebugStatus(status: TTSStatus | null, systemSpeechSupported: boolean) {
  if (!status) return systemSpeechSupported ? "系统语音" : "unknown";
  if (!status.configured) return systemSpeechSupported ? "系统语音" : "未配置";
  if (status.available) return "外部可用";
  return "外部未连接";
}

function formatSpeechMode(mode: SpeechPlaybackMode) {
  if (mode === "stream") return "分句流式";
  if (mode === "replay") return "重播";
  if (mode === "reply") return "整段回复";
  return "待机";
}

function formatSttServiceStatus(status: STTStatus) {
  if (!status.configured) {
    return status.error ?? "STT 未配置";
  }
  if (!status.available) {
    return status.error ? `STT 服务未连接: ${status.error}` : "STT 服务未连接";
  }
  const detail = status.detail;
  if (detail?.model) {
    const loaded = detail.model_loaded ? "已加载" : "首次转写时加载";
    return `语音输入待机 · ${detail.model}/${detail.device ?? "device"} · ${loaded}`;
  }
  return "语音输入待机";
}

function formatSttResultStatus(result: STTResult) {
  const parts = [`已转写 · ${result.model ?? "STT"}`];
  if (result.latency_ms !== null && result.latency_ms !== undefined) {
    parts.push(`${result.latency_ms} ms`);
  }
  if (result.language) {
    parts.push(result.language);
  }
  return parts.join(" · ");
}

function splitSpeechSegments(text: string, flush: boolean) {
  const segments: string[] = [];
  let rest = text.replace(/\s+/g, " ").trimStart();
  const sentenceEnd = /[。！？!?；;\n]/;

  while (rest) {
    const match = sentenceEnd.exec(rest);
    if (!match || match.index < 0) break;
    const end = match.index + match[0].length;
    segments.push(rest.slice(0, end));
    rest = rest.slice(end).trimStart();
  }

  while (rest.length > 100) {
    const boundary = findSpeechBoundary(rest, 100);
    segments.push(rest.slice(0, boundary));
    rest = rest.slice(boundary).trimStart();
  }

  if (flush && rest.trim()) {
    segments.push(rest);
    rest = "";
  }

  return {
    segments: normalizeSpeechSegments(segments),
    rest
  };
}

function findSpeechBoundary(text: string, maxLength: number) {
  const slice = text.slice(0, maxLength);
  const boundaries = ["，", ",", "、", " "];
  for (const boundary of boundaries) {
    const index = slice.lastIndexOf(boundary);
    if (index >= 32) {
      return index + boundary.length;
    }
  }
  return maxLength;
}

function normalizeSpeechSegments(segments: string[]) {
  return segments.map((segment) => segment.trim()).filter(Boolean);
}

async function streamChatRequest(text: string, handlers: StreamHandlers) {
  const response = await fetch(`${backendBaseUrl}/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, session_id: "default", speak: false })
  });
  if (!response.ok) {
    throw new Error(`Stream request failed: ${response.status}`);
  }
  if (!response.body) {
    throw new Error("Streaming response is not available.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let doneResult: ChatResult | null = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let separatorIndex = findSseSeparator(buffer);
    while (separatorIndex !== -1) {
      const rawEvent = buffer.slice(0, separatorIndex);
      buffer = buffer.slice(separatorIndex + sseSeparatorLength(buffer, separatorIndex));
      const parsed = parseSseEvent(rawEvent);
      if (parsed.event === "meta") {
        handlers.onMeta?.(parsed.data as StreamMeta);
      } else if (parsed.event === "delta") {
        const data = parsed.data as { text?: string };
        if (data.text) {
          handlers.onDelta(data.text);
        }
      } else if (parsed.event === "done") {
        doneResult = parsed.data as ChatResult;
        handlers.onDone?.(doneResult);
      } else if (parsed.event === "error") {
        const data = parsed.data as { message?: string };
        throw new Error(data.message ?? "Streaming request failed.");
      }
      separatorIndex = findSseSeparator(buffer);
    }
  }

  if (!doneResult) {
    throw new Error("Streaming response ended before completion.");
  }
  return doneResult;
}

function findSseSeparator(buffer: string) {
  const lf = buffer.indexOf("\n\n");
  const crlf = buffer.indexOf("\r\n\r\n");
  if (lf === -1) return crlf;
  if (crlf === -1) return lf;
  return Math.min(lf, crlf);
}

function sseSeparatorLength(buffer: string, index: number) {
  return buffer.slice(index, index + 4) === "\r\n\r\n" ? 4 : 2;
}

function parseSseEvent(raw: string) {
  const lines = raw.replace(/\r\n/g, "\n").split("\n");
  let event = "message";
  const dataLines: string[] = [];
  for (const line of lines) {
    if (line.startsWith("event:")) {
      event = line.slice("event:".length).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice("data:".length).trimStart());
    }
  }
  const dataText = dataLines.join("\n");
  return {
    event,
    data: dataText ? JSON.parse(dataText) : {}
  };
}

async function synthesizeTts(text: string, signal?: AbortSignal): Promise<TTSResult> {
  const response = await fetch(`${backendBaseUrl}/tts/synthesize`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
    signal
  });
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const message =
      payload && typeof payload === "object" && "error" in payload
        ? String(payload.error)
        : `TTS request failed: ${response.status}`;
    throw new Error(message);
  }
  if (!payload) {
    throw new Error("TTS service returned empty response.");
  }
  return payload as TTSResult;
}

function ttsResultToAudioSource(result: TTSResult) {
  if (result.audio_base64) {
    const blob = base64ToBlob(result.audio_base64, result.content_type ?? "audio/wav");
    return { url: URL.createObjectURL(blob), revoke: true };
  }
  if (result.audio_url) {
    return { url: result.audio_url, revoke: false };
  }
  return null;
}

function base64ToBlob(base64: string, contentType: string) {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return new Blob([bytes], { type: contentType });
}

async function transcribeAudio(blob: Blob): Promise<STTResult> {
  const response = await fetch(`${backendBaseUrl}/stt/transcribe`, {
    method: "POST",
    headers: {
      "Content-Type": blob.type || "application/octet-stream",
      "X-Filename": recordingFilename(blob.type)
    },
    body: blob
  });
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const message =
      payload && typeof payload === "object" && "error" in payload
        ? String(payload.error)
        : `STT request failed: ${response.status}`;
    throw new Error(message);
  }
  if (!payload) {
    throw new Error("STT service returned empty response.");
  }
  return payload as STTResult;
}

function chooseRecordingMimeType() {
  const candidates = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"];
  return candidates.find((candidate) => MediaRecorder.isTypeSupported(candidate)) ?? "";
}

function recordingFilename(contentType: string) {
  if (contentType.includes("mp4")) return "recording.mp4";
  if (contentType.includes("webm")) return "recording.webm";
  return "recording.audio";
}
