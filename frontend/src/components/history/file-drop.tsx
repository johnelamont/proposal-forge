"use client";

// Drop zone for F5. Reads dropped files as text in the browser and shows
// each as accepted or refused (client-side mirror of the server rules).
// Nothing leaves the device until the operator clicks Extract.

import { useRef, useState } from "react";

import { MAX_FILES, nameRefusal, sizeRefusal } from "@/lib/file-rules";
import type { DroppedFile, RefusedFile } from "@/lib/types/work-history";

export interface Screened {
  accepted: DroppedFile[];
  refused: RefusedFile[];
}

export function FileDrop({
  value,
  onChange,
  disabled,
}: {
  value: Screened;
  onChange: (next: Screened) => void;
  disabled?: boolean;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);

  async function addFiles(list: FileList | File[]) {
    const accepted = [...value.accepted];
    const refused = [...value.refused];
    for (const file of Array.from(list)) {
      if (accepted.some((a) => a.name === file.name)) continue;
      const reason = nameRefusal(file.name) ?? sizeRefusal(file.size);
      if (reason) {
        refused.push({ name: file.name, reason });
        continue;
      }
      if (accepted.length >= MAX_FILES) {
        refused.push({
          name: file.name,
          reason: `more than ${MAX_FILES} files`,
        });
        continue;
      }
      accepted.push({ name: file.name, content: await file.text() });
    }
    onChange({ accepted, refused });
  }

  function remove(name: string) {
    onChange({
      accepted: value.accepted.filter((a) => a.name !== name),
      refused: value.refused.filter((r) => r.name !== name),
    });
  }

  return (
    <div className="flex flex-col gap-3">
      <div
        role="button"
        tabIndex={0}
        onClick={() => !disabled && inputRef.current?.click()}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") inputRef.current?.click();
        }}
        onDragOver={(e) => {
          e.preventDefault();
          setOver(true);
        }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setOver(false);
          if (!disabled) void addFiles(e.dataTransfer.files);
        }}
        className={`flex cursor-pointer flex-col items-center justify-center gap-1 rounded-lg border-2 border-dashed p-8 text-center text-sm ${
          over
            ? "border-neutral-900 bg-neutral-50 dark:border-neutral-100 dark:bg-neutral-900"
            : "border-neutral-300 dark:border-neutral-700"
        } ${disabled ? "opacity-50" : ""}`}
      >
        <span className="font-medium">
          Drop the project&apos;s README or docs here
        </span>
        <span className="text-neutral-500">
          or click to choose. Markdown, text, or a dependency manifest; up to{" "}
          {MAX_FILES} files, 200 KB each.
        </span>
        <input
          ref={inputRef}
          type="file"
          multiple
          hidden
          onChange={(e) => {
            if (e.target.files) void addFiles(e.target.files);
            e.target.value = "";
          }}
        />
      </div>

      <p className="text-xs text-neutral-500">
        Only the files listed below leave this device. If this was a client
        project, check that the contract allows sharing its docs with an AI
        processor before extracting.
      </p>

      {(value.accepted.length > 0 || value.refused.length > 0) && (
        <ul className="divide-y divide-neutral-200 rounded border border-neutral-200 text-sm dark:divide-neutral-800 dark:border-neutral-800">
          {value.accepted.map((f) => (
            <li
              key={f.name}
              className="flex items-center justify-between gap-3 px-3 py-2"
            >
              <span className="truncate">
                <span className="mr-2 text-green-700 dark:text-green-400">
                  ✓
                </span>
                {f.name}
                <span className="ml-2 text-xs text-neutral-500">
                  {Math.ceil(f.content.length / 1000)} KB
                </span>
              </span>
              <button
                type="button"
                onClick={() => remove(f.name)}
                disabled={disabled}
                className="text-xs underline"
              >
                remove
              </button>
            </li>
          ))}
          {value.refused.map((f) => (
            <li
              key={f.name}
              className="flex items-center justify-between gap-3 px-3 py-2 text-neutral-500"
            >
              <span className="truncate">
                <span className="mr-2 text-red-600 dark:text-red-400">✕</span>
                {f.name}
                <span className="ml-2 text-xs">refused — {f.reason}</span>
              </span>
              <button
                type="button"
                onClick={() => remove(f.name)}
                className="text-xs underline"
              >
                dismiss
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
