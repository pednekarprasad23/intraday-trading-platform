import { useEffect, useState } from 'react';
import { research, type Page, type ResearchReport, type ResearchReportDetail, type ResearchSignal, type ResearchEvaluation, type CandidateRanking, type RankingsPage } from './api';

type Collection = 'evaluations' | 'signals' | 'backtests' | 'walkForwards' | 'rankings';
const names: Record<Collection, string> = { evaluations: 'Evaluations', signals: 'Accepted signals', backtests: 'Backtests', walkForwards: 'Walk-forwards', rankings: 'Rankings' };
const collections: Collection[] = ['evaluations', 'signals', 'backtests', 'walkForwards', 'rankings'];
const time = (value: string | null) => value ? new Date(value).toLocaleString(undefined, { timeZoneName: 'short' }) : 'Unavailable';
const source = (provider: string, demo: boolean) => `${demo ? 'DEMO · ' : ''}${provider}`;
const value = (item: unknown) => item == null ? 'Unavailable' : typeof item === 'object' ? JSON.stringify(item, null, 2) : String(item);

function Pager({ total, offset, onChange }: { total: number; offset: number; onChange: (value: number) => void }) {
  return <div className="pager"><button disabled={offset === 0} onClick={() => onChange(Math.max(0, offset - 20))}>Previous</button><span>{total === 0 ? '0 records' : `${offset + 1}–${Math.min(offset + 20, total)} of ${total}`}</span><button disabled={offset + 20 >= total} onClick={() => onChange(offset + 20)}>Next</button></div>;
}
function ReportDetails({ report, close }: { report: ResearchReport; close: () => void }) {
  const [detail, setDetail] = useState<ResearchReportDetail>();
  const [error, setError] = useState('');
  const [copied, setCopied] = useState(false);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) { if (event.key === 'Escape') close(); }
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [close]);
  useEffect(() => {
    let active = true;
    setDetail(undefined); setError(''); setCopied(false);
    research.detail(report.kind, report.id).then(result => { if (active) setDetail(result); }).catch((cause: Error) => { if (active) setError(cause.message); });
    return () => { active = false; };
  }, [report.id, report.kind, retry]);
  return <div className="detail-backdrop" onClick={close}><section className="detail-panel" role="dialog" aria-modal="true" aria-labelledby="detail-title" onClick={e => e.stopPropagation()}>
    <div className="section-heading"><div><p className="eyebrow">READ-ONLY REPORT</p><h3 id="detail-title">{report.kind === 'BACKTEST' ? 'Simulated backtest' : 'Simulated walk-forward'}</h3></div><button className="quiet-button" onClick={close} autoFocus>Close</button></div>
    {error && <p role="alert" className="error">{error} <button onClick={() => setRetry(n => n + 1)}>Retry</button></p>}
    {!detail && !error && <p role="status">Loading report details…</p>}
    {detail && <>
      <p className="muted">{source(detail.provider, detail.demo)} · {detail.timeframe} · {time(detail.created_at)}</p>
      <p className="notice-inline">Research simulation only. Assumed fills and costs; no broker order or verified future return.</p>
      <div className="metric-grid"><div><span>Simulated net P&amp;L</span><strong>{value(detail.metrics.net_pnl)}</strong></div><div><span>Trades</span><strong>{value(detail.metrics.trade_count)}</strong></div><div><span>Win rate</span><strong>{value(detail.metrics.win_rate)}</strong></div><div><span>Max drawdown</span><strong>{value(detail.metrics.max_drawdown)}</strong></div><div><span>Expectancy</span><strong>{value(detail.metrics.expectancy)}</strong></div><div><span>Profit factor</span><strong>{value(detail.metrics.profit_factor)}</strong></div></div>
      <h4>Provenance</h4><p>Instrument: <code>{detail.instrument_id}</code> · Strategy: {detail.strategy_id} ({detail.strategy_version})</p>
      <p className="hash-line">Report fingerprint: <code>{detail.fingerprint}</code> <button className="quiet-button" onClick={() => navigator.clipboard.writeText(detail.fingerprint).then(() => setCopied(true)).catch(() => setCopied(false))}>Copy fingerprint</button> <span role="status">{copied ? 'Copied' : ''}</span></p>
      <p className="hash-line">Input fingerprint: <code>{detail.input_fingerprint}</code></p>
      <h4>Warnings</h4>{detail.warnings.length ? <ul>{detail.warnings.map((warning, index) => <li key={index}>{warning}</li>)}</ul> : <p>None reported.</p>}
      <h4>Simulation configuration &amp; assumed costs</h4><pre>{value(detail.simulation_config)}</pre>
      <h4>Strategy configuration</h4><pre>{value(detail.strategy_config)}</pre>
      <h4>Historical sources</h4><pre>{value(detail.sources)}</pre>
      <h4>{detail.kind === 'BACKTEST' ? 'Bounded trade and event summaries' : 'Walk-forward fold summaries'}</h4><p className="muted">{detail.kind === 'BACKTEST' ? 'Stored trade and event summaries are each capped at 100 entries; this is not a complete ledger.' : 'Each fold records its training and test summary, not an order ledger.'}</p>
      <pre>{value(detail.kind === 'BACKTEST' ? { trades: detail.trade_summary, events: detail.event_summary } : detail.folds)}</pre>
    </>}
  </section></div>;
}

