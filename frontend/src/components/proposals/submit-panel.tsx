"use client";

// The Submit step (F6): the Lead preview with every field the app will send,
// the AI-derived fields with their flags and a confirm form, the checklist,
// and Create Lead — the affirmative action, logged on every press.

import Link from "next/link";
import { useEffect, useState } from "react";

import { zohoApi } from "@/lib/api";
import type {
  CreateLeadResult,
  LeadAttempt,
  LeadFieldsIn,
  LeadPreview,
} from "@/lib/types/zoho";

const INPUT =
  "w-full rounded border border-neutral-300 px-3 py-2 text-sm dark:border-neutral-700 dark:bg-neutral-900";

const FIELD_ORDER = [
  "Upwork_Job_ID",
  "Job_Name",
  "Job_Link",
  "Lead_Status",
  "Lead_Source",
  "Last_Name",
  "Industry",
  "Job_Type",
  "Tools",
  "Rate_Type",
  "Budget",
  "Hourly_Rate",
  "Upwork_Fixed_Price",
  "Skills_Required",
  "Client_s_Desired_Experience_Level",
  "Deliverables",
  "Proposal_Date",
  "Proposal_Link",
  "By_Invitation",
  "Proposal",
];

function show(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "boolean") return v ? "Yes" : "No";
  return String(v);
}

