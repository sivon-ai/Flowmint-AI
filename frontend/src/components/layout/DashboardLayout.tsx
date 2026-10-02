import { NavLink, Outlet } from 'react-router-dom';
import {
  LayoutDashboard,
  Bot,
  Package,
  Warehouse,
  ShoppingCart,
  LogOut,
  Zap,
  ChevronRight,
  Lightbulb,
  TrendingUp,
} from 'lucide-react';
import type { User } from '../../types';

interface Props {
  user: User;
  onLogout: () => void;
}

const navItems = [
  { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/copilot', icon: Bot, label: 'AI Copilot', badge: 'AI' },
  { to: '/opportunities', icon: Lightbulb, label: 'Opportunities', badge: '2B' },
  { to: '/simulations', icon: TrendingUp, label: 'Simulations' },
  { to: '/products', icon: Package, label: 'Products' },
  { to: '/inventory', icon: Warehouse, label: 'Inventory' },
  { to: '/orders', icon: ShoppingCart, label: 'Orders' },
];

export default function DashboardLayout({ user, onLogout }: Props) {
  return (
    <div className="min-h-screen flex">
      {/* Sidebar */}
      <aside className="w-64 bg-surface-900/50 border-r border-surface-700/50 flex flex-col">
        {/* Logo */}
        <div className="p-5 border-b border-surface-700/50">
          <div className="flex items-center gap-2.5">
            <div className="p-2 bg-brand-600/20 rounded-lg">
              <Zap className="w-5 h-5 text-brand-400" />
            </div>
            <div>
              <div className="text-lg font-bold text-white tracking-tight">Flowmint</div>
              <div className="text-[10px] font-medium text-brand-400 uppercase tracking-widest">
                AI Revenue OS
              </div>
            </div>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-3 space-y-1">
          {navItems.map(item => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                isActive ? 'nav-link-active' : 'nav-link'
              }
            >
              <item.icon className="w-4.5 h-4.5" />
              <span className="flex-1">{item.label}</span>
              {item.badge && (
                <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-brand-500/20 text-brand-400 border border-brand-500/30">
                  {item.badge}
                </span>
              )}
            </NavLink>
          ))}

          {/* Phase 3 items (greyed out) */}
          <div className="pt-4 mt-4 border-t border-surface-700/50">
            <div className="px-3 py-1 text-[10px] font-semibold text-surface-300/40 uppercase tracking-widest">
              Coming in Phase 3
            </div>
            {['Policy Guardrails', 'Human Approvals', 'Autonomous Execution', 'Audit Trail'].map(label => (
              <div key={label} className="nav-link opacity-30 cursor-not-allowed">
                <ChevronRight className="w-4 h-4" />
                <span>{label}</span>
              </div>
            ))}
          </div>
        </nav>

        {/* User */}
        <div className="p-4 border-t border-surface-700/50">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-brand-600/30 flex items-center justify-center text-brand-400 text-sm font-bold">
              {user.full_name.charAt(0)}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium text-white truncate">{user.full_name}</div>
              <div className="text-xs text-surface-300 truncate">{user.email}</div>
            </div>
            <button
              onClick={onLogout}
              className="p-1.5 rounded-lg text-surface-300 hover:text-danger-500 hover:bg-surface-800 transition-colors"
              title="Logout"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        <div className="p-6 lg:p-8 max-w-7xl mx-auto animate-fade-in">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
