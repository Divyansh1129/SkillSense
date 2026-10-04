import { useTranslation } from "react-i18next";
import { useApi } from "../api";
import { Card, DataState, SortTable } from "../components/ui";
import { useFmt } from "../lib";

export default function Methodology() {
  const { t } = useTranslation(); const f = useFmt();
  const w = useApi<any>("/config/weights"), src = useApi<any>("/meta/sources"), mq = useApi<any>("/meta/mapping-quality"), bt = useApi<any>("/meta/model-quality");
  const items = t("me.items", { returnObjects: true }) as unknown as string[];
  const formulas = t("me.formulas", { returnObjects: true }) as unknown as string[];
  const metric = (scope: string, model: string, m: string) => bt.data?.metrics?.find((x: any) => x.scope === scope && x.model === model && x.metric === m)?.value;
  const rows = ["snaive", "harmonic", "gbm", "ensemble"].map((m) => ({ model: m, wape: metric("all_bottom", m, "wape"), smape: metric("all_bottom", m, "smape"), mape: metric("all_bottom", m, "mape"), c80: m === "ensemble" ? metric("all_bottom", m, "coverage_80") : null, c95: m === "ensemble" ? metric("all_bottom", m, "coverage_95") : null }));
  return (
    <div className="space-y-4">
      <h2 className="text-lg font-bold">{t("me.title")}</h2>
      <Card><p>{t("me.intro")}</p></Card>
      <Card title={t("me.formula")}><ul className="list-disc pl-5 space-y-1">{formulas.map((x, i) => <li key={i}><code>{x}</code></li>)}</ul></Card>
      <Card title={t("me.weights")}>
        <DataState loading={w.loading} error={w.error} empty={!w.data}>
          {w.data && <SortTable caption={t("me.weights")} rows={Object.keys(w.data.weights).map((k) => ({ k, w: w.data.weights[k], r: w.data.rationale[k] }))}
            cols={[{ key: "k", label: t("me.source"), render: (r) => t(`ex.src_${r.k}`) }, { key: "w", label: t("me.weight"), num: true, render: (r) => f.pct(r.w) }, { key: "r", label: t("me.rationale") }]} />}
        </DataState>
      </Card>
      <Card title={t("me.freshness")}>
        <DataState loading={src.loading} error={src.error} empty={!src.data}>
          {src.data && <SortTable caption={t("me.freshness")} rows={src.data.items} cols={[
            { key: "source", label: t("me.source"), render: (r) => t(`ex.src_${r.source}`, { defaultValue: r.source }) },
            { key: "rows_raw", label: t("me.rows"), num: true, render: (r) => f.n(r.rows_raw) },
            { key: "rows_rejected", label: t("me.rejected"), num: true, render: (r) => f.n(r.rows_rejected) },
            { key: "dups", label: t("me.dups"), num: true, render: (r) => f.n((r.exact_duplicates || 0) + (r.near_duplicates || 0)) },
            { key: "completeness", label: t("me.completeness"), num: true, render: (r) => f.pct(r.completeness, 1) },
            { key: "latest_period", label: t("me.latest") },
            { key: "freshness_lag_months", label: t("me.lag"), num: true, render: (r) => f.n(r.freshness_lag_months) }]} />}
        </DataState>
      </Card>
      <Card title={t("me.mapping")}>
        <DataState loading={mq.loading} error={mq.error} empty={!mq.data?.metrics?.n_postings}>
          {mq.data?.metrics && <dl className="grid grid-cols-2 md:grid-cols-4 gap-2">
            <div><dt className="muted">Top-1 (in scope)</dt><dd className="font-bold">{f.pct(mq.data.metrics.top1_accuracy_in_scope, 1)}</dd></div>
            <div><dt className="muted">Auto-accepted share</dt><dd className="font-bold">{f.pct(mq.data.metrics.auto_accepted_share, 1)}</dd></div>
            <div><dt className="muted">Auto-accepted accuracy</dt><dd className="font-bold">{f.pct(mq.data.metrics.auto_accepted_accuracy, 1)}</dd></div>
            <div><dt className="muted">Review queue share</dt><dd className="font-bold">{f.pct(mq.data.metrics.review_queue_share, 1)}</dd></div>
          </dl>}
          <p className="muted text-sm mt-2">{mq.data?.metrics?.note}</p>
        </DataState>
      </Card>
      <Card title={t("me.backtest")}>
        <DataState loading={bt.loading} error={bt.error} empty={!bt.data}>
          <SortTable caption={t("me.backtest")} rows={rows} cols={[
            { key: "model", label: t("me.model") }, { key: "wape", label: "WAPE", num: true, render: (r) => f.pct(r.wape, 1) },
            { key: "smape", label: "sMAPE", num: true, render: (r) => f.pct(r.smape, 1) }, { key: "mape", label: "MAPE", num: true, render: (r) => f.pct(r.mape, 1) },
            { key: "c80", label: "80% coverage", num: true, render: (r) => (r.c80 == null ? "–" : f.pct(r.c80, 1)) }, { key: "c95", label: "95% coverage", num: true, render: (r) => (r.c95 == null ? "–" : f.pct(r.c95, 1)) }]} />
          <p className="muted text-sm mt-2">{bt.data?.note}</p>
        </DataState>
      </Card>
      <Card title={t("me.assumptions")}><ul className="list-disc pl-5 space-y-1">{items.map((x, i) => <li key={i}>{x}</li>)}</ul></Card>
    </div>
  );
}
