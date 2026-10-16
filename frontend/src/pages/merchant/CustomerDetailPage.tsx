import { useEffect, useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { api, ApiError } from '../../lib/api';
import type { Customer, CustomerOrdersResponse, CustomerUpdateRequest } from '../../types';
import {
  ArrowLeft,
  User,
  Mail,
  Phone,
  Calendar,
  ShoppingBag,
  Clock,
  TrendingUp,
  CreditCard,
  Edit2,
  AlertTriangle,
  Package,
  X,
  CheckCircle2,
} from 'lucide-react';

export default function CustomerDetailPage() {
  const { customerId } = useParams<{ customerId: string }>();
  const navigate = useNavigate();

  const [customer, setCustomer] = useState<Customer | null>(null);
  const [ordersData, setOrdersData] = useState<CustomerOrdersResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>('');
  const [showEditModal, setShowEditModal] = useState(false);
  const [toastMessage, setToastMessage] = useState('');

  const loadData = async () => {
    if (!customerId) return;
    setLoading(true);
    setError('');

    try {
      const [custRes, ordersRes] = await Promise.all([
        api.get<Customer>(`/customers/${customerId}`),
        api.get<CustomerOrdersResponse>(`/customers/${customerId}/orders`),
      ]);

      if (custRes.data) {
        setCustomer(custRes.data);
      }
      if (ordersRes.data) {
        setOrdersData(ordersRes.data);
      }
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError('Failed to load customer profile');
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [customerId]);

  const formatCurrency = (val: number) =>
    new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 0,
    }).format(val);

  const formatDate = (dateStr: string) => {
    try {
      return new Date(dateStr).toLocaleDateString('en-IN', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return dateStr;
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status.toLowerCase()) {
      case 'completed':
      case 'confirmed':
      case 'delivered':
        return 'badge-success';
      case 'pending':
      case 'processing':
        return 'badge-warning';
      case 'cancelled':
        return 'badge-danger';
      default:
        return 'badge-info';
    }
  };

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(''), 4000);
  };

  if (loading) {
    return (
      <div className="p-16 text-center space-y-4">
        <div className="w-8 h-8 border-2 border-brand-500 border-t-transparent rounded-full animate-spin mx-auto" />
        <p className="text-xs text-surface-400">Loading customer profile and purchase history...</p>
      </div>
    );
  }

  if (error || !customer) {
    return (
      <div className="p-12 text-center space-y-4 max-w-lg mx-auto">
        <div className="w-14 h-14 rounded-2xl bg-red-950/40 border border-red-500/30 text-red-400 flex items-center justify-center mx-auto">
          <AlertTriangle className="w-7 h-7" />
        </div>
        <h2 className="text-lg font-bold text-white">Customer Not Found</h2>
        <p className="text-xs text-surface-300">
          {error || 'This customer record does not exist or belongs to another merchant account.'}
        </p>
        <div className="pt-2">
          <Link to="/customers" className="btn-secondary text-xs inline-flex items-center gap-1.5">
            <ArrowLeft className="w-3.5 h-3.5" /> Back to Customers
          </Link>
        </div>
      </div>
    );
  }

  const summary = ordersData?.summary;
  const orders = ordersData?.orders || [];

  return (
    <div className="space-y-6 max-w-6xl mx-auto pb-12">
      {/* Toast Notification */}
      {toastMessage && (
        <div className="fixed top-5 right-5 z-50 flex items-center gap-2 px-4 py-3 bg-emerald-950 border border-emerald-500/40 text-emerald-300 rounded-xl shadow-2xl text-xs animate-slide-up">
          <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Navigation Breadcrumb */}
      <div>
        <Link
          to="/customers"
          className="inline-flex items-center gap-1.5 text-xs text-surface-400 hover:text-white transition"
        >
          <ArrowLeft className="w-3.5 h-3.5" /> Back to Customers List
        </Link>
      </div>

      {/* Customer Header Card */}
      <div className="card p-6 bg-gradient-to-r from-surface-900 to-surface-950 border border-surface-800">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="flex items-start gap-4">
            <div className="w-14 h-14 rounded-2xl bg-brand-500/15 border border-brand-500/30 text-brand-400 font-extrabold text-xl flex items-center justify-center shrink-0">
              {customer.name.charAt(0).toUpperCase()}
            </div>
            <div className="space-y-1">
              <div className="flex flex-wrap items-center gap-2">
                <h1 className="text-xl font-bold text-white">{customer.name}</h1>
                {summary && summary.total_orders >= 2 && (
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-brand-500/20 text-brand-300 border border-brand-500/40">
                    Repeat Buyer ({summary.total_orders} Orders)
                  </span>
                )}
                {summary && summary.total_orders === 1 && (
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">
                    First-Time Buyer
                  </span>
                )}
                {summary && summary.total_orders === 0 && (
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-surface-800 text-surface-300 border border-surface-700">
                    Registered Prospect (0 Purchases)
                  </span>
                )}
              </div>

              <div className="flex flex-wrap items-center gap-4 text-xs text-surface-400 pt-1">
                <div className="flex items-center gap-1.5">
                  <Mail className="w-3.5 h-3.5 text-surface-500" />
                  <span className="text-surface-200">{customer.email}</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <Phone className="w-3.5 h-3.5 text-surface-500" />
                  <span>{customer.phone || 'No phone number'}</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <Calendar className="w-3.5 h-3.5 text-surface-500" />
                  <span>Joined {formatDate(customer.created_at)}</span>
                </div>
              </div>
            </div>
          </div>

          <button
            type="button"
            onClick={() => setShowEditModal(true)}
            className="btn-secondary flex items-center gap-2 text-xs self-start md:self-center"
          >
            <Edit2 className="w-3.5 h-3.5" /> Edit Profile
          </button>
        </div>
      </div>

      {/* KPI Stats Grid — Ground-Truth Verified Orders */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="card p-4 bg-surface-950 border border-surface-800">
          <div className="text-xs text-surface-400 flex items-center gap-1.5">
            <ShoppingBag className="w-3.5 h-3.5 text-brand-400" /> Total Orders
          </div>
          <div className="text-2xl font-bold text-white mt-1">
            {summary?.total_orders ?? 0}
          </div>
          <div className="text-[11px] text-surface-500 mt-0.5">Non-cancelled orders</div>
        </div>

        <div className="card p-4 bg-surface-950 border border-surface-800">
          <div className="text-xs text-surface-400 flex items-center gap-1.5">
            <CreditCard className="w-3.5 h-3.5 text-emerald-400" /> Total Spend
          </div>
          <div className="text-2xl font-bold text-emerald-400 mt-1">
            {formatCurrency(Number(summary?.total_spent ?? 0))}
          </div>
          <div className="text-[11px] text-surface-500 mt-0.5">Actual captured revenue</div>
        </div>

        <div className="card p-4 bg-surface-950 border border-surface-800">
          <div className="text-xs text-surface-400 flex items-center gap-1.5">
            <TrendingUp className="w-3.5 h-3.5 text-amber-400" /> Average Order Value
          </div>
          <div className="text-2xl font-bold text-white mt-1">
            {summary && summary.total_orders > 0
              ? formatCurrency(Number(summary.average_order_value))
              : '—'}
          </div>
          <div className="text-[11px] text-surface-500 mt-0.5">Derived basket size</div>
        </div>

        <div className="card p-4 bg-surface-950 border border-surface-800">
          <div className="text-xs text-surface-400 flex items-center gap-1.5">
            <Clock className="w-3.5 h-3.5 text-purple-400" /> Latest Order Date
          </div>
          <div className="text-sm font-bold text-white mt-2 truncate">
            {summary?.last_order_date ? formatDate(summary.last_order_date) : 'No orders yet'}
          </div>
          <div className="text-[11px] text-surface-500 mt-0.5">Recency indicator</div>
        </div>
      </div>

      {/* Purchase History Section */}
      <div className="card overflow-hidden">
        <div className="p-5 border-b border-surface-800 flex items-center justify-between">
          <div>
            <h2 className="text-base font-bold text-white flex items-center gap-2">
              <ShoppingBag className="w-4 h-4 text-brand-400" /> Real Purchase History
            </h2>
            <p className="text-xs text-surface-400 mt-0.5">
              Verified order records associated with {customer.name} in PostgreSQL.
            </p>
          </div>
          <span className="text-xs text-surface-400 font-mono">
            {orders.length} record{orders.length === 1 ? '' : 's'} found
          </span>
        </div>

        {orders.length === 0 ? (
          <div className="p-12 text-center space-y-3">
            <div className="w-12 h-12 rounded-xl bg-surface-800 flex items-center justify-center text-surface-400 mx-auto">
              <ShoppingBag className="w-6 h-6" />
            </div>
            <p className="text-white font-medium text-sm">No purchase history yet.</p>
            <p className="text-xs text-surface-400 max-w-sm mx-auto">
              This customer has not completed any orders under your store yet.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-surface-950/40 border-b border-surface-800 text-surface-400 font-mono">
                <tr>
                  <th className="px-6 py-3.5">Order Number</th>
                  <th className="px-6 py-3.5">Date</th>
                  <th className="px-6 py-3.5">Status</th>
                  <th className="px-6 py-3.5">Items Purchased</th>
                  <th className="px-6 py-3.5 text-right">Subtotal</th>
                  <th className="px-6 py-3.5 text-right">Total (INR)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-800/60">
                {orders.map(order => (
                  <tr key={order.id} className="hover:bg-surface-800/20 transition">
                    <td className="px-6 py-4 font-mono font-bold text-brand-400">
                      {order.order_number}
                    </td>
                    <td className="px-6 py-4 text-surface-300">
                      {formatDate(order.created_at)}
                    </td>
                    <td className="px-6 py-4">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${getStatusBadge(order.status)}`}>
                        {order.status}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-surface-300 max-w-xs">
                      {order.items && order.items.length > 0 ? (
                        <div className="space-y-1">
                          {order.items.slice(0, 3).map((item, idx) => (
                            <div key={idx} className="truncate">
                              <span className="font-semibold text-white">{item.quantity}x</span> {item.product_name}
                            </div>
                          ))}
                          {order.items.length > 3 && (
                            <div className="text-[10px] text-surface-500">
                              +{order.items.length - 3} more items
                            </div>
                          )}
                        </div>
                      ) : (
                        <span className="text-surface-500 italic">No line items</span>
                      )}
                    </td>
                    <td className="px-6 py-4 text-right text-surface-400 font-mono">
                      {formatCurrency(Number(order.subtotal))}
                    </td>
                    <td className="px-6 py-4 text-right text-white font-bold font-mono text-sm">
                      {formatCurrency(Number(order.total))}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Edit Customer Modal */}
      {showEditModal && customer && (
        <EditCustomerModal
          customer={customer}
          onClose={() => setShowEditModal(false)}
          onUpdated={updated => {
            setCustomer(updated);
            setShowEditModal(false);
            showToast(`Profile for '${updated.name}' saved.`);
          }}
        />
      )}
    </div>
  );
}

// --- Edit Customer Modal Subcomponent ---

function EditCustomerModal({
  customer,
  onClose,
  onUpdated,
}: {
  customer: Customer;
  onClose: () => void;
  onUpdated: (customer: Customer) => void;
}) {
  const [name, setName] = useState(customer.name);
  const [email, setEmail] = useState(customer.email);
  const [phone, setPhone] = useState(customer.phone || '');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!name.trim()) {
      setError('Customer name is required.');
      return;
    }
    if (!email.trim()) {
      setError('Email address is required.');
      return;
    }

    setSubmitting(true);
    try {
      const payload: CustomerUpdateRequest = {
        name: name.trim(),
        email: email.trim().toLowerCase(),
        phone: phone.trim() || null,
      };
      const res = await api.patch<Customer>(`/customers/${customer.id}`, payload);
      if (res.data) {
        onUpdated(res.data);
      }
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('Failed to update customer');
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div className="card p-6 w-full max-w-md animate-slide-up bg-surface-900 border border-surface-700 shadow-2xl">
        <div className="flex items-center justify-between mb-4 pb-3 border-b border-surface-800">
          <h2 className="text-lg font-bold text-white flex items-center gap-2">
            <Edit2 className="w-5 h-5 text-brand-400" /> Edit Customer Profile
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="text-surface-400 hover:text-white p-1 rounded-lg"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-surface-300 mb-1">
              Customer Full Name <span className="text-red-400">*</span>
            </label>
            <input
              type="text"
              required
              value={name}
              onChange={e => setName(e.target.value)}
              className="input-field w-full text-xs"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-surface-300 mb-1">
              Email Address <span className="text-red-400">*</span>
            </label>
            <input
              type="email"
              required
              value={email}
              onChange={e => setEmail(e.target.value)}
              className="input-field w-full text-xs"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-surface-300 mb-1">
              Phone Number <span className="text-surface-500 font-normal">(Optional)</span>
            </label>
            <input
              type="tel"
              value={phone}
              onChange={e => setPhone(e.target.value)}
              className="input-field w-full text-xs font-mono"
            />
          </div>

          {error && (
            <div className="p-3 bg-red-950/30 border border-red-500/40 rounded-xl text-xs text-red-300 flex items-start gap-2">
              <AlertTriangle className="w-4 h-4 shrink-0 text-red-400 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          <div className="flex justify-end gap-3 pt-2">
            <button type="button" onClick={onClose} className="btn-secondary text-xs">
              Cancel
            </button>
            <button type="submit" disabled={submitting} className="btn-primary text-xs">
              {submitting ? 'Saving...' : 'Save Changes'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
