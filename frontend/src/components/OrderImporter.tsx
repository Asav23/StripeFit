import { useRef, useState } from "react";
import { api } from "../api/client";
import type { IngestSummary } from "../api/types";
import { useMe, useToast } from "../context";
import { MailIcon } from "./Icons";
import IngestResults from "./IngestResults";
import { Button, Notice, Skeleton } from "./ui";

const ACCEPT = ".eml,.html,.htm,.txt,.pdf,.png,.jpg,.jpeg,.webp";

export default function OrderImporter() {
  const { refresh } = useMe();
  const { showError } = useToast();
  const [dragging, setDragging] = useState(false);
  const [working, setWorking] = useState(false);
  const [summary, setSummary] = useState<IngestSummary | null>(null);
  const input = useRef<HTMLInputElement>(null);

  const run = async (task: () => Promise<IngestSummary>) => {
    setWorking(true);
    setSummary(null);
    try {
      setSummary(await task());
      void refresh();
    } catch (e) {
      showError(e);
    } finally {
      setWorking(false);
    }
  };

  const upload = (files: FileList | null) => {
    if (files?.length) void run(() => api.ingestEmails([...files]));
  };

  return (
    <div className="space-y-4">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          upload(e.dataTransfer.files);
        }}
        onClick={() => input.current?.click()}
        className={`flex cursor-pointer flex-col items-center gap-2 rounded-2xl border-2 border-dashed px-4 py-8 text-center transition ${
          dragging ? "border-indigo-500 bg-indigo-50" : "border-slate-300 bg-white"
        }`}
      >
        <MailIcon className="h-9 w-9 text-indigo-600" />
        <p className="font-semibold text-slate-800">Drop order emails or screenshots here</p>
        <p className="text-xs text-slate-500">.eml, .html, .txt, .pdf, or a screenshot. Several at once is fine.</p>
        <input
          ref={input}
          type="file"
          accept={ACCEPT}
          multiple
          hidden
          onChange={(e) => {
            upload(e.target.files);
            e.target.value = "";
          }}
        />
      </div>

      <Button variant="secondary" className="w-full" onClick={() => run(api.ingestSamples)} disabled={working}>
        Try it with our sample order emails
      </Button>

      <Notice tone="info">
        <strong>Your privacy:</strong> we strip addresses, phone numbers, email addresses and card details before the AI
        reads anything, and we keep only the item details, never the email. Screenshots go to the AI as they are, so crop
        out your address first.
      </Notice>

      {working && (
        <div className="space-y-2">
          <p className="text-sm text-slate-500">Reading your orders…</p>
          <Skeleton className="h-6 w-2/3" />
          <Skeleton className="h-24" />
        </div>
      )}
      {summary && <IngestResults summary={summary} />}
    </div>
  );
}
