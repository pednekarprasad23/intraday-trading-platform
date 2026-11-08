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
import { GlobalStatusBar } from './GlobalStatusBar';
import { StatusBadge } from './StatusBadge';
import { DashboardView } from './DashboardView';

type View = 'dashboard' | 'research' | 'market' | 'instruments' | 'system' | 'paper' | 'historical' | 'orders' | 'positions' | 'risk' | 'reconcile';

interface NavGroup {
  category: string;
  items: { key: View; name: string; note: string; badge?: string }[];
}

const navGroups: NavGroup[] = [
  {
    category: 'OPERATIONS',
    items: [
      { key: 'dashboard', name: 'Dashboard', note: 'Command & control overview' },
      { key: 'paper', name: 'Paper Trading', note: 'Simulated ledger & orders', badge: 'PAPER' },
      { key: 'orders', name: 'Orders & Signals', note: 'Execution lifecycle & stream' },
      { key: 'positions', name: 'Positions', note: 'Open exposures & P&L' },
      { key: 'risk', name: 'Risk & Controls', note: 'Kill switch & risk events' },
      { key: 'reconcile', name: 'Reconciliation', note: 'Signal-to-fill audit', badge: 'V2.4' },
    ],
  },
  {
    category: 'FOUNDATION',
    items: [
      { key: 'research', name: 'Research', note: 'Historical strategy analysis' },
      { key: 'historical', name: 'Historical Data', note: 'Candlestick parquet partitions' },
      { key: 'market', name: 'Market Data', note: 'Connector snapshots & coverage' },
      { key: 'instruments', name: 'Instruments', note: 'Provider catalog metadata' },
      { key: 'system', name: 'System', note: 'Platform health & audit logs' },
    ],
  },
];

