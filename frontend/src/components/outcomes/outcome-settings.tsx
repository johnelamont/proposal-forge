"use client";

// Settings → Outcome webhook (F8): the per-user integration secret Zoho uses
// to post outcomes, shown exactly once when generated; the endpoint URL to
// store in Zoho; and where to find the Zoho-side setup steps.

import Link from "next/link";
import { useEffect, useState } from "react";

import { outcomesApi } from "@/lib/api";
import type { SecretStatus } from "@/lib/types/outcomes";

export function OutcomeSettings() {
  const [status, setStatus] = useState<SecretStatus | null>(null);
  const [secret, setSecret] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState<"secret" | "url" | null>(null);

  useEffect(() => {
    outcomesApi
      .secretStatus()
      .then(setStatus)
      .catch((e: unknown) =>
        setError(e instanceof Error ? e.message : "Could not load."),
      );
  }, []);

  async function generate() {
    if (
      status?.exists &&
      !window.confirm(
        "Rotate the secret? The current one stops working immediately; update forge_secret in Zoho afterwards.",
      )
    )
      return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const created = await outcomesApi.generateSecret();
      setSecret(created.secret);
      setStatus(created);
      setNotice(
        "Secret generated. Copy it now — it is shown only this once and stored only as a hash.",
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not generate.");
    } finally {
      setBusy(false);
    }
  }

  async function revoke() {
    if (
      !window.confirm(
        "Revoke the secret? Zoho will get 401 on every outcome until you generate a new one.",
      )
    )
      return;
    setBusy(true);
    setError(null);
    try {
      await outcomesApi.revokeSecret();
      setSecret(null);
      setStatus(await outcomesApi.secretStatus());
      setNotice("Secret revoked.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not revoke.");
    } finally {
      setBusy(false);
    }
  }

  async function copy(text: string, which: "secret" | "url") {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(which);
      setTimeout(() => setCopied(null), 1500);
    } catch {
      setError("Clipboard unavailable; select and copy by hand.");
    }
  }

  return (
    <section className="flex flex-col gap-5">
      <nav className="flex gap-4 text-sm">
        <Link href="/" className="underline">
          Home
        </Link>
        <Link href="/settings/zoho" className="underline">
          Zoho connection
        </Link>
        <Link href="/settings/review-queue" className="underline">
          Review queue
        </Link>
      </nav>
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">
          Outcome webhook
        </h1>
        <p className="mt-1 text-sm text-neutral-600 dark:text-neutral-400">
          Zoho posts each outcome (Won button, or a closing Lead Status) to this
          app with a secret only you hold. Generate it here, then store it in
          Zoho as the <code>forge_secret</code> organization variable. Setup
          steps for the field, button and workflow rule are in the repo under{" "}
          <code>zoho/README.md</code>.
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
      {notice && !error && (
        <p
          role="status"
          className="rounded border border-green-300 bg-green-50 px-3 py-2 text-sm text-green-800 dark:border-green-800 dark:bg-green-950 dark:text-green-200"
        >
          {notice}
        </p>
      )}
      {!status && !error && (
        <p className="text-sm text-neutral-500">Loading…</p>
      )}

      {status && (
        <div className="flex flex-col gap-4 rounded-lg border border-neutral-200 p-4 text-sm dark:border-neutral-800">
          <div>
            <p className="text-xs text-neutral-500">
              Endpoint URL (store as <code>forge_endpoint</code>)
            </p>
            <div className="mt-1 flex flex-wrap items-center gap-2">
              <code className="rounded bg-neutral-50 px-2 py-1 text-xs break-all dark:bg-neutral-900">
                {status.endpoint_url}
              </code>
              <button
                type="button"
                onClick={() => void copy(status.endpoint_url, "url")}
                className="rounded border border-neutral-300 px-2 py-1 text-xs dark:border-neutral-700"
              >
                {copied === "url" ? "Copied" : "Copy"}
              </button>
            </div>
          </div>

          {secret && (
            <div className="rounded border border-amber-300 bg-amber-50 p-3 dark:border-amber-800 dark:bg-amber-950">
              <p className="text-xs font-medium text-amber-900 dark:text-amber-100">
                Your secret — shown once. Store it as <code>forge_secret</code>{" "}
                in Zoho now.
              </p>
              <div className="mt-1 flex flex-wrap items-center gap-2">
                <code className="rounded bg-white px-2 py-1 text-xs break-all dark:bg-neutral-900">
                  {secret}
                </code>
                <button
                  type="button"
                  onClick={() => void copy(secret, "secret")}
                  className="rounded bg-neutral-900 px-3 py-1 text-xs font-medium text-white dark:bg-neutral-100 dark:text-neutral-900"
                >
                  {copied === "secret" ? "Copied" : "Copy secret"}
                </button>
              </div>
            </div>
          )}

          <p>
            {status.exists ? (
              <>
                <span className="font-medium text-green-700 dark:text-green-400">
                  Secret in place
                </span>
                <span className="text-neutral-500">
                  {" "}
                  since{" "}
                  {status.created_at
                    ? new Date(status.created_at).toLocaleString()
                    : "—"}
                  {" · "}
                  last outcome received{" "}
                  {status.last_used_at
                    ? new Date(status.last_used_at).toLocaleString()
                    : "never"}
                </span>
              </>
            ) : (
              <span className="font-medium">No secret yet.</span>
            )}
          </p>

          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() => void generate()}
              disabled={busy}
              className="rounded bg-neutral-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-neutral-100 dark:text-neutral-900"
            >
              {busy
                ? "Working…"
                : status.exists
                  ? "Rotate secret"
                  : "Generate secret"}
            </button>
            {status.exists && (
              <button
                type="button"
                onClick={() => void revoke()}
                disabled={busy}
                className="rounded border border-neutral-300 px-3 py-2 text-xs disabled:opacity-50 dark:border-neutral-700"
              >
                Revoke
              </button>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
