import { useEffect, useState, type FormEvent } from 'react';
import { createRoot } from 'react-dom/client';
import { api, type Instrument, type SystemStatus } from './api';
import './style.css';
import { Mt5View } from './Mt5View';
import { AngelOneView } from './AngelOneView';

function App() {
  const [signedIn, setSignedIn] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<SystemStatus>();
  const [items, setItems] = useState<Instrument[]>([]);
  const [search, setSearch] = useState('');
  async function load(query = '') {
    setBusy(true); setError('');
    try {
      const [s, instruments] = await Promise.all([api<SystemStatus>('/system/status'), api<{items: Instrument[]}>('/instruments?search=' + encodeURIComponent(query))]);
      setStatus(s); setItems(instruments.items);
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  useEffect(() => { api('/auth/me').then(() => { setSignedIn(true); void load(); }).catch(() => {}); }, []);
  async function login(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError('');
    const values = new FormData(event.currentTarget);
    try { await api('/auth/login', {method: 'POST', body: JSON.stringify({email: values.get('email'), password: values.get('password')})}); setSignedIn(true); await load(); }
    catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  return <main className="mx-auto max-w-6xl p-6">
    <header><h1>Intraday</h1><p>Read-only data foundation · Phase 2</p></header>
    <aside className="notice"><strong>LIVE TRADING UNAVAILABLE</strong><p>Instrument master entries are demo data. Optional MT5 snapshots are separately labeled terminal data. Angel One is optional and read-only; no execution service is available.</p></aside>
    {error && <p role="alert" className="error">{error}</p>}
    {!signedIn ? <section><h2>Administrator sign in</h2><form onSubmit={login}>
      <label>Email<input name="email" type="email" autoComplete="username" required /></label>
      <label>Password<input name="password" type="password" autoComplete="current-password" required /></label>
      <button disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}</button>
      <p>Create your single-user account with the documented local bootstrap command.</p>
    </form></section> : <>
      <nav><a href="#status">System status</a><a href="#instruments">Instrument master</a><button onClick={async () => { try { await api('/auth/logout', {method:'POST'}); setSignedIn(false); setStatus(undefined); setItems([]); } catch(e) {setError((e as Error).message);} }}>Sign out</button></nav>
      <section id="status"><h2>System status</h2>{status ? <dl><dt>Version</dt><dd>{status.version}</dd><dt>Environment</dt><dd>{status.environment}</dd><dt>Mode</dt><dd>{status.trading_mode} — simulator not yet implemented</dd><dt>Market feed</dt><dd>{status.market_data}</dd><dt>Live execution</dt><dd>Unavailable</dd></dl> : <p>Loading status…</p>}</section>
      <Mt5View />
      <AngelOneView />
      <section id="instruments"><h2>Demo instrument master</h2><form onSubmit={e => { e.preventDefault(); void load(search); }}><label>Search instruments<input value={search} onChange={e => setSearch(e.target.value)} /></label><button disabled={busy}>Search</button></form>
        {busy ? <p role="status">Loading…</p> : <div className="table-wrap"><table><caption>Illustrative metadata only. No provider eligibility is verified.</caption><thead><tr><th>Symbol</th><th>Name</th><th>Asset</th><th>Exchange</th><th>Execution</th></tr></thead><tbody>{items.map(i => <tr key={i.id}><td>{i.canonical_symbol}</td><td>{i.display_name}</td><td>{i.asset_class}</td><td>{i.exchange}</td><td>Disabled</td></tr>)}</tbody></table>{items.length === 0 && <p>No matching demo instruments. Run seed-demo if the database is empty.</p>}</div>}
      </section><section><h2>Coming later</h2><p>Strategies, charts, paper orders, research, and settings are not implemented in this phase.</p></section>
    </>}
  </main>;
}
createRoot(document.getElementById('root')!).render(<App />);
