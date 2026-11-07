import { afterEach, expect, it, vi } from 'vitest';
import { api, market, research } from './api';
afterEach(() => vi.restoreAllMocks());
it('uses same-origin credentials and returns parsed data', async () => {
  const fetcher = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({status:'ok'})));
  expect(await api('/health/live')).toEqual({status:'ok'});
  expect(fetcher).toHaveBeenCalledWith('/api/v1/health/live', expect.objectContaining({credentials:'same-origin'}));
});
it('reports session expiry without returning protected data', async () => {
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('', {status:401}));
  await expect(api('/instruments')).rejects.toThrow('session may have expired');
});
it('loads bounded read-only research pages with same-origin credentials', async () => {
  const fetcher = vi.spyOn(globalThis, 'fetch').mockImplementation(async () => new Response(JSON.stringify({ total: 0, items: [] })));
  expect(await research.signals(20)).toEqual({ total: 0, items: [] });
  expect(await research.backtests()).toEqual({ total: 0, items: [] });
  expect(await research.walkForwards()).toEqual({ total: 0, items: [] });
  expect(fetcher.mock.calls.map(call => call[0])).toEqual([
    '/api/v1/research/signals?limit=20&offset=20',
    '/api/v1/research/backtests?limit=20&offset=0',
    '/api/v1/research/walk-forwards?limit=20&offset=0',
  ]);
  expect(fetcher.mock.calls.every(call => (call[1] as RequestInit).credentials === 'same-origin')).toBe(true);
});
it('loads a read-only report detail by kind and identifier', async () => {
  const fetcher = vi.spyOn(globalThis, 'fetch').mockImplementation(async () => new Response(JSON.stringify({ fingerprint: 'abc', sources: [] })));
  expect(await research.detail('BACKTEST', 'report-id')).toMatchObject({ fingerprint: 'abc' });
  expect(await research.detail('WALK_FORWARD', 'report-id')).toMatchObject({ sources: [] });
  expect(fetcher.mock.calls.map(call => call[0])).toEqual([
    '/api/v1/research/backtests/report-id',
    '/api/v1/research/walk-forwards/report-id',
  ]);
});
it('loads bounded market coverage without implying a live quote', async () => {
  const fetcher = vi.spyOn(globalThis, 'fetch').mockImplementation(async () => new Response(JSON.stringify({ total: 0, items: [], live_feed_status: 'unavailable', observed_at: '2026-11-08T00:00:00Z' })));
  expect(await market.coverage(50, { provider: 'DHAN', historical: 'true' })).toMatchObject({ total: 0, live_feed_status: 'unavailable' });
  expect(fetcher).toHaveBeenCalledWith('/api/v1/market/coverage?limit=50&offset=50&provider=DHAN&historical=true', expect.objectContaining({ credentials: 'same-origin' }));
});
it('reports service failures', async () => {
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('', {status:503}));
  await expect(api('/system/status')).rejects.toThrow('503');
});
