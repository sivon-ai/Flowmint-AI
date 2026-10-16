import { describe, it, expect, beforeEach, vi } from 'vitest';
import '@testing-library/jest-dom';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider } from '../context/ThemeContext';
import DashboardLayout from '../components/layout/DashboardLayout';
import IntegrationsPage from '../pages/merchant/IntegrationsPage';
import DashboardPage from '../pages/merchant/DashboardPage';
import StorefrontPage from '../pages/buyer/StorefrontPage';
import { api } from '../lib/api';
import type { User, PaymentConfig, StoreConnection, Product } from '../types';

const mockUser: User = {
  id: 'usr-1',
  email: 'merchant@flowmint.test',
  full_name: 'Alex Merchant',
  role: 'owner',
  merchant_id: 'm-1',
  is_active: true,
};

describe('Merchant Navigation & Sidebar Structure', () => {
  beforeEach(() => {
    localStorage.clear();
    api.clearTokens();
    vi.restoreAllMocks();
  });

  it('organizes sidebar into the 4 requested merchant sections plus Judge walkthrough', () => {
    render(
      <ThemeProvider>
        <MemoryRouter initialEntries={['/dashboard']}>
          <DashboardLayout user={mockUser} onLogout={vi.fn()} />
        </MemoryRouter>
      </ThemeProvider>
    );

    // Verify Section Headers
    expect(screen.getByText('Demo Walkthrough')).toBeInTheDocument();
    expect(screen.getByText('Workspace')).toBeInTheDocument();
    expect(screen.getByText('Revenue Intelligence')).toBeInTheDocument();
    expect(screen.getByText('Governance & Observability')).toBeInTheDocument();
    expect(screen.getByText('Settings & Connections')).toBeInTheDocument();

    // Verify Workspace items
    expect(screen.getByRole('link', { name: /Dashboard/i })).toHaveAttribute('href', '/dashboard');
    expect(screen.getByRole('link', { name: /Products/i })).toHaveAttribute('href', '/products');
    expect(screen.getByRole('link', { name: /Inventory/i })).toHaveAttribute('href', '/inventory');
    expect(screen.getByRole('link', { name: /Orders/i })).toHaveAttribute('href', '/orders');
    expect(screen.getByRole('link', { name: /Customers/i })).toHaveAttribute('href', '/customers');

    // Verify Revenue Intelligence items
    expect(screen.getByRole('link', { name: /AI Copilot/i })).toHaveAttribute('href', '/copilot');
    expect(screen.getByRole('link', { name: /Opportunities/i })).toHaveAttribute('href', '/opportunities');
    expect(screen.getByRole('link', { name: /Simulations/i })).toHaveAttribute('href', '/simulations');
    expect(screen.getByRole('link', { name: /Attribution/i })).toHaveAttribute('href', '/attribution');

    // Verify Governance & Observability items
    expect(screen.getByRole('link', { name: /Approvals/i })).toHaveAttribute('href', '/approvals');
    expect(screen.getByRole('link', { name: /Policy Engine/i })).toHaveAttribute('href', '/policies');
    expect(screen.getByRole('link', { name: /Trace Viewer/i })).toHaveAttribute('href', '/traces');
    expect(screen.getByRole('link', { name: /AI Evaluation/i })).toHaveAttribute('href', '/evaluation');
    expect(screen.getByRole('link', { name: /Audit Trail/i })).toHaveAttribute('href', '/audit');

    // Verify Settings & Connections items
    expect(screen.getByRole('link', { name: /Integrations/i })).toHaveAttribute('href', '/integrations');

    // Verify Judge Walkthrough is separate demo entry
    expect(screen.getByRole('link', { name: /Judge Walkthrough/i })).toHaveAttribute('href', '/judge');
  });

  it('does NOT include Storefront as a permanent item in the merchant sidebar', () => {
    render(
      <ThemeProvider>
        <MemoryRouter initialEntries={['/dashboard']}>
          <DashboardLayout user={mockUser} onLogout={vi.fn()} />
        </MemoryRouter>
      </ThemeProvider>
    );

    const sidebarLinks = screen.getAllByRole('link');
    const storefrontSidebarLink = sidebarLinks.find(link => link.getAttribute('href') === '/store');
    expect(storefrontSidebarLink).toBeUndefined();
  });
});

