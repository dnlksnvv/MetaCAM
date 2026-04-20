import { useEffect, useRef, useState } from "react";
import { Menu, Sparkles, Download, RefreshCw, AlertCircle, FileText } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { toast } from "sonner";
import { ProjectsSidebar } from "@/components/ProjectsSidebar";
import { UploadDropzone } from "@/components/UploadDropzone";
import { GerberPreview } from "@/components/GerberPreview";
import { GenerateWizard } from "@/components/GenerateWizard";
import { ApiConfigBar } from "@/components/ApiConfigBar";
import { PWAInstallBanner } from "@/components/PWAInstallBanner";
import { AboutDialog, GITHUB_URL } from "@/components/AboutDialog";
import { useLocalCache } from "@/hooks/useLocalCache";
import { api, ApiError } from "@/lib/api";
import { config } from "@/config";
import { DEFAULT_CONFIG, type GenerateResponse, type PreviewData, type ProjectSummary, type UnifiedConfig } from "@/lib/types";

function toPaths(obj: any): { paths: number[][][] } | undefined {
  if (!obj) return undefined;
  if (Array.isArray(obj.paths)) return { paths: obj.paths as number[][][] };
  // Backend may return NCC/CNCJob previews as { lines: [{points:[{x,y}]}] }
  const lines = obj.lines;
  if (Array.isArray(lines)) {
    const paths: number[][][] = [];
    for (const ln of lines) {
      const pts = ln?.points;
      if (!Array.isArray(pts) || pts.length < 2) continue;
      const path: number[][] = [];
      for (const p of pts) {
        const x = typeof p?.x === "number" ? p.x : Number(p?.x);
        const y = typeof p?.y === "number" ? p.y : Number(p?.y);
        if (Number.isFinite(x) && Number.isFinite(y)) path.push([x, y]);
      }
      if (path.length >= 2) paths.push(path);
    }
    return paths.length ? { paths } : undefined;
  }
  return undefined;
}

