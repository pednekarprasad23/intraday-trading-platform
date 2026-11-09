import { useEffect, useState } from 'react';
import { opportunities, type OpportunityItem, type OpportunitiesSummary, type CalibrationData, type MissedRecord } from './api';

export function OpportunitiesView() {
  const [summary, setSummary] = useState<OpportunitiesSummary | null>(null);
  const [items, setItems] = useState<OpportunityItem[]>([]);
  const [calibration, setCalibration] = useState<CalibrationData | null>(null);
  const [missed, setMissed] = useState<MissedRecord[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [expiryFilter, setExpiryFilter] = useState<string>('');
  const [optionTypeFilter, setOptionTypeFilter] = useState<string>('ALL');
  const [minScore, setMinScore] = useState<number>(0);
  const [rankingEligibleOnly, setRankingEligibleOnly] = useState<boolean>(false);

  // Selected Detail Item
  const [selectedItem, setSelectedItem] = useState<OpportunityItem | null>(null);
  const [activeTab, setActiveTab] = useState<'opportunities' | 'calibration' | 'missed'>('opportunities');

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [sumRes, listRes, calRes, missedRes] = await Promise.all([
        opportunities.summary(),
        opportunities.list({
          expiry: expiryFilter || undefined,
          option_type: optionTypeFilter !== 'ALL' ? optionTypeFilter : undefined,
          min_score: minScore > 0 ? minScore : undefined,
          ranking_eligible_only: rankingEligibleOnly || undefined,
        }),
        opportunities.calibration(),
        opportunities.missed(),
      ]);
      setSummary(sumRes);
      setItems(listRes.items);
      setCalibration(calRes);
      setMissed(missedRes.items);
    } catch (err: any) {
      setError(err?.message || 'Failed to load Opportunity Portal intelligence');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 5000);
    return () => clearInterval(interval);
  }, [expiryFilter, optionTypeFilter, minScore, rankingEligibleOnly]);

  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 text-white shadow-lg">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold tracking-tight">TradeCartel Opportunity Portal</h1>
              <span className="px-2.5 py-0.5 text-xs font-semibold bg-indigo-500/20 text-indigo-400 border border-indigo-500/30 rounded-full">
                V2.11 Research & Intelligence
              </span>
            </div>
            <p className="text-sm text-slate-400 mt-1">
              Multi-engine NIFTY Options analysis, quantitative ranking, explainability, and historical outcome evaluation.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <span className="inline-flex items-center gap-1.5 px-3 py-1 text-xs font-medium rounded-md bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
              System State: {summary?.system_state || 'RESEARCH & INTELLIGENCE ONLY'}
            </span>
            <button
              onClick={loadData}
              className="px-3 py-1.5 text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg border border-slate-700 transition"
            >
              Manual Refresh
            </button>
          </div>
        </div>

        {/* Summary Metric Cards */}
        {summary && (
          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-4 mt-6 pt-6 border-t border-slate-800">
            <div>
              <div className="text-xs text-slate-400 font-medium">Underlying</div>
              <div className="text-lg font-bold text-slate-100 mt-0.5">{summary.underlying}</div>
            </div>
            <div>
              <div className="text-xs text-slate-400 font-medium">Spot Price</div>
              <div className="text-lg font-bold text-emerald-400 mt-0.5">{summary.spot}</div>
            </div>
            <div>
              <div className="text-xs text-slate-400 font-medium">Expiry</div>
              <div className="text-lg font-bold text-slate-100 mt-0.5">{summary.expiry}</div>
            </div>
            <div>
              <div className="text-xs text-slate-400 font-medium">Total Candidates</div>
              <div className="text-lg font-bold text-slate-100 mt-0.5">{summary.candidates_count}</div>
            </div>
            <div>
              <div className="text-xs text-slate-400 font-medium">Ranking Eligible</div>
              <div className="text-lg font-bold text-indigo-400 mt-0.5">{summary.ranking_eligible_count}</div>
            </div>
            <div>
              <div className="text-xs text-slate-400 font-medium">Data Coverage</div>
              <div className="text-xs font-semibold text-slate-300 mt-1 truncate" title={summary.data_coverage}>
                {summary.data_coverage}
              </div>
            </div>
            <div>
              <div className="text-xs text-slate-400 font-medium">Execution Mode</div>
              <div className="text-xs font-semibold text-amber-400 mt-1">Simulation Only</div>
            </div>
          </div>
        )}
      </div>

      {/* Navigation Tabs */}
      <div className="flex border-b border-slate-800">
        <button
          onClick={() => setActiveTab('opportunities')}
          className={`px-4 py-2.5 text-sm font-medium border-b-2 transition ${
            activeTab === 'opportunities'
              ? 'border-indigo-500 text-indigo-400'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          Ranked Opportunities ({items.length})
        </button>
        <button
          onClick={() => setActiveTab('calibration')}
          className={`px-4 py-2.5 text-sm font-medium border-b-2 transition ${
            activeTab === 'calibration'
              ? 'border-indigo-500 text-indigo-400'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          Calibration & Bands
        </button>
        <button
          onClick={() => setActiveTab('missed')}
          className={`px-4 py-2.5 text-sm font-medium border-b-2 transition ${
            activeTab === 'missed'
              ? 'border-indigo-500 text-indigo-400'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          Missed Opportunity Analysis ({missed.length})
        </button>
      </div>

      {activeTab === 'opportunities' && (
        <div className="space-y-4">
          {/* Filters Bar */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 flex flex-wrap items-center gap-4">
            <div className="flex items-center gap-2">
              <label className="text-xs text-slate-400 font-medium">Type:</label>
              <select
                value={optionTypeFilter}
                onChange={(e) => setOptionTypeFilter(e.target.value)}
                className="bg-slate-800 border border-slate-700 text-slate-200 text-xs rounded-lg px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              >
                <option value="ALL">All Options</option>
                <option value="CALL">CALL</option>
                <option value="PUT">PUT</option>
              </select>
            </div>

            <div className="flex items-center gap-2">
              <label className="text-xs text-slate-400 font-medium">Min Score:</label>
              <input
                type="number"
                min="0"
                max="100"
                value={minScore}
                onChange={(e) => setMinScore(Number(e.target.value))}
                className="w-20 bg-slate-800 border border-slate-700 text-slate-200 text-xs rounded-lg px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              />
            </div>

            <div className="flex items-center gap-2">
              <label className="text-xs text-slate-400 font-medium">Expiry:</label>
              <input
                type="text"
                placeholder="YYYY-MM-DD"
                value={expiryFilter}
                onChange={(e) => setExpiryFilter(e.target.value)}
                className="w-32 bg-slate-800 border border-slate-700 text-slate-200 text-xs rounded-lg px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              />
            </div>

            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="eligibleOnly"
                checked={rankingEligibleOnly}
                onChange={(e) => setRankingEligibleOnly(e.target.checked)}
                className="rounded bg-slate-800 border-slate-700 text-indigo-500 focus:ring-indigo-500"
              />
              <label htmlFor="eligibleOnly" className="text-xs text-slate-300 font-medium cursor-pointer">
                Ranking Eligible Only
              </label>
            </div>

            <div className="ml-auto text-xs text-slate-400">
              Showing {items.length} opportunities (Auto-refreshing every 5s)
            </div>
          </div>

          {/* Opportunities Table */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-lg">
            {error && (
              <div className="p-4 bg-red-500/10 border-b border-red-500/20 text-red-400 text-xs">
                {error}
              </div>
            )}
            {loading && items.length === 0 ? (
              <div className="p-8 text-center text-slate-400 text-sm">Loading intelligence pipeline...</div>
            ) : items.length === 0 ? (
              <div className="p-8 text-center text-slate-400 text-sm">No opportunities match current filter criteria.</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="border-b border-slate-800 bg-slate-950/50 text-xs font-semibold text-slate-400 uppercase tracking-wider">
                      <th className="py-3.5 px-4">Rank / Contract</th>
                      <th className="py-3.5 px-4">Type</th>
                      <th className="py-3.5 px-4">Strike</th>
                      <th className="py-3.5 px-4">Expiry</th>
                      <th className="py-3.5 px-4">Score</th>
                      <th className="py-3.5 px-4">Liquidity</th>
                      <th className="py-3.5 px-4">IV Snapshot</th>
                      <th className="py-3.5 px-4">OI / Part.</th>
                      <th className="py-3.5 px-4">Completeness</th>
                      <th className="py-3.5 px-4">Status</th>
                      <th className="py-3.5 px-4 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60 text-xs text-slate-300">
                    {items.map((item, idx) => (
                      <tr
                        key={item.candidate_id || idx}
                        onClick={() => setSelectedItem(item)}
                        className="hover:bg-slate-800/40 cursor-pointer transition"
                      >
                        <td className="py-3 px-4 font-medium text-slate-100 flex items-center gap-2">
                          <span className="w-6 h-6 rounded-full bg-slate-800 text-indigo-400 flex items-center justify-center font-bold text-[10px] border border-slate-700">
                            #{idx + 1}
                          </span>
                          <span>{item.contract}</span>
                        </td>
                        <td className="py-3 px-4">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                            item.option_type === 'CALL' ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/20' : 'bg-pink-500/10 text-pink-400 border border-pink-500/20'
                          }`}>
                            {item.option_type}
                          </span>
                        </td>
                        <td className="py-3 px-4 font-mono">{item.strike}</td>
                        <td className="py-3 px-4 text-slate-400">{item.expiry}</td>
                        <td className="py-3 px-4 font-bold text-indigo-300 font-mono text-sm">
                          {item.composite_score}
                        </td>
                        <td className="py-3 px-4 font-mono text-slate-300">{item.sub_scores.liquidity_quality}</td>
                        <td className="py-3 px-4 font-mono text-slate-300">{item.sub_scores.iv_snapshot}</td>
                        <td className="py-3 px-4 font-mono text-slate-300">{item.sub_scores.oi_participation}</td>
                        <td className="py-3 px-4">
                          <span className={`px-2 py-0.5 rounded text-[10px] uppercase font-semibold ${
                            item.completeness === 'complete' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                          }`}>
                            {item.completeness}
                          </span>
                        </td>
                        <td className="py-3 px-4 text-slate-400 text-[11px]">{item.status}</td>
                        <td className="py-3 px-4 text-right">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              setSelectedItem(item);
                            }}
                            className="px-2.5 py-1 bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-400 rounded border border-indigo-500/30 font-medium text-[11px] transition"
                          >
                            Inspect
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {activeTab === 'calibration' && calibration && (
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 space-y-6 shadow-lg">
          <div>
            <h2 className="text-lg font-bold text-slate-100">Research Calibration & Score Bands</h2>
            <p className="text-xs text-slate-400 mt-1">
              Sample count: {calibration.sample_count} | Coverage: {calibration.coverage_percentage}%
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {Object.entries(calibration.score_bands).map(([band, data]) => (
              <div key={band} className="bg-slate-950/60 border border-slate-800 rounded-lg p-4">
                <div className="text-xs text-slate-400 font-semibold uppercase">Score Band {band}</div>
                <div className="text-2xl font-bold text-slate-100 mt-1">{data.count} <span className="text-xs font-normal text-slate-400">setups</span></div>
                <div className="mt-3 text-xs text-emerald-400 font-medium">
                  Favorable Outcome: {data.favorable_outcome_pct}%
                </div>
              </div>
            ))}
          </div>

          <div className="border-t border-slate-800 pt-6">
            <h3 className="text-sm font-semibold text-slate-200 mb-3">Classification Distributions</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {Object.entries(calibration.classification_distributions).map(([cls, count]) => (
                <div key={cls} className="flex items-center justify-between bg-slate-950/40 border border-slate-800/80 px-4 py-2.5 rounded-lg text-xs">
                  <span className="text-slate-300 font-medium">{cls}</span>
                  <span className="font-mono font-bold text-indigo-400">{count}</span>
                </div>
              ))}
            </div>
          </div>

          {calibration.warnings && calibration.warnings.length > 0 && (
            <div className="p-4 bg-amber-500/10 border border-amber-500/20 rounded-lg text-xs text-amber-300">
              <span className="font-bold">Research Notice:</span> {calibration.warnings.join(' ')}
            </div>
          )}
        </div>
      )}

      {activeTab === 'missed' && (
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 space-y-6 shadow-lg">
          <div>
            <h2 className="text-lg font-bold text-slate-100">Missed Opportunity Analysis (V2.10C)</h2>
            <p className="text-xs text-slate-400 mt-1">
              Requires both T0 intelligence evaluation AND objective future outcome linkage. Analyzes high-score filtered setups.
            </p>
          </div>

          <div className="space-y-4">
            {missed.map((m) => (
              <div key={m.opportunity_id} className="bg-slate-950/60 border border-slate-800 rounded-xl p-5 space-y-3">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div className="flex items-center gap-3">
                    <span className="px-2.5 py-1 bg-indigo-500/10 text-indigo-400 border border-indigo-500/30 rounded font-mono text-xs font-bold">
                      Score: {m.overall_score}
                    </span>
                    <span className="text-sm font-semibold text-slate-200">{m.candidate_id}</span>
                  </div>
                  <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                    {m.classification}
                  </span>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs pt-2 border-t border-slate-800/80">
                  <div>
                    <span className="text-slate-400 font-medium">Miss Reason / Filter State:</span>
                    <div className="text-slate-200 mt-0.5">{m.miss_reason}</div>
                  </div>
                  <div>
                    <span className="text-slate-400 font-medium">Objective Future Outcome:</span>
                    <div className="text-emerald-400 font-semibold mt-0.5">{m.objective_future_outcome}</div>
                  </div>
                </div>
                {m.notes && (
                  <div className="text-xs text-slate-400 bg-slate-900/50 p-3 rounded-lg border border-slate-800">
                    <span className="font-medium text-slate-300">Research Note:</span> {m.notes}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Opportunity Detail Modal / Slide-over */}
      {selectedItem && (
        <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-4xl max-h-[90vh] overflow-y-auto shadow-2xl p-6 space-y-6 text-slate-100">
            {/* Modal Header */}
            <div className="flex items-center justify-between border-b border-slate-800 pb-4">
              <div>
                <div className="flex items-center gap-3">
                  <h2 className="text-xl font-bold">{selectedItem.contract}</h2>
                  <span className={`px-2.5 py-0.5 rounded text-xs font-bold ${
                    selectedItem.option_type === 'CALL' ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/20' : 'bg-pink-500/10 text-pink-400 border border-pink-500/20'
                  }`}>
                    {selectedItem.option_type}
                  </span>
                </div>
                <p className="text-xs text-slate-400 mt-1 font-mono">ID: {selectedItem.candidate_id}</p>
              </div>
              <button
                onClick={() => setSelectedItem(null)}
                className="w-8 h-8 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 flex items-center justify-center font-bold transition"
              >
                ✕
              </button>
            </div>

            {/* Score & Core Metrics */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 bg-slate-950/60 p-4 rounded-xl border border-slate-800">
              <div>
                <div className="text-xs text-slate-400">Opportunity Score</div>
                <div className="text-2xl font-bold text-indigo-400 font-mono mt-0.5">{selectedItem.composite_score}</div>
              </div>
              <div>
                <div className="text-xs text-slate-400">Completeness</div>
                <div className="text-sm font-semibold text-emerald-400 uppercase mt-1">{selectedItem.completeness}</div>
              </div>
              <div>
                <div className="text-xs text-slate-400">Ranking Eligible</div>
                <div className="text-sm font-semibold text-slate-200 mt-1">{selectedItem.ranking_eligible ? 'YES' : 'NO'}</div>
              </div>
              <div>
                <div className="text-xs text-slate-400">Last Price</div>
                <div className="text-sm font-mono font-bold text-slate-200 mt-1">{selectedItem.last_price}</div>
              </div>
            </div>

            {/* Explainability Section ("WHY THIS RANKED HERE") */}
            <div className="bg-slate-950/40 border border-slate-800 rounded-xl p-5 space-y-4">
              <h3 className="text-sm font-bold text-indigo-400 tracking-wide uppercase">
                {selectedItem.explainability.title}
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {selectedItem.explainability.components.map((comp, i) => (
                  <div key={i} className="bg-slate-900 border border-slate-800 rounded-lg p-3 space-y-1.5">
                    <div className="flex items-center justify-between text-xs font-semibold">
                      <span className="text-slate-200">{comp.name}</span>
                      <span className="text-indigo-400 font-mono">Contrib: {comp.contribution} (Wt: {comp.weight})</span>
                    </div>
                    <p className="text-[11px] text-slate-400">{comp.evidence}</p>
                  </div>
                ))}
              </div>
              <div className="text-[11px] text-amber-300/80 bg-amber-500/10 border border-amber-500/20 p-3 rounded-lg">
                <span className="font-semibold">Limitation Note:</span> {selectedItem.explainability.limitations}
              </div>
            </div>

            {/* 4 Independent Analysis Engines */}
            <div>
              <h3 className="text-sm font-semibold text-slate-200 mb-3">Independent Analysis Engine Sub-Scores</h3>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                <div className="bg-slate-950/60 border border-slate-800 p-4 rounded-xl">
                  <div className="text-xs text-slate-400">Liquidity Quality</div>
                  <div className="text-xl font-bold font-mono text-emerald-400 mt-1">{selectedItem.sub_scores.liquidity_quality}</div>
                </div>
                <div className="bg-slate-950/60 border border-slate-800 p-4 rounded-xl">
                  <div className="text-xs text-slate-400">IV Snapshot</div>
                  <div className="text-xl font-bold font-mono text-cyan-400 mt-1">{selectedItem.sub_scores.iv_snapshot}</div>
                </div>
                <div className="bg-slate-950/60 border border-slate-800 p-4 rounded-xl">
                  <div className="text-xs text-slate-400">OI / Participation</div>
                  <div className="text-xl font-bold font-mono text-indigo-400 mt-1">{selectedItem.sub_scores.oi_participation}</div>
                </div>
                <div className="bg-slate-950/60 border border-slate-800 p-4 rounded-xl">
                  <div className="text-xs text-slate-400">Greeks Snapshot</div>
                  <div className="text-xl font-bold font-mono text-purple-400 mt-1">{selectedItem.sub_scores.greeks_snapshot}</div>
                </div>
              </div>
            </div>

            {/* Historical Outcome Intelligence */}
            {selectedItem.historical_outcome && (
              <div className="bg-slate-950/40 border border-slate-800 rounded-xl p-5 space-y-2">
                <h3 className="text-sm font-semibold text-slate-200">Historical Objective Outcome Evaluation</h3>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs pt-2">
                  <div>
                    <span className="text-slate-400">Status:</span>
                    <div className="font-semibold text-emerald-400 mt-0.5">{selectedItem.historical_outcome.future_evaluation_status}</div>
                  </div>
                  <div>
                    <span className="text-slate-400">Price Change:</span>
                    <div className="font-mono font-bold text-slate-200 mt-0.5">{selectedItem.historical_outcome.objective_price_change}</div>
                  </div>
                  <div>
                    <span className="text-slate-400">Classification:</span>
                    <div className="font-semibold text-indigo-300 mt-0.5">{selectedItem.historical_outcome.classification}</div>
                  </div>
                  <div>
                    <span className="text-slate-400">Coverage:</span>
                    <div className="font-mono text-slate-200 mt-0.5">{selectedItem.historical_outcome.coverage}</div>
                  </div>
                </div>
              </div>
            )}

            {/* Modal Footer / Execution Isolation Guarantee */}
            <div className="flex items-center justify-between pt-4 border-t border-slate-800 text-xs text-slate-400">
              <span className="text-amber-400 font-medium">🔒 Zero Execution Coupling: Research & Intelligence View Only (No Order/Broker Actions)</span>
              <button
                onClick={() => setSelectedItem(null)}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg font-medium transition"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
