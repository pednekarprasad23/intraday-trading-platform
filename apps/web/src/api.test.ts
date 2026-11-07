import { afterEach, expect, it, vi } from 'vitest';
import { api, research } from './api';
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
it('reports service failures', async () => {
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('', {status:503}));
  await expect(api('/system/status')).rejects.toThrow('503');
});
