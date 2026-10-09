-- F2: the wheelhouse advisory, computed on demand per job post and stored so
-- reopening the job does not repeat the Claude call. Refreshable.
alter table public.job_posts
  add column advisory    jsonb,
  add column advisory_at timestamptz;

comment on column public.job_posts.advisory is
  'F2 Advisory (backend/app/models/advisory.py): comparables from work_history, '
  'match strength, and Claude''s fit reading or its failure. Null until computed.';
