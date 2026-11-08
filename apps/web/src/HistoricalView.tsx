import { useEffect, useState, useCallback, useMemo, useRef } from 'react';
import { historical, type HistoricalCandle, type HistoricalPartition, type Page } from './api';
import './HistoricalView.css';

const DEFAULT_TIMEFRAME = '1m';
const DEFAULT_SESSION = '2026-11-06';
const MAX_ROWS = 500;

// ============================================================================
// Chart rendering with native canvas (no external dependencies)
// ============================================================================

interface ChartBounds {
  x: number;
  y: number;
  width: number;
  height: number;
}

function useChartContainer() {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [bounds, setBounds] = useState<ChartBounds>({ x: 0, y: 0, width: 0, height: 0 });

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const resizeObserver = new ResizeObserver(entries => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        setBounds({ x: 0, y: 0, width, height });
      }
    });

    resizeObserver.observe(el);
    return () => resizeObserver.disconnect();
  }, []);

  return { containerRef, bounds };
}

function drawCandlestickChart(
  canvas: HTMLCanvasElement,
  candles: HistoricalCandle[],
  bounds: ChartBounds,
  selectedDate: string
) {
  const ctx = canvas.getContext('2d');
  if (!ctx) return;

  const { x, y, width, height } = bounds;
  const padding = { top: 20, right: 40, bottom: 30, left: 10 };
  const chartWidth = width - padding.left - padding.right;
  const chartHeight = height - padding.top - padding.bottom;

  // Clear canvas
  ctx.fillStyle = getComputedStyle(document.body).getPropertyValue('--bg-surface') || '#0d1117';
  ctx.fillRect(0, 0, width, height);

  // Determine price range
  let minPrice = Infinity;
  let maxPrice = -Infinity;
  for (const c of candles) {
    const open = parseFloat(c.open);
    const high = parseFloat(c.high);
    const low = parseFloat(c.low);
    const close = parseFloat(c.close);
    if (high > maxPrice) maxPrice = high;
    if (low < minPrice) minPrice = low;
  }

  if (minPrice === Infinity || maxPrice === -Infinity) return;

  const priceRange = maxPrice - minPrice;
  const pricePadding = priceRange * 0.05;
  minPrice -= pricePadding;
  maxPrice += pricePadding;

  // Y-axis scale
  const scaleY = (price: number) =>
    height - padding.bottom - ((price - minPrice) / (maxPrice - minPrice)) * chartHeight;

  // X-axis scale
  const candleWidth = candles.length > 0 ? Math.min(10, chartWidth / candles.length - 2) : 10;
  const gap = Math.max(1, (chartWidth - candleWidth * candles.length) / (candles.length + 1));

  // Draw grid lines
  ctx.strokeStyle = getComputedStyle(document.body).getPropertyValue('--border-default') || '#30363d';
  ctx.lineWidth = 1;

  // Horizontal grid lines (5 levels)
  const numGridLines = 5;
  for (let i = 0; i <= numGridLines; i++) {
    const price = minPrice + (maxPrice - minPrice) * (i / numGridLines);
    const py = scaleY(price);
    ctx.beginPath();
    ctx.moveTo(padding.left, py);
    ctx.lineTo(width - padding.right, py);
    ctx.stroke();

    // Price labels
    ctx.fillStyle = getComputedStyle(document.body).getPropertyValue('--fg-muted') || '#7a8591';
    ctx.font = '11px system-ui, -apple-system, sans-serif';
    ctx.textAlign = 'left';
    ctx.fillText(price.toFixed(2), width - padding.right + 4, py + 4);
  }

  // Draw candles
  candles.forEach((candle, i) => {
    const cx = padding.left + gap + i * (candleWidth + gap);
    const open = parseFloat(candle.open);
    const high = parseFloat(candle.high);
    const low = parseFloat(candle.low);
    const close = parseFloat(candle.close);
    const bullish = close >= open;

    const top = scaleY(Math.max(high, open, close));
    const bottom = scaleY(Math.min(low, open, close));
    const bodyHeight = Math.max(1, Math.abs(bottom - top));

    // Fill color
    ctx.fillStyle = bullish
      ? getComputedStyle(document.body).getPropertyValue('--color-success') || '#238636'
      : getComputedStyle(document.body).getPropertyValue('--color-danger') || '#da3633';

    // Draw wick
    ctx.strokeStyle = ctx.fillStyle;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(cx + candleWidth / 2, scaleY(high));
    ctx.lineTo(cx + candleWidth / 2, scaleY(low));
    ctx.stroke();

    // Draw body
    ctx.fillRect(cx, top, candleWidth, bodyHeight);
  });

  // X-axis labels (show every nth candle)
  ctx.fillStyle = getComputedStyle(document.body).getPropertyValue('--fg-muted') || '#7a8591';
  ctx.textAlign = 'center';
  const labelStep = Math.max(1, Math.floor(candles.length / 10));
  for (let i = 0; i < candles.length; i += labelStep) {
    const cx = padding.left + gap + i * (candleWidth + gap);
    const dateStr = candles[i].bar_time.substring(11, 16); // HH:MM
    ctx.fillText(dateStr, cx, height - padding.bottom + 20);
  }
}

