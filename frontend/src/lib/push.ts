// Browser side of the outfit notifications: service worker + Web Push subscription.

export type PushSupport = "supported" | "unsupported" | "insecure" | "denied";

export function pushSupport(): PushSupport {
  if (!window.isSecureContext) return "insecure"; // push needs https or localhost
  if (!("serviceWorker" in navigator) || !("PushManager" in window) || !("Notification" in window)) return "unsupported";
  if (Notification.permission === "denied") return "denied";
  return "supported";
}

export const SUPPORT_HINTS: Record<Exclude<PushSupport, "supported">, string> = {
  insecure: "Notifications need https or localhost. Open the app at http://localhost:5173.",
  unsupported: "This browser can't show notifications. On iPhone, add StripeFit to your Home Screen first.",
  denied: "Notifications are blocked for this site. Allow them in your browser's site settings, then reload.",
};

function keyBytes(base64url: string): Uint8Array {
  const padded = (base64url + "=".repeat((4 - (base64url.length % 4)) % 4)).replace(/-/g, "+").replace(/_/g, "/");
  return Uint8Array.from(atob(padded), (c) => c.charCodeAt(0));
}

async function registration(): Promise<ServiceWorkerRegistration> {
  await navigator.serviceWorker.register("/sw.js");
  return navigator.serviceWorker.ready;
}

/** Ask permission and subscribe this browser. Returns null if the user said no. */
export async function subscribe(publicKey: string): Promise<PushSubscriptionJSON | null> {
  const permission = await Notification.requestPermission();
  if (permission !== "granted") return null;
  const reg = await registration();
  const existing = await reg.pushManager.getSubscription();
  const sub =
    existing ??
    (await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: keyBytes(publicKey) as BufferSource }));
  return sub.toJSON();
}

/** This browser's current subscription, if any (never prompts). */
export async function currentSubscription(): Promise<PushSubscription | null> {
  if (pushSupport() !== "supported") return null;
  const reg = await navigator.serviceWorker.getRegistration("/sw.js");
  return reg ? reg.pushManager.getSubscription() : null;
}

export async function unsubscribe(): Promise<string | null> {
  const sub = await currentSubscription();
  if (!sub) return null;
  await sub.unsubscribe();
  return sub.endpoint;
}
