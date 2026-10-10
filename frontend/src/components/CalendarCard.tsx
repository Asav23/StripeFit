import { CalendarDays, ChevronDown, Link2, Lock, Unlink } from "lucide-react";
import { useState } from "react";
import { api } from "../api/client";
import type { CalendarStatus } from "../api/types";
import { useToast } from "../context";
import { Button } from "./ui";

const SOURCE_TAG: Record<string, { label: string; className: string }> = {
  google: { label: "Connected", className: "bg-ok-soft text-ok" },
  link: { label: "Connected by link", className: "bg-ok-soft text-ok" },
  demo: { label: "Demo events", className: "bg-warn-soft text-warn" },
};

/** Connect a calendar so the outfit is planned around your day: a private iCal link (no setup) or Google sign-in. */
export default function CalendarCard({ status, onChange }: { status: CalendarStatus; onChange: () => void }) {
  const { notify, showError } = useToast();
  const [busy, setBusy] = useState<"google" | "link" | "remove" | null>(null);
  const [url, setUrl] = useState("");
  const [showHelp, setShowHelp] = useState(!status.link && !status.connected);

  const signIn = async () => {
    setBusy("google");
    try {
      window.location.href = (await api.calendarAuthUrl()).url; // Google consent screen, then back to /today
    } catch (e) {
      showError(e);
      setBusy(null);
    }
  };

  const saveLink = async () => {
    if (!url.trim()) return;
    setBusy("link");
    try {
      const result = await api.calendarSaveLink(url.trim());
      setUrl("");
      notify(`Calendar linked (${result.events} events found). Your outfits now plan around your day.`, "success",
        status.demo ? "Demo events are still on: switch the AI log's calendar back to “Real calendar”." : undefined);
      onChange();
    } catch (e) {
      showError(e);
    } finally {
      setBusy(null);
    }
  };

  const disconnect = async () => {
    setBusy("remove");
    try {
      if (status.connected) await api.calendarDisconnect();
      if (status.link) await api.calendarRemoveLink();
      notify("Calendar disconnected. Outfits are back to casual days.", "info");
      onChange();
    } catch (e) {
      showError(e);
    } finally {
      setBusy(null);
    }
  };

  const tag = status.source ? SOURCE_TAG[status.source] : null;
  const linked = status.connected || status.link;

  return (
    <section className="rounded-xl border border-line bg-card p-4 shadow-[var(--shadow-card)]" aria-labelledby="calendar-title">
      <h2 id="calendar-title" className="mb-1 flex items-center gap-2 text-[14px] font-semibold">
        <CalendarDays className="h-4 w-4 text-accent" /> Your calendar
        {tag && <span className={`tag ml-auto ${tag.className}`}>{tag.label}</span>}
      </h2>
      <p className="mb-3 text-[12.5px] leading-snug text-ink-2">
        {linked
          ? "Your outfit dresses for your most important event, with tips for anything else that day."
          : "Link it and the outfit dresses for what's actually on: an interview, lectures, football later."}
      </p>

      {linked ? (
        <Button variant="secondary" size="sm" className="w-full" onClick={disconnect} loading={busy === "remove"}>
          {busy !== "remove" && <Unlink className="h-3.5 w-3.5" />} Disconnect calendar
        </Button>
      ) : (
        <div className="space-y-2.5">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void saveLink();
            }}
            className="space-y-2"
          >
            <label htmlFor="ical-link" className="block text-[12.5px] font-medium">
              Paste your private calendar link
            </label>
            <input
              id="ical-link"
              type="url"
              inputMode="url"
              autoComplete="off"
              spellCheck={false}
              placeholder="https://calendar.google.com/calendar/ical/…/basic.ics"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              className="field h-9 text-[12.5px]"
            />
            <Button type="submit" size="sm" className="w-full" loading={busy === "link"} disabled={!url.trim()}>
              {busy !== "link" && <Link2 className="h-3.5 w-3.5" />} Link calendar
            </Button>
          </form>

          <button
            type="button"
            onClick={() => setShowHelp((v) => !v)}
            aria-expanded={showHelp}
            className="flex w-full items-center gap-1 text-[12px] font-medium text-accent"
          >
            Where do I find it?
            <ChevronDown className={`h-3.5 w-3.5 transition ${showHelp ? "rotate-180" : ""}`} />
          </button>
          {showHelp && (
            <ol className="list-decimal space-y-1 rounded-md bg-sunk py-2.5 pl-8 pr-3 text-[12px] leading-snug text-ink-2">
              <li>
                Open <strong>Google Calendar</strong> on a computer, then the gear icon → <strong>Settings</strong>.
              </li>
              <li>On the left, under “Settings for my calendars”, click your calendar.</li>
              <li>
                Scroll to <strong>Integrate calendar</strong> and copy <strong>“Secret address in iCal format”</strong>.
              </li>
              <li>Paste it above. (Outlook and iCloud “publish” links work too.)</li>
            </ol>
          )}

          {status.configured && (
            <Button variant="ghost" size="sm" className="w-full" onClick={signIn} loading={busy === "google"}>
              Or sign in with Google
            </Button>
          )}
        </div>
      )}

      <p className="mt-3 flex items-start gap-1.5 text-[11.5px] leading-snug text-muted">
        <Lock className="mt-0.5 h-3 w-3 shrink-0" />
        Read-only. The link is kept private on this computer, and event names are never saved or sent to the AI.
      </p>
    </section>
  );
}
