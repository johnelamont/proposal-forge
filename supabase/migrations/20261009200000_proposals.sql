-- F3 (proposal drafting) and F4 (price quote), with the R1/R2 audit trail in
-- the same migration as the feature:
--   profiles           the operator's positioning, rates, greeting, sign-off
--   proposals          one per job post; status and pointer to the current draft
--   draft_versions     APPEND-ONLY: every draft, edit and refine is a new row
--   proposal_approvals APPEND-ONLY: every Copy is an approval of one version
-- Append-only is enforced twice: no update/delete RLS policies, and a trigger
-- that refuses UPDATE/DELETE even for roles that bypass RLS.

-- --- profiles ---------------------------------------------------------------

create table public.profiles (
  user_id              uuid primary key default auth.uid()
                       references auth.users (id) on delete cascade,
  signature_name       text not null default '',
  positioning          text not null default '',
  greeting             text not null default 'Hi,',
  sign_off             text not null default 'Kind Regards,',
  tone_notes           text not null default '',
  -- Phrases the draft must never claim about the operator, e.g. "Zoho Partner".
  never_claim          text[] not null default '{}',
  default_hourly_rate  numeric(10,2),
  fixed_price_range    text,
  created_at           timestamptz not null default now(),
  updated_at           timestamptz not null default now()
);

create trigger profiles_set_updated_at
  before update on public.profiles
  for each row execute function public.set_updated_at();

alter table public.profiles enable row level security;

create policy "profiles: owner can read"
  on public.profiles for select to authenticated using (user_id = auth.uid());
create policy "profiles: owner can insert"
  on public.profiles for insert to authenticated with check (user_id = auth.uid());
create policy "profiles: owner can update"
  on public.profiles for update to authenticated
  using (user_id = auth.uid()) with check (user_id = auth.uid());

-- --- proposals --------------------------------------------------------------

create table public.proposals (
  id                   uuid primary key default gen_random_uuid(),
  user_id              uuid not null default auth.uid()
                       references auth.users (id) on delete cascade,
  job_post_id          uuid not null references public.job_posts (id) on delete cascade,
  status               text not null default 'draft'
                       check (status in ('draft', 'submitted', 'won', 'lost', 'withdrawn')),
  -- Questions found on Upwork's apply form that the job post did not show.
  extra_questions      jsonb not null default '[]'::jsonb,
  current_version_id   uuid,
  created_at           timestamptz not null default now(),
  updated_at           timestamptz not null default now(),
  constraint proposals_one_per_job unique (user_id, job_post_id)
);

create trigger proposals_set_updated_at
  before update on public.proposals
  for each row execute function public.set_updated_at();

alter table public.proposals enable row level security;

create policy "proposals: owner can read"
  on public.proposals for select to authenticated using (user_id = auth.uid());
create policy "proposals: owner can insert"
  on public.proposals for insert to authenticated with check (user_id = auth.uid());
create policy "proposals: owner can update"
  on public.proposals for update to authenticated
  using (user_id = auth.uid()) with check (user_id = auth.uid());

-- --- draft_versions (append-only) ---------------------------------------------

create table public.draft_versions (
  id            uuid primary key default gen_random_uuid(),
  proposal_id   uuid not null references public.proposals (id) on delete cascade,
  user_id       uuid not null default auth.uid()
                references auth.users (id) on delete cascade,
  version       integer not null,
  -- 'ai' full draft, 'refine' one section rewritten by Claude,
  -- 'edit' one section typed by the operator, 'manual' written from scratch.
  source        text not null check (source in ('ai', 'refine', 'edit', 'manual')),
  -- Sections (backend/app/models/proposal.py): cover_letter, answers[], quote.
  sections      jsonb not null,
  -- Model, confidence, warnings, or the failure that left a section empty.
  ai_meta       jsonb,
  created_at    timestamptz not null default now(),
  constraint draft_versions_numbering unique (proposal_id, version)
);

create index draft_versions_proposal on public.draft_versions (proposal_id, version);

alter table public.proposals
  add constraint proposals_current_version_fk
  foreign key (current_version_id) references public.draft_versions (id);

alter table public.draft_versions enable row level security;

create policy "draft_versions: owner can read"
  on public.draft_versions for select to authenticated using (user_id = auth.uid());
create policy "draft_versions: owner can insert"
  on public.draft_versions for insert to authenticated with check (user_id = auth.uid());
-- No update or delete policy: versions are history.

-- --- proposal_approvals (append-only) ------------------------------------------

create table public.proposal_approvals (
  id                 uuid primary key default gen_random_uuid(),
  proposal_id        uuid not null references public.proposals (id) on delete cascade,
  draft_version_id   uuid not null references public.draft_versions (id),
  user_id            uuid not null default auth.uid()
                     references auth.users (id) on delete cascade,
  -- Which part was copied: one section, or everything at once.
  section            text not null
                     check (section in ('cover_letter', 'answer', 'quote', 'all')),
  section_index      integer,
  -- SHA-256 of exactly the text that went to the clipboard.
  content_hash       text not null check (content_hash ~ '^[0-9a-f]{64}$'),
  approved_by        uuid not null default auth.uid(),
  approved_at        timestamptz not null default now()
);

create index proposal_approvals_proposal
  on public.proposal_approvals (proposal_id, approved_at desc);

alter table public.proposal_approvals enable row level security;

create policy "proposal_approvals: owner can read"
  on public.proposal_approvals for select to authenticated using (user_id = auth.uid());
create policy "proposal_approvals: owner can insert"
  on public.proposal_approvals for insert to authenticated
  with check (user_id = auth.uid() and approved_by = auth.uid());
-- No update or delete policy: approvals are an audit record.

-- --- append-only enforcement ---------------------------------------------------

-- Refuses UPDATE and DELETE on audit tables. The one exception is a
-- deliberate purge (e.g. deleting the operator's account, which cascades):
-- an admin session sets `set app.allow_purge = 'on'` first. The API never
-- sets it, and RLS gives application roles no delete path anyway.
create or replace function public.refuse_change()
returns trigger
language plpgsql
as $$
begin
  if tg_op = 'DELETE'
     and coalesce(current_setting('app.allow_purge', true), 'off') = 'on' then
    return old;
  end if;
  raise exception '% is append-only', tg_table_name
    using errcode = 'restrict_violation';
end;
$$;

create trigger draft_versions_append_only
  before update or delete on public.draft_versions
  for each row execute function public.refuse_change();

create trigger proposal_approvals_append_only
  before update or delete on public.proposal_approvals
  for each row execute function public.refuse_change();

comment on table public.proposal_approvals is
  'F3/F4 R2 audit: each Copy is an approval of a draft version. Append-only.';
comment on table public.draft_versions is
  'F3 draft history. Append-only; proposals.current_version_id points at the latest.';
