-- F8: outcomes in, and the learning index.
--   integration_secrets  one per user; sha256 of the bearer secret Zoho sends
--   proposal_outcomes    APPEND-ONLY: every outcome received (R2)
--   outcome_queue        outcomes whose Upwork job ID matched no proposal (R8: held, never dropped)
--   rag_index            one row per proposal with an outcome; derived, rebuildable (ADR-003)
--   proposals            + outcome_recorded_at
--   profiles             + stale_submitted_days (the "follow up on Upwork?" nudge age)
--   record_outcome()     the inbound path: SECURITY DEFINER, executable by anon only
--   resolve_queued_outcome(), rebuild_rag_index()  the operator's two actions (authenticated)
-- The inbound call carries no user JWT (Zoho has none), so the tenant is
-- resolved from the secret hash inside record_outcome(); every other table
-- stays behind RLS as before. See docs/F8_OUTCOMES.md and ADR-005.

-- --- integration_secrets --------------------------------------------------------

create table public.integration_secrets (
  user_id       uuid primary key default auth.uid()
                references auth.users (id) on delete cascade,
  -- sha256 hex of the plaintext shown once in Settings. Never the plaintext.
  secret_hash   text not null unique check (secret_hash ~ '^[0-9a-f]{64}$'),
  created_at    timestamptz not null default now(),
  last_used_at  timestamptz
);

alter table public.integration_secrets enable row level security;

create policy "integration_secrets: owner can read"
  on public.integration_secrets for select to authenticated using (user_id = auth.uid());
create policy "integration_secrets: owner can insert"
  on public.integration_secrets for insert to authenticated with check (user_id = auth.uid());
create policy "integration_secrets: owner can update"
  on public.integration_secrets for update to authenticated
  using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy "integration_secrets: owner can delete"
  on public.integration_secrets for delete to authenticated using (user_id = auth.uid());

-- --- proposal_outcomes (append-only) --------------------------------------------

create table public.proposal_outcomes (
  id            uuid primary key default gen_random_uuid(),
  proposal_id   uuid not null references public.proposals (id) on delete cascade,
  user_id       uuid not null references auth.users (id) on delete cascade,
  outcome       text not null check (outcome in ('won', 'lost', 'withdrawn')),
  lost_reason   text check (lost_reason in ('hired_other', 'job_closed', 'junk_lead', 'not_qualified')),
  decided_at    timestamptz,
  zoho_lead_id  text,
  -- Allow-listed Lead values as received (docs/ZOHO_INTEGRATION.md). Validated
  -- by the backend before it gets here; never contains client identity.
  lead          jsonb not null default '{}'::jsonb,
  source        text not null check (source in ('zoho', 'manual_match')),
  received_at   timestamptz not null default now(),
  constraint proposal_outcomes_reason_pairing
    check ((outcome = 'lost') = (lost_reason is not null))
);

create index proposal_outcomes_proposal
  on public.proposal_outcomes (proposal_id, received_at desc);

alter table public.proposal_outcomes enable row level security;

create policy "proposal_outcomes: owner can read"
  on public.proposal_outcomes for select to authenticated using (user_id = auth.uid());
-- No insert policy: rows are written only by the SECURITY DEFINER functions below.
-- No update or delete policy: audit record.

create trigger proposal_outcomes_append_only
  before update or delete on public.proposal_outcomes
  for each row execute function public.refuse_change();

-- --- outcome_queue ----------------------------------------------------------------

create table public.outcome_queue (
  id                    uuid primary key default gen_random_uuid(),
  user_id               uuid not null references auth.users (id) on delete cascade,
  upwork_job_id         text not null,
  zoho_lead_id          text,
  payload               jsonb not null,
  received_at           timestamptz not null default now(),
  resolved_at           timestamptz,
  resolved_proposal_id  uuid references public.proposals (id) on delete set null,
  dismissed_at          timestamptz
);

create index outcome_queue_open
  on public.outcome_queue (user_id, received_at desc)
  where resolved_at is null and dismissed_at is null;

alter table public.outcome_queue enable row level security;

create policy "outcome_queue: owner can read"
  on public.outcome_queue for select to authenticated using (user_id = auth.uid());
create policy "outcome_queue: owner can update"
  on public.outcome_queue for update to authenticated
  using (user_id = auth.uid()) with check (user_id = auth.uid());
