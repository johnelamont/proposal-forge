"use client";

// A real <select> of suggested values plus an "Other…" choice that reveals a
// text input. Values not in the list (e.g. Claude's extracted wording) show
// as Other with the text filled in. Reliable across browsers, unlike datalist.

import { useState } from "react";

const OTHER = "__other__";

export function PickOrType({
  value,
  options,
  onChange,
  className,
  placeholder,
}: {
  value: string;
  options: readonly string[];
  onChange: (next: string) => void;
  className: string;
  placeholder?: string;
}) {
  const inList = options.includes(value);
  // Once the operator chooses Other, keep the text box open even while empty.
  const [other, setOther] = useState(value !== "" && !inList);
  const showText = other || (value !== "" && !inList);

  return (
    <div className="flex flex-col gap-2">
      <select
        value={showText ? OTHER : value}
        onChange={(e) => {
          if (e.target.value === OTHER) {
            setOther(true);
            if (inList) onChange("");
          } else {
            setOther(false);
            onChange(e.target.value);
          }
        }}
        className={className}
      >
        <option value="">—</option>
        {options.map((o) => (
          <option key={o} value={o}>
            {o}
          </option>
        ))}
        <option value={OTHER}>Other…</option>
      </select>
      {showText && (
        <input
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder ?? "Type your own"}
          autoFocus={value === ""}
          className={className}
        />
      )}
    </div>
  );
}
