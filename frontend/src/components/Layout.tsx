import { NavLink } from "react-router-dom";
import type { ReactNode } from "react";

const NAV = [
  { to: "/", label: "Home", desc: "Today at a glance", icon: "🏠", end: true },
  {
    to: "/forecast",
    label: "Customer & Staff Forecast",
    desc: "Expected customers + staffing",
    icon: "📈",
    end: false,
  },
  {
    to: "/orders",
    label: "Supplies to Order",
    desc: "Ingredients to buy ahead",
    icon: "📦",
    end: false,
  },
  {
    to: "/feedback",
    label: "Report Results",
    desc: "Enter what actually happened",
    icon: "✍️",
    end: false,
  },
];

export default function Layout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen flex flex-col md:flex-row">
      {/* Sidebar */}
      <aside className="md:w-64 md:min-h-screen bg-white border-r border-slate-200 px-4 py-5 flex md:flex-col gap-1">
        <div className="flex items-center gap-2 px-2 pb-4 md:pb-6">
          <span className="text-2xl">🍽️</span>
          <div>
            <div className="font-semibold text-slate-900 leading-tight">RRPS</div>
            <div className="text-xs text-slate-500 leading-tight">
              Restaurant planning
            </div>
          </div>
        </div>
        <nav className="flex md:flex-col gap-1 flex-1 overflow-x-auto">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `flex items-start gap-3 px-3 py-2 rounded-lg transition-colors shrink-0 ${
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
                    <span className="text-sm font-medium leading-tight whitespace-nowrap md:whitespace-normal">
                      {item.label}
                    </span>
                    <span
                      className={`hidden md:block text-xs leading-tight mt-0.5 ${
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

      {/* Main */}
      <main className="flex-1 px-4 py-6 md:px-8 md:py-8 max-w-6xl w-full mx-auto">
        {children}
      </main>
    </div>
  );
}
