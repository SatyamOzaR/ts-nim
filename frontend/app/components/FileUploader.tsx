"use client";

import { useState, useRef, useCallback } from "react";
import { BACKEND_URL, apiHeaders } from "../lib/api";

interface UploadResult {
  imported: number;
  merged: number;
  skipped?: number;
  interactions?: number;
  summary?: string;
}

interface FileUploaderProps {
  memberName: string;
  onClose: () => void;
  onSuccess: (result: UploadResult) => void;
}

export function FileUploader({ memberName, onClose, onSuccess }: FileUploaderProps) {
  const [files, setFiles] = useState<File[]>([]);
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  const addFiles = useCallback((incoming: FileList | null) => {
    if (!incoming) return;
    const next = [...files];
    for (const f of Array.from(incoming)) {
      if (next.length >= 5) break;
      if (!next.find((x) => x.name === f.name && x.size === f.size)) {
        next.push(f);
      }
    }
    setFiles(next);
    setError("");
  }, [files]);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    if (files.length >= 5) {
      setError("Maximum 5 files allowed.");
      return;
    }
    addFiles(e.dataTransfer.files);
  }, [files, addFiles]);

  const removeFile = (idx: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== idx));
    setError("");
  };

  const handleSubmit = async () => {
    if (files.length === 0) {
      setError("Please select at least one file.");
      return;
    }

    setUploading(true);
    setError("");

    try {
      const formData = new FormData();
      formData.append("member_name", memberName);
      for (const f of files) {
        formData.append("files", f);
      }

      const resp = await fetch(`${BACKEND_URL}/api/connections/import-smart`, {
        method: "POST",
        headers: apiHeaders(),
        body: formData,
      });

      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}));
        throw new Error(body.detail || `Upload failed: ${resp.statusText}`);
      }

      const result: UploadResult = await resp.json();
      onSuccess(result);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="w-full max-w-md rounded-2xl border border-zinc-700 bg-zinc-900 p-6 shadow-2xl">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-semibold text-zinc-100">Import Files</h3>
          <button
            onClick={onClose}
            className="rounded-md p-1 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-100"
          >
            <svg width="20" height="20" viewBox="0 0 20 20" fill="currentColor">
              <path d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z" />
            </svg>
          </button>
        </div>

        <p className="mb-4 text-xs text-zinc-500">
          Upload up to 5 files in any format — LinkedIn CSV, email exports (.eml), calendar files (.ics), PDFs, or plain text. The AI will extract contacts and interactions automatically.
        </p>

        <div className="space-y-3">
          {/* Drop zone */}
          <div
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
            onClick={() => files.length < 5 && fileRef.current?.click()}
            className={`cursor-pointer rounded-lg border-2 border-dashed p-6 text-center transition-colors ${
              dragOver
                ? "border-indigo-500 bg-indigo-500/10"
                : files.length >= 5
                  ? "cursor-not-allowed border-zinc-700 opacity-50"
                  : "border-zinc-700 hover:border-zinc-500"
            }`}
          >
            <input
              ref={fileRef}
              type="file"
              multiple
              className="hidden"
              onChange={(e) => addFiles(e.target.files)}
            />
            <svg
              className="mx-auto mb-2 text-zinc-600"
              width="24"
              height="24"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
            >
              <path d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1M16 12l-4-4-4 4M12 8v8" />
            </svg>
            <p className="text-sm text-zinc-500">
              {files.length >= 5
                ? "Maximum 5 files reached"
                : "Drop files here or click to browse"}
            </p>
            <p className="mt-0.5 text-xs text-zinc-600">CSV, EML, ICS, PDF, TXT and more</p>
          </div>

          {/* File list */}
          {files.length > 0 && (
            <ul className="space-y-1.5">
              {files.map((f, i) => (
                <li
                  key={i}
                  className="flex items-center justify-between rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2"
                >
                  <span className="truncate text-sm text-zinc-300">{f.name}</span>
                  <button
                    type="button"
                    onClick={() => removeFile(i)}
                    className="ml-2 shrink-0 rounded p-0.5 text-zinc-500 hover:text-zinc-200"
                  >
                    <svg width="14" height="14" viewBox="0 0 20 20" fill="currentColor">
                      <path d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z" />
                    </svg>
                  </button>
                </li>
              ))}
            </ul>
          )}

          {error && <p className="text-sm text-red-400">{error}</p>}

          <button
            onClick={handleSubmit}
            disabled={uploading || files.length === 0}
            className="w-full rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-indigo-500 disabled:opacity-50"
          >
            {uploading ? "Extracting with AI..." : `Import ${files.length || ""} file${files.length !== 1 ? "s" : ""}`}
          </button>
        </div>
      </div>
    </div>
  );
}
