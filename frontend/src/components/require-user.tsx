// Server Component: renders children only for a signed-in user; otherwise
// sends them home to sign in. Wrap in <Suspense> where used.
import { redirect } from "next/navigation";
import { connection } from "next/server";

import { createClient } from "@/lib/supabase/server";

export async function RequireUser({ children }: { children: React.ReactNode }) {
  await connection();
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/");
  return <>{children}</>;
}
