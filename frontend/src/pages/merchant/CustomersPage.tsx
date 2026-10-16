import { useEffect, useState, useRef } from 'react';
import { Link } from 'react-router-dom';
import { api, ApiError } from '../../lib/api';
import type { Customer, CustomerCreateRequest, CustomerUpdateRequest } from '../../types';
import {
  Users,
  Search,
  UserPlus,
  Edit2,
  Eye,
  X,
  CheckCircle2,
  AlertTriangle,
  ChevronLeft,
  ChevronRight,
  Phone,
  Mail,
  Calendar,
  ShoppingBag,
} from 'lucide-react';

export default function CustomersPage() {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalCount, setTotalCount] = useState(0);

  // Modals state
  const [showAddModal, setShowAddModal] = useState(false);
  const [editingCustomer, setEditingCustomer] = useState<Customer | null>(null);
  const [successToast, setSuccessToast] = useState('');

  const searchTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const loadCustomers = async (currentPage = page, searchQuery = search) => {
    setLoading(true);
    try {
      const q = searchQuery.trim() ? `&q=${encodeURIComponent(searchQuery.trim())}` : '';
      const res = await api.get<Customer[]>(`/customers?page=${currentPage}&per_page=15${q}`);
      setCustomers(res.data || []);
      if (res.meta) {
        setPage(res.meta.page);
        setTotalPages(res.meta.total_pages);
        setTotalCount(res.meta.total);
      }
    } catch (err) {
      console.error('Failed to load customers:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadCustomers(page, search);
  }, [page]);

  const handleSearchChange = (value: string) => {
    setSearch(value);
    if (searchTimeoutRef.current) {
      clearTimeout(searchTimeoutRef.current);
    }
    searchTimeoutRef.current = setTimeout(() => {
      setPage(1);
      loadCustomers(1, value);
    }, 300);
  };

  const handleClearSearch = () => {
    setSearch('');
    setPage(1);
    loadCustomers(1, '');
  };

  const formatCurrency = (amount: number) =>
    new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 0,
    }).format(amount);

  const formatDate = (dateStr: string) => {
    try {
      return new Date(dateStr).toLocaleDateString('en-IN', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
      });
    } catch {
      return dateStr;
    }
  };

  const showNotification = (msg: string) => {
    setSuccessToast(msg);
    setTimeout(() => setSuccessToast(''), 4000);
  };

  return (
    <div className="space-y-6">
      {/* Toast Notification */}
      {successToast && (
        <div className="fixed top-5 right-5 z-50 flex items-center gap-2 px-4 py-3 bg-emerald-950 border border-emerald-500/40 text-emerald-300 rounded-xl shadow-2xl text-xs animate-slide-up">
          <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
          <span>{successToast}</span>
        </div>
      )}

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Users className="w-6 h-6 text-brand-400" /> Customers
          </h1>
          <p className="text-surface-300 text-sm mt-1">
            Manage customer profiles, understand purchase history, and review customer activity.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setShowAddModal(true)}
          className="btn-primary flex items-center gap-2 self-start sm:self-auto"
        >
          <UserPlus className="w-4 h-4" /> Add Customer
        </button>
      </div>

      {/* Search Input */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-surface-400" />
        <input
          type="text"
          value={search}
          onChange={e => handleSearchChange(e.target.value)}
          placeholder="Search customers by name, email, or phone number..."
          className="input-field w-full pl-10 pr-10"
        />
        {search && (
          <button
            type="button"
            onClick={handleClearSearch}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-surface-400 hover:text-white transition"
            title="Clear search"
          >
            <X className="w-4 h-4" />
          </button>
        )}
      </div>

      {/* Customers Table / Card Container */}
      <div className="card overflow-hidden">
        {loading ? (
          <div className="p-12 text-center text-surface-300 space-y-3">
            <div className="w-8 h-8 border-2 border-brand-500 border-t-transparent rounded-full animate-spin mx-auto" />
            <p className="text-xs">Loading customer records...</p>
          </div>
        ) : customers.length === 0 ? (
          <div className="p-12 text-center space-y-4">
            <div className="w-14 h-14 rounded-2xl bg-surface-800 flex items-center justify-center text-surface-400 mx-auto">
              <Users className="w-7 h-7" />
            </div>
            {search ? (
              <div className="space-y-2">
                <p className="text-white font-medium">No customers match your search</p>
                <p className="text-xs text-surface-400">
                  Try checking for spelling errors or search using an email or phone number.
                </p>
                <button
                  type="button"
                  onClick={handleClearSearch}
                  className="btn-secondary text-xs mt-2"
                >
                  Clear search
                </button>
              </div>
            ) : (
              <div className="space-y-2">
                <p className="text-white font-medium">No customers yet</p>
                <p className="text-xs text-surface-400">
                  Add your first customer to get started with profile tracking and order history.
                </p>
                <button
                  type="button"
                  onClick={() => setShowAddModal(true)}
                  className="btn-primary text-xs mt-2"
                >
                  <UserPlus className="w-4 h-4 mr-1.5 inline" /> Add Customer
                </button>
              </div>
            )}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="border-b border-surface-700/50 bg-surface-950/40">
                  <th className="table-header px-6 py-3.5 text-left">Customer</th>
                  <th className="table-header px-6 py-3.5 text-left">Email Address</th>
                  <th className="table-header px-6 py-3.5 text-left">Phone</th>
                  <th className="table-header px-6 py-3.5 text-center">Orders</th>
                  <th className="table-header px-6 py-3.5 text-right">Total Spent</th>
                  <th className="table-header px-6 py-3.5 text-right">Joined</th>
                  <th className="table-header px-6 py-3.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-800/60">
                {customers.map(c => (
                  <tr key={c.id} className="table-row">
                    {/* Name & Avatar */}
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        <div className="w-9 h-9 rounded-full bg-brand-500/15 border border-brand-500/30 text-brand-300 font-bold text-xs flex items-center justify-center shrink-0">
                          {c.name.charAt(0).toUpperCase()}
                        </div>
                        <div>
                          <Link
                            to={`/customers/${c.id}`}
                            className="text-sm font-semibold text-white hover:text-brand-400 transition"
                          >
                            {c.name}
                          </Link>
                          <div className="text-[11px] font-mono text-surface-500">
                            {c.id.slice(0, 8)}...
                          </div>
                        </div>
                      </div>
                    </td>

                    {/* Email */}
                    <td className="px-6 py-4 text-xs text-surface-300">
                      <div className="flex items-center gap-1.5">
                        <Mail className="w-3.5 h-3.5 text-surface-500 shrink-0" />
                        <span className="truncate max-w-[200px]">{c.email}</span>
                      </div>
                    </td>

                    {/* Phone */}
                    <td className="px-6 py-4 text-xs text-surface-300">
                      {c.phone ? (
                        <div className="flex items-center gap-1.5 font-mono">
                          <Phone className="w-3.5 h-3.5 text-surface-500 shrink-0" />
                          <span>{c.phone}</span>
                        </div>
                      ) : (
                        <span className="text-surface-500 italic text-[11px]">Not provided</span>
                      )}
                    </td>

                    {/* Orders Count */}
                    <td className="px-6 py-4 text-center">
                      <span className="px-2.5 py-1 rounded-full text-xs font-semibold bg-surface-800 text-surface-200 border border-surface-700">
                        {c.order_count} {c.order_count === 1 ? 'order' : 'orders'}
                      </span>
                    </td>

                    {/* Total Spent */}
                    <td className="px-6 py-4 text-right text-xs font-bold text-white">
                      {formatCurrency(Number(c.total_spent))}
                    </td>

                    {/* Joined Date */}
                    <td className="px-6 py-4 text-right text-xs text-surface-400">
                      {formatDate(c.created_at)}
                    </td>

                    {/* Actions */}
                    <td className="px-6 py-4 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <Link
                          to={`/customers/${c.id}`}
                          className="p-1.5 rounded-lg text-surface-400 hover:text-brand-400 hover:bg-surface-800 transition"
                          title="View customer profile"
                        >
                          <Eye className="w-4 h-4" />
                        </Link>
                        <button
                          type="button"
                          onClick={() => setEditingCustomer(c)}
                          className="p-1.5 rounded-lg text-surface-400 hover:text-white hover:bg-surface-800 transition"
                          title="Edit customer"
                        >
                          <Edit2 className="w-4 h-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination Bar */}
        {totalCount > 0 && (
          <div className="px-6 py-3.5 border-t border-surface-800 bg-surface-950/40 flex items-center justify-between text-xs text-surface-400">
            <div>
              Showing {customers.length} of {totalCount} customer{totalCount === 1 ? '' : 's'}
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="p-1.5 rounded-lg bg-surface-800 hover:bg-surface-700 disabled:opacity-30 text-white transition border border-surface-700"
                title="Previous page"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <span className="font-mono px-2">
                Page {page} of {totalPages}
              </span>
              <button
                type="button"
                onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
                className="p-1.5 rounded-lg bg-surface-800 hover:bg-surface-700 disabled:opacity-30 text-white transition border border-surface-700"
                title="Next page"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Add Customer Modal */}
      {showAddModal && (
        <AddCustomerModal
          onClose={() => setShowAddModal(false)}
          onCreated={newCustomer => {
            setShowAddModal(false);
            showNotification(`Customer '${newCustomer.name}' added successfully.`);
            loadCustomers(1, search);
          }}
        />
      )}

      {/* Edit Customer Modal */}
      {editingCustomer && (
        <EditCustomerModal
          customer={editingCustomer}
          onClose={() => setEditingCustomer(null)}
          onUpdated={updated => {
            setEditingCustomer(null);
            showNotification(`Customer '${updated.name}' updated successfully.`);
            loadCustomers(page, search);
          }}
        />
      )}
    </div>
  );
}

// --- Add Customer Modal Subcomponent ---

function AddCustomerModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: (customer: Customer) => void;
}) {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
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
      const payload: CustomerCreateRequest = {
        name: name.trim(),
        email: email.trim().toLowerCase(),
        phone: phone.trim() || null,
      };
      const res = await api.post<Customer>('/customers', payload);
      if (res.data) {
        onCreated(res.data);
      }
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('Failed to create customer');
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
            <UserPlus className="w-5 h-5 text-brand-400" /> Add New Customer
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
              placeholder="e.g. Priya Sharma"
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
              placeholder="e.g. priya@example.in"
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
              placeholder="e.g. +91 98765 43210"
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
              {submitting ? 'Creating...' : 'Save Customer'}
            </button>
          </div>
        </form>
      </div>
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
