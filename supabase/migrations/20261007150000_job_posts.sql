-- F1: pasted Upwork job posts and their parse results.
-- One row per paste. Nothing is treated as a parsed job until `decision` is
-- set (Continue / Abandon); abandoned rows are kept for analytics.
-- RLS: every statement is scoped to the owning user. No delete policy.

create table public.job_posts (
  id              uuid primary key default gen_random_uuid(),
  user_id         uuid not null default auth.uid()
                  references auth.users (id) on delete cascade,
  raw_paste       text not null,
  -- JobAnalysis (backend/app/models/job.py): parsed, ai, ai_failure,
  -- conflicts, parse_status. Kept whole so a job can be re-read after a
  -- parser fix without a new copy-paste.
  analysis        jsonb not null,
  parse_status    text not null
                  check (parse_status in ('ok', 'ai_failed', 'unrecognised')),
  upwork_job_id   text,
  decision        text check (decision in ('continue', 'abandon')),
  decided_at      timestamptz,
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now(),
  constraint job_posts_decision_pair
    check ((decision is null) = (decided_at is null))
);

comment on table public.job_posts is
  'F1 job post pastes. analysis.parsed.description is the only text that reaches Claude.';

-- One proposal per job per user; mobile pastes may lack the ID until supplied.
create unique index job_posts_user_upwork_job_id
  on public.job_posts (user_id, upwork_job_id)
  where upwork_job_id is not null;

create index job_posts_user_created
  on public.job_posts (user_id, created_at desc);

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create trigger job_posts_set_updated_at
  before update on public.job_posts
  for each row execute function public.set_updated_at();

alter table public.job_posts enable row level security;

create policy "job_posts: owner can read"
  on public.job_posts for select
  to authenticated
  using (user_id = auth.uid());

create policy "job_posts: owner can insert"
  on public.job_posts for insert
  to authenticated
  with check (user_id = auth.uid());

create policy "job_posts: owner can update"
  on public.job_posts for update
  to authenticated
  using (user_id = auth.uid())
  with check (user_id = auth.uid());