const Index = () => {
  const cache = useLocalCache();
  const [active, setActive] = useState<ProjectSummary | null>(null);
  const [preview, setPreview] = useState<PreviewData | undefined>();
  const [run, setRun] = useState<GenerateResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [wizardOpen, setWizardOpen] = useState(false);
  const [wizardCfg, setWizardCfg] = useState<UnifiedConfig | undefined>(undefined);
  const [apiOnline, setApiOnline] = useState<boolean | null>(null);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [aboutOpen, setAboutOpen] = useState(false);
  const synced = useRef(false);

  // Lock body scroll when overlays are open (mobile sidebar or wizard)
  useEffect(() => {
    const lock = mobileSidebarOpen || wizardOpen;
    const isPwa = document.documentElement.dataset.pwa === "1";
    const el = document.documentElement;
    const body = document.body;
    if (isPwa && lock) {
      el.style.overflow = "hidden";
      body.style.overflow = "hidden";
      body.style.touchAction = "none";
    } else {
      el.style.overflow = "";
      body.style.overflow = "";
      body.style.touchAction = "";
    }
    return () => {
      el.style.overflow = "";
      body.style.overflow = "";
      body.style.touchAction = "";
    };
  }, [mobileSidebarOpen, wizardOpen]);

  // Первичная синхронизация со backend
  useEffect(() => {
    if (synced.current) return;
    synced.current = true;
    (async () => {
      try {
        const [pj, cf] = await Promise.all([api.listProjects(), api.listConfigs()]);
        setApiOnline(true);
        cache.replaceProjects(pj.projects ?? []);
        cache.replaceConfigs(cf.configs ?? []);
      } catch (e) {
        setApiOnline(false);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const openProject = async (p: ProjectSummary) => {
    setMobileSidebarOpen(false);
    setActive(p);
    setPreview(undefined);
    setRun(null);
    try {
      const det = await api.getProject(p.id);
      setPreview(det.preview);
      if (det.latest && det.latest.status === "done") {
        const ncc = toPaths((det.latest as any).ncc);
        const cncjob = toPaths((det.latest as any).cncjob);
        setRun({
          project: det.project,
          config: det.config!,
          configs: cache.configs,
          run: det.latest,
          copper: det.preview?.copper,
          ncc,
          cncjob,
          downloadUrl: api.downloadUrl(p.id, det.latest.id),
        });
      }
    } catch (e: any) {
      toast.error("Не удалось загрузить проект", { description: e.message });
    }
  };

  const handleUpload = async (file: File) => {
    setBusy(true);
    try {
      const { project, preview } = await api.createProject(file);
      cache.upsertProject(project);
      setActive(project);
      setPreview(preview);
      setRun(null);
      toast.success("Проект создан", { description: project.name });
    } catch (e: any) {
      const msg = e instanceof ApiError ? e.message : "Бекенд недоступен";
      toast.error("Ошибка загрузки", { description: msg });
    } finally {
      setBusy(false);
    }
  };

  const handleGenerate = async (cfg: UnifiedConfig) => {
    if (!active) return;
    setGenerating(true);
    try {
      const res = await api.generate(active.id, cfg);
      setRun(res);
      cache.upsertProject(res.project);
      cache.replaceConfigs(res.configs ?? []);
      cache.pushConfig(res.config);
      setWizardOpen(false);
      toast.success("G-code готов", { description: "Файл .nc доступен для скачивания." });
    } catch (e: any) {
      toast.error("Ошибка генерации", { description: e.message });
    } finally {
      setGenerating(false);
    }
  };

  const startWizard = (cfg?: UnifiedConfig) => {
    if (!active) {
      toast.error("Сначала загрузите Gerber-файл");
      return;
    }
    setMobileSidebarOpen(false);
    setWizardCfg(cfg ?? run?.config ?? DEFAULT_CONFIG);
    setWizardOpen(true);
  };

  const handleDownload = () => {
    if (!run || !active) return;
    const url = run.downloadUrl ?? api.downloadUrl(active.id, run.run.id);
    window.open(url, "_blank");
  };

  const sidebar = (
    <ProjectsSidebar
      projects={cache.projects}
      activeId={active?.id}
      configs={cache.configs}
      onSelect={openProject}
      onNew={() => { setActive(null); setPreview(undefined); setRun(null); }}
      onAbout={() => { setMobileSidebarOpen(false); setAboutOpen(true); }}
      onRename={async (id, name) => {
        cache.renameProject(id, name);
        try { await api.renameProject(id, name); } catch (e: any) { toast.error("Не удалось переименовать", { description: e.message }); }
      }}
      onDelete={async (id) => {
        cache.removeProject(id);
        if (active?.id === id) { setActive(null); setPreview(undefined); setRun(null); }
        try { await api.deleteProject(id); } catch {}
      }}
      onPickConfig={(c) => startWizard(c)}
      onDeleteConfig={async (c) => {
        cache.removeConfig(c);
        if (c.id || c.hash) try { await api.deleteConfig(c.id || c.hash!); } catch {}
      }}
    />
  );

  return (
    // On mobile use solid surface background so it blends with header/sidebar.
    // On desktop keep the hero gradient.
    <div className="min-h-[100dvh] bg-surface md:bg-gradient-hero">
      <div className="flex min-h-[100dvh] w-full">
        {/* Desktop sidebar */}
        <div className="hidden md:flex w-72 shrink-0 sticky top-0 h-[100dvh] overflow-hidden">
          {sidebar}
        </div>

        {/* Main */}
        <div className="flex-1 flex flex-col min-w-0">
          {/* Top bar */}
          {/* Fixed header: iOS Safari + PWA reliable */}
          <header className="fixed top-0 inset-x-0 md:left-72 md:w-[calc(100%-18rem)] z-40 glass border-b border-border">
            <div className="flex items-center gap-3 px-4 sm:px-6 h-14">
              <Sheet open={mobileSidebarOpen} onOpenChange={setMobileSidebarOpen}>
                <SheetTrigger asChild>
                  <Button variant="ghost" size="icon" className="md:hidden">
                    <Menu className="h-5 w-5" />
                  </Button>
                </SheetTrigger>
                <SheetContent side="left" className="p-0 w-[85vw] max-w-sm">{sidebar}</SheetContent>
              </Sheet>

              <div className="flex-1 min-w-0">
                {active ? (
                  <div className="text-sm font-semibold truncate">{active.name}</div>
                ) : (
                  <div className="md:hidden">
                    <div className="text-sm font-semibold truncate">MetaCAM</div>
                    <div className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground truncate">
                      Gerber → G-code
                    </div>
                  </div>
                )}
              </div>

              <div className="hidden sm:block">
                <ApiConfigBar />
              </div>

              {apiOnline === false && (
                <div className="flex items-center gap-1.5 rounded-full border border-warning/40 bg-warning/10 px-2.5 py-1 text-[11px] text-foreground/80">
                  <AlertCircle className="h-3 w-3" /> Backend offline
                </div>
              )}
            </div>
          </header>

          {/* Body */}
          {/* Padding-top to compensate fixed header height (h-14) */}
          <main className="flex-1 px-4 sm:px-6 pt-16 pb-5 sm:pt-16 sm:pb-8">
            {!active ? (
              <HeroEmpty onUpload={handleUpload} busy={busy} />
            ) : (
              <ProjectView
                project={active}
                preview={preview}
                run={run}
                onConvert={() => startWizard(run?.config)}
                onReopen={() => startWizard(run?.config)}
                onDownload={handleDownload}
                onReupload={handleUpload}
                busy={busy}
                generating={generating}
              />
            )}
          </main>
        </div>
      </div>

      <GenerateWizard
        open={wizardOpen}
        initial={wizardCfg}
        onClose={() => setWizardOpen(false)}
        onGenerate={handleGenerate}
        generating={generating}
      />
      <AboutDialog open={aboutOpen} onOpenChange={setAboutOpen} />
      <PWAInstallBanner />
    </div>
  );
};

function HeroEmpty({ onUpload, busy }: { onUpload: (f: File) => void; busy: boolean }) {
  const TEST_FILE_URL = "/test/sample.gtl";

  const uploadTestFile = async () => {
    try {
      const res = await fetch(TEST_FILE_URL, { cache: "no-store" });
      if (!res.ok) throw new Error(`Test file not found (${res.status})`);
      const blob = await res.blob();
      const file = new File([blob], "sample.gtl", { type: "application/octet-stream" });
      onUpload(file);
    } catch (e: any) {
      toast.error("Тестовый файл не найден", {
        description: `Положите файл в frontend/public/test/sample.gtl (сейчас: ${TEST_FILE_URL})`,
      });
    }
  };

  return (
    <div className="mx-auto max-w-3xl space-y-8 animate-fade-in">
      <div className="text-center space-y-4 pt-4 sm:pt-10">
        <div className="inline-flex items-center gap-2 rounded-full border border-border bg-surface px-3 py-1 text-[11px] font-mono uppercase tracking-widest text-muted-foreground">
          <span className="h-1.5 w-1.5 rounded-full bg-success animate-pulse" />
          {config.appName} · v1.0
        </div>
        <h1 className="text-3xl sm:text-5xl font-bold tracking-tight">
          Gerber → <span className="text-gradient">G-code</span> за один шаг
        </h1>
        <p className="text-base text-muted-foreground max-w-xl mx-auto">
          Загрузите файл платы, выберите параметры — получите готовый управляющий код для ЧПУ.
          Минимум кликов, максимум точности.
        </p>
      </div>

      <UploadDropzone
        onFile={onUpload}
        busy={busy}
        footer={
          <div className="rounded-xl border border-primary/25 bg-primary/5 px-3.5 py-3 text-left">
            <div className="text-[12px] font-semibold leading-tight">Быстрый старт</div>
            <div className="text-[11px] text-muted-foreground leading-snug mt-0.5">
              Без загрузки файла — откройте готовый пример.
            </div>

            <div className="relative mt-3">
              <span className="absolute -inset-1 rounded-full bg-primary/20 blur-md" />
              <span className="absolute -inset-1 rounded-full bg-primary/30 animate-ping" />
              <Button
                type="button"
                disabled={busy}
                onClick={uploadTestFile}
                className="relative w-full h-auto rounded-full px-6 py-2.5 shadow-glow text-[12px] leading-snug whitespace-normal"
              >
                <Sparkles className="h-4 w-4 mr-1.5" />
                Использовать тестовый файл Метаматериала
              </Button>
            </div>
          </div>
        }
      />

      <div className="grid grid-cols-3 gap-3 text-center">
        {[
          { k: "01", t: "Загрузить", d: "Gerber-файл" },
          { k: "02", t: "Настроить", d: "Инструмент и проходы" },
          { k: "03", t: "Сгенерировать", d: ".nc файл" },
        ].map((s) => (
          <div key={s.k} className="rounded-xl border border-border bg-card p-3 sm:p-4">
            <div className="font-mono text-[10px] text-primary tracking-widest">{s.k}</div>
            <div className="font-semibold text-[13px] sm:text-sm mt-1 leading-tight break-words">
              {s.t}
            </div>
            <div className="text-[11px] text-muted-foreground">{s.d}</div>
          </div>
        ))}
      </div>

      <div className="text-center text-xs text-muted-foreground">
        <a
          href={GITHUB_URL}
          target="_blank"
          rel="noreferrer"
          className="underline underline-offset-4 hover:text-foreground transition"
        >
          GitHub: dnlksnvv/MetaCAM
        </a>
      </div>
    </div>
  );
}

function ProjectView({
  project, preview, run, onConvert, onReopen, onDownload, onReupload, busy, generating,
}: {
  project: ProjectSummary;
  preview?: PreviewData;
  run: GenerateResponse | null;
  onConvert: () => void;
  onReopen: () => void;
  onDownload: () => void;
  onReupload: (f: File) => void;
  busy: boolean;
  generating: boolean;
}) {
  const hasPreview = !!preview?.copper?.paths?.length;
  const [showCopper, setShowCopper] = useState(true);
  const [showNcc, setShowNcc] = useState(true);
  const [showCnc, setShowCnc] = useState(true);

  const copper = showCopper ? preview?.copper : undefined;
  const ncc = showNcc ? run?.ncc : undefined;
  const cncjob = showCnc ? run?.cncjob : undefined;
  return (
    <div className="space-y-4 animate-fade-in">
      {/* Toolbar */}
      <div className="flex flex-col sm:flex-row sm:flex-wrap sm:items-center gap-2">
        <div className="flex-1 min-w-0">
          <div className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">Источник</div>
          <div className="text-sm flex items-center gap-2 truncate">
            <FileText className="h-3.5 w-3.5 text-muted-foreground" />
            <span className="truncate">{project.source?.filename ?? project.name}</span>
            {project.source?.size_bytes && (
              <span className="font-mono text-[11px] text-muted-foreground">
                · {(project.source.size_bytes / 1024).toFixed(1)} KB
              </span>
            )}
          </div>
        </div>

        <div className="flex flex-wrap gap-2 sm:justify-end">
          {run ? (
            <>
              <Button variant="outline" onClick={onReopen}>
                <RefreshCw className="h-4 w-4 mr-1.5" /> Изменить параметры
              </Button>
              <Button onClick={onDownload} className="shadow-glow">
                <Download className="h-4 w-4 mr-1.5" /> Скачать .nc
              </Button>
            </>
          ) : (
            <Button onClick={onConvert} disabled={!hasPreview} className="shadow-glow">
              <Sparkles className="h-4 w-4 mr-1.5" /> Сгенерировать G-code
            </Button>
          )}
        </div>
      </div>

      {/* Preview */}
      <div className="relative rounded-2xl border border-border bg-card overflow-hidden">
        <div className="grid-bg absolute inset-0 opacity-40 pointer-events-none" />
        <GerberPreview
          className="relative h-[55vh] sm:h-[65vh] w-full"
          copper={copper}
          ncc={ncc}
          cncjob={cncjob}
          bounds={preview?.bounds}
          nccToolDiaMm={run?.config?.ncc?.toolDiameter}
          cncToolDiaMm={run?.config?.milling?.toolDiameter}
          empty={busy ? "Обработка..." : "Превью пустое"}
        />
        {/* Legend */}
        <div className="absolute left-3 bottom-3 flex flex-wrap gap-2 font-mono text-[10px] uppercase tracking-widest">
          <Legend
            color="hsl(var(--copper))"
            label="Copper"
            active={showCopper}
            onToggle={() => setShowCopper((v) => !v)}
          />
          {run?.ncc && (
            <Legend
              color="hsl(var(--ncc-path))"
              label="NCC"
              active={showNcc}
              onToggle={() => setShowNcc((v) => !v)}
            />
          )}
          {run?.cncjob && (
            <Legend
              color="hsl(var(--cnc-path))"
              label="CNCJob"
              active={showCnc}
              onToggle={() => setShowCnc((v) => !v)}
            />
          )}
        </div>
        {generating && (
          <div className="absolute inset-0 flex items-center justify-center bg-background/60 backdrop-blur-sm">
            <div className="text-center space-y-2">
              <div className="mx-auto h-12 w-12 rounded-full border-2 border-primary border-t-transparent animate-spin" />
              <div className="text-sm">Генерируем траекторию...</div>
            </div>
          </div>
        )}
      </div>

      {/* Re-upload helper */}
      <div className="text-xs text-muted-foreground text-center">
        Хотите загрузить другой файл?{" "}
        <label className="text-primary hover:underline cursor-pointer">
          Выбрать
          <input
            type="file"
            className="sr-only"
            accept=".gbr,.ger,.gtl,.gbl,.gto,.gbo,.drl,.txt"
            onChange={(e) => e.target.files?.[0] && onReupload(e.target.files[0])}
          />
        </label>
      </div>
    </div>
  );
}

function Legend({
  color,
  label,
  active,
  onToggle,
}: {
  color: string;
  label: string;
  active: boolean;
  onToggle: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onToggle}
      className={[
        "flex items-center gap-1.5 rounded-full px-2 py-1 border transition",
        "bg-background/80 border-border hover:bg-background",
        active ? "opacity-100" : "opacity-40 line-through",
      ].join(" ")}
      title={active ? "Hide layer" : "Show layer"}
    >
      <span className="h-2 w-2 rounded-full" style={{ background: color }} />
      <span>{label}</span>
    </button>
  );
}

export default Index;
