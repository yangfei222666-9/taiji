'use client';

import { useEffect, useRef, useState } from 'react';
import { ArtifactList, type Artifact } from '@/components/ArtifactList';
import { StatusCard, type RunStatus } from '@/components/StatusCard';

type StartRunResponse = {
  run_id?: string;
  error?: string;
  trigger_mode?: string;
};

export function RunButton() {
  const [inviteToken, setInviteToken] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [run, setRun] = useState<RunStatus | null>(null);
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const timerRef = useRef<number | null>(null);

  useEffect(() => {
    setInviteToken(window.localStorage.getItem('taiji_invite_token') ?? '');
    return () => {
      if (timerRef.current) window.clearInterval(timerRef.current);
    };
  }, []);

  async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
    const res = await fetch(url, init);
    const data = (await res.json()) as T;
    if (!res.ok) {
      const message = typeof (data as { error?: unknown }).error === 'string' ? (data as { error: string }).error : res.statusText;
      throw new Error(message);
    }
    return data;
  }

  async function loadArtifacts(runId: string) {
    const data = await fetchJson<{ artifacts: Artifact[] }>(`/api/artifacts?run_id=${encodeURIComponent(runId)}`, {
      headers: {
        'x-taiji-invite-token': inviteToken
      }
    });
    setArtifacts(data.artifacts);
  }

  async function poll(runId: string) {
    const update = async () => {
      const nextRun = await fetchJson<RunStatus>(`/api/run_status?id=${encodeURIComponent(runId)}`, {
        headers: {
          'x-taiji-invite-token': inviteToken
        }
      });
      setRun(nextRun);
      if (nextRun.status === 'succeeded' || nextRun.status === 'failed' || nextRun.status === 'cancelled') {
        if (timerRef.current) window.clearInterval(timerRef.current);
        timerRef.current = null;
        setBusy(false);
        await loadArtifacts(runId);
      }
    };

    await update();
    timerRef.current = window.setInterval(update, 1500);
  }

  async function startRun() {
    setError('');
    setArtifacts([]);
    setBusy(true);
    window.localStorage.setItem('taiji_invite_token', inviteToken);

    try {
      const data = await fetchJson<StartRunResponse>('/api/start_run', {
        method: 'POST',
        headers: {
          'content-type': 'application/json',
          'x-taiji-invite-token': inviteToken
        },
        body: JSON.stringify({
          demo_id: 'starter-demo'
        })
      });

      if (!data.run_id) throw new Error('Run was not created.');
      await poll(data.run_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      setBusy(false);
    }
  }

  return (
    <section className="stack">
      <div className="panel stack">
        <h2>Start Demo Run</h2>
        <div className="form-row">
          <label className="label" htmlFor="invite-token">
            Invite token
          </label>
          <input
            id="invite-token"
            className="input"
            type="password"
            value={inviteToken}
            onChange={(event) => setInviteToken(event.target.value)}
            placeholder="Paste tester token"
            autoComplete="off"
          />
        </div>
        <button className="button" onClick={startRun} disabled={busy}>
          {busy ? 'Running' : 'Start Demo'}
        </button>
        {error ? <p className="error">{error}</p> : null}
      </div>

      <StatusCard run={run} />

      <section className="panel stack">
        <h2>Artifacts</h2>
        <ArtifactList artifacts={artifacts} />
      </section>
    </section>
  );
}
