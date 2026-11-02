-- KilnWatch: private map layers (e.g. Rashmi's Google Maps school scrape).
-- First create the bucket in the dashboard: Storage -> New bucket -> name "private-layer",
-- "Public bucket" OFF. Then run this once in the SQL editor.
-- Effect: only signed-in people listed in public.editors can download files from that bucket;
-- everyone else (including the public dashboard's visitors) is refused.

create policy "editors read private layers" on storage.objects
  for select to authenticated
  using (
    bucket_id = 'private-layer'
    and exists (select 1 from public.editors e where e.user_id = auth.uid())
  );

-- Check (should list the policy):
-- select policyname, cmd from pg_policies where tablename = 'objects' and policyname like 'editors%';
