-- F6: Zoho Lead out.
--   zoho_connections   one OAuth connection per user; refresh token encrypted by the backend
--   zoho_oauth_states  one-time, short-lived state nonces for the connect flow
--   proposals          Lead fields confirmed by the operator, classifier output, sync state
--   lead_attempts      APPEND-ONLY: every Create Lead press (R2)

create table public.zoho_connections (
  user_id            uuid primary key default auth.uid()
                     references auth.users (id) on delete cascade,
  -- AES-GCM ciphertext (base64: nonce || ciphertext) under TOKEN_ENCRYPTION_KEY.
  refresh_token_enc  text not null,
  api_domain         text not null,
  accounts_url       text not null,
  scopes             text[] not null default '{}',
  connected_at       timestamptz not null default now(),
  last_used_at       timestamptz
);

alter table public.zoho_connections enable row level security;

create policy "zoho_connections: owner can read"
  on public.zoho_connections for select to authenticated using (user_id = auth.uid());
create policy "zoho_connections: owner can insert"
  on public.zoho_connections for insert to authenticated with check (user_id = auth.uid());
create policy "zoho_connections: owner can update"
  on public.zoho_connections for update to authenticated
  using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy "zoho_connections: owner can delete"
  on public.zoho_connections for delete to authenticated using (user_id = auth.uid());

create table public.zoho_oauth_states (
  nonce       text primary key,
  user_id     uuid not null default auth.uid()
              references auth.users (id) on delete cascade,
  expires_at  timestamptz not null default now() + interval '10 minutes'
);

alter table public.zoho_oauth_states enable row level security;

create policy "zoho_oauth_states: owner can read"
  on public.zoho_oauth_states for select to authenticated using (user_id = auth.uid());
create policy "zoho_oauth_states: owner can insert"
  on public.zoho_oauth_states for insert to authenticated with check (user_id = auth.uid());
create policy "zoho_oauth_states: owner can delete"
  on public.zoho_oauth_states for delete to authenticated using (user_id = auth.uid());

alter table public.proposals
  add column lead_fields          jsonb,
  add column lead_classification  jsonb,
  add column zoho_lead_id         text,
  add column lead_sync_state      text not null default 'none'
                                  check (lead_sync_state in ('none', 'created', 'failed')),
  add column submitted_at         timestamptz;

create table public.lead_attempts (
  id               uuid primary key default gen_random_uuid(),
  proposal_id      uuid not null references public.proposals (id) on delete cascade,
  user_id          uuid not null default auth.uid()
                   references auth.users (id) on delete cascade,
  -- SHA-256 of the exact JSON payload sent.
  payload_hash     text not null check (payload_hash ~ '^[0-9a-f]{64}$'),
  response_status  integer,
  zoho_lead_id     text,
  action           text,          -- 'insert' | 'update' from Zoho, when known
  error            text,
  attempted_by     uuid not null default auth.uid(),
  attempted_at     timestamptz not null default now()
);

create index lead_attempts_proposal on public.lead_attempts (proposal_id, attempted_at desc);

alter table public.lead_attempts enable row level security;

create policy "lead_attempts: owner can read"
  on public.lead_attempts for select to authenticated using (user_id = auth.uid());
create policy "lead_attempts: owner can insert"
  on public.lead_attempts for insert to authenticated
  with check (user_id = auth.uid() and attempted_by = auth.uid());
-- No update or delete policy: audit record.

create trigger lead_attempts_append_only
  before update or delete on public.lead_attempts
  for each row execute function public.refuse_change();

comment on table public.lead_attempts is
  'F6 R2 audit: every Create Lead press, with the payload hash and Zoho''s answer. Append-only.';
comment on table public.zoho_connections is
  'F6: per-user Zoho OAuth. refresh_token_enc is AES-GCM under the backend''s TOKEN_ENCRYPTION_KEY.';
