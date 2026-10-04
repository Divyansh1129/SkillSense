import { Suspense, lazy, useEffect, useRef, useState } from "react";
import { NavLink, Route, Routes, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { LANGS } from "./i18n";
import { getRole, setRole } from "./api";
import { UiCtx } from "./components/ui";
const Overview = lazy(() => import("./pages/Overview"));
const Explorer = lazy(() => import("./pages/Explorer"));
const Rankings = lazy(() => import("./pages/Rankings"));
const Alerts = lazy(() => import("./pages/Alerts"));
const Workbench = lazy(() => import("./pages/Workbench"));
const Methodology = lazy(() => import("./pages/Methodology"));
const Admin = lazy(() => import("./pages/Admin"));

const NAV: [string, string, string][] = [["/", "overview", "▦"], ["/explorer", "explorer", "⌕"], ["/rankings", "rankings", "↕"], ["/alerts", "alerts", "◉"], ["/workbench", "workbench", "◇"], ["/methodology", "methodology", "≋"], ["/admin", "admin", "⚙"]];

export default function App() {
  const { t, i18n } = useTranslation();
  const location = useLocation();
  const [hc, setHc] = useState(localStorage.getItem("ss_hc") === "1");
  const [size, setSize] = useState(Number(localStorage.getItem("ss_size") || 100));
  const [selectedRole, setSelectedRole] = useState(getRole());
  const [roleMenuOpen, setRoleMenuOpen] = useState(false);
  const roleMenuRef = useRef<HTMLDivElement>(null);
  useEffect(() => { document.documentElement.classList.toggle("hc", hc); localStorage.setItem("ss_hc", hc ? "1" : "0"); }, [hc]);
  useEffect(() => { document.documentElement.style.fontSize = `${size}%`; localStorage.setItem("ss_size", String(size)); }, [size]);
  useEffect(() => {
    if (!roleMenuOpen) return;
    const closeOutside = (event: MouseEvent) => {
      if (!roleMenuRef.current?.contains(event.target as Node)) setRoleMenuOpen(false);
    };
    document.addEventListener("mousedown", closeOutside);
    return () => document.removeEventListener("mousedown", closeOutside);
  }, [roleMenuOpen]);
  useEffect(() => {
    if (roleMenuOpen) roleMenuRef.current?.querySelector<HTMLButtonElement>('[role="menuitemradio"]')?.focus();
  }, [roleMenuOpen]);
  return (
    <UiCtx.Provider value={{ hc }}>
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:bg-white focus:text-black focus:p-2">Skip to content</a>
      <div className="app-shell md:flex">
      <aside className="sidebar md:fixed md:inset-y-0 md:left-0 md:w-64 md:flex md:flex-col md:px-4 md:py-6 px-4 py-4 z-10">
        <div className="mb-8 rounded-xl bg-white px-2 shadow-lg shadow-black/10">
          <img className="brand-logo" src="/skillsense-logo.png" alt="SkillSense labour intelligence" />
        </div>
        <div className="px-3 mb-2 text-[10px] font-bold uppercase tracking-[.18em] text-slate-400">Workspace</div>
        <nav className="side-nav space-y-1" aria-label="Main navigation">
          {NAV.map(([to, k, icon]) => <NavLink key={to} to={to} end={to === "/"} className={({ isActive }) => `sidebar-link ${isActive ? "active" : ""}`}>
            <span className="nav-icon" aria-hidden="true">{icon}</span><span>{t(`nav.${k}`)}</span>
          </NavLink>)}
        </nav>
        <div className="hidden md:block mt-auto rounded-2xl border border-white/10 bg-gradient-to-br from-white/10 to-white/[.03] p-4 text-xs text-slate-300 leading-relaxed">
          <div className="flex items-center gap-2 mb-2"><span className="w-2 h-2 rounded-full bg-amber-300 shadow-[0_0_10px_rgba(252,211,77,.7)]"/><div className="font-semibold text-white">{t("app.title")}</div></div>
          {t("app.subtitle")}
        </div>
      </aside>
      <div className="min-w-0 flex-1 md:ml-64">
      <header className="border-b sticky top-0 z-[5]" style={{ borderColor: "var(--line)" }}>
        <div className="px-5 lg:px-8 py-3.5 flex flex-wrap items-center justify-between gap-3">
          <div><div className="text-[10px] font-bold uppercase tracking-[.18em] muted">{t("app.subtitle")}</div><h1 className="font-bold text-lg mt-0.5">{t(`nav.${NAV.find(([to]) => to === location.pathname)?.[1] || "overview"}`)}</h1></div>
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <label className="sr-only" htmlFor="language-select">{t("c.language")}</label>
            <select id="language-select" value={i18n.language} onChange={(e) => i18n.changeLanguage(e.target.value)}>{LANGS.map(([c, n]) => <option key={c} value={c}>{n}</option>)}</select>
            <div role="group" aria-label={t("c.text_size")} className="flex items-center gap-1">
              <button className="btn" aria-label="Decrease text size" onClick={() => setSize(Math.max(85, size - 10))}>A−</button>
              <button className="btn" aria-label="Increase text size" onClick={() => setSize(Math.min(150, size + 10))}>A+</button>
            </div>
            <button className="btn" aria-pressed={hc} onClick={() => setHc(!hc)}>{t("c.contrast")}</button>
            <div ref={roleMenuRef} className="role-picker">
              <span className="role-label">{t("c.role")}</span>
              <button type="button" id="role-select" className="role-trigger" aria-label={`${t("c.role")}: ${selectedRole}`} aria-haspopup="menu" aria-expanded={roleMenuOpen}
                onClick={() => setRoleMenuOpen((open) => !open)} onKeyDown={(event) => { if (event.key === "Escape") setRoleMenuOpen(false); }}>
                {selectedRole === "viewer" ? "Viewer" : selectedRole === "analyst" ? "Analyst" : "Admin"}
                <span className={`role-chevron ${roleMenuOpen ? "open" : ""}`} aria-hidden="true" />
              </button>
              {roleMenuOpen && <div className="role-menu" role="menu" aria-labelledby="role-select" onKeyDown={(event) => {
                const options = Array.from(event.currentTarget.querySelectorAll<HTMLButtonElement>('[role="menuitemradio"]'));
                const current = options.indexOf(document.activeElement as HTMLButtonElement);
                if (event.key === "Escape") { event.preventDefault(); setRoleMenuOpen(false); document.getElementById("role-select")?.focus(); }
                else if (event.key === "ArrowDown" || event.key === "ArrowUp" || event.key === "Home" || event.key === "End") {
                  event.preventDefault();
                  const next = event.key === "Home" ? 0 : event.key === "End" ? options.length - 1 : (current + (event.key === "ArrowDown" ? 1 : -1) + options.length) % options.length;
                  options[next]?.focus();
                }
              }}>
                {(["viewer", "analyst", "admin"] as const).map((role) => <button type="button" role="menuitemradio" aria-checked={selectedRole === role} key={role}
                  className="role-option" onClick={() => { setRole(role); setSelectedRole(role); setRoleMenuOpen(false); }}>
                  <span>{role[0].toUpperCase() + role.slice(1)}</span>{selectedRole === role && <span aria-hidden="true">✓</span>}
                </button>)}
              </div>}
            </div>
          </div>
        </div>
      </header>
      <div className="demo-banner px-5 lg:px-8 py-2 text-sm" role="note"><span className="font-bold">⚠ {t("app.demo")}</span><span className="ml-2">{t("app.demo_long")}</span></div>
      <main id="main" className="max-w-[1600px] mx-auto p-5 lg:p-8">
        <Suspense fallback={<div className="muted card" role="status">{t("c.loading")}</div>}>
          <Routes>
            <Route path="/" element={<Overview />} />
            <Route path="/explorer" element={<Explorer />} />
            <Route path="/rankings" element={<Rankings />} />
            <Route path="/alerts" element={<Alerts />} />
            <Route path="/workbench" element={<Workbench />} />
            <Route path="/methodology" element={<Methodology />} />
            <Route path="/admin" element={<Admin />} />
          </Routes>
        </Suspense>
      </main>
      <footer className="px-5 lg:px-8 pb-6 text-xs muted">SkillSense · Decision support for skilling planners <span className="mx-1">·</span> Forecasts are indicative and require planner review.</footer>
      </div>
      </div>
    </UiCtx.Provider>
  );
}
