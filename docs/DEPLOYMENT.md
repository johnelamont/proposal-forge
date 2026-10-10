# Deployment

Three hosted pieces, all on free tiers, plus DNS on `techledger.ai`:

| Piece | Host | Public name | Deploys how |
|---|---|---|---|
| Frontend (Next.js) | Vercel | `https://upworkforge.techledger.ai` | Vercel's GitHub integration on push to `main` |
| Backend (FastAPI) | Fly.io, app `upworkforge-api` | `https://api.upworkforge.techledger.ai` | `.github/workflows/deploy-backend.yml` on push to `main` touching `backend/`, or `fly deploy` from `backend/` |
| Database + auth | Supabase hosted project `gmlxibzldwomwclzxbhc` (us-east-1) | `https://gmlxibzldwomwclzxbhc.supabase.co` (never typed by a person) | `supabase db push` from the repo root |

Local development is unchanged ([README → Development](../README.md#development)); the local stack is a test bed, the hosted stack is where real data lives.

## One-time setup

Steps marked **(you)** open a browser login and have to be done by the operator; the rest can be scripted.

### 1. Supabase

1. **(you)** Create an account at supabase.com and a project (region: the one nearest you; it cannot be changed later). Choose a strong database password and keep it — it is needed for the data move.
2. **(you)** `supabase login` (opens a browser), then from the repo root: `supabase link --project-ref <ref>`.
3. `supabase db push` — applies every migration in `supabase/migrations/` to the hosted database. Repeat after each merged migration (it only applies new ones).
4. **(you)** In the dashboard, Authentication → URL Configuration: Site URL `https://upworkforge.techledger.ai`; Redirect URLs `https://upworkforge.techledger.ai/**` and `https://upworkforge.vercel.app/**`. Authentication → Providers → Email: *Confirm email* **off** — Supabase's built-in mailer allows only a few auth emails per hour (the first attempt hit "email rate limit exceeded"), and with sign-ups closed right after the operator's account exists, confirmation protects nothing.
5. Note from Project Settings → API: the project URL and the **anon / publishable key**; from Project Settings → Database: the *Session pooler* connection string.

### 2. Fly.io (backend)

1. **(you)** `scoop install flyctl`, create an account, `fly auth login`.
2. From `backend/`: `fly launch --no-deploy --copy-config --name upworkforge-api --region iad` (accepts the committed `fly.toml`; say no to a Postgres database — Supabase is the database).
3. Secrets (never in files). `ANTHROPIC_API_KEY` must be a **workspace-scoped** Console key (`sk-ant-api03-…`); an organisation-scoped key (`sk-ant-usr-…`) is rejected with a 400 asking for an `anthropic-workspace-id` header. A dedicated workspace for the app keeps its spend on its own line.
   ```powershell
   fly secrets set ANTHROPIC_API_KEY=sk-ant-... SUPABASE_URL=https://<ref>.supabase.co SUPABASE_ANON_KEY=<anon key> CORS_ORIGINS='["https://upworkforge.techledger.ai"]' ANTHROPIC_MODEL=claude-opus-5-5
   ```
4. `fly deploy --ha=false` → check `https://upworkforge-api.fly.dev/health`. (Without `--ha=false` Fly creates two machines for high availability; `fly scale count 1` trims it back. One is plenty for a single operator.)
5. Custom name: `fly certs add api.upworkforge.techledger.ai`, then the DNS record below (the CNAME works; Fly's suggested A/AAAA records are an alternative). `fly certs check api.upworkforge.techledger.ai` until it reports issued.
6. For automatic deploys: `fly tokens create deploy -x 999999h` and add it as the GitHub repository secret `FLY_API_TOKEN`.

### 3. Vercel (frontend)

1. **(you)** `vercel login`. The project `upworkforge` was created from the CLI (`vercel link --project upworkforge` inside `frontend/`); the first deploys were `vercel deploy --prod` from that folder. For automatic deploys on push, in the dashboard: Settings → General → **Root Directory `frontend`**, then Settings → Git → connect `johnelamont/proposal-forge`. Note: `vercel link` appends `.vercel` and `.env*` to `frontend/.gitignore` and a `VERCEL_OIDC_TOKEN` line to `.env.local`; remove them (the `.env*` line would re-hide `.env.example`).
2. Environment variables (Production): `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `NEXT_PUBLIC_API_URL=https://api.upworkforge.techledger.ai`, `NEXT_PUBLIC_ALLOW_SIGNUP=true` (for the first sign-up only — see step 5). From a terminal: `vercel env add NAME production --value "…" --no-sensitive` — the flags matter, the CLI otherwise waits on prompts and silently stores nothing. `NEXT_PUBLIC_*` values are baked in at build time, so changing one needs a redeploy (`vercel deploy --prod`).
3. Deploy. Then Settings → Domains → add `upworkforge.techledger.ai`; Vercel shows the record to create.

### 4. DNS on `techledger.ai`

| Type | Name | Value |
|---|---|---|
| CNAME | `upworkforge` | `cname.vercel-dns.com` |
| CNAME | `api.upworkforge` | `upworkforge-api.fly.dev` |

Certificates are issued automatically by both hosts once the records resolve (minutes to an hour). **On Cloudflare the records must be DNS only (grey cloud), not proxied**: behind Cloudflare's proxy Fly cannot validate its certificate and TLS is terminated twice.

### 5. Your account, then close the door

1. Open `https://upworkforge.techledger.ai`, **Create account** with your email and sign in (no confirmation email with *Confirm email* off).
2. **Turn sign-ups off** — the URL is public and every account can spend Claude credits:
   - Vercel: set `NEXT_PUBLIC_ALLOW_SIGNUP=false` and redeploy (hides the button).
   - Supabase dashboard: Authentication → Providers → Email → *Allow new users to sign up* off (closes the API too).
3. Add the app to your phone's home screen (Share → Add to Home Screen).

### 6. Move your local data (optional, once)

With the local stack running and your hosted account created:

```powershell
uv run --directory backend python ../scripts/migrate_local_to_cloud.py --cloud-url "<session pooler string>" --cloud-user-id <your hosted user id> --dry-run
```

Drop `--dry-run` to run it. It copies `work_history` and `job_posts` rows, rewriting the owner to your hosted account. Auth internals are not copied.

## Day to day

- Merge to `main` → Vercel redeploys the frontend (Git connection confirmed working 2026-10-09); the Fly workflow redeploys the backend when `backend/` changed (`FLY_API_TOKEN` is set).
- New migration merged → `supabase db push` from the repo root (additive; never resets).
- Secrets change → `fly secrets set …` (backend) or Vercel env settings + redeploy (frontend).
- Supabase free projects pause after a week without traffic; signing in wakes them. If that becomes a nuisance, a weekly ping of the API URL from a Vercel cron is the fix noted in ARCHITECTURE.md.

## Checks after a deploy

- `https://api.upworkforge.techledger.ai/health` → `{"status":"ok","environment":"production"}`
- Sign in on the phone; paste a job; the review appears; Work history loads.
- Vercel and Fly dashboards show the deploy green; `fly logs` for backend errors.
