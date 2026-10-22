-- KilnWatch dashboard: analyst edits (add / move / flag kilns and schools).
-- Run once in the Supabase SQL editor. Edits are private to listed editors and are
-- folded into the analysis by analysis/pull_dashboard_edits.py; nothing changes the
-- published numbers until the pipeline is re-run.

create table if not exists public.editors (
  user_id uuid primary key references auth.users(id) on delete cascade,
  name text not null
);

create table if not exists public.edits (
  id bigint generated always as identity primary key,
  created_at timestamptz not null default now(),
  created_by uuid not null default auth.uid() references auth.users(id),
  editor_name text not null,
  feature text not null check (feature in ('kiln', 'school')),
  action text not null check (action in ('add', 'move', 'not_present', 'note')),
  target_id text,                       -- kiln id or UDISE code of an existing feature
  name text,
  lat double precision check (lat between 26 and 31),
  lon double precision check (lon between 75 and 79),
  evidence text not null check (length(evidence) >= 10),
  imagery text,                         -- e.g. Esri World Imagery, Esri Wayback, Google Earth history
  imagery_date text,
  status text not null default 'pending' check (status in ('pending', 'applied', 'rejected'))
);

alter table public.editors enable row level security;
alter table public.edits enable row level security;

-- an editor can see that they are an editor
create policy "editors read self" on public.editors
  for select to authenticated using (user_id = auth.uid());

-- only editors can read and add edits; each edit is stamped with its author
create policy "editors read edits" on public.edits
  for select to authenticated using (exists (select 1 from public.editors e where e.user_id = auth.uid()));
create policy "editors add edits" on public.edits
  for insert to authenticated
  with check (created_by = auth.uid() and exists (select 1 from public.editors e where e.user_id = auth.uid()));
-- an editor may withdraw their own edit while it is still pending
create policy "withdraw own pending" on public.edits
  for delete to authenticated using (created_by = auth.uid() and status = 'pending');

-- After signing in once on the dashboard's Edit page, make yourself an editor
-- (replace the email with the one you signed in with):
-- insert into public.editors (user_id, name)
--   select id, 'Rashmi Sinha' from auth.users where email = 'you@example.com';
