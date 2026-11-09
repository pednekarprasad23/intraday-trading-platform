import { useEffect, useState } from 'react';
import { paper, type PaperOrder } from './api';

function time(value: string | null) {
  if (!value) return '—';
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

function stateBadge(state: string) {
  const colorMap: Record<string, { bg: string; color: string }> = {
    filled: { bg: '#e6f7f3', color: '#126756' },
    submitted: { bg: '#e6f0ff', color: '#1d4ed8' },
    pending: { bg: '#fff8e6', color: '#8a6d00' },
    rejected: { bg: '#fef0ee', color: '#9a392a' },
    cancelled: { bg: '#f0f0f0', color: '#64778a' },
    partial: { bg: '#e6f7ff', color: '#0369a1' },
  };
  const badge = colorMap[state] || { bg: '#f0f0f0', color: '#64778a' };
  return (
    <span style={{ display: 'inline-block', borderRadius: '6px', padding: '3px 8px', background: badge.bg, color: badge.color, fontSize: '0.74rem', fontWeight: 700 }}>
      {state.toUpperCase()}
    </span>
  );
}

function sideBadge(side: string) {
  const isBuy = side.toLowerCase() === 'buy';
  return (
    <span style={{ display: 'inline-block', borderRadius: '6px', padding: '3px 8px', background: isBuy ? '#e6f7f3' : '#fef0ee', color: isBuy ? '#126756' : '#9a392a', fontSize: '0.74rem', fontWeight: 700 }}>
      {side.toUpperCase()}
    </span>
  );
}

export function OrdersView() {
  const [orders, setOrders] = useState<PaperOrder[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedState, setSelectedState] = useState<string>('');
  const [selectedOrder, setSelectedOrder] = useState<PaperOrder | null>(null);

  async function loadOrders(stateFilter?: string) {
    try {
      setLoading(true);
      setError(null);
      const res = await paper.orders(0, stateFilter || undefined);
      setOrders(res.items || []);
      setTotal(res.total || 0);
    } catch (err: any) {
      setError(err?.message || 'Failed to load paper orders');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadOrders(selectedState);
  }, [selectedState]);

  return (
    <div className="view-container" style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <div className="section-heading" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h2>Orders &amp; Execution Lifecycle</h2>
          <p className="muted">Real-time paper trading order stream, execution states, fills, and risk rejections ({total} total).</p>
        </div>
        <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
          <select
            value={selectedState}
            onChange={e => setSelectedState(e.target.value)}
            style={{ padding: '6px 12px', borderRadius: '6px', border: '1px solid #d4dde4', background: '#fff', fontSize: '0.85rem' }}
          >
            <option value="">All States</option>
            <option value="pending">Pending</option>
            <option value="submitted">Submitted</option>
            <option value="filled">Filled</option>
            <option value="partial">Partial</option>
            <option value="rejected">Rejected</option>
            <option value="cancelled">Cancelled</option>
          </select>
          <button className="quiet-button" onClick={() => void loadOrders(selectedState)} disabled={loading}>
            {loading ? 'Refreshing…' : 'Refresh Orders'}
          </button>
        </div>
      </div>

      {error && <p role="alert" className="error">Orders error: {error}</p>}

      <section style={{ background: '#fff', padding: '16px', border: '1px solid #d4dde4', borderRadius: '8px' }}>
        {orders.length === 0 && !loading ? (
          <p className="muted" style={{ padding: '40px 0', textAlign: 'center' }}>No orders found for the selected filter.</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Strategy / Project</th>
                  <th>Instrument</th>
                  <th>Side</th>
                  <th>Type</th>
                  <th>Qty / Filled</th>
                  <th>Price</th>
                  <th>State</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {orders.map(o => (
                  <tr key={o.id}>
                    <td>{time(o.created_at)}</td>
                    <td><code>{o.strategy_id || 'manual'}</code></td>
                    <td><code style={{ fontSize: '0.78rem' }}>{o.instrument_id}</code></td>
                    <td>{sideBadge(o.side)}</td>
                    <td>{o.order_type.toUpperCase()}</td>
                    <td>{o.quantity} / {o.filled_quantity}</td>
                    <td>{o.price ? `₹${o.price}` : 'Market'}</td>
                    <td>{stateBadge(o.state)}</td>
                    <td>
                      <button className="quiet-button" style={{ padding: '2px 8px', fontSize: '0.75rem' }} onClick={() => setSelectedOrder(o)}>
                        Inspect
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Order Detail Modal / Drawer */}
      {selectedOrder && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', justifyContent: 'flex-end', zIndex: 1000 }}>
          <div style={{ width: '500px', background: '#fff', height: '100%', padding: '24px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '20px', boxShadow: '-4px 0 20px rgba(0,0,0,0.15)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #eef2f5', paddingBottom: '12px' }}>
              <h3 style={{ margin: 0, fontSize: '1.1rem' }}>Order Execution Details</h3>
              <button className="quiet-button" onClick={() => setSelectedOrder(null)}>Close</button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', fontSize: '0.85rem' }}>
              <div><span className="muted">Order ID:</span> <code style={{ fontSize: '0.75rem' }}>{selectedOrder.id}</code></div>
              <div><span className="muted">Strategy ID:</span> <strong>{selectedOrder.strategy_id || 'manual'}</strong></div>
              <div><span className="muted">Instrument ID:</span> <code style={{ fontSize: '0.75rem' }}>{selectedOrder.instrument_id}</code></div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                <div><span className="muted">Side:</span> {sideBadge(selectedOrder.side)}</div>
                <div><span className="muted">State:</span> {stateBadge(selectedOrder.state)}</div>
                <div><span className="muted">Type:</span> <strong>{selectedOrder.order_type.toUpperCase()}</strong></div>
                <div><span className="muted">Execution Mode:</span> <strong style={{ color: '#126756' }}>PAPER</strong></div>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                <div><span className="muted">Requested Qty:</span> <strong>{selectedOrder.quantity}</strong></div>
                <div><span className="muted">Filled Qty:</span> <strong>{selectedOrder.filled_quantity}</strong></div>
              </div>
              <div><span className="muted">Limit Price:</span> <strong>{selectedOrder.price ? `₹${selectedOrder.price}` : 'Market Order'}</strong></div>
            </div>

            {/* Execution Lifecycle Stepper */}
            <div style={{ borderTop: '1px solid #eef2f5', paddingTop: '16px' }}>
              <h4 style={{ margin: '0 0 10px 0', fontSize: '0.95rem' }}>Execution Lifecycle</h4>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '0.8rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 10px', background: '#f8fafc', borderRadius: '6px' }}>
                  <span>1. Created / Received</span>
                  <span className="muted">{time(selectedOrder.created_at)}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 10px', background: selectedOrder.submitted_at ? '#e6f7f3' : '#f8fafc', borderRadius: '6px' }}>
                  <span>2. Submitted to Paper Engine</span>
                  <span className="muted">{time(selectedOrder.submitted_at)}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 10px', background: selectedOrder.filled_at ? '#e6f7f3' : selectedOrder.state === 'rejected' ? '#fef0ee' : '#f8fafc', borderRadius: '6px' }}>
                  <span>3. {selectedOrder.state === 'rejected' ? 'Rejected' : 'Filled / Completed'}</span>
                  <span className="muted">{time(selectedOrder.filled_at)}</span>
                </div>
              </div>
            </div>

            {selectedOrder.rejected_reason && (
              <div style={{ background: '#fef0ee', border: '1px solid #f9dcd8', padding: '12px', borderRadius: '8px', color: '#9a392a', fontSize: '0.82rem' }}>
                <strong>Rejection Reason:</strong> {selectedOrder.rejected_reason}
              </div>
            )}

            <div style={{ borderTop: '1px solid #eef2f5', paddingTop: '16px' }}>
              <h4 style={{ margin: '0 0 10px 0', fontSize: '0.95rem' }}>Fills ({selectedOrder.fills.length})</h4>
              {selectedOrder.fills.length === 0 ? (
                <p className="muted" style={{ fontSize: '0.8rem' }}>No fills recorded for this order.</p>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {selectedOrder.fills.map(fill => (
                    <div key={fill.id} style={{ padding: '8px', background: '#f8fafc', borderRadius: '6px', fontSize: '0.8rem', display: 'flex', justifyContent: 'space-between' }}>
                      <div>
                        <div>Qty: <strong>{fill.quantity}</strong> @ ₹{fill.price}</div>
                        <div className="muted" style={{ fontSize: '0.72rem' }}>Comm: ₹{fill.commission} | Slippage: ₹{fill.slippage}</div>
                      </div>
                      <div className="muted" style={{ fontSize: '0.72rem' }}>{time(fill.filled_at)}</div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