export function SubmitPanel({
  proposalId,
  onSubmitted,
}: {
  proposalId: string;
  onSubmitted: () => void;
}) {
  const [preview, setPreview] = useState<LeadPreview | null>(null);
  const [attempts, setAttempts] = useState<LeadAttempt[]>([]);
  const [error, setError] = useState<string | null>(null);
  // Starts busy: the preview is loading until the first fetch settles.
  const [busy, setBusy] = useState<string | null>("load");
  const [result, setResult] = useState<CreateLeadResult | null>(null);
  const [fields, setFields] = useState<LeadFieldsIn>({
    industry: null,
    job_type: null,
    tools: null,
    proposal_link: null,
    by_invitation: false,
  });
  const [open, setOpen] = useState(false);

  function load(p: LeadPreview) {
    setPreview(p);
    const c = p.classification;
    const f = p.lead_fields;
    setFields({
      industry: f?.industry ?? c?.industry ?? null,
      job_type: f?.job_type ?? c?.job_type ?? null,
      tools: f?.tools ?? c?.tools ?? null,
      proposal_link: f?.proposal_link ?? null,
      by_invitation: f?.by_invitation ?? false,
    });
  }

  useEffect(() => {
    Promise.all([
      zohoApi.leadPreview(proposalId),
      zohoApi.leadAttempts(proposalId),
    ])
      .then(([p, a]) => {
        load(p);
        setAttempts(a);
      })
      .catch((e: unknown) =>
        setError(
          e instanceof Error ? e.message : "Could not load the preview.",
        ),
      )
      .finally(() => setBusy(null));
  }, [proposalId]);

  async function run<T>(
    action: string,
    call: () => Promise<T>,
  ): Promise<T | null> {
    setError(null);
    setBusy(action);
    try {
      return await call();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
      return null;
    } finally {
      setBusy(null);
    }
  }

  async function confirm() {
    const p = await run("confirm", () =>
      zohoApi.setLeadFields(proposalId, {
        ...fields,
        tools: fields.tools?.trim() || null,
        proposal_link: fields.proposal_link?.trim() || null,
      }),
    );
    if (p) {
      load(p);
      setOpen(false);
    }
  }

  async function createLead() {
    const r = await run("create", () => zohoApi.createLead(proposalId));
    if (!r) return;
    setResult(r);
    setAttempts(await zohoApi.leadAttempts(proposalId));
    if (r.ok) onSubmitted();
  }

  const connected =
    preview?.checklist.find((c) => c.key === "connected")?.ok ?? false;

  return (
    <section className="flex flex-col gap-4 rounded-lg border border-neutral-200 p-4 dark:border-neutral-800">
      <header>
        <h2 className="text-sm font-semibold tracking-wide text-neutral-500 uppercase">
          Submit · Zoho Lead
        </h2>
        <p className="mt-1 text-sm text-neutral-600 dark:text-neutral-400">
          <strong>Submit on Upwork first</strong>, by hand — the app never does.
          Then create the Lead: this is exactly what will be sent to Zoho.
          Pressing twice updates the same Lead (matched on the Upwork job ID).
        </p>
      </header>

      {error && (
        <p
          role="alert"
          className="rounded border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-800 dark:bg-red-950 dark:text-red-300"
        >
          {error}
        </p>
      )}

      {!preview && !error && (
        <p className="text-sm text-neutral-500">Loading preview…</p>
      )}

      {preview && !connected && (
        <p className="rounded border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-100">
          Zoho isn&apos;t connected.{" "}
          <Link href="/settings/zoho" className="underline">
            Connect it in Settings
          </Link>{" "}
          — a one-time step.
        </p>
      )}

      {preview && (
        <>
          {/* AI-derived fields */}
          <div className="rounded border border-neutral-200 p-3 text-sm dark:border-neutral-800">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <h3 className="font-medium">
                Categorised by Claude
                {preview.lead_fields?.confirmed_at && (
                  <span className="ml-2 text-xs font-normal text-green-700 dark:text-green-400">
                    confirmed by you
                  </span>
                )}
              </h3>
              <div className="flex gap-3 text-xs">
                <button
                  type="button"
                  onClick={() => setOpen((v) => !v)}
                  className="underline"
                >
                  {open ? "Close" : "Confirm or change"}
                </button>
                <button
                  type="button"
                  disabled={busy !== null}
                  onClick={() =>
                    void run("reclassify", () =>
                      zohoApi.leadPreview(proposalId, true),
                    ).then((p) => p && load(p))
                  }
                  className="underline disabled:opacity-50"
                >
                  {busy === "reclassify" ? "Asking Claude…" : "Re-run"}
                </button>
              </div>
            </div>

            {preview.classification_failure &&
              !preview.lead_fields?.confirmed_at && (
                <p
                  role="alert"
                  className="mt-2 text-xs text-red-700 dark:text-red-300"
                >
                  Not categorised — {preview.classification_failure.message} Set
                  the fields yourself below.
                </p>
              )}

            <dl className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-3">
              {(["Industry", "Job_Type", "Tools"] as const).map((name) => {
                const flag = preview.flags.find((f) => f.field === name);
                const key =
                  name === "Job_Type" ? "job_type" : name.toLowerCase();
                const conf =
                  preview.classification?.confidence[
                    key as "industry" | "job_type" | "tools"
                  ];
                return (
                  <div
                    key={name}
                    className={`rounded border px-2 py-1.5 ${flag ? "border-amber-400 bg-amber-50 dark:border-amber-700 dark:bg-amber-950" : "border-neutral-200 dark:border-neutral-800"}`}
                  >
                    <dt className="text-xs text-neutral-500">
                      {name.replace("_", " ")}
                    </dt>
                    <dd className="text-sm">{show(preview.payload[name])}</dd>
                    <dd className="text-[11px] text-neutral-500">
                      {flag ? (
                        <span className="text-amber-800 dark:text-amber-200">
                          ⚠ {flag.reason}
                        </span>
                      ) : conf !== undefined &&
                        !preview.lead_fields?.confirmed_at ? (
                        `confidence ${Math.round(conf * 100)}% (threshold ${Math.round((preview.thresholds[name] ?? 0) * 100)}%)`
                      ) : null}
                    </dd>
                  </div>
                );
              })}
            </dl>

            {open && (
              <form
                className="mt-3 flex flex-col gap-3"
                onSubmit={(e) => {
                  e.preventDefault();
                  void confirm();
                }}
              >
                <div className="grid gap-3 sm:grid-cols-2">
                  <label className="flex flex-col gap-1 text-xs text-neutral-500">
                    Industry
                    <select
                      value={fields.industry ?? ""}
                      onChange={(e) =>
                        setFields({
                          ...fields,
                          industry: e.target.value || null,
                        })
                      }
                      className={INPUT}
                    >
                      <option value="">—</option>
                      {preview.picklists.Industry.map((v) => (
                        <option key={v} value={v}>
                          {v}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="flex flex-col gap-1 text-xs text-neutral-500">
                    Job type
                    <select
                      value={fields.job_type ?? ""}
                      onChange={(e) =>
                        setFields({
                          ...fields,
                          job_type: e.target.value || null,
                        })
                      }
                      className={INPUT}
                    >
                      <option value="">—</option>
                      {preview.picklists.Job_Type.map((v) => (
                        <option key={v} value={v}>
                          {v}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
                <label className="flex flex-col gap-1 text-xs text-neutral-500">
                  Tools (comma-separated, up to 255 characters)
                  <input
                    value={fields.tools ?? ""}
                    maxLength={255}
                    onChange={(e) =>
                      setFields({ ...fields, tools: e.target.value })
                    }
                    className={INPUT}
                  />
                </label>
                <label className="flex flex-col gap-1 text-xs text-neutral-500">
                  Proposal link (from Upwork, after you submitted)
                  <input
                    value={fields.proposal_link ?? ""}
                    onChange={(e) =>
                      setFields({ ...fields, proposal_link: e.target.value })
                    }
                    placeholder="https://www.upwork.com/ab/proposals/…"
                    className={INPUT}
                  />
                </label>
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={fields.by_invitation}
                    onChange={(e) =>
                      setFields({ ...fields, by_invitation: e.target.checked })
                    }
                  />
                  The client invited me to this job
                </label>
                <div className="flex items-center gap-3">
                  <button
                    type="submit"
                    disabled={busy !== null}
                    className="rounded bg-neutral-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-neutral-100 dark:text-neutral-900"
                  >
                    {busy === "confirm" ? "Saving…" : "Confirm these values"}
                  </button>
                  <span className="text-xs text-neutral-500">
                    Confirming clears the flags; your values are what gets sent.
                  </span>
                </div>
              </form>
            )}
          </div>

          {/* Full payload */}
          <details className="rounded border border-neutral-200 p-3 text-sm dark:border-neutral-800">
            <summary className="cursor-pointer font-medium">
              Everything that will be sent (
              {Object.keys(preview.payload).length} fields)
            </summary>
            {preview.truncations.length > 0 && (
              <ul className="mt-2 space-y-1 text-xs text-amber-800 dark:text-amber-200">
                {preview.truncations.map((t) => (
                  <li key={t}>Truncated — {t}</li>
                ))}
              </ul>
            )}
            <dl className="mt-2 grid grid-cols-1 gap-x-4 gap-y-2 sm:grid-cols-2">
              {FIELD_ORDER.filter((k) => k in preview.payload).map((k) => (
                <div
                  key={k}
                  className={
                    k === "Proposal" || k === "Deliverables"
                      ? "sm:col-span-2"
                      : ""
                  }
                >
                  <dt className="text-xs text-neutral-500">
                    {k.replace(/_/g, " ")}
                  </dt>
                  <dd
                    className={`text-sm ${k === "Proposal" || k === "Deliverables" ? "max-h-48 overflow-auto rounded bg-neutral-50 p-2 font-sans text-xs whitespace-pre-wrap dark:bg-neutral-900" : "wrap-break-word"}`}
                  >
                    {show(preview.payload[k])}
                  </dd>
                </div>
              ))}
            </dl>
            <p className="mt-2 text-xs text-neutral-500">
              Not sent, by design: names, email, phone, company, address —
              nothing identifying the client is known or sent at this stage.
            </p>
          </details>

          {/* Checklist + button */}
          <div className="flex flex-col gap-3 rounded border border-neutral-200 p-3 text-sm dark:border-neutral-800">
            <ul className="space-y-1">
              {preview.checklist.map((c) => (
                <li
                  key={c.key}
                  className={
                    c.ok
                      ? "text-green-800 dark:text-green-300"
                      : "text-neutral-600 dark:text-neutral-400"
                  }
                >
                  {c.ok ? "✓" : "○"} {c.label}
                </li>
              ))}
            </ul>
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <button
                type="button"
                onClick={() => void createLead()}
                disabled={!preview.ready || busy !== null}
                className="rounded bg-neutral-900 px-5 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-neutral-100 dark:text-neutral-900"
              >
                {busy === "create"
                  ? "Creating Lead…"
                  : attempts.some((a) => a.zoho_lead_id)
                    ? "Update Lead in Zoho"
                    : "Create Lead in Zoho"}
              </button>
              <span className="text-xs text-neutral-500">
                {preview.ready
                  ? "Clicking is the approval; every press is logged."
                  : "Complete the checklist to enable."}
              </span>
            </div>
            {result && (
              <p
                role={result.ok ? "status" : "alert"}
                className={`rounded px-3 py-2 text-sm ${result.ok ? "border border-green-300 bg-green-50 text-green-800 dark:border-green-800 dark:bg-green-950 dark:text-green-200" : "border border-red-300 bg-red-50 text-red-700 dark:border-red-800 dark:bg-red-950 dark:text-red-300"}`}
              >
                {result.ok
                  ? `Lead ${result.action === "update" ? "updated" : "created"} in Zoho (ID ${result.zoho_lead_id}). Proposal marked submitted.`
                  : `Lead not created — ${result.error}`}
                {result.reconnect && (
                  <>
                    {" "}
                    <Link href="/settings/zoho" className="underline">
                      Reconnect Zoho
                    </Link>
                    .
                  </>
                )}
              </p>
            )}
          </div>

          {attempts.length > 0 && (
            <details className="text-xs text-neutral-500">
              <summary className="cursor-pointer">
                Attempt log ({attempts.length})
              </summary>
              <ul className="mt-2 space-y-1">
                {attempts.map((a) => (
                  <li key={a.id}>
                    {new Date(a.attempted_at).toLocaleString()} ·{" "}
                    {a.zoho_lead_id
                      ? `${a.action ?? "ok"} → Lead ${a.zoho_lead_id}`
                      : `failed${a.response_status ? ` (${a.response_status})` : ""}: ${a.error ?? ""}`}{" "}
                    · payload {a.payload_hash.slice(0, 10)}…
                  </li>
                ))}
              </ul>
            </details>
          )}
        </>
      )}
    </section>
  );
}
