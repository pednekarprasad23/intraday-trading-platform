export interface Instrument { id: string; canonical_symbol: string; display_name: string; asset_class: string; exchange: string; execution_enabled: boolean; demo: boolean }
export interface SystemStatus { version: string; environment: string; trading_mode: string; live_trading_enabled: boolean; market_data: string }
export interface ResearchMetrics { net_pnl: string; expectancy: string | null; win_rate: string | null; profit_factor: string | null; max_drawdown: string; longest_losing_streak: number; trade_count: number }
export interface ResearchSignal { id: string; instrument_id: string; strategy_version_id: string; decision_time: string; direction: string; quality: string; provider: string; demo: boolean; partition_id: string; partition_sha256: string; input_sha256: string; label: string }
export interface ResearchReport { id: string; kind: 'BACKTEST' | 'WALK_FORWARD'; fingerprint: string; input_fingerprint: string; instrument_id: string; provider: string; demo: boolean; timeframe: string; strategy_id: string; strategy_version: string; metrics: ResearchMetrics; warnings: string[]; created_at: string; label: string; fold_count?: number; train_size?: number; test_size?: number }
export interface ResearchReportDetail extends ResearchReport { simulation_config: Record<string, unknown>; strategy_config: Record<string, unknown>; sources: unknown[]; trade_summary?: unknown[]; event_summary?: unknown[]; folds?: unknown[] }
export interface ResearchEvaluation { id: string; decision_time: string | null; instrument_id: string; direction: string; quality: string; reasons: string[]; provider: string; demo: boolean; partition_sha256: string; strategy_id: string; label: string }
export interface ScoreComponent { performance: number; risk: number; data_quality: number; structure_alignment: number }
export interface CandidateRanking { candidate_id: string; strategy_id: string; strategy_version: number; instrument_id: string; session_date: string; composite_score: number; score_breakdown: ScoreComponent; sub_scores: Record<string, number>; is_rejected: boolean; rejection_reasons: string[]; ranking_version: number; commentary: string; evidence: Record<string, unknown> }
export interface RankingsPage extends Page<CandidateRanking> { limit: number; offset: number }
export interface Page<T> { total: number; items: T[] }
export interface MarketCoverageItem { instrument_id: string; canonical_symbol: string; display_name: string; asset_class: string; exchange: string; demo: boolean; provider: string; provider_instrument_key: string; provider_exchange: string | null; mapping_verified_at: string | null; data_enabled: boolean; execution_enabled: boolean; latest_historical_session: string | null; historical_partition_count: number; live_quote_available: boolean }
export interface MarketCoverage extends Page<MarketCoverageItem> { live_feed_status: string; live_feed_note: string; observed_at: string }
export interface CoverageFilters { search?: string; provider?: string; asset_class?: string; exchange?: string; demo?: string; historical?: string }

// ============================================================================
// Paper Trading
// ============================================================================

export interface PaperAccountSummary {
  account_id: string;
  name: string;
  currency: string;
  initial_capital: string;
  available_capital: string;
  reserved_capital: string;
  total_pnl: string;
  unrealized_pnl: string;
  realized_pnl: string;
  position_count: number;
  open_position_value: string;
}