-- Inserted only by record_outcome().

-- --- rag_index --------------------------------------------------------------------

create table public.rag_index (
  proposal_id       uuid primary key references public.proposals (id) on delete cascade,
  user_id           uuid not null references auth.users (id) on delete cascade,
  outcome           text not null check (outcome in ('won', 'lost', 'withdrawn')),
  lost_reason       text,
  industry          text,
  job_type          text,
  tools             text,
  rate_type         text,
  hourly_rate       numeric(10,2),
  fixed_price       numeric(12,2),
  budget            numeric(12,2),
  budget_band       text,
  quote_model       text,
  quote_amount      numeric(12,2),
  job_title         text,
  skills            text[] not null default '{}',
  -- The operator's own words: the copied (approved) cover letter, trimmed.
  proposal_excerpt  text,
  decided_at        timestamptz,
  archived          boolean not null default false,
  indexed_at        timestamptz not null default now()
);

create index rag_index_user_industry on public.rag_index (user_id, industry) where not archived;

alter table public.rag_index enable row level security;

create policy "rag_index: owner can read"
  on public.rag_index for select to authenticated using (user_id = auth.uid());
create policy "rag_index: owner can archive"
  on public.rag_index for update to authenticated
  using (user_id = auth.uid()) with check (user_id = auth.uid());
-- The owner may change only `archived`; everything else is derived.
revoke update on public.rag_index from authenticated;
grant update (archived) on public.rag_index to authenticated;

-- --- proposals / profiles -------------------------------------------------------

alter table public.proposals add column outcome_recorded_at timestamptz;

alter table public.profiles
  add column stale_submitted_days integer not null default 14
  check (stale_submitted_days between 1 and 365);

-- --- helpers (internal; not callable through the API) ------------------------------

create or replace function public.forge_budget_band(p_rate_type text, p_amount numeric)
returns text
language sql
immutable
as $$
  select case
    when p_amount is null then null
    when lower(coalesce(p_rate_type, '')) = 'hourly' then
      case when p_amount < 30 then 'under $30/h'
           when p_amount < 75 then '$30–75/h'
           else 'over $75/h' end
    else
      case when p_amount < 1000 then 'under $1k'
           when p_amount < 10000 then '$1k–10k'
           else 'over $10k' end
  end
$$;

-- Writes (or rewrites) one proposal's rag_index row from what the client saw:
-- the version of the latest approval, the parsed job, and the Lead values.
create or replace function public._forge_index_proposal(
  p_user uuid, p_proposal uuid, p_outcome text, p_reason text,
  p_lead jsonb, p_decided timestamptz
) returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  v_sections  jsonb;
  v_analysis  jsonb;
  v_fields    jsonb;
  v_class     jsonb;
  v_rate      text;
  v_hourly    numeric;
  v_fixed     numeric;
  v_budget    numeric;
  v_qmodel    text;
  v_qamount   numeric;
  v_skills    text[];
