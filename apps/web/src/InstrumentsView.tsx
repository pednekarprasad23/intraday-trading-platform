import { useEffect, useState, type FormEvent } from 'react';
import { api, type Instrument } from './api';
import './InstrumentsView.css';

export function InstrumentsView() {
  const [items, setItems] = useState<Instrument[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [assetClass, setAssetClass] = useState<string>('');
  const [exchange, setExchange] = useState<string>('');
  const [active, setActive] = useState<boolean | undefined>(undefined);
  const [offset, setOffset] = useState(0);
  const limit = 50;

  const load = async (reset = true) => {
    setLoading(true);
    setError('');
    try {
      const params = new URLSearchParams({
        limit: limit.toString(),
        offset: (reset ? 0 : offset).toString(),
        ...(search && { search }),
        ...(assetClass && { asset_class: assetClass }),
        ...(exchange && { exchange }),
        ...(active !== undefined && { active: active.toString() }),
      });
      const data = await api<{ items: Instrument[]; total: number }>('/instruments?' + params.toString());
      setItems(reset ? data.items : [...items, ...data.items]);
    } catch (e) {
      setError((e as Error).message);
      setItems([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void load(); }, []);

  function handleSearch(e: FormEvent) {
    e.preventDefault();
    setOffset(0);
    void load();
  }

  function handleFilter() {
    setOffset(0);
    void load();
  }

  function handleClearFilters() {
    setSearch('');
    setAssetClass('');
    setExchange('');
    setActive(undefined);
    setOffset(0);
    void load();
  }

  const uniqueAssetClasses = [...new Set(items.map(i => i.asset_class))];
  const uniqueExchanges = [...new Set(items.map(i => i.exchange))];

  return (
    <section id="instruments" className="workspace-panel instruments-view">
      <div className="section-heading">
        <div>
          <p className="eyebrow">PROVIDER CATALOG</p>
          <h2>Instrument master</h2>
          <p className="muted">
            Mappings include illustrative DEMO entries and any verified provider metadata.
            Listing does not imply data entitlement or execution eligibility.
          </p>
        </div>
      </div>

      {/* Filters */}
      <div className="instruments-filters">
        <form onSubmit={handleSearch} className="filter-row">
          <label>
            Search
            <input
              type="text"
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Symbol or name"
            />
          </label>
          <label>
            Asset class
            <select value={assetClass} onChange={e => setAssetClass(e.target.value)}>
              <option value="">All</option>
              <option value="INDEX">INDEX</option>
              <option value="EQUITY">EQUITY</option>
              <option value="FUTURES">FUTURES</option>
              <option value="COMMODITY">COMMODITY</option>
              <option value="CRYPTO">CRYPTO</option>
            </select>
          </label>
          <label>
            Exchange
            <select value={exchange} onChange={e => setExchange(e.target.value)}>
              <option value="">All</option>
              <option value="NSE">NSE</option>
              <option value="BSE">BSE</option>
              <option value="DEMO">DEMO</option>
              <option value="MT5">MT5</option>
            </select>
          </label>
          <label>
            Active
            <select value={active === undefined ? '' : active.toString()} onChange={e => setActive(e.target.value === 'true')}>
              <option value="">All</option>
              <option value="true">Active</option>
              <option value="false">Inactive</option>
            </select>
          </label>
          <div className="filter-actions">
            <button type="submit" className="primary-button" disabled={loading}>
              Search
            </button>
            <button type="button" className="quiet-button" onClick={handleClearFilters}>
              Clear
            </button>
          </div>
        </form>
      </div>

      {/* Status */}
      {loading && <p role="status">Loading instruments…</p>}
      {error && (
        <p role="alert" className="error">
          Unable to load instruments: {error} <button className="quiet-button" onClick={() => void load()}>Retry</button>
        </p>
      )}

      {/* Table */}
      {!loading && !error && (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Symbol</th>
                <th>Name</th>
                <th>Asset Class</th>
                <th>Exchange</th>
                <th>Source</th>
                <th>Execution</th>
              </tr>
            </thead>
            <tbody>
              {items.map(i => (
                <tr key={i.id}>
                  <td><strong>{i.canonical_symbol}</strong></td>
                  <td>{i.display_name}</td>
                  <td><span className="asset-class-badge">{i.asset_class}</span></td>
                  <td><span className="exchange-badge">{i.exchange}</span></td>
                  <td><span className="result-pill">{i.demo ? 'DEMO' : 'Provider mapping'}</span></td>
                  <td>{i.execution_enabled ? <span className="status-ok">Enabled</span> : <span className="status-disabled">Disabled</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {items.length === 0 && (
            <p className="empty-state">No matching instruments. Try another search or check the catalog import.</p>
          )}
        </div>
      )}

      {/* Stats */}
      {!loading && !error && items.length > 0 && (
        <div className="instruments-stats">
          <h4>Summary</h4>
          <div className="stat-row">
            <span className="stat-label">Total:</span>
            <span className="stat-value">{items.length} instruments</span>
          </div>
          <div className="stat-row">
            <span className="stat-label">By Asset Class:</span>
            <div className="stat-breakdown">
              {['INDEX', 'EQUITY', 'FUTURES', 'COMMODITY', 'CRYPTO'].map(ac => {
                const count = items.filter(i => i.asset_class === ac).length;
                return count > 0 ? <span key={ac}>{ac}: {count}</span> : null;
              })}
            </div>
          </div>
          <div className="stat-row">
            <span className="stat-label">By Exchange:</span>
            <div className="stat-breakdown">
              {['NSE', 'BSE', 'DEMO', 'MT5'].map(ex => {
                const count = items.filter(i => i.exchange === ex).length;
                return count > 0 ? <span key={ex}>{ex}: {count}</span> : null;
              })}
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