export function ResearchView() {
  const [tab, setTab] = useState<Collection>('evaluations');
  const [offsets, setOffsets] = useState<Record<Collection, number>>({ evaluations: 0, signals: 0, backtests: 0, walkForwards: 0, rankings: 0 });
  const [pages, setPages] = useState<Partial<{ evaluations: Page<ResearchEvaluation>; signals: Page<ResearchSignal>; backtests: Page<ResearchReport>; walkForwards: Page<ResearchReport>; rankings: Page<CandidateRanking> }>>({});
  const [errors, setErrors] = useState<Partial<Record<Collection, string>>>({});
  const [loading, setLoading] = useState<Partial<Record<Collection, boolean>>>({});
  const [retries, setRetries] = useState<Partial<Record<Collection, number>>>({});
  const [selected, setSelected] = useState<ResearchReport>();
  const [selectedRanking, setSelectedRanking] = useState<CandidateRanking>();
  useEffect(() => {
    let active = true;
    collections.forEach(key => {
      setLoading(previous => ({ ...previous, [key]: true }));
      research[key](offsets[key]).then(result => {
        if (!active) return;
        setPages(previous => ({ ...previous, [key]: result }));
        setErrors(previous => ({ ...previous, [key]: undefined }));
      }).catch((cause: Error) => {
        if (!active) return;
        setPages(previous => ({ ...previous, [key]: undefined }));
        setErrors(previous => ({ ...previous, [key]: cause.message }));
      }).finally(() => { if (active) setLoading(previous => ({ ...previous, [key]: false })); });
    });
    return () => { active = false; };
  }, [offsets.evaluations, offsets.signals, offsets.backtests, offsets.walkForwards, retries.evaluations, retries.signals, retries.backtests, retries.walkForwards]);
  const page = pages[tab];
  return <section id="research" className="workspace-panel" aria-labelledby="research-title">
    <div className="section-heading"><div><p className="eyebrow">RESEARCH ONLY · SIMULATED · NO BROKER ORDER</p><h2 id="research-title">Research workspace</h2><p className="muted">Explore operator evaluations and offline simulations. No live idea scanner or order controls.</p></div><span className="status-pill">NO EXECUTION</span></div>
    <div className="notice-inline"><strong>Simulated, not traded.</strong> Backtest figures rely on assumed fills and costs; this page cannot create orders or run simulations. Accepted LONG snapshots saved before this checkpoint remain visible. An empty signal catalog does not mean a strategy failed; earlier NONE/rejected evaluations were not retained.</div>
    <div className="catalog-overview" aria-label="Catalog totals">{collections.map(key => <div key={key}><span>{names[key]}</span><strong>{loading[key] && !pages[key] ? '…' : errors[key] ? 'Unavailable' : pages[key]?.total ?? '…'}</strong><small>{errors[key] ? 'Request failed' : 'Historical records'}</small></div>)}</div>
    <div className="tab-list" role="tablist" aria-label="Research collections">{collections.map(key => <button key={key} role="tab" aria-selected={tab === key} aria-controls="catalog-content" className={tab === key ? 'active' : ''} onClick={() => setTab(key)}>{names[key]}</button>)}</div>
    <div id="catalog-content" role="tabpanel" aria-label={names[tab]}>
      <div className="section-heading"><div><h3>{tab === 'evaluations' ? 'Operator evaluation history' : names[tab]}</h3><p className="muted">{tab === 'signals' ? 'Accepted LONG snapshots; not live trade ideas.' : tab === 'evaluations' ? 'Operator decisions, including NONE and rejected results where recorded.' : tab === 'rankings' ? 'Deterministic composite scores from backtest metrics; versioned rules, no LLM required.' : 'Offline simulated results; never broker fills.'}</p></div></div>
      {errors[tab] && <p role="alert" className="error">{names[tab]} unavailable: {errors[tab]} <button onClick={() => setRetries(previous => ({ ...previous, [tab]: (previous[tab] ?? 0) + 1 }))}>Retry</button></p>}
      {loading[tab] && <p role="status">Loading {names[tab].toLowerCase()}…</p>}
      {!loading[tab] && !errors[tab] && page?.total === 0 && <div className="empty-state"><strong>No {names[tab].toLowerCase()} recorded yet.</strong><p>Records appear after an operator imports eligible historical data and runs research commands. No conclusion about strategy quality follows from this empty view.</p></div>}
      {!loading[tab] && !errors[tab] && page && page.total > 0 && <div className="table-wrap"><table><thead><tr>{tab === 'signals' ? <><th>Decision time</th><th>Decision</th><th>Source</th><th>Instrument</th><th>Partition SHA-256</th></> : tab === 'evaluations' ? <><th>Decision time</th><th>Result</th><th>Source</th><th>Reason</th><th>Partition SHA-256</th></> : <><th>Created</th><th>Strategy</th><th>Source</th><th>Simulated net P&amp;L</th><th>Trades / folds</th><th>Report</th></>}</tr></thead><tbody>
        {tab === 'signals' && pages.signals?.items.map(item => <tr key={item.id}><td>{time(item.decision_time)}</td><td>{item.direction} · {item.quality}</td><td>{source(item.provider, item.demo)}</td><td><code>{item.instrument_id}</code></td><td><code title={item.partition_sha256}>{item.partition_sha256.slice(0, 12)}…</code></td></tr>)}
        {tab === 'evaluations' && pages.evaluations?.items.map(item => <tr key={item.id}><td>{time(item.decision_time)}</td><td><span className="result-pill">{item.direction} · {item.quality}</span></td><td>{source(item.provider, item.demo)}</td><td>{item.reasons.join(', ') || 'None reported'}</td><td><code title={item.partition_sha256}>{item.partition_sha256.slice(0, 12)}…</code></td></tr>)}
        {(tab === 'backtests' || tab === 'walkForwards') && pages[tab]?.items.map(item => <tr key={item.id}><td>{time(item.created_at)}</td><td>{item.strategy_id}</td><td>{source(item.provider, item.demo)} · {item.timeframe}</td><td>{value(item.metrics.net_pnl)}</td><td>{item.kind === 'BACKTEST' ? value(item.metrics.trade_count) : `${value(item.fold_count)} folds`}</td><td><button className="quiet-button" onClick={() => setSelected(item)}>View details</button></td></tr>)}
        {tab === 'rankings' && pages.rankings?.items.map(item => <tr key={item.candidate_id}><td>{item.session_date}</td><td>{item.strategy_id} v{item.strategy_version}</td><td><span className={item.is_rejected ? 'reject-badge' : 'accept-badge'}>{item.is_rejected ? 'Rejected' : 'Accepted'}</span></td><td><strong>{item.composite_score.toFixed(1)}</strong><div className="score-bar"><div style={{ width: `${item.composite_score}%` }} /></div></td><td>{item.rejection_reasons.length > 0 ? item.rejection_reasons.join(', ') : '—'}</td><td><button className="quiet-button" onClick={() => setSelectedRanking(item)}>View details</button></td></tr>)}
      </tbody></table></div>}
      {!loading[tab] && !errors[tab] && page && <Pager total={page.total} offset={offsets[tab]} onChange={next => setOffsets(previous => ({ ...previous, [tab]: next }))} />}
    </div>
    {selected && <ReportDetails report={selected} close={() => setSelected(undefined)} />}
    {selectedRanking && <RankingDetails ranking={selectedRanking} close={() => setSelectedRanking(undefined)} />}
  </section>;
}

