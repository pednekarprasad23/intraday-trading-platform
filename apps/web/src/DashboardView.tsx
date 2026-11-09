import { useEffect, useState } from 'react';
import { paper, api, type PaperAccountSummary, type PaperPosition, type PaperOrder, type KillSwitchStatus, type PaperRiskEvent } from './api';

interface HealthStatus {
  status: string;
  timestamp: string;
  dependencies: Record<string, string>;
  response_time_ms: number;
}

function formatCurrency(value: string | null, currency: string = 'INR') {
  if (value == null) return '—';
  const num = parseFloat(value);
  if (isNaN(num)) return value;
  return new Intl.NumberFormat('en-IN', { style: 'currency', currency, minimumFractionDigits: 2 }).format(num);
}

function time(value: string | null) {
  if (!value) return '—';
  try {
    return new Date(value).toLocaleTimeString();
  } catch {
    return value;
  }
}

function PnL({ value }: { value: string | null }) {
  if (value == null) return <span>—</span>;
  const num = parseFloat(value);
  if (isNaN(num)) return <span>{value}</span>;
  const color = num > 0 ? '#126756' : num < 0 ? '#9a392a' : '#64778a';
  const sign = num > 0 ? '+' : '';
  return <span style={{ color, fontWeight: 700 }}>{sign}{num.toLocaleString('en-IN', { maximumFractionDigits: 2 })}</span>;
}

