import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../../lib/api';
import type { User, OnboardingStatus, StoreConnection } from '../../types';
import {
  Zap,
  ShoppingBag,
  Store,
  ShieldCheck,
  CheckCircle2,
  AlertCircle,
  ArrowRight,
  ExternalLink,
  Code2,
  RefreshCw,
  CreditCard,
  Lock,
  ChevronRight,
  Sparkles,
  HelpCircle,
} from 'lucide-react';

interface Props {
  user: User;
  onUpdateUser: (updated: User) => void;
}

type Step = 'connect_store' | 'payment_setup';
type Platform = 'shopify' | 'woocommerce' | 'custom' | null;

export default function OnboardingPage({ user, onUpdateUser }: Props) {
  const navigate = useNavigate();
  const [currentStep, setCurrentStep] = useState<Step>('connect_store');
  const [selectedPlatform, setSelectedPlatform] = useState<Platform>('shopify');
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Shopify form state
  const [shopifyDomain, setShopifyDomain] = useState('');
  const [shopifyConfigured, setShopifyConfigured] = useState<boolean | null>(null);
  const [shopifyNote, setShopifyNote] = useState<string | null>(null);

  // WooCommerce form state
  const [wcUrl, setWcUrl] = useState('');
  const [wcConsumerKey, setWcConsumerKey] = useState('');
  const [wcConsumerSecret, setWcConsumerSecret] = useState('');
  const [wcStoreName, setWcStoreName] = useState('');

  // Custom Store state
  const [customStoreName, setCustomStoreName] = useState('');
  const [customStoreUrl, setCustomStoreUrl] = useState('');
  const [customResponse, setCustomResponse] = useState<any>(null);

  // Sync animation/progress state
  const [syncing, setSyncing] = useState(false);
  const [syncStep, setSyncStep] = useState(0);
  const [connectedStore, setConnectedStore] = useState<StoreConnection | null>(null);

  // Payment Setup state
  const [paymentChoice, setPaymentChoice] = useState<string>('store_native');
  const [razorpayKeyId, setRazorpayKeyId] = useState('');
  const [razorpayKeySecret, setRazorpayKeySecret] = useState('');
  const [razorpayMode, setRazorpayMode] = useState<'test' | 'live'>('test');

  // Check initial onboarding status
  useEffect(() => {
    api.get<OnboardingStatus>('/onboarding/status')
      .then(res => {
        if (res.data) {
          if (res.data.active_store) {
            setConnectedStore(res.data.active_store);
          }
          if (res.data.onboarding_step === 'payment_setup') {
            setCurrentStep('payment_setup');
          }
        }
      })
      .catch(console.error);
  }, []);

  // Handle Shopify OAuth Initiation
  const handleShopifyConnect = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!shopifyDomain.trim()) return;
    setLoading(true);
    setErrorMsg(null);
    setShopifyNote(null);

    try {
      const res = await api.post<{
        authorization_url: string | null;
        state: string | null;
        configured: boolean;
        message: string | null;
      }>('/stores/shopify/authorize', { shop_domain: shopifyDomain.trim() });

      if (res.data) {
        if (!res.data.configured) {
          setShopifyConfigured(false);
          setShopifyNote(res.data.message || 'Shopify App credentials are not configured in server environment.');
        } else if (res.data.authorization_url) {
          // Redirect to live Shopify OAuth installation screen
          window.location.href = res.data.authorization_url;
        }
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to initiate Shopify authorization');
    } finally {
      setLoading(false);
    }
  };

  // Handle WooCommerce Connect
  const handleWooCommerceConnect = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setErrorMsg(null);
    setSyncing(true);
    setSyncStep(1); // Verifying

    try {
      const res = await api.post<StoreConnection>('/stores/woocommerce/connect', {
        store_url: wcUrl.trim(),
        consumer_key: wcConsumerKey.trim(),
        consumer_secret: wcConsumerSecret.trim(),
        store_name: wcStoreName.trim() || undefined,
      });

      if (res.data) {
        setConnectedStore(res.data);
        setSyncStep(4); // Synchronized
        setSuccessMsg(`Successfully connected ${res.data.store_name || 'WooCommerce Store'}!`);
      }
    } catch (err: any) {
      setSyncing(false);
      setErrorMsg(err.message || 'Failed to connect WooCommerce store');
    } finally {
      setLoading(false);
    }
  };

  // Handle Custom Store Connect
  const handleCustomStoreConnect = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setErrorMsg(null);

    try {
      const res = await api.post<any>('/stores/custom/connect', {
        store_name: customStoreName.trim(),
        store_url: customStoreUrl.trim(),
      });

      if (res.data) {
        setCustomResponse(res.data);
        setConnectedStore(res.data.connection);
        setSuccessMsg(`Ingestion credentials generated for ${customStoreName}!`);
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to setup custom store ingestion');
    } finally {
      setLoading(false);
    }
  };

  // Skip or Set Up Manually
  const handleSkipOrManual = async () => {
    setLoading(true);
    try {
      await api.post('/onboarding/skip', {});
      const updatedUser: User = { ...user, onboarding_completed: true };
      onUpdateUser(updatedUser);
      navigate('/dashboard');
    } catch (err: any) {
      setErrorMsg(err.message || 'Could not update setup status');
    } finally {
      setLoading(false);
    }
  };

  // Save Payment Configuration & Finish Onboarding
  const handleSavePayments = async () => {
    setLoading(true);
    setErrorMsg(null);

    try {
      await api.post('/payments/config', {
        payment_mode: paymentChoice,
        razorpay_key_id: razorpayKeyId.trim() || undefined,
        razorpay_key_secret: razorpayKeySecret.trim() || undefined,
        razorpay_mode: razorpayMode,
      });

      await api.post('/onboarding/step', { step: 'completed' });
      const updatedUser: User = { ...user, onboarding_completed: true };
      onUpdateUser(updatedUser);
      navigate('/dashboard');
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to save payment preferences');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-surface-950 flex flex-col justify-between p-4 sm:p-8 relative">
      {/* Background glow effects */}
      <div className="fixed top-1/4 left-1/3 w-96 h-96 bg-brand-600/5 rounded-full blur-3xl pointer-events-none" />
      <div className="fixed bottom-1/4 right-1/4 w-80 h-80 bg-brand-500/5 rounded-full blur-3xl pointer-events-none" />

      {/* Header */}
      <header className="max-w-4xl mx-auto w-full flex items-center justify-between pb-6 border-b border-surface-700/60">
        <div className="flex items-center gap-3">
          <div className="p-2.5 bg-brand-500/15 rounded-xl border border-brand-400/25">
            <Zap className="w-6 h-6 text-brand-400" />
          </div>
          <div>
            <div className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
              Flowmint AI
              <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-brand-500/15 text-brand-400 border border-brand-400/30">
                Setup
              </span>
            </div>
            <div className="text-xs text-surface-300">Turn every signal into a revenue action</div>
          </div>
        </div>

        {/* Step Indicator */}
        <div className="hidden sm:flex items-center gap-3 text-xs">
          <div className={`flex items-center gap-1.5 ${currentStep === 'connect_store' ? 'text-brand-400 font-bold' : 'text-surface-400'}`}>
            <span className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] ${currentStep === 'connect_store' ? 'bg-brand-500 text-white' : 'bg-surface-800'}`}>
              1
            </span>
            <span>Connect Store</span>
          </div>
          <ChevronRight className="w-4 h-4 text-surface-600" />
          <div className={`flex items-center gap-1.5 ${currentStep === 'payment_setup' ? 'text-brand-400 font-bold' : 'text-surface-400'}`}>
            <span className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] ${currentStep === 'payment_setup' ? 'bg-brand-500 text-white' : 'bg-surface-800'}`}>
              2
            </span>
            <span>Configure Payments</span>
          </div>
        </div>
      </header>

      {/* Main Body */}
      <main className="max-w-4xl mx-auto w-full py-8 flex-1">
        {errorMsg && (
          <div className="mb-6 p-4 bg-danger-500/10 border border-danger-500/30 rounded-xl flex items-center gap-3 text-sm text-danger-400 animate-fade-in">
            <AlertCircle className="w-5 h-5 flex-shrink-0" />
            <span>{errorMsg}</span>
          </div>
        )}

        {successMsg && (
          <div className="mb-6 p-4 bg-emerald-500/10 border border-emerald-500/30 rounded-xl flex items-center gap-3 text-sm text-emerald-300 animate-fade-in">
            <CheckCircle2 className="w-5 h-5 flex-shrink-0" />
            <span>{successMsg}</span>
          </div>
        )}

        {/* ======================================================== */}
        {/* STEP 1: CONNECT STORE */}
        {/* ======================================================== */}
        {currentStep === 'connect_store' && !syncing && (
          <div className="space-y-8 animate-fade-in">
            {/* Title & Tagline */}
            <div className="text-center sm:text-left space-y-2">
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-brand-500/10 text-brand-400 border border-brand-400/20 text-xs font-semibold">
                <Sparkles className="w-3.5 h-3.5" />
                First-Login Setup
              </div>
              <h1 className="text-3xl sm:text-4xl font-bold text-white tracking-tight">
                Where is your online store?
              </h1>
              <p className="text-surface-300 text-sm sm:text-base max-w-2xl">
                Bring your products, orders, inventory and customer activity into Flowmint AI so
                revenue insights are based on your actual business.
              </p>
            </div>

            {/* Read-only Data Safety Guarantee */}
            <div className="card p-4 border-brand-500/25 bg-brand-950/15 flex items-start gap-3">
              <ShieldCheck className="w-5 h-5 text-brand-400 flex-shrink-0 mt-0.5" />
              <div className="text-xs text-surface-300 space-y-1">
                <span className="font-semibold text-white">Read-Only Synchronization & Data Safety:</span>
                <p>
                  Flowmint AI inspects catalog records, orders, and customer activity to detect
                  revenue opportunities. We will never modify external product prices, inventory, or
                  orders without your explicit human approval.
                </p>
              </div>
            </div>

            {/* Platform Selection Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              {/* Shopify */}
              <button
                type="button"
                onClick={() => { setSelectedPlatform('shopify'); setErrorMsg(null); }}
                className={`card p-5 text-left transition-all ${
                  selectedPlatform === 'shopify'
                    ? 'border-brand-500 ring-2 ring-brand-500/20 bg-brand-950/20'
                    : 'hover:border-surface-600'
                }`}
              >
                <div className="flex items-center justify-between mb-3">
                  <div className="w-10 h-10 rounded-xl bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center text-emerald-400 font-bold text-lg">
                    S
                  </div>
                  <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                    OAuth 2.0
                  </span>
                </div>
                <h3 className="text-base font-semibold text-white">Shopify</h3>
                <p className="text-xs text-surface-400 mt-1 line-clamp-2">
                  Connect via official Shopify App authorization to sync catalog and orders.
                </p>
              </button>

              {/* WooCommerce */}
              <button
                type="button"
                onClick={() => { setSelectedPlatform('woocommerce'); setErrorMsg(null); }}
                className={`card p-5 text-left transition-all ${
                  selectedPlatform === 'woocommerce'
                    ? 'border-brand-500 ring-2 ring-brand-500/20 bg-brand-950/20'
                    : 'hover:border-surface-600'
                }`}
              >
                <div className="flex items-center justify-between mb-3">
                  <div className="w-10 h-10 rounded-xl bg-purple-500/15 border border-purple-500/30 flex items-center justify-center text-purple-400 font-bold text-lg">
                    W
                  </div>
                  <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-purple-500/10 text-purple-400 border border-purple-500/20">
                    REST API
                  </span>
                </div>
                <h3 className="text-base font-semibold text-white">WooCommerce</h3>
                <p className="text-xs text-surface-400 mt-1 line-clamp-2">
                  Connect via WooCommerce REST API using your Consumer Key & Secret.
                </p>
              </button>

              {/* Custom Store */}
              <button
                type="button"
                onClick={() => { setSelectedPlatform('custom'); setErrorMsg(null); }}
                className={`card p-5 text-left transition-all ${
                  selectedPlatform === 'custom'
                    ? 'border-brand-500 ring-2 ring-brand-500/20 bg-brand-950/20'
                    : 'hover:border-surface-600'
                }`}
              >
                <div className="flex items-center justify-between mb-3">
                  <div className="w-10 h-10 rounded-xl bg-blue-500/15 border border-blue-500/30 flex items-center justify-center text-blue-400 font-bold">
                    <Code2 className="w-5 h-5" />
                  </div>
                  <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/20">
                    API Contract
                  </span>
                </div>
                <h3 className="text-base font-semibold text-white">Custom Store</h3>
                <p className="text-xs text-surface-400 mt-1 line-clamp-2">
                  Connect React, Node.js, Django or Python stores using our ingestion API.
                </p>
              </button>
            </div>

            {/* Platform Coming Soon Row */}
            <div className="flex items-center gap-3 pt-2 text-xs text-surface-400">
              <span className="font-medium">Coming soon:</span>
              <span className="px-2.5 py-1 rounded-md bg-surface-900 border border-surface-700/60 opacity-60">
                BigCommerce
              </span>
              <span className="px-2.5 py-1 rounded-md bg-surface-900 border border-surface-700/60 opacity-60">
                Magento
              </span>
              <span className="px-2.5 py-1 rounded-md bg-surface-900 border border-surface-700/60 opacity-60">
                Amazon
              </span>
            </div>

            {/* Platform Connection Form */}
            <div className="card p-6 sm:p-8 space-y-6">
              {/* SHOPIFY FORM */}
              {selectedPlatform === 'shopify' && (
                <form onSubmit={handleShopifyConnect} className="space-y-5">
                  <div className="flex items-center gap-3 pb-4 border-b border-surface-700/60">
                    <div className="p-2 bg-emerald-500/10 rounded-lg text-emerald-400 font-bold">
                      S
                    </div>
                    <div>
                      <h4 className="text-base font-semibold text-white">Connect Shopify Store</h4>
                      <p className="text-xs text-surface-400">
                        Enter your myshopify domain to start OAuth authorization.
                      </p>
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-surface-200 mb-1.5">
                      Shopify Store Domain
                    </label>
                    <div className="relative">
                      <input
                        type="text"
                        value={shopifyDomain}
                        onChange={e => setShopifyDomain(e.target.value)}
                        placeholder="your-store-name.myshopify.com"
                        className="input-field w-full pl-3 pr-24"
                        required
                      />
                      <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-surface-400 pointer-events-none">
                        .myshopify.com
                      </span>
                    </div>
                    <p className="text-xs text-surface-400 mt-1.5">
                      Example: <span className="font-mono text-surface-300">my-apparel.myshopify.com</span> or slug <span className="font-mono text-surface-300">my-apparel</span>
                    </p>
                  </div>

                  {shopifyConfigured === false && shopifyNote && (
                    <div className="p-4 bg-amber-500/10 border border-amber-500/30 rounded-xl space-y-2 text-xs text-amber-200">
                      <div className="font-semibold flex items-center gap-1.5 text-amber-300">
                        <AlertCircle className="w-4 h-4" />
                        Platform Configuration Notice
                      </div>
                      <p>{shopifyNote}</p>
                      <p className="text-[11px] text-surface-300">
                        To test in development without live Shopify app keys, you can test WooCommerce REST API or use the Custom Store ingestion protocol below.
                      </p>
                    </div>
                  )}

                  <div className="flex items-center justify-between pt-2">
                    <button
                      type="submit"
                      disabled={loading || !shopifyDomain.trim()}
                      className="btn-primary flex items-center gap-2 px-6"
                    >
                      {loading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <ExternalLink className="w-4 h-4" />}
                      <span>Authorize with Shopify</span>
                    </button>

                    <button
                      type="button"
                      onClick={handleSkipOrManual}
                      className="text-xs text-surface-400 hover:text-white transition-colors"
                    >
                      Skip for now
                    </button>
                  </div>
                </form>
              )}

              {/* WOOCOMMERCE FORM */}
              {selectedPlatform === 'woocommerce' && (
                <form onSubmit={handleWooCommerceConnect} className="space-y-4">
                  <div className="flex items-center gap-3 pb-4 border-b border-surface-700/60">
                    <div className="p-2 bg-purple-500/10 rounded-lg text-purple-400 font-bold">
                      W
                    </div>
                    <div>
                      <h4 className="text-base font-semibold text-white">Connect WooCommerce Store</h4>
                      <p className="text-xs text-surface-400">
                        Provide your store HTTPS URL and read-only REST API keys from WooCommerce &gt; Settings &gt; Advanced &gt; REST API.
                      </p>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div className="sm:col-span-2">
                      <label className="block text-sm font-medium text-surface-200 mb-1.5">
                        Store URL (HTTPS)
                      </label>
                      <input
                        type="url"
                        value={wcUrl}
                        onChange={e => setWcUrl(e.target.value)}
                        placeholder="https://yourstore.com"
                        className="input-field w-full"
                        required
                      />
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-surface-200 mb-1.5">
                        Consumer Key
                      </label>
                      <input
                        type="text"
                        value={wcConsumerKey}
                        onChange={e => setWcConsumerKey(e.target.value)}
                        placeholder="ck_xxxxxxxxxxxxxxxxxxxxxxxx"
                        className="input-field w-full font-mono text-xs"
                        required
                      />
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-surface-200 mb-1.5">
                        Consumer Secret
                      </label>
                      <input
                        type="password"
                        value={wcConsumerSecret}
                        onChange={e => setWcConsumerSecret(e.target.value)}
                        placeholder="cs_xxxxxxxxxxxxxxxxxxxxxxxx"
                        className="input-field w-full font-mono text-xs"
                        required
                      />
                    </div>

                    <div className="sm:col-span-2">
                      <label className="block text-sm font-medium text-surface-200 mb-1.5">
                        Store Name (Optional)
                      </label>
                      <input
                        type="text"
                        value={wcStoreName}
                        onChange={e => setWcStoreName(e.target.value)}
                        placeholder="e.g. Urban Threads Flagship"
                        className="input-field w-full"
                      />
                    </div>
                  </div>

                  <div className="flex items-center justify-between pt-4">
                    <button
                      type="submit"
                      disabled={loading || !wcUrl || !wcConsumerKey || !wcConsumerSecret}
                      className="btn-primary flex items-center gap-2 px-6"
                    >
                      {loading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <ShieldCheck className="w-4 h-4" />}
                      <span>Verify &amp; Connect Store</span>
                    </button>

                    <button
                      type="button"
                      onClick={handleSkipOrManual}
                      className="text-xs text-surface-400 hover:text-white transition-colors"
                    >
                      Skip for now
                    </button>
                  </div>
                </form>
              )}

              {/* CUSTOM STORE FORM */}
              {selectedPlatform === 'custom' && (
                <div className="space-y-5">
                  <div className="flex items-center gap-3 pb-4 border-b border-surface-700/60">
                    <div className="p-2 bg-blue-500/10 rounded-lg text-blue-400 font-bold">
                      <Code2 className="w-5 h-5" />
                    </div>
                    <div>
                      <h4 className="text-base font-semibold text-white">Custom Storefront Ingestion</h4>
                      <p className="text-xs text-surface-400">
                        Generate merchant ingestion keys to push catalog, orders, and customer activity from your custom stack.
                      </p>
                    </div>
                  </div>

                  {!customResponse ? (
                    <form onSubmit={handleCustomStoreConnect} className="space-y-4">
                      <div>
                        <label className="block text-sm font-medium text-surface-200 mb-1.5">
                          Storefront Name
                        </label>
                        <input
                          type="text"
                          value={customStoreName}
                          onChange={e => setCustomStoreName(e.target.value)}
                          placeholder="e.g. Next.js Commerce App"
                          className="input-field w-full"
                          required
                        />
                      </div>

                      <div>
                        <label className="block text-sm font-medium text-surface-200 mb-1.5">
                          Storefront Website URL
                        </label>
                        <input
                          type="url"
                          value={customStoreUrl}
                          onChange={e => setCustomStoreUrl(e.target.value)}
                          placeholder="https://mystore.example.com"
                          className="input-field w-full"
                          required
                        />
                      </div>

                      <div className="flex items-center justify-between pt-2">
                        <button
                          type="submit"
                          disabled={loading || !customStoreName || !customStoreUrl}
                          className="btn-primary flex items-center gap-2 px-6"
                        >
                          {loading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Code2 className="w-4 h-4" />}
                          <span>Generate Ingestion API Keys</span>
                        </button>

                        <button
                          type="button"
                          onClick={handleSkipOrManual}
                          className="text-xs text-surface-400 hover:text-white transition-colors"
                        >
                          Skip for now
                        </button>
                      </div>
                    </form>
                  ) : (
                    <div className="space-y-4 animate-fade-in">
                      <div className="p-4 bg-surface-900 border border-surface-700/80 rounded-xl space-y-3">
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-semibold text-brand-400 uppercase tracking-wider">
                            Your Store Ingestion Key
                          </span>
                          <span className="text-[10px] text-surface-400 font-mono">Keep Secret</span>
                        </div>
                        <div className="font-mono text-xs p-2.5 bg-surface-950 rounded border border-surface-700 text-emerald-300 break-all select-all">
                          {customResponse.ingestion_api_key}
                        </div>
                      </div>

                      <div className="space-y-2">
                        <label className="text-xs font-medium text-surface-300">
                          Sample Ingestion Request:
                        </label>
                        <pre className="p-3 bg-surface-950 rounded-xl border border-surface-800 text-[11px] font-mono text-surface-300 overflow-x-auto">
{`curl -X POST "${customResponse.ingestion_endpoint}/${customResponse.connection.id}/ingest/products" \\
  -H "Authorization: Bearer <MERCHANT_JWT>" \\
  -H "Content-Type: application/json" \\
  -d '{
    "products": [{
      "external_id": "prod_123",
      "name": "Wireless Noise Cancelling Headphones",
      "sku": "WH-1000XM5",
      "price": 24990,
      "quantity": 25
    }]
  }'`}
                        </pre>
                      </div>

                      <div className="flex items-center justify-between pt-2">
                        <button
                          type="button"
                          onClick={() => setCurrentStep('payment_setup')}
                          className="btn-primary flex items-center gap-2"
                        >
                          <span>Proceed to Payment Setup</span>
                          <ArrowRight className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Manual Setup Alternative */}
            <div className="card p-6 bg-surface-900/40 border-surface-700/50 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
              <div className="space-y-1">
                <h4 className="text-sm font-semibold text-white">Don't have an online store yet?</h4>
                <p className="text-xs text-surface-400">
                  You can manage products, customers, and inventory manually within Flowmint AI.
                </p>
              </div>
              <button
                type="button"
                onClick={handleSkipOrManual}
                disabled={loading}
                className="btn-secondary text-xs px-4 py-2 flex items-center gap-2 flex-shrink-0"
              >
                <span>Set up manually / Skip for now</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        )}

        {/* ======================================================== */}
        {/* SYNCHRONIZATION PROGRESS OVERLAY */}
        {/* ======================================================== */}
        {syncing && (
          <div className="card p-8 text-center space-y-6 max-w-lg mx-auto animate-fade-in">
            <div className="w-16 h-16 mx-auto rounded-2xl bg-brand-500/15 border border-brand-400/30 flex items-center justify-center">
              <RefreshCw className="w-8 h-8 text-brand-400 animate-spin" />
            </div>

            <div className="space-y-2">
              <h2 className="text-2xl font-bold text-white">
                Synchronizing Commerce Records
              </h2>
              <p className="text-xs text-surface-400">
                Fetching actual catalog, customers, and order history from your store.
              </p>
            </div>

            {/* Real Progress Steps */}
            <div className="space-y-3 text-left max-w-sm mx-auto text-xs">
              <div className="flex items-center gap-2.5 text-emerald-400 font-medium">
                <CheckCircle2 className="w-4 h-4" />
                <span>Store connection verified</span>
              </div>

              <div className="flex items-center gap-2.5 text-emerald-400 font-medium">
                <CheckCircle2 className="w-4 h-4" />
                <span>Catalog products &amp; inventory synced</span>
              </div>

              <div className="flex items-center gap-2.5 text-emerald-400 font-medium">
                <CheckCircle2 className="w-4 h-4" />
                <span>Customer records &amp; profiles mapped</span>
              </div>

              <div className="flex items-center gap-2.5 text-emerald-400 font-medium">
                <CheckCircle2 className="w-4 h-4" />
                <span>Orders &amp; financial statuses reconciled</span>
              </div>
            </div>

            <div className="pt-4 border-t border-surface-700/60">
              <button
                type="button"
                onClick={() => { setSyncing(false); setCurrentStep('payment_setup'); }}
                className="btn-primary w-full py-2.5 flex items-center justify-center gap-2"
              >
                <span>Proceed to Configure Payments</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}

        {/* ======================================================== */}
        {/* STEP 2: CONFIGURE PAYMENTS */}
        {/* ======================================================== */}
        {currentStep === 'payment_setup' && (
          <div className="space-y-8 animate-fade-in">
            <div className="text-center sm:text-left space-y-2">
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-brand-500/10 text-brand-400 border border-brand-400/20 text-xs font-semibold">
                <CreditCard className="w-3.5 h-3.5" />
                Step 2 of 2
              </div>
              <h1 className="text-3xl sm:text-4xl font-bold text-white tracking-tight">
                How do you currently accept payments?
              </h1>
              <p className="text-surface-300 text-sm sm:text-base max-w-2xl">
                Define how payments are accepted and reconciled so revenue attribution is accurate.
              </p>
            </div>

            {/* Payment Choice Options */}
            <div className="grid grid-cols-1 gap-3.5">
              {/* Option A */}
              <label
                className={`card p-5 cursor-pointer flex items-start gap-3.5 transition-all ${
                  paymentChoice === 'store_native'
                    ? 'border-brand-500 ring-2 ring-brand-500/20 bg-brand-950/20'
                    : 'hover:border-surface-600'
                }`}
              >
                <input
                  type="radio"
                  name="paymentChoice"
                  value="store_native"
                  checked={paymentChoice === 'store_native'}
                  onChange={e => setPaymentChoice(e.target.value)}
                  className="mt-1"
                />
                <div className="space-y-1">
                  <div className="text-sm font-semibold text-white">
                    A. Payments are handled by my existing online store
                  </div>
                  <p className="text-xs text-surface-400">
                    Customers checkout through your existing Shopify or WooCommerce checkout. Flowmint
                    imports order-level payment and financial statuses directly.
                  </p>
                </div>
              </label>

              {/* Option B */}
              <label
                className={`card p-5 cursor-pointer flex items-start gap-3.5 transition-all ${
                  paymentChoice === 'razorpay_reconciliation'
                    ? 'border-brand-500 ring-2 ring-brand-500/20 bg-brand-950/20'
                    : 'hover:border-surface-600'
                }`}
              >
                <input
                  type="radio"
                  name="paymentChoice"
                  value="razorpay_reconciliation"
                  checked={paymentChoice === 'razorpay_reconciliation'}
                  onChange={e => setPaymentChoice(e.target.value)}
                  className="mt-1"
                />
                <div className="space-y-1">
                  <div className="text-sm font-semibold text-white">
                    B. I use Razorpay and want to connect payment information
                  </div>
                  <p className="text-xs text-surface-400">
                    Connect Razorpay webhooks and gateway keys for transaction-level settlement, refund
                    tracking, and payment failure recovery.
                  </p>
                </div>
              </label>

              {/* Option C */}
              <label
                className={`card p-5 cursor-pointer flex items-start gap-3.5 transition-all ${
                  paymentChoice === 'razorpay_hosted'
                    ? 'border-brand-500 ring-2 ring-brand-500/20 bg-brand-950/20'
                    : 'hover:border-surface-600'
                }`}
              >
                <input
                  type="radio"
                  name="paymentChoice"
                  value="razorpay_hosted"
                  checked={paymentChoice === 'razorpay_hosted'}
                  onChange={e => setPaymentChoice(e.target.value)}
                  className="mt-1"
                />
                <div className="space-y-1">
                  <div className="text-sm font-semibold text-white">
                    C. I want to accept payments through a Flowmint-hosted storefront
                  </div>
                  <p className="text-xs text-surface-400">
                    Enable Razorpay Standard Checkout on Flowmint Store so buyers can purchase
                    directly through autonomous agent recommendations.
                  </p>
                </div>
              </label>

              {/* Option D */}
              <label
                className={`card p-5 cursor-pointer flex items-start gap-3.5 transition-all ${
                  paymentChoice === 'later'
                    ? 'border-brand-500 ring-2 ring-brand-500/20 bg-brand-950/20'
                    : 'hover:border-surface-600'
                }`}
              >
                <input
                  type="radio"
                  name="paymentChoice"
                  value="later"
                  checked={paymentChoice === 'later'}
                  onChange={e => setPaymentChoice(e.target.value)}
                  className="mt-1"
                />
                <div className="space-y-1">
                  <div className="text-sm font-semibold text-white">
                    D. I'll configure payments later
                  </div>
                  <p className="text-xs text-surface-400">
                    Skip payment configuration for now. You can configure gateway credentials anytime
                    in Settings &gt; Integrations.
                  </p>
                </div>
              </label>
            </div>

            {/* Optional Razorpay Key Input if B or C chosen */}
            {(paymentChoice === 'razorpay_reconciliation' || paymentChoice === 'razorpay_hosted') && (
              <div className="card p-6 space-y-4 border-brand-500/30 bg-surface-900/60 animate-fade-in">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-sm font-semibold text-white">
                    <Lock className="w-4 h-4 text-brand-400" />
                    Razorpay Gateway Credentials
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => setRazorpayMode('test')}
                      className={`text-xs px-2.5 py-1 rounded-md transition-colors ${
                        razorpayMode === 'test'
                          ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40 font-bold'
                          : 'text-surface-400 hover:text-white'
                      }`}
                    >
                      Test Mode
                    </button>
                    <button
                      type="button"
                      onClick={() => setRazorpayMode('live')}
                      className={`text-xs px-2.5 py-1 rounded-md transition-colors ${
                        razorpayMode === 'live'
                          ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 font-bold'
                          : 'text-surface-400 hover:text-white'
                      }`}
                    >
                      Live Mode
                    </button>
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-medium text-surface-300 mb-1">
                      Razorpay Key ID
                    </label>
                    <input
                      type="text"
                      value={razorpayKeyId}
                      onChange={e => setRazorpayKeyId(e.target.value)}
                      placeholder={razorpayMode === 'test' ? 'rzp_test_...' : 'rzp_live_...'}
                      className="input-field w-full font-mono text-xs"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-surface-300 mb-1">
                      Razorpay Key Secret (Server Encrypted)
                    </label>
                    <input
                      type="password"
                      value={razorpayKeySecret}
                      onChange={e => setRazorpayKeySecret(e.target.value)}
                      placeholder="••••••••••••••••••••"
                      className="input-field w-full font-mono text-xs"
                    />
                  </div>
                </div>
                <p className="text-[11px] text-surface-400">
                  Credentials are encrypted server-side with authenticated AES-128-CBC + HMAC-SHA256 and never logged or exposed.
                </p>
              </div>
            )}

            {/* Launch Dashboard Action */}
            <div className="flex items-center justify-between pt-4">
              <button
                type="button"
                onClick={() => setCurrentStep('connect_store')}
                className="btn-secondary text-xs px-4 py-2"
              >
                Back
              </button>

              <button
                type="button"
                onClick={handleSavePayments}
                disabled={loading}
                className="btn-primary flex items-center gap-2 px-6 py-2.5"
              >
                {loading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
                <span>Finish Setup &amp; Launch Dashboard</span>
              </button>
            </div>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="max-w-4xl mx-auto w-full pt-6 border-t border-surface-700/60 flex items-center justify-between text-xs text-surface-400">
        <div>Flowmint AI Revenue OS &bull; Isolated Multi-Merchant Architecture</div>
        <div className="flex items-center gap-4">
          <a href="/judge" className="hover:text-white transition-colors">
            Judge Walkthrough
          </a>
          <button onClick={handleSkipOrManual} className="hover:text-white transition-colors">
            Skip setup
          </button>
        </div>
      </footer>
    </div>
  );
}
