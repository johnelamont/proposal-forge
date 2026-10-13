-- F7: PDF portfolio export.
--   portfolio_exports  APPEND-ONLY: every approved export (R1/R2) — who, when,
--                      the manifest hash the operator approved, the PDF hash,
--                      and the selection that produced it.
-- The row is written before the file is returned; no record → no file.

create table public.portfolio_exports (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid not null default auth.uid()
                references auth.users (id) on delete cascade,
  -- SHA-256 of the canonical manifest (exactly the text rendered).
  content_hash  text not null check (content_hash ~ '^[0-9a-f]{64}$'),
  -- SHA-256 of the PDF bytes handed to the operator.
  pdf_hash      text not null check (pdf_hash ~ '^[0-9a-f]{64}$'),
  selection     jsonb not null,
  entry_count   integer not null check (entry_count between 1 and 40),
  page_count    integer not null check (page_count >= 1),
  exported_by   uuid not null default auth.uid(),
  exported_at   timestamptz not null default now()
);

create index portfolio_exports_user on public.portfolio_exports (user_id, exported_at desc);

alter table public.portfolio_exports enable row level security;

create policy "portfolio_exports: owner can read"
  on public.portfolio_exports for select to authenticated using (user_id = auth.uid());
create policy "portfolio_exports: owner can insert"
  on public.portfolio_exports for insert to authenticated
  with check (user_id = auth.uid() and exported_by = auth.uid());
-- No update or delete policy: audit record.

create trigger portfolio_exports_append_only
  before update or delete on public.portfolio_exports
  for each row execute function public.refuse_change();

comment on table public.portfolio_exports is
  'F7 R2 audit: each approved PDF export with the manifest and PDF hashes. Append-only.';
