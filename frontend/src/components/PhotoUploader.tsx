import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, api } from "../api/client";
import { useMe, useToast } from "../context";
import { CameraIcon, ImageIcon } from "./Icons";
import { Notice, Spinner, UpgradeBanner } from "./ui";

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
  const cameraInput = useRef<HTMLInputElement>(null);
  const galleryInput = useRef<HTMLInputElement>(null);

  const update = (key: string, patch: Partial<Upload>) =>
    setUploads((list) => list.map((u) => (u.key === key ? { ...u, ...patch } : u)));

  const handleFiles = async (fileList: FileList | null) => {
    if (!fileList?.length) return;
    const files = [...fileList];
    const batch: Upload[] = files.map((f, i) => ({
      key: `${Date.now()}-${i}-${f.name}`,
      name: f.name,
      preview: URL.createObjectURL(f),
      state: "queued",
      message: "Waiting…",
    }));
    setUploads((list) => [...batch, ...list]);
    setBlocked(null);

    // One request per photo so each gets its own progress, two at a time.
    const queue = files.map((file, i) => ({ file, key: batch[i].key }));
    const worker = async () => {
      for (let job = queue.shift(); job; job = queue.shift()) {
        const { file, key } = job;
        if (!file.type.startsWith("image/")) {
          update(key, { state: "failed", message: "Not an image file." });
          continue;
        }
        if (file.size > MAX_MB * 1024 * 1024) {
          update(key, { state: "failed", message: `Over ${MAX_MB} MB. Try a smaller photo.` });
          continue;
        }
        update(key, { state: "working", message: "Labelling with AI…" });
        try {
          const [result] = await api.uploadPhotos([file]);
          update(key, {
            state: result.ok ? "done" : "failed",
            message: result.ok ? `${result.item?.name}: ready to review` : result.message,
          });
        } catch (e) {
          if (e instanceof ApiError && e.code === "upgrade_required") {
            setBlocked(e.message);
            update(key, { state: "failed", message: "Wardrobe full on the free plan." });
          } else {
            update(key, { state: "failed", message: e instanceof ApiError ? e.message : "Upload failed." });
            if (!(e instanceof ApiError)) showError(e);
          }
        }
      }
    };
    await Promise.all(Array.from({ length: CONCURRENCY }, worker));
    void refresh();
  };

  const doneCount = uploads.filter((u) => u.state === "done").length;
  const working = uploads.some((u) => u.state === "working" || u.state === "queued");

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3">
        <button
          onClick={() => cameraInput.current?.click()}
          className="flex flex-col items-center gap-2 rounded-2xl bg-indigo-600 px-4 py-6 font-semibold text-white shadow-sm"
        >
          <CameraIcon className="h-8 w-8" />
          Take a photo
        </button>
        <button
          onClick={() => galleryInput.current?.click()}
          className="flex flex-col items-center gap-2 rounded-2xl bg-white px-4 py-6 font-semibold text-slate-700 ring-1 ring-slate-200"
        >
          <ImageIcon className="h-8 w-8" />
          From gallery
        </button>
      </div>
      <input
        ref={cameraInput}
        type="file"
        accept="image/*"
        capture="environment"
        multiple
        hidden
        onChange={(e) => {
          void handleFiles(e.target.files);
          e.target.value = "";
        }}
      />
      <input
        ref={galleryInput}
        type="file"
        accept="image/*"
        multiple
        hidden
        onChange={(e) => {
          void handleFiles(e.target.files);
          e.target.value = "";
        }}
      />
      <p className="text-center text-xs text-slate-500">
        One item per photo works best: lay it flat or hang it up in good light. JPEG, PNG or WebP, up to 10 MB.
      </p>

      {blocked && <UpgradeBanner message={blocked} />}

      {uploads.length > 0 && (
        <ul className="space-y-2">
          {uploads.map((u) => (
            <li key={u.key} className="flex items-center gap-3 rounded-2xl bg-white p-2 ring-1 ring-slate-200">
              <img src={u.preview} alt="" className="h-14 w-14 rounded-xl object-cover" />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-slate-800">{u.name}</p>
                <p className={`text-xs ${u.state === "failed" ? "text-rose-600" : "text-slate-500"}`}>{u.message}</p>
              </div>
              {u.state === "working" && <Spinner className="h-5 w-5 text-indigo-600" />}
              {u.state === "done" && <span className="text-lg text-emerald-600">✓</span>}
              {u.state === "failed" && <span className="text-lg text-rose-500">!</span>}
            </li>
          ))}
        </ul>
      )}

      {doneCount > 0 && !working && (
        <Notice tone="success">
          {doneCount} item{doneCount > 1 ? "s" : ""} labelled.{" "}
          <Link to="/review" className="font-semibold underline">
            Review and confirm →
          </Link>
        </Notice>
      )}
    </div>
  );
}
