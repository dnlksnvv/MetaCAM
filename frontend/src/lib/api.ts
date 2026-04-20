import { config } from "@/config";
import type {
  GenerateResponse,
  PreviewData,
  ProjectDetails,
  ProjectSummary,
  UnifiedConfig,
} from "./types";

class ApiError extends Error {
  constructor(message: string, public status?: number) {
    super(message);
  }
}

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let msg = `HTTP ${res.status}`;
    try {
      const j = await res.json();
      msg = j.detail || j.message || msg;
    } catch {}
    throw new ApiError(msg, res.status);
  }
  const ct = res.headers.get("content-type") || "";
  if (ct.includes("application/json")) return (await res.json()) as T;
  return (await res.text()) as unknown as T;
}

const base = () => config.apiBase;

export const api = {
  // ---------- projects ----------
  async listProjects(): Promise<{ projects: ProjectSummary[] }> {
    return handle(await fetch(`${base()}/projects`));
  },

  async getProject(id: string): Promise<ProjectDetails> {
    return handle(await fetch(`${base()}/projects/${id}`));
  },

  async createProject(file: File, name?: string): Promise<{ project: ProjectSummary; preview: PreviewData }> {
    const fd = new FormData();
    fd.append("file", file);
    if (name) fd.append("name", name);
    return handle(await fetch(`${base()}/projects`, { method: "POST", body: fd }));
  },

  async renameProject(id: string, name: string): Promise<{ project: ProjectSummary }> {
    const fd = new FormData();
    fd.append("name", name);
    return handle(await fetch(`${base()}/projects/${id}`, { method: "PATCH", body: fd }));
  },

  async deleteProject(id: string): Promise<{ ok: boolean }> {
    return handle(await fetch(`${base()}/projects/${id}`, { method: "DELETE" }));
  },

  // ---------- configs ----------
  async listConfigs(): Promise<{ configs: UnifiedConfig[] }> {
    return handle(await fetch(`${base()}/configs/recent`));
  },

  async saveConfig(cfg: UnifiedConfig): Promise<{ config: UnifiedConfig; configs: UnifiedConfig[] }> {
    const fd = new FormData();
    fd.append("config", JSON.stringify(cfg));
    return handle(await fetch(`${base()}/configs`, { method: "POST", body: fd }));
  },

  async deleteConfig(idOrHash: string): Promise<{ ok: boolean; configs: UnifiedConfig[] }> {
    return handle(await fetch(`${base()}/configs/${idOrHash}`, { method: "DELETE" }));
  },

  // ---------- generation ----------
  async generate(projectId: string, cfg: UnifiedConfig, configId?: string): Promise<GenerateResponse> {
    const fd = new FormData();
    if (configId) fd.append("config_id", configId);
    fd.append("config", JSON.stringify(cfg));
    return handle(await fetch(`${base()}/projects/${projectId}/generate`, { method: "POST", body: fd }));
  },

  downloadUrl(projectId: string, runId: string): string {
    return `${base()}/projects/${projectId}/runs/${runId}/download`;
  },
};

export { ApiError };
