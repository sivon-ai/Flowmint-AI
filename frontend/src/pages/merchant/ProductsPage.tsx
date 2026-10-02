import { useEffect, useState } from 'react';
import { api, ApiError } from '../../lib/api';
import type { Product } from '../../types';
import { Plus, Search, Package, Edit2, Trash2 } from 'lucide-react';

export default function ProductsPage() {
  const [products, setProducts] = useState<Product[]>([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);

  const loadProducts = async () => {
    setLoading(true);
    try {
      const q = search ? `&q=${encodeURIComponent(search)}` : '';
      const res = await api.get<Product[]>(`/products?per_page=50${q}`);
      setProducts(res.data || []);
    } catch (e) { console.error(e); }
    setLoading(false);
  };

  useEffect(() => { loadProducts(); }, [search]);

  const formatPrice = (price: number) =>
    new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(price);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Products</h1>
          <p className="text-surface-300 text-sm mt-1">Manage your product catalog</p>
        </div>
        <button className="btn-primary flex items-center gap-2" onClick={() => setShowCreate(true)}>
          <Plus className="w-4 h-4" /> Add Product
        </button>
      </div>

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
              </tr>
            </thead>
            <tbody>
              {products.map(product => (
                <tr key={product.id} className="table-row">
                  <td className="px-6 py-3.5">
                    <div>
                      <div className="text-sm font-medium text-white">{product.name}</div>
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
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Create Modal placeholder */}
      {showCreate && (
        <CreateProductModal
          onClose={() => setShowCreate(false)}
          onCreated={() => { setShowCreate(false); loadProducts(); }}
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
