import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import type { GmailStatus } from "../api/types";
import { useMe, useToast } from "../context";
import IngestResults from "./IngestResults";
import { Button, Notice, Skeleton, inputClass } from "./ui";

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

  if (!status) return <Skeleton className="h-40" />;

  const explanation = (
    <ul className="list-disc space-y-1 pl-5 text-sm text-slate-600">
      <li>
        <strong>Read-only</strong> access. StripeFit can't send, delete or change anything.
      </li>
      <li>We only search order emails (orders, dispatch, delivery, refunds) from known clothing shops.</li>
      <li>Only the last {months} months, up to 100 emails.</li>
      <li>Personal details are removed before the AI reads an email. Email bodies are never stored.</li>
    </ul>
  );

  if (!status.configured) {
    return (
      <div className="space-y-3">
        <Notice tone="warn">
          <strong>Gmail import isn't set up on this server yet.</strong> The developer needs to add Google OAuth keys
          (GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET). You can still upload order emails on the “From an order” tab.
        </Notice>
        {explanation}
      </div>
    );
  }

  const job = status.job;
  const progress = job.total ? Math.round((job.done / job.total) * 100) : 0;

  return (
    <div className="space-y-4">
      {!status.connected ? (
        <>
          <div className="rounded-2xl bg-white p-4 ring-1 ring-slate-200">
            <h3 className="mb-2 font-semibold">What StripeFit reads</h3>
            {explanation}
          </div>
          <Button className="w-full" onClick={connect} loading={busy}>
            Connect Gmail
          </Button>
        </>
      ) : (
        <>
          <Notice tone="success">Gmail connected (read-only).</Notice>
          <div className="flex items-center gap-2">
            <select className={inputClass} value={months} onChange={(e) => setMonths(Number(e.target.value))} disabled={job.running}>
              {[3, 6, 12, 24].map((m) => (
                <option key={m} value={m}>
                  Last {m} months
                </option>
              ))}
            </select>
            <Button onClick={startImport} loading={busy || job.running} className="shrink-0">
              {job.running ? "Importing…" : "Import orders"}
            </Button>
          </div>
          {job.running && (
            <div className="space-y-1">
              <div className="h-2 overflow-hidden rounded-full bg-slate-200">
                <div className="h-full bg-indigo-600 transition-all" style={{ width: `${progress}%` }} />
              </div>
              <p className="text-xs text-slate-500">
                {job.total ? `${job.done} of ${job.total} emails` : "Searching your inbox for order emails…"}
              </p>
            </div>
          )}
          {job.error && <Notice tone="error">{job.error}</Notice>}
          {!job.running && job.summary && (
            <>
              {job.already_imported > 0 && (
                <p className="text-xs text-slate-500">{job.already_imported} emails were already imported earlier and skipped.</p>
              )}
              <IngestResults summary={job.summary} />
            </>
          )}
          <button onClick={disconnect} className="text-sm text-slate-500 underline" disabled={busy}>
            Disconnect Gmail
          </button>
        </>
      )}
    </div>
  );
}
