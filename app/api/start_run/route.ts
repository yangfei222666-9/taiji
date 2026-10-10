import { NextRequest, NextResponse } from 'next/server';
import { assertRunAccess, consumeInviteToken, extractInviteToken, getInviteByToken, inviteRequired, readJsonBody } from '@/lib/auth';
import { getRuntimeLimits, getTriggerMode } from '@/lib/cloudrun';
import { triggerRun } from '@/lib/github';
import { getSupabaseAdmin } from '@/lib/supabase';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

type RunReservation = {
  run_id: string | null;
  outcome: 'reserved' | 'active_run_limit_reached';
};

export async function POST(req: NextRequest) {
  const body = await readJsonBody(req);
  const supabase = getSupabaseAdmin();
  const limits = getRuntimeLimits();

  let inviteId: string | null = null;
  let inviteToken = '';

  if (inviteRequired()) {
    inviteToken = extractInviteToken(req, body);
    if (!inviteToken) {
      return NextResponse.json({ error: 'missing_invite_token' }, { status: 401 });
    }

    const invite = await getInviteByToken(supabase, inviteToken);
    if (!invite) {
      return NextResponse.json({ error: 'invalid_invite_token' }, { status: 401 });
    }
    if (invite.expires_at && new Date(invite.expires_at).getTime() <= Date.now()) {
      return NextResponse.json({ error: 'invite_expired' }, { status: 403 });
    }
    if (invite.used_runs >= invite.max_runs) {
      return NextResponse.json({ error: 'invite_run_limit_reached' }, { status: 429 });
    }
    inviteId = invite.id;
  }

  const payload = {
    text: 'hello from taiji',
    requested_at: new Date().toISOString(),
    timeout_seconds: limits.timeoutSeconds
  };
  const demoId = typeof body.demo_id === 'string' ? body.demo_id : 'starter-demo';

  const { data: reservation, error } = await supabase
    .rpc('reserve_run_slot', {
      p_max_active_runs: limits.maxActiveRuns,
      p_demo_id: demoId,
      p_invite_id: inviteId,
      p_payload: payload
    })
    .single<RunReservation>();

  if (error || !reservation) {
    return NextResponse.json({ error: error?.message ?? 'run_reservation_failed' }, { status: 500 });
  }

  if (reservation.outcome === 'active_run_limit_reached') {
    return NextResponse.json({ error: reservation.outcome }, { status: 429 });
  }

  if (reservation.outcome !== 'reserved' || !reservation.run_id) {
    return NextResponse.json({ error: 'run_reservation_failed' }, { status: 500 });
  }

  const data = { id: reservation.run_id };

  if (inviteRequired()) {
    const inviteResult = await consumeInviteToken(supabase, inviteToken);
    if (!inviteResult.ok) {
      await supabase
        .from('runs')
        .update({
          status: 'cancelled',
          progress: 100,
          logs: inviteResult.error,
          finished_at: new Date().toISOString()
        })
        .eq('id', data.id);

      return NextResponse.json({ error: inviteResult.error, run_id: data.id }, { status: inviteResult.status });
    }
  }

  const access = await assertRunAccess(supabase, req, data.id, body);
  if (!access.ok) {
    return NextResponse.json({ error: access.error }, { status: access.status });
  }

  const triggerMode = getTriggerMode();

  try {
    if (triggerMode === 'mock') {
      await completeMockRun(data.id);
    } else {
      await triggerRun(data.id);
    }
  } catch (err) {
    const message = err instanceof Error ? err.message : 'queue_dispatch_failed';
    await supabase
      .from('runs')
      .update({
        status: 'failed',
        progress: 100,
        logs: message,
        finished_at: new Date().toISOString()
      })
      .eq('id', data.id);

    return NextResponse.json({ error: message, run_id: data.id }, { status: 502 });
  }

  return NextResponse.json({
    run_id: data.id,
    trigger_mode: triggerMode
  });
}

async function completeMockRun(runId: string) {
  const supabase = getSupabaseAdmin();
  const { artifactBucket } = getRuntimeLimits();
  const started = Date.now();
  const artifactPath = `runs/${runId}/result.json`;
  const result = {
    message: 'hello from local mock runtime',
    run_id: runId,
    generated_at: new Date().toISOString()
  };

  await supabase
    .from('runs')
    .update({
      status: 'running',
      progress: 40,
      started_at: new Date(started).toISOString(),
      logs: 'mock runtime started'
    })
    .eq('id', runId);

  const artifactBody = new Blob([JSON.stringify(result, null, 2)], {
    type: 'application/json'
  });
  const upload = await supabase.storage.from(artifactBucket).upload(artifactPath, artifactBody, {
    contentType: 'application/json',
    upsert: true
  });

  const logs = upload.error ? `mock runtime completed; artifact upload skipped: ${upload.error.message}` : 'mock runtime completed';

  if (!upload.error) {
    await supabase.from('run_artifacts').insert({
      run_id: runId,
      bucket: artifactBucket,
      path: artifactPath,
      label: 'result.json',
      content_type: 'application/json',
      bytes: artifactBody.size
    });
  }

  await supabase
    .from('runs')
    .update({
      status: 'succeeded',
      progress: 100,
      artifact_bucket: upload.error ? null : artifactBucket,
      artifact_path: upload.error ? null : artifactPath,
      artifact_url: upload.error ? null : `storage://${artifactBucket}/${artifactPath}`,
      logs,
      duration_ms: Date.now() - started,
      finished_at: new Date().toISOString()
    })
    .eq('id', runId);
}
