/**
 * Unit tests for Store Integration & Onboarding API Client.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { storeApi, onboardingApi, paymentApi, api } from '../lib/api';

describe('Store & Onboarding API Client', () => {
  beforeEach(() => {
    localStorage.clear();
    api.clearTokens();
    vi.restoreAllMocks();
  });

  it('calls getStatus and parses onboarding status correctly', async () => {
    const mockStatus = {
      onboarding_completed: false,
      store_connected: false,
      current_step: 1,
      platform: null,
      store_url: null,
      setup_mode: 'unconfigured',
    };

    const mockFetch = vi.fn().mockResolvedValue({
      status: 200,
      ok: true,
      json: async () => ({ success: true, data: mockStatus }),
    });
    globalThis.fetch = mockFetch;

    const res = await onboardingApi.getStatus();
    expect(res.success).toBe(true);
    expect(res.data).not.toBeNull();
    expect(res.data?.onboarding_completed).toBe(false);
    expect(res.data?.setup_mode).toBe('unconfigured');
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/onboarding/status'),
      expect.objectContaining({ method: 'GET' })
    );
  });

  it('calls skip and records manual setup fallback', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      status: 200,
      ok: true,
      json: async () => ({
        success: true,
        data: {
          onboarding_completed: true,
          store_connected: false,
          current_step: 2,
          setup_mode: 'manual',
        },
      }),
    });
    globalThis.fetch = mockFetch;

    const res = await onboardingApi.skip();
    expect(res.success).toBe(true);
    expect(res.data).not.toBeNull();
    expect(res.data?.setup_mode).toBe('manual');
    expect(res.data?.onboarding_completed).toBe(true);
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/onboarding/skip'),
      expect.objectContaining({ method: 'POST' })
    );
  });

  it('calls connectWooCommerce with secure credentials payload', async () => {
    const mockConnection = {
      id: 'conn-123',
      provider: 'woocommerce',
      store_url: 'https://mystore.example.com',
      status: 'connected',
      synced_products_count: 5,
    };

    const mockFetch = vi.fn().mockResolvedValue({
      status: 200,
      ok: true,
      json: async () => ({ success: true, data: mockConnection }),
    });
    globalThis.fetch = mockFetch;

    const res = await storeApi.connectWooCommerce({
      store_url: 'https://mystore.example.com',
      consumer_key: 'ck_test123',
      consumer_secret: 'cs_test456',
    });

    expect(res.success).toBe(true);
    expect(res.data).not.toBeNull();
    expect(res.data?.provider).toBe('woocommerce');
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/stores/woocommerce/connect'),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          store_url: 'https://mystore.example.com',
          consumer_key: 'ck_test123',
          consumer_secret: 'cs_test456',
        }),
      })
    );
  });

  it('calls generateCustomApiKey and syncCustomStore', async () => {
    const mockKeyData = {
      api_key: 'fma_test_key_abc',
      connection_id: 'conn-cust-1',
      endpoint: 'https://api.flowmint.ai/api/v1/stores/custom/sync',
    };

    const mockFetch = vi.fn().mockResolvedValue({
      status: 200,
      ok: true,
      json: async () => ({ success: true, data: mockKeyData }),
    });
    globalThis.fetch = mockFetch;

    const keyRes = await storeApi.generateCustomApiKey({
      store_name: 'FastAPI Store',
      store_url: 'https://store.example.com',
    });

    expect(keyRes.success).toBe(true);
    expect(keyRes.data).not.toBeNull();
    expect(keyRes.data?.api_key).toBe('fma_test_key_abc');
    expect(keyRes.data?.connection_id).toBe('conn-cust-1');
  });

  it('calls paymentApi.verify to authenticate Razorpay signature on server', async () => {
    const mockVerifyResult = {
      verified: true,
      payment_id: 'pay_local_123',
      status: 'captured',
      razorpay_payment_id: 'pay_rzp_456',
    };

    const mockFetch = vi.fn().mockResolvedValue({
      status: 200,
      ok: true,
      json: async () => ({ success: true, data: mockVerifyResult }),
    });
    globalThis.fetch = mockFetch;

    const res = await paymentApi.verify({
      payment_id: 'pay_local_123',
      razorpay_order_id: 'order_rzp_789',
      razorpay_payment_id: 'pay_rzp_456',
      razorpay_signature: 'hmac_sha256_sig',
    });

    expect(res.success).toBe(true);
    expect(res.data).not.toBeNull();
    expect(res.data?.verified).toBe(true);
    expect(res.data?.status).toBe('captured');
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/payments/verify'),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          payment_id: 'pay_local_123',
          razorpay_order_id: 'order_rzp_789',
          razorpay_payment_id: 'pay_rzp_456',
          razorpay_signature: 'hmac_sha256_sig',
        }),
      })
    );
  });
});
