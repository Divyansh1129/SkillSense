import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, useApi, useRole, useTaxonomy } from "../api";
import { Card, DataState, Field } from "../components/ui";
import { useFmt, useNames } from "../lib";

export default function Admin() {
  const { t } = useTranslation(); const f = useFmt(); const nm = useNames(); const tax = useTaxonomy(); const role = useRole();
  const isAdmin = role === "admin";
  const w = useApi<any>("/config/weights"), thr = useApi<any>(role === "viewer" ? null : "/config/thresholds");
  const st = useApi<any>("/pipeline/status"), rv = useApi<any>(role === "viewer" ? null : "/mapping/review");
  const [wt, setWt] = useState<Record<string, number>>({}), [th, setTh] = useState<Record<string, number>>({}), [msg, setMsg] = useState("");
  useEffect(() => { if (w.data) setWt(w.data.weights); }, [w.data]);
  useEffect(() => { if (thr.data) setTh(thr.data); }, [thr.data]);
  useEffect(() => { if (st.data?.status === "running") { const h = setTimeout(st.reload, 3000); return () => clearTimeout(h); } }, [st.data]);
  const sum = (Object.values(wt) as number[]).reduce((a: number, b: number) => a + b, 0);
  const guard = async (fn: () => Promise<any>, ok = "OK") => { try { await fn(); setMsg(ok); } catch (e: any) { setMsg(e.message); } };
  return (
    <div className="space-y-4">
      <h2 className="text-lg font-bold">{t("ad.title")}</h2>
      {!isAdmin && <p role="note" className="muted">{t("ad.admin_only")}</p>}
      {msg && <div role="status" className="card">{msg}</div>}
      <Card title={t("ad.weights")}>
        <DataState loading={w.loading} error={w.error} empty={!w.data}>
          <div className="grid gap-3 md:grid-cols-2">
            {Object.keys(wt).map((k) => (
              <Field key={k} label={`${t(`ex.src_${k}`)}: ${f.pct(wt[k])}`}>
                <input type="range" min={0} max={100} value={Math.round(wt[k] * 100)} disabled={!isAdmin} onChange={(e) => setWt({ ...wt, [k]: Number(e.target.value) / 100 })} />
                <span className="muted text-xs">{w.data?.rationale?.[k]}</span>
              </Field>))}
          </div>
          <p className={Math.abs(sum - 1) > 0.01 ? "text-red-600 font-semibold mt-2" : "mt-2"}>{t("ad.sum")}: {f.pct(sum)} {Math.abs(sum - 1) > 0.01 && `— ${t("ad.must_sum")}`}</p>
          <button className="btn btn-primary mt-2" disabled={!isAdmin || Math.abs(sum - 1) > 0.01} onClick={() => guard(async () => { await api("/config/weights", { method: "PUT", body: wt }); st.reload(); })}>{t("ad.save_weights")}</button>
        </DataState>
      </Card>
      <Card title={t("ad.pipeline")}>
        <div className="flex flex-wrap items-center gap-3">
          <button className="btn btn-primary" disabled={!isAdmin} onClick={() => guard(async () => { await api("/pipeline/run", { method: "POST", body: { from_stage: "ingest" } }); st.reload(); })}>{t("ad.run")}</button>
          <span aria-live="polite">{t("ad.status")}: {st.data ? `${st.data.run_id} — ${st.data.status}${st.data.stage ? ` (${st.data.stage})` : ""}` : "–"}</span>
        </div>
        {st.data?.error && <pre className="text-xs overflow-auto mt-2">{st.data.error}</pre>}
      </Card>
      <Card title={t("ad.thresholds")}>
        <DataState loading={thr.loading} error={thr.error} empty={!thr.data}>
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {Object.keys(th).map((k) => <Field key={k} label={k}><input type="number" step="0.01" value={th[k]} disabled={!isAdmin} onChange={(e) => setTh({ ...th, [k]: Number(e.target.value) })} /></Field>)}
          </div>
          <button className="btn btn-primary mt-2" disabled={!isAdmin} onClick={() => guard(() => api("/config/thresholds", { method: "PUT", body: th }))}>{t("ad.save_thr")}</button>
        </DataState>
      </Card>
      <Card title={t("ad.review")}>
        <DataState loading={rv.loading} error={rv.error} empty={!rv.data?.items?.length}>
          <div className="overflow-auto max-h-96">
            <table><caption className="sr-only">{t("ad.review")}</caption>
              <thead><tr><th scope="col">{t("ad.title_col")}</th><th scope="col">{t("ad.n")}</th><th scope="col">{t("ad.suggested")}</th><th scope="col">{t("c.confidence")}</th><th scope="col"></th></tr></thead>
              <tbody>{(rv.data?.items || []).slice(0, 50).map((r: any) => (
                <tr key={r.id}><td>{r.sample_title}</td><td>{f.n(r.n_postings)}</td><td>{nm.trade(r.suggested_trade, r.suggested_trade_name)}</td><td>{f.pct(r.confidence)}</td>
                  <td className="flex flex-wrap gap-1">
                    <button className="btn" disabled={role === "viewer"} onClick={() => guard(async () => { await api(`/mapping/review/${r.id}`, { method: "POST", body: { action: "approve" } }); rv.reload(); }, t("ad.applied"))}>{t("ad.approve")}</button>
                    <select aria-label={t("ad.reassign")} disabled={role === "viewer"} defaultValue="" onChange={(e) => e.target.value && guard(async () => { await api(`/mapping/review/${r.id}`, { method: "POST", body: { action: "reassign", trade_code: e.target.value } }); rv.reload(); }, t("ad.applied"))}>
                      <option value="">{t("ad.reassign")}</option>{(tax?.trades || []).map((x: any) => <option key={x.code} value={x.code}>{nm.trade(x.code, x.name)}</option>)}</select>
                    <button className="btn" disabled={role === "viewer"} onClick={() => guard(async () => { await api(`/mapping/review/${r.id}`, { method: "POST", body: { action: "reject" } }); rv.reload(); }, t("ad.applied"))}>{t("ad.reject")}</button>
                  </td></tr>))}</tbody>
            </table>
          </div>
        </DataState>
      </Card>
    </div>
  );
}
