-- F5: the operator's past projects, extracted from dropped files or typed in.
-- Columns hold the operator-confirmed record; ai_extraction keeps Claude's
-- original reading for provenance; source_files keeps the dropped text so an
-- entry can be re-extracted later without re-dropping.
-- RLS: owner-scoped on every statement, delete included (operator's own data,
-- Standard classification).

create table public.work_history (
  id               uuid primary key default gen_random_uuid(),
  user_id          uuid not null default auth.uid()
                   references auth.users (id) on delete cascade,
  name             text not null check (char_length(name) between 1 and 200),
  summary          text not null default '',
  tech_stack       text[] not null default '{}',
  vertical         text,
  project_type     text,
  complexity       text check (complexity in ('low', 'medium', 'high')),
  role             text,
  outcomes         text[] not null default '{}',
  client_name      text,
  -- F7 allow-list: a client is never named in exports unless this is true.
  may_name_client  boolean not null default false,
  budget_band      text,
  started          text check (started ~ '^\d{4}-\d{2}$'),
  ended            text check (ended ~ '^\d{4}-\d{2}$'),
  source_files     jsonb not null default '[]'::jsonb,
  ai_extraction    jsonb,
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now()
);

comment on table public.work_history is
  'F5 work history. Only source_files text reaches Claude, after file_rules screening.';

create index work_history_user_ended
  on public.work_history (user_id, ended desc nulls last, updated_at desc);

create trigger work_history_set_updated_at
  before update on public.work_history
  for each row execute function public.set_updated_at();

alter table public.work_history enable row level security;

create policy "work_history: owner can read"
  on public.work_history for select
  to authenticated
  using (user_id = auth.uid());

create policy "work_history: owner can insert"
  on public.work_history for insert
  to authenticated
  with check (user_id = auth.uid());

create policy "work_history: owner can update"
  on public.work_history for update
  to authenticated
  using (user_id = auth.uid())
  with check (user_id = auth.uid());

create policy "work_history: owner can delete"
  on public.work_history for delete
  to authenticated
  using (user_id = auth.uid());
