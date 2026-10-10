export type Category = "top" | "bottom" | "one_piece" | "outerwear" | "shoes" | "accessory" | "sportswear" | "unknown";
export type Owner = "me" | "child" | "other" | "unknown";
export type Status = "available" | "worn" | "in_wash" | "unavailable" | "on_the_way" | "returned";
export type Slot = "top" | "bottom" | "one_piece" | "outerwear" | "shoes" | "accessory";

export interface Item {
  id: number;
  name: string;
  image_url: string | null;
  thumb_url: string | null;
  has_real_photo: boolean;
  category: Category;
  colours: string[];
  formality: number | null;
  warmth: number | null;
  waterproof: boolean | null;
  material: string | null;
  owner: Owner;
  status: Status;
  confirmed: boolean;
  confidence: number | null;
  notes: string | null;
  source: "photo" | "email" | "gmail" | "manual";
  source_ref: string | null;
  retailer: string | null;
  size: string | null;
  price: number | null;
  currency: string | null;
  last_worn: string | null;
  created_at: string;
}

export type ItemEdit = Partial<
  Pick<Item, "name" | "category" | "colours" | "formality" | "warmth" | "waterproof" | "material" | "owner" | "status" | "retailer" | "size">
>;

export interface Duplicate {
  item: Item;
  level: "definite" | "likely" | "possible";
  reason: string;
}

export interface ReviewItem extends Item {
  duplicate: Duplicate | null;
  missing_fields: string[];
  low_confidence: boolean;
  prompt: string | null;
}

export interface Purchase {
  stripe_session_id: string;
  amount_total: number | null;
  currency: string | null;
  status: string;
  created_at: string;
}

export interface Me {
  premium: boolean;
  premium_since: string | null;
  confirmed_item_count: number;
  pending_count: number;
  item_limit: number | null;
  mock_ai: boolean;
  stripe_configured: boolean;
  gmail_configured: boolean;
  latest_purchase: Purchase | null;
}

export interface Weather {
  location_name: string;
  time: string;
  temperature_c: number;
  precipitation_probability: number | null;
  precipitation_mm: number | null;
  wind_kmh: number | null;
  weather_code: number | null;
  description: string;
  icon: string;
  is_wet: boolean;
  // Across the whole event (missing on older outfits):
  window_hours?: number | null;
  temperature_min_c?: number | null;
  temperature_max_c?: number | null;
  precipitation_probability_max?: number | null;
  rain_from?: string | null;
}

export interface ParsedRequest {
  occasion: string;
  occasion_detail: string | null;
  destination: string | null;
  datetime_iso: string;
  travel_mode: string;
  dress_code: string | null;
  parse_fallback?: boolean;
}

export interface Outfit {
  id: number;
  request_text: string;
  parsed: ParsedRequest;
  weather: Weather | null;
  slots: { slot: Slot; item: Item }[];
  explanation: string;
  gaps: string[];
  notices: string[];
  used_fallback: boolean;
  feedback: "up" | "down" | null;
  worn: boolean;
  created_at: string;
  kind: "plan" | "daily";
  for_date: string | null;
}

export type Day = "today" | "tomorrow";

export interface DayEvent {
  title: string;
  start: string;
  end: string;
  all_day: boolean;
  location: string | null;
  occasion: string | null; // null = says nothing about clothes (e.g. "Dentist")
}

export interface DailySettings {
  enabled: boolean; // morning notification
  time: string; // "HH:MM", Europe/Dublin
  location: string | null;
  evening_enabled: boolean; // night-before notification
  evening_time: string;
}

export interface DailySettingsOut extends DailySettings {
  push_configured: boolean;
  subscriptions: number;
  last_sent_date: string | null;
  evening_last_sent: string | null;
  calendar_connected: boolean;
}

export interface DailyResponse {
  day: string;
  outfit: Outfit;
  events: DayEvent[];
  settings: DailySettingsOut;
}

export interface CalendarStatus {
  configured: boolean; // Google sign-in is set up on the server
  connected: boolean; // signed in with Google
  link: boolean; // a private iCal link is saved
  demo: boolean;
  source: "demo" | "google" | "link" | null; // what the planner uses
}

export interface PushConfig {
  configured: boolean;
  public_key: string | null;
}

export interface StylePreferences {
  favourite_colours: string[];
  avoid_colours: string[];
  style_notes: string | null;
}

export interface StyleProfile {
  occasion: string;
  stated: StylePreferences;
  learned: {
    liked_colours: string[];
    disliked_colours: string[];
    loved_item_ids: number[];
    avoided_item_ids: number[];
    lean_for_this_occasion: string | null;
  };
  liked_outfits: Record<string, string>[];
  signals: number;
}

export interface DemoEvent {
  title: string;
  start: string;
  end?: string;
  location?: string;
}

export interface PlanResponse {
  outfit: Outfit | null;
  clarification: string | null;
}

export interface PhotoResult {
  filename: string;
  ok: boolean;
  item: Item | null;
  message: string;
}

export interface FileIngestResult {
  filename: string;
  email_type: string | null;
  retailer: string | null;
  order_id: string | null;
  items_created: number;
  items_updated: number;
  items_skipped: number;
  notes: string[];
}

export interface IngestSummary {
  files: FileIngestResult[];
  items_created: number;
  items_updated: number;
  skipped: Record<string, number>;
  summary: string;
}

export interface EmailJob {
  id: string;
  running: boolean;
  total: number;
  done: number;
  error: string | null;
  results: FileIngestResult[];
  summary: IngestSummary | null;
}

export interface GmailJob {
  running: boolean;
  total: number;
  done: number;
  already_imported: number;
  error: string | null;
  results: FileIngestResult[];
  summary: IngestSummary | null;
}

export interface GmailStatus {
  configured: boolean;
  connected: boolean;
  job: GmailJob;
}

export interface AICallRow {
  id: number;
  task: string;
  model: string;
  latency_ms: number;
  prompt_tokens: number | null;
  completion_tokens: number | null;
  cost: number | null;
  success: boolean;
  error: string | null;
  created_at: string;
}

export interface AICallLog {
  calls: AICallRow[];
  totals: { count: number; failures: number; cost: number; avg_latency_ms: number };
  mock_ai: boolean;
  models: Record<string, [string, string[]]>;
}