export interface PaperPosition {
  id: string;
  account_id: string;
  instrument_id: string;
  symbol: string;
  quantity: string;
  avg_entry_price: string | null;
  unrealized_pnl: string;
  realized_pnl: string;
  last_marked_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface PaperOrder {
  id: string;
  account_id: string;
  instrument_id: string;
  side: string;
  order_type: string;
  quantity: string;
  filled_quantity: string;
  price: string | null;
  state: string;
  created_at: string;
  submitted_at: string | null;
  filled_at: string | null;
  rejected_reason: string | null;
  fills: { id: string; order_id: string; quantity: string; price: string; commission: string; fees: string; slippage: string; filled_at: string; provenance: string }[];
  strategy_id: string | null;
}

export interface KillSwitchStatus {
  name: string;
  state: string;
  triggered_by: string | null;
  triggered_at: string | null;
  reason: string | null;
  reset_by: string | null;
  reset_at: string | null;
  auto_triggered: boolean;
  created_at: string | null;
  updated_at: string | null;
}

export interface OrderSubmission {
  instrument_id: string;
  side: 'buy' | 'sell';
  quantity: string;
  order_type?: 'market' | 'limit' | 'stop' | 'stop_limit';
  price?: string;
  stop_price?: string;
  strategy_id?: string;
}

export interface PaperRiskEvent {
  id: string;
  account_id: string;
  event_type: string;
  order_id: string | null;
  instrument_id: string | null;
  details: Record<string, unknown>;
  blocked: boolean;
  created_at: string;
}

export interface PaperPagination<T> { total: number; items: T[] }

export const paper = {
  summary: () => api<PaperAccountSummary>('/paper/summary'),
  positions: () => api<PaperPosition[]>('/paper/positions'),
  orders: (offset = 0, state?: string) => {
    const params = new URLSearchParams({ limit: '50', offset: String(offset) });
    if (state) params.set('state', state);
    return api<PaperPagination<PaperOrder>>(`/paper/orders?${params}`);
  },
  submitOrder: (body: OrderSubmission) => api<PaperOrder>('/paper/orders', { method: 'POST', body: JSON.stringify(body) }),
  killSwitch: () => api<KillSwitchStatus>('/paper/kill-switch'),
  triggerKillSwitch: (reason: string) => api<KillSwitchStatus>('/paper/kill-switch', { method: 'POST', body: JSON.stringify({ reason }) }),
  resetKillSwitch: () => api<KillSwitchStatus>('/paper/kill-switch/reset', { method: 'POST' }),
  riskEvents: (offset = 0, eventType?: string, blocked?: boolean) => {
    const params = new URLSearchParams({ limit: '50', offset: String(offset) });
    if (eventType) params.set('event_type', eventType);
    if (blocked !== undefined) params.set('blocked', String(blocked));
    return api<PaperPagination<PaperRiskEvent>>(`/paper/risk-events?${params}`);
  },
};

export const market = { coverage: (offset = 0, filters: CoverageFilters = {}) => {
  const params = new URLSearchParams({ limit: '50', offset: String(offset) });
  for (const [key, value] of Object.entries(filters)) if (value) params.set(key, value);
  return api<MarketCoverage>(`/market/coverage?${params}`);
} };
export const research = {
  signals: (offset = 0) => api<Page<ResearchSignal>>(`/research/signals?limit=20&offset=${offset}`),
  evaluations: (offset = 0) => api<Page<ResearchEvaluation>>(`/research/evaluations?limit=20&offset=${offset}`),
  backtests: (offset = 0) => api<Page<ResearchReport>>(`/research/backtests?limit=20&offset=${offset}`),
  walkForwards: (offset = 0) => api<Page<ResearchReport>>(`/research/walk-forwards?limit=20&offset=${offset}`),
  rankings: (offset = 0, strategyId?: string, rejectedOnly = false) => {
    const params = new URLSearchParams({ limit: '50', offset: String(offset) });
    if (strategyId) params.set('strategy_id', strategyId);
    if (rejectedOnly) params.set('rejected_only', 'true');
    return api<RankingsPage>(`/research/rankings?${params}`);
  },
  latestRankings: (strategyId?: string) => {
    const params = new URLSearchParams();
    if (strategyId) params.set('strategy_id', strategyId);
    return api<{ total: number; items: CandidateRanking[] }>(`/research/rankings/latest?${params}`);
  },
  detail: (kind: ResearchReport['kind'], id: string) => api<ResearchReportDetail>(`/research/${kind === 'BACKTEST' ? 'backtests' : 'walk-forwards'}/${encodeURIComponent(id)}`),
};
export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/v1${path}`, { ...init, credentials: 'same-origin', headers: { 'Content-Type': 'application/json', ...init?.headers } });
  if (!response.ok) throw new Error(response.status === 401 ? 'Please sign in. Your session may have expired.' : `Request failed (${response.status}). Please retry.`);
  return response.json() as Promise<T>;
}
