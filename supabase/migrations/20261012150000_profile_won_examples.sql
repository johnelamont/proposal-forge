-- F8d: the drafter may show Claude up to three of the operator's own winning
-- cover letters on comparable jobs (voice and structure only). Operator's
-- choice, on by default; Profile → "Learn from proposals that won".
alter table public.profiles
  add column use_won_examples boolean not null default true;

comment on column public.profiles.use_won_examples is
  'F8: include excerpts of the operator''s own won proposals in the draft prompt.';
