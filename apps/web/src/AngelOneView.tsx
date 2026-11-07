import { useEffect, useState } from 'react';
import { api } from './api';

type AngelSnapshot = {
  quality: string;
  age_seconds?: number;
  snapshot: null | {
    observed_at: string;
    authenticated: boolean;
    quotes: { symbol: string; ltp: string; event_time: string | null; received_at: string; quality?: string }[];
    errors: string[];
  };
};

export function AngelOneView() {
  const [data, setData] = useState<AngelSnapshot>();
  const [error, setError] = useState(false);
  const [clock, setClock] = useState(Date.now());
  useEffect(() => {
    let active = true;
    async function refresh() {
      try {
        const result = await api<AngelSnapshot>('/angelone/snapshot', { signal: AbortSignal.timeout(5000) });
        if (active) { setData(result); setError(false); }
      } catch { if (active) { setData(undefined); setError(true); } }
    }
    void refresh();
    const timer = window.setInterval(() => void refresh(), 15000);
    const tick = window.setInterval(() => setClock(Date.now()), 1000);
    return () => { active = false; clearInterval(timer); clearInterval(tick); };
  }, []);
  const candidate = data?.snapshot;
  const age = candidate ? (clock - Date.parse(candidate.observed_at)) / 1000 : Infinity;
  const snapshot = age >= 0 && age < 45 ? candidate : null;
  return <section id="angelone">
    <h2>Angel One · Read-only market data</h2>
    <p>Provider: ANGEL_ONE. No credentials or session tokens are shown. Orders are unavailable.</p>
    <p role="status">Feed: {error ? 'UNAVAILABLE — request failed' : !data ? 'Loading…' : candidate && !snapshot ? 'STALE' : data.quality}</p>
    {!snapshot ? <p>No current Angel One snapshot. The outbound worker is disabled or unavailable.</p> : <>
      <p>Observed: {snapshot.observed_at} · Age: {Math.floor(age)} seconds</p>
      {snapshot.errors.length > 0 && <p role="alert">{snapshot.errors.join('; ')}</p>}
      <div className="table-wrap"><table><caption>LTP snapshots; event time is shown only if provided by Angel One. Receipt time alone does not prove a fresh market event.</caption><thead><tr><th>Symbol</th><th>Last price</th><th>Event time (UTC)</th><th>Received (UTC)</th><th>Quality</th></tr></thead><tbody>{snapshot.quotes.map(q => <tr key={q.symbol}><td>{q.symbol}</td><td>{q.ltp}</td><td>{q.event_time ?? 'Not provided by LTP response'}</td><td>{q.received_at}</td><td>{q.event_time && clock - Date.parse(q.event_time) >= 45000 ? 'STALE' : q.quality ?? data?.quality ?? 'UNAVAILABLE'}</td></tr>)}</tbody></table>{snapshot.quotes.length === 0 && <p>No configured Angel One quotes.</p>}</div>
    </>}
  </section>;
}
