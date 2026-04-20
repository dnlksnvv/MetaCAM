import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronLeft, ChevronRight, Sparkles, Cpu, Settings2, Wrench, X, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { cn } from "@/lib/utils";
import type { UnifiedConfig, ToolType } from "@/lib/types";
import { DEFAULT_CONFIG } from "@/lib/types";

interface Props {
  open: boolean;
  initial?: UnifiedConfig;
  onClose: () => void;
  onGenerate: (cfg: UnifiedConfig) => Promise<void> | void;
  generating?: boolean;
}

const STEPS = [
  { id: "method", title: "Метод обработки", icon: Sparkles },
  { id: "tool", title: "Инструмент", icon: Cpu },
  { id: "overlap", title: "Перекрытие и поля", icon: Settings2 },
  { id: "milling", title: "Параметры фрезеровки", icon: Wrench },
] as const;

export function GenerateWizard({ open, initial, onClose, onGenerate, generating }: Props) {
  const [step, setStep] = useState(0);
  const [cfg, setCfg] = useState<UnifiedConfig>(initial ?? DEFAULT_CONFIG);
  const [advancedOpen, setAdvancedOpen] = useState(true);

  // When opening (or when `initial` changes), reset wizard state.
  useEffect(() => {
    if (!open) return;
    const next = initial ?? DEFAULT_CONFIG;
    setCfg(next);
    // If we already have a config, method is effectively known -> skip "method" step.
    setStep(initial ? 1 : 0);
    setAdvancedOpen(true);
  }, [open, initial]);

  if (!open) return null;
  const isLast = step === STEPS.length - 1;

  const updateNCC = (k: keyof UnifiedConfig["ncc"], v: any) => setCfg({ ...cfg, ncc: { ...cfg.ncc, [k]: v } });
  const updateMill = (k: keyof UnifiedConfig["milling"], v: any) => setCfg({ ...cfg, milling: { ...cfg.milling, [k]: v } });

  return (
    <AnimatePresence>
      <motion.div
        className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-foreground/40 backdrop-blur-sm"
        initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
        onClick={onClose}
      >
        <motion.div
          className="w-full sm:max-w-xl max-h-[95vh] sm:max-h-[90vh] bg-card text-card-foreground rounded-t-3xl sm:rounded-2xl shadow-lg overflow-hidden flex flex-col border border-border"
          initial={{ y: 60, opacity: 0, scale: 0.98 }}
          animate={{ y: 0, opacity: 1, scale: 1 }}
          exit={{ y: 40, opacity: 0 }}
          transition={{ type: "spring", damping: 28, stiffness: 280 }}
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className="px-5 sm:px-6 pt-4 pb-3 border-b border-border">
            <div className="flex items-center justify-between">
              <div className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
                Шаг {step + 1} / {STEPS.length}
              </div>
              <button onClick={onClose} className="text-muted-foreground hover:text-foreground transition" aria-label="Закрыть">
                <X className="h-4 w-4" />
              </button>
            </div>
            <h2 className="text-lg sm:text-xl font-semibold tracking-tight mt-1">{STEPS[step].title}</h2>
            {/* progress */}
            <div className="mt-3 flex gap-1.5">
              {STEPS.map((_, i) => (
                <div key={i} className={cn("h-1 flex-1 rounded-full transition-colors", i <= step ? "bg-primary" : "bg-muted")} />
              ))}
            </div>
          </div>

          {/* Content */}
          <div className="flex-1 overflow-y-auto px-5 sm:px-6 py-5">
            <AnimatePresence mode="wait">
              <motion.div
                key={step}
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                transition={{ duration: 0.2 }}
                className="space-y-5"
              >
                {step === 0 && (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <button
                      className="group rounded-xl border-2 border-primary bg-primary/5 p-5 text-left transition hover:bg-primary/10"
                    >
                      <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-gradient-primary text-primary-foreground mb-3">
                        <Sparkles className="h-5 w-5" />
                      </div>
                      <div className="font-semibold">NCC</div>
                      <div className="text-xs text-muted-foreground mt-1">Non-copper clearing — снимает всю лишнюю медь.</div>
                      <div className="font-mono text-[10px] uppercase tracking-widest text-primary mt-3">Выбрано</div>
                    </button>
                    <div className="rounded-xl border border-dashed border-border p-5 opacity-50 cursor-not-allowed">
                      <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-muted text-muted-foreground mb-3">
                        <Wrench className="h-5 w-5" />
                      </div>
                      <div className="font-semibold">Isolation</div>
                      <div className="text-xs text-muted-foreground mt-1">Скоро — изоляционная обводка контуров.</div>
                    </div>
                  </div>
                )}

                {step === 1 && (
                  <div className="space-y-4">
                    <Field label="Диаметр инструмента, мм" hint="Диаметр кончика фрезы для NCC.">
                      <Input type="number" step="0.01" min={0.01}
                        value={cfg.ncc.toolDiameter}
                        onChange={(e) => updateNCC("toolDiameter", parseFloat(e.target.value) || 0)} />
                    </Field>
                    <Field label="Тип инструмента">
                      <Select value={cfg.ncc.toolType} onValueChange={(v) => updateNCC("toolType", v as ToolType)}>
                        <SelectTrigger><SelectValue /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="V">V — гравер</SelectItem>
                          <SelectItem value="C1">C1 — цилиндр 1 заход</SelectItem>
                          <SelectItem value="C2">C2 — цилиндр 2 захода</SelectItem>
                          <SelectItem value="C3">C3 — цилиндр 3 захода</SelectItem>
                          <SelectItem value="C4">C4 — цилиндр 4 захода</SelectItem>
                          <SelectItem value="B">B — шар</SelectItem>
                        </SelectContent>
                      </Select>
                    </Field>
                  </div>
                )}

                {step === 2 && (
                  <div className="space-y-5">
                    <Field label={`Перекрытие — ${cfg.ncc.overlapPct}%`} hint="Сколько проходов перекрывают друг друга.">
                      <Slider value={[cfg.ncc.overlapPct]} min={0} max={95} step={1}
                        onValueChange={([v]) => updateNCC("overlapPct", v)} />
                    </Field>
                    <Field label="Поле (margin), мм" hint="Отступ от края платы.">
                      <Input type="number" step="0.1" value={cfg.ncc.margin}
                        onChange={(e) => updateNCC("margin", parseFloat(e.target.value) || 0)} />
                    </Field>

                    <button
                      type="button"
                      onClick={() => setAdvancedOpen(!advancedOpen)}
                      className="flex items-center gap-2 text-sm font-medium text-muted-foreground hover:text-foreground transition pt-2"
                    >
                      <ChevronRight className={cn("h-4 w-4 transition-transform", advancedOpen && "rotate-90")} />
                      Расширенные настройки
                    </button>
                    {advancedOpen && (
                      <div className="space-y-3 rounded-xl border border-border bg-surface p-4">
                        <Toggle label="Connect" desc="Соединять проходы для уменьшения подъёмов."
                          checked={cfg.ncc.connect} onCheckedChange={(v) => updateNCC("connect", v)} />
                        <Toggle label="Contour" desc="Дополнительный обход по контуру."
                          checked={cfg.ncc.contour} onCheckedChange={(v) => updateNCC("contour", v)} />
                        <Toggle label="Check validity" desc="Проверять корректность геометрии."
                          checked={cfg.ncc.checkValidity} onCheckedChange={(v) => updateNCC("checkValidity", v)} />
                        <Toggle label="Check inset" desc="Проверять валидность внутреннего смещения."
                          checked={cfg.ncc.checkInset} onCheckedChange={(v) => updateNCC("checkInset", v)} />
                      </div>
                    )}
                  </div>
                )}

                {step === 3 && (
                  <div className="grid grid-cols-2 gap-3">
                    <Field label="Dia, мм">
                      <Input type="number" step="0.01" value={cfg.milling.toolDiameter}
                        onChange={(e) => updateMill("toolDiameter", parseFloat(e.target.value) || 0)} />
                    </Field>
                    <Field label="Cut Z">
                      <Input type="number" step="0.01" value={cfg.milling.cutZ}
                        onChange={(e) => updateMill("cutZ", parseFloat(e.target.value) || 0)} />
                    </Field>
                    <Field label="Travel Z">
                      <Input type="number" step="0.1" value={cfg.milling.travelZ}
                        onChange={(e) => updateMill("travelZ", parseFloat(e.target.value) || 0)} />
                    </Field>
                    <Field label="End move Z">
                      <Input type="number" step="0.1" value={cfg.milling.endMoveZ}
                        onChange={(e) => updateMill("endMoveZ", parseFloat(e.target.value) || 0)} />
                    </Field>
                    <Field label="Feed X-Y">
                      <Input type="number" value={cfg.milling.feedrateXY}
                        onChange={(e) => updateMill("feedrateXY", parseFloat(e.target.value) || 0)} />
                    </Field>
                    <Field label="Feed Z">
                      <Input type="number" value={cfg.milling.feedrateZ}
                        onChange={(e) => updateMill("feedrateZ", parseFloat(e.target.value) || 0)} />
                    </Field>
                    <Field label="Spindle (RPM)">
                      <Input type="number" value={cfg.milling.spindleSpeed}
                        onChange={(e) => updateMill("spindleSpeed", parseFloat(e.target.value) || 0)} />
                    </Field>
                    <Field label="Dwell time, с">
                      <Input type="number" step="0.1" value={cfg.milling.dwellTime} disabled={!cfg.milling.dwell}
                        onChange={(e) => updateMill("dwellTime", parseFloat(e.target.value) || 0)} />
                    </Field>
                    <div className="col-span-2">
                      <Toggle label="Dwell" desc="Задержка шпинделя перед резом."
                        checked={cfg.milling.dwell} onCheckedChange={(v) => updateMill("dwell", v)} />
                    </div>
                  </div>
                )}
              </motion.div>
            </AnimatePresence>
          </div>

          {/* Footer */}
          <div className="border-t border-border px-5 sm:px-6 py-3 flex items-center justify-between gap-3 bg-surface">
            <Button variant="ghost" onClick={() => (step === 0 ? onClose() : setStep(step - 1))} disabled={generating}>
              <ChevronLeft className="h-4 w-4 mr-1" />
              {step === 0 ? "Отмена" : "Назад"}
            </Button>
            {isLast ? (
              <Button onClick={() => onGenerate(cfg)} disabled={generating} className="min-w-[140px] shadow-glow">
                {generating ? <><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Генерация...</> : <>Сгенерировать <Sparkles className="h-4 w-4 ml-2" /></>}
              </Button>
            ) : (
              <Button onClick={() => setStep(step + 1)}>
                Далее <ChevronRight className="h-4 w-4 ml-1" />
              </Button>
            )}
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <Label className="text-xs font-medium text-foreground/80">{label}</Label>
      {children}
      {hint && <div className="text-[11px] text-muted-foreground">{hint}</div>}
    </div>
  );
}

function Toggle({ label, desc, checked, onCheckedChange }: { label: string; desc: string; checked: boolean; onCheckedChange: (v: boolean) => void }) {
  return (
    <div className="flex items-start justify-between gap-3 py-1.5">
      <div className="flex-1">
        <Label className="text-sm font-medium">{label}</Label>
        <div className="text-[11px] text-muted-foreground">{desc}</div>
      </div>
      <Switch checked={checked} onCheckedChange={onCheckedChange} />
    </div>
  );
}
