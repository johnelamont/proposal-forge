// Reads the public Supabase settings and fails loudly if they are missing,
// rather than letting the client library throw a less helpful error later.
//
// The variables must be referenced literally (process.env.NEXT_PUBLIC_X), not
// looked up by name: Next.js inlines NEXT_PUBLIC_* into browser bundles by
// string replacement, and a dynamic lookup is empty in the browser.

const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

function required(name: string, value: string | undefined): string {
  if (!value) {
    throw new Error(
      `${name} is not set. Copy frontend/.env.example to frontend/.env.local and fill it in.`,
    );
  }
  return value;
}

export function supabaseEnv() {
  return {
    url: required("NEXT_PUBLIC_SUPABASE_URL", url),
    anonKey: required("NEXT_PUBLIC_SUPABASE_ANON_KEY", anonKey),
  };
}
