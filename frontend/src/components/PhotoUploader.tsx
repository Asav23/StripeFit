import { ArrowRight, Camera, CheckCircle2, ImagePlus, XCircle } from "lucide-react";
import { useRef, useState, type DragEvent } from "react";
import { ApiError, api } from "../api/client";
import { useMe, useToast } from "../context";
import { LinkButton, Notice, Spinner, UpgradeBanner } from "./ui";

interface Upload {
  key: string;
  name: string;
  preview: string;
  state: "queued" | "working" | "done" | "failed";
  message: string;
}

const CONCURRENCY = 2;
const MAX_MB = 10;

export default function PhotoUploader() {
  const { refresh } = useMe();
  const { showError } = useToast();
  const [uploads, setUploads] = useState<Upload[]>([]);
  const [blocked, setBlocked] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const cameraInput = useRef<HTMLInputElement>(null);
  const galleryInput = useRef<HTMLInputElement>(null);

  const update = (key: string, patch: Partial<Upload>) => setUploads((list) => list.map((u) => (u.key === key ? { ...u, ...patch } : u)));

  const handleFiles = async (fileList: FileList | null) => {
    if (!fileList?.length) return;
    const files = [...fileList];
    const batch: Upload[] = files.map((f, i) => ({
      key: `${Date.now()}-${i}-${f.name}`,
      name: f.name,
      preview: URL.createObjectURL(f),
      state: "queued",
      message: "Waiting",
    }));
    setUploads((list) => [...batch, ...list]);
    setBlocked(null);

    // One request per photo so each gets its own progress, two at a time.
    const queue = files.map((file, i) => ({ file, key: batch[i].key }));
    const worker = async () => {
      for (let job = queue.shift(); job; job = queue.shift()) {
        const { file, key } = job;
        if (!file.type.startsWith("image/")) {
          update(key, { state: "failed", message: "Not an image file" });
          continue;
        }
        if (file.size > MAX_MB * 1024 * 1024) {
          update(key, { state: "failed", message: `Over ${MAX_MB} MB, try a smaller photo` });
          continue;
        }
        update(key, { state: "working", message: "Labelling…" });
        try {
          const [result] = await api.uploadPhotos([file]);
          update(key, { state: result.ok ? "done" : "failed", message: result.ok ? (result.item?.name ?? "Ready") : result.message });
        } catch (e) {
          if (e instanceof ApiError && e.code === "upgrade_required") {
            setBlocked(e.message);
            update(key, { state: "failed", message: "Free wardrobe is full" });
          } else {
            update(key, { state: "failed", message: e instanceof ApiError ? e.message : "Upload failed" });
            if (!(e instanceof ApiError)) showError(e);
          }
        }
      }
    };
    await Promise.all(Array.from({ length: CONCURRENCY }, worker));
    void refresh();
  };

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragging(false);
    void handleFiles(e.dataTransfer.files);
  };

  const doneCount = uploads.filter((u) => u.state === "done").length;
  const working = uploads.some((u) => u.state === "working" || u.state === "queued");

  return (
    <div className="space-y-6">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={`grid gap-3 rounded-lg border border-dashed p-3 transition sm:grid-cols-2 ${dragging ? "border-accent bg-accent-soft" : "border-line-strong"}`}
      >
        <button
          onClick={() => cameraInput.current?.click()}
          className="surface-night flex items-center gap-4 rounded-lg p-5 text-left shadow-[var(--shadow-raised)] transition hover:brightness-110 sm:flex-col sm:items-start sm:p-6"
        >
          <Camera className="h-6 w-6" strokeWidth={1.5} />
          <span>
            <span className="block text-[15px] font-medium">Take a photo</span>
            <span className="block text-[13px] text-white/65">Use your phone's camera</span>
          </span>
        </button>
        <button
          onClick={() => galleryInput.current?.click()}
          className="flex items-center gap-4 rounded-lg border border-line-strong bg-card p-5 text-left shadow-[var(--shadow-xs)] transition hover:border-accent/50 hover:shadow-[var(--shadow-card)] sm:flex-col sm:items-start sm:p-6"
        >
          <ImagePlus className="h-6 w-6" strokeWidth={1.5} />
          <span>
            <span className="block text-[15px] font-medium">Choose photos</span>
            <span className="block text-[13px] text-muted">Several at once, or drop them here</span>
          </span>
        </button>
      </div>
      {[
        { ref: cameraInput, capture: true },
        { ref: galleryInput, capture: false },
      ].map(({ ref, capture }) => (
        <input
          key={String(capture)}
          ref={ref}
          type="file"
          accept="image/*"
          {...(capture ? { capture: "environment" as const } : {})}
          multiple
          hidden
          onChange={(e) => {
            void handleFiles(e.target.files);
            e.target.value = "";
          }}
        />
      ))}

      <ul className="grid gap-x-8 gap-y-1 text-[13px] text-ink-2 sm:grid-cols-3">
        <li><span className="font-mono text-accent">01</span> One item per photo</li>
        <li><span className="font-mono text-accent">02</span> Lay it flat or hang it up</li>
        <li><span className="font-mono text-accent">03</span> Good light, plain background</li>
      </ul>

      {blocked && <UpgradeBanner message={blocked} />}

      {uploads.length > 0 && (
        <ul className="divide-y divide-line rounded-xl border border-line bg-card shadow-[var(--shadow-card)]" aria-live="polite">
          {uploads.map((u) => (
            <li key={u.key} className="flex items-center gap-3 px-3 py-2.5">
              <img src={u.preview} alt="" className="h-12 w-12 rounded-sm object-cover" />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium">{u.state === "done" ? u.message : u.name}</p>
                <p className={`truncate text-xs ${u.state === "failed" ? "text-danger" : "text-muted"}`}>
                  {u.state === "done" ? "Labelled, ready to review" : u.message}
                </p>
              </div>
              {(u.state === "working" || u.state === "queued") && <Spinner className={`h-4 w-4 ${u.state === "queued" ? "text-line-strong" : "text-ink"}`} />}
              {u.state === "done" && <CheckCircle2 className="h-5 w-5 text-ok" strokeWidth={1.75} />}
              {u.state === "failed" && <XCircle className="h-5 w-5 text-danger" strokeWidth={1.75} />}
            </li>
          ))}
        </ul>
      )}

      {doneCount > 0 && !working && (
        <Notice tone="success">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <span>
              {doneCount} item{doneCount > 1 ? "s" : ""} labelled. Check the labels before they join your wardrobe.
            </span>
            <LinkButton to="/review">
              Review <ArrowRight className="h-4 w-4" />
            </LinkButton>
          </div>
        </Notice>
      )}
    </div>
  );
}
