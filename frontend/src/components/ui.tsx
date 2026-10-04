import { createContext, ReactNode, useContext, useState } from "react";
import { useTranslation } from "react-i18next";

export const UiCtx = createContext<{ hc: boolean }>({ hc: false });
export const useUi = () => useContext(UiCtx);

export function Card({ title, children, className = "" }: { title?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`card ${className}`}>
      {title && <h2 className="font-semibold mb-2">{title}</h2>}
      {children}
    </section>
  );
}

export function Kpi({ label, value, sub }: { label: string; value: ReactNode; sub?: ReactNode }) {
  return (
    <div className="card kpi-card">
      <div className="flex items-center justify-between gap-2"><div className="muted text-xs font-bold uppercase tracking-wider">{label}</div><span className="kpi-mark" aria-hidden="true" /></div>
      <div className="text-xl font-bold mt-3 leading-tight">{value}</div>
      {sub && <div className="muted text-sm mt-2">{sub}</div>}
    </div>
  );
}

/** Loading / error / empty states for every data view. */
export function DataState({ loading, error, empty, onRetry, children }: { loading?: boolean; error?: string | null; empty?: boolean; onRetry?: () => void; children: ReactNode }) {
  const { t } = useTranslation();
  if (loading) return <div role="status" aria-live="polite" className="muted p-4">{t("c.loading")}</div>;
  if (error) return (
    <div role="alert" className="card border-red-600">
      <strong>{t("c.error")}</strong>: {error} {onRetry && <button className="btn ml-2" onClick={onRetry}>{t("c.retry")}</button>}
    </div>
  );
  if (empty) return <div className="muted p-4">{t("c.empty")}</div>;
  return <>{children}</>;
}

export function Dir({ dir }: { dir: string }) {
  const { t } = useTranslation();
  const icon = dir === "shortage" ? "▲" : dir === "oversupply" ? "▼" : "●";
  const color = dir === "shortage" ? "var(--short)" : dir === "oversupply" ? "var(--over)" : "var(--muted)";
  return <span style={{ color, fontWeight: 600 }}><span aria-hidden="true">{icon} </span>{t(`c.${dir}`)}</span>;
}

export function LevelBadge({ level }: { level?: string | null }) {
  const { t } = useTranslation();
  if (!level) return <span className="muted">–</span>;
  const icon = level === "critical" ? "⛔" : level === "warning" ? "⚠" : "◔";
  return <span className="border rounded px-1.5 py-0.5 text-sm whitespace-nowrap" style={{ borderColor: "var(--line)" }}><span aria-hidden="true">{icon} </span>{t(`lvl.${level}`)}</span>;
}

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return <label className="flex flex-col text-sm gap-1"><span className="muted">{label}</span>{children}</label>;
}

export function Select({ label, value, onChange, options }: { label: string; value: string; onChange: (v: string) => void; options: [string, string][] }) {
  return (
    <Field label={label}>
      <select value={value} onChange={(e) => onChange(e.target.value)}>
        {options.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
      </select>
    </Field>
  );
}

/** Chart with a text/table alternative (WCAG). */
export function ChartTable({ chart, columns, rows, caption }: { chart: ReactNode; columns: string[]; rows: (string | number)[][]; caption: string }) {
  const { t } = useTranslation();
  const [asTable, setAsTable] = useState(false);
  return (
    <div>
      <div className="flex justify-end mb-1">
        <button className="btn text-sm" aria-pressed={asTable} onClick={() => setAsTable(!asTable)}>{asTable ? t("c.view_chart") : t("c.view_table")}</button>
      </div>
      {asTable ? (
        <div className="overflow-auto max-h-80">
          <table><caption className="sr-only">{caption}</caption>
            <thead><tr>{columns.map((c) => <th key={c} scope="col">{c}</th>)}</tr></thead>
            <tbody>{rows.map((r, i) => <tr key={i}>{r.map((v, j) => <td key={j}>{v}</td>)}</tr>)}</tbody>
          </table>
        </div>
      ) : chart}
    </div>
  );
}

export type Col = { key: string; label: string; render?: (row: any) => ReactNode; num?: boolean; sortVal?: (row: any) => any };

export function SortTable({ cols, rows, onRowClick, caption, defaultSort }: { cols: Col[]; rows: any[]; onRowClick?: (r: any) => void; caption?: string; defaultSort?: string }) {
  const [sort, setSort] = useState<{ k: string; dir: 1 | -1 }>({ k: defaultSort || "", dir: -1 });
  const col = cols.find((c) => c.key === sort.k);
  const sorted = col ? [...rows].sort((a, b) => {
    const va = col.sortVal ? col.sortVal(a) : a[col.key], vb = col.sortVal ? col.sortVal(b) : b[col.key];
    return (va > vb ? 1 : va < vb ? -1 : 0) * sort.dir;
  }) : rows;
  return (
    <div className="overflow-auto">
      <table>
        {caption && <caption className="sr-only">{caption}</caption>}
        <thead><tr>{cols.map((c) => (
          <th key={c.key} scope="col" aria-sort={sort.k === c.key ? (sort.dir === 1 ? "ascending" : "descending") : "none"} className={c.num ? "text-right" : ""}>
            <button className="font-semibold" onClick={() => setSort({ k: c.key, dir: sort.k === c.key ? ((-sort.dir) as 1 | -1) : -1 })}>
              {c.label}{sort.k === c.key ? (sort.dir === 1 ? " ↑" : " ↓") : ""}
            </button>
          </th>))}</tr></thead>
        <tbody>
          {sorted.map((r, i) => (
            <tr key={i} className={onRowClick ? "cursor-pointer hover:bg-slate-100 hover:text-black" : ""} onClick={() => onRowClick?.(r)}
                tabIndex={onRowClick ? 0 : undefined} onKeyDown={(e) => { if (onRowClick && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); onRowClick(r); } }}>
              {cols.map((c) => <td key={c.key} className={c.num ? "text-right" : ""}>{c.render ? c.render(r) : r[c.key]}</td>)}
            </tr>))}
        </tbody>
      </table>
    </div>
  );
}
