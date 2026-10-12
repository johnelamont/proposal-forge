"use client";

// Settings → Zoho: connect (consent at Zoho, token stored encrypted), status,
// disconnect. When Zoho sends the browser back here with ?code&state, this
// component completes the exchange under the signed-in user's session.

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { zohoApi } from "@/lib/api";
import type { ConnectionStatus } from "@/lib/types/zoho";

export function ZohoSettings() {
  const router = useRouter();
  const params = useSearchParams();
  const code = params.get("code");
  const state = params.get("state");
  // Zoho reports a declined or failed consent in the URL; read it directly.
  const zohoError = params.get("error");
  const [status, setStatus] = useState<ConnectionStatus | null>(null);
  const [error, setError] = useState<string | null>(
    zohoError ? `Zoho reported: ${zohoError}. Nothing was connected.` : null,
  );
  const [notice, setNotice] = useState<string | null>(null);
  // Busy from the start when we arrive with a code to exchange.
  const [busy, setBusy] = useState(Boolean(code && state));
  const completedOnce = useRef(false);

  useEffect(() => {
    if (zohoError) {
      router.replace("/settings/zoho");
      return;
    }
    if (code && state && !completedOnce.current) {
      completedOnce.current = true;
      zohoApi
        .complete(code, state)
        .then((s) => {
          setStatus(s);
          setNotice("Zoho connected.");
        })
        .catch((e: unknown) =>
          setError(e instanceof Error ? e.message : "Could not complete."),
        )
        .finally(() => {
          setBusy(false);
          router.replace("/settings/zoho"); // drop the one-time code from the URL
        });
      return;
    }
    zohoApi
      .status()
      .then(setStatus)
      .catch((e: unknown) =>
        setError(e instanceof Error ? e.message : "Could not load."),
      );
  }, [code, state, zohoError, router]);

  async function connect() {
    setError(null);
    setNotice(null);
    setBusy(true);
    try {
      const start = await zohoApi.connect();
      window.location.assign(start.authorize_url); // off to Zoho's consent page
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not start.");
      setBusy(false);
    }
  }

  async function disconnect() {
    if (
      !window.confirm(
        "Disconnect Zoho? Lead creation will stop until you reconnect.",
      )
    )
      return;
    setError(null);
    setBusy(true);
    try {
      await zohoApi.disconnect();
      setStatus(await zohoApi.status());
      setNotice("Disconnected. The token was revoked at Zoho.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not disconnect.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="flex flex-col gap-5">
      <nav className="flex gap-4 text-sm">
        <Link href="/" className="underline">
          Home
        </Link>
      </nav>
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Zoho CRM</h1>
        <p className="mt-1 text-sm text-neutral-600 dark:text-neutral-400">
          We need to connect you to Zoho CRM to create and update Leads; the app
          never reads. The token is encrypted and stored against your account.
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

      {status && !status.configured && (
        <p className="text-sm text-amber-800 dark:text-amber-200">
          The server has no Zoho client configured (ZOHO_CLIENT_ID / SECRET /
          TOKEN_ENCRYPTION_KEY). See docs/DEPLOYMENT.md.
        </p>
      )}

      {status?.configured && (
        <div className="rounded-lg border border-neutral-200 p-4 text-sm dark:border-neutral-800">
          {status.connected ? (
            <div className="flex flex-col gap-3">
              <p>
                <span className="font-medium text-green-700 dark:text-green-400">
                  Connected
                </span>
                {status.connected_at && (
                  <span className="text-neutral-500">
                    {" "}
                    since {new Date(status.connected_at).toLocaleString()}
                  </span>
                )}
                {status.last_used_at && (
                  <span className="text-neutral-500">
                    {" "}
                    · last Lead {new Date(status.last_used_at).toLocaleString()}
                  </span>
                )}
              </p>
              <p className="text-xs text-neutral-500">
                Permissions: {status.scopes.join(", ") || "—"}
              </p>
              <div>
                <button
                  type="button"
                  onClick={() => void disconnect()}
                  disabled={busy}
                  className="rounded border border-neutral-300 px-3 py-1.5 text-xs disabled:opacity-50 dark:border-neutral-700"
                >
                  Disconnect
                </button>
              </div>
            </div>
          ) : (
            <div className="flex flex-col gap-3">
              <p>
                <span className="font-medium">Not connected.</span>{" "}
                <span className="text-neutral-500">
                  You&apos;ll be sent to Zoho to sign in and approve, then
                  brought back here.
                </span>
              </p>
              <div>
                <button
                  type="button"
                  onClick={() => void connect()}
                  disabled={busy}
                  className="rounded bg-neutral-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-neutral-100 dark:text-neutral-900"
                >
                  {busy ? "Connecting…" : "Connect to Zoho"}
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
