import { FileText, ShieldCheck } from "lucide-react";
import { useRef, useState } from "react";
import { api } from "../api/client";
import type { IngestSummary } from "../api/types";
import { useMe, useToast } from "../context";
import IngestResults from "./IngestResults";
import { Button, Skeleton, Spinner } from "./ui";

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
    <div className="grid gap-6 lg:grid-cols-[1fr_280px]">
      <div className="space-y-4">
        <button
          type="button"
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
          disabled={working}
          className={`flex w-full flex-col items-center gap-3 rounded-lg border border-dashed px-6 py-10 text-center transition ${
            dragging ? "border-ink bg-sunk" : "border-line-strong hover:border-ink"
          }`}
        >
          {working ? <Spinner className="h-6 w-6" /> : <FileText className="h-6 w-6 text-ink-2" strokeWidth={1.5} />}
          <span className="text-[15px] font-medium">{working ? "Reading your orders…" : "Drop order emails or screenshots"}</span>
          <span className="text-[13px] text-muted">.eml, .html, .txt, .pdf or an image. Confirmations, dispatch, refunds, exchanges.</span>
        </button>
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
        <div className="flex items-center gap-3">
          <span className="h-px flex-1 bg-line" />
          <span className="kicker">or</span>
          <span className="h-px flex-1 bg-line" />
        </div>
        <Button variant="secondary" className="w-full" onClick={() => run(api.ingestSamples)} disabled={working}>
          Try it with 18 sample order emails
        </Button>

        {working && (
          <div className="space-y-2">
            <Skeleton className="h-20" />
            <Skeleton className="h-40" />
          </div>
        )}
        {summary && <IngestResults summary={summary} />}
      </div>

      <aside className="h-fit rounded-lg border border-line p-4 text-[13px] leading-relaxed text-ink-2">
        <p className="mb-2 flex items-center gap-2 font-medium text-ink">
          <ShieldCheck className="h-4 w-4 text-ok" /> What happens to your email
        </p>
        <ul className="space-y-1.5">
          <li>Addresses, phone numbers, email addresses and card details are removed before the AI reads anything.</li>
          <li>Only item details are kept. The email itself is never stored.</li>
          <li>Refunds remove items; child sizes and gifts are flagged for you.</li>
          <li className="text-warn">Screenshots go to the AI as they are, so crop out your address first.</li>
        </ul>
      </aside>
    </div>
  );
}
