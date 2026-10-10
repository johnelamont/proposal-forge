"use client";

// The operator's profile: what Claude is told about them, and the frame
// (greeting, sign-off) applied to every cover letter. Required before the
// first draft.

import Link from "next/link";
import { useEffect, useState } from "react";

import { profileApi } from "@/lib/api";
import { EMPTY_PROFILE, type ProfileIn } from "@/lib/types/proposal";

const INPUT =
  "w-full rounded border border-neutral-300 px-3 py-2 text-sm dark:border-neutral-700 dark:bg-neutral-900";

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="flex flex-col gap-1 text-sm">
      <span className="text-xs text-neutral-500">{label}</span>
      {children}
      {hint && <span className="text-xs text-neutral-500">{hint}</span>}
    </label>
  );
}

export function ProfileForm() {
  const [v, setV] = useState<ProfileIn>(EMPTY_PROFILE);
  const [neverClaimText, setNeverClaimText] = useState("");
  const [loaded, setLoaded] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    profileApi
      .get()
      .then((p) => {
        if (p) {
          setV(p);
          setNeverClaimText(p.never_claim.join(", "));
        }
        setLoaded(true);
      })
      .catch((e: unknown) =>
        setError(e instanceof Error ? e.message : "Could not load."),
      );
  }, []);

  const set = <K extends keyof ProfileIn>(k: K, val: ProfileIn[K]) =>
    setV((prev) => ({ ...prev, [k]: val }));

  async function save() {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const saved = await profileApi.put({
        ...v,
        signature_name: v.signature_name.trim(),
        positioning: v.positioning.trim(),
        greeting: v.greeting.trim() || "Hi,",
        sign_off: v.sign_off.trim() || "Kind Regards,",
        never_claim: neverClaimText
          .split(/[,\n]/)
          .map((s) => s.trim())
          .filter(Boolean),
        default_hourly_rate:
          v.default_hourly_rate && String(v.default_hourly_rate).trim() !== ""
            ? String(v.default_hourly_rate).trim()
            : null,
        fixed_price_range: v.fixed_price_range?.trim() || null,
      });
      setV(saved);
      setNotice("Profile saved.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  const ready = v.signature_name.trim() !== "" && v.positioning.trim() !== "";

  return (
    <section className="flex flex-col gap-5">
      <nav className="flex gap-4 text-sm">
        <Link href="/" className="underline">
          Home
        </Link>
      </nav>
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Profile</h1>
        <p className="mt-1 text-sm text-neutral-600 dark:text-neutral-400">
          What Claude is told about you when drafting, and the greeting and
          sign-off every cover letter gets. Drafting needs at least your name
          and the positioning paragraph.
        </p>
      </header>

      {!loaded && !error && (
        <p className="text-sm text-neutral-500">Loading…</p>
      )}

      {loaded && (
        <form
          className="flex flex-col gap-4"
          onSubmit={(e) => {
            e.preventDefault();
            void save();
          }}
        >
          <Field label="Name to sign with">
            <input
              required
              value={v.signature_name}
              onChange={(e) => set("signature_name", e.target.value)}
              className={INPUT}
            />
          </Field>

          <Field
            label="Positioning"
            hint="Who you are and what you do, in your own words. Claude writes in this voice and never goes beyond it."
          >
            <textarea
              required
              rows={5}
              value={v.positioning}
              onChange={(e) => set("positioning", e.target.value)}
              className={INPUT}
            />
          </Field>

          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Greeting" hint="First line of every cover letter.">
              <input
                value={v.greeting}
                onChange={(e) => set("greeting", e.target.value)}
                className={INPUT}
              />
            </Field>
            <Field
              label="Sign-off"
              hint="Followed by your name on the next line."
            >
              <input
                value={v.sign_off}
                onChange={(e) => set("sign_off", e.target.value)}
                className={INPUT}
              />
            </Field>
          </div>

          <Field
            label="Tone notes"
            hint="e.g. “Plain English. Short paragraphs. No hype.”"
          >
            <textarea
              rows={2}
              value={v.tone_notes}
              onChange={(e) => set("tone_notes", e.target.value)}
              className={INPUT}
            />
          </Field>

          <Field
            label="Never claim"
            hint="Comma-separated phrases a draft must never assert about you, e.g. “Zoho Partner, certified”. If one appears, the draft is flagged."
          >
            <input
              value={neverClaimText}
              onChange={(e) => setNeverClaimText(e.target.value)}
              className={INPUT}
            />
          </Field>

          <div className="grid gap-4 sm:grid-cols-2">
            <Field
              label="Default hourly rate (USD)"
              hint="Used for hourly quotes."
            >
              <input
                inputMode="decimal"
                value={v.default_hourly_rate ?? ""}
                onChange={(e) => set("default_hourly_rate", e.target.value)}
                className={INPUT}
              />
            </Field>
            <Field
              label="Typical fixed-price range"
              hint="e.g. $2K–$8K. Shown as quote evidence."
            >
              <input
                value={v.fixed_price_range ?? ""}
                onChange={(e) => set("fixed_price_range", e.target.value)}
                className={INPUT}
              />
            </Field>
          </div>

          {error && (
            <p
              role="alert"
              className="rounded border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-800 dark:bg-red-950 dark:text-red-300"
            >
              {error}
            </p>
          )}
          {notice && !error && (
            <p
              role="status"
              className="rounded border border-green-300 bg-green-50 px-3 py-2 text-sm text-green-800 dark:border-green-800 dark:bg-green-950 dark:text-green-200"
            >
              {notice}
            </p>
          )}

          <div className="flex items-center justify-between gap-3">
            <span className="text-xs text-neutral-500">
              {ready
                ? "Ready for drafting."
                : "Name and positioning are required."}
            </span>
            <button
              type="submit"
              disabled={busy || !ready}
              className="rounded bg-neutral-900 px-5 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-neutral-100 dark:text-neutral-900"
            >
              {busy ? "Saving…" : "Save profile"}
            </button>
          </div>
        </form>
      )}
    </section>
  );
}