begin
  select dv.sections into v_sections
    from proposal_approvals pa
    join draft_versions dv on dv.id = pa.draft_version_id
   where pa.proposal_id = p_proposal
   order by pa.approved_at desc
   limit 1;

  select jp.analysis, p.lead_fields, p.lead_classification -> 'result'
    into v_analysis, v_fields, v_class
    from proposals p
    join job_posts jp on jp.id = p.job_post_id
   where p.id = p_proposal;

  select coalesce(array_agg(x), '{}') into v_skills
    from jsonb_array_elements_text(coalesce(v_analysis -> 'parsed' -> 'skills', '[]'::jsonb)) x;

  v_rate := coalesce(
    p_lead ->> 'Rate_Type',
    case lower(v_analysis -> 'parsed' -> 'engagement' ->> 'payment_type')
      when 'hourly' then 'Hourly' when 'fixed' then 'Fixed' end);
  v_hourly  := nullif(p_lead ->> 'Hourly_Rate', '')::numeric;
  v_fixed   := nullif(p_lead ->> 'Upwork_Fixed_Price', '')::numeric;
  v_budget  := nullif(p_lead ->> 'Budget', '')::numeric;
  v_qmodel  := v_sections -> 'quote' ->> 'model';
  v_qamount := nullif(v_sections -> 'quote' ->> 'amount', '')::numeric;
  if v_hourly is null and v_qmodel = 'hourly' then v_hourly := v_qamount; end if;
  if v_fixed  is null and v_qmodel = 'fixed'  then v_fixed  := v_qamount; end if;

  insert into rag_index (
    proposal_id, user_id, outcome, lost_reason, industry, job_type, tools,
    rate_type, hourly_rate, fixed_price, budget, budget_band,
    quote_model, quote_amount, job_title, skills, proposal_excerpt,
    decided_at, indexed_at
  ) values (
    p_proposal, p_user, p_outcome, p_reason,
    coalesce(p_lead ->> 'Industry', v_fields ->> 'industry', v_class ->> 'industry'),
    coalesce(p_lead ->> 'Job_Type', v_fields ->> 'job_type', v_class ->> 'job_type'),
    coalesce(p_lead ->> 'Tools', v_fields ->> 'tools', v_class ->> 'tools'),
    v_rate, v_hourly, v_fixed, v_budget,
    public.forge_budget_band(v_rate, coalesce(v_budget, v_fixed, v_hourly)),
    v_qmodel, v_qamount,
    v_analysis -> 'parsed' ->> 'title', v_skills,
    left(v_sections ->> 'cover_letter', 1500),
    p_decided, now()
  )
  on conflict (proposal_id) do update set
    outcome = excluded.outcome, lost_reason = excluded.lost_reason,
    industry = excluded.industry, job_type = excluded.job_type, tools = excluded.tools,
    rate_type = excluded.rate_type, hourly_rate = excluded.hourly_rate,
    fixed_price = excluded.fixed_price, budget = excluded.budget,
    budget_band = excluded.budget_band, quote_model = excluded.quote_model,
    quote_amount = excluded.quote_amount, job_title = excluded.job_title,
    skills = excluded.skills, proposal_excerpt = excluded.proposal_excerpt,
    decided_at = excluded.decided_at, indexed_at = now();
end;
$$;

-- Appends the outcome, moves the proposal's status, and (re)indexes — one transaction.
create or replace function public._forge_apply_outcome(
  p_user uuid, p_proposal uuid, p_payload jsonb, p_source text
) returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_outcome  text := p_payload ->> 'outcome';
  v_reason   text := nullif(p_payload ->> 'lost_reason', '');
  v_lead     jsonb := coalesce(p_payload -> 'lead', '{}'::jsonb);
  v_decided  timestamptz := nullif(p_payload ->> 'decided_at', '')::timestamptz;
  v_last     record;
  v_label    text;
begin
  select outcome, lost_reason into v_last
    from proposal_outcomes
   where proposal_id = p_proposal
   order by received_at desc
   limit 1;

  v_label := v_outcome || case when v_reason is not null then ' (' || v_reason || ')' else '' end;

  if found and v_last.outcome = v_outcome
     and coalesce(v_last.lost_reason, '') = coalesce(v_reason, '') then
    return jsonb_build_object(
      'code', 200, 'message', 'Already recorded as ' || v_label || ' in Proposal Forge',
      'proposal_id', p_proposal, 'outcome', v_outcome,
      'indexed', true, 'queued', false, 'duplicate', true);
  end if;

  insert into proposal_outcomes
    (proposal_id, user_id, outcome, lost_reason, decided_at, zoho_lead_id, lead, source)
  values
    (p_proposal, p_user, v_outcome, v_reason, v_decided, p_payload ->> 'zoho_lead_id', v_lead, p_source);

  update proposals
     set status = v_outcome, outcome_recorded_at = now()
   where id = p_proposal;

  perform public._forge_index_proposal(p_user, p_proposal, v_outcome, v_reason, v_lead, v_decided);

  return jsonb_build_object(
    'code', 200, 'message', 'Recorded ' || v_label || ' in Proposal Forge',
    'proposal_id', p_proposal, 'outcome', v_outcome,
    'indexed', true, 'queued', false, 'duplicate', false);
end;
$$;

revoke all on function public.forge_budget_band(text, numeric) from public, anon, authenticated;
revoke all on function public._forge_index_proposal(uuid, uuid, text, text, jsonb, timestamptz)
  from public, anon, authenticated;
revoke all on function public._forge_apply_outcome(uuid, uuid, jsonb, text)
  from public, anon, authenticated;

-- --- record_outcome: the inbound path (anon) ---------------------------------------

