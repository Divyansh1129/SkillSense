import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, download, qs, useRole, useTaxonomy } from "../api";
import { Card, DataState, Dir, Field, Select, SortTable } from "../components/ui";
import { useFmt, useNames } from "../lib";

export default function Workbench() {
  const { t } = useTranslation(); const f = useFmt(); const nm = useNames(); const tax = useTaxonomy(); const role = useRole();
  const [sc, setSc] = useState({ state: "", district: "UP-KNP", sector: "", trade: "ELE01" });
  const [mode, setMode] = useState("pct"), [val, setVal] = useState(-30), [horizon, setHorizon] = useState("12");
  const [budget, setBudget] = useState(""), [maxc, setMaxc] = useState(50);
  const [wi, setWi] = useState<any>(null), [wiErr, setWiErr] = useState<string | null>(null), [wiLoad, setWiLoad] = useState(false);
  const [rec, setRec] = useState<any>(null), [recErr, setRecErr] = useState<string | null>(null), [recLoad, setRecLoad] = useState(false);
  const scope = Object.fromEntries(Object.entries(sc).filter(([, v]) => v));

  useEffect(() => {  // instant what-if (debounced)
    const h = setTimeout(() => {
      setWiLoad(true); setWiErr(null);
      api("/whatif", { method: "POST", body: { ...scope, mode, value: val, horizon: Number(horizon) } }).then(setWi).catch((e) => { setWi(null); setWiErr(e.message); }).finally(() => setWiLoad(false));
    }, 250);
    return () => clearTimeout(h);
  }, [JSON.stringify(scope), mode, val, horizon, role]);

  const recommend = () => {
    setRecLoad(true); setRecErr(null);
    api("/recommend-targets", { method: "POST", body: { ...scope, budget: budget ? Number(budget) : null, max_change_pct: maxc } }).then(setRec).catch((e) => setRecErr(e.message)).finally(() => setRecLoad(false));
  };
  const o = (k: string, v: string) => setSc({ ...sc, [k]: v });
  const B = wi?.before, A = wi?.after;
  const Box = ({ title, x }: { title: string; x: any }) => (
    <Card title={title}>
      <dl className="grid grid-cols-2 gap-x-3 gap-y-1">
        <dt className="muted">{t("c.seats")}</dt><dd>{f.n(x.seats)}</dd>
        <dt className="muted">{t("c.demand")}</dt><dd>{f.n(x.demand)}</dd>
        <dt className="muted">{t("c.supply")}</dt><dd>{f.n(x.supply)}</dd>
        <dt className="muted">{t("c.gap")}</dt><dd>{f.n(x.gap)} ({f.pct(x.gap_pct)})</dd>
        <dt className="muted">{t("c.severity")}</dt><dd>{f.n(x.severity, 1)}</dd>
      </dl>
    </Card>);
  return (
    <div className="space-y-4">
      <h2 className="text-lg font-bold">{t("wb.title")}</h2>
      <Card title={t("wb.scope")}>
        <div className="flex flex-wrap gap-3">
          <Select label={t("c.state")} value={sc.state} onChange={(v) => o("state", v)} options={[["", t("c.all")], ...(tax?.states || []).map((s: any) => [s.code, nm.state(s.code)] as [string, string])]} />
          <Select label={t("c.sector")} value={sc.sector} onChange={(v) => o("sector", v)} options={[["", t("c.all")], ["ELE", nm.sector("ELE")], ["REN", nm.sector("REN")], ["HLT", nm.sector("HLT")]]} />
          <Select label={t("c.district")} value={sc.district} onChange={(v) => o("district", v)} options={[["", t("c.all")], ...(tax?.districts || []).map((d: any) => [d.code, nm.district(d.code, d.name)] as [string, string])]} />
          <Select label={t("c.trade")} value={sc.trade} onChange={(v) => o("trade", v)} options={[["", t("c.all")], ...(tax?.trades || []).map((x: any) => [x.code, nm.trade(x.code, x.name)] as [string, string])]} />
          <Select label={t("c.horizon")} value={horizon} onChange={setHorizon} options={[["6", "6"], ["12", "12"]]} />
        </div>
      </Card>
      <Card title={t("wb.change")}>
        <div className="flex flex-wrap gap-4 items-end">
          <Select label="" value={mode} onChange={(m) => { setMode(m); setVal(0); }} options={[["pct", t("wb.pct")], ["abs", t("wb.abs")]]} />
          <Field label={`${t("wb.change")}: ${val}${mode === "pct" ? "%" : ""}`}>
            <input type="range" aria-label={t("wb.change")} min={mode === "pct" ? -100 : -2000} max={mode === "pct" ? 200 : 2000} step={mode === "pct" ? 5 : 25} value={val} onChange={(e) => setVal(Number(e.target.value))} className="w-64" />
          </Field>
          <input type="number" aria-label={t("wb.change")} value={val} onChange={(e) => setVal(Number(e.target.value))} className="w-24" />
        </div>
      </Card>
      <DataState loading={wiLoad && !wi} error={wiErr === "Requires role 'analyst' (you are 'viewer')" ? t("wb.need_role") : wiErr} empty={!wi}>
        {wi && <>
          <p className="muted">{t("wb.series", { n: wi.n_series })}</p>
          <div className="grid gap-3 md:grid-cols-2" aria-live="polite"><Box title={t("wb.before")} x={B} /><Box title={t("wb.after")} x={A} /></div>
          <SortTable defaultSort="severity" caption={t("wb.title")} rows={wi.items} cols={[
            { key: "district", label: t("c.district"), render: (r) => nm.district(r.district_code, r.district) },
            { key: "trade", label: t("c.trade"), render: (r) => nm.trade(r.trade_code, r.trade) },
            { key: "seats", label: t("c.seats"), num: true, render: (r) => `${f.n(r.seats)} → ${f.n(r.seats_new)}` },
            { key: "gap", label: t("c.gap"), num: true, render: (r) => `${f.n(r.gap)} → ${f.n(r.gap_new)}` },
            { key: "severity", label: t("c.severity"), num: true, render: (r) => `${f.n(r.severity, 1)} → ${f.n(r.severity_new, 1)}` },
            { key: "direction_new", label: t("c.direction"), render: (r) => <Dir dir={r.direction_new} /> }]} />
        </>}
      </DataState>
      <Card title={t("wb.recommend")}>
        <p className="muted text-sm mb-2">{t("wb.reco_note")}</p>
        <div className="flex flex-wrap gap-3 items-end">
          <Field label={t("wb.budget")}><input type="number" value={budget} onChange={(e) => setBudget(e.target.value)} /></Field>
          <Field label={t("wb.max_change")}><input type="number" min={0} max={300} value={maxc} onChange={(e) => setMaxc(Number(e.target.value))} /></Field>
          <button className="btn btn-primary" onClick={recommend}>{t("wb.recommend")}</button>
          <button className="btn" onClick={() => download(`/export/targets.csv${qs(scope)}`)}>{t("wb.download")}</button>
        </div>
        <DataState loading={recLoad} error={recErr} empty={false}>
          {rec && <div className="mt-3">
            <p>{t("c.seats")}: {f.n(rec.total_seats_before)} → {f.n(rec.total_seats_after)} · {t("wb.abs_gap")}: {f.n(rec.abs_gap_before)} → {f.n(rec.abs_gap_after)}</p>
            <h3 className="font-semibold mt-2">{t("wb.reco_title")}</h3>
            <SortTable caption={t("wb.reco_title")} defaultSort="change" rows={rec.items} cols={[
              { key: "district", label: t("c.district"), render: (r) => nm.district(r.district_code, r.district) },
              { key: "trade", label: t("c.trade"), render: (r) => nm.trade(r.trade_code, r.trade) },
              { key: "seats", label: t("c.seats"), num: true, render: (r) => f.n(r.seats) },
              { key: "suggested_seats", label: t("c.suggested"), num: true, render: (r) => f.n(r.suggested_seats) },
              { key: "change", label: t("wb.change_col"), num: true, sortVal: (r) => Math.abs(r.change), render: (r) => (r.change > 0 ? "+" : "") + f.n(r.change) },
              { key: "gap_after", label: t("wb.gap_after"), num: true, render: (r) => f.n(r.gap_after) }]} />
          </div>}
        </DataState>
      </Card>
    </div>
  );
}
