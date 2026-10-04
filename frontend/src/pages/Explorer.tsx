import { lazy, useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useApi, useTaxonomy } from "../api";
const Plot = lazy(() => import("../components/Plot"));
const PAL = { blue: "#0072B2", orange: "#E69F00", green: "#009E73", pink: "#CC79A7", vermillion: "#D55E00" };
import { Card, ChartTable, DataState, Dir, LevelBadge, Select } from "../components/ui";
import { useAlertText, useFmt, useNames } from "../lib";

export default function Explorer() {
  const { t } = useTranslation(); const f = useFmt(); const nm = useNames(); const alertText = useAlertText();
  const [sp, setSp] = useSearchParams();
  const district = sp.get("district") || "MH-PUN", trade = sp.get("trade") || "REN01";
  const tax = useTaxonomy();
  const ts = useApi<any>(`/timeseries/${district}/${trade}`);
  const di = useApi<any>(`/demand-index/${district}/${trade}`);
  const set = (k: string, v: string) => { const n = new URLSearchParams(sp); n.set("district", district); n.set("trade", trade); n.set(k, v); setSp(n); };
  const d = ts.data;

  const series = useMemo(() => {
    if (!d) return null;
    const hm = d.history.map((r: any) => r.month), fm = d.forecast.map((r: any) => r.month);
    const all = [...hm, ...fm], sup = d.supply_monthly;
    return { hm, fm, all, sup };
  }, [d]);

  const tr = tax?.trades?.find((x: any) => x.code === trade);
  const g = d?.gap;
  const fx = (x: any[]) => x.map((m) => f.month(m));
  return (
    <div className="space-y-4 min-w-0">
      <h2 className="text-lg font-bold">{t("ex.title")}</h2>
      {tax && <div className="flex flex-wrap gap-3">
        <Select label={t("c.district")} value={district} onChange={(v) => set("district", v)} options={tax.districts.map((x: any) => [x.code, `${nm.district(x.code, x.name)} (${x.state})`])} />
        <Select label={t("c.trade")} value={trade} onChange={(v) => set("trade", v)} options={tax.trades.map((x: any) => [x.code, nm.trade(x.code, x.name)])} />
      </div>}
      <DataState loading={ts.loading} error={ts.error} onRetry={ts.reload} empty={!d}>
        {d && series && <>
          <div className="grid gap-3 md:grid-cols-4">
            <Card title={t("ex.summary", { h: 12 })} className="md:col-span-2">
              <dl className="grid grid-cols-2 gap-x-4 gap-y-1">
                <dt className="muted">{t("c.demand")}</dt><dd>{f.n(g?.demand)}</dd>
                <dt className="muted">{t("c.supply")}</dt><dd>{f.n(g?.supply)}</dd>
                <dt className="muted">{t("c.gap")}</dt><dd>{f.n(g?.gap)} ({f.pct(g?.gap_pct)}) {g && <Dir dir={g.direction} />}</dd>
                <dt className="muted">{t("c.severity")}</dt><dd>{f.n(g?.severity)}</dd>
                <dt className="muted">{t("c.seats")} / {t("c.suggested")}</dt><dd>{f.n(g?.seats)} → {f.n(g?.suggested_seats)}</dd>
                <dt className="muted">{t("c.confidence")}</dt><dd>{f.pct(g?.confidence)}</dd>
              </dl>
            </Card>
            <Card title={nm.trade(trade, tr?.name)} className="md:col-span-2">
              <dl className="grid grid-cols-2 gap-x-4 gap-y-1">
                <dt className="muted">{t("ex.nco")}</dt><dd>{tr?.nco_code}</dd>
                <dt className="muted">{t("ex.nsqf")}</dt><dd>{tr?.nsqf_level}</dd>
                <dt className="muted">{t("ex.ssc")}</dt><dd>{tr?.ssc}</dd>
                <dt className="muted">{t("c.sector")}</dt><dd>{tr && nm.sector(tr.sector)}</dd>
              </dl>
            </Card>
          </div>

          <Card title={t("ex.alerts")}>
            {d.alerts.length === 0 ? <p className="muted">{t("ex.none")}</p> : (
              <ul className="space-y-2">{d.alerts.map((a: any) => { const x = alertText(a); return (
                <li key={a.alert_key} className="border-l-4 pl-3" style={{ borderColor: "var(--short)" }}>
                  <div className="font-semibold">{t(`flag.${a.flag}`)} <LevelBadge level={a.level} /></div>
                  <div>{x.reason}</div><div className="muted">→ {x.action}</div></li>); })}</ul>)}
          </Card>

          <Card title={`${t("ex.forecast")} (${t("c.openings")})`} className="overflow-hidden">
            <ChartTable caption={t("ex.forecast")} columns={[t("c.month"), t("c.actual") + " / " + t("ex.forecast"), "80% low", "80% high", t("ex.supply_line")]}
              rows={[...d.history.map((r: any) => [f.month(r.month), f.n(r.openings_est, 1), "", "", f.n(series.sup, 1)]),
                ...d.forecast.map((r: any) => [f.month(r.month), f.n(r.yhat, 1), f.n(r.lo80, 1), f.n(r.hi80, 1), f.n(series.sup, 1)])]}
              chart={<Plot label={t("ex.forecast")} height={390} layout={{ xaxis: { categoryorder: "array", categoryarray: fx(series.all) } }} data={[
                { x: fx(series.fm), y: d.forecast.map((r: any) => r.hi95), mode: "lines", line: { width: 0 }, showlegend: false, hoverinfo: "skip" },
                { x: fx(series.fm), y: d.forecast.map((r: any) => r.lo95), mode: "lines", line: { width: 0 }, fill: "tonexty", fillcolor: "rgba(0,114,178,0.12)", name: t("ex.band95") },
                { x: fx(series.fm), y: d.forecast.map((r: any) => r.hi80), mode: "lines", line: { width: 0 }, showlegend: false, hoverinfo: "skip" },
                { x: fx(series.fm), y: d.forecast.map((r: any) => r.lo80), mode: "lines", line: { width: 0 }, fill: "tonexty", fillcolor: "rgba(0,114,178,0.28)", name: t("ex.band80") },
                { x: fx(series.hm), y: d.history.map((r: any) => r.openings_est), mode: "lines", name: t("c.actual"), line: { color: PAL.blue, width: 2 } },
                { x: fx(series.fm), y: d.forecast.map((r: any) => r.yhat), mode: "lines+markers", name: t("ex.forecast"), line: { color: PAL.vermillion, width: 2, dash: "dot" }, marker: { symbol: "diamond" } },
                { x: fx(series.all), y: series.all.map(() => series.sup), mode: "lines", name: t("ex.supply_line"), line: { color: PAL.green, width: 2, dash: "dash" } },
              ]} />} />
          </Card>

          <Card title={t("ex.gap_chart")} className="overflow-hidden">
            {(() => {
              const y = [...d.history.map((r: any) => r.openings_est), ...d.forecast.map((r: any) => r.yhat)].map((v: number) => v - series.sup);
              const x = fx(series.all);
              return <ChartTable caption={t("ex.gap_chart")} columns={[t("c.month"), t("c.gap"), t("c.direction")]}
                rows={y.map((v, i) => [x[i], f.n(v, 1), v > 0 ? t("c.shortage") : t("c.oversupply")])}
                chart={<Plot label={t("ex.gap_chart")} height={360} layout={{ xaxis: { categoryorder: "array", categoryarray: x } }} data={[
                  { x: x.filter((_, i) => y[i] > 0), y: y.filter((v) => v > 0), type: "bar", name: "▲ " + t("c.shortage"), marker: { color: PAL.orange } },
                  { x: x.filter((_, i) => y[i] <= 0), y: y.filter((v) => v <= 0), type: "bar", name: "▼ " + t("c.oversupply"), marker: { color: PAL.blue, pattern: { shape: "/" } } }]} />} />;
            })()}
          </Card>

          <Card title={t("ex.contrib")} className="overflow-hidden">
            <DataState loading={di.loading} error={di.error} empty={!di.data}>
              {di.data && (() => {
                const it = di.data.items; const srcs: [string, string][] = [["postings", PAL.blue], ["hiring", PAL.orange], ["plfs", PAL.green], ["eshram", PAL.pink]];
                return <ChartTable caption={t("ex.contrib")} columns={[t("c.month"), ...srcs.map(([s]) => t(`ex.src_${s}`)), t("c.confidence")]}
                  rows={it.map((r: any) => [f.month(r.month), ...srcs.map(([s]) => f.n(r[`o_${s}`], 1)), f.pct(r.confidence)])}
                  chart={<Plot label={t("ex.contrib")} height={360} layout={{ barmode: "relative" }} data={srcs.map(([s, c]) => ({ x: it.map((r: any) => f.month(r.month)), y: it.map((r: any) => r[`o_${s}`]), type: "bar", name: t(`ex.src_${s}`), marker: { color: c } }))} />} />;
              })()}
            </DataState>
          </Card>
        </>}
      </DataState>
    </div>
  );
}