-- Called by the backend with the anon key and no user JWT. The payload has
-- already passed the backend's validation (contract, allow-list). Resolves
-- the tenant from the secret hash; 401 / 202 / 200 as jsonb {code, message, ...}.
create or replace function public.record_outcome(p_secret_hash text, p_payload jsonb)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_user      uuid;
  v_proposal  uuid;
  v_job_id    text := p_payload ->> 'upwork_job_id';
begin
  select user_id into v_user from integration_secrets where secret_hash = p_secret_hash;
  if not found then
    return jsonb_build_object(
      'code', 401,
      'message', 'Proposal Forge rejected the integration secret — regenerate it in settings');
  end if;
  update integration_secrets set last_used_at = now() where user_id = v_user;

  select p.id into v_proposal
    from proposals p
    join job_posts jp on jp.id = p.job_post_id
   where p.user_id = v_user and jp.upwork_job_id = v_job_id
   limit 1;

  if not found then
    insert into outcome_queue (user_id, upwork_job_id, zoho_lead_id, payload)
    values (v_user, v_job_id, p_payload ->> 'zoho_lead_id', p_payload);
    return jsonb_build_object(
      'code', 202,
      'message', 'No matching proposal — held for review in Proposal Forge',
      'indexed', false, 'queued', true, 'duplicate', false);
  end if;

  return public._forge_apply_outcome(v_user, v_proposal, p_payload, 'zoho');
end;
$$;

revoke all on function public.record_outcome(text, jsonb) from public, authenticated;
grant execute on function public.record_outcome(text, jsonb) to anon;

-- --- the operator's two actions (authenticated) ----------------------------------------

-- Match a queued outcome to one of the caller's proposals.
create or replace function public.resolve_queued_outcome(p_queue_id uuid, p_proposal_id uuid)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_user    uuid := auth.uid();
  v_queue   record;
  v_result  jsonb;
begin
  if v_user is null then
    raise exception 'not signed in' using errcode = 'insufficient_privilege';
  end if;
  select * into v_queue from outcome_queue
   where id = p_queue_id and user_id = v_user
     and resolved_at is null and dismissed_at is null;
  if not found then
    raise exception 'queued outcome not found' using errcode = 'no_data_found';
  end if;
  if not exists (select 1 from proposals where id = p_proposal_id and user_id = v_user) then
    raise exception 'proposal not found' using errcode = 'no_data_found';
  end if;
  v_result := public._forge_apply_outcome(v_user, p_proposal_id, v_queue.payload, 'manual_match');
  update outcome_queue
     set resolved_at = now(), resolved_proposal_id = p_proposal_id
   where id = p_queue_id;
  return v_result;
end;
$$;

-- Rebuild the caller's rag_index from history (after a matcher or mapping change).
create or replace function public.rebuild_rag_index()
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
  v_user  uuid := auth.uid();
  v_row   record;
  v_n     integer := 0;
begin
  if v_user is null then
    raise exception 'not signed in' using errcode = 'insufficient_privilege';
  end if;
  for v_row in
    select distinct on (proposal_id) proposal_id, outcome, lost_reason, lead, decided_at
      from proposal_outcomes
     where user_id = v_user
     order by proposal_id, received_at desc
  loop
    perform public._forge_index_proposal(
      v_user, v_row.proposal_id, v_row.outcome, v_row.lost_reason, v_row.lead, v_row.decided_at);
    v_n := v_n + 1;
  end loop;
  return v_n;
end;
$$;

revoke all on function public.resolve_queued_outcome(uuid, uuid) from public, anon;
grant execute on function public.resolve_queued_outcome(uuid, uuid) to authenticated;
revoke all on function public.rebuild_rag_index() from public, anon;
grant execute on function public.rebuild_rag_index() to authenticated;

comment on table public.proposal_outcomes is
  'F8 R2 audit: every outcome received from Zoho (or matched from the queue). Append-only.';
comment on table public.outcome_queue is
  'F8 R8: outcomes whose Upwork job ID matched no proposal. Held until matched or dismissed.';
comment on table public.rag_index is
  'ADR-003: one row per proposal with an outcome, derived from history + the copied version. rebuild_rag_index() regenerates it.';
comment on function public.record_outcome(text, jsonb) is
  'F8 inbound path. The only function the anon role may execute; tenant resolved from the secret hash.';