function drawVolumeChart(
  canvas: HTMLCanvasElement,
  candles: HistoricalCandle[],
  bounds: ChartBounds
) {
  const ctx = canvas.getContext('2d');
  if (!ctx) return;

  const { x, y, width, height } = bounds;
  const padding = { top: 10, right: 40, bottom: 20, left: 10 };
  const chartWidth = width - padding.left - padding.right;
  const chartHeight = height - padding.top - padding.bottom - 15; // -15 for label

  // Clear canvas
  ctx.fillStyle = getComputedStyle(document.body).getPropertyValue('--bg-surface') || '#0d1117';
  ctx.fillRect(0, 0, width, height);

  // Find max volume
  const maxVolume = Math.max(...candles.map(c => parseFloat(c.volume)));

  // Y-axis scale
  const scaleY = (volume: number) =>
    height - padding.bottom - (volume / maxVolume) * chartHeight;

  // X-axis scale
  const candleWidth = candles.length > 0 ? Math.min(10, chartWidth / candles.length - 2) : 10;
  const gap = Math.max(1, (chartWidth - candleWidth * candles.length) / (candles.length + 1));

  // Draw volume bars
  candles.forEach((candle, i) => {
    const cx = padding.left + gap + i * (candleWidth + gap);
    const volume = parseFloat(candle.volume);
    const barHeight = Math.max(1, height - padding.bottom - scaleY(volume));
    const bullish = parseFloat(candle.close) >= parseFloat(candle.open);

    ctx.fillStyle = bullish
      ? getComputedStyle(document.body).getPropertyValue('--color-success')?.replace(')', ', 0.3)') || 'rgba(56, 139, 55, 0.3)'
      : getComputedStyle(document.body).getPropertyValue('--color-danger')?.replace(')', ', 0.3)') || 'rgba(248, 81, 73, 0.3)';

    ctx.fillRect(cx, scaleY(volume), candleWidth, barHeight);
  });

  // X-axis label
  ctx.fillStyle = getComputedStyle(document.body).getPropertyValue('--fg-muted') || '#7a8591';
  ctx.font = '11px system-ui, -apple-system, sans-serif';
  ctx.textAlign = 'left';
  ctx.fillText('Volume', padding.left, 12);
}

// ============================================================================
// HistoricalView Component
// ============================================================================

