import { useEffect, useState } from "react";
import type { ProjectSummary, UnifiedConfig } from "@/lib/types";
import { configHash } from "@/lib/configHash";
import { config as appConfig } from "@/config";

const PROJECTS_KEY = "metacam.projects";
const CONFIGS_KEY = "metacam.configs";

/** Лёгкий локальный кэш на случай оффлайна / отсутствия бекенда.
 *  Реальный источник правды — FastAPI, но кэш позволяет UI работать сразу.
 */
export function useLocalCache() {
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [configs, setConfigs] = useState<UnifiedConfig[]>([]);

  useEffect(() => {
    try {
      const p = JSON.parse(localStorage.getItem(PROJECTS_KEY) || "[]");
      const c = JSON.parse(localStorage.getItem(CONFIGS_KEY) || "[]");
      setProjects(Array.isArray(p) ? p : []);
      setConfigs(Array.isArray(c) ? c : []);
    } catch {}
  }, []);

  const saveProjects = (next: ProjectSummary[]) => {
    const trimmed = next.slice(0, appConfig.maxProjects);
    setProjects(trimmed);
    localStorage.setItem(PROJECTS_KEY, JSON.stringify(trimmed));
  };

  const saveConfigs = (next: UnifiedConfig[]) => {
    const trimmed = next.slice(0, appConfig.maxRecentConfigs);
    setConfigs(trimmed);
    localStorage.setItem(CONFIGS_KEY, JSON.stringify(trimmed));
  };

  const upsertProject = (p: ProjectSummary) => {
    const filtered = projects.filter((x) => x.id !== p.id);
    saveProjects([p, ...filtered]);
  };

  const removeProject = (id: string) => {
    saveProjects(projects.filter((p) => p.id !== id));
  };

  const renameProject = (id: string, name: string) => {
    saveProjects(projects.map((p) => (p.id === id ? { ...p, name, updated_at: new Date().toISOString() } : p)));
  };

  const pushConfig = (cfg: UnifiedConfig) => {
    const h = cfg.hash || configHash(cfg);
    const withHash = { ...cfg, hash: h };
    const filtered = configs.filter((c) => (c.hash || configHash(c)) !== h);
    saveConfigs([withHash, ...filtered]);
  };

  const removeConfig = (cfg: UnifiedConfig) => {
    const h = cfg.hash || configHash(cfg);
    saveConfigs(configs.filter((c) => (c.hash || configHash(c)) !== h));
  };

  const replaceConfigs = (next: UnifiedConfig[]) => saveConfigs(next);
  const replaceProjects = (next: ProjectSummary[]) => saveProjects(next);

  return { projects, configs, upsertProject, removeProject, renameProject, pushConfig, removeConfig, replaceConfigs, replaceProjects };
}
