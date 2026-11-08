import React from 'react';

export type StatusKind = 'paper' | 'paused' | 'readonly' | 'healthy' | 'triggered' | 'offline' | 'degraded';

export function StatusBadge({ status, label }: { status: StatusKind; label?: string }) {
  const styles: Record<StatusKind, { bg: string; color: string; text: string }> = {
    paper: { bg: 'rgba(59, 130, 246, 0.15)', color: '#3b82f6', text: 'PAPER' },
    paused: { bg: 'rgba(245, 158, 11, 0.15)', color: '#d97706', text: 'PAUSED' },
    readonly: { bg: 'rgba(20, 184, 166, 0.15)', color: '#0d9488', text: 'BROKER READ-ONLY' },
    healthy: { bg: 'rgba(16, 185, 129, 0.15)', color: '#059669', text: 'HEALTHY' },
    triggered: { bg: 'rgba(239, 68, 68, 0.15)', color: '#dc2626', text: 'KILL SWITCH TRIGGERED' },
    degraded: { bg: 'rgba(245, 158, 11, 0.15)', color: '#d97706', text: 'DEGRADED' },
    offline: { bg: 'rgba(107, 114, 128, 0.15)', color: '#4b5563', text: 'OFFLINE' },
  };

  const cfg = styles[status] || styles.offline;

  return (
    <span style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: '6px',
      borderRadius: '6px',
      padding: '4px 9px',
      background: cfg.bg,
      color: cfg.color,
      fontSize: '0.72rem',
      fontWeight: 700,
      letterSpacing: '0.04em',
      whiteSpace: 'nowrap',
    }}>
      <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: cfg.color }} />
      {label || cfg.text}
    </span>
  );
}
