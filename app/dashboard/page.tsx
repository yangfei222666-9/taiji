import Link from 'next/link';
import { getSupabaseAdmin, hasSupabaseAdminEnv } from '@/lib/supabase';

export const dynamic = 'force-dynamic';

type RunRow = {
  id: string;
  created_at: string;
  demo_id: string | null;
  status: string;
  progress: number;
  duration_ms: number | null;
};

export default async function DashboardPage() {
  let rows: RunRow[] = [];
  let setupError = '';

  if (hasSupabaseAdminEnv()) {
    const supabase = getSupabaseAdmin();
    const { data, error } = await supabase
      .from('runs')
      .select('id, created_at, demo_id, status, progress, duration_ms')
      .order('created_at', { ascending: false })
      .limit(25);

    if (error) {
      setupError = error.message;
    } else {
      rows = data ?? [];
    }
  } else {
    setupError = 'Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE.';
  }

  return (
    <main className="shell">
      <div className="topbar">
        <div className="brand">
          <h1>Run Dashboard</h1>
          <p>Latest Supabase-backed demo runs.</p>
        </div>
        <Link className="navlink" href="/">
          Start Run
        </Link>
      </div>

      <section className="panel">
        {setupError ? (
          <p className="error">{setupError}</p>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Created</th>
                  <th>Run</th>
                  <th>Demo</th>
                  <th>Status</th>
                  <th>Progress</th>
                  <th>Duration</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id}>
                    <td className="code">{new Date(row.created_at).toLocaleString()}</td>
                    <td className="code">{row.id}</td>
                    <td>{row.demo_id ?? 'starter-demo'}</td>
                    <td>{row.status}</td>
                    <td>{row.progress}%</td>
                    <td>{row.duration_ms ? `${row.duration_ms} ms` : '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </main>
  );
}