export function App() {
  const [signedIn, setSignedIn] = useState(false);
  const [checking, setChecking] = useState(true);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [view, setView] = useState<View>('dashboard');
  const [menuOpen, setMenuOpen] = useState(false);
  const [status, setStatus] = useState<SystemStatus>();
  const [items, setItems] = useState<Instrument[]>([]);
  const [search, setSearch] = useState('');

  async function load(query = '') {
    setBusy(true); setError('');
    const [s, instruments] = await Promise.allSettled([
      api<SystemStatus>('/system/status'),
      api<{items: Instrument[]}>('/instruments?search=' + encodeURIComponent(query))
    ]);
    if (s.status === 'fulfilled') setStatus(s.value);
    if (instruments.status === 'fulfilled') setItems(instruments.value.items);
    if (s.status === 'rejected' || instruments.status === 'rejected') {
      setError('Some platform data could not be loaded. Please retry.');
    }
    setBusy(false);
  }

  useEffect(() => {
    let active = true;
    api('/auth/me').then(() => {
      if (active) { setSignedIn(true); void load(); }
    }).catch(() => {}).finally(() => {
      if (active) setChecking(false);
    });
    return () => { active = false; };
  }, []);

  async function login(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError('');
    const values = new FormData(event.currentTarget);
    try {
      await api('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email: values.get('email'), password: values.get('password') })
      });
      setSignedIn(true);
      void load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function logout() {
    setBusy(true); setError('');
    try {
      await api('/auth/logout', { method: 'POST' });
      setSignedIn(false);
      setStatus(undefined);
      setView('dashboard');
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const currentNavName = navGroups.flatMap(g => g.items).find(i => i.key === view)?.name || 'Dashboard';

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">I<span>·</span></span>
          <div>
            <strong>Intraday</strong>
            <small>Operations Workspace</small>
          </div>
        </div>
        <div className="topbar-right">
          <GlobalStatusBar />
          {signedIn && (
            <button className="quiet-button signout" onClick={() => void logout()} disabled={busy}>
              Sign out
            </button>
          )}
        </div>
      </header>

      {checking ? (
        <main className="login-frame">
          <section className="login-card" role="status">Checking your session…</section>
        </main>
      ) : !signedIn ? (
        <main className="login-frame">
          <section className="login-card">
            <p className="eyebrow">PRIVATE WORKSPACE</p>
            <h1>Welcome back.</h1>
            <p className="muted">Sign in to review operational controls, simulated order ledgers, and historical research.</p>
            {error && <p role="alert" className="error">{error}</p>}
            <form onSubmit={login}>
              <label>Email
                <input name="email" type="email" autoComplete="username" required />
              </label>
              <label>Password
                <input name="password" type="password" autoComplete="current-password" required />
              </label>
              <button disabled={busy} className="primary-button">
                {busy ? 'Signing in…' : 'Sign in'}
              </button>
            </form>
            <p className="login-footnote">No public registration. Create your account with the local bootstrap command.</p>
          </section>
        </main>
      ) : (
        <div className="workspace-layout">
          <aside className="sidebar">
            {navGroups.map(group => (
              <div key={group.category} style={{ marginBottom: '16px' }}>
                <div className="sidebar-label">{group.category}</div>
                <nav aria-label={`${group.category} navigation`}>
                  {group.items.map(item => (
                    <button
                      key={item.key}
                      className={`nav-item ${view === item.key ? 'selected' : ''}`}
                      aria-current={view === item.key ? 'page' : undefined}
                      onClick={() => { setView(item.key); setMenuOpen(false); }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%' }}>
                        <strong>{item.name}</strong>
                        {item.badge && <span style={{ fontSize: '0.65rem', padding: '2px 5px', borderRadius: '4px', background: 'rgba(59,130,246,0.15)', color: '#3b82f6', fontWeight: 700 }}>{item.badge}</span>}
                      </div>
                      <small>{item.note}</small>
                    </button>
                  ))}
                </nav>
              </div>
            ))}
            <div className="sidebar-footer">
              <strong>Execution Mode</strong>
              <span>Paper simulation &amp; read-only broker telemetry active.</span>
            </div>
          </aside>

          <main className="workspace-main">
            <div className="mobile-nav">
              <button className="quiet-button" aria-expanded={menuOpen} aria-controls="mobile-menu" onClick={() => setMenuOpen(!menuOpen)}>
                ☰ &nbsp; {currentNavName}
              </button>
              <nav id="mobile-menu" aria-label="Mobile workspace navigation" hidden={!menuOpen}>
                {navGroups.flatMap(g => g.items).map(item => (
                  <button key={item.key} onClick={() => { setView(item.key); setMenuOpen(false); }}>
                    {item.name}
                  </button>
                ))}
              </nav>
            </div>

            <div className="page-intro">
              <div>
                <p className="eyebrow">INTRADAY / {view.toUpperCase()}</p>
                <h1>{currentNavName}</h1>
                <p className="muted">
                  {view === 'dashboard' ? 'TradeCartel-inspired command & control operations workspace.' :
                   view === 'research' ? 'Historical strategy performance analysis and backtest reports.' :
                   view === 'market' ? 'Connector snapshots, latency, and market data coverage.' :
                   view === 'instruments' ? 'Provider metadata, lot sizes, and contract specs.' :
                   view === 'historical' ? 'Browse stored OHLCV parquet partitions and candlestick charts.' :
                   view === 'paper' ? 'Simulated paper trading account, ledger, and execution tools.' :
                   view === 'orders' ? 'Live signal stream and paper order execution records.' :
                   view === 'positions' ? 'Current open positions, average entry prices, and unrealized P&L.' :
                   view === 'risk' ? 'Persistent kill switch and session risk event log.' :
                   view === 'reconcile' ? 'Signal-to-fill audit and execution reconciliation console (Coming in V2.4).' :
                   'Platform health and operational telemetry.'}
                </p>
              </div>
              <span className="asof-label">Operations Cockpit</span>
            </div>

            {error && (
              <p role="alert" className="error">
                {error} <button className="quiet-button" onClick={() => void load(search)}>Retry</button>
              </p>
            )}

            {view === 'dashboard' && <DashboardView />}

            {view === 'research' && <ResearchView />}
            {(view === 'market' || view === 'orders' || view === 'positions' || view === 'risk') && (
              <>
                <div className="notice-inline">
                  Connector data can be absent or stale. Quotes and terminal snapshots are not execution instructions.
                </div>
                {view === 'orders' || view === 'positions' || view === 'risk' ? (
                  <PaperTradingView />
                ) : (
                  <><CoverageView /><Mt5View /><AngelOneView /></>
                )}
              </>
            )}
            {view === 'historical' && <HistoricalView />}
            {view === 'instruments' && <InstrumentsView />}
            {view === 'paper' && <PaperTradingView />}
            {view === 'reconcile' && (
              <section className="workspace-panel">
                <div className="section-heading">
                  <div>
                    <p className="eyebrow">RECONCILIATION CONSOLE</p>
                    <h2>Signal-to-Fill Audit</h2>
                  </div>
                </div>
                <p className="notice-inline">
                  The Reconciliation Console is scheduled for implementation in <strong>Phase V2.4</strong>. It will provide end-to-end matching of strategy signals, simulated orders, broker fills, and realized P&L with discrepancy detection.
                </p>
              </section>
            )}
            {view === 'system' && (
              <section id="status" className="workspace-panel">
                <div className="section-heading">
                  <div>
                    <p className="eyebrow">PLATFORM HEALTH</p>
                    <h2>System status</h2>
                  </div>
                  <button className="quiet-button" disabled={busy} onClick={() => void load(search)}>Refresh</button>
                </div>
                {status ? (
                  <dl className="status-list">
                    <div><dt>Version</dt><dd>{status.version}</dd></div>
                    <div><dt>Environment</dt><dd>{status.environment}</dd></div>
                    <div><dt>Trading mode</dt><dd>{status.trading_mode}</dd></div>
                    <div><dt>Market feed</dt><dd>{status.market_data}</dd></div>
                    <div>
                      <dt>Live execution</dt>
                      <dd><span className="result-pill">{status.live_trading_enabled ? 'Reported enabled — review configuration' : 'Unavailable (Read-Only)'}</span></dd>
                    </div>
                  </dl>
                ) : (
                  <p role="status">Status unavailable. Refresh to retry.</p>
                )}
                <div className="notice-inline">
                  Offline research simulations only. Paper orders and read-only broker telemetry active.
                </div>
              </section>
            )}

            <footer className="workspace-footer">
              TradeCartel Operations Cockpit · Historical results and simulated outcomes are not broker fills or investment advice.
            </footer>
          </main>
        </div>
      )}
    </div>
  );
}

createRoot(document.getElementById('root')!).render(<App />);