export function HistoricalView() {
  const { containerRef, bounds } = useChartContainer();
  const chartCanvas = useRef<HTMLCanvasElement | null>(null);
  const volCanvas = useRef<HTMLCanvasElement | null>(null);
  const [partitions, setPartitions] = useState<HistoricalPartition[]>([]);
  const [selectedPartition, setSelectedPartition] = useState<HistoricalPartition | null>(null);
  const [candles, setCandles] = useState<HistoricalCandle[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [candlesLoading, setCandlesLoading] = useState(false);
  const [candleError, setCandleError] = useState('');
  const [candleOffset, setCandleOffset] = useState(0);
  const [showTable, setShowTable] = useState(false);
  const [filterTimeframe, setFilterTimeframe] = useState('');
  const [filterSession, setFilterSession] = useState('');

  // Load partitions on mount
  useEffect(() => {
    let active = true;
    setLoading(true);
    historical
      .partitions()
      .then(result => {
        if (active) {
          setPartitions(result.items);
          setError('');
        }
      })
      .catch(error => {
        if (active) {
          setPartitions([]);
          setError((error as Error).message);
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  // Filter partitions
  const filteredPartitions = useMemo(() => {
    return partitions.filter(p => {
      if (filterTimeframe && p.timeframe !== filterTimeframe) return false;
      if (filterSession && p.session_date !== filterSession) return false;
      return true;
    });
  }, [partitions, filterTimeframe, filterSession]);

  // Load candles when partition is selected
  const loadCandles = useCallback(async (partition: HistoricalPartition, offset: number = 0) => {
    setSelectedPartition(partition);
    setCandleOffset(offset);
    setCandlesLoading(true);
    setCandleError('');
    setShowTable(false);
    try {
      const result = await historical.candles(partition.id, offset);
      setCandles(result.items);
      // Update partition metadata with new counts
      setSelectedPartition({
        ...partition,
        row_count: result.total,
      });
    } catch (error) {
      setCandleError((error as Error).message);
      setCandles([]);
    } finally {
      setCandlesLoading(false);
    }
  }, []);

  // Draw charts when candles change
  useEffect(() => {
    if (!candles.length || !chartCanvas.current || !volCanvas.current || !containerRef.current) return;

    const canvas = chartCanvas.current;
    const volCanvasEl = volCanvas.current;
    const container = containerRef.current;

    // Draw OHLCV chart
    drawCandlestickChart(canvas, candles, bounds, selectedPartition?.session_date || '');

    // Draw volume chart
    drawVolumeChart(volCanvasEl, candles, bounds);
  }, [candles, bounds, chartCanvas, volCanvas, containerRef, selectedPartition?.session_date]);

  // Get unique timeframes and sessions for filters
  const uniqueTimeframes = useMemo(() => {
    return [...new Set(partitions.map(p => p.timeframe))];
  }, [partitions]);

  const uniqueSessions = useMemo(() => {
    return [...new Set(partitions.map(p => p.session_date))].sort();
  }, [partitions]);

  if (!containerRef.current) {
    return (
      <section className="historical-view">
        <div className="section-heading">
          <div>
            <p className="eyebrow">HISTORICAL DATA</p>
            <h2>Historical market data</h2>
            <p className="muted">
              Browse stored OHLCV partitions with candlestick visualization and session coverage.
            </p>
          </div>
        </div>
        <p>Loading...</p>
      </section>
    );
  }

  return (
    <section className="historical-view">
      <div className="section-heading">
        <div>
          <p className="eyebrow">HISTORICAL DATA</p>
          <h2>Historical market data</h2>
          <p className="muted">
            Browse stored OHLCV partitions with candlestick visualization and session coverage.
            Select a partition to view candles.
          </p>
        </div>
      </div>

      {/* Filters */}
      <div className="historical-filters">
        <div className="filter-group">
          <label>
            Timeframe
            <select
              value={filterTimeframe}
              onChange={e => setFilterTimeframe(e.target.value)}
            >
              <option value="">All timeframes</option>
              {uniqueTimeframes.map(tf => (
                <option key={tf} value={tf}>
                  {tf}
                </option>
              ))}
            </select>
          </label>
          <label>
            Session date
            <select
              value={filterSession}
              onChange={e => setFilterSession(e.target.value)}
            >
              <option value="">All sessions</option>
              {uniqueSessions.map(session => (
                <option key={session} value={session}>
                  {session}
                </option>
              ))}
            </select>
          </label>
          <button
            className="quiet-button"
            onClick={() => {
              setFilterTimeframe('');
              setFilterSession('');
            }}
          >
            Clear filters
          </button>
        </div>
      </div>

      {/* Partitions list */}
      {loading && <p role="status">Loading historical partitions…</p>}
      {error && (
        <p role="alert" className="error">
          Unable to load historical data: {error}
        </p>
      )}
      {!loading && !error && filteredPartitions.length === 0 && (
        <p className="empty-state">
          No historical partitions found. Import data to see partitions listed here.
        </p>
      )}
      {!loading && !error && filteredPartitions.length > 0 && (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Session Date</th>
                <th>Provider</th>
                <th>Timeframe</th>
                <th>Bars</th>
                <th>Checksum</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {filteredPartitions.map(partition => (
                <tr key={partition.id}>
                  <td>{partition.session_date}</td>
                  <td>{partition.provider}</td>
                  <td>
                    <code>{partition.timeframe}</code>
                  </td>
                  <td>{partition.row_count}</td>
                  <td>
                    <code>{partition.checksum_sha256.slice(0, 16)}…</code>
                  </td>
                  <td>
                    <button
                      className="primary-button"
                      onClick={() => loadCandles(partition)}
                    >
                      View
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Selected partition display */}
      {selectedPartition && (
        <div className="candles-display">
          <div className="candles-header">
            <h3>
              {selectedPartition.session_date} · {selectedPartition.timeframe} ·{' '}
              {selectedPartition.row_count} bars
            </h3>
            <div className="candles-actions">
              <button
                className={`quiet-button ${showTable ? 'active' : ''}`}
                onClick={() => setShowTable(false)}
              >
                Chart
              </button>
              <button
                className={`quiet-button ${showTable ? 'active' : ''}`}
                onClick={() => setShowTable(true)}
              >
                Table
              </button>
            </div>
          </div>

          {/* Chart view */}
          {!showTable && (
            <div className="chart-container">
              <div className="chart-info">
                <div className="info-item">
                  <strong>Session:</strong> {selectedPartition.session_date}
                </div>
                <div className="info-item">
                  <strong>Timeframe:</strong> {selectedPartition.timeframe}
                </div>
                <div className="info-item">
                  <strong>Bars:</strong> {candles.length} of {selectedPartition.row_count}
                  {candles.length < selectedPartition.row_count && (
                    <button
                      className="quiet-button"
                      onClick={() => {
                        const newOffset = candleOffset + MAX_ROWS;
                        loadCandles(selectedPartition, newOffset);
                      }}
                    >
                      Load more
                    </button>
                  )}
                </div>
              </div>

              <div className="chart-wrapper">
                <div className="chart-card">
                  <h4>OHLCV Chart</h4>
                  <div className="chart-body">
                    <div ref={containerRef} className="canvas-container">
                      <canvas
                        ref={chartCanvas}
                        width={800}
                        height={400}
                        style={{
                          width: '100%',
                          height: '100%',
                          display: 'block',
                        }}
                      />
                    </div>
                    {candlesLoading && (
                      <div className="loading-overlay">Loading candles…</div>
                    )}
                    {candleError && (
                      <div className="error-overlay">{candleError}</div>
                    )}
                  </div>
                </div>

                <div className="chart-card">
                  <h4>Volume</h4>
                  <div className="chart-body">
                    <div ref={containerRef} className="canvas-container">
                      <canvas
                        ref={volCanvas}
                        width={800}
                        height={150}
                        style={{
                          width: '100%',
                          height: '100%',
                          display: 'block',
                        }}
                      />
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Table view */}
          {showTable && (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Bar Time (IST)</th>
                    <th>Open</th>
                    <th>High</th>
                    <th>Low</th>
                    <th>Close</th>
                    <th>Volume</th>
                  </tr>
                </thead>
                <tbody>
                  {candlesLoading && (
                    <tr>
                      <td colSpan={6}>Loading candles…</td>
                    </tr>
                  )}
                  {candleError && (
                    <tr>
                      <td colSpan={6} className="error">
                        {candleError}
                      </td>
                    </tr>
                  )}
                  {!candlesLoading && !candleError && candles.length === 0 && (
                    <tr>
                      <td colSpan={6} className="empty-state">
                        No candles available for this partition.
                      </td>
                    </tr>
                  )}
                  {!candlesLoading && !candleError && candles.length > 0 && (
                    candles.map(candle => (
                      <tr key={candle.bar_time}>
                        <td>
                          <code>{new Date(candle.bar_time).toLocaleString('en-IN')}</code>
                        </td>
                        <td>{candle.open}</td>
                        <td>{candle.high}</td>
                        <td>{candle.low}</td>
                        <td>{candle.close}</td>
                        <td>{candle.volume}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
              {candles.length > 0 &&
                candles.length < selectedPartition.row_count && (
                  <div className="pager">
                    <button
                      disabled={candleOffset === 0 || candlesLoading}
                      onClick={() => {
                        const newOffset = candleOffset - MAX_ROWS;
                        loadCandles(selectedPartition, Math.max(0, newOffset));
                      }}
                    >
                      Previous
                    </button>
                    <span>
                      {candleOffset + 1}–
                      {Math.min(candleOffset + candles.length, selectedPartition.row_count)} of{' '}
                      {selectedPartition.row_count}
                    </span>
                    <button
                      disabled={
                        candleOffset + candles.length >= selectedPartition.row_count ||
                        candlesLoading
                      }
                      onClick={() => {
                        const newOffset = candleOffset + MAX_ROWS;
                        loadCandles(selectedPartition, newOffset);
                      }}
                    >
                      Next
                    </button>
                  </div>
                )}
            </div>
          )}
        </div>
      )}

      {/* Session coverage summary */}
      <div className="coverage-summary">
        <h4>Session Coverage</h4>
        {partitions.length > 0 ? (
          <div className="coverage-stats">
            <div className="stat">
              <span className="stat-value">{partitions.length}</span>
              <span className="stat-label">total partitions</span>
            </div>
            <div className="stat">
              <span className="stat-value">
                {[...new Set(partitions.map(p => p.session_date))].length}
              </span>
              <span className="stat-label">unique sessions</span>
            </div>
            <div className="stat">
              <span className="stat-value">
                {partitions.reduce((sum, p) => sum + p.row_count, 0).toLocaleString()}
              </span>
              <span className="stat-label">total bars</span>
            </div>
          </div>
        ) : (
          <p className="muted">No historical data available.</p>
        )}
      </div>
    </section>
  );
}
