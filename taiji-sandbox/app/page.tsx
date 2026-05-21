import Link from 'next/link';
import { RunButton } from '@/components/RunButton';

export default function Home() {
  return (
    <main className="shell">
      <div className="topbar">
        <div className="brand">
          <h1>Taiji Sandbox</h1>
          <p>Invite-gated ephemeral runtime for fork, deploy, and tester loops.</p>
        </div>
        <Link className="navlink" href="/dashboard">
          Dashboard
        </Link>
      </div>

      <div className="layout">
        <RunButton />
        <section className="panel stack" aria-label="Runtime guardrails">
          <h2>Runtime Contract</h2>
          <div className="status-grid">
            <div className="metric">
              <div className="metric-label">Queue</div>
              <div className="metric-value">GitHub Actions</div>
            </div>
            <div className="metric">
              <div className="metric-label">Executor</div>
              <div className="metric-value">Cloud Run Job</div>
            </div>
            <div className="metric">
              <div className="metric-label">State</div>
              <div className="metric-value">Supabase</div>
            </div>
            <div className="metric">
              <div className="metric-label">Artifact TTL</div>
              <div className="metric-value">24h</div>
            </div>
          </div>
          <p className="muted">
            Invite quotas, active-run caps, private artifacts, and 30-second job timeout are part of the default path.
          </p>
        </section>
      </div>
    </main>
  );
}
