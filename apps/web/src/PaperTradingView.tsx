import { useEffect, useState, type FormEvent } from 'react';
import { paper, api, type PaperAccountSummary, type PaperPosition, type PaperOrder, type KillSwitchStatus, type OrderSubmission, type PaperRiskEvent } from './api';

type Tab = 'summary' | 'orders' | 'positions' | 'killswitch' | 'risk';
const tabNames: Record<Tab, string> = { summary: 'Account', orders: 'Orders', positions: 'Positions', killswitch: 'Kill Switch', risk: 'Risk Events' };

function formatCurrency(value: string | null, currency: string = 'INR') {
  if (value == null) return '—';
  const num = parseFloat(value);
  if (isNaN(num)) return value;
  return new Intl.NumberFormat('en-IN', { style: 'currency', currency, minimumFractionDigits: 2 }).format(num);
}

function formatDecimal(value: string | null) {
  if (value == null) return '—';
  const num = parseFloat(value);
  if (isNaN(num)) return value;
  return num.toLocaleString('en-IN', { maximumFractionDigits: 4 });
}

function time(value: string | null) {
  return value ? new Date(value).toLocaleString(undefined, { timeZoneName: 'short' }) : '—';
}

function stateBadge(state: string) {
  const colorMap: Record<string, string> = {
    filled: '#e6f7f3', submitted: '#e6f0ff', pending: '#fff8e6',
    rejected: '#fef0ee', cancelled: '#f0f0f0', partial: '#e6f7ff',
    expired: '#f0f0f0', uncertain: '#fff0e6',
  };
  const bg = colorMap[state] ?? '#f0f0f0';
  return <span style={{ display: 'inline-block', borderRadius: '6px', padding: '4px 8px', background: bg, color: state === 'rejected' ? '#9a392a' : '#385671', fontSize: '0.74rem', fontWeight: 700 }}>{state}</span>;
}

function sideBadge(side: string) {
  if (side === 'buy') return <span style={{ display: 'inline-block', borderRadius: '6px', padding: '4px 8px', background: '#e6f7f3', color: '#126756', fontSize: '0.74rem', fontWeight: 700 }}>BUY</span>;
  return <span style={{ display: 'inline-block', borderRadius: '6px', padding: '4px 8px', background: '#fef0ee', color: '#9a392a', fontSize: '0.74rem', fontWeight: 700 }}>SELL</span>;
}

function ksStateBadge(state: string) {
  if (state === 'triggered') return <span style={{ display: 'inline-block', borderRadius: '6px', padding: '4px 8px', background: '#fef0ee', color: '#9a392a', fontSize: '0.74rem', fontWeight: 700 }}>TRIGGERED</span>;
  if (state === 'reset_pending') return <span style={{ display: 'inline-block', borderRadius: '6px', padding: '4px 8px', background: '#fff8e6', color: '#8a6d00', fontSize: '0.74rem', fontWeight: 700 }}>RESET PENDING</span>;
  return <span style={{ display: 'inline-block', borderRadius: '6px', padding: '4px 8px', background: '#e6f7f3', color: '#126756', fontSize: '0.74rem', fontWeight: 700 }}>ARMED</span>;
}

function PnL({ value }: { value: string | null }) {
  if (value == null) return <span>—</span>;
  const num = parseFloat(value);
  if (isNaN(num)) return <span>{value}</span>;
  const color = num > 0 ? '#126756' : num < 0 ? '#9a392a' : '#64778a';
  const sign = num > 0 ? '+' : '';
  return <span style={{ color, fontWeight: 700 }}>{sign}{num.toLocaleString('en-IN', { maximumFractionDigits: 2 })}</span>;
}

function PositionsTable({ positions }: { positions: PaperPosition[] }) {
  return <div className="table-wrap"><table>
    <thead><tr><th>Instrument</th><th>Qty</th><th>Avg Entry</th><th>Unrealized P&amp;L</th><th>Realized P&amp;L</th><th>Total P&amp;L</th><th>Last Marked</th></tr></thead>
    <tbody>{positions.map(p => {
      const totalPnl = String(parseFloat(p.unrealized_pnl || '0') + parseFloat(p.realized_pnl || '0'));
      return <tr key={p.id}>
        <td><code>{p.symbol}</code></td>
        <td>{formatDecimal(p.quantity)}</td>
        <td>{p.avg_entry_price ? parseFloat(p.avg_entry_price).toLocaleString('en-IN', { maximumFractionDigits: 2 }) : '—'}</td>
        <td><PnL value={p.unrealized_pnl} /></td>
        <td><PnL value={p.realized_pnl} /></td>
        <td><PnL value={totalPnl} /></td>
        <td>{time(p.last_marked_at)}</td>
      </tr>;
    })}</tbody>
  </table></div>;
}

