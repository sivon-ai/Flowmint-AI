import { useEffect, useState } from 'react';
import { api } from '../../lib/api';
import { Warehouse, AlertTriangle } from 'lucide-react';

interface InventoryItem {
  id: string;
  product_id: string;
  merchant_id: string;
  quantity: number;
  reserved: number;
  available: number;
  low_stock_threshold: number;
  is_low_stock: boolean;
  is_in_stock: boolean;
  updated_at: string;
}

export default function InventoryPage() {
  const [items, setItems] = useState<InventoryItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get<InventoryItem[]>('/inventory')
      .then(res => setItems(res.data || []))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const lowStockCount = items.filter(i => i.is_low_stock).length;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Inventory</h1>
          <p className="text-surface-300 text-sm mt-1">Stock levels and reservations</p>
        </div>
        {lowStockCount > 0 && (
          <div className="badge-warning flex items-center gap-1.5 px-3 py-1.5">
            <AlertTriangle className="w-3.5 h-3.5" />
            {lowStockCount} low stock items
          </div>
        )}
      </div>

      <div className="card overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-surface-300">Loading inventory...</div>
        ) : items.length === 0 ? (
          <div className="p-12 text-center">
            <Warehouse className="w-12 h-12 text-surface-300/30 mx-auto mb-3" />
            <p className="text-surface-300">No inventory data</p>
          </div>
        ) : (
          <table className="w-full">
            <thead>
              <tr className="border-b border-surface-700/50">
                <th className="table-header px-6 py-3 text-left">Product ID</th>
                <th className="table-header px-6 py-3 text-center">Total Qty</th>
                <th className="table-header px-6 py-3 text-center">Reserved</th>
                <th className="table-header px-6 py-3 text-center">Available</th>
                <th className="table-header px-6 py-3 text-center">Status</th>
                <th className="table-header px-6 py-3 text-right">Updated</th>
              </tr>
            </thead>
            <tbody>
              {items.map(item => (
                <tr key={item.id} className="table-row">
                  <td className="px-6 py-3.5 text-sm font-mono text-surface-300">
                    {item.product_id.slice(0, 8)}...
                  </td>
                  <td className="px-6 py-3.5 text-sm text-center text-white font-medium">
                    {item.quantity}
                  </td>
                  <td className="px-6 py-3.5 text-sm text-center text-warning-500">
                    {item.reserved}
                  </td>
                  <td className="px-6 py-3.5 text-sm text-center font-medium text-white">
                    {item.available}
                  </td>
                  <td className="px-6 py-3.5 text-center">
                    {!item.is_in_stock ? (
                      <span className="badge-danger">Out of Stock</span>
                    ) : item.is_low_stock ? (
                      <span className="badge-warning">Low Stock</span>
                    ) : (
                      <span className="badge-success">In Stock</span>
                    )}
                  </td>
                  <td className="px-6 py-3.5 text-sm text-right text-surface-300">
                    {new Date(item.updated_at).toLocaleString('en-IN')}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
