"use client";

import { useState, useRef, useCallback } from "react";
import { BACKEND_URL, apiHeaders } from "../lib/api";

interface UploadResult {
  imported: number;
  merged: number;
  message: string;
}

export function CSVUploader({
  onClose,
  onSuccess,
}: {
  onClose: () => void;
  onSuccess: (result: UploadResult) => void;
}) {
  const [memberName, setMemberName] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped?.name.endsWith(".csv")) {
      setFile(dropped);
      setError("");
    } else {
      setError("Please drop a CSV file");
    }
  }, []);

  const handleSubmit = async () => {
    if (!memberName.trim()) {
      setError("Please enter your name");
      return;
    }
    if (!file) {
      setError("Please select a CSV file");
      return;
    }

    setUploading(true);
    setError("");

    try {
      const formData = new FormData();
      formData.append("member_name", memberName.trim());
      formData.append("file", file);

      const resp = await fetch(`${BACKEND_URL}/api/connections/import`, {
        method: "POST",
        headers: apiHeaders(),
        body: formData,
      });

      if (!resp.ok) {
        throw new Error(`Upload failed: ${resp.statusText}`);
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
          <h3 className="text-lg font-semibold">Import LinkedIn Connections</h3>
          <button
            onClick={onClose}
            className="rounded-md p-1 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-100"
          >
            <svg width="20" height="20" viewBox="0 0 20 20" fill="currentColor">
              <path d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z" />
            </svg>
          </button>
        </div>

        <div className="space-y-4">
          <div>
            <label className="mb-1 block text-sm font-medium text-zinc-400">
              Your Name (Team Member)
            </label>
            <input
              type="text"
              value={memberName}
              onChange={(e) => setMemberName(e.target.value)}
              placeholder="e.g., Paras Mehta"
              className="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-sm text-zinc-100 placeholder-zinc-500 outline-none focus:border-indigo-500"
            />
          </div>

          <div
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
            onClick={() => fileRef.current?.click()}
            className={`cursor-pointer rounded-lg border-2 border-dashed p-8 text-center transition-colors ${
              dragOver
                ? "border-indigo-500 bg-indigo-500/10"
                : "border-zinc-700 hover:border-zinc-500"
            }`}
          >
            <input
              ref={fileRef}
              type="file"
              accept=".csv"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) {
                  setFile(f);
                  setError("");
                }
              }}
            />
            {file ? (
              <p className="text-sm text-zinc-300">{file.name}</p>
            ) : (
              <p className="text-sm text-zinc-500">
                Drop your LinkedIn CSV here or click to browse
              </p>
            )}
          </div>

          {error && (
            <p className="text-sm text-red-400">{error}</p>
          )}

          <button
            onClick={handleSubmit}
            disabled={uploading}
            className="w-full rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-indigo-500 disabled:opacity-50"
          >
            {uploading ? "Importing..." : "Import Connections"}
          </button>
        </div>
      </div>
    </div>
  );
}
