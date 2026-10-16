import { useEffect, useState, useCallback, useRef } from 'react';
import { api, ApiError } from '../../lib/api';
import type { Product, StoreConnection, StoreSyncStatus, ProductUpdateRequest, ShopifySyncResult } from '../../types';
import { Plus, Search, Package, Edit2, Trash2, Upload, RefreshCw, Store, CheckCircle2, Clock, AlertCircle } from 'lucide-react';
import ProductImportModal from '../../components/merchant/ProductImportModal';

export default function ProductsPage() {
  const [products, setProducts] = useState<Product[]>([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [showImport, setShowImport] = useState(false);
  const [editingProduct, setEditingProduct] = useState<Product | null>(null);

  // Store integration & auto-sync state
  const [storeConnection, setStoreConnection] = useState<StoreConnection | null>(null);
  const [isSyncing, setIsSyncing] = useState(false);
  const [syncMsg, setSyncMsg] = useState<string | null>(null);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const loadProducts = useCallback(async () => {
    setLoading(true);
    try {
      const q = search ? `&q=${encodeURIComponent(search)}` : '';
      const res = await api.get<Product[]>(`/products?per_page=50${q}`);
      setProducts(res.data || []);
    } catch (e) {
      console.error('Failed to load products', e);
    } finally {
      setLoading(false);
    }
  }, [search]);

  const loadStoreConnection = useCallback(async () => {
    try {
      const res = await api.get<StoreConnection[]>('/stores');
      const active = (res.data || []).find(c => ['connected', 'synced', 'syncing'].includes(c.status));
      if (active) {
        setStoreConnection(active);
        if (active.sync_status === 'running') {
          setIsSyncing(true);
        }
      } else {
        setStoreConnection(null);
      }
    } catch (e) {
      console.error('Failed to load store connection', e);
    }
  }, []);

  // Initial load
  useEffect(() => {
    loadProducts();
    loadStoreConnection();
  }, [loadProducts, loadStoreConnection]);

  // Refetch when browser window gains focus (e.g. merchant edited product in Shopify tab and switched back)
  useEffect(() => {
    const handleFocus = () => {
      loadProducts();
      loadStoreConnection();
    };
    window.addEventListener('focus', handleFocus);
    return () => window.removeEventListener('focus', handleFocus);
  }, [loadProducts, loadStoreConnection]);

  // 5-second polling when a sync job is running
  useEffect(() => {
    if (!isSyncing || !storeConnection) {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
      return;
    }

    pollingRef.current = setInterval(async () => {
      try {
        const res = await api.get<StoreConnection>(`/stores/${storeConnection.id}`);
        if (res.data) {
          setStoreConnection(res.data);
          if (res.data.sync_status !== 'running') {
            setIsSyncing(false);
            if (pollingRef.current) {
              clearInterval(pollingRef.current);
              pollingRef.current = null;
            }
            // Sync finished: refetch fresh products from PostgreSQL
            await loadProducts();
          }
        }
      } catch (err) {
        setIsSyncing(false);
        if (pollingRef.current) {
          clearInterval(pollingRef.current);
          pollingRef.current = null;
        }
      }
    }, 5000);

    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
    };
  }, [isSyncing, storeConnection?.id, loadProducts]);

  // Manual Quick Sync
  const handleQuickSync = async () => {
    if (!storeConnection || isSyncing) return;
    setIsSyncing(true);
    setSyncMsg(null);
    try {
      const res = await api.post<StoreSyncStatus>(`/stores/${storeConnection.id}/sync`);
      if (res.data) {
        setSyncMsg(`Synced ${res.data.records_processed} records.`);
        await Promise.all([loadProducts(), loadStoreConnection()]);
      }
    } catch (err: any) {
      setSyncMsg(err.message || 'Sync failed');
    } finally {
      setIsSyncing(false);
    }
  };

  const formatPrice = (price: number) =>
    new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(price);

  const formatLastSync = (dateStr: string | null) => {
    if (!dateStr) return 'Never';
    const date = new Date(dateStr);
    const now = new Date();
    const diffSec = Math.floor((now.getTime() - date.getTime()) / 1000);
    if (diffSec < 60) return 'Just now';
    if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`;
    return date.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' });
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Products</h1>
          <p className="text-surface-300 text-sm mt-1">Manage your product catalog</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            type="button"
            className="btn-secondary flex items-center gap-2"
            onClick={() => setShowImport(true)}
          >
            <Upload className="w-4 h-4" /> Import Products
          </button>
          <button className="btn-primary flex items-center gap-2" onClick={() => setShowCreate(true)}>
            <Plus className="w-4 h-4" /> Add Product
          </button>
        </div>
      </div>

      {/* Connected Store Live Sync Status Bar */}
      {storeConnection && (
        <div className="bg-surface-800/80 border border-brand-500/20 rounded-xl p-3 sm:px-4 sm:py-3 flex flex-wrap items-center justify-between gap-3 backdrop-blur-sm">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-brand-500/10 border border-brand-500/30 flex items-center justify-center text-brand-400">
              <Store className="w-4 h-4" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-white capitalize">
                  {storeConnection.provider} Connected
                </span>
                <span className="text-xs text-surface-300 font-mono">
                  ({storeConnection.store_name || storeConnection.store_url.replace('https://', '')})
                </span>
                {isSyncing ? (
                  <span className="inline-flex items-center gap-1 text-[11px] font-medium text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded-full border border-amber-500/30">
                    <RefreshCw className="w-3 h-3 animate-spin" /> Syncing...
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 text-[11px] font-medium text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full border border-emerald-500/30">
                    <CheckCircle2 className="w-3 h-3" /> Live Synced
                  </span>
                )}
              </div>
              <div className="flex items-center gap-3 text-xs text-surface-300 mt-0.5">
                <span className="flex items-center gap-1">
                  <Clock className="w-3 h-3 text-surface-300" /> Last updated: {formatLastSync(storeConnection.last_sync_at)}
                </span>
                <span className="hidden sm:inline text-surface-400">•</span>
                <span className="hidden sm:inline text-surface-300">
                  Shopify product updates sync automatically via webhooks
                </span>
                {syncMsg && <span className="text-brand-300 font-medium">({syncMsg})</span>}
              </div>
            </div>
          </div>

          <button
            type="button"
            onClick={handleQuickSync}
            disabled={isSyncing}
            className="btn-secondary text-xs flex items-center gap-1.5 px-3 py-1.5 self-start sm:self-auto disabled:opacity-50"
            title="Reconcile latest changes from connected store"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isSyncing ? 'animate-spin text-brand-400' : ''}`} />
            <span>{isSyncing ? 'Syncing...' : 'Sync Now'}</span>
          </button>
        </div>
      )}

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-surface-300" />
        <input
          className="input-field w-full pl-10"
          placeholder="Search products by name, SKU, or description..."
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
      </div>

      {/* Products Table */}
      <div className="card overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-surface-300">Loading products...</div>
        ) : products.length === 0 ? (
          <div className="p-12 text-center">
            <Package className="w-12 h-12 text-surface-300/30 mx-auto mb-3" />
            <p className="text-surface-300">No products found</p>
            <button className="btn-primary mt-4" onClick={() => setShowCreate(true)}>
              Create your first product
            </button>
          </div>
        ) : (
          <table className="w-full">
            <thead>
              <tr className="border-b border-surface-700/50">
                <th className="table-header px-6 py-3 text-left">Product</th>
                <th className="table-header px-6 py-3 text-left">SKU</th>
                <th className="table-header px-6 py-3 text-right">Price</th>
                <th className="table-header px-6 py-3 text-center">Stock</th>
                <th className="table-header px-6 py-3 text-center">Status</th>
                <th className="table-header px-6 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {products.map(product => (
                <tr key={product.id} className="table-row">
                  <td className="px-6 py-3.5">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-white">{product.name}</span>
                        {product.is_shopify_connected ? (
                          <span className="inline-flex items-center gap-1 text-[11px] font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-1.5 py-0.5 rounded">
                            <Store className="w-3 h-3" />
                            Shopify
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-[11px] font-medium bg-surface-800 text-surface-400 border border-surface-700 px-1.5 py-0.5 rounded">
                            Local
                          </span>
                        )}
                      </div>
                      {product.attributes.length > 0 && (
                        <div className="flex gap-2 mt-1">
                          {product.attributes.slice(0, 3).map(a => (
                            <span key={a.key} className="text-xs text-surface-300 bg-surface-800 px-1.5 py-0.5 rounded">
                              {a.key}: {a.value}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </td>
                  <td className="px-6 py-3.5 text-sm font-mono text-surface-300">
                    {product.sku}
                  </td>
                  <td className="px-6 py-3.5 text-sm text-right">
                    <span className="font-medium text-white">{formatPrice(Number(product.price))}</span>
                    {product.compare_at_price && (
                      <span className="ml-2 text-surface-300 line-through text-xs">
                        {formatPrice(Number(product.compare_at_price))}
                      </span>
                    )}
                  </td>
                  <td className="px-6 py-3.5 text-center">
                    {product.inventory ? (
                      <span className={
                        product.inventory.is_low_stock ? 'badge-warning' :
                        product.inventory.is_in_stock ? 'badge-success' : 'badge-danger'
                      }>
                        {product.inventory.available} avail
                      </span>
                    ) : '—'}
                  </td>
                  <td className="px-6 py-3.5 text-center">
                    <span className={
                      product.status === 'active' ? 'badge-success' :
                      product.status === 'draft' ? 'badge-warning' : 'badge-danger'
                    }>
                      {product.status}
                    </span>
                  </td>
                  <td className="px-6 py-3.5 text-right">
                    <button
                      onClick={() => setEditingProduct(product)}
                      className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium rounded-md bg-surface-800 hover:bg-surface-700 text-surface-200 hover:text-white border border-surface-700 transition"
                      title="Edit product"
                    >
                      <Edit2 className="w-3.5 h-3.5 text-brand-400" />
                      <span>Edit</span>
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Edit Product Modal */}
      {editingProduct && (
        <EditProductModal
          product={editingProduct}
          onClose={() => setEditingProduct(null)}
          onSaved={() => {
            loadProducts();
          }}
        />
      )}

      {/* Create Modal placeholder */}
      {showCreate && (
        <CreateProductModal
          onClose={() => setShowCreate(false)}
          onCreated={() => { setShowCreate(false); loadProducts(); }}
        />
      )}

      {/* Bulk Catalog Import Modal */}
      {showImport && (
        <ProductImportModal
          isOpen={showImport}
          onClose={() => setShowImport(false)}
          onImportComplete={() => {
            setShowImport(false);
            loadProducts();
          }}
        />
      )}
    </div>
  );
}

function CreateProductModal({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [name, setName] = useState('');
  const [sku, setSku] = useState('');
  const [price, setPrice] = useState('');
  const [description, setDescription] = useState('');
  const [stock, setStock] = useState('0');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError('');

    try {
      await api.post('/products', {
        name,
        sku,
        price: parseFloat(price),
        description: description || undefined,
        initial_stock: parseInt(stock) || 0,
      });
      onCreated();
    } catch (err) {
      if (err instanceof ApiError) setError(err.message);
      else setError('Failed to create product');
    }
    setSubmitting(false);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="card p-6 w-full max-w-lg animate-slide-up">
        <h2 className="text-xl font-bold text-white mb-4">Create Product</h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-surface-300 mb-1">Product Name</label>
            <input className="input-field w-full" value={name} onChange={e => setName(e.target.value)} required />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-surface-300 mb-1">SKU</label>
              <input className="input-field w-full" value={sku} onChange={e => setSku(e.target.value)} required />
            </div>
            <div>
              <label className="block text-sm font-medium text-surface-300 mb-1">Price (₹)</label>
              <input className="input-field w-full" type="number" step="0.01" value={price} onChange={e => setPrice(e.target.value)} required />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-surface-300 mb-1">Description</label>
            <textarea className="input-field w-full" rows={3} value={description} onChange={e => setDescription(e.target.value)} />
          </div>
          <div>
            <label className="block text-sm font-medium text-surface-300 mb-1">Initial Stock</label>
            <input className="input-field w-full" type="number" value={stock} onChange={e => setStock(e.target.value)} />
          </div>
          {error && <p className="text-danger-500 text-sm">{error}</p>}
          <div className="flex gap-3 justify-end">
            <button type="button" className="btn-secondary" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn-primary" disabled={submitting}>
              {submitting ? 'Creating...' : 'Create Product'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

interface EditProductModalProps {
  product: Product;
  onClose: () => void;
  onSaved: () => void;
}

function EditProductModal({ product, onClose, onSaved }: EditProductModalProps) {
  const [name, setName] = useState(product.name);
  const [sku, setSku] = useState(product.sku);
  const [price, setPrice] = useState(String(product.price));
  const [compareAtPrice, setCompareAtPrice] = useState(product.compare_at_price ? String(product.compare_at_price) : '');
  const [stock, setStock] = useState(String(product.inventory?.quantity ?? product.inventory?.available ?? 0));
  const [description, setDescription] = useState(product.description || '');
  const [status, setStatus] = useState<'active' | 'draft' | 'archived'>(product.status);
  const [syncToShopify, setSyncToShopify] = useState(Boolean(product.is_shopify_connected));
  const [error, setError] = useState('');
  const [syncResult, setSyncResult] = useState<ShopifySyncResult | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [savedSuccess, setSavedSuccess] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSyncResult(null);

    // Form validations
    if (!name.trim()) {
      setError('Product name is required.');
      return;
    }
    if (!sku.trim()) {
      setError('SKU is required.');
      return;
    }
    const numPrice = parseFloat(price);
    if (isNaN(numPrice) || numPrice <= 0) {
      setError('Price must be a valid positive number.');
      return;
    }
    const numStock = parseInt(stock, 10);
    if (isNaN(numStock) || numStock < 0) {
      setError('Stock quantity must be a non-negative number.');
      return;
    }

    setSubmitting(true);
    try {
      const payload: ProductUpdateRequest = {
        name: name.trim(),
        sku: sku.trim(),
        price: numPrice,
        compare_at_price: compareAtPrice ? parseFloat(compareAtPrice) : null,
        inventory_quantity: numStock,
        description: description.trim() || undefined,
        status,
        sync_to_shopify: product.is_shopify_connected ? syncToShopify : false,
      };

      const res = await api.patch<Product>(`/products/${product.id}`, payload);
      setSavedSuccess(true);

      if (res.data?.shopify_sync_result) {
        setSyncResult(res.data.shopify_sync_result);
      }

      onSaved();
    } catch (err: any) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError(err.message || 'Failed to update product');
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 overflow-y-auto">
      <div className="card p-6 w-full max-w-xl animate-slide-up my-8 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between mb-4 pb-3 border-b border-surface-700/50">
          <div>
            <h2 className="text-xl font-bold text-white flex items-center gap-2">
              <Edit2 className="w-5 h-5 text-brand-400" />
              Edit Product
            </h2>
            <p className="text-xs text-surface-400 mt-0.5">
              Product ID: <span className="font-mono text-surface-300">{product.id}</span>
            </p>
          </div>
          {product.is_shopify_connected ? (
            <span className="inline-flex items-center gap-1.5 text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 px-2.5 py-1 rounded-full">
              <Store className="w-3.5 h-3.5" />
              Shopify Linked ({product.external_product_id})
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5 text-xs font-medium bg-surface-800 text-surface-400 border border-surface-700 px-2.5 py-1 rounded-full">
              Local Product
            </span>
          )}
        </div>

        {/* Sync Result Feedback Banners */}
        {savedSuccess && (
          <div className="mb-4 space-y-2">
            <div className="p-3 bg-emerald-500/10 border border-emerald-500/30 rounded-lg flex items-start gap-2 text-emerald-300 text-sm">
              <CheckCircle2 className="w-4 h-4 text-emerald-400 mt-0.5 shrink-0" />
              <div>
                <span className="font-semibold">Local Save:</span> Product changes saved successfully in Flowmint AI.
              </div>
            </div>

            {syncResult && syncResult.status === 'pushed' && (
              <div className="p-3 bg-brand-500/10 border border-brand-500/30 rounded-lg flex items-start gap-2 text-brand-300 text-sm">
                <Store className="w-4 h-4 text-brand-400 mt-0.5 shrink-0" />
                <div>
                  <span className="font-semibold">Shopify Sync:</span> {syncResult.message}
                </div>
              </div>
            )}

            {syncResult && syncResult.status === 'permission_denied' && (
              <div className="p-3 bg-amber-500/10 border border-amber-500/30 rounded-lg flex items-start gap-2 text-amber-300 text-sm">
                <AlertCircle className="w-4 h-4 text-amber-400 mt-0.5 shrink-0" />
                <div>
                  <span className="font-semibold">Shopify Permission Warning:</span> {syncResult.message}
                </div>
              </div>
            )}

            {syncResult && syncResult.status === 'failed' && (
              <div className="p-3 bg-danger-500/10 border border-danger-500/30 rounded-lg flex items-start gap-2 text-danger-300 text-sm">
                <AlertCircle className="w-4 h-4 text-danger-400 mt-0.5 shrink-0" />
                <div>
                  <span className="font-semibold">Shopify Sync Failed:</span> {syncResult.message}
                </div>
              </div>
            )}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-surface-300 mb-1">
              Product Name <span className="text-danger-400">*</span>
            </label>
            <input
              className="input-field w-full"
              value={name}
              onChange={e => setName(e.target.value)}
              disabled={submitting}
              required
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-surface-300 mb-1">
                SKU <span className="text-danger-400">*</span>
              </label>
              <input
                className="input-field w-full font-mono text-sm"
                value={sku}
                onChange={e => setSku(e.target.value)}
                disabled={submitting}
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-surface-300 mb-1">
                Status
              </label>
              <select
                className="input-field w-full"
                value={status}
                onChange={e => setStatus(e.target.value as any)}
                disabled={submitting}
              >
                <option value="active">Active</option>
                <option value="draft">Draft</option>
                <option value="archived">Archived</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-surface-300 mb-1">
                Price (₹) <span className="text-danger-400">*</span>
              </label>
              <input
                className="input-field w-full"
                type="number"
                step="0.01"
                min="0.01"
                value={price}
                onChange={e => setPrice(e.target.value)}
                disabled={submitting}
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-surface-300 mb-1">
                Compare-at Price (₹)
              </label>
              <input
                className="input-field w-full"
                type="number"
                step="0.01"
                min="0.01"
                placeholder="Optional"
                value={compareAtPrice}
                onChange={e => setCompareAtPrice(e.target.value)}
                disabled={submitting}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-surface-300 mb-1">
                Stock Quantity
              </label>
              <input
                className="input-field w-full"
                type="number"
                min="0"
                value={stock}
                onChange={e => setStock(e.target.value)}
                disabled={submitting}
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-surface-300 mb-1">Description</label>
            <textarea
              className="input-field w-full"
              rows={3}
              value={description}
              onChange={e => setDescription(e.target.value)}
              disabled={submitting}
              placeholder="Product description..."
            />
          </div>

          {/* Shopify Bidirectional Synchronization Option */}
          {product.is_shopify_connected ? (
            <div className="p-3.5 bg-surface-800/80 border border-surface-700 rounded-lg space-y-2">
              <label className="flex items-start gap-2.5 cursor-pointer">
                <input
                  type="checkbox"
                  className="mt-1 h-4 w-4 rounded border-surface-600 bg-surface-900 text-brand-500 focus:ring-brand-500"
                  checked={syncToShopify}
                  onChange={e => setSyncToShopify(e.target.checked)}
                  disabled={submitting}
                />
                <div>
                  <span className="text-sm font-semibold text-white flex items-center gap-1.5">
                    <Store className="w-4 h-4 text-brand-400" />
                    Push changes to connected Shopify store
                  </span>
                  <p className="text-xs text-surface-400 mt-0.5">
                    Uses the Shopify GraphQL Admin API to update product title, price, SKU, status, and inventory in your live Shopify store. Requires <code className="text-surface-300 font-mono">write_products</code> and <code className="text-surface-300 font-mono">write_inventory</code> scopes.
                  </p>
                </div>
              </label>
            </div>
          ) : (
            <div className="p-3 bg-surface-800/40 border border-surface-800 rounded-lg text-xs text-surface-400">
              <span className="font-semibold text-surface-300">Local-only product:</span> This product was created directly in Flowmint AI. Changes will be saved to your PostgreSQL database only.
            </div>
          )}

          {error && (
            <div className="p-3 bg-danger-500/10 border border-danger-500/30 rounded-lg text-danger-400 text-sm flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <div className="flex gap-3 justify-end pt-2 border-t border-surface-700/50">
            <button
              type="button"
              className="btn-secondary"
              onClick={onClose}
              disabled={submitting}
            >
              {savedSuccess ? 'Done' : 'Cancel'}
            </button>
            <button
              type="submit"
              className="btn-primary flex items-center gap-2"
              disabled={submitting}
            >
              {submitting && <RefreshCw className="w-4 h-4 animate-spin" />}
              <span>{submitting ? 'Saving...' : (product.is_shopify_connected && syncToShopify ? 'Save & Push to Shopify' : 'Save Changes')}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
