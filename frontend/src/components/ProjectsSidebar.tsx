import { Plus, FileCog, Trash2, Pencil, Check, X, Cpu, Info, Github } from "lucide-react";
import { useState } from "react";
import type { ProjectSummary, UnifiedConfig } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { GITHUB_URL } from "@/components/AboutDialog";

interface Props {
  projects: ProjectSummary[];
  activeId?: string;
  configs: UnifiedConfig[];
  onSelect: (p: ProjectSummary) => void;
  onNew: () => void;
  onRename: (id: string, name: string) => void;
  onDelete: (id: string) => void;
  onPickConfig: (cfg: UnifiedConfig) => void;
  onDeleteConfig: (cfg: UnifiedConfig) => void;
  onAbout: () => void;
}

export function ProjectsSidebar({
  projects, activeId, configs, onSelect, onNew, onRename, onDelete, onPickConfig, onDeleteConfig, onAbout,
}: Props) {
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState("");

  return (
    <aside className="flex h-full w-full flex-col bg-sidebar border-r border-sidebar-border">
      {/* Sidebar header (keep compact to avoid micro-scroll on desktop) */}
      <div className="px-4 py-2.5 border-b border-sidebar-border flex items-center gap-2">
        <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-gradient-primary text-primary-foreground shadow-sm">
          <Cpu className="h-5 w-5" />
        </div>
        <div className="flex-1">
          <div className="font-semibold tracking-tight leading-tight">MetaCAM</div>
          <div className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground mt-0.5">
            Gerber → G-code
          </div>
        </div>
      </div>

      <div className="p-3">
        <Button onClick={onNew} className="w-full justify-start gap-2" variant="default">
          <Plus className="h-4 w-4" /> Новый проект
        </Button>
      </div>

      <div className="px-4 pt-2 pb-1.5 font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
        Проекты ({projects.length})
      </div>
      <div className="flex-1 px-2 space-y-1 min-h-0">
        {projects.length === 0 && (
          <div className="px-3 py-6 text-xs text-muted-foreground text-center">
            Пока нет проектов. Загрузите Gerber, чтобы начать.
          </div>
        )}
        {projects.map((p) => {
          const active = p.id === activeId;
          const isEdit = editing === p.id;
          return (
            <div
              key={p.id}
              className={cn(
                "group rounded-lg px-2.5 py-2 transition-colors cursor-pointer border border-transparent",
                active
                  ? "bg-sidebar-accent border-sidebar-border shadow-sm"
                  : "hover:bg-sidebar-accent/60"
              )}
              onClick={() => !isEdit && onSelect(p)}
            >
              <div className="flex items-center gap-2">
                <div className={cn("h-1.5 w-1.5 rounded-full", active ? "bg-primary" : "bg-muted-foreground/40")} />
                {isEdit ? (
                  <div className="flex-1 flex gap-1">
                    <Input
                      autoFocus
                      value={draft}
                      onChange={(e) => setDraft(e.target.value)}
                      onClick={(e) => e.stopPropagation()}
                      className="h-7 text-sm"
                    />
                    <Button size="icon" variant="ghost" className="h-7 w-7"
                      onClick={(e) => { e.stopPropagation(); onRename(p.id, draft.trim() || p.name); setEditing(null); }}>
                      <Check className="h-3.5 w-3.5" />
                    </Button>
                    <Button size="icon" variant="ghost" className="h-7 w-7"
                      onClick={(e) => { e.stopPropagation(); setEditing(null); }}>
                      <X className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                ) : (
                  <>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium truncate">{p.name}</div>
                      <div className="text-[10px] font-mono text-muted-foreground truncate">
                        {new Date(p.updated_at).toLocaleString("ru-RU", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })}
                        {p.has_run && <span className="ml-2 text-success">● готово</span>}
                      </div>
                    </div>
                    <div className="opacity-100 md:opacity-0 md:group-hover:opacity-100 transition flex">
                      <Button size="icon" variant="ghost" className="h-7 w-7"
                        onClick={(e) => { e.stopPropagation(); setEditing(p.id); setDraft(p.name); }}>
                        <Pencil className="h-3.5 w-3.5" />
                      </Button>
                      <Button size="icon" variant="ghost" className="h-7 w-7 hover:text-destructive"
                        onClick={(e) => { e.stopPropagation(); if (confirm(`Удалить «${p.name}»?`)) onDelete(p.id); }}>
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  </>
                )}
              </div>
            </div>
          );
        })}
      </div>

      <div className="border-t border-sidebar-border">
        <div className="px-4 pt-3 pb-1.5 font-mono text-[10px] uppercase tracking-widest text-muted-foreground flex items-center gap-2">
          <FileCog className="h-3 w-3" /> Недавние конфиги ({configs.length})
        </div>
        <div className="px-2 pb-3 space-y-1">
          {configs.length === 0 && (
            <div className="px-3 py-3 text-xs text-muted-foreground text-center">
              Конфиги появятся после первой генерации.
            </div>
          )}
          {configs.map((c, i) => (
            <div key={c.id || c.hash || i}
              className="group flex items-center gap-2 rounded-lg px-2.5 py-1.5 hover:bg-sidebar-accent/60 cursor-pointer"
              onClick={() => onPickConfig(c)}
            >
              <div className="font-mono text-[10px] text-muted-foreground w-5">#{i + 1}</div>
              <div className="flex-1 min-w-0 text-xs">
                <div className="truncate font-medium">
                  Ø{c.ncc.toolDiameter} · {c.ncc.overlapPct}% · {c.ncc.toolType}
                </div>
                <div className="font-mono text-[10px] text-muted-foreground truncate">
                  cut {c.milling.cutZ} · F{c.milling.feedrateXY}
                </div>
              </div>
              <Button size="icon" variant="ghost"
                className="h-6 w-6 opacity-100 md:opacity-0 md:group-hover:opacity-100 hover:text-destructive"
                onClick={(e) => { e.stopPropagation(); onDeleteConfig(c); }}>
                <Trash2 className="h-3 w-3" />
              </Button>
            </div>
          ))}
        </div>
      </div>

      <div className="border-t border-sidebar-border p-3 flex items-center justify-between gap-2">
        <Button variant="ghost" className="justify-start gap-2 px-2" onClick={onAbout}>
          <Info className="h-4 w-4" /> О приложении
        </Button>
        <Button variant="ghost" size="icon" asChild title="GitHub">
          <a href={GITHUB_URL} target="_blank" rel="noreferrer">
            <Github className="h-4 w-4" />
          </a>
        </Button>
      </div>
    </aside>
  );
}
