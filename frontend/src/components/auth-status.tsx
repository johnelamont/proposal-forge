// Server Component: reads the session cookie and renders either the signed-in
// state or the sign-in form. Kept separate from the page so the static shell
// can prerender while this part streams (Next.js cacheComponents).
import { SignInForm } from "@/components/sign-in-form";
import { SignOutButton } from "@/components/sign-out-button";
import { createClient } from "@/lib/supabase/server";

export async function AuthStatus() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    return <SignInForm />;
  }

  return (
    <section className="flex flex-col items-center gap-4">
      <p className="text-sm">
        Signed in as <span className="font-medium">{user.email}</span>
      </p>
      <SignOutButton />
    </section>
  );
}
