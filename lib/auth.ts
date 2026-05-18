import { createHash } from 'crypto';
import type { NextRequest } from 'next/server';
import type { SupabaseClient } from '@supabase/supabase-js';

type InviteRow = {
  id: string;
  email: string | null;
  max_runs: number;
  used_runs: number;
  expires_at: string | null;
};

export function inviteRequired() {
  return process.env.DEMO_REQUIRE_INVITE !== 'false';
}

export function hashInviteToken(token: string) {
  return createHash('sha256').update(token).digest('hex');
}

export async function readJsonBody(req: NextRequest): Promise<Record<string, unknown>> {
  try {
    return (await req.json()) as Record<string, unknown>;
  } catch {
    return {};
  }
}

export function extractInviteToken(req: NextRequest, body?: Record<string, unknown>) {
  const headerToken = req.headers.get('x-taiji-invite-token')?.trim();
  const auth = req.headers.get('authorization')?.trim();
  const bearerToken = auth?.toLowerCase().startsWith('bearer ') ? auth.slice(7).trim() : '';
  const bodyToken = typeof body?.invite_token === 'string' ? body.invite_token.trim() : '';
  return headerToken || bearerToken || bodyToken;
}

export async function getInviteByToken(supabase: SupabaseClient, token: string) {
  const tokenHash = hashInviteToken(token);
  const { data, error } = await supabase
    .from('invites')
    .select('id, email, max_runs, used_runs, expires_at')
    .eq('token_hash', tokenHash)
    .maybeSingle<InviteRow>();

  if (error) throw error;
  return data;
}

export async function consumeInviteToken(supabase: SupabaseClient, token: string) {
  const invite = await getInviteByToken(supabase, token);

  if (!invite) {
    return { ok: false as const, status: 401, error: 'invalid_invite_token' };
  }

  if (invite.expires_at && new Date(invite.expires_at).getTime() <= Date.now()) {
    return { ok: false as const, status: 403, error: 'invite_expired' };
  }

  if (invite.used_runs >= invite.max_runs) {
    return { ok: false as const, status: 429, error: 'invite_run_limit_reached' };
  }

  const { data, error } = await supabase.rpc('consume_invite_run', {
    p_invite_id: invite.id
  });

  if (error) throw error;
  const consumed = Array.isArray(data) ? (data[0] as InviteRow | undefined) : (data as InviteRow | null);

  if (!consumed) {
    return { ok: false as const, status: 429, error: 'invite_run_limit_reached' };
  }

  return { ok: true as const, invite: consumed };
}

export async function assertRunAccess(supabase: SupabaseClient, req: NextRequest, runId: string, body?: Record<string, unknown>) {
  if (!inviteRequired()) return { ok: true as const };

  const token = extractInviteToken(req, body);
  if (!token) return { ok: false as const, status: 401, error: 'missing_invite_token' };

  const invite = await getInviteByToken(supabase, token);
  if (!invite) return { ok: false as const, status: 401, error: 'invalid_invite_token' };

  const { data, error } = await supabase.from('runs').select('id').eq('id', runId).eq('invite_id', invite.id).maybeSingle();
  if (error) throw error;
  if (!data) return { ok: false as const, status: 403, error: 'run_not_allowed_for_invite' };

  return { ok: true as const };
}
