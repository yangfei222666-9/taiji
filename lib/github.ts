export async function triggerRun(runId: string) {
  const repo = process.env.GH_REPO;
  const token = process.env.GH_TOKEN;
  const ref = process.env.GH_REF || 'main';
  const workflow = process.env.GH_WORKFLOW || 'ephemeral-run.yml';

  if (!repo || !token) {
    throw new Error('Missing GH_REPO or GH_TOKEN for workflow_dispatch.');
  }

  const res = await fetch(`https://api.github.com/repos/${repo}/actions/workflows/${workflow}/dispatches`, {
    method: 'POST',
    headers: {
      authorization: `Bearer ${token}`,
      accept: 'application/vnd.github+json',
      'content-type': 'application/json',
      'x-github-api-version': '2022-11-28'
    },
    body: JSON.stringify({
      ref,
      inputs: {
        run_id: runId
      }
    })
  });

  if (!res.ok) {
    const body = await res.text();
    throw new Error(`GitHub workflow_dispatch failed with HTTP ${res.status}: ${body.slice(0, 240)}`);
  }

  return {
    workflow,
    ref
  };
}
