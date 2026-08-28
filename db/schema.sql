create extension if not exists pgcrypto;

create table if not exists public.invites (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  email text,
  token_hash text not null unique,
  max_runs int not null default 20 check (max_runs > 0),
  used_runs int not null default 0 check (used_runs >= 0),
  expires_at timestamptz
);

create table if not exists public.runs (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  started_at timestamptz,
  finished_at timestamptz,
  invite_id uuid references public.invites(id) on delete set null,
  demo_id text,
  status text not null default 'queued' check (status in ('queued', 'running', 'succeeded', 'failed', 'cancelled')),
  progress int not null default 0 check (progress >= 0 and progress <= 100),
  payload jsonb not null default '{}'::jsonb,
  artifact_bucket text,
  artifact_path text,
  artifact_url text,
  logs text,
  error text,
  duration_ms int
);

create table if not exists public.run_artifacts (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  run_id uuid not null references public.runs(id) on delete cascade,
  bucket text not null default 'taiji-artifacts',
  path text not null,
  label text not null default 'artifact',
  content_type text,
  bytes int
);

create index if not exists runs_status_created_at_idx on public.runs(status, created_at desc);
create index if not exists runs_invite_created_at_idx on public.runs(invite_id, created_at desc);
create index if not exists run_artifacts_run_id_idx on public.run_artifacts(run_id);

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists runs_set_updated_at on public.runs;
create trigger runs_set_updated_at
before update on public.runs
for each row
execute function public.set_updated_at();

create or replace function public.consume_invite_run(p_invite_id uuid)
returns table (
  id uuid,
  email text,
  max_runs int,
  used_runs int,
  expires_at timestamptz
)
language plpgsql
security invoker
set search_path = public
as $$
begin
  return query
  update public.invites i
  set used_runs = i.used_runs + 1
  where i.id = p_invite_id
    and i.used_runs < i.max_runs
    and (i.expires_at is null or i.expires_at > now())
  returning i.id, i.email, i.max_runs, i.used_runs, i.expires_at;
end;
$$;

create or replace function public.reserve_run_slot(
  p_max_active_runs int,
  p_demo_id text,
  p_invite_id uuid,
  p_payload jsonb
)
returns table (
  run_id uuid,
  outcome text
)
language plpgsql
security invoker
set search_path = public
as $$
declare
  v_active_runs int;
  v_run_id uuid;
begin
  if p_max_active_runs is null or p_max_active_runs <= 0 then
    raise exception 'p_max_active_runs must be positive' using errcode = '22023';
  end if;

  perform pg_advisory_xact_lock(hashtextextended('taiji.reserve_run_slot', 0));

  select count(*)
  into v_active_runs
  from public.runs
  where status in ('queued', 'running');

  if v_active_runs >= p_max_active_runs then
    return query select null::uuid, 'active_run_limit_reached'::text;
    return;
  end if;

  insert into public.runs (demo_id, invite_id, payload, status, progress)
  values (p_demo_id, p_invite_id, p_payload, 'queued', 0)
  returning id into v_run_id;

  return query select v_run_id, 'reserved'::text;
end;
$$;

alter table public.invites enable row level security;
alter table public.runs enable row level security;
alter table public.run_artifacts enable row level security;

revoke all on public.invites from anon, authenticated;
revoke all on public.runs from anon, authenticated;
revoke all on public.run_artifacts from anon, authenticated;
revoke all on function public.consume_invite_run(uuid) from public, anon, authenticated;
revoke all on function public.reserve_run_slot(int, text, uuid, jsonb) from public, anon, authenticated;

grant all on public.invites to service_role;
grant all on public.runs to service_role;
grant all on public.run_artifacts to service_role;
grant execute on function public.consume_invite_run(uuid) to service_role;
grant execute on function public.reserve_run_slot(int, text, uuid, jsonb) to service_role;

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'taiji-artifacts',
  'taiji-artifacts',
  false,
  52428800,
  array['application/json', 'text/plain']
)
on conflict (id) do update
set public = false,
    file_size_limit = excluded.file_size_limit,
    allowed_mime_types = excluded.allowed_mime_types;

-- Supabase 2026 note: new tables may not be auto-exposed to the Data API.
-- This starter keeps browser access behind Next.js API routes and service-role server code.
-- Do not grant anon/authenticated table access unless you also add narrow RLS policies.