function RankingDetails({ ranking, close }: { ranking: CandidateRanking; close: () => void }) {
  return <div className="detail-backdrop" onClick={close}><section className="detail-panel" role="dialog" aria-modal="true" aria-labelledby="ranking-title" onClick={e => e.stopPropagation()}>
    <div className="section-heading"><div><p className="eyebrow">RESEARCH ONLY / SIMULATED / NO BROKER ORDER</p><h3 id="ranking-title">Candidate ranking</h3></div><button className="quiet-button" onClick={close} autoFocus>Close</button></div>
    <p className="muted">{ranking.strategy_id} v{ranking.strategy_version} · {ranking.session_date}</p>
    <div className="metric-grid">
      <div><span>Composite score</span><strong>{ranking.composite_score.toFixed(1)} / 100</strong></div>
      <div><span>Status</span><strong className={ranking.is_rejected ? 'reject-badge' : 'accept-badge'}>{ranking.is_rejected ? 'Rejected' : 'Accepted'}</strong></div>
      <div><span>Version</span><strong>v{ranking.ranking_version}</strong></div>
    </div>
    <h4>Score breakdown</h4>
    <div className="metric-grid">
      <div><span>Performance</span><strong>{ranking.score_breakdown.performance.toFixed(1)}</strong></div>
      <div><span>Risk</span><strong>{ranking.score_breakdown.risk.toFixed(1)}</strong></div>
      <div><span>Data quality</span><strong>{ranking.score_breakdown.data_quality.toFixed(1)}</strong></div>
      <div><span>Structure alignment</span><strong>{ranking.score_breakdown.structure_alignment.toFixed(1)}</strong></div>
    </div>
    {ranking.is_rejected && <><h4>Rejection reasons</h4><ul>{ranking.rejection_reasons.map((reason, i) => <li key={i}>{reason}</li>)}</ul></>}
    <h4>Commentary</h4><pre className="commentary-box">{ranking.commentary}</pre>
  </section></div>;
}