function Pager({ total, offset, onChange }: { total: number; offset: number; onChange: (value: number) => void }) {
  const pageSize = 50;
  return <div className="pager"><button disabled={offset === 0} onClick={() => onChange(Math.max(0, offset - pageSize))}>Previous</button><span>{total === 0 ? '0 records' : `${offset + 1}–${Math.min(offset + pageSize, total)} of ${total}`}</span><button disabled={offset + pageSize >= total} onClick={() => onChange(offset + pageSize)}>Next</button></div>;
}

function KillSwitchPanel({ status, loading, error, onTrigger, onReset, onRefresh }: { status: KillSwitchStatus | null; loading: boolean; error: string; onTrigger: (reason: string) => void; onReset: () => void; onRefresh: () => void }) {
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const [triggerBusy, setTriggerBusy] = useState(false);
  const [confirmReset, setConfirmReset] = useState(false);
  const [confirmText, setConfirmText] = useState('');

  async function handleTrigger() {
    if (!reason.trim() || triggerBusy) return;
    setTriggerBusy(true);
    try { await onTrigger(reason.trim()); setReason(''); }
    finally { setTriggerBusy(false); }
  }

  async function handleReset() {
    if (busy) return;
    setBusy(true);
    try { await onReset(); setConfirmReset(false); setConfirmText(''); }
    finally { setBusy(false); }
  }

  return <section>
    <div className="section-heading"><div><h3>Kill Switch Control</h3><p className="muted">Emergency stop — blocks all new orders when triggered.</p></div></div>

    {error && <p role="alert" className="error">Kill switch unavailable: {error} <button className="quiet-button" onClick={onRefresh}>Retry</button></p>}
    {loading && <p role="status">Loading kill switch status…</p>}
    {!loading && !error && status && <>
      <div className="metric-grid">
        <div><span>Status</span><strong>{ksStateBadge(status.state)}</strong></div>
        <div><span>Triggered By</span><strong>{status.triggered_by ? 'User' : '—'}</strong></div>
        <div><span>Triggered At</span><strong>{time(status.triggered_at)}</strong></div>
      </div>
      {status.reason && <p className="notice-inline"><strong>Reason:</strong> {status.reason}</p>}

      {status.state === 'triggered' && !confirmReset && <p><button className="primary-button" onClick={() => setConfirmReset(true)}>Confirm Reset</button></p>}
      {confirmReset && <div style={{ display: 'flex', gap: '10px', alignItems: 'end', flexWrap: 'wrap', marginTop: '16px' }}>
        <label style={{ flex: '1', minWidth: '200px' }}>Type <code>RESET</code> to confirm<input value={confirmText} onChange={e => setConfirmText(e.target.value)} placeholder="Type RESET" /></label>
        <button className="primary-button" disabled={busy || confirmText !== 'RESET'} onClick={handleReset}>{busy ? 'Resetting…' : 'Reset Kill Switch'}</button>
        <button className="quiet-button" onClick={() => { setConfirmReset(false); setConfirmText(''); }}>Cancel</button>
      </div>}

      {status.state === 'armed' && <div style={{ marginTop: '20px' }}>
        <h4>Trigger Kill Switch</h4>
        <div className="search-form">
          <label>Reason<input value={reason} onChange={e => setReason(e.target.value)} placeholder="Reason for triggering" /></label>
          <button className="primary-button" disabled={triggerBusy || !reason.trim()} onClick={handleTrigger} style={{ background: '#9a392a', borderColor: '#9a392a' }}>{triggerBusy ? 'Triggering…' : 'Trigger Kill Switch'}</button>
        </div>
      </div>}
    </>}
  </section>;
}

