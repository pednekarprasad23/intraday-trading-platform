import { useEffect, useState } from 'react';
import { paper, api, type PaperPosition, type PaperOrder } from './api';

function time(value: string | null) {
  if (!value) return '—';
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

function PnLBadge({ value }: { value: string }) {
  const num = parseFloat(value);
  const color = num > 0 ? '#126756' : num < 0 ? '#9a392a' : '#64778a';
  return <strong style={{ color, fontSize: '0.95rem' }}>{num > 0 ? '+' : ''}{num.toLocaleString('en-IN', { maximumFractionDigits: 2 })}</strong>;
}

export function PositionsView() {
  const [positions, setPositions] = useState<PaperPosition[]>([]);
  const [orders, setOrders] = useState<PaperOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedPosition, setSelectedPosition] = useState<PaperPosition | null>(null);
  const [positionFills, setPositionFills] = useState<any[]>([]);
  const [loadingFills, setLoadingFills] = useState(false);

  async function loadData() {
    try {
      setLoading(true);
      setError(null);
      const [pos, ord] = await Promise.all([
        paper.positions(),
        paper.orders(),
      ]);
      setPositions(pos || []);
      setOrders(ord.items || []);
    } catch (err: any) {
      setError(err?.message || 'Failed to load positions');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadData();
  }, []);

  async function inspectPosition(pos: PaperPosition) {
    setSelectedPosition(pos);
    setLoadingFills(true);
    try {
      const res = await api<any[]>(`/paper/positions/${pos.id}/fills`);
      setPositionFills(res || []);
    } catch (err: any) {
      setError(err?.message || 'Failed to load position fills');
    } finally {
      setLoadingFills(false);
    }
  }

  const totalUnrealized = positions.reduce((sum, p) => sum + parseFloat(p.unrealized_pnl || '0'), 0);
  const totalRealized = positions.reduce((sum, p) => sum + parseFloat(p.realized_pnl || '0'), 0);

  return (
    <div className="view-container" style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <div className="section-heading" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h2>Positions &amp; P&amp;L</h2>
          <p className="muted">Open exposures, unrealized P&amp;L, and execution audit trails. All values backend-authoritative.</p>
        </div>
        <button className="quiet-button" onClick={() => void loadData()} disabled={loading}>
          {loading ? 'Refreshing…' : 'Refresh Positions'}
        </button>
      </div>

      {error && <p role="alert" className="error">Positions error: {error}</p>}

      {/* Summary KPI Strip */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '16px' }}>
        <div style={{ background: '#fff', padding: '16px', borderRadius: '8px', border: '1px solid #d4dde4' }}>
          <span className="muted" style={{ fontSize: '0.8rem' }}>Total Unrealized P&amp;L</span>
          <div style={{ fontSize: '1.2rem', marginTop: '4px' }}>
            <PnLBadge value={totalUnrealized.toString()} />
          </div>
        </div>
        <div style={{ background: '#fff', padding: '16px', borderRadius: '8px', border: '1px solid #d4dde4' }}>
          <span className="muted" style={{ fontSize: '0.8rem' }}>Total Realized P&amp;L</span>
          <div style={{ fontSize: '1.2rem', marginTop: '4px' }}>
            <PnLBadge value={totalRealized.toString()} />
          </div>
        </div>
        <div style={{ background: '#fff', padding: '16px', borderRadius: '8px', border: '1px solid #d4dde4' }}>
          <span className="muted" style={{ fontSize: '0.8rem' }}>Open Positions</span>
          <div style={{ fontSize: '1.2rem', fontWeight: 700, marginTop: '4px' }}>{positions.length}</div>
        </div>
        <div style={{ background: '#fff', padding: '16px', borderRadius: '8px', border: '1px solid #d4dde4' }}>
          <span className="muted" style={{ fontSize: '0.8rem' }}>Execution Mode</span>
          <div style={{ fontSize: '1.2rem', fontWeight: 700, marginTop: '4px', color: '#126756' }}>PAPER</div>
        </div>
      </div>

      <section style={{ background: '#fff', padding: '16px', border: '1px solid #d4dde4', borderRadius: '8px' }}>
        {positions.length === 0 && !loading ? (
          <p className="muted" style={{ padding: '40px 0', textAlign: 'center' }}>No open positions. (Realized P&amp;L: {totalRealized.toLocaleString()})</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Instrument / Symbol</th>
                  <th>Quantity</th>
                  <th>Avg Entry Price</th>
                  <th>Unrealized P&amp;L</th>
                  <th>Realized P&amp;L</th>
                  <th>Last Marked</th>
                  <th>Created</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {positions.map(pos => (
                  <tr key={pos.id}>
                    <td><code>{pos.symbol}</code></td>
                    <td>{pos.quantity}</td>
                    <td>{pos.avg_entry_price ? `₹${parseFloat(pos.avg_entry_price).toLocaleString()}` : '—'}</td>
                    <td><PnLBadge value={pos.unrealized_pnl} /></td>
                    <td><PnLBadge value={pos.realized_pnl} /></td>
                    <td>{time(pos.last_marked_at)}</td>
                    <td>{time(pos.created_at)}</td>
                    <td>
                      <button className="quiet-button" style={{ padding: '2px 8px', fontSize: '0.75rem' }} onClick={() => void inspectPosition(pos)}>
                        Audit Fills
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Position Trades/Fills Audit Panel */}
      {selectedPosition && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', justifyContent: 'flex-end', zIndex: 1000 }}>
          <div style={{ width: '550px', background: '#fff', height: '100%', padding: '24px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '20px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #eef2f5', paddingBottom: '12px' }}>
              <h3 style={{ margin: 0 }}>Position Audit: {selectedPosition.symbol}</h3>
              <button className="quiet-button" onClick={() => setSelectedPosition(null)}>Close</button>
            </div>

            <div style={{ background: '#f8fafc', padding: '12px', borderRadius: '8px', fontSize: '0.85rem', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
              <div><span className="muted">Instrument ID:</span> <code style={{ fontSize: '0.7rem' }}>{selectedPosition.instrument_id}</code></div>
              <div><span className="muted">Qty:</span> <strong>{selectedPosition.quantity}</strong></div>
              <div><span className="muted">Unrealized P&amp;L:</span> <PnLBadge value={selectedPosition.unrealized_pnl} /></div>
              <div><span className="muted">Realized P&amp;L:</span> <PnLBadge value={selectedPosition.realized_pnl} /></div>
            </div>

            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                <h4 style={{ margin: 0, fontSize: '0.95rem' }}>Contributing Fills (Correlation: STRONG)</h4>
                <span style={{ fontSize: '0.7rem', padding: '2px 6px', background: '#e6f0ff', color: '#1d4ed8', borderRadius: '4px', fontWeight: 700 }}>STRONG</span>
              </div>
              <p className="muted" style={{ fontSize: '0.75rem', margin: '0 0 12px 0' }}>
                Fills linked via instrument + account identity. No durable foreign key exists. Order → Position correlation is STRONG, not EXACT.
              </p>
              {loadingFills ? (
                <p className="muted">Loading fills…</p>
              ) : positionFills.length === 0 ? (
                <p className="muted" style={{ padding: '16px 0', textAlign: 'center' }}>No fills found for this position.</p>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {positionFills.map(fill => {
                    const matchingOrder = orders.find(o => o.id === fill.order_id);
                    return (
                      <div key={fill.id} style={{ padding: '10px', background: '#f8fafc', borderRadius: '6px', fontSize: '0.8rem', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                        <div>
                          <div>Order ID: <code style={{ fontSize: '0.7rem' }}>{matchingOrder ? matchingOrder.id.substring(0, 8) + '…' : fill.order_id.substring(0, 8) + '…'}</code></div>
                          <div style={{ marginTop: '2px' }}>Qty: <strong>{fill.quantity}</strong> @ ₹{fill.price}</div>
                          <div className="muted" style={{ fontSize: '0.72rem', marginTop: '2px' }}>
                            Comm: ₹{fill.commission} | Fees: ₹{fill.fees} | Slippage: ₹{fill.slippage}
                          </div>
                          {matchingOrder && (
                            <div style={{ fontSize: '0.72rem', marginTop: '2px' }}>
                              Side: <strong>{matchingOrder.side.toUpperCase()}</strong> | Type: {matchingOrder.order_type.toUpperCase()} | Strategy: <code>{matchingOrder.strategy_id || 'manual'}</code>
                            </div>
                          )}
                        </div>
                        <div className="muted" style={{ fontSize: '0.72rem', textAlign: 'right' }}>{time(fill.filled_at)}</div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
