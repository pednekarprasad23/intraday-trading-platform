import { useEffect, useState, type FormEvent } from 'react';
import { historical, market, type CoverageFilters, type HistoricalCandle, type HistoricalPartition, type MarketCoverage } from './api';

const pageSize = 50;
const dateTime = (value: string | null) => value ? new Date(value).toLocaleString(undefined, { timeZoneName: 'short' }) : 'Not recorded';

export function CoverageView() {
  const [offset, setOffset] = useState(0);
  const [draft, setDraft] = useState<CoverageFilters>({});
  const [filters, setFilters] = useState<CoverageFilters>({});
  const [retry, setRetry] = useState(0);
  const [data, setData] = useState<MarketCoverage>();
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [partitions, setPartitions] = useState<HistoricalPartition[]>([]);
  const [selectedPartition, setSelectedPartition] = useState<HistoricalPartition>();
  const [candles, setCandles] = useState<HistoricalCandle[]>([]);
  const [candleError, setCandleError] = useState('');
  const [candlesLoading, setCandlesLoading] = useState(false);
  useEffect(() => {
    let active = true;
    setLoading(true);
    market.coverage(offset, filters).then(result => { if (active) { setData(result); setError(''); } })
      .catch((cause: Error) => { if (active) { setData(undefined); setError(cause.message); } })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [offset, filters, retry]);
  useEffect(() => {
    let active = true;
    historical.partitions().then(result => { if (active) setPartitions(result.items); }).catch(() => { if (active) setPartitions([]); });
    return () => { active = false; };
  }, [retry]);
  async function showCandles(partition: HistoricalPartition) {
    setSelectedPartition(partition); setCandles([]); setCandleError(''); setCandlesLoading(true);
    try { const result = await historical.candles(partition.id); setCandles(result.items); }
    catch (cause) { setCandleError((cause as Error).message); }
    finally { setCandlesLoading(false); }
  }
  function apply(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setOffset(0); setFilters({ ...draft });
  }
  return <section className="workspace-panel" aria-labelledby="coverage-title">
    <div className="section-heading"><div><p className="eyebrow">SOURCE EVIDENCE</p><h2 id="coverage-title">Data coverage</h2><p className="muted">Stored provider mappings, not a live market scanner. Filters and page counts refer only to this catalog.</p></div><button className="quiet-button" onClick={() => setRetry(n => n + 1)}>Refresh</button></div>
    <div className="notice-inline"><strong>Live feed: {data?.live_feed_status ?? 'unavailable'}.</strong> {data?.live_feed_note ?? 'A historical record does not establish current quotes or market-data entitlement.'} Constituents, OI, news and global-market context are not connected yet.</div>
    <form className="search-form" onSubmit={apply} aria-label="Filter coverage">
      <label>Symbol, name or provider key<input value={draft.search ?? ''} maxLength={100} onChange={e => setDraft({ ...draft, search: e.target.value })} /></label>
      <label>Provider<input value={draft.provider ?? ''} maxLength={50} onChange={e => setDraft({ ...draft, provider: e.target.value })} placeholder="e.g. DHAN" /></label>
      <label>Asset class<input value={draft.asset_class ?? ''} maxLength={30} onChange={e => setDraft({ ...draft, asset_class: e.target.value })} placeholder="e.g. OPTION" /></label>
      <label>Exchange<input value={draft.exchange ?? ''} maxLength={30} onChange={e => setDraft({ ...draft, exchange: e.target.value })} placeholder="e.g. NSE" /></label>
      <label>Origin<select value={draft.demo ?? ''} onChange={e => setDraft({ ...draft, demo: e.target.value })}><option value="">All</option><option value="false">Non-demo</option><option value="true">Demo</option></select></label>
      <label>Historical partitions<select value={draft.historical ?? ''} onChange={e => setDraft({ ...draft, historical: e.target.value })}><option value="">All</option><option value="true">Stored</option><option value="false">None stored</option></select></label>
      <button className="primary-button">Apply filters</button><button type="button" className="quiet-button" onClick={() => { setDraft({}); setFilters({}); setOffset(0); }}>Clear</button>
    </form>
    {data && !error && <p className="muted">Catalog checked {dateTime(data.observed_at)}. Latest historical session is a session date, not quote freshness. {data.total} matching mapping{data.total === 1 ? '' : 's'}; unrecorded sessions and missing markets cannot be inferred from this catalog.</p>}
    {loading && <p role="status">Loading data coverage…</p>}
    {error && <p role="alert" className="error">Coverage unavailable: {error} <button className="quiet-button" onClick={() => setRetry(n => n + 1)}>Retry</button></p>}
    {!loading && !error && data?.total === 0 && <p className="empty-state">No provider mappings match these filters. Clear filters to see the stored catalog; this does not establish market-wide coverage.</p>}
    {!loading && !error && data && data.total > 0 && <><div className="table-wrap"><table><thead><tr><th>Instrument</th><th>Source</th><th>Mapping verified</th><th>Historical coverage gap</th><th>Latest stored session</th><th>Live quote</th></tr></thead><tbody>{data.items.map(item => <tr key={`${item.instrument_id}:${item.provider}:${item.provider_instrument_key}`}><td><strong>{item.display_name}</strong><br /><code>{item.canonical_symbol}</code> {item.demo && <span className="result-pill">DEMO</span>}</td><td>{item.provider} · {item.provider_exchange ?? item.exchange}</td><td>{dateTime(item.mapping_verified_at)}</td><td>{item.historical_partition_count ? `${item.historical_partition_count} stored partition(s); full date range not verified` : 'No historical partitions stored'}</td><td>{item.latest_historical_session ?? 'None stored'}</td><td>{item.live_quote_available ? 'Available' : 'Unavailable'}</td></tr>)}</tbody></table></div><div className="pager"><button disabled={offset === 0 || loading} onClick={() => setOffset(Math.max(0, offset - pageSize))}>Previous</button><span>{offset + 1}–{Math.min(offset + data.items.length, data.total)} of {data.total} matching mappings</span><button disabled={offset + pageSize >= data.total || loading} onClick={() => setOffset(offset + pageSize)}>Next</button></div></>}
    <div className="section-heading"><div><h3>Verified historical candles</h3><p className="muted">Stored OHLCV loaded through checksum and schema verification.</p></div></div>
    {partitions.length === 0 ? <p className="empty-state">No readable historical partitions are cataloged.</p> : <div className="table-wrap"><table><thead><tr><th>Session</th><th>Provider</th><th>Timeframe</th><th>Bars</th><th>Checksum</th><th>Data</th></tr></thead><tbody>{partitions.map(partition => <tr key={partition.id}><td>{partition.session_date}</td><td>{partition.provider}</td><td>{partition.timeframe}</td><td>{partition.row_count}</td><td><code>{partition.checksum_sha256.slice(0, 12)}…</code></td><td><button className="quiet-button" onClick={() => void showCandles(partition)}>View candles</button></td></tr>)}</tbody></table></div>}
    {selectedPartition && <div><h4>{selectedPartition.session_date} · {selectedPartition.timeframe} candles</h4>{candlesLoading && <p role="status">Verifying and loading candles…</p>}{candleError && <p role="alert" className="error">Historical candles unavailable: {candleError}</p>}{!candlesLoading && !candleError && candles.length > 0 && <div className="table-wrap"><table><thead><tr><th>Time</th><th>Open</th><th>High</th><th>Low</th><th>Close</th><th>Volume</th></tr></thead><tbody>{candles.map(candle => <tr key={candle.bar_time}><td>{dateTime(candle.bar_time)}</td><td>{candle.open}</td><td>{candle.high}</td><td>{candle.low}</td><td>{candle.close}</td><td>{candle.volume}</td></tr>)}</tbody></table></div>}</div>}
  </section>;
}