function OrderForm({ onSubmit, loading, instruments, error }: { onSubmit: (body: OrderSubmission) => void; loading: boolean; instruments: { id: string; symbol: string }[]; error: string }) {
  const [side, setSide] = useState<'buy' | 'sell'>('buy');
  const [instrumentId, setInstrumentId] = useState('');
  const [quantity, setQuantity] = useState('');
  const [orderType, setOrderType] = useState('market');
  const [price, setPrice] = useState('');
  const [stopPrice, setStopPrice] = useState('');
  const [success, setSuccess] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (loading || !instrumentId || !quantity) return;
    const body: OrderSubmission = {
      instrument_id: instrumentId,
      side,
      quantity: parseFloat(quantity).toString(),
      order_type: orderType as OrderSubmission['order_type'],
    };
    if (orderType === 'limit' && price) body.price = parseFloat(price).toString();
    if ((orderType === 'stop' || orderType === 'stop_limit') && stopPrice) body.stop_price = parseFloat(stopPrice).toString();
    await onSubmit(body);
    setInstrumentId('');
    setQuantity('');
    setPrice('');
    setStopPrice('');
    setSide('buy');
    setOrderType('market');
    setSuccess(true);
    setTimeout(() => setSuccess(false), 3000);
  }

  return <section>
    <div className="section-heading"><div><h3>Submit Order</h3><p className="muted">Create a new paper order. Orders are executed through the risk validation pipeline.</p></div></div>

    {error && <p role="alert" className="error">{error}</p>}
    {success && <p style={{ padding: '13px 16px', background: '#e6f7f3', border: '1px solid #68d3bd', borderRadius: '9px', color: '#126756' }}>Order submitted successfully.</p>}

    <form onSubmit={handleSubmit} style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px', marginTop: '16px' }}>
      <label>Side<select value={side} onChange={e => setSide(e.target.value as 'buy' | 'sell')}><option value="buy">Buy</option><option value="sell">Sell</option></select></label>
      <label>Instrument<select value={instrumentId} onChange={e => setInstrumentId(e.target.value)} required><option value="">Select instrument</option>{instruments.map(i => <option key={i.id} value={i.id}>{i.symbol}</option>)}</select></label>
      <label>Quantity<input type="number" min="1" step="1" value={quantity} onChange={e => setQuantity(e.target.value)} placeholder="Quantity" required /></label>
      <label>Order Type<select value={orderType} onChange={e => setOrderType(e.target.value)}><option value="market">Market</option><option value="limit">Limit</option><option value="stop">Stop</option><option value="stop_limit">Stop Limit</option></select></label>
      {orderType === 'limit' && <label>Limit Price<input type="number" min="0.01" step="0.01" value={price} onChange={e => setPrice(e.target.value)} placeholder="Limit price" /></label>}
      {(orderType === 'stop' || orderType === 'stop_limit') && <label>Stop Price<input type="number" min="0.01" step="0.01" value={stopPrice} onChange={e => setStopPrice(e.target.value)} placeholder="Stop price" /></label>}
      <div style={{ display: 'flex', alignItems: 'end' }}><button className="primary-button" disabled={loading || !instrumentId || !quantity}>{loading ? 'Submitting…' : 'Submit Order'}</button></div>
    </form>
  </section>;
}

function OrdersView({ orders, loading, error, pagination, onPager, onRetry }: { orders: PaperOrder[]; loading: boolean; error: string; pagination: { total: number } | null; onPager: (offset: number) => void; onRetry: () => void }) {
  return <section>
    <div className="section-heading"><div><h3>Order History</h3><p className="muted">All paper orders and their execution status.</p></div></div>

    {error && <p role="alert" className="error">{error} <button className="quiet-button" onClick={onRetry}>Retry</button></p>}
    {loading && <p role="status">Loading orders…</p>}
    {!loading && !error && orders.length === 0 && <div className="empty-state"><strong>No orders recorded yet.</strong></div>}
    {!loading && !error && orders.length > 0 && <div className="table-wrap"><table>
      <thead><tr><th>Time</th><th>Side</th><th>Instrument</th><th>Type</th><th>Qty</th><th>Price</th><th>Filled</th><th>Status</th><th>Strategy</th></tr></thead>
      <tbody>{orders.map(o => <tr key={o.id}>
        <td>{time(o.created_at)}</td>
        <td>{sideBadge(o.side)}</td>
        <td><code>{o.instrument_id}</code></td>
        <td>{o.order_type}</td>
        <td>{formatDecimal(o.quantity)}</td>
        <td>{o.price ? parseFloat(o.price).toLocaleString('en-IN', { maximumFractionDigits: 2 }) : '—'}</td>
        <td>{formatDecimal(o.filled_quantity)}</td>
        <td>{stateBadge(o.state)}</td>
        <td>{o.strategy_id || '—'}</td>
      </tr>)}</tbody>
    </table></div>}
    {!loading && !error && pagination && <Pager total={pagination.total} offset={0} onChange={onPager} />}
  </section>;
}

function PositionsView({ positions, loading, error }: { positions: PaperPosition[]; loading: boolean; error: string }) {
  return <section>
    <div className="section-heading"><div><h3>Open Positions</h3><p className="muted">Current market positions with mark-to-market values.</p></div></div>

    {error && <p role="alert" className="error">{error}</p>}
    {loading && <p role="status">Loading positions…</p>}
    {!loading && !error && positions.length === 0 && <div className="empty-state"><strong>No open positions.</strong></div>}
    {!loading && !error && positions.length > 0 && <PositionsTable positions={positions} />}
  </section>;
}

