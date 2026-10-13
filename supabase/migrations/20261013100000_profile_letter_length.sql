-- F3 follow-up: an explicit cover-letter length preference on the profile.
-- 'none' keeps the original rule (no limit; say what needs saying and stop).
alter table public.profiles
  add column cover_letter_length text not null default 'none'
  check (cover_letter_length in ('short', 'medium', 'none'));

comment on column public.profiles.cover_letter_length is
  'Drafter target for the cover letter: short (~120–180 words), medium (~200–300), none (no limit). Recorded on each version''s ai_meta.length_target.';
