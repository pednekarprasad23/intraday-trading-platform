import { useEffect, useState } from 'react';
import { api } from './api';

type CorrelationQuality = 'EXACT' | 'STRONG' | 'AMBIGUOUS' | 'UNAVAILABLE';

interface ReconciliationRow {
  type: 'signal-order' | 'order-position';
  id: string;
  instrument_id: string;
  strategy_id: string | null;
  timestamp: string;
  correlation: CorrelationQuality;
  detail: string;
  entity_label: string;
}

function qualityBadge(quality: CorrelationQuality) {
  const styles: Record<CorrelationQuality, { bg: string; color: string }> = {
    EXACT: { bg: '#e6f7f3', color: '#126756' },
    STRONG: { bg: '#e6f0ff', color: '#1d4ed8' },
    AMBIGUOUS: { bg: '#fff8e6', color: '#8a6d00' },
    UNAVAILABLE: { bg: '#f0f0f0', color: '#64778a' },
  };
  const style = styles[quality];
  return (
    <span style={{ display: 'inline-block', padding: '2px 8px', borderRadius: '4px', background: style.bg, color: style.color, fontSize: '0.7rem', fontWeight: 800 }}>
      {quality}
    </span>
  );
}

function time(value: string) {
  if (!value) return '—';
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

export function ReconciliationView() {
  const [orders, setOrders] = useState<any[]>([]);
  const [positions, setPositions] = useState<any[]>([]);
  const [signals, setSignals] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function loadData() {
    try {
      setLoading(true);
      setError(null);
      const [ordRes, posRes] = await Promise.all([
        api<any>('/paper/orders?limit=50'),
        api<any>('/paper/positions'),
      ]);

      setOrders(ordRes.items || []);
      setPositions(posRes || []);

      // Attempt to fetch signals if endpoint exists; handle gracefully
      try {
        const sigRes = await api<any>('/research/signals?limit=20');
        setSignals(sigRes.items || []);
      } catch {
        setSignals([]);
      }
    } catch (err: any) {
      setError(err?.message || 'Failed to load reconciliation data');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadData();
  }, []);

  // Build reconciliation rows with explicit correlation classifications
  const rows: ReconciliationRow[] = [];

  // Order -> Position: STRONG (instrument + account match)
  for (const pos of positions) {
    const matchingOrders = orders.filter(o => o.instrument_id === pos.instrument_id);
    for (const ord of matchingOrders) {
      rows.push({
        type: 'order-position',
        id: `${ord.id}-${pos.id}`,
        instrument_id: pos.instrument_id,
        strategy_id: ord.strategy_id,
        timestamp: ord.filled_at || ord.created_at,
        correlation: 'STRONG',
        detail: `Order ${ord.id.substring(0, 8)}… (${ord.state}) linked to Position ${pos.id.substring(0, 8)}… via instrument/account identity`,
        entity_label: `${ord.side.toUpperCase()} ${ord.quantity} → Position (${pos.quantity})`,
      });
    }
  }

  // Signal -> Order: AMBIGUOUS (strategy_id tag + timestamp heuristic)
  for (const ord of orders) {
    if (!ord.strategy_id) continue;
    const matchingSignals = signals.filter((s: any) => s.strategy_version_id === ord.strategy_id || s.strategy_id === ord.strategy_id);
    for (const sig of matchingSignals) {
      rows.push({
        type: 'signal-order',
        id: `${sig.id}-${ord.id}`,
        instrument_id: ord.instrument_id || sig.instrument_id,
        strategy_id: ord.strategy_id,
        timestamp: ord.created_at,
        correlation: 'AMBIGUOUS',
        detail: `Signal ${sig.id.substring(0, 8)}… potentially caused Order ${ord.id.substring(0, 8)}… via strategy_id tag association`,
        entity_label: `Signal (${sig.direction || '—'}) → Order (${ord.side.toUpperCase()} ${ord.quantity})`,
      });
    }
  }

  // Unmatched positions and signals
  const unmatchedPositions = positions.filter(p => !orders.some(o => o.instrument_id === p.instrument_id));
  const unmatchedOrders = orders.filter(o => o.state === 'filled' && !positions.some(p => p.instrument_id === o.instrument_id));

  return (
    <div className="view-container" style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <div className="section-heading" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h2>Reconciliation Console</h2>
          <p className="muted">Operational traceability for orders, positions, and signal associations. All correlations are explicitly classified.</p>
        </div>
        <button className="quiet-button" onClick={() => void loadData()} disabled={loading}>
          {loading ? 'Refreshing…' : 'Refresh Audit'}
        </button>
      </div>

      {error && <p role="alert" className="error">Reconciliation error: {error}</p>}

      {/* Correlation Legend */}
      <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', background: '#f8fafc', padding: '12px', borderRadius: '8px', border: '1px solid #eef2f5' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}><strong style={{ fontSize: '0.8rem' }}>Legend:</strong> {qualityBadge('EXACT')} <span style={{ fontSize: '0.78rem' }}>Durable foreign key (e.g., order→fill)</span></div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>{qualityBadge('STRONG')} <span style={{ fontSize: '0.78rem' }}>Instrument/account identity match</span></div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>{qualityBadge('AMBIGUOUS')} <span style={{ fontSize: '0.78rem' }}>Strategy tag/timestamp heuristic only</span></div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>{qualityBadge('UNAVAILABLE')} <span style={{ fontSize: '0.78rem' }}>No durable identifier exists</span></div>
      </div>

      {/* Summary Stats */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '12px' }}>
        <div style={{ background: '#fff', padding: '14px', borderRadius: '8px', border: '1px solid #d4dde4' }}>
          <span className="muted" style={{ fontSize: '0.78rem' }}>Order→Position Links</span>
          <div style={{ fontSize: '1.3rem', fontWeight: 700, marginTop: '4px', color: '#1d4ed8' }}>
            {rows.filter(r => r.type === 'order-position').length}
          </div>
          <div style={{ marginTop: '4px' }}>{qualityBadge('STRONG')}</div>
        </div>
        <div style={{ background: '#fff', padding: '14px', borderRadius: '8px', border: '1px solid #d4dde4' }}>
          <span className="muted" style={{ fontSize: '0.78rem' }}>Signal→Order Links</span>
          <div style={{ fontSize: '1.3rem', fontWeight: 700, marginTop: '4px', color: '#8a6d00' }}>
            {rows.filter(r => r.type === 'signal-order').length}
          </div>
          <div style={{ marginTop: '4px' }}>{qualityBadge('AMBIGUOUS')}</div>
        </div>
        <div style={{ background: '#fff', padding: '14px', borderRadius: '8px', border: '1px solid #d4dde4' }}>
          <span className="muted" style={{ fontSize: '0.78rem' }}>Unmatched Positions</span>
          <div style={{ fontSize: '1.3rem', fontWeight: 700, marginTop: '4px' }}>{unmatchedPositions.length}</div>
        </div>
        <div style={{ background: '#fff', padding: '14px', borderRadius: '8px', border: '1px solid #d4dde4' }}>
          <span className="muted" style={{ fontSize: '0.78rem' }}>Unmatched Orders</span>
          <div style={{ fontSize: '1.3rem', fontWeight: 700, marginTop: '4px' }}>{unmatchedOrders.length}</div>
        </div>
      </div>

      {/* Main Reconciliation Table */}
      <section style={{ background: '#fff', padding: '16px', border: '1px solid #d4dde4', borderRadius: '8px' }}>
        {loading ? (
          <p className="muted" style={{ textAlign: 'center', padding: '40px 0' }}>Loading reconciliation audit…</p>
        ) : rows.length === 0 ? (
          <p className="muted" style={{ textAlign: 'center', padding: '40px 0' }}>
            No reconciliation candidates found. This is expected when positions are empty or orders lack strategy tags.
            <br />
            <span style={{ fontSize: '0.8rem' }}>Order→Position: <strong>STRONG</strong> when instrument matches. Signal→Order: <strong>AMBIGUOUS</strong> without durable FK.</span>
          </p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Entity</th>
                  <th>Instrument</th>
                  <th>Strategy Tag</th>
                  <th>Timestamp</th>
                  <th>Link Type</th>
                  <th>Correlation</th>
                  <th>Notes</th>
                </tr>
              </thead>
              <tbody>
                {rows.map(row => (
                  <tr key={row.id}>
                    <td style={{ fontSize: '0.82rem' }}>{row.entity_label}</td>
                    <td><code style={{ fontSize: '0.7rem' }}>{row.instrument_id.substring(0, 12)}…</code></td>
                    <td><code>{row.strategy_id || '—'}</code></td>
                    <td>{time(row.timestamp)}</td>
                    <td><span style={{ textTransform: 'capitalize' }}>{row.type.replace('-', ' → ')}</span></td>
                    <td>{qualityBadge(row.correlation)}</td>
                    <td style={{ fontSize: '0.75rem', color: '#64778a' }}>{row.detail}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Discrepancy Panel */}
      {(unmatchedPositions.length > 0 || unmatchedOrders.length > 0) && (
        <section style={{ background: '#fff8e6', border: '1px solid #ffeaa7', padding: '16px', borderRadius: '8px' }}>
          <h4 style={{ margin: 0, marginBottom: '10px', fontSize: '0.9rem', color: '#8a6d00' }}>⚠ Unmatched Entities</h4>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', fontSize: '0.82rem' }}>
            {unmatchedPositions.length > 0 && (
              <div>
                <strong>Unmatched Positions ({unmatchedPositions.length}):</strong>
                <ul style={{ margin: '6px 0', paddingLeft: '18px' }}>
                  {unmatchedPositions.map(p => <li key={p.id}><code>{p.instrument_id.substring(0, 8)}…</code> Qty: {p.quantity}</li>)}
                </ul>
              </div>
            )}
            {unmatchedOrders.length > 0 && (
              <div>
                <strong>Unmatched Filled Orders ({unmatchedOrders.length}):</strong>
                <ul style={{ margin: '6px 0', paddingLeft: '18px' }}>
                  {unmatchedOrders.map(o => <li key={o.id}><code>{o.id.substring(0, 8)}…</code> {o.side.toUpperCase()} {o.quantity}</li>)}
                </ul>
              </div>
            )}
          </div>
          <p style={{ fontSize: '0.75rem', color: '#8a6d00', marginTop: '10px' }}>
            These entities do not have counterpart matches via instrument/account correlation. This may indicate new positions or closed fills.
          </p>
        </section>
      )}
    </div>
  );
}
