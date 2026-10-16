/**
 * Flowmint AI — API Client
 *
 * Centralized HTTP client for backend communication.
 * Handles JWT token storage, refresh, and error standardization.
 */

const API_BASE = `${import.meta.env.VITE_API_URL || ''}/api/v1`;

interface ApiResponse<T> {
  success: boolean;
  data: T | null;
  meta?: { page: number; per_page: number; total: number; total_pages: number };
  errors?: { code: string; message: string; field?: string }[];
}

class ApiClient {
  private accessToken: string | null = null;

  constructor() {
    this.accessToken = localStorage.getItem('flowmint_access_token');
  }

  setToken(token: string) {
    this.accessToken = token;
    localStorage.setItem('flowmint_access_token', token);
  }

  setRefreshToken(token: string) {
    localStorage.setItem('flowmint_refresh_token', token);
  }

  clearTokens() {
    this.accessToken = null;
    localStorage.removeItem('flowmint_access_token');
    localStorage.removeItem('flowmint_refresh_token');
  }

  isAuthenticated(): boolean {
    return !!this.accessToken;
  }

  private async request<T>(
    method: string,
    path: string,
    body?: unknown,
    customHeaders?: Record<string, string>,
  ): Promise<ApiResponse<T>> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...customHeaders,
    };

    if (this.accessToken) {
      headers['Authorization'] = `Bearer ${this.accessToken}`;
    }

    const response = await fetch(`${API_BASE}${path}`, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
    });

    if (response.status === 204) {
      return { success: true, data: null };
    }

    const json = await response.json();

    if (!response.ok) {
      throw new ApiError(
        json.errors?.[0]?.message || 'Request failed',
        json.errors?.[0]?.code || 'UNKNOWN',
        response.status,
      );
    }

    return json;
  }

  get<T>(path: string, customHeaders?: Record<string, string>) { return this.request<T>('GET', path, undefined, customHeaders); }
  post<T>(path: string, body?: unknown, customHeaders?: Record<string, string>) { return this.request<T>('POST', path, body, customHeaders); }
  put<T>(path: string, body?: unknown, customHeaders?: Record<string, string>) { return this.request<T>('PUT', path, body, customHeaders); }
  patch<T>(path: string, body?: unknown, customHeaders?: Record<string, string>) { return this.request<T>('PATCH', path, body, customHeaders); }
  delete<T>(path: string, customHeaders?: Record<string, string>) { return this.request<T>('DELETE', path, undefined, customHeaders); }

  async upload<T>(path: string, formData: FormData): Promise<ApiResponse<T>> {
    const headers: Record<string, string> = {};
    if (this.accessToken) {
      headers['Authorization'] = `Bearer ${this.accessToken}`;
    }

    const response = await fetch(`${API_BASE}${path}`, {
      method: 'POST',
      headers,
      body: formData,
    });

    if (response.status === 204) {
      return { success: true, data: null };
    }

    const json = await response.json();

    if (!response.ok) {
      throw new ApiError(
        json.errors?.[0]?.message || 'Upload request failed',
        json.errors?.[0]?.code || 'UNKNOWN',
        response.status,
      );
    }

    return json;
  }
}

export class ApiError extends Error {
  code: string;
  status: number;

  constructor(message: string, code: string, status: number) {
    super(message);
    this.code = code;
    this.status = status;
  }
}

export const api = new ApiClient();
export type { ApiResponse };

import type { StoreConnection, OnboardingStatus, PaymentConfig, StoreSyncStatus } from '../types';

export const onboardingApi = {
  getStatus: () => api.get<OnboardingStatus>('/onboarding/status'),
  skip: () => api.post<OnboardingStatus>('/onboarding/skip'),
  setStep: (step: string) => api.post<OnboardingStatus>('/onboarding/step', { step }),
};

export const storeApi = {
  listConnections: () => api.get<StoreConnection[]>('/stores'),
  authorizeShopify: (shopDomain: string) =>
    api.post<{ authorization_url: string | null; state: string | null; configured: boolean; message: string | null }>(
      '/stores/shopify/authorize',
      { shop_domain: shopDomain }
    ),
  connectWooCommerce: (payload: { store_url: string; consumer_key: string; consumer_secret: string; store_name?: string }) =>
    api.post<StoreConnection>('/stores/woocommerce/connect', payload),
  generateCustomApiKey: (payload: { store_name: string; store_url: string }) =>
    api.post<{ api_key: string; connection_id: string; endpoint: string }>('/stores/custom/key', payload),
  syncCustomStore: (apiKey: string, payload: any) =>
    api.post<any>('/stores/custom/sync', payload, { 'X-Store-API-Key': apiKey }),
  triggerSync: (connectionId: string) =>
    api.post<StoreSyncStatus>(`/stores/${connectionId}/sync`),
  reconcile: (connectionId: string) =>
    api.post<StoreSyncStatus>(`/stores/${connectionId}/reconcile`),
  disconnect: (connectionId: string) =>
    api.post<{ success: boolean; message: string }>(`/stores/${connectionId}/disconnect`),
};

export const paymentApi = {
  getConfig: () => api.get<PaymentConfig>('/payments/config'),
  updateConfig: (payload: {
    payment_mode?: string;
    razorpay_key_id?: string;
    razorpay_key_secret?: string;
    razorpay_webhook_secret?: string;
    razorpay_mode?: 'test' | 'live';
  }) => api.post<PaymentConfig>('/payments/config', payload),
  verify: (payload: {
    payment_id: string;
    razorpay_order_id: string;
    razorpay_payment_id: string;
    razorpay_signature: string;
  }) => api.post<{ verified: boolean; payment_id: string; status: string; razorpay_payment_id: string }>('/payments/verify', payload),
};

