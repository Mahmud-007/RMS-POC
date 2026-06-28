import { NavLink } from "react-router-dom";
import type { ReactNode } from "react";

const NAV = [
  { to: "/", label: "Home", icon: "🏠", end: true },
  { to: "/forecast", label: "Forecast", icon: "📈", end: false },
  { to: "/orders", label: "Orders", icon: "📦", end: false },
  { to: "/feedback", label: "Feedback", icon: "✍️", end: false },
];

export default function Layout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen flex flex-col md:flex-row">
      {/* Sidebar */}
      <aside className="md:w-60 md:min-h-screen bg-white border-r border-slate-200 px-4 py-5 flex md:flex-col gap-1">
        <div className="flex items-center gap-2 px-2 pb-4 md:pb-6">
          <span className="text-2xl">🍽️</span>
          <div>
            <div className="font-semibold text-slate-900 leading-tight">RMS</div>
            <div className="text-xs text-slate-500 leading-tight">Forecasting</div>
          </div>
        </div>
        <nav className="flex md:flex-col gap-1 flex-1">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-slate-900 text-white"
                    : "text-slate-600 hover:bg-slate-100"
                }`
              }
            >
              <span>{item.icon}</span>
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>
      </aside>

      {/* Main */}
      <main className="flex-1 px-4 py-6 md:px-8 md:py-8 max-w-6xl w-full mx-auto">
        {children}
      </main>
    </div>
  );
}
