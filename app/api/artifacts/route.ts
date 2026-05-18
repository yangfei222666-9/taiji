import { NextRequest, NextResponse } from 'next/server';
import { assertRunAccess } from '@/lib/auth';
import { getSupabaseAdmin } from '@/lib/supabase';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

type ArtifactRow = {
  id: string;
  bucket: string;
  path: string;
  label: string;
  content_type: string | null;
  bytes: number | null;
  created_at: string;
};

export async function GET(req: NextRequest) {
  const runId = req.nextUrl.searchParams.get('run_id');
  if (!runId) {
    return NextResponse.json({ error: 'missing_run_id' }, { status: 400 });
  }

  const supabase = getSupabaseAdmin();
  const access = await assertRunAccess(supabase, req, runId);
  if (!access.ok) {
    return NextResponse.json({ error: access.error }, { status: access.status });
  }

  const { data, error } = await supabase
    .from('run_artifacts')
    .select('id, bucket, path, label, content_type, bytes, created_at')
    .eq('run_id', runId)
    .order('created_at', { ascending: true });

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  const artifacts = await Promise.all(
    ((data ?? []) as ArtifactRow[]).map(async (artifact) => {
      const signed = await supabase.storage.from(artifact.bucket).createSignedUrl(artifact.path, 600);
      return {
        ...artifact,
        signed_url: signed.data?.signedUrl,
        signed_url_error: signed.error?.message
      };
    })
  );

  return NextResponse.json({ artifacts });
}
