import { contextBridge, ipcRenderer } from "electron";

const backendBaseUrl = "http://127.0.0.1:8787";

type EvaluationRecordRequest = {
  event_type: string;
  session_id?: string | null;
  source?: string | null;
  latency_ms?: number | null;
  reason?: string | null;
  payload?: Record<string, unknown>;
};

type ActivityEventRequest = {
  activity_type: string;
  source?: string | null;
  intensity?: number;
  note?: string | null;
};

type MemoryCardExportFormat = "markdown" | "json";

contextBridge.exposeInMainWorld("kanojoApi", {
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
  heartbeat: async (options?: { enabled?: boolean; force?: boolean; source?: string }) => {
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
  deactivateMemory: async (memoryId: number) => {
    const response = await fetch(`${backendBaseUrl}/memories/${memoryId}`, {
      method: "DELETE"
    });
    if (!response.ok) {
      throw new Error(`Memory deactivate request failed: ${response.status}`);
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
  notify: async (title: string, body: string) => {
    return ipcRenderer.invoke("kanojo:notify", { title, body });
  }
});

async function fetchMemoryCardExport(format: MemoryCardExportFormat) {
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
