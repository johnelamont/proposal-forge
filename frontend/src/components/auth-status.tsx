// Server Component: reads the session cookie and renders either the signed-in
// state or the sign-in form. Kept separate from the page so the static shell
// can prerender while this part streams (Next.js cacheComponents).
import Link from "next/link";
import { connection } from "next/server";

import { RecentJobs } from "@/components/jobs/recent-jobs";
import { SignInForm } from "@/components/sign-in-form";
import { SignOutButton } from "@/components/sign-out-button";
import { createClient } from "@/lib/supabase/server";

export async function AuthStatus() {
  // A session check is request-time by definition. Declaring that up front
  // keeps Next.js from trying to prerender this subtree (the Supabase client
  // reads the clock as it is constructed, which prerendering rejects).
  await connection();

  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    return <SignInForm />;
  }

  return (
    <section className="flex w-full flex-col items-center gap-6">
      <RecentJobs />
      <nav className="flex gap-4 text-sm">
        <Link href="/history" className="underline">
          Work history
        </Link>
      </nav>
      <p className="text-sm">
        Signed in as <span className="font-medium">{user.email}</span>
      </p>
      <SignOutButton />
    </section>
  );
}
