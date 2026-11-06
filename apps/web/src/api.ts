export interface Instrument { id: string; canonical_symbol: string; display_name: string; asset_class: string; exchange: string; execution_enabled: boolean; demo: boolean }
export interface SystemStatus { version: string; environment: string; trading_mode: string; live_trading_enabled: boolean; market_data: string }
export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/v1${path}`, { ...init, credentials: 'same-origin', headers: { 'Content-Type': 'application/json', ...init?.headers } });
  if (!response.ok) throw new Error(response.status === 401 ? 'Please sign in. Your session may have expired.' : `Request failed (${response.status}). Please retry.`);
  return response.json() as Promise<T>;
}
