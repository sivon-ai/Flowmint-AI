import { NavLink, Outlet, useLocation } from 'react-router-dom';
import ThemeToggle from '../common/ThemeToggle';
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
  ShieldCheck,
  CheckSquare,
  FileText,
  DollarSign,
  GitBranch,
  FlaskConical,
  Award,
} from 'lucide-react';
import type { User } from '../../types';

interface Props {
  user: User;
  onLogout: () => void;
}

const navItems = [
  { to: '/judge', icon: Award, label: 'Judge Walkthrough', badge: 'JUDGE' },
  { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/copilot', icon: Bot, label: 'AI Copilot', badge: 'AI' },
  { to: '/opportunities', icon: Lightbulb, label: 'Opportunities' },
  { to: '/simulations', icon: TrendingUp, label: 'Simulations' },
  { to: '/approvals', icon: CheckSquare, label: 'Approvals', badge: 'HITL' },
  { to: '/policies', icon: ShieldCheck, label: 'Policy Engine' },
  { to: '/attribution', icon: DollarSign, label: 'Attribution', badge: 'ROI' },
  { to: '/traces', icon: GitBranch, label: 'Trace Viewer' },
  { to: '/evaluation', icon: FlaskConical, label: 'AI Evaluation', badge: '900' },
  { to: '/audit', icon: FileText, label: 'Audit Trail' },
  { to: '/products', icon: Package, label: 'Products' },
  { to: '/inventory', icon: Warehouse, label: 'Inventory' },
  { to: '/orders', icon: ShoppingCart, label: 'Orders' },
];

export default function DashboardLayout({ user, onLogout }: Props) {
  const location = useLocation();

  const isItemActive = (to: string, isActive: boolean) => {
    if (to === '/dashboard') {
      return location.pathname === '/dashboard';
    }
    if (to === '/judge') {
      return location.pathname === '/judge' || location.pathname.startsWith('/dashboard/judge');
    }
    return isActive;
  };

  return (
    <div className="min-h-screen flex">
      {/* Sidebar */}
      <aside className="w-64 bg-surface-900 border-r border-surface-700 flex flex-col">
        {/* Logo */}
        <div className="p-5 border-b border-surface-700/60">
          <div className="flex items-center gap-2.5">
            <div className="p-2 bg-brand-500/15 rounded-lg border border-brand-400/25">
              <Zap className="w-5 h-5 text-brand-400" />
            </div>
            <div>
              <div className="text-lg font-bold text-surface-200 tracking-tight leading-tight">Flowmint</div>
              <div className="text-[10px] font-semibold text-brand-400 uppercase tracking-widest">
                AI Revenue OS
              </div>
            </div>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
          {navItems.map(item => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/dashboard' || item.to === '/judge'}
              className={({ isActive }) =>
                isItemActive(item.to, isActive) ? 'nav-link-active' : 'nav-link'
              }
            >
              <item.icon className="w-4.5 h-4.5" />
              <span className="flex-1">{item.label}</span>
              {item.badge && (
                <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-brand-500/15 text-brand-400 border border-brand-400/30">
                  {item.badge}
                </span>
              )}
            </NavLink>
          ))}
        </nav>

        {/* User & Theme Toggle */}
        <div className="p-4 border-t border-surface-700/60 bg-surface-800/40">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-full bg-brand-500/20 border border-brand-400/30 flex items-center justify-center text-brand-400 text-sm font-bold">
              {user.full_name.charAt(0)}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium text-surface-200 truncate">{user.full_name}</div>
              <div className="text-xs text-surface-300 truncate">{user.email}</div>
            </div>
            <ThemeToggle />
            <button
              onClick={onLogout}
              className="p-1.5 rounded-lg text-surface-300 hover:text-danger-500 hover:bg-surface-700/50 transition-colors"
              title="Logout"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        {/* Persistent Demo / Seed Data Banner */}
        {user.email === 'admin@techmart.in' && (
          <div className="bg-amber-500/10 border-b border-amber-500/25 px-6 py-2.5 flex flex-wrap items-center justify-between gap-3 text-xs">
            <div className="flex items-center gap-2.5 text-amber-200">
              <span className="px-2 py-0.5 rounded font-mono font-bold bg-amber-500/20 text-amber-400 border border-amber-500/30">
                DEMO / EVALUATION DATASET
              </span>
              <span>
                Canonical scenario: <strong>TechMart India</strong> (37 carts, ₹1,42,000 at risk). All telemetry, products, orders, and customer profiles shown are simulated demonstration data.
              </span>
            </div>
            <NavLink
              to="/judge"
              className="text-amber-400 hover:text-amber-300 font-semibold underline underline-offset-2 flex items-center gap-1 shrink-0"
            >
              Open /judge Walkthrough &rarr;
            </NavLink>
          </div>
        )}
        <div className="p-6 lg:p-8 max-w-7xl mx-auto animate-fade-in">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