describe('Preview Storefront Action on Integrations & Dashboard Pages', () => {
  beforeEach(() => {
    localStorage.clear();
    api.clearTokens();
    vi.restoreAllMocks();
  });

  it('renders Preview Storefront button on IntegrationsPage with correct link and button hierarchy', async () => {
    const mockConnections: StoreConnection[] = [
      {
        id: 'conn-1',
        merchant_id: 'm-1',
        provider: 'shopify',
        store_url: 'https://test-store.myshopify.com',
        store_name: 'test-store',
        external_store_id: 'sh_123',
        status: 'connected',
        scopes: 'read_products,write_products',
        sync_status: 'completed',
        last_sync_at: '2026-10-16T10:00:00Z',
        sync_summary: { products: 1 },
        last_error: null,
        disconnected_at: null,
        created_at: '2026-10-01T00:00:00Z',
        updated_at: '2026-10-16T10:00:00Z',
      },
    ];

    const mockPaymentConfig: PaymentConfig = {
      payment_mode: 'later',
      razorpay_configured: false,
      razorpay_key_id: null,
      razorpay_mode: 'test',
      webhook_url: 'https://api.flowmint.test/webhooks/razorpay',
    };

    globalThis.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/api/v1/stores')) {
        return Promise.resolve({
          status: 200,
          ok: true,
          json: async () => ({ success: true, data: mockConnections }),
        });
      }
      if (url.includes('/api/v1/payments/config')) {
        return Promise.resolve({
          status: 200,
          ok: true,
          json: async () => ({ success: true, data: mockPaymentConfig }),
        });
      }
      return Promise.resolve({
        status: 200,
        ok: true,
        json: async () => ({ success: true, data: {} }),
      });
    });

    render(
      <ThemeProvider>
        <MemoryRouter>
          <IntegrationsPage />
        </MemoryRouter>
      </ThemeProvider>
    );

    // 1. Check header actions: Preview Storefront & Connect Another Store
    const previewBtn = await screen.findByRole('link', { name: /Preview Storefront/i });
    expect(previewBtn).toBeInTheDocument();
    expect(previewBtn).toHaveAttribute('href', '/store');
    expect(previewBtn).toHaveAttribute('target', '_blank');
    expect(previewBtn.className).toContain('btn-secondary');

    const connectStoreBtn = screen.getByRole('link', { name: /Connect Another Store/i });
    expect(connectStoreBtn).toBeInTheDocument();
    expect(connectStoreBtn).toHaveAttribute('href', '/onboarding/connect-store');
    expect(connectStoreBtn.className).toContain('btn-primary');

    // 2. Check channel overview card displays honest deferred payment status
    expect(await screen.findByText('Flowmint Customer Storefront')).toBeInTheDocument();
    expect(screen.getByText('PREVIEW ONLY (CHECKOUT PENDING)')).toBeInTheDocument();
  });

  it('renders Preview Storefront quick action on DashboardPage', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      status: 200,
      ok: true,
      json: async () => ({
        success: true,
        data: {
          today_revenue: 0,
          revenue_change_pct: 0,
          active_opportunities: 0,
          pending_approvals: 0,
          low_stock_alerts: 0,
          health_score: 100,
          recent_activity: [],
        },
      }),
    });

    render(
      <ThemeProvider>
        <MemoryRouter>
          <DashboardPage />
        </MemoryRouter>
      </ThemeProvider>
    );

    const previewLink = screen.getByRole('link', { name: /Preview Storefront/i });
    expect(previewLink).toBeInTheDocument();
    expect(previewLink).toHaveAttribute('href', '/store');
    expect(previewLink).toHaveAttribute('target', '_blank');
  });
});

