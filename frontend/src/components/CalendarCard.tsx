import { CalendarDays, Link2, Lock, Unlink } from "lucide-react";
import { useState } from "react";
import { api } from "../api/client";
import type { CalendarStatus } from "../api/types";
import { useToast } from "../context";
import { Button } from "./ui";

/** Connect Google Calendar (read-only) so tomorrow's outfit is planned around your day. */
export default function CalendarCard({ status, onChange }: { status: CalendarStatus; onChange: () => void }) {
  const { notify, showError } = useToast();
  const [busy, setBusy] = useState(false);

  const connect = async () => {
    setBusy(true);
    try {
      window.location.href = (await api.calendarAuthUrl()).url; // Google consent screen, then back to /today
    } catch (e) {
      showError(e);
      setBusy(false);
    }
  };

  const disconnect = async () => {
    setBusy(true);
    try {
      await api.calendarDisconnect();
      notify("Google Calendar disconnected. Outfits are back to casual days.", "info");
      onChange();
    } catch (e) {
      showError(e);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="rounded-xl border border-line bg-card p-4 shadow-[var(--shadow-card)]" aria-labelledby="calendar-title">
      <h2 id="calendar-title" className="mb-1 flex items-center gap-2 text-[14px] font-semibold">
        <CalendarDays className="h-4 w-4 text-accent" /> Google Calendar
        {status.connected && <span className="tag ml-auto bg-ok-soft text-ok">Connected</span>}
        {!status.connected && status.demo && <span className="tag ml-auto bg-warn-soft text-warn">Demo events</span>}
      </h2>
      <p className="mb-3 text-[12.5px] leading-snug text-ink-2">
        {status.connected
          ? "Your outfit dresses for your most important event, with tips for anything else that day."
          : "Connect it and the outfit dresses for what's actually on: an interview, lectures, football later."}
      </p>
      {status.connected ? (
        <Button variant="secondary" size="sm" className="w-full" onClick={disconnect} loading={busy}>
          {!busy && <Unlink className="h-3.5 w-3.5" />} Disconnect
        </Button>
      ) : status.configured ? (
        <Button size="sm" className="w-full" onClick={connect} loading={busy}>
          {!busy && <Link2 className="h-3.5 w-3.5" />} Connect Google Calendar
        </Button>
      ) : (
        <p className="rounded-md bg-sunk px-3 py-2 text-[12px] leading-snug text-muted">
          Not set up on the server yet: add the Google OAuth client to <code>backend/.env</code>
          {status.demo ? ". Demo events are on (AI log page)." : ", or turn on demo events on the AI log page."}
        </p>
      )}
      <p className="mt-3 flex items-start gap-1.5 text-[11.5px] leading-snug text-muted">
        <Lock className="mt-0.5 h-3 w-3 shrink-0" />
        Read-only. Event names stay on this screen: they're never saved or sent to the AI.
      </p>
    </section>
  );
}
