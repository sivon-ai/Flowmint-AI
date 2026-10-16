/**
 * Unit tests for Frontend Customer API integration & data handling.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { api, ApiError } from '../lib/api';
import type { Customer, CustomerOrdersResponse } from '../types';

describe('Customer API & Data Integration', () => {
  beforeEach(() => {
    localStorage.clear();
    api.clearTokens();
    vi.restoreAllMocks();
  });

  it('fetches customer list with pagination and search query', async () => {
    api.setToken('test-token');

    const mockCustomers: Customer[] = [
      {
        id: 'cust-1',
        merchant_id: 'm-1',
        name: 'Aarav Patel',
        email: 'aarav@example.in',
        phone: '+91 98765 00001',
        order_count: 3,
        total_spent: 14500,
        created_at: '2026-10-01T10:00:00Z',
      },
    ];

    const mockFetch = vi.fn().mockResolvedValue({
      status: 200,
      ok: true,
      json: async () => ({
        success: true,
        data: mockCustomers,
        meta: { page: 1, per_page: 15, total: 1, total_pages: 1 },
      }),
    });
    globalThis.fetch = mockFetch;

    const res = await api.get<Customer[]>('/customers?page=1&per_page=15&q=aarav');
    expect(res.success).toBe(true);
    expect(res.data).toHaveLength(1);
    expect(res.data?.[0].name).toBe('Aarav Patel');
    expect(res.data?.[0].order_count).toBe(3);
    expect(res.data?.[0].total_spent).toBe(14500);

    const callUrl = mockFetch.mock.calls[0][0] as string;
    expect(callUrl).toContain('/api/v1/customers?page=1&per_page=15&q=aarav');
  });

  it('creates a new customer via POST /customers', async () => {
    api.setToken('test-token');

    const createdCustomer: Customer = {
      id: 'new-cust-123',
      merchant_id: 'm-1',
      name: 'Pooja Iyer',
      email: 'pooja@example.in',
      phone: '+91 99887 76655',
      order_count: 0,
      total_spent: 0,
      created_at: '2026-10-15T12:00:00Z',
    };

    const mockFetch = vi.fn().mockResolvedValue({
      status: 201,
      ok: true,
      json: async () => ({ success: true, data: createdCustomer }),
    });
    globalThis.fetch = mockFetch;

    const res = await api.post<Customer>('/customers', {
      name: 'Pooja Iyer',
      email: 'pooja@example.in',
      phone: '+91 99887 76655',
    });

    expect(res.success).toBe(true);
    expect(res.data?.id).toBe('new-cust-123');
    expect(res.data?.name).toBe('Pooja Iyer');
    expect(res.data?.order_count).toBe(0);
  });

  it('updates an existing customer via PATCH /customers/:id', async () => {
    api.setToken('test-token');

    const updatedCustomer: Customer = {
      id: 'cust-1',
      merchant_id: 'm-1',
      name: 'Aarav Patel (Updated)',
      email: 'aarav.patel@example.in',
      phone: '+91 98765 99999',
      order_count: 3,
      total_spent: 14500,
      created_at: '2026-10-01T10:00:00Z',
    };

    const mockFetch = vi.fn().mockResolvedValue({
      status: 200,
      ok: true,
      json: async () => ({ success: true, data: updatedCustomer }),
    });
    globalThis.fetch = mockFetch;

    const res = await api.patch<Customer>('/customers/cust-1', {
      name: 'Aarav Patel (Updated)',
      email: 'aarav.patel@example.in',
      phone: '+91 98765 99999',
    });

    expect(res.success).toBe(true);
    expect(res.data?.name).toBe('Aarav Patel (Updated)');
  });

  it('retrieves real customer orders and derived purchase summary', async () => {
    api.setToken('test-token');

    const ordersResponse: CustomerOrdersResponse = {
      customer_id: 'cust-1',
      summary: {
        total_orders: 2,
        total_spent: 8500,
        last_order_date: '2026-10-12T14:30:00Z',
        average_order_value: 4250,
      },
      orders: [
        {
          id: 'ord-1',
          merchant_id: 'm-1',
          customer_id: 'cust-1',
          cart_id: null,
          order_number: 'ORD-20261012-001',
          status: 'completed',
          subtotal: 5000,
          tax: 0,
          discount: 0,
          total: 5000,
          currency: 'INR',
          shipping_address: null,
          items: [],
          created_at: '2026-10-12T14:30:00Z',
        },
        {
          id: 'ord-2',
          merchant_id: 'm-1',
          customer_id: 'cust-1',
          cart_id: null,
          order_number: 'ORD-20261005-001',
          status: 'confirmed',
          subtotal: 3500,
          tax: 0,
          discount: 0,
          total: 3500,
          currency: 'INR',
          shipping_address: null,
          items: [],
          created_at: '2026-10-05T09:15:00Z',
        },
      ],
    };

    const mockFetch = vi.fn().mockResolvedValue({
      status: 200,
      ok: true,
      json: async () => ({ success: true, data: ordersResponse }),
    });
    globalThis.fetch = mockFetch;

    const res = await api.get<CustomerOrdersResponse>('/customers/cust-1/orders');
    expect(res.success).toBe(true);
    expect(res.data?.summary.total_orders).toBe(2);
    expect(res.data?.summary.total_spent).toBe(8500);
    expect(res.data?.summary.average_order_value).toBe(4250);
    expect(res.data?.orders).toHaveLength(2);
  });

  it('surfaces backend conflict errors when email is duplicate', async () => {
    api.setToken('test-token');

    const mockFetch = vi.fn().mockResolvedValue({
      status: 409,
      ok: false,
      json: async () => ({
        success: false,
        errors: [{ code: 'CONFLICT', message: "Customer with email 'exists@example.in' already exists" }],
      }),
    });
    globalThis.fetch = mockFetch;

    await expect(
      api.post('/customers', { name: 'Dup', email: 'exists@example.in' })
    ).rejects.toThrow(ApiError);
  });
});
