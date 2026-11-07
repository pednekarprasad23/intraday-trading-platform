import { useEffect, useState } from 'react';
import { api } from './api';

type SnapshotResponse = {
  quality: string;
  snapshot: null | {
    observed_at: string;
    account: null | { currency: string; balance: string; equity: string; profit: string; margin: string; free_margin: string };
    positions: null | { symbol: string; side: string; volume: string; price_open: string; price_current: string; profit: string; opened_at: string }[];
    history: null | { symbol: string; type: number; volume: string; price: string; profit: string; time: string }[];
    quotes: { symbol: string; bid: string; ask: string; event_time: string; received_at: string; quality: string }[];
    errors: string[];
  };
};

export function Mt5View() {
  const [data, setData] = useState<SnapshotResponse>();
  const [error, setError] = useState(false);
  const [clock, setClock] = useState(Date.now());
  useEffect(() => {
    let active = true;
    async function refresh() {
      try {
        const result = await api<SnapshotResponse>('/mt5/snapshot', { signal: AbortSignal.timeout(5000) });
        if (active) { setData(result); setError(false); }
      } catch { if (active) { setData(undefined); setError(true); } }
    }
    void refresh();
    const poll = window.setInterval(() => void refresh(), 15000);
    const tick = window.setInterval(() => setClock(Date.now()), 1000);
    return () => { active = false; clearInterval(poll); clearInterval(tick); };
  }, []);
  const age = data?.snapshot ? (clock - Date.parse(data.snapshot.observed_at)) / 1000 : Infinity;
  const snapshot = age >= 0 && age < 45 ? data?.snapshot : null;
  return <section id="mt5">
    <h2>MT5 terminal · Read-only</h2>
    <p>Source: Windows MT5 terminal. Account identifiers omitted. No order actions are available.</p>
    <p role="status">Snapshot: {error ? 'UNAVAILABLE — request failed' : !data ? 'Loading…' : data.snapshot && !snapshot ? 'STALE' : data.quality}</p>
    {!snapshot ? <p>No current snapshot. The optional Windows worker must be enabled and running.</p> : <>
      <p>Observed: {snapshot.observed_at} · Age: {Math.floor(age)} seconds</p>
      {snapshot.errors.length > 0 && <p role="alert">{snapshot.errors.join('; ')}</p>}
      <h3>Account summary</h3>
      {snapshot.account ? <dl>{Object.entries(snapshot.account).filter(([key]) => ['currency', 'balance', 'equity', 'profit', 'margin', 'free_margin'].includes(key)).map(([key, value]) => <div key={key}><dt>{key.replaceAll('_', ' ')}</dt><dd>{value}</dd></div>)}</dl> : <p>Account unavailable</p>}
      <h3>Open positions</h3>
      {snapshot.positions === null ? <p>Positions unavailable</p> : <div className="table-wrap"><table><caption>{snapshot.positions.length} open positions</caption><thead><tr><th>Symbol</th><th>Side</th><th>Volume</th><th>Open price</th><th>Current price</th><th>Profit</th></tr></thead><tbody>{snapshot.positions.map((p, i) => <tr key={i}><td>{p.symbol}</td><td>{p.side}</td><td>{p.volume}</td><td>{p.price_open}</td><td>{p.price_current}</td><td>{p.profit}</td></tr>)}</tbody></table></div>}
      <h3>Historical deals · Last 7 days</h3>
      {snapshot.history === null ? <p>History unavailable</p> : <div className="table-wrap"><table><caption>Raw MT5 deal types; includes non-trade operations. Not an execution or performance report.</caption><thead><tr><th>Time (UTC)</th><th>Symbol</th><th>Type code</th><th>Volume</th><th>Price</th><th>Profit</th></tr></thead><tbody>{snapshot.history.map((d, i) => <tr key={i}><td>{d.time}</td><td>{d.symbol || '—'}</td><td>{d.type}</td><td>{d.volume}</td><td>{d.price}</td><td>{d.profit}</td></tr>)}</tbody></table>{snapshot.history.length === 0 && <p>No deals in this window.</p>}</div>}
      <h3>Bid / ask snapshots</h3>
      <div className="table-wrap"><table><caption>Bid and ask are not last-traded prices. Quotes are stale after 45 seconds, including outside market hours.</caption><thead><tr><th>Symbol</th><th>Bid</th><th>Ask</th><th>Event time (UTC)</th><th>Received (UTC)</th><th>Quality</th></tr></thead><tbody>{snapshot.quotes.map(q => <tr key={q.symbol}><td>{q.symbol}</td><td>{q.bid}</td><td>{q.ask}</td><td>{q.event_time}</td><td>{q.received_at}</td><td>{clock - Date.parse(q.event_time) >= 45000 ? 'STALE' : q.quality}</td></tr>)}</tbody></table>{snapshot.quotes.length === 0 && <p>No quotes configured or available.</p>}</div>
    </>}
  </section>;
}
