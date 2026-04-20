/**
 * MetaCAM конфиг.
 *
 * IP/URL бекенда задаётся:
 *  1) переменной окружения VITE_API_URL (.env / .env.local)
 *  2) либо вручную ниже в DEFAULT_API_URL
 *
 * Также можно переопределить в рантайме из консоли:
 *   localStorage.setItem('metacam.apiUrl', 'http://192.168.1.42:8081')
 */

const DEFAULT_DEV_API_URL = "http://localhost:8081";

function resolveApiUrl(): string {
  if (typeof window !== "undefined") {
    const fromStorage = window.localStorage?.getItem("metacam.apiUrl");
    if (fromStorage) return fromStorage.replace(/\/+$/, "");

    const fromRuntime = (window as any).__METACAM_ENV__?.API_URL as string | undefined;
    if (fromRuntime?.trim()) return fromRuntime.trim().replace(/\/+$/, "");

    // In production (Docker/Nginx) we want same-origin API.
    // In local dev (vite on localhost) default to backend port 8081.
    const host = window.location.hostname;
    if (host === "localhost" || host === "127.0.0.1") {
      return DEFAULT_DEV_API_URL;
    }
    return window.location.origin.replace(/\/+$/, "");
  }
  const fromEnv = (import.meta.env.VITE_API_URL as string | undefined)?.trim();
  if (fromEnv) return fromEnv.replace(/\/+$/, "");
  return DEFAULT_DEV_API_URL;
}

export const config = {
  apiUrl: resolveApiUrl(),
  apiBase: `${resolveApiUrl()}/api/v1`,
  appName: "MetaCAM",
  maxProjects: 4,
  maxRecentConfigs: 4,
};

export function setApiUrl(url: string) {
  const clean = url.replace(/\/+$/, "");
  window.localStorage.setItem("metacam.apiUrl", clean);
  window.location.reload();
}
