import { useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { api, qs, useApi, useRole, useTaxonomy } from "../api";
import { Card, DataState, LevelBadge, Select } from "../components/ui";
import { useAlertText, useFmt, useNames } from "../lib";

function AlertCard({ a, onDone }: { a: any; onDone: () => void }) {
  const { t } = useTranslation(); const nm = useNames(); const text = useAlertText(); const f = useFmt(); const role = useRole();
  const canAcknowledge = role !== "viewer";
  const [note, setNote] = useState(a.ack?.note || ""); const [err, setErr] = useState("");
  const x = text(a);
  const act = async (status: string) => {
    try { await api(`/alerts/${a.id}/ack`, { method: "POST", body: { status, note } }); onDone(); } catch (e: any) { setErr(e.message); }
  };
  return (
    <li className="card">
      <div className="flex flex-wrap gap-2 items-center justify-between">
        <div className="font-semibold">{t(`flag.${a.flag}`)} <LevelBadge level={a.level} /></div>
        <div className="muted text-sm">{t("c.severity")}: {f.n(a.severity, 1)}</div>
      </div>
      <div className="mt-1"><Link className="underline" to={`/explorer?district=${a.district_code}&trade=${a.trade_code}`}>{nm.trade(a.trade_code, a.trade)} · {nm.district(a.district_code, a.district)}</Link></div>
      <p className="mt-1">{x.reason}</p>
      <p className="muted">→ {x.action}</p>
      <div className="flex flex-wrap gap-2 items-center mt-2">
        <label className="sr-only" htmlFor={`n${a.id}`}>{t("al.note")}</label>
        <input id={`n${a.id}`} placeholder={t("al.note")} value={note} onChange={(e) => setNote(e.target.value)} disabled={!canAcknowledge} />
        <button className="btn" disabled={!canAcknowledge} onClick={() => act("acknowledged")}>{t("al.ack")}</button>
        <button className="btn" disabled={!canAcknowledge} onClick={() => act("dismissed")}>{t("al.dismiss")}</button>
        {a.ack && <button className="btn" disabled={!canAcknowledge} onClick={() => act("open")}>{t("al.reopen")}</button>}
        <span className="muted text-sm">{t("al.status")}: {a.ack ? t(`al.${a.ack.status === "open" ? "open" : a.ack.status}`) : t("al.open")}</span>
      </div>
      {err && <div role="alert" className="text-red-600 mt-1">{err}</div>}
    </li>
  );
}

export default function Alerts() {
  const { t } = useTranslation(); const nm = useNames(); const tax = useTaxonomy(); const role = useRole();
  const [level, setLevel] = useState(""), [state, setState] = useState(""), [sector, setSector] = useState(""), [flag, setFlag] = useState(""), [dismissed, setDismissed] = useState(false);
  const r = useApi<any>(`/alerts${qs({ level, state, sector, flag, include_dismissed: dismissed })}`);
  const items = (r.data?.items || []).slice(0, 150);
  return (
    <div className="space-y-4">
      <h2 className="text-lg font-bold">{t("al.title")}</h2>
      {role === "viewer" && <p role="note" className="muted">{t("al.need_role")}</p>}
      <div className="flex flex-wrap gap-3 items-end">
        <Select label={t("c.level")} value={level} onChange={setLevel} options={[["", t("c.all")], ["critical", t("lvl.critical")], ["warning", t("lvl.warning")], ["watch", t("lvl.watch")]]} />
        <Select label={t("c.flag")} value={flag} onChange={setFlag} options={[["", t("c.all")], ...["ACUTE_SHORTAGE", "APPROACHING_SATURATION", "EMERGING_DEMAND", "DATA_LOW_CONFIDENCE"].map((k) => [k, t(`flag.${k}`)] as [string, string])]} />
        <Select label={t("c.state")} value={state} onChange={setState} options={[["", t("c.all")], ...(tax?.states || []).map((s: any) => [s.code, nm.state(s.code)] as [string, string])]} />
        <Select label={t("c.sector")} value={sector} onChange={setSector} options={[["", t("c.all")], ["ELE", nm.sector("ELE")], ["REN", nm.sector("REN")], ["HLT", nm.sector("HLT")]]} />
        <label className="flex items-center gap-2"><input type="checkbox" checked={dismissed} onChange={(e) => setDismissed(e.target.checked)} /> {t("al.show_dismissed")}</label>
        {r.data && <span className="muted">{t("al.count", { n: r.data.total })}</span>}
      </div>
      <DataState loading={r.loading} error={r.error} onRetry={r.reload} empty={!items.length}>
        <ul className="space-y-3">{items.map((a: any) => <AlertCard key={a.id + a.alert_key} a={a} onDone={r.reload} />)}</ul>
      </DataState>
    </div>
  );
}
