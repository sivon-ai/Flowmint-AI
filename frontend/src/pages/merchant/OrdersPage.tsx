import { useEffect, useState } from 'react';
import { api } from '../../lib/api';
import type { Order } from '../../types';
import { ShoppingCart } from 'lucide-react';

export default function OrdersPage() {
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get<Order[]>('/orders?per_page=50')
      .then(res => setOrders(res.data || []))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const formatCurrency = (val: number) =>
    new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(val);

  const statusStyles: Record<string, string> = {
    pending: 'badge-warning',
    confirmed: 'badge-success',
    completed: 'badge-success',
    cancelled: 'badge-danger',
    processing: 'badge-info',
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Orders</h1>
        <p className="text-surface-300 text-sm mt-1">Track and manage customer orders</p>
      </div>

      <div className="card overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-surface-300">Loading orders...</div>
        ) : orders.length === 0 ? (
          <div className="p-12 text-center">
            <ShoppingCart className="w-12 h-12 text-surface-300/30 mx-auto mb-3" />
            <p className="text-surface-300">No orders yet</p>
          </div>
        ) : (
          <table className="w-full">
            <thead>
              <tr className="border-b border-surface-700/50">
                <th className="table-header px-6 py-3 text-left">Order #</th>
                <th className="table-header px-6 py-3 text-left">Status</th>
                <th className="table-header px-6 py-3 text-center">Items</th>
                <th className="table-header px-6 py-3 text-right">Subtotal</th>
                <th className="table-header px-6 py-3 text-right">Total</th>
                <th className="table-header px-6 py-3 text-right">Date</th>
              </tr>
            </thead>
            <tbody>
              {orders.map(order => (
                <tr key={order.id} className="table-row">
                  <td className="px-6 py-3.5 text-sm font-mono text-brand-400 font-medium">
                    {order.order_number}
                  </td>
                  <td className="px-6 py-3.5">
                    <span className={statusStyles[order.status] || 'badge-info'}>
                      {order.status}
                    </span>
                  </td>
                  <td className="px-6 py-3.5 text-sm text-center text-surface-300">
                    {order.items.length}
                  </td>
                  <td className="px-6 py-3.5 text-sm text-right text-surface-300">
                    {formatCurrency(Number(order.subtotal))}
                  </td>
                  <td className="px-6 py-3.5 text-sm text-right font-medium text-white">
                    {formatCurrency(Number(order.total))}
                  </td>
                  <td className="px-6 py-3.5 text-sm text-right text-surface-300">
                    {new Date(order.created_at).toLocaleDateString('en-IN', {
                      day: '2-digit', month: 'short', year: 'numeric',
                    })}
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