function RiskEventsView({ events, loading, error, pagination, onPager, onRetry }: { events: PaperRiskEvent[]; loading: boolean; error: string; pagination: { total: number } | null; onPager: (offset: number) => void; onRetry: () => void }) {
  return <section>
    <div className="section-heading"><div><h3>Risk Events</h3><p className="muted">Events logged when risk checks fail or the kill switch is triggered.</p></div></div>

    {error && <p role="alert" className="error">{error} <button className="quiet-button" onClick={onRetry}>Retry</button></p>}
    {loading && <p role="status">Loading risk events…</p>}
    {!loading && !error && events.length === 0 && <div className="empty-state"><strong>No risk events recorded.</strong></div>}
    {!loading && !error && events.length > 0 && <div className="table-wrap"><table>
      <thead><tr><th>Time</th><th>Type</th><th>Blocked</th><th>Details</th></tr></thead>
      <tbody>{events.map(e => <tr key={e.id}>
        <td>{time(e.created_at)}</td>
        <td>{e.event_type}</td>
        <td>{e.blocked ? <span className="reject-badge">Yes</span> : <span className="accept-badge">No</span>}</td>
        <td style={{ maxWidth: '300px', overflowWrap: 'anywhere' }}>{JSON.stringify(e.details)}</td>
      </tr>)}</tbody>
    </table></div>}
    {!loading && !error && pagination && <Pager total={pagination.total} offset={0} onChange={onPager} />}
  </section>;
}

