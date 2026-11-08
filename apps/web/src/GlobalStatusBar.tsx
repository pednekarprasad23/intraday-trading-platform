import { useEffect, useState } from 'react';
import { api, type KillSwitchStatus } from './api';
import { StatusBadge, type StatusKind } from './StatusBadge';

interface HealthStatus {
  status: string;
  timestamp: string;
  dependencies: Record<string, string>;
  response_time_ms: number;
}

export function GlobalStatusBar() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [killSwitch, setKillSwitch] = useState<KillSwitchStatus | null>(null);
  const [currentTime, setCurrentTime] = useState<string>('');

  async function fetchStatus() {
    try {
      const [h, k] = await Promise.allSettled([
        api<HealthStatus>('/monitoring/health'),
        api<KillSwitchStatus>('/paper/kill-switch'),
      ]);
      if (h.status === 'fulfilled') setHealth(h.value);
      if (k.status === 'fulfilled') setKillSwitch(k.value);
    } catch {
      // ignore
    }
  }

  useEffect(() => {
    void fetchStatus();
    const timer = setInterval(() => {
      setCurrentTime(new Date().toUTCString().replace('GMT', 'UTC'));
    }, 1000);
    setCurrentTime(new Date().toUTCString().replace('GMT', 'UTC'));

    const interval = setInterval(() => void fetchStatus(), 15000);
    return () => {
      clearInterval(timer);
      clearInterval(interval);
    };
  }, []);

  const healthKind: StatusKind = health?.status === 'healthy' ? 'healthy' : health?.status === 'degraded' ? 'degraded' : 'offline';
  const ksKind: StatusKind = killSwitch?.state === 'triggered' ? 'triggered' : 'healthy';

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: '16px',
      fontSize: '0.78rem',
      color: '#4b5563',
      flexWrap: 'wrap',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
        <span>System:</span>
        <StatusBadge status={healthKind} label={health?.status ? health.status.toUpperCase() : 'CHECKING'} />
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
        <span>Mode:</span>
        <StatusBadge status="paper" label="PAPER SIMULATION" />
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
        <span>Kill Switch:</span>
        <StatusBadge status={ksKind} label={killSwitch?.state ? killSwitch.state.toUpperCase() : 'ARMED'} />
      </div>

      {currentTime && (
        <div style={{ display: 'flex', alignItems: 'center', fontFamily: 'monospace', fontSize: '0.74rem' }}>
          {currentTime}
        </div>
      )}
    </div>
  );
}
