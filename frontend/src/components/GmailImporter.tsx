import { Check, Mail } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import type { GmailStatus } from "../api/types";
import { useMe, useToast } from "../context";
import IngestResults from "./IngestResults";
import { Button, Notice, Skeleton } from "./ui";

const POLL_MS = 1500;

export default function GmailImporter() {
  const { refresh: refreshMe } = useMe();
  const { showError } = useToast();
  const [status, setStatus] = useState<GmailStatus | null>(null);
  const [months, setMonths] = useState(12);
  const [busy, setBusy] = useState(false);
  const poller = useRef<number | null>(null);

  const load = useCallback(async () => {
    try {
      const s = await api.gmailStatus();
      setStatus(s);
      return s;
    } catch (e) {
      showError(e);
      return null;
    }
  }, [showError]);

  const stopPolling = () => {
    if (poller.current) window.clearInterval(poller.current);
    poller.current = null;
  };

  const startPolling = useCallback(() => {
    stopPolling();
    poller.current = window.setInterval(async () => {
      try {
        const job = await api.gmailImportStatus();
        setStatus((s) => (s ? { ...s, job } : s));
        if (!job.running) {
          stopPolling();
          void refreshMe();
        }
      } catch {
        stopPolling();
      }
    }, POLL_MS);
  }, [refreshMe]);

  useEffect(() => {
    load().then((s) => s?.job.running && startPolling());
    return stopPolling;
  }, [load, startPolling]);

  const connect = async () => {
    setBusy(true);
    try {
      const { url } = await api.gmailAuthUrl();
      window.location.href = url;
    } catch (e) {
      showError(e);
      setBusy(false);
    }
  };

  const disconnect = async () => {
    setBusy(true);
    try {
      await api.gmailDisconnect();
      await load();
    } catch (e) {
      showError(e);
    } finally {
      setBusy(false);
    }
  };

  const startImport = async () => {
    setBusy(true);
    try {
      const { job } = await api.gmailImport(months);
      setStatus((s) => (s ? { ...s, job } : s));
      startPolling();
    } catch (e) {
      showError(e);
    } finally {
      setBusy(false);
    }
  };

  if (!status) return <Skeleton className="h-48" />;

  const promises = (
    <ul className="space-y-2 text-[13px] text-ink-2">
      {[
        "Read-only: StripeFit can't send, delete or change anything.",
        "Only order emails (orders, dispatch, delivery, refunds) from known clothing shops.",
        `Only the last ${months} months, up to 100 emails.`,
        "Personal details are removed before the AI reads an email. Email bodies are never stored.",
      ].map((t) => (
        <li key={t} className="flex gap-2">
          <Check className="mt-0.5 h-3.5 w-3.5 shrink-0 text-ok" strokeWidth={2.5} />
          {t}
        </li>
      ))}
    </ul>
  );

  const job = status.job;
  const progress = job.total ? Math.round((job.done / job.total) * 100) : 0;

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_280px]">
      <div className="space-y-4">
        {!status.configured ? (
          <Notice tone="warn">
            <p className="font-medium">Gmail import isn't set up on this server yet.</p>
            <p className="mt-0.5 text-ink-2">
              It needs Google OAuth keys (GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in backend/.env). Meanwhile, upload order emails on the
              Order emails tab.
            </p>
          </Notice>
        ) : !status.connected ? (
          <div className="flex flex-col items-start gap-4 rounded-lg border border-line bg-card p-6">
            <span className="grid h-11 w-11 place-items-center rounded-full bg-sunk">
              <Mail className="h-5 w-5" strokeWidth={1.5} />
            </span>
            <div>
              <h3 className="display text-[28px]">Let your inbox fill your wardrobe</h3>
              <p className="mt-1 text-sm text-ink-2">Connect once; import whenever you've bought something new.</p>
            </div>
            <Button onClick={connect} loading={busy}>
              Connect Gmail
            </Button>
          </div>
        ) : (
          <div className="space-y-4 rounded-lg border border-line bg-card p-5">
            <div className="flex items-center justify-between gap-3">
              <p className="flex items-center gap-2 text-sm font-medium">
                <span className="h-2 w-2 rounded-full bg-ok" /> Gmail connected (read-only)
              </p>
              <button onClick={disconnect} className="text-[13px] text-muted underline-offset-4 hover:text-ink hover:underline" disabled={busy}>
                Disconnect
              </button>
            </div>
            <div className="flex gap-2">
              <select className="field h-10 py-0" value={months} onChange={(e) => setMonths(Number(e.target.value))} disabled={job.running} aria-label="How far back">
                {[3, 6, 12, 24].map((m) => (
                  <option key={m} value={m}>
                    Last {m} months
                  </option>
                ))}
              </select>
              <Button onClick={startImport} loading={busy || job.running} className="shrink-0">
                {job.running ? "Importing" : "Import orders"}
              </Button>
            </div>
            {job.running && (
              <div className="space-y-1.5" aria-live="polite">
                <div className="h-1 overflow-hidden rounded-full bg-line">
                  <div className="h-full bg-ink transition-all duration-500" style={{ width: `${progress}%` }} />
                </div>
                <p className="font-mono text-[11px] text-muted">
                  {job.total ? `${job.done} / ${job.total} emails` : "Searching for order emails…"}
                </p>
              </div>
            )}
            {job.error && <Notice tone="error">{job.error}</Notice>}
          </div>
        )}
        {!job.running && job.summary && (
          <>
            {job.already_imported > 0 && <p className="text-xs text-muted">{job.already_imported} emails were imported before and skipped.</p>}
            <IngestResults summary={job.summary} />
          </>
        )}
      </div>
      <aside className="h-fit rounded-lg border border-line p-4">
        <p className="mb-3 text-[13px] font-medium">What StripeFit reads</p>
        {promises}
      </aside>
    </div>
  );
}