export function PaperTradingView() {
  const [tab, setTab] = useState<Tab>('summary');
  const [summary, setSummary] = useState<PaperAccountSummary | null>(null);
  const [positions, setPositions] = useState<PaperPosition[]>([]);
  const [orders, setOrders] = useState<PaperOrder[]>([]);
  const [orderPagination, setOrderPagination] = useState<{ total: number } | null>(null);
  const [riskEvents, setRiskEvents] = useState<PaperRiskEvent[]>([]);
  const [riskPagination, setRiskPagination] = useState<{ total: number } | null>(null);
  const [killSwitch, setKillSwitch] = useState<KillSwitchStatus | null>(null);
  const [error, setError] = useState('');
  const [submitError, setSubmitError] = useState('');
  const [submitLoading, setSubmitLoading] = useState(false);
  const [instruments, setInstruments] = useState<{ id: string; symbol: string }[]>([]);
  const [retry, setRetry] = useState(0);
  const [orderOffset, setOrderOffset] = useState(0);
  const [riskOffset, setRiskOffset] = useState(0);

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const [summaryRes, positionsRes, ordersRes, ksRes, riskRes, instrumentRes] = await Promise.allSettled([
          paper.summary(),
          paper.positions(),
          paper.orders(orderOffset),
          paper.killSwitch(),
          paper.riskEvents(riskOffset),
          api<{ items: { id: string; canonical_symbol: string }[] }>('/instruments?limit=100'),
        ]);

        if (!active) return;

        if (summaryRes.status === 'fulfilled') setSummary(summaryRes.value);
        if (positionsRes.status === 'fulfilled') setPositions(positionsRes.value);
        if (ordersRes.status === 'fulfilled') { setOrders(ordersRes.value.items); setOrderPagination({ total: ordersRes.value.total }); }
        if (ksRes.status === 'fulfilled') setKillSwitch(ksRes.value);
        if (riskRes.status === 'fulfilled') { setRiskEvents(riskRes.value.items); setRiskPagination({ total: riskRes.value.total }); }
        if (instrumentRes.status === 'fulfilled') setInstruments(instrumentRes.value.items.map(i => ({ id: i.id, symbol: i.canonical_symbol })));
        if ([summaryRes, positionsRes, ordersRes, ksRes].some(r => r.status === 'rejected')) setError('Some paper trading data could not be loaded.');
      } catch (e) { setError((e as Error).message); }
    }
    void load();
    return () => { active = false; };
  }, [orderOffset, riskOffset, retry]);

  async function submitOrder(body: OrderSubmission) {
    setSubmitLoading(true);
    setSubmitError('');
    try { await paper.submitOrder(body); setRetry(n => n + 1); }
    catch (e) { setSubmitError((e as Error).message); }
    finally { setSubmitLoading(false); }
  }

  async function triggerKillSwitch(reason: string) {
    setSubmitLoading(true);
    try { await paper.triggerKillSwitch(reason); setRetry(n => n + 1); }
    finally { setSubmitLoading(false); }
  }

  async function resetKillSwitch() {
    setSubmitLoading(true);
    try { await paper.resetKillSwitch(); setRetry(n => n + 1); }
    finally { setSubmitLoading(false); }
  }

  return <section id="paper-trading" className="workspace-panel" aria-labelledby="paper-trading-title">
    <div className="section-heading"><div><p className="eyebrow">PAPER TRADING</p><h2 id="paper-trading-title">Paper trading workspace</h2><p className="muted">Simulated trading with risk controls. No real capital is at risk.</p></div>{killSwitch?.state === 'triggered' && <span className="mode-badge" style={{ background: '#fef0ee', color: '#9a392a' }}>KILL SWITCH ACTIVE</span>}</div>

    <div className="notice-inline"><strong>Simulated trading only.</strong> Paper orders use risk validation and assumed fills. This is not live execution and does not place real orders.</div>

    {error && <p role="alert" className="error">{error} <button className="quiet-button" onClick={() => setRetry(n => n + 1)}>Retry</button></p>}

    <div className="catalog-overview" aria-label="Account overview">
      <div><span>Initial Capital</span><strong>{summary ? formatCurrency(summary.initial_capital, summary.currency) : '—'}</strong><small>Starting amount</small></div>
      <div><span>Available Capital</span><strong>{summary ? formatCurrency(summary.available_capital, summary.currency) : '—'}</strong><small>For new positions</small></div>
      <div><span>Total P&amp;L</span><strong style={{ color: summary && parseFloat(summary.total_pnl) > 0 ? '#126756' : summary && parseFloat(summary.total_pnl) < 0 ? '#9a392a' : '#64778a' }}>{summary ? formatCurrency(summary.total_pnl, summary.currency) : '—'}</strong><small>Unrealized + realized</small></div>
      <div><span>Open Positions</span><strong>{summary?.position_count ?? '—'}</strong><small>Current holdings</small></div>
    </div>

    <div className="tab-list" role="tablist" aria-label="Paper trading sections">{(Object.keys(tabNames) as Tab[]).map(key => <button key={key} role="tab" aria-selected={tab === key} aria-controls="paper-content" className={tab === key ? 'active' : ''} onClick={() => setTab(key)}>{tabNames[key]}</button>)}</div>

    <div id="paper-content" role="tabpanel" aria-label={tabNames[tab]}>
      {tab === 'summary' && <div>
        <h3>Account Summary</h3>
        <div className="metric-grid">
          <div><span>Account</span><strong>{summary?.name ?? '—'}</strong></div>
          <div><span>Currency</span><strong>{summary?.currency ?? '—'}</strong></div>
          <div><span>Reserved Capital</span><strong>{summary ? formatCurrency(summary.reserved_capital, summary.currency) : '—'}</strong></div>
          <div><span>Open Position Value</span><strong>{summary ? formatCurrency(summary.open_position_value, summary.currency) : '—'}</strong></div>
          <div><span>Unrealized P&amp;L</span><strong style={{ color: summary && parseFloat(summary.unrealized_pnl) > 0 ? '#126756' : summary && parseFloat(summary.unrealized_pnl) < 0 ? '#9a392a' : '#64778a' }}>{summary ? formatCurrency(summary.unrealized_pnl, summary.currency) : '—'}</strong></div>
          <div><span>Realized P&amp;L</span><strong style={{ color: summary && parseFloat(summary.realized_pnl) > 0 ? '#126756' : summary && parseFloat(summary.realized_pnl) < 0 ? '#9a392a' : '#64778a' }}>{summary ? formatCurrency(summary.realized_pnl, summary.currency) : '—'}</strong></div>
        </div>
        <PositionsView positions={positions} loading={!summary} error={error} />
      </div>}

      {tab === 'orders' && <OrdersView orders={orders} loading={!summary} error={error} pagination={orderPagination} onPager={setOrderOffset} onRetry={() => setRetry(n => n + 1)} />}

      {tab === 'positions' && <PositionsView positions={positions} loading={!summary} error={error} />}

      {tab === 'killswitch' && <KillSwitchPanel status={killSwitch} loading={!summary} error={error} onTrigger={triggerKillSwitch} onReset={resetKillSwitch} onRefresh={() => setRetry(n => n + 1)} />}

      {tab === 'risk' && <RiskEventsView events={riskEvents} loading={!summary} error={error} pagination={riskPagination} onPager={setRiskOffset} onRetry={() => setRetry(n => n + 1)} />}
    </div>

    <OrderForm onSubmit={submitOrder} loading={submitLoading} instruments={instruments} error={submitError} />
  </section>;
}
