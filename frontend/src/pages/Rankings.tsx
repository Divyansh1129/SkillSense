import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { download, qs, useApi, useTaxonomy } from "../api";
import { Card, DataState, Dir, LevelBadge, Select, SortTable } from "../components/ui";
import { useFmt, useNames } from "../lib";

export default function Rankings() {
  const { t } = useTranslation(); const f = useFmt(); const nm = useNames(); const nav = useNavigate(); const tax = useTaxonomy();
  const [type, setType] = useState("shortage"), [level, setLevel] = useState("trade"), [state, setState] = useState(""), [sector, setSector] = useState(""), [horizon, setHorizon] = useState("12"), [top, setTop] = useState("15");
  const r = useApi<any>(`/ranking${qs({ type, level, state, sector, horizon, top })}`);
  const flt = { state, sector };
  const cols: any[] = [];
  if (level === "state") cols.push({ key: "state", label: t("c.state"), render: (x: any) => nm.state(x.state) });
  if (level === "district") cols.push({ key: "district", label: t("c.district"), render: (x: any) => nm.district(x.district_code, x.district) }, { key: "state", label: t("c.state"), render: (x: any) => nm.state(x.state) });
  if (level === "trade") cols.push({ key: "district", label: t("c.district"), render: (x: any) => nm.district(x.district_code, x.district) }, { key: "trade", label: t("c.trade"), render: (x: any) => nm.trade(x.trade_code, x.trade) });
  cols.push({ key: "direction", label: t("c.direction"), render: (x: any) => <Dir dir={x.direction} /> },
    { key: "severity", label: t("c.severity"), num: true, render: (x: any) => f.n(x.severity, 1) },
    { key: "gap", label: t("c.gap"), num: true, render: (x: any) => f.n(x.gap) },
    { key: "gap_pct", label: t("c.gap_pct"), num: true, render: (x: any) => f.pct(x.gap_pct) },
    { key: "demand", label: t("c.demand"), num: true, render: (x: any) => f.n(x.demand) },
    { key: "supply", label: t("c.supply"), num: true, render: (x: any) => f.n(x.supply) });
  if (level === "trade") cols.push({ key: "seats", label: t("c.seats"), num: true, render: (x: any) => f.n(x.seats) }, { key: "suggested_seats", label: t("c.suggested"), num: true, render: (x: any) => f.n(x.suggested_seats) }, { key: "flag_level", label: t("c.flag"), render: (x: any) => <LevelBadge level={x.flag_level} /> });
  else cols.push({ key: "critical", label: t("rk.critical"), num: true, render: (x: any) => f.n(x.critical) });
  return (
    <div className="space-y-4">
      <h2 className="text-lg font-bold">{t("rk.title")}</h2>
      <div className="flex flex-wrap gap-3 items-end">
        <Select label={t("rk.by")} value={type} onChange={setType} options={[["shortage", t("c.shortage")], ["oversupply", t("c.oversupply")]]} />
        <Select label="Level" value={level} onChange={setLevel} options={[["trade", t("rk.lv_trade")], ["district", t("rk.lv_district")], ["state", t("rk.lv_state")]]} />
        <Select label={t("c.state")} value={state} onChange={setState} options={[["", t("c.all")], ...(tax?.states || []).map((s: any) => [s.code, nm.state(s.code)] as [string, string])]} />
        <Select label={t("c.sector")} value={sector} onChange={setSector} options={[["", t("c.all")], ["ELE", nm.sector("ELE")], ["REN", nm.sector("REN")], ["HLT", nm.sector("HLT")]]} />
        <Select label={t("c.horizon")} value={horizon} onChange={setHorizon} options={[["6", "6"], ["12", "12"]]} />
        <Select label={t("c.top")} value={top} onChange={setTop} options={[["10", "10"], ["15", "15"], ["30", "30"], ["60", "60"]]} />
      </div>
      <Card>
        <DataState loading={r.loading} error={r.error} onRetry={r.reload} empty={!r.data?.items?.length}>
          <SortTable cols={cols} rows={r.data?.items || []} defaultSort="severity" caption={t("rk.title")}
            onRowClick={level === "trade" ? (x) => nav(`/explorer?district=${x.district_code}&trade=${x.trade_code}`) : undefined} />
        </DataState>
      </Card>
      <Card title={`${t("rk.downloads")} (${t("c.export")})`}>
        <div className="flex flex-wrap gap-2">
          <button className="btn" onClick={() => download(`/export/forecast.csv${qs(flt)}`)}>{t("rk.forecast_csv")}</button>
          <button className="btn" onClick={() => download(`/export/forecast.xlsx${qs(flt)}`)}>{t("rk.forecast_xlsx")}</button>
          <button className="btn" onClick={() => download(`/export/forecast.json${qs(flt)}`)}>{t("rk.forecast_json")}</button>
          <button className="btn" onClick={() => download(`/export/targets.csv${qs(flt)}`)}>{t("rk.targets_csv")}</button>
        </div>
      </Card>
    </div>
  );
}
