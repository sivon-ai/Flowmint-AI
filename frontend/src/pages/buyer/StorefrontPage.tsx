import { useState, useEffect } from 'react';
import { api } from '../../lib/api';
import type { Product, AgentChatResponse } from '../../types';
import {
  Search,
  ShoppingBag,
  Zap,
  Sparkles,
  Bot,
  CheckCircle2,
  AlertCircle,
  Tag,
  ArrowRight,
  Filter,
  CreditCard,
  RefreshCw,
} from 'lucide-react';

const SUGGESTED_QUERIES = [
  'Laptops under ₹70,000',
  'Wireless earbuds with active noise cancellation',
  'Mechanical keyboards',
  'Products in stock under ₹5,000',
];

export default function StorefrontPage() {
  const [searchQuery, setSearchQuery] = useState('');
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(false);
  const [aiResponse, setAiResponse] = useState<string | null>(null);
  const [aiTraceId, setAiTraceId] = useState<string | null>(null);
  const [searched, setSearched] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Razorpay Checkout State
  const [checkoutProduct, setCheckoutProduct] = useState<Product | null>(null);
  const [checkoutQty, setCheckoutQty] = useState(1);
  const [buyerName, setBuyerName] = useState('Jane Doe');
  const [buyerEmail, setBuyerEmail] = useState('buyer@example.com');
  const [isCheckingOut, setIsCheckingOut] = useState(false);
  const [checkoutError, setCheckoutError] = useState<string | null>(null);
  const [paymentSuccess, setPaymentSuccess] = useState<any>(null);

  const handleBuyNow = (p: Product) => {
    setCheckoutProduct(p);
    setCheckoutQty(1);
    setCheckoutError(null);
    setPaymentSuccess(null);
  };

  const loadRazorpayScript = (): Promise<boolean> => {
    return new Promise(resolve => {
      if ((window as any).Razorpay) {
        resolve(true);
        return;
      }
      const script = document.createElement('script');
      script.src = 'https://checkout.razorpay.com/v1/checkout.js';
      script.onload = () => resolve(true);
      script.onerror = () => resolve(false);
      document.body.appendChild(script);
    });
  };

  const handleExecuteCheckout = async () => {
    if (!checkoutProduct) return;
    setIsCheckingOut(true);
    setCheckoutError(null);

    try {
      if (!api.isAuthenticated()) {
        throw new Error('Please sign in or use the Merchant Portal to complete purchases in development mode.');
      }

      // 1. Create Cart
      const cartRes = await api.post<{ id: string }>('/carts', { customer_id: null });
      if (!cartRes.data?.id) throw new Error('Failed to create shopping cart');
      const cartId = cartRes.data.id;

      // 2. Add Item
      await api.post(`/carts/${cartId}/items`, {
        product_id: checkoutProduct.id,
        quantity: checkoutQty,
      });

      // 3. Create Order
      const orderRes = await api.post<{ id: string; order_number: string }>('/orders', {
        cart_id: cartId,
      });
      if (!orderRes.data?.id) throw new Error('Failed to generate order from cart');
      const orderId = orderRes.data.id;

      // 4. Initiate Razorpay Order on Backend
      const payRes = await api.post<any>(`/payments/${orderId}/initiate`);
      if (!payRes.data?.razorpay_order_id) {
        throw new Error('Backend failed to create Razorpay order');
      }

      const { payment_id, razorpay_order_id, razorpay_key_id, amount, currency, order_number } = payRes.data;

      // 5. Load SDK & open checkout modal
      const loaded = await loadRazorpayScript();
      if (!loaded) {
        throw new Error('Failed to load Razorpay Checkout SDK. Check your internet connection.');
      }

      const options = {
        key: razorpay_key_id,
        amount: amount,
        currency: currency,
        name: 'Flowmint Store',
        description: `Order ${order_number}`,
        order_id: razorpay_order_id,
        prefill: {
          name: buyerName,
          email: buyerEmail,
        },
        theme: {
          color: '#8B5E3C',
        },
        handler: async function (response: any) {
          try {
            // 6. Verify signature on server
            const verifyRes = await api.post<any>('/payments/verify', {
              payment_id: payment_id,
              razorpay_order_id: response.razorpay_order_id,
              razorpay_payment_id: response.razorpay_payment_id,
              razorpay_signature: response.razorpay_signature,
            });
            if (verifyRes.data) {
              setPaymentSuccess(verifyRes.data);
            }
          } catch (vErr: any) {
            setCheckoutError(vErr.message || 'Payment signature verification failed.');
          } finally {
            setIsCheckingOut(false);
          }
        },
        modal: {
          ondismiss: function () {
            setIsCheckingOut(false);
          },
        },
      };

      const rzp = new (window as any).Razorpay(options);
      rzp.on('payment.failed', function (resp: any) {
        setCheckoutError(resp.error?.description || 'Payment failed.');
        setIsCheckingOut(false);
      });
      rzp.open();
    } catch (err: any) {
      setCheckoutError(err.message || 'Checkout error occurred.');
      setIsCheckingOut(false);
    }
  };

  // Load initial catalog
  useEffect(() => {
    loadFeaturedProducts();
  }, []);

  const loadFeaturedProducts = async () => {
    try {
      const endpoint = api.isAuthenticated() ? '/products?per_page=8' : '/products/public?per_page=8';
      const res = await api.get<Product[]>(endpoint);
      if (res.data) {
        setProducts(res.data);
      }
    } catch (e) {
      console.error('Failed to load catalog', e);
    }
  };

  const handleSearch = async (queryText?: string) => {
    const q = (queryText || searchQuery).trim();
    if (!q || loading) return;

    if (queryText) setSearchQuery(queryText);
    setLoading(true);
    setErrorMsg(null);
    setSearched(true);
    setAiResponse(null);
    setAiTraceId(null);

    try {
      // If user is authenticated, query Buyer Agent directly for grounded reasoning + tool search
      if (api.isAuthenticated()) {
        const res = await api.post<AgentChatResponse>('/agents/buyer', {
          message: q,
        });

        if (res.data) {
          setAiResponse(res.data.response);
          setAiTraceId(res.data.trace_id);
          // If structured products list was returned by search_products tool
          if (Array.isArray(res.data.structured_data)) {
            // Map structured tool results to Product items
            const mapped = res.data.structured_data.map((item: any) => ({
              id: item.id,
              merchant_id: '',
              category_id: null,
              name: item.name,
              slug: item.sku?.toLowerCase() || 'prod',
              description: item.description,
              sku: item.sku,
              price: item.price,
              compare_at_price: null,
              currency: item.currency || 'INR',
              status: 'active' as const,
              image_url: null,
              attributes: [],
              inventory: {
                quantity: item.stock_quantity,
                reserved: 0,
                available: item.stock_quantity,
                is_low_stock: item.stock_quantity < 5,
                is_in_stock: item.in_stock,
              },
              created_at: new Date().toISOString(),
              updated_at: new Date().toISOString(),
            }));
            setProducts(mapped);
          } else {
            // Fallback to lexical catalog search
            const catRes = await api.get<Product[]>(`/products?q=${encodeURIComponent(q)}`);
            if (catRes.data) setProducts(catRes.data);
          }
        }
      } else {
        // Unauthenticated search: public product catalog search
        const res = await api.get<Product[]>(`/products/public?q=${encodeURIComponent(q)}`);
        if (res.data) {
          setProducts(res.data);
        }
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Search failed. Please try a different query.');
    } finally {
      setLoading(false);
    }
  };

  const formatCurrency = (val: number, currency: string = 'INR') =>
    new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: currency || 'INR',
      maximumFractionDigits: 0,
    }).format(val);

  return (
    <div className="min-h-screen bg-surface-950">
      {/* Header */}
      <header className="border-b border-surface-700/50 bg-surface-900/80 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Zap className="w-5 h-5 text-brand-400" />
            <span className="text-lg font-bold text-white tracking-tight">Flowmint Store</span>
            <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-brand-500/10 text-brand-400 border border-brand-500/20 ml-2">
              Buyer AI
            </span>
          </div>

          <div className="flex items-center gap-3">
            <a href="/dashboard" className="text-xs text-surface-300 hover:text-white transition-colors">
              Merchant Portal
            </a>
            <button className="btn-secondary flex items-center gap-2 text-xs py-2">
              <ShoppingBag className="w-4 h-4" />
              <span>Cart (0)</span>
            </button>
          </div>
        </div>
      </header>

      {/* Hero Search Section */}
      <section className="py-14 px-6 border-b border-surface-800/60 bg-gradient-to-b from-surface-900/40 to-surface-950">
        <div className="max-w-3xl mx-auto text-center">
          <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-brand-600/10 border border-brand-500/20 text-brand-400 text-xs font-medium mb-5">
            <Sparkles className="w-3.5 h-3.5" />
            Grounded Autonomous Commerce
          </div>
          <h1 className="text-4xl sm:text-5xl font-bold text-white tracking-tight leading-tight">
            Discover Products with{' '}
            <span className="bg-gradient-to-r from-brand-400 to-brand-600 bg-clip-text text-transparent">
              Buyer AI
            </span>
          </h1>
          <p className="text-surface-300 text-sm sm:text-base mt-3 max-w-xl mx-auto">
            Natural language product discovery powered by verified catalog tools, live stock checks,
            and grounded catalog results.
          </p>

          {/* Search Box */}
          <form
            onSubmit={e => {
              e.preventDefault();
              handleSearch();
            }}
            className="mt-8 relative max-w-2xl mx-auto"
          >
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-surface-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              placeholder='Try: "Ultrabook laptop under ₹70,000" or "Wireless earbuds"'
              className="input-field w-full pl-12 pr-28 py-3.5 text-sm sm:text-base rounded-2xl shadow-xl border-surface-700/80 focus:border-brand-500"
            />
            <button
              type="submit"
              disabled={loading || !searchQuery.trim()}
              className="absolute right-2 top-1/2 -translate-y-1/2 btn-primary py-2 px-4 rounded-xl text-xs flex items-center gap-1.5 disabled:opacity-50"
            >
              {loading ? (
                <>
                  <Bot className="w-3.5 h-3.5 animate-spin" />
                  <span>Searching</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-3.5 h-3.5" />
                  <span>Search</span>
                </>
              )}
            </button>
          </form>

          {/* Suggested Queries */}
          <div className="flex flex-wrap items-center justify-center gap-2 mt-4">
            <span className="text-xs text-surface-400 flex items-center gap-1">
              <Filter className="w-3 h-3" /> Quick suggestions:
            </span>
            {SUGGESTED_QUERIES.map(q => (
              <button
                key={q}
                onClick={() => handleSearch(q)}
                className="text-xs px-2.5 py-1 rounded-full bg-surface-900 border border-surface-700/60 text-surface-300 hover:text-white hover:border-brand-500/50 transition-colors"
              >
                {q}
              </button>
            ))}
          </div>
        </div>
      </section>

      {/* Main Content Area */}
      <main className="max-w-6xl mx-auto px-6 py-10 space-y-8">
        {/* Error Alert */}
        {errorMsg && (
          <div className="p-4 bg-red-950/40 border border-red-800/40 rounded-xl flex items-center gap-3 text-sm text-red-300">
            <AlertCircle className="w-5 h-5 flex-shrink-0" />
            <span>{errorMsg}</span>
          </div>
        )}

        {/* AI Explanation / Reasoning Card */}
        {aiResponse && (
          <div className="card p-5 border-brand-500/30 bg-brand-950/10 space-y-3 animate-fade-in">
            <div className="flex items-center justify-between text-xs pb-2 border-b border-surface-700/40">
              <div className="flex items-center gap-2 text-brand-400 font-semibold">
                <Bot className="w-4 h-4" />
                Buyer Agent Recommendation
              </div>
              {aiTraceId && (
                <span className="font-mono text-[10px] text-surface-400">
                  Trace: {aiTraceId}
                </span>
              )}
            </div>
            <div className="text-sm text-surface-200 leading-relaxed whitespace-pre-wrap">
              {aiResponse}
            </div>
          </div>
        )}

        {/* Product Catalog Grid */}
        <section>
          <div className="flex items-center justify-between mb-6">
            <div>
              <h2 className="text-xl font-bold text-white">
                {searched ? 'Search Results' : 'Catalog Products'}
              </h2>
              <p className="text-xs text-surface-400 mt-0.5">
                {products.length} {products.length === 1 ? 'item' : 'items'} available
              </p>
            </div>
            {searched && (
              <button
                onClick={() => {
                  setSearched(false);
                  setSearchQuery('');
                  setAiResponse(null);
                  loadFeaturedProducts();
                }}
                className="text-xs text-brand-400 hover:underline"
              >
                Reset catalog
              </button>
            )}
          </div>

          {products.length === 0 ? (
            <div className="card p-12 text-center space-y-3">
              <ShoppingBag className="w-10 h-10 text-surface-500 mx-auto" />
              <h3 className="text-base font-semibold text-white">No products found</h3>
              <p className="text-xs text-surface-400 max-w-sm mx-auto">
                No catalog items matched your query. Try broadening your keywords or clearing
                budget constraints.
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-5">
              {products.map(p => {
                const available = p.inventory?.available ?? 0;
                const inStock = available > 0;

                return (
                  <div
                    key={p.id}
                    className="card-hover p-4 flex flex-col justify-between group transition-all"
                  >
                    <div>
                      {/* Placeholder Image / Icon */}
                      <div className="aspect-square bg-surface-900 border border-surface-800 rounded-xl mb-3 flex items-center justify-center relative overflow-hidden group-hover:border-brand-500/30 transition-colors">
                        <ShoppingBag className="w-10 h-10 text-surface-600 group-hover:text-brand-400 transition-colors" />
                        {/* Stock Tag */}
                        <div className="absolute top-2.5 right-2.5">
                          {inStock ? (
                            <span className="badge-success text-[10px] px-2 py-0.5 flex items-center gap-1">
                              <CheckCircle2 className="w-3 h-3" />
                              {available} In Stock
                            </span>
                          ) : (
                            <span className="badge-danger text-[10px] px-2 py-0.5">
                              Out of Stock
                            </span>
                          )}
                        </div>
                      </div>

                      {/* Title & SKU */}
                      <div className="space-y-1">
                        <h3 className="text-sm font-semibold text-white group-hover:text-brand-300 transition-colors line-clamp-1">
                          {p.name}
                        </h3>
                        <div className="flex items-center gap-1.5 text-[11px] text-surface-400 font-mono">
                          <Tag className="w-3 h-3" />
                          <span>{p.sku}</span>
                        </div>
                        {p.description && (
                          <p className="text-xs text-surface-400 line-clamp-2 mt-1">
                            {p.description}
                          </p>
                        )}
                      </div>
                    </div>

                    {/* Price and Action */}
                    <div className="mt-4 pt-3 border-t border-surface-700/40 flex items-center justify-between">
                      <div>
                        <div className="text-xs text-surface-400">Price</div>
                        <div className="text-base font-bold text-white">
                          {formatCurrency(p.price, p.currency)}
                        </div>
                      </div>

                      <div className="flex items-center gap-2">
                        <button
                          disabled={!inStock}
                          onClick={() => handleBuyNow(p)}
                          className="btn-primary py-1.5 px-3 text-xs flex items-center gap-1 disabled:opacity-40"
                        >
                          <span>Buy Now</span>
                          <ArrowRight className="w-3 h-3" />
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </section>
      </main>

      {/* Razorpay Checkout Modal */}
      {checkoutProduct && (
        <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="card p-6 sm:p-8 max-w-lg w-full space-y-6 animate-scale-up border-brand-500/40">
            {/* Header */}
            <div className="flex items-center justify-between pb-4 border-b border-surface-700/60">
              <div className="flex items-center gap-2.5">
                <div className="p-2 bg-brand-500/15 rounded-lg border border-brand-400/25">
                  <CreditCard className="w-5 h-5 text-brand-400" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-white">Flowmint Store Checkout</h3>
                  <div className="text-xs text-surface-400 flex items-center gap-1.5">
                    <span>Razorpay Standard Checkout</span>
                    <span className="badge-warning text-[10px] px-1.5 py-0.2">Test Mode</span>
                  </div>
                </div>
              </div>
              <button
                onClick={() => { setCheckoutProduct(null); setPaymentSuccess(null); }}
                className="text-surface-400 hover:text-white text-sm"
              >
                ✕
              </button>
            </div>

            {paymentSuccess ? (
              <div className="space-y-5 text-center py-4 animate-fade-in">
                <div className="w-14 h-14 mx-auto rounded-full bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center text-emerald-400">
                  <CheckCircle2 className="w-8 h-8" />
                </div>
                <div className="space-y-1">
                  <h4 className="text-xl font-bold text-white">Payment Verified &amp; Confirmed!</h4>
                  <p className="text-xs text-surface-300">
                    Your order was successfully paid and verified using server-side HMAC-SHA256 signature verification.
                  </p>
                </div>

                <div className="p-4 bg-surface-900 rounded-xl border border-surface-700/70 text-left text-xs space-y-2 font-mono">
                  <div className="flex justify-between">
                    <span className="text-surface-400">Payment ID:</span>
                    <span className="text-emerald-300">{paymentSuccess.payment_id}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-surface-400">Status:</span>
                    <span className="text-emerald-400 font-bold uppercase">{paymentSuccess.status}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-surface-400">Amount Paid:</span>
                    <span className="text-white font-bold">{formatCurrency(paymentSuccess.amount, paymentSuccess.currency)}</span>
                  </div>
                </div>

                <button
                  onClick={() => { setCheckoutProduct(null); setPaymentSuccess(null); }}
                  className="btn-primary w-full py-2.5 text-xs font-semibold"
                >
                  Return to Storefront
                </button>
              </div>
            ) : (
              <div className="space-y-5">
                {checkoutError && (
                  <div className="p-3 bg-danger-500/10 border border-danger-500/30 rounded-lg text-xs text-danger-300 flex items-center gap-2">
                    <AlertCircle className="w-4 h-4 flex-shrink-0" />
                    <span>{checkoutError}</span>
                  </div>
                )}

                {/* Product Summary */}
                <div className="p-4 bg-surface-900 rounded-xl border border-surface-700/60 flex items-center justify-between">
                  <div>
                    <h4 className="text-sm font-semibold text-white">{checkoutProduct.name}</h4>
                    <span className="text-xs font-mono text-surface-400">SKU: {checkoutProduct.sku}</span>
                  </div>
                  <div className="text-right">
                    <div className="text-sm font-bold text-white">
                      {formatCurrency(checkoutProduct.price, checkoutProduct.currency)}
                    </div>
                    <span className="text-[11px] text-surface-400">Qty: {checkoutQty}</span>
                  </div>
                </div>

                {/* Buyer Information Form */}
                <div className="space-y-3">
                  <div>
                    <label className="block text-xs font-medium text-surface-300 mb-1">
                      Buyer Full Name
                    </label>
                    <input
                      type="text"
                      value={buyerName}
                      onChange={e => setBuyerName(e.target.value)}
                      placeholder="Jane Doe"
                      className="input-field w-full text-xs"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-medium text-surface-300 mb-1">
                      Email Address
                    </label>
                    <input
                      type="email"
                      value={buyerEmail}
                      onChange={e => setBuyerEmail(e.target.value)}
                      placeholder="buyer@example.com"
                      className="input-field w-full text-xs"
                    />
                  </div>
                </div>

                {/* Total Calculation */}
                <div className="pt-3 border-t border-surface-700/60 space-y-1.5 text-xs">
                  <div className="flex justify-between text-surface-400">
                    <span>Subtotal</span>
                    <span>{formatCurrency(checkoutProduct.price * checkoutQty, checkoutProduct.currency)}</span>
                  </div>
                  <div className="flex justify-between text-surface-400">
                    <span>Estimated Tax</span>
                    <span>₹0.00</span>
                  </div>
                  <div className="flex justify-between text-sm font-bold text-white pt-1 border-t border-surface-800">
                    <span>Total Amount</span>
                    <span className="text-brand-400">
                      {formatCurrency(checkoutProduct.price * checkoutQty, checkoutProduct.currency)}
                    </span>
                  </div>
                </div>

                {/* Action Buttons */}
                <div className="flex items-center justify-end gap-3 pt-2">
                  <button
                    type="button"
                    onClick={() => setCheckoutProduct(null)}
                    className="btn-secondary text-xs px-4 py-2"
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    disabled={isCheckingOut}
                    onClick={handleExecuteCheckout}
                    className="btn-primary text-xs px-5 py-2.5 flex items-center gap-2"
                  >
                    {isCheckingOut ? (
                      <>
                        <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                        <span>Opening Razorpay...</span>
                      </>
                    ) : (
                      <>
                        <CreditCard className="w-3.5 h-3.5" />
                        <span>Pay with Razorpay</span>
                      </>
                    )}
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
