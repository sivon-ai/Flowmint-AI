/**
 * Unit tests for Frontend API Client.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { api, ApiError } from '../lib/api';

describe('ApiClient', () => {
  beforeEach(() => {
    localStorage.clear();
    api.clearTokens();
    vi.restoreAllMocks();
  });

  it('manages authentication tokens in localStorage', () => {
    expect(api.isAuthenticated()).toBe(false);

    api.setToken('test-access-token');
    api.setRefreshToken('test-refresh-token');

    expect(api.isAuthenticated()).toBe(true);
    expect(localStorage.getItem('flowmint_access_token')).toBe('test-access-token');
    expect(localStorage.getItem('flowmint_refresh_token')).toBe('test-refresh-token');

    api.clearTokens();
    expect(api.isAuthenticated()).toBe(false);
    expect(localStorage.getItem('flowmint_access_token')).toBeNull();
  });

  it('attaches Authorization header when token is present', async () => {
    api.setToken('auth-bearer-token');

    const mockFetch = vi.fn().mockResolvedValue({
      status: 200,
      ok: true,
      json: async () => ({ success: true, data: { id: '123' } }),
    });
    globalThis.fetch = mockFetch;

    const res = await api.get('/products');
    expect(res.success).toBe(true);
    expect(mockFetch).toHaveBeenCalledTimes(1);

    const callArgs = mockFetch.mock.calls[0];
    expect(callArgs[1].headers['Authorization']).toBe('Bearer auth-bearer-token');
    expect(callArgs[1].headers['Content-Type']).toBe('application/json');
  });

  it('handles 204 No Content responses cleanly', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      status: 204,
      ok: true,
    });
    globalThis.fetch = mockFetch;

    const res = await api.delete('/products/123');
    expect(res.success).toBe(true);
    expect(res.data).toBeNull();
  });

  it('throws ApiError with code and status on HTTP errors', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      status: 404,
      ok: false,
      json: async () => ({
        success: false,
        errors: [{ code: 'NOT_FOUND', message: 'Product not found' }],
      }),
    });
    globalThis.fetch = mockFetch;

    await expect(api.get('/products/999')).rejects.toThrow(ApiError);
  });
});
