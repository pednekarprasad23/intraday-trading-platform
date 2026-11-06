import { afterEach, expect, it, vi } from 'vitest';
import { api } from './api';
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
it('reports service failures', async () => {
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('', {status:503}));
  await expect(api('/system/status')).rejects.toThrow('503');
});
