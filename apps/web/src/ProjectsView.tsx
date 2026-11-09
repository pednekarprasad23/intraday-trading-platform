import { useEffect, useState, useCallback } from 'react';
import { api, type Project, type ProjectRun, type KillSwitchStatus, type SystemStatus } from './api';
import { StatusBadge } from './StatusBadge';

const STALE_THRESHOLD_MS = 30_000;  // 30 seconds

interface ProjectHealth {
  status: 'HEALTHY' | 'STALE' | 'INACTIVE' | 'UNAVAILABLE';
  ageMs: number;
  label: string;
}

function computeProjectHealth(project: Project): ProjectHealth {
  const now = Date.now();
  const ageMs = project.heartbeat_at ? now - new Date(project.heartbeat_at).getTime() : Infinity;
  let status: 'HEALTHY' | 'STALE' | 'INACTIVE' | 'UNAVAILABLE';
  let label: string;

  if (!project.runtime_status || project.runtime_status !== 'RUNNING') {
    status = 'INACTIVE';
    label = 'UNAVAILABLE';
  } else if (ageMs > STALE_THRESHOLD_MS) {
    status = 'STALE';
    label = `${Math.round(ageMs / 1000)}s ago`;
  } else if (project.heartbeat_at) {
    status = 'HEALTHY';
    label = `${Math.round(ageMs / 1000)}s ago`;
  } else {
    status = 'INACTIVE';
    label = 'N/A';
  }

  return { status, ageMs, label };
}

function formatResultSummary(summary: any | null) {
  if (!summary) return '—';
  const parts: string[] = [];
  if (summary.net_pnl !== undefined) parts.push(`P&L: ${summary.net_pnl}`);
  if (summary.trade_count !== undefined) parts.push(`Trades: ${summary.trade_count}`);
  if (summary.win_rate !== undefined) parts.push(`Win: ${summary.win_rate}`);
  if (summary.profit_factor !== undefined) parts.push(`PF: ${summary.profit_factor}`);
  if (summary.execution_status) parts.push(`${summary.execution_status}`);
  return parts.length ? parts.join(' | ') : '—';
}

