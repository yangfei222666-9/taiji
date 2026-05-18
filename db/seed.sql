insert into public.invites (
  email,
  token_hash,
  max_runs,
  used_runs,
  expires_at
)
values (
  'tester@example.com',
  encode(digest('dev-invite-token', 'sha256'), 'hex'),
  20,
  0,
  now() + interval '14 days'
)
on conflict (token_hash) do update
set email = excluded.email,
    max_runs = excluded.max_runs,
    expires_at = excluded.expires_at;

insert into public.runs (
  demo_id,
  status,
  progress,
  payload,
  logs
)
values (
  'starter-demo',
  'succeeded',
  100,
  '{"text":"hello taiji"}',
  'seed run'
);
