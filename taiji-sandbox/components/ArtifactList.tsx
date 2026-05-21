'use client';

export type Artifact = {
  id: string;
  label: string;
  path: string;
  signed_url?: string;
  created_at?: string;
};

export function ArtifactList({ artifacts }: { artifacts: Artifact[] }) {
  if (artifacts.length === 0) {
    return <p className="muted">No artifacts yet.</p>;
  }

  return (
    <ul className="artifact-list">
      {artifacts.map((artifact) => (
        <li key={artifact.id}>
          <div className="code">{artifact.label}</div>
          <div className="muted code">{artifact.path}</div>
          {artifact.signed_url ? (
            <a href={artifact.signed_url} target="_blank" rel="noreferrer">
              Open signed URL
            </a>
          ) : (
            <span className="muted">Signed URL unavailable</span>
          )}
        </li>
      ))}
    </ul>
  );
}
