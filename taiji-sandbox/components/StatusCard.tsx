'use client';

export type RunStatus = {
  id: string;
  status: string;
  progress: number;
  logs?: string | null;
  duration_ms?: number | null;
};

function badgeClass(status: string) {
  if (status === 'succeeded') return 'badge badge-ok';
  if (status === 'failed') return 'badge badge-failed';
  if (status === 'running') return 'badge badge-running';
  return 'badge badge-queued';
}

export function StatusCard({ run }: { run: RunStatus | null }) {
  if (!run) {
    return (
      <section className="panel stack">
        <h2>Run Status</h2>
        <p className="muted">Start a run to see progress.</p>
      </section>
    );
  }

  return (
    <section className="panel stack">
      <h2>Run Status</h2>
      <span className={badgeClass(run.status)}>{run.status}</span>
      <div className="metric">
        <div className="metric-label">Run ID</div>
        <div className="metric-value">{run.id}</div>
      </div>
      <div className="progress" aria-label={`Progress ${run.progress}%`}>
        <div className="progress-bar" style={{ width: `${Math.max(0, Math.min(100, run.progress))}%` }} />
      </div>
      <div className="muted">Progress: {run.progress}%</div>
      {run.duration_ms ? <div className="muted">Duration: {run.duration_ms} ms</div> : null}
      {run.logs ? <pre className="code">{run.logs}</pre> : null}
    </section>
  );
}
