"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { createClient } from "@/lib/supabase/client";

// The deployed URL is public and every account can spend Claude credits, so
// sign-up is switched off after the operator's account exists (Supabase's own
// setting closes the API; this only hides the button). Allowed by default
// for local development.
const ALLOW_SIGNUP = process.env.NEXT_PUBLIC_ALLOW_SIGNUP !== "false";

// Supabase's messages are terse; say what to do next.
function friendly(message: string): string {
  if (/not confirmed/i.test(message)) {
    return "Your email isn't confirmed yet. Open the confirmation link we emailed you, then sign in.";
  }
  if (/invalid login credentials/i.test(message)) {
    return "Wrong email or password, or the account doesn't exist yet.";
  }
  if (/already registered/i.test(message)) {
    return "That email already has an account. Sign in instead.";
  }
  return message;
}

export function SignInForm() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(mode: "signIn" | "signUp") {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const supabase = createClient();
      if (mode === "signUp") {
        const { data, error } = await supabase.auth.signUp({
          email,
          password,
          // Where the confirmation link lands; must be in Supabase's redirect
          // allow-list (Authentication → URL Configuration).
          options: { emailRedirectTo: window.location.origin },
        });
        if (error) {
          setError(friendly(error.message));
          return;
        }
        // Hosted Supabase requires email confirmation: no session yet.
        if (!data.session) {
          setNotice(
            "Account created. Open the confirmation link we just emailed you, then sign in here.",
          );
          return;
        }
      } else {
        const { error } = await supabase.auth.signInWithPassword({
          email,
          password,
        });
        if (error) {
          setError(friendly(error.message));
          return;
        }
      }
      router.refresh();
    } catch (e) {
      // Configuration or network failures: show them, never swallow them.
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form
      className="flex w-full max-w-sm flex-col gap-3"
      onSubmit={(e) => {
        e.preventDefault();
        void submit("signIn");
      }}
    >
      <label className="flex flex-col gap-1 text-sm">
        Email
        <input
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="rounded border border-neutral-300 px-3 py-2 dark:border-neutral-700 dark:bg-neutral-900"
        />
      </label>
      <label className="flex flex-col gap-1 text-sm">
        Password
        <input
          type="password"
          autoComplete="current-password"
          required
          minLength={6}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="rounded border border-neutral-300 px-3 py-2 dark:border-neutral-700 dark:bg-neutral-900"
        />
      </label>
      {error && (
        <p role="alert" className="text-sm text-red-600 dark:text-red-400">
          {error}
        </p>
      )}
      {notice && (
        <p
          role="status"
          className="rounded border border-green-300 bg-green-50 px-3 py-2 text-sm text-green-800 dark:border-green-800 dark:bg-green-950 dark:text-green-200"
        >
          {notice}
        </p>
      )}
      <div className="flex gap-2">
        <button
          type="submit"
          disabled={busy}
          className="rounded bg-neutral-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-neutral-100 dark:text-neutral-900"
        >
          Sign in
        </button>
        {ALLOW_SIGNUP && (
          <button
            type="button"
            disabled={busy}
            onClick={() => void submit("signUp")}
            className="rounded border border-neutral-300 px-4 py-2 text-sm font-medium disabled:opacity-50 dark:border-neutral-700"
          >
            Create account
          </button>
        )}
      </div>
    </form>
  );
}
