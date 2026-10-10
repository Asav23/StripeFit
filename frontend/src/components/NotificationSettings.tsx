import { BellRing, Moon, Send, Sun } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { DailySettingsOut } from "../api/types";
import { useToast } from "../context";
import { SUPPORT_HINTS, currentSubscription, pushSupport, subscribe, unsubscribe } from "../lib/push";
import { Button, Notice, Switch } from "./ui";

type Which = "evening" | "morning";

/** Night-before and morning outfit notifications (Web Push). */
export default function NotificationSettings({
  settings,
  onChange,
}: {
  settings: DailySettingsOut;
  onChange: (s: DailySettingsOut) => void;
}) {
  const { notify, showError } = useToast();
  const [subscribed, setSubscribed] = useState(false);
  const [busy, setBusy] = useState<Which | "test" | null>(null);
  const support = pushSupport();

  useEffect(() => {
    currentSubscription()
      .then((s) => setSubscribed(!!s))
      .catch(() => undefined);
  }, []);

  const save = async (changes: Partial<DailySettingsOut>) => {
    const next = { ...settings, ...changes };
    onChange(
      await api.saveDailySettings({
        enabled: next.enabled,
        time: next.time,
        location: next.location,
        evening_enabled: next.evening_enabled,
        evening_time: next.evening_time,
      }),
    );
  };

  /** Make sure this browser can receive notifications. Returns false (with a message) if not. */
  const ensureSubscribed = async (): Promise<boolean> => {
    if (subscribed) return true;
    const config = await api.pushConfig();
    if (!config.configured || !config.public_key) {
      notify("Notifications aren't set up on the server yet.", "error", "Run python scripts/make_vapid_keys.py in backend/, then restart the API.");
      return false;
    }
    const subscription = await subscribe(config.public_key);
    if (!subscription) {
      notify("Notifications weren't allowed.", "error", "Allow notifications for this site in your browser, then try again.");
      return false;
    }
    await api.pushSubscribe(subscription);
    setSubscribed(true);
    return true;
  };

  const toggle = async (which: Which, on: boolean) => {
    setBusy(which);
    try {
      if (on && !(await ensureSubscribed())) return;
      const otherOn = which === "evening" ? settings.enabled : settings.evening_enabled;
      await save(which === "evening" ? { evening_enabled: on } : { enabled: on });
      if (!on && !otherOn) {
        const endpoint = await unsubscribe(); // nothing left to send to this browser
        if (endpoint) await api.pushUnsubscribe(endpoint);
        setSubscribed(false);
      }
      if (on) {
        const at = which === "evening" ? settings.evening_time : settings.time;
        notify(which === "evening" ? `Every evening at ${at} you'll get tomorrow's outfit.` : `Every morning at ${at} you'll get today's outfit.`, "success");
      }
    } catch (e) {
      showError(e);
    } finally {
      setBusy(null);
    }
  };

  const changeTime = (which: Which, value: string) => {
    if (!value) return;
    save(which === "evening" ? { evening_time: value } : { time: value }).catch(showError);
  };

  const sendTest = async () => {
    setBusy("test");
    try {
      if (!(await ensureSubscribed())) return;
      await api.pushTest();
      notify("Sent. Check your notifications for tomorrow's outfit.", "success");
    } catch (e) {
      showError(e);
    } finally {
      setBusy(null);
    }
  };

  const here = subscribed && support === "supported";
  const rows: { which: Which; icon: typeof Moon; title: string; hint: string; on: boolean; time: string }[] = [
    {
      which: "evening",
      icon: Moon,
      title: "Night before",
      hint: "Tomorrow's outfit and weather, so you can get it ready.",
      on: settings.evening_enabled && here,
      time: settings.evening_time,
    },
    { which: "morning", icon: Sun, title: "Morning", hint: "A reminder of today's outfit.", on: settings.enabled && here, time: settings.time },
  ];

  return (
    <section className="rounded-xl border border-line bg-card p-4 shadow-[var(--shadow-card)]" aria-labelledby="notify-title">
      <h2 id="notify-title" className="mb-3 flex items-center gap-2 text-[14px] font-semibold">
        <BellRing className="h-4 w-4 text-accent" /> Outfit notifications
      </h2>
      <ul className="divide-y divide-line">
        {rows.map(({ which, icon: Icon, title, hint, on, time }) => (
          <li key={which} className="py-3 first:pt-0 last:pb-0">
            <div className="flex items-center gap-2.5">
              <Icon className="h-4 w-4 shrink-0 text-ink-2" strokeWidth={1.75} />
              <p className="flex-1 text-[14px] font-medium">{title}</p>
              <Switch
                checked={on}
                onChange={(next) => toggle(which, next)}
                label={`${title} notification`}
                disabled={busy !== null || (support !== "supported" && !on)}
              />
            </div>
            <div className="mt-1.5 flex items-center gap-3 pl-[26px]">
              <p className="flex-1 text-[12px] leading-snug text-muted">{hint}</p>
              <input
                type="time"
                value={time}
                onChange={(e) => changeTime(which, e.target.value)}
                className="field h-8 w-[100px] shrink-0 px-2 py-0 text-[13px]"
                aria-label={`${title} notification time`}
              />
            </div>
          </li>
        ))}
      </ul>
      {support !== "supported" && <Notice tone="warn" className="mt-3">{SUPPORT_HINTS[support]}</Notice>}
      {support === "supported" && !subscribed && (settings.enabled || settings.evening_enabled) && (
        <p className="mt-2 text-[12px] text-muted">Notifications are on for another browser. Switch them on here too to get them on this device.</p>
      )}
      {here && (settings.enabled || settings.evening_enabled) && (
        <Button variant="secondary" size="sm" className="mt-3 w-full" onClick={sendTest} loading={busy === "test"}>
          {busy !== "test" && <Send className="h-3.5 w-3.5" />}
          Send a test now
        </Button>
      )}
    </section>
  );
}
