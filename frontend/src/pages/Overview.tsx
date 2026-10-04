import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { qs, useApi } from "../api";
import { Card, DataState, Dir, Field, Kpi, LevelBadge, Select, SortTable } from "../components/ui";
import { useFmt, useNames } from "../lib";

function Tile({ title, gp, dir, sub, onClick }: { title: string; gp: number; dir: string; sub: string; onClick?: () => void }) {
  const { t } = useTranslation(); const f = useFmt();
  const color = dir === "shortage" ? "var(--short)" : dir === "oversupply" ? "var(--over)" : "var(--muted)";
  return (
    <button onClick={onClick} className="card text-left w-full hover:shadow-md" style={{ borderLeft: `8px solid ${color}` }}
      aria-label={`${title}: ${t(`c.${dir}`)} ${f.pct(Math.abs(gp))}. ${sub}`}>
      <div className="font-semibold">{title}</div>
      <div style={{ color, fontWeight: 600 }}><span aria-hidden="true">{dir === "shortage" ? "▲" : dir === "oversupply" ? "▼" : "●"} </span>{t(`c.${dir}`)} {f.pct(Math.abs(gp))}</div>
      <div className="h-2 rounded mt-2" style={{ background: "var(--line)" }} aria-hidden="true">
        <div className="h-2 rounded" style={{ width: `${Math.min(Math.abs(gp), 1) * 100}%`, background: color }} /></div>
      <div className="muted text-sm mt-1">{sub}</div>
    </button>
  );
}

export default function Overview() {
  const { t } = useTranslation(); const f = useFmt(); const nm = useNames(); const nav = useNavigate();
  const [sel, setSel] = useState<{ state?: string; district?: string }>({});
  const [sector, setSector] = useState(""); const [horizon, setHorizon] = useState("12");
  const ov = useApi<any>(`/overview${qs({ horizon, sector })}`);
  const gp = useApi<any>(sel.district ? `/gap${qs({ district: sel.district, horizon, page_size: 50, sector })}` : null);
  const d = ov.data;
  const secOpts: [string, string][] = [["", t("c.all")], ["ELE", nm.sector("ELE")], ["REN", nm.sector("REN")], ["HLT", nm.sector("HLT")]];
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div><p className="text-xs font-semibold uppercase tracking-widest text-teal-700">{t("ov.eyebrow", { defaultValue: "MSDE · Planning intelligence" })}</p><h2 className="text-2xl font-bold mt-1">{t("ov.page_title", { defaultValue: "Labour demand and training alignment" })}</h2>
          <p className="muted mt-1 max-w-3xl">{t("ov.page_intro", { defaultValue: "Track forecast demand against expected trained supply, identify emerging gaps and explore pilot geographies." })}</p></div>
        <div className="flex flex-wrap gap-3 items-end rounded-xl border bg-white p-3" style={{ borderColor: "var(--line)" }}>
          <Select label={t("c.sector")} value={sector} onChange={setSector} options={secOpts} />
          <Select label={t("c.horizon")} value={horizon} onChange={setHorizon} options={[["6", "6"], ["12", "12"]]} />
        </div>
      </div>
      <DataState loading={ov.loading} error={ov.error} onRetry={ov.reload} empty={!d}>
        {d && <>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
            <Kpi label={t("ov.kpi_critical")} value={f.n(d.kpis.critical_alerts)} sub={`${f.n(d.kpis.warning_alerts)} ${t("lvl.warning")}`} />
            <Kpi label={t("ov.kpi_short")} value={d.kpis.top_shortage ? nm.trade(d.kpis.top_shortage.trade_code, d.kpis.top_shortage.trade) : "–"} sub={d.kpis.top_shortage && `${t("c.gap_pct")}: ${f.pct(d.kpis.top_shortage.gap_pct)}`} />
            <Kpi label={t("ov.kpi_over")} value={d.kpis.top_oversupply ? nm.trade(d.kpis.top_oversupply.trade_code, d.kpis.top_oversupply.trade) : "–"} sub={d.kpis.top_oversupply && `${t("c.gap_pct")}: ${f.pct(d.kpis.top_oversupply.gap_pct)}`} />
            <Kpi label={t("ov.kpi_refresh")} value={f.date(d.run.finished)} sub={d.run.run_id} />
            <Kpi label={t("ov.kpi_fresh")} value={t("ov.lag", { n: f.n(d.kpis.max_freshness_lag_months) })} sub={`${t("me.completeness")} ≥ ${f.pct(d.kpis.min_completeness)}`} />
          </div>
          <Card title={sel.district ? t("ov.trades_in") : sel.state ? t("ov.districts") : t("ov.states")}>
            <nav aria-label="Breadcrumb" className="flex flex-wrap gap-2 items-center mb-3">
              <button className="btn" onClick={() => setSel({})}>{t("c.national")}</button>
              {sel.state && <><span aria-hidden="true">›</span><button className="btn" onClick={() => setSel({ state: sel.state })}>{nm.state(sel.state)}</button></>}
              {sel.district && <><span aria-hidden="true">›</span><span aria-current="page" className="font-semibold">{nm.district(sel.district)}</span></>}
            </nav>
            <p className="muted text-sm mb-3">{t("ov.map_note")} {t("ov.bar_hint")}.</p>
            {!sel.state && (<>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {d.states.map((s: any) => <Tile key={s.state} title={nm.state(s.state)} gp={s.gap_pct} dir={s.direction} sub={`${f.n(s.critical)} ${t("c.critical_n")} · ${t("c.demand")}: ${f.n(s.demand)}`} onClick={() => setSel({ state: s.state })} />)}
              </div></>)}
            {sel.state && !sel.district && (<>
              <h3 className="font-semibold mb-2">{t("ov.districts")}</h3>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                {d.districts.filter((x: any) => x.state === sel.state).map((x: any) => <Tile key={x.district_code} title={nm.district(x.district_code, x.district)} gp={x.gap_pct} dir={x.direction}
                  sub={`${f.n(x.critical)} ${t("c.critical_n")} · ${t("c.severity")}: ${f.n(x.severity)}`} onClick={() => setSel({ state: sel.state, district: x.district_code })} />)}
              </div></>)}
            {sel.district && (<>
              <DataState loading={gp.loading} error={gp.error} onRetry={gp.reload} empty={!gp.data?.items?.length}>
                <SortTable defaultSort="severity" caption={t("ov.trades_in")} onRowClick={(r) => nav(`/explorer?district=${r.district_code}&trade=${r.trade_code}`)}
                  rows={gp.data?.items || []}
                  cols={[{ key: "trade", label: t("c.trade"), render: (r) => nm.trade(r.trade_code, r.trade) },
                    { key: "direction", label: t("c.direction"), render: (r) => <Dir dir={r.direction} /> },
                    { key: "gap_pct", label: t("c.gap_pct"), num: true, render: (r) => f.pct(r.gap_pct) },
                    { key: "demand", label: t("c.demand"), num: true, render: (r) => f.n(r.demand) },
                    { key: "supply", label: t("c.supply"), num: true, render: (r) => f.n(r.supply) },
                    { key: "severity", label: t("c.severity"), num: true, render: (r) => f.n(r.severity) },
                    { key: "flag_level", label: t("c.flag"), render: (r) => <LevelBadge level={r.flag_level} /> }]} />
                <p className="muted text-sm mt-2">{t("ov.open")} ↩</p>
              </DataState></>)}
          </Card>
        </>}
      </DataState>
    </div>
  );
}
