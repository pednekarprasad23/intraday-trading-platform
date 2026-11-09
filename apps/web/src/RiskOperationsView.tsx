import { useEffect, useState } from 'react';
import { paper, api, type PaperAccountSummary, type KillSwitchStatus, type PaperRiskEvent } from './api';

function time(value: string | null) {
  if (!value) return '—';
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

function PnLBadge({ value }: { value: string | number }) {
  const num = typeof value === 'string' ? parseFloat(value) : value;
  const color = num > 0 ? '#126756' : num < 0 ? '#9a392a' : '#64778a';
  return <strong style={{ color }}>{num > 0 ? '+' : ''}{num.toLocaleString('en-IN', { maximumFractionDigits: 2 })}</strong>;
}

export function RiskOperationsView() {
  const [summary, setSummary] = useState<PaperAccountSummary | null>(null);
  const [killSwitch, setKillSwitch] = useState<KillSwitchStatus | null>(null);
  const [riskEvents, setRiskEvents] = useState<PaperRiskEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Trigger kill switch modal state
  const [showTriggerModal, setShowTriggerModal] = useState(false);
  const [triggerReason, setTriggerReason] = useState('Manual risk operator trigger');
  const [triggering, setTriggering] = useState(false);

  // Reset kill switch modal state
  const [showResetModal, setShowResetModal] = useState(false);
  const [resetting, setResetting] = useState(false);

  // Reset paper account modal state
  const [showResetAccountModal, setShowResetAccountModal] = useState(false);
  const [resettingAccount, setResettingAccount] = useState(false);

  async function loadData() {
    try {
      setLoading(true);
      setError(null);
      const [sumRes, ksRes, eventsRes] = await Promise.all([
        paper.summary(),
        paper.killSwitch(),
        paper.riskEvents(0),
      ]);
      setSummary(sumRes);
      setKillSwitch(ksRes);
      setRiskEvents(eventsRes.items || []);
    } catch (err: any) {
      setError(err?.message || 'Failed to load risk operations data');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadData();
    // 5-second polling per V2.5 refresh requirement
    const interval = setInterval(() => {
      void loadData();
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  async function handleTriggerKillSwitch() {
    if (!triggerReason.trim()) return;
    setTriggering(true);
    try {
      const updated = await paper.triggerKillSwitch(triggerReason);
      setKillSwitch(updated);
      setShowTriggerModal(false);
      void loadData();
    } catch (err: any) {
      setError(err?.message || 'Failed to trigger kill switch');
    } finally {
      setTriggering(false);
    }
  }

  async function handleResetKillSwitch() {
    setResetting(true);
    try {
      const updated = await paper.resetKillSwitch();
      setKillSwitch(updated);
      setShowResetModal(false);
      void loadData();
    } catch (err: any) {
      setError(err?.message || 'Failed to reset kill switch');
    } finally {
      setResetting(false);
    }
  }

  async function handleResetAccount() {
    setResettingAccount(true);
    try {
      const updated = await paper.resetAccount(summary?.account_id);
      setSummary(updated);
      setShowResetAccountModal(false);
      void loadData();
    } catch (err: any) {
      setError(err?.message || 'Failed to reset paper account');
    } finally {
      setResettingAccount(false);
    }
  }

  const isArmed = killSwitch?.state === 'armed';

  return (
    <div className="view-container" style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div className="section-heading" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h2>Risk Operations Console</h2>
          <p className="muted">Backend-authoritative risk limits, kill switch safety controls, and execution event audits.</p>
        </div>
        <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
          <span style={{ padding: '4px 10px', borderRadius: '6px', background: isArmed ? '#e6f7f3' : '#fef0ee', color: isArmed ? '#126756' : '#9a392a', fontSize: '0.8rem', fontWeight: 800 }}>
            KILL SWITCH: {killSwitch?.state?.toUpperCase() || 'UNKNOWN'}
          </span>
          <button className="quiet-button" onClick={() => void loadData()} disabled={loading}>
            {loading ? 'Refreshing…' : 'Refresh State'}
          </button>
        </div>
      </div>

      {error && <p role="alert" className="error">Risk error: {error}</p>}

      {/* Operational Safety Mode Banner */}
      <div style={{ background: '#f8fafc', border: '1px solid #d4dde4', borderRadius: '8px', padding: '16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
        <div style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
          <div>
            <span className="muted" style={{ fontSize: '0.75rem', display: 'block' }}>Execution Mode</span>
            <strong style={{ color: '#126756', fontSize: '0.95rem' }}>PAPER / SIMULATION</strong>
          </div>
          <div style={{ borderLeft: '1px solid #d4dde4', paddingLeft: '16px' }}>
            <span className="muted" style={{ fontSize: '0.75rem', display: 'block' }}>Broker Execution Authority</span>
            <strong style={{ color: '#64778a', fontSize: '0.95rem' }}>READ-ONLY / SIMULATED ROUTING</strong>
          </div>
          <div style={{ borderLeft: '1px solid #d4dde4', paddingLeft: '16px' }}>
            <span className="muted" style={{ fontSize: '0.75rem', display: 'block' }}>Live Trading</span>
            <strong style={{ color: '#9a392a', fontSize: '0.95rem' }}>DISABLED (Fail-Closed)</strong>
          </div>
        </div>
        <div>
          {isArmed ? (
            <button
              onClick={() => setShowTriggerModal(true)}
              style={{ background: '#9a392a', color: '#fff', border: 'none', padding: '8px 16px', borderRadius: '6px', fontWeight: 700, cursor: 'pointer' }}
            >
              Trigger Emergency Kill Switch
            </button>
          ) : (
            <button
              onClick={() => setShowResetModal(true)}
              style={{ background: '#126756', color: '#fff', border: 'none', padding: '8px 16px', borderRadius: '6px', fontWeight: 700, cursor: 'pointer' }}
            >
              Reset Kill Switch (Operator Auth)
            </button>
          )}
        </div>
      </div>

      {/* Risk & Capital KPIs */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
        <div style={{ background: '#fff', padding: '16px', borderRadius: '8px', border: '1px solid #d4dde4', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
          <div>
            <span className="muted" style={{ fontSize: '0.78rem' }}>Available Capital</span>
            <div style={{ fontSize: '1.25rem', fontWeight: 700, marginTop: '4px' }}>
              {summary ? `₹${parseFloat(summary.available_capital.toString()).toLocaleString('en-IN', { maximumFractionDigits: 2 })}` : '—'}
            </div>
            <span className="muted" style={{ fontSize: '0.72rem' }}>Initial: ₹{summary ? parseFloat(summary.initial_capital.toString()).toLocaleString() : '—'}</span>
          </div>
          <button
            className="quiet-button"
            onClick={() => setShowResetAccountModal(true)}
            style={{ marginTop: '12px', fontSize: '0.75rem', alignSelf: 'flex-start', color: '#9a392a', borderColor: '#d4dde4', padding: '4px 8px' }}
          >
            Reset Account &amp; Positions
          </button>
        </div>
        <div style={{ background: '#fff', padding: '16px', borderRadius: '8px', border: '1px solid #d4dde4' }}>
          <span className="muted" style={{ fontSize: '0.78rem' }}>Reserved Capital</span>
          <div style={{ fontSize: '1.25rem', fontWeight: 700, marginTop: '4px' }}>
            {summary ? `₹${parseFloat(summary.reserved_capital.toString()).toLocaleString('en-IN', { maximumFractionDigits: 2 })}` : '—'}
          </div>
          <span className="muted" style={{ fontSize: '0.72rem' }}>Open positions value</span>
        </div>
        <div style={{ background: '#fff', padding: '16px', borderRadius: '8px', border: '1px solid #d4dde4' }}>
          <span className="muted" style={{ fontSize: '0.78rem' }}>Total P&amp;L</span>
          <div style={{ fontSize: '1.25rem', marginTop: '4px' }}>
            <PnLBadge value={summary?.total_pnl || 0} />
          </div>
          <span className="muted" style={{ fontSize: '0.72rem' }}>Unrealized + Realized</span>
        </div>
        <div style={{ background: '#fff', padding: '16px', borderRadius: '8px', border: '1px solid #d4dde4' }}>
          <span className="muted" style={{ fontSize: '0.78rem' }}>Open Positions Count</span>
          <div style={{ fontSize: '1.25rem', fontWeight: 700, marginTop: '4px' }}>
            {summary?.position_count ?? '—'}
          </div>
          <span className="muted" style={{ fontSize: '0.72rem' }}>Active risk exposures</span>
        </div>
      </div>

      {/* Kill Switch Detail Status Box */}
      <section style={{ background: '#fff', padding: '20px', borderRadius: '8px', border: '1px solid #d4dde4' }}>
        <h3 style={{ margin: '0 0 12px 0', fontSize: '1rem' }}>Kill Switch State &amp; Audit</h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '16px', fontSize: '0.85rem' }}>
          <div>
            <span className="muted">State Name:</span> <strong>{killSwitch?.name || 'global'}</strong>
          </div>
          <div>
            <span className="muted">Current Status:</span> <strong style={{ color: isArmed ? '#126756' : '#9a392a' }}>{killSwitch?.state?.toUpperCase()}</strong>
          </div>
          <div>
            <span className="muted">Triggered At:</span> {time(killSwitch?.triggered_at || null)}
          </div>
          <div>
            <span className="muted">Reason:</span> {killSwitch?.reason || '—'}
          </div>
          <div>
            <span className="muted">Reset At:</span> {time(killSwitch?.reset_at || null)}
          </div>
          <div>
            <span className="muted">Auto-Triggered:</span> {killSwitch?.auto_triggered ? 'Yes' : 'No'}
          </div>
        </div>
      </section>

      {/* Recent Risk Events & Blocked Orders */}
      <section style={{ background: '#fff', padding: '20px', borderRadius: '8px', border: '1px solid #d4dde4' }}>
        <h3 style={{ margin: '0 0 12px 0', fontSize: '1rem' }}>Recent Risk Events &amp; Blocked Activity</h3>
        {riskEvents.length === 0 ? (
          <p className="muted" style={{ textAlign: 'center', padding: '30px 0' }}>No risk events recorded. All submitted orders complied with limits.</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Event Type</th>
                  <th>Blocked</th>
                  <th>Order ID</th>
                  <th>Details</th>
                  <th>Timestamp</th>
                </tr>
              </thead>
              <tbody>
                {riskEvents.map(event => (
                  <tr key={event.id}>
                    <td><code>{event.event_type}</code></td>
                    <td>
                      <span style={{ padding: '2px 6px', borderRadius: '4px', background: event.blocked ? '#fef0ee' : '#e6f7f3', color: event.blocked ? '#9a392a' : '#126756', fontSize: '0.75rem', fontWeight: 700 }}>
                        {event.blocked ? 'BLOCKED' : 'LOGGED'}
                      </span>
                    </td>
                    <td><code style={{ fontSize: '0.7rem' }}>{event.order_id ? event.order_id.substring(0, 12) + '…' : '—'}</code></td>
                    <td style={{ fontSize: '0.8rem' }}>{JSON.stringify(event.details)}</td>
                    <td style={{ fontSize: '0.8rem' }}>{time(event.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Trigger Kill Switch Confirmation Modal */}
      {showTriggerModal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div style={{ background: '#fff', padding: '24px', borderRadius: '8px', width: '450px', maxWidth: '90%', display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <h3 style={{ margin: 0, color: '#9a392a' }}>⚠️ Trigger Emergency Kill Switch</h3>
            <p style={{ fontSize: '0.85rem', margin: 0 }}>
              This will immediately halt all new order submissions across the paper trading engine. Existing open positions and monitoring remain active.
            </p>
            <label style={{ fontSize: '0.85rem', display: 'flex', flexDirection: 'column', gap: '6px' }}>
              Reason for triggering:
              <input
                type="text"
                value={triggerReason}
                onChange={e => setTriggerReason(e.target.value)}
                style={{ padding: '8px', borderRadius: '4px', border: '1px solid #d4dde4' }}
              />
            </label>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '10px' }}>
              <button className="quiet-button" onClick={() => setShowTriggerModal(false)} disabled={triggering}>Cancel</button>
              <button
                onClick={() => void handleTriggerKillSwitch()}
                disabled={triggering || !triggerReason.trim()}
                style={{ background: '#9a392a', color: '#fff', border: 'none', padding: '8px 16px', borderRadius: '6px', fontWeight: 700, cursor: 'pointer' }}
              >
                {triggering ? 'Triggering…' : 'Confirm & Trigger'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Reset Kill Switch Confirmation Modal */}
      {showResetModal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div style={{ background: '#fff', padding: '24px', borderRadius: '8px', width: '450px', maxWidth: '90%', display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <h3 style={{ margin: 0, color: '#126756' }}>Reset Kill Switch</h3>
            <p style={{ fontSize: '0.85rem', margin: 0 }}>
              This will re-arm the trading engine after operator confirmation. Ensure risk conditions have been reviewed and resolved.
            </p>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '10px' }}>
              <button className="quiet-button" onClick={() => setShowResetModal(false)} disabled={resetting}>Cancel</button>
              <button
                onClick={() => void handleResetKillSwitch()}
                disabled={resetting}
                style={{ background: '#126756', color: '#fff', border: 'none', padding: '8px 16px', borderRadius: '6px', fontWeight: 700, cursor: 'pointer' }}
              >
                {resetting ? 'Resetting…' : 'Confirm & Re-arm'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Reset Account Modal */}
      {showResetAccountModal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div style={{ background: '#fff', padding: '24px', borderRadius: '8px', width: '450px', maxWidth: '90%', display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <h3 style={{ margin: 0, color: '#9a392a' }}>Reset Paper Account Capital &amp; Positions</h3>
            <p style={{ fontSize: '0.85rem', margin: 0 }}>
              This will restore available capital back to initial capital and clear all open simulated positions. A risk audit event will be recorded.
            </p>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '10px' }}>
              <button className="quiet-button" onClick={() => setShowResetAccountModal(false)} disabled={resettingAccount}>Cancel</button>
              <button
                onClick={() => void handleResetAccount()}
                disabled={resettingAccount}
                style={{ background: '#9a392a', color: '#fff', border: 'none', padding: '8px 16px', borderRadius: '6px', fontWeight: 700, cursor: 'pointer' }}
              >
                {resettingAccount ? 'Resetting…' : 'Confirm Account Reset'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
