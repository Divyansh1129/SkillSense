import { useCallback, useEffect, useState } from "react";

const KEYS: Record<string, string> = { viewer: "dev-viewer-key", analyst: "dev-analyst-key", admin: "dev-admin-key" };
export const getRole = () => {
  const saved = localStorage.getItem("ss_role");
  return saved && KEYS[saved] ? saved : "admin";
};
export const setRole = (r: string) => {
  if (!KEYS[r]) return;
  localStorage.setItem("ss_role", r);
  window.dispatchEvent(new Event("skillsense:role-change"));
};
const key = () => KEYS[getRole()];

export function useRole() {
  const [role, setRoleState] = useState(getRole);
  useEffect(() => {
    const sync = () => setRoleState(getRole());
    window.addEventListener("skillsense:role-change", sync);
    return () => window.removeEventListener("skillsense:role-change", sync);
  }, []);
  return role;
}

export class ApiErr extends Error { status: number; constructor(s: number, m: string) { super(m); this.status = s; } }

export async function api<T = any>(path: string, opts: { method?: string; body?: any } = {}): Promise<T> {
  const r = await fetch(`/api/v1${path}`, {
    method: opts.method || "GET",
    headers: { "X-API-Key": key(), ...(opts.body ? { "Content-Type": "application/json" } : {}) },
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new ApiErr(r.status, j?.error?.message || r.statusText);
  return j as T;
}

export function download(path: string) {
  window.open(`/api/v1${path}${path.includes("?") ? "&" : "?"}api_key=${key()}`, "_blank");
}

export function qs(o: Record<string, any>) {
  const p = Object.entries(o).filter(([, v]) => v !== "" && v != null && v !== false).map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`);
  return p.length ? "?" + p.join("&") : "";
}

/** GET hook with loading/error/reload. Pass null to stay idle. */
export function useApi<T = any>(path: string | null) {
  const role = useRole();
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [n, setN] = useState(0);
  useEffect(() => {
    if (!path) { setData(null); setError(null); setLoading(false); return; }
    let live = true;
    setLoading(true); setError(null);
    api<T>(path).then((d) => live && setData(d)).catch((e) => live && setError(e.message)).finally(() => live && setLoading(false));
    return () => { live = false; };
  }, [path, n, role]);
  const reload = useCallback(() => setN((x) => x + 1), []);
  return { data, error, loading, reload };
}

let taxCache: any = null;
export function useTaxonomy() {
  const [tax, setTax] = useState<any>(taxCache);
  useEffect(() => { if (!taxCache) api("/meta/taxonomy").then((t) => { taxCache = t; setTax(t); }).catch(() => {}); }, []);
  return tax;
}
