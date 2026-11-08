import { useEffect, useState, type FormEvent } from 'react';
import { createRoot } from 'react-dom/client';
import { api, type Instrument, type SystemStatus } from './api';
import './style.css';
import { Mt5View } from './Mt5View';
import { AngelOneView } from './AngelOneView';
import { ResearchView } from './ResearchView';
import { CoverageView } from './CoverageView';
import { PaperTradingView } from './PaperTradingView';
import { HistoricalView } from './HistoricalView';
import { InstrumentsView } from './InstrumentsView';

type View = 'research' | 'market' | 'instruments' | 'system' | 'paper' | 'historical';
const nav: { key: View; name: string; note: string }[] = [
  { key: 'research', name: 'Research', note: 'Historical analysis' },
  { key: 'market', name: 'Market data', note: 'Connector snapshots' },
  { key: 'instruments', name: 'Instruments', note: 'Provider metadata' },
  { key: 'historical', name: 'Historical data', note: 'Candlestick charts' },
  { key: 'paper', name: 'Paper trading', note: 'Simulated orders' },
  { key: 'system', name: 'System', note: 'Platform health' },
];

export function App() {
  const [signedIn, setSignedIn] = useState(false);
  const [checking, setChecking] = useState(true);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [view, setView] = useState<View>('research');
  const [menuOpen, setMenuOpen] = useState(false);
  const [status, setStatus] = useState<SystemStatus>();
  const [items, setItems] = useState<Instrument[]>([]);
  const [search, setSearch] = useState('');
  async function load(query = '') {
    setBusy(true); setError('');
    const [s, instruments] = await Promise.allSettled([api<SystemStatus>('/system/status'), api<{items: Instrument[]}>('/instruments?search=' + encodeURIComponent(query))]);
    if (s.status === 'fulfilled') setStatus(s.value);
    if (instruments.status === 'fulfilled') setItems(instruments.value.items);
    if (s.status === 'rejected' || instruments.status === 'rejected') setError('Some platform data could not be loaded. Please retry.');
    setBusy(false);
  }
  useEffect(() => {
    let active = true;
    api('/auth/me').then(() => { if (active) { setSignedIn(true); void load(); } }).catch(() => {}).finally(() => { if (active) setChecking(false); });
    return () => { active = false; };
  }, []);
  async function login(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError('');
    const values = new FormData(event.currentTarget);
    try { await api('/auth/login', {method: 'POST', body: JSON.stringify({email: values.get('email'), password: values.get('password')})}); setSignedIn(true); void load(); }
    catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  async function logout() {
    setBusy(true); setError('');
    try { await api('/auth/logout', {method: 'POST'}); setSignedIn(false); setStatus(undefined); setView('research'); }
    catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  return <div className="app-shell">
    <header className="topbar"><div className="brand"><span className="brand-mark" aria-hidden="true">I<span>·</span></span><div><strong>Intraday</strong><small>Research workspace</small></div></div><div className="topbar-right"><span className="mode-badge">● &nbsp; RESEARCH ONLY</span>{signedIn && <button className="quiet-button signout" onClick={() => void logout()} disabled={busy}>Sign out</button>}</div></header>
    {checking ? <main className="login-frame"><section className="login-card" role="status">Checking your session…</section></main> : !signedIn ? <main className="login-frame"><section className="login-card"><p className="eyebrow">PRIVATE WORKSPACE</p><h1>Welcome back.</h1><p className="muted">Sign in to review market snapshots and historical, simulated research.</p>{error && <p role="alert" className="error">{error}</p>}<form onSubmit={login}><label>Email<input name="email" type="email" autoComplete="username" required /></label><label>Password<input name="password" type="password" autoComplete="current-password" required /></label><button disabled={busy} className="primary-button">{busy ? 'Signing in…' : 'Sign in'}</button></form><p className="login-footnote">No public registration. Create your account with the local bootstrap command.</p></section></main> : <div className="workspace-layout">
      <aside className="sidebar"><div className="sidebar-label">WORKSPACE</div><nav aria-label="Workspace navigation">{nav.map(item => <button key={item.key} className={`nav-item ${view === item.key ? 'selected' : ''}`} aria-current={view === item.key ? 'page' : undefined} onClick={() => { setView(item.key); setMenuOpen(false); }}><strong>{item.name}</strong><small>{item.note}</small></button>)}</nav><div className="sidebar-footer"><strong>Execution disabled</strong><span>No order service is available. Research results are not live signals.</span></div></aside>
      <main className="workspace-main"><div className="mobile-nav"><button className="quiet-button" aria-expanded={menuOpen} aria-controls="mobile-menu" onClick={() => setMenuOpen(!menuOpen)}>☰ &nbsp; {nav.find(item => item.key === view)?.name}</button><nav id="mobile-menu" aria-label="Mobile workspace navigation" hidden={!menuOpen}>{nav.map(item => <button key={item.key} onClick={() => { setView(item.key); setMenuOpen(false); }}>{item.name}</button>)}</nav></div>
        <div className="page-intro"><div><p className="eyebrow">INTRADAY / {view.toUpperCase()}</p><h1>{nav.find(item => item.key === view)?.name}</h1><p className="muted">{view === 'research' ? 'A clear view of what the historical evidence actually says.' : view === 'market' ? 'Optional read-only connector snapshots, with freshness shown at source.' : view === 'instruments' ? 'Catalog metadata with explicit demo and execution labels.' : view === 'historical' ? 'Browse stored OHLCV partitions with candlestick visualization and session coverage.' : 'Environment and platform availability.'}</p></div><span className="asof-label">Read-only platform</span></div>
        {error && <p role="alert" className="error">{error} <button className="quiet-button" onClick={() => void load(search)}>Retry</button></p>}
        {view === 'research' && <ResearchView />}
        {view === 'market' && <><div className="notice-inline">Connector data can be absent or stale. Quotes and terminal snapshots are not execution instructions.</div><CoverageView /><Mt5View /><AngelOneView /></>}
        {view === 'historical' && <HistoricalView />}
        {view === 'instruments' && <InstrumentsView />}
        {view === 'system' && <section id="status" className="workspace-panel"><div className="section-heading"><div><p className="eyebrow">PLATFORM HEALTH</p><h2>System status</h2></div><button className="quiet-button" disabled={busy} onClick={() => void load(search)}>Refresh</button></div>{status ? <dl className="status-list"><div><dt>Version</dt><dd>{status.version}</dd></div><div><dt>Environment</dt><dd>{status.environment}</dd></div><div><dt>Trading mode</dt><dd>{status.trading_mode}</dd></div><div><dt>Market feed</dt><dd>{status.market_data}</dd></div><div><dt>Live execution</dt><dd><span className="result-pill">{status.live_trading_enabled ? 'Reported enabled — review configuration' : 'Unavailable'}</span></dd></div></dl> : <p role="status">Status unavailable. Refresh to retry.</p>}<div className="notice-inline">Offline research simulations only. Paper orders and live execution are not implemented in this workspace.</div></section>}
        {view === 'paper' && <PaperTradingView />}
        <footer className="workspace-footer">Research-only environment · Historical results and simulated outcomes are not broker fills or investment advice.</footer>
      </main>
    </div>}
  </div>;
}
createRoot(document.getElementById('root')!).render(<App />);
