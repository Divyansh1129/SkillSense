import { useTranslation } from "react-i18next";

const LOC: Record<string, string> = { en: "en-IN", hi: "hi-IN", mr: "mr-IN" };

export function useFmt() {
  const { i18n } = useTranslation();
  const loc = LOC[i18n.language] || "en-IN";
  return {
    n: (x: any, d = 0) => (x == null || isNaN(x) ? "–" : new Intl.NumberFormat(loc, { maximumFractionDigits: d }).format(x)),
    pct: (x: any, d = 0) => (x == null || isNaN(x) ? "–" : new Intl.NumberFormat(loc, { style: "percent", maximumFractionDigits: d }).format(x)),
    date: (s: any) => (s ? new Intl.DateTimeFormat(loc, { dateStyle: "medium" }).format(new Date(s)) : "–"),
    month: (m: string) => new Intl.DateTimeFormat(loc, { month: "short", year: "numeric" }).format(new Date(m + "-01")),
  };
}

/** Translate names (trade / district / sector / state) with English fallback. */
export function useNames() {
  const { t } = useTranslation();
  return {
    trade: (c: string, fb?: string) => String(t(`trade.${c}`, { defaultValue: fb || c })),
    district: (c: string, fb?: string) => String(t(`district.${c}`, { defaultValue: fb || c })),
    sector: (c: string) => String(t(`sector.${c}`, { defaultValue: c })),
    state: (c: string) => String(t(`state.${c}`, { defaultValue: c })),
  };
}

/** Alert reason/action are generated from templates with translation keys + params returned by the API. */
export function useAlertText() {
  const { t } = useTranslation();
  const nm = useNames();
  return (a: any) => {
    const rp = a.reason_params || {};
    const ap = { ...(a.action_params || {}) };
    if (ap.shift_trade_code) ap.shift_trade = nm.trade(ap.shift_trade_code);
    return {
      reason: String(t(a.reason_key, { ...rp, defaultValue: a.reason_en })),
      action: String(t(a.action_key, { ...ap, defaultValue: a.action_en })),
    };
  };
}
