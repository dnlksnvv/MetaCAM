import type { UnifiedConfig } from "./types";

/** Стабильный hash конфига для дедупликации в recent-списке (на клиенте). */
export function configHash(cfg: UnifiedConfig): string {
  const norm = {
    method: cfg.method,
    ncc: cfg.ncc,
    milling: cfg.milling,
  };
  const str = JSON.stringify(norm, Object.keys(norm).sort());
  let h = 0;
  for (let i = 0; i < str.length; i++) h = ((h << 5) - h + str.charCodeAt(i)) | 0;
  return `cfg_${(h >>> 0).toString(36)}`;
}