describe('Storefront Page Behavior & Commerce Configuration Respect', () => {
  const mockProducts: Product[] = [
    {
      id: 'prod-1',
      merchant_id: 'm-1',
      category_id: null,
      name: 'Wireless Ergonomic Keyboard',
      slug: 'wireless-ergonomic-keyboard',
      description: 'Comfortable split keyboard with mechanical tactile switches',
      sku: 'KB-SPLIT-01',
      price: 6499,
      compare_at_price: 7999,
      currency: 'INR',
      status: 'active',
      image_url: null,
      attributes: [],
      inventory: {
        quantity: 14,
        reserved: 0,
        available: 14,
        is_low_stock: false,
        is_in_stock: true,
      },
      created_at: '2026-10-01T00:00:00Z',
      updated_at: '2026-10-01T00:00:00Z',
    },
  ];

  beforeEach(() => {
    localStorage.clear();
    api.clearTokens();
    vi.restoreAllMocks();
  });

  it('provides a Return to Dashboard link when authenticated merchant opens preview', async () => {
    api.setToken('valid-merchant-token');

    globalThis.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/products')) {
        return Promise.resolve({
          status: 200,
          ok: true,
          json: async () => ({ success: true, data: mockProducts }),
        });
      }
      if (url.includes('/payments/config')) {
        return Promise.resolve({
          status: 200,
          ok: true,
          json: async () => ({
            success: true,
            data: {
              payment_mode: 'later',
              razorpay_configured: false,
              razorpay_key_id: null,
              razorpay_mode: 'test',
              webhook_url: 'https://api.flowmint.test/webhooks/razorpay',
            },
          }),
        });
      }
      if (url.includes('/stores')) {
        return Promise.resolve({
          status: 200,
          ok: true,
          json: async () => ({ success: true, data: [] }),
        });
      }
      return Promise.resolve({
        status: 200,
        ok: true,
        json: async () => ({ success: true, data: {} }),
      });
    });

    render(
      <ThemeProvider>
        <MemoryRouter>
          <StorefrontPage />
        </MemoryRouter>
      </ThemeProvider>
    );

    // Check Return to Dashboard link is present
    const backBtn = await screen.findByRole('link', { name: /Return to Dashboard/i });
    expect(backBtn).toBeInTheDocument();
    expect(backBtn).toHaveAttribute('href', '/dashboard');

    // Check preview banner is displayed with truthful payment status
    expect(await screen.findByText('Storefront Preview')).toBeInTheDocument();
    expect(
      screen.getByText(/Purchasing & checkout are/i)
    ).toBeInTheDocument();
    expect(screen.getByText(/unavailable/i)).toBeInTheDocument();
  });

  it('disables checkout and displays honest messaging when payment configuration is Later', async () => {
    api.setToken('valid-merchant-token');

    globalThis.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/products')) {
        return Promise.resolve({
          status: 200,
          ok: true,
          json: async () => ({ success: true, data: mockProducts }),
        });
      }
      if (url.includes('/payments/config')) {
        return Promise.resolve({
          status: 200,
          ok: true,
          json: async () => ({
            success: true,
            data: {
              payment_mode: 'later',
              razorpay_configured: false,
              razorpay_key_id: null,
              razorpay_mode: 'test',
              webhook_url: 'https://api.flowmint.test/webhooks/razorpay',
            },
          }),
        });
      }
      if (url.includes('/stores')) {
        return Promise.resolve({
          status: 200,
          ok: true,
          json: async () => ({ success: true, data: [] }),
        });
      }
      return Promise.resolve({
        status: 200,
        ok: true,
        json: async () => ({ success: true, data: {} }),
      });
    });

    render(
      <ThemeProvider>
        <MemoryRouter>
          <StorefrontPage />
        </MemoryRouter>
      </ThemeProvider>
    );

    // Wait for product to load
    expect(await screen.findByText('Wireless Ergonomic Keyboard')).toBeInTheDocument();

    // Click "Buy Now" on the product
    const buyNowBtn = screen.getByRole('button', { name: /Buy Now/i });
    fireEvent.click(buyNowBtn);

    // Modal should open
    expect(await screen.findByText('Flowmint Store Checkout')).toBeInTheDocument();

    // Honest alert message should be visible
    expect(screen.getByText('Checkout Unavailable in Preview Mode')).toBeInTheDocument();
    expect(screen.getByText(/Payment configuration was set to/i)).toBeInTheDocument();

    // Action button should state "Checkout Unavailable" and be disabled
    const payBtn = screen.getByRole('button', { name: /Checkout Unavailable/i });
    expect(payBtn).toBeDisabled();

    // Link to configure payments in Integrations should be present
    const configLink = screen.getByRole('link', { name: /Configure Payments in Integrations/i });
    expect(configLink).toHaveAttribute('href', '/integrations');
  });
});