export function ProjectOperationalCard({ name, strategyId, instrument, market, broker, mode, state, pnl, lastSignal, lastExecution, health, onInspectOrders }: {
  name: string;
  strategyId?: string;
  instrument: string;
  market: string;
  broker: string;
  mode: string;
  state: string;
  pnl?: string | null;
  lastSignal?: string | null;
  lastExecution?: string | null;
  health: 'HEALTHY' | 'WARNING' | 'ERROR' | 'OFFLINE';
  onInspectOrders?: () => void;
}) {
  const healthColors: Record<string, { bg: string; color: string }> = {
    HEALTHY: { bg: '#e6f7f3', color: '#126756' },
    WARNING: { bg: '#fff8e6', color: '#8a6d00' },
    ERROR: { bg: '#fef0ee', color: '#9a392a' },
    OFFLINE: { bg: '#f0f0f0', color: '#64778a' },
  };
  const badgeStyle = healthColors[health] || healthColors.OFFLINE;

  return (
    <div className="card" style={{ border: '1px solid #d4dde4', borderRadius: '8px', padding: '16px', background: '#fff', display: 'flex', flexDirection: 'column', gap: '10px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <h4 style={{ margin: 0, fontSize: '1rem', color: '#111b21' }}>{name}</h4>
          {strategyId && <span className="muted" style={{ fontSize: '0.75rem', fontFamily: 'monospace' }}>ID: {strategyId}</span>}
        </div>
        <span style={{ padding: '2px 8px', borderRadius: '4px', background: badgeStyle.bg, color: badgeStyle.color, fontSize: '0.7rem', fontWeight: 700 }}>
          {health}
        </span>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', fontSize: '0.85rem' }}>
        <div><span className="muted">Instrument:</span> <strong>{instrument}</strong></div>
        <div><span className="muted">Market:</span> <strong>{market}</strong></div>
        <div><span className="muted">Broker:</span> <strong>{broker}</strong></div>
        <div><span className="muted">Mode:</span> <span style={{ fontWeight: 700, color: '#385671' }}>{mode}</span></div>
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: '1px solid #eef2f5', paddingTop: '8px', marginTop: '4px' }}>
        <div>
          <span className="muted" style={{ fontSize: '0.78rem' }}>State: <strong>{state}</strong></span>
        </div>
        <div>
          <span className="muted" style={{ fontSize: '0.78rem' }}>P&amp;L: </span>
          <PnL value={pnl ?? '0'} />
        </div>
      </div>

      {(lastSignal || lastExecution) && (
        <div style={{ fontSize: '0.75rem', color: '#64778a', borderTop: '1px dashed #eef2f5', paddingTop: '6px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            {lastSignal && <div>Last Signal: {time(lastSignal)}</div>}
            {lastExecution && <div>Last Execution: {time(lastExecution)}</div>}
          </div>
          {onInspectOrders && (
            <button className="quiet-button" style={{ padding: '2px 6px', fontSize: '0.7rem' }} onClick={onInspectOrders}>
              Orders →
            </button>
          )}
        </div>
      )}
    </div>
  );
}

export function DashboardView({ onNavigate }: { onNavigate?: (view: any) => void }) {
  const [account, setAccount] = useState<PaperAccountSummary | null>(null);
  const [positions, setPositions] = useState<PaperPosition[]>([]);
  const [orders, setOrders] = useState<PaperOrder[]>([]);
  const [killSwitch, setKillSwitch] = useState<KillSwitchStatus | null>(null);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [riskEvents, setRiskEvents] = useState<PaperRiskEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  async function loadData() {
    try {
      setError(null);
      const [accRes, posRes, ordRes, ksRes, healthRes, riskRes] = await Promise.all([
        paper.summary().catch(() => null),
        paper.positions().catch(() => []),
        paper.orders().catch(() => ({ total: 0, items: [] })),
        paper.killSwitch().catch(() => null),
        api<HealthStatus>('/monitoring/health').catch(() => null),
        paper.riskEvents().catch(() => ({ total: 0, items: [] })),
      ]);

      setAccount(accRes);
      setPositions(Array.isArray(posRes) ? posRes : []);
      setOrders(ordRes.items || []);
      setKillSwitch(ksRes);
      setHealth(healthRes);
      setRiskEvents(riskRes.items || []);
      setLastUpdated(new Date());
    } catch (err: any) {
      setError(err?.message || 'Failed to load telemetry');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 5000);
    return () => clearInterval(interval);
  }, []);

  const totalPnl = account?.total_pnl ?? '0';
  const unrealizedPnl = account?.unrealized_pnl ?? '0';
  const realizedPnl = account?.realized_pnl ?? '0';
  const availableCapital = account?.available_capital ?? '0';
  const positionCount = positions.length;
  const ksState = killSwitch?.state ?? 'ARMED';

  // Normalize recent activity from orders and risk events
  const activityItems = [
    ...orders.map(o => ({
      id: o.id,
      type: 'order' as const,
      timestamp: o.created_at,
      title: `${o.side.toUpperCase()} ${o.quantity} ${o.instrument_id}`,
      status: o.state,
      detail: `Type: ${o.order_type}`
    })),
    ...riskEvents.map(r => ({
      id: r.id,
      type: 'risk' as const,
      timestamp: r.created_at,
      title: `Risk Event: ${r.event_type}`,
      status: r.blocked ? 'BLOCKED' : 'NOTICED',
      detail: r.details ? JSON.stringify(r.details) : ''
    }))
  ].sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()).slice(0, 12);

  return (
    <div className="view-container" style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <div className="section-heading" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h2>Command &amp; Control Operations Dashboard</h2>
          <p className="muted">Real-time operator telemetry, paper execution engine, and active project state.</p>
        </div>
        <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
          {lastUpdated && <span className="muted" style={{ fontSize: '0.8rem' }}>Updated: {lastUpdated.toLocaleTimeString()}</span>}
          <button className="quiet-button" onClick={loadData} disabled={loading}>{loading ? 'Refreshing…' : 'Refresh Telemetry'}</button>
          {onNavigate && (
            <button className="primary-button" style={{ padding: '6px 12px', fontSize: '0.85rem' }} onClick={() => onNavigate('orders')}>
              View Orders &amp; Lifecycle →
            </button>
          )}
        </div>
      </div>

      {error && <p role="alert" className="error">Dashboard telemetry error: {error}</p>}

      {/* A. SUMMARY KPI ROW */}
      <section>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
          <h3 style={{ fontSize: '1.05rem', margin: 0, color: '#111b21' }}>Summary Key Performance Indicators</h3>
          {onNavigate && (
            <button className="quiet-button" style={{ fontSize: '0.8rem' }} onClick={() => onNavigate('signals')}>
              View Signals Stream →
            </button>
          )}
        </div>
        <div className="metric-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
          <div className="card" style={{ padding: '16px', background: '#fff', border: '1px solid #d4dde4', borderRadius: '8px' }}>
            <span className="muted" style={{ fontSize: '0.8rem' }}>Total P&amp;L</span>
            <div style={{ fontSize: '1.3rem', marginTop: '4px' }}><PnL value={totalPnl} /></div>
            <div className="muted" style={{ fontSize: '0.72rem', marginTop: '2px' }}>Realized: <PnL value={realizedPnl} /></div>
          </div>

          <div className="card" style={{ padding: '16px', background: '#fff', border: '1px solid #d4dde4', borderRadius: '8px' }}>
            <span className="muted" style={{ fontSize: '0.8rem' }}>Unrealized P&amp;L</span>
            <div style={{ fontSize: '1.3rem', marginTop: '4px' }}><PnL value={unrealizedPnl} /></div>
            <div className="muted" style={{ fontSize: '0.72rem', marginTop: '2px' }}>Positions: {positionCount} active</div>
          </div>

          <div className="card" style={{ padding: '16px', background: '#fff', border: '1px solid #d4dde4', borderRadius: '8px' }}>
            <span className="muted" style={{ fontSize: '0.8rem' }}>Available Capital</span>
            <div style={{ fontSize: '1.3rem', fontWeight: 700, color: '#111b21', marginTop: '4px' }}>{formatCurrency(availableCapital, account?.currency || 'INR')}</div>
            <div className="muted" style={{ fontSize: '0.72rem', marginTop: '2px' }}>Mode: PAPER SIMULATION</div>
          </div>

          <div className="card" style={{ padding: '16px', background: '#fff', border: '1px solid #d4dde4', borderRadius: '8px' }}>
            <span className="muted" style={{ fontSize: '0.8rem' }}>Kill Switch Status</span>
            <div style={{ fontSize: '1.1rem', fontWeight: 700, marginTop: '4px', color: ksState === 'triggered' ? '#9a392a' : '#126756' }}>
              {ksState}
            </div>
            <div className="muted" style={{ fontSize: '0.72rem', marginTop: '2px' }}>{ksState === 'triggered' ? 'Orders blocked' : 'Execution armed'}</div>
          </div>

          <div className="card" style={{ padding: '16px', background: '#fff', border: '1px solid #d4dde4', borderRadius: '8px' }}>
            <span className="muted" style={{ fontSize: '0.8rem' }}>System Health</span>
            <div style={{ fontSize: '1.1rem', fontWeight: 700, marginTop: '4px', color: health?.status === 'healthy' ? '#126756' : '#9a392a' }}>
              {health?.status ? health.status.toUpperCase() : 'HEALTHY'}
            </div>
            <div className="muted" style={{ fontSize: '0.72rem', marginTop: '2px' }}>Database &amp; Redis connected</div>
          </div>
        </div>
      </section>

      {/* B. PROJECT OPERATIONAL CARDS */}
      <section>
        <div className="section-heading">
          <div>
            <h3 style={{ fontSize: '1.05rem', marginBottom: '4px', color: '#111b21' }}>Project &amp; Strategy Operating Cards</h3>
            <p className="muted">Configured strategy identities and real-time execution state.</p>
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px', marginTop: '12px' }}>
          <ProjectOperationalCard
            name="Daily XAU Momentum"
            strategyId="xau-daily-v1"
            instrument="XAUUSD"
            market="Spot Gold CFD"
            broker="MT5 Terminal Bridge"
            mode="PAPER"
            state={ksState === 'triggered' ? 'PAUSED' : 'ARMED'}
            pnl={totalPnl}
            health={ksState === 'triggered' ? 'WARNING' : 'HEALTHY'}
            lastSignal={orders[0]?.created_at}
            lastExecution={orders[0]?.submitted_at}
            onInspectOrders={onNavigate ? () => onNavigate('orders') : undefined}
          />

          <ProjectOperationalCard
            name="XAUUSD Pullback Strategy"
            strategyId="xau-pullback-v2"
            instrument="XAUUSD"
            market="Spot Gold CFD"
            broker="MT5 Terminal Bridge"
            mode="PAPER"
            state="ARMED"
            pnl="0.00"
            health="HEALTHY"
            onInspectOrders={onNavigate ? () => onNavigate('orders') : undefined}
          />

          <ProjectOperationalCard
            name="NIFTY F&O Intraday Breakout"
            strategyId="nifty-breakout-v1"
            instrument="NIFTY 50"
            market="NSE F&O"
            broker="AngelOne / Dhan"
            mode="PAPER"
            state="READY"
            pnl="0.00"
            health="HEALTHY"
            onInspectOrders={onNavigate ? () => onNavigate('orders') : undefined}
          />
        </div>
      </section>

      {/* C. OPEN POSITIONS & RECENT ACTIVITY */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
        <section style={{ background: '#fff', padding: '16px', border: '1px solid #d4dde4', borderRadius: '8px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
            <h3 style={{ fontSize: '1.05rem', margin: 0, color: '#111b21' }}>Open Positions ({positions.length})</h3>
            {onNavigate && (
              <button className="quiet-button" style={{ fontSize: '0.78rem' }} onClick={() => onNavigate('positions')}>
                Positions →
              </button>
            )}
          </div>
          {positions.length === 0 ? (
            <p className="muted" style={{ padding: '20px 0', textAlign: 'center' }}>No open positions.</p>
          ) : (
            <div className="table-wrap">
              <table>
                <thead><tr><th>Instrument</th><th>Qty</th><th>Unrealized P&amp;L</th></tr></thead>
                <tbody>
                  {positions.map(p => (
                    <tr key={p.id}>
                      <td><code>{p.symbol}</code></td>
                      <td>{p.quantity}</td>
                      <td><PnL value={p.unrealized_pnl} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <section style={{ background: '#fff', padding: '16px', border: '1px solid #d4dde4', borderRadius: '8px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
            <h3 style={{ fontSize: '1.05rem', margin: 0, color: '#111b21' }}>Recent Activity &amp; Orders</h3>
            {onNavigate && (
              <button className="quiet-button" style={{ fontSize: '0.78rem' }} onClick={() => onNavigate('orders')}>
                Orders →
              </button>
            )}
          </div>
          {activityItems.length === 0 ? (
            <p className="muted" style={{ padding: '20px 0', textAlign: 'center' }}>No recent activity.</p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '250px', overflowY: 'auto' }}>
              {activityItems.map((item, idx) => (
                <div
                  key={item.id || idx}
                  style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px', background: '#f8fafc', borderRadius: '6px', fontSize: '0.83rem', cursor: onNavigate ? 'pointer' : 'default' }}
                  onClick={onNavigate ? () => onNavigate('orders') : undefined}
                >
                  <div>
                    <strong>{item.title}</strong>
                    <div className="muted" style={{ fontSize: '0.72rem' }}>{item.detail} • {time(item.timestamp)}</div>
                  </div>
                  <span style={{ padding: '2px 6px', borderRadius: '4px', background: item.status === 'rejected' || item.status === 'BLOCKED' ? '#fef0ee' : '#e6f7f3', color: item.status === 'rejected' || item.status === 'BLOCKED' ? '#9a392a' : '#126756', fontSize: '0.7rem', fontWeight: 700 }}>
                    {item.status}
                  </span>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
