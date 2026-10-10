import type {
  AICallLog,
  GmailJob,
  GmailStatus,
  IngestSummary,
  Item,
  ItemEdit,
  Me,
  Outfit,
  PhotoResult,
  PlanResponse,
  Purchase,
  ReviewItem,
  Slot,
  Status,
} from "./types";

/** Every API failure becomes one of these, with a message that is safe to show. */
export class ApiError extends Error {
  code: string;
  status: number;
  nextStep?: string;
  detail: Record<string, unknown>;

  constructor(code: string, status: number, message: string, nextStep?: string, detail: Record<string, unknown> = {}) {
    super(message);
    this.code = code;
    this.status = status;
    this.nextStep = nextStep;
    this.detail = detail;
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, init);
  } catch {
    throw new ApiError("network", 0, "Can't reach the StripeFit server.", "Check your connection and that the backend is running.");
  }
  if (response.status === 204) return undefined as T;
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = body?.detail;
    if (detail && typeof detail === "object" && "message" in detail) {
      throw new ApiError(detail.code ?? "error", response.status, detail.message, detail.next_step, detail);
    }
    throw new ApiError("error", response.status, "Something went wrong.", "Please try again.");
  }
  return body as T;
}

const json = (method: string, data?: unknown): RequestInit => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: data === undefined ? undefined : JSON.stringify(data),
});

function form(files: File[], field = "files"): RequestInit {
  const body = new FormData();
  files.forEach((f) => body.append(field, f));
  return { method: "POST", body };
}

export const api = {
  health: () => request<{ ok: boolean; mock_ai: boolean }>("/api/health"),
  me: () => request<Me>("/api/me"),

  // wardrobe
  items: (params: { status?: string; category?: string } = {}) => {
    const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v) as [string, string][]);
    return request<Item[]>(`/api/items${qs.size ? `?${qs}` : ""}`);
  },
  createItem: (data: ItemEdit & { name: string; category: string }) => request<Item>("/api/items", json("POST", data)),
  updateItem: (id: number, data: ItemEdit) => request<Item>(`/api/items/${id}`, json("PATCH", data)),
  deleteItem: (id: number) => request<void>(`/api/items/${id}`, { method: "DELETE" }),
  bulkDelete: (ids: number[]) => request<{ deleted: number }>("/api/items/bulk-delete", json("POST", { ids })),
  setStatus: (id: number, status: Status) => request<Item>(`/api/items/${id}/status`, json("POST", { status })),
  washWorn: () => request<{ updated: number }>("/api/items/wash-worn", json("POST")),
  laundryDone: () => request<{ updated: number }>("/api/items/laundry-done", json("POST")),
  replacePhoto: (id: number, file: File) => request<Item>(`/api/items/${id}/photo`, form([file], "file")),

  // adding + review
  uploadPhotos: (files: File[]) => request<PhotoResult[]>("/api/ingest/photo", form(files)),
  ingestEmails: (files: File[]) => request<IngestSummary>("/api/ingest/email", form(files)),
  ingestSamples: () => request<IngestSummary>("/api/ingest/samples", json("POST")),
  review: () => request<ReviewItem[]>("/api/review"),
  confirm: (id: number, data: ItemEdit & { duplicate_decision?: "merge" | "keep_both"; merge_target_id?: number }) =>
    request<{ item: Item; merged: boolean }>(`/api/review/${id}/confirm`, json("POST", data)),
  reject: (id: number) => request<void>(`/api/review/${id}/reject`, json("POST")),

  // outfits
  plan: (request_text: string) => request<PlanResponse>("/api/outfits/plan", json("POST", { request_text })),
  outfits: () => request<Outfit[]>("/api/outfits"),
  swap: (id: number, slot: Slot) => request<Outfit>(`/api/outfits/${id}/swap`, json("POST", { slot })),
  wear: (id: number) => request<Outfit>(`/api/outfits/${id}/wear`, json("POST")),
  feedback: (id: number, feedback: "up" | "down" | null) =>
    request<Outfit>(`/api/outfits/${id}/feedback`, json("POST", { feedback })),

  // pro
  checkout: () => request<{ url: string }>("/api/stripe/checkout", json("POST")),
  stripeSession: (id: string) =>
    request<{ paid: boolean; payment_status: string; purchase: Purchase | null }>(`/api/stripe/session/${encodeURIComponent(id)}`),
  demoCheckout: () => request<{ session_id: string }>("/api/stripe/demo/complete", json("POST")),
  resetPremium: () => request<{ premium: boolean }>("/api/debug/reset-premium", json("POST")),

  // gmail
  gmailStatus: () => request<GmailStatus>("/api/gmail/status"),
  gmailAuthUrl: () => request<{ url: string }>("/api/gmail/auth-url"),
  gmailDisconnect: () => request<{ connected: boolean }>("/api/gmail/disconnect", json("POST")),
  gmailImport: (months: number) => request<{ started: boolean; job: GmailJob }>("/api/gmail/import", json("POST", { months })),
  gmailImportStatus: () => request<GmailJob>("/api/gmail/import/status"),

  // debug / demo controls
  aiCalls: () => request<AICallLog>("/api/debug/ai-calls"),
  weatherOverride: () => request<{ preset: string | null; presets: string[] }>("/api/debug/weather-override"),
  setWeatherOverride: (preset: string | null) =>
    request<{ preset: string | null }>("/api/debug/weather-override", json("POST", { preset })),
  mockOverrides: () => request<{ overrides: Record<string, string> }>("/api/debug/mock-override"),
  setMockOverride: (task: string, variant: string | null) =>
    request<{ overrides: Record<string, string> }>("/api/debug/mock-override", json("POST", { task, variant })),
};