export function ProjectsView() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [killSwitch, setKillSwitch] = useState<KillSwitchStatus | null>(null);
  const [refreshTick, setRefreshTick] = useState(0);

  const handleManualRefresh = useCallback(() => setRefreshTick(r => r + 1), []);

  useEffect(() => {
    let cancelled = false;
    const tick = setInterval(() => {
      if (!cancelled) setRefreshTick(r => r + 1);
    }, 5000);
    void api<KillSwitchStatus>('/paper/kill-switch');
    return () => {
      cancelled = true;
      clearInterval(tick);
    };
  }, []);

  useEffect(() => {
    void api<KillSwitchStatus>('/paper/kill-switch').then(({ state }) => setKillSwitch({ state: state || 'ARMED' }));
  }, []);

  useEffect(() => {
    void api<{ total: number; items: Project[] }>('/api/v1/projects?limit=50&offset=0').then(res => {
      setProjects(res.items);
    });
  }, [refreshTick]);

  const handleProjectStart = useCallback(async (projectId: string) => {
    try {
      await api<Project>(`/api/v1/projects/${projectId}/start`, { method: 'POST' });
    } catch {
    }
  }, []);

  const handleProjectStop = useCallback(async (projectId: string) => {
    if (!confirm('Project runtime will stop. Active runs may be cancelled. This does NOT enable LIVE trading.')) return;
    try {
      await api<Project>(`/api/v1/projects/${projectId}/stop`, { method: 'POST' });
    } catch {
    }
  }, []);

  return (
    <div style={{ padding: '16px', maxWidth: '1400px', margin: '0 auto' }}>
      <header style={{ marginBottom: '24px', paddingBottom: '16px', borderBottom: '1px solid #e2e8f0' }}>
        <h1 style={{ margin: '0 0 8px', fontSize: '1.25rem', fontWeight: 600, color: '#183048' }}>Projects</h1>
        <p style={{ margin: 0, fontSize: '0.875rem', color: '#64748b' }}>
          Runtime-backed project lifecycle with sandboxed execution
        </p>
      </header>

      {killSwitch && (
        <div style={{ marginBottom: '16px', padding: '8px 12px', borderRadius: '6px', background: killSwitch.state === 'TRIGGERED' ? 'rgba(239, 68, 68, 0.15)' : 'rgba(34, 197, 94, 0.08)', color: killSwitch.state === 'TRIGGERED' ? '#dc2626' : '#22c55e', fontSize: '0.75rem' }}>
          <StatusBadge status={killSwitch.state === 'TRIGGERED' ? 'triggered' : 'healthy'} />
          {killSwitch.state === 'TRIGGERED' ? 'KILL SWITCH BLOCKS EXECUTION' : 'Kill Switch ARMED'}
        </div>
      )}

      {projects.length === 0 ? (
        <div style={{ padding: '32px', textAlign: 'center', color: '#9ca3af' }}>
          No projects found. Create one to begin.
        </div>
      ) : (
        <div style={{ display: 'grid', gap: '16px', gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))' }}>
          {projects.map((project) => {
            const health = computeProjectHealth(project);

            return (
              <div key={project.id} style={{
                border: '1px solid #e2e8f0',
                borderRadius: '8px',
                background: '#fff',
                overflow: 'hidden',
                boxShadow: '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
                display: 'flex',
                flexDirection: 'column',
                height: '100%',
              }}>
                <div style={{
                  padding: '12px 16px',
                  borderBottom: '1px solid #e2e8f0',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                }}>
                  <div>
                    <h3 style={{ margin: '0 0 4px', fontSize: '0.9375rem', fontWeight: 600, color: '#183048' }}>
                      {project.name}
                    </h3>
                    <p style={{ margin: '0 0 2px', fontSize: '0.75rem', color: '#64748b' }}>
                      {project.slug || '—'}
                    </p>
                  </div>
                  <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                    <span style={{ fontSize: '0.7rem', color: '#64748b' }}>State: </span>
                    <StatusBadge status={project.status.value as any} label={project.status.value} />
                  </div>
                </div>

                <div style={{
                  padding: '8px 16px',
                  borderBottom: '1px solid #f1f5f9',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <StatusBadge status={health.status} label={health.label} />
                    <span style={{ fontSize: '0.7rem', color: '#64748b' }}>Runtime</span>
                  </div>
                  <div style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '2px',
                    background: 'rgba(239, 68, 68, 0.15)',
                    borderRadius: '4px',
                    padding: '2px 6px',
                    fontSize: '0.65rem',
                    color: '#dc2626',
                  }}>
                    LIVE DISABLED
                  </div>
                </div>

                <div style={{ padding: '8px 16px', flex: 1 }}>
                  <p style={{ margin: '0 0 4px', fontSize: '0.75rem', color: '#64748b' }}>Execution: SIMULATION / PAPER</p>
                  <p style={{ margin: '0', fontSize: '0.75rem', color: '#64748b' }}>Mode: {project.runtime_status || 'STOPPED'}</p>
                  {project.last_error && (
                    <p style={{ margin: '4px 0 0', fontSize: '0.7rem', color: '#dc2626', fontWeight: 500 }}>
                      Error: {project.last_error}
                    </p>
                  )}
                </div>

                <div style={{ padding: '4px 16px', fontSize: '0.7rem', color: '#64748b' }}>
                  Heartbeat: {health.label}
                </div>

                <div style={{ padding: '8px 16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                    {project.runtime_status === 'RUNNING' && (
                      <div style={{ fontSize: '0.7rem', color: '#10b981' }}>
                        Active run: {project.runs?.[0]?.id || '—'}
                      </div>
                    )}
                    {project.status.value === 'STOPPED' && (
                      <button
                        onClick={() => handleProjectStart(project.id)}
                        disabled={killSwitch.state === 'TRIGGERED'}
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '4px',
                          padding: '6px 12px',
                          fontSize: '0.7rem',
                          fontWeight: 500,
                          borderRadius: '6px',
                          background: killSwitch.state === 'TRIGGERED' ? 'rgba(239, 68, 68, 0.3)' : '#10b981',
                          color: killSwitch.state === 'TRIGGERED' ? '#dc2626' : '#fff',
                          border: 'none',
                          cursor: killSwitch.state === 'TRIGGERED' ? 'not-allowed' : 'pointer',
                          transition: 'background 0.15s',
                        }
                        title={killSwitch.state === 'TRIGGERED' ? 'Kill Switch triggered. Start blocked.' : 'Start project'}
                      >
                        <StatusBadge status={killSwitch.state !== 'TRIGGERED' ? 'healthy' : 'triggered'} size="small" />
                        START
                      </button>
                    )}
                    {project.status.value !== 'STOPPED' && (
                      <button
                        onClick={() => handleProjectStop(project.id)}
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '4px',
                          padding: '6px 12px',
                          fontSize: '0.7rem',
                          fontWeight: 500,
                          borderRadius: '6px',
                          background: '#f87171',
                          color: '#fff',
                          border: 'none',
                          cursor: 'pointer',
                          transition: 'background 0.15s',
                        }
                        title="Stop project runtime (cancels active runs)"
                      >
                        <StatusBadge status="triggered" size="small" />
                        STOP
                      </button>
                    )}
                  </div>

                  {project.runs?.[0] && project.runs[0].status === 'COMPLETED' && (
                    <div style={{ marginTop: '4px', fontSize: '0.65rem', color: '#059669' }}>
                      Run result: {formatResultSummary(project.runs[0].result_summary)}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}