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
  ): Promise<ApiResponse<T>> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
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

  get<T>(path: string) { return this.request<T>('GET', path); }
  post<T>(path: string, body?: unknown) { return this.request<T>('POST', path, body); }
  patch<T>(path: string, body?: unknown) { return this.request<T>('PATCH', path, body); }
  delete<T>(path: string) { return this.request<T>('DELETE', path); }
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
