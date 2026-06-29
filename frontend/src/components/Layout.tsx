import { NavLink } from "react-router-dom";
import type { ReactNode } from "react";

const NAV = [
  { to: "/", label: "Home", short: "Home", desc: "Today at a glance", icon: "🏠", end: true },
  {
    to: "/forecast",
    label: "Customer & Staff Forecast",
    short: "Forecast",
    desc: "Expected customers + staffing",
    icon: "📈",
    end: false,
  },
  {
    to: "/orders",
    label: "Supplies to Order",
    short: "Supplies",
    desc: "Ingredients to buy ahead",
    icon: "📦",
    end: false,
  },
  {
    to: "/feedback",
    label: "Report Results",
    short: "Results",
    desc: "Enter what actually happened",
    icon: "✍️",
    end: false,
  },
];

export default function Layout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen flex flex-col md:flex-row">
      {/* Mobile top header — centered brand */}
      <header className="md:hidden sticky top-0 z-20 bg-white border-b border-slate-200 py-3 flex items-center justify-center gap-2">
        <span className="text-xl">🍽️</span>
        <span className="font-semibold text-slate-900 tracking-wide">RRPS</span>
      </header>

      {/* Desktop sidebar */}
      <aside className="hidden md:flex md:flex-col md:w-64 md:min-h-screen bg-white border-r border-slate-200 px-4 py-5 gap-1">
        <div className="flex items-center gap-2 px-2 pb-6">
          <span className="text-2xl">🍽️</span>
          <div>
            <div className="font-semibold text-slate-900 leading-tight">RRPS</div>
            <div className="text-xs text-slate-500 leading-tight">
              Restaurant planning
            </div>
          </div>
        </div>
        <nav className="flex flex-col gap-1">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `flex items-start gap-3 px-3 py-2 rounded-lg transition-colors ${
                  isActive
                    ? "bg-slate-900 text-white"
                    : "text-slate-600 hover:bg-slate-100"
                }`
              }
            >
              {({ isActive }) => (
                <>
                  <span className="text-base leading-6">{item.icon}</span>
                  <span className="flex flex-col">
                    <span className="text-sm font-medium leading-tight">
                      {item.label}
                    </span>
                    <span
                      className={`text-xs leading-tight mt-0.5 ${
                        isActive ? "text-slate-300" : "text-slate-400"
                      }`}
                    >
                      {item.desc}
                    </span>
                  </span>
                </>
              )}
            </NavLink>
          ))}
        </nav>
      </aside>

      {/* Main — extra bottom padding on mobile to clear the fixed tab bar */}
      <main className="flex-1 px-4 py-5 pb-24 md:px-8 md:py-8 md:pb-8 max-w-6xl w-full mx-auto">
        {children}
      </main>

      {/* Mobile bottom tab bar — 4 tabs, evenly spread, no scroll */}
      <nav className="md:hidden fixed bottom-0 inset-x-0 z-20 bg-white border-t border-slate-200 grid grid-cols-4 pb-[env(safe-area-inset-bottom)]">
        {NAV.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) =>
              `flex flex-col items-center justify-center gap-0.5 py-2 text-xs transition-colors ${
                isActive ? "text-slate-900" : "text-slate-400"
              }`
            }
          >
            {({ isActive }) => (
              <>
                <span className={`text-lg leading-none ${isActive ? "" : "opacity-70"}`}>
                  {item.icon}
                </span>
                <span className="leading-none font-medium">{item.short}</span>
              </>
            )}
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
