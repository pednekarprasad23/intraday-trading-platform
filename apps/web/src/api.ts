export interface Instrument { id: string; canonical_symbol: string; display_name: string; asset_class: string; exchange: string; execution_enabled: boolean; demo: boolean }
export interface SystemStatus { version: string; environment: string; trading_mode: string; live_trading_enabled: boolean; market_data: string }
export interface ResearchMetrics { net_pnl: string; expectancy: string | null; win_rate: string | null; profit_factor: string | null; max_drawdown: string; longest_losing_streak: number; trade_count: number }
export interface ResearchSignal { id: string; instrument_id: string; strategy_version_id: string; decision_time: string; direction: string; quality: string; provider: string; demo: boolean; partition_id: string; partition_sha256: string; input_sha256: string; label: string }
export interface ResearchReport { id: string; kind: 'BACKTEST' | 'WALK_FORWARD'; fingerprint: string; instrument_id: string; provider: string; demo: boolean; timeframe: string; strategy_id: string; metrics: ResearchMetrics; warnings: string[]; created_at: string; label: string; fold_count?: number }
export interface ResearchEvaluation { id: string; decision_time: string | null; instrument_id: string; direction: string; quality: string; reasons: string[]; provider: string; demo: boolean; partition_sha256: string; strategy_id: string; label: string }
export interface Page<T> { total: number; items: T[] }
export const research = {
  signals: (offset = 0) => api<Page<ResearchSignal>>(`/research/signals?limit=20&offset=${offset}`),
  evaluations: (offset = 0) => api<Page<ResearchEvaluation>>(`/research/evaluations?limit=20&offset=${offset}`),
  backtests: (offset = 0) => api<Page<ResearchReport>>(`/research/backtests?limit=20&offset=${offset}`),
  walkForwards: (offset = 0) => api<Page<ResearchReport>>(`/research/walk-forwards?limit=20&offset=${offset}`),
};
export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/v1${path}`, { ...init, credentials: 'same-origin', headers: { 'Content-Type': 'application/json', ...init?.headers } });
  if (!response.ok) throw new Error(response.status === 401 ? 'Please sign in. Your session may have expired.' : `Request failed (${response.status}). Please retry.`);
  return response.json() as Promise<T>;
}
