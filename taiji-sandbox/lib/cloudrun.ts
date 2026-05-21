export type TriggerMode = 'mock' | 'github';

export function getTriggerMode(): TriggerMode {
  return process.env.DEMO_TRIGGER_MODE === 'github' ? 'github' : 'mock';
}

export function getRuntimeLimits() {
  return {
    maxActiveRuns: numberFromEnv('DEMO_MAX_ACTIVE_RUNS', 3),
    timeoutSeconds: numberFromEnv('DEMO_RUN_TIMEOUT_SECONDS', 30),
    artifactBucket: process.env.ARTIFACT_BUCKET || 'taiji-artifacts'
  };
}

function numberFromEnv(name: string, fallback: number) {
  const value = Number(process.env[name]);
  return Number.isFinite(value) && value > 0 ? value : fallback;
}
