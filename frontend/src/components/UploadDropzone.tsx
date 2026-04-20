import { useCallback, useState } from "react";
import { Upload, FileUp } from "lucide-react";
import { cn } from "@/lib/utils";

interface Props {
  onFile: (file: File) => void;
  busy?: boolean;
  footer?: React.ReactNode;
}

const ACCEPT = ".gbr,.ger,.gtl,.gbl,.gto,.gbo,.gts,.gbs,.gko,.drl,.txt";

export function UploadDropzone({ onFile, busy, footer }: Props) {
  const [drag, setDrag] = useState(false);

  const handle = useCallback(
    (f?: File | null) => {
      if (!f) return;
      onFile(f);
    },
    [onFile]
  );

  return (
    <label
      onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
      onDragLeave={() => setDrag(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDrag(false);
        handle(e.dataTransfer.files?.[0]);
      }}
      className={cn(
        "group relative block cursor-pointer overflow-hidden rounded-2xl border-2 border-dashed transition-all",
        "bg-surface hover:bg-surface-2 hover:border-primary/60",
        drag && "border-primary bg-primary/5 scale-[1.01]",
        busy && "pointer-events-none opacity-70",
        !drag && "border-border"
      )}
    >
      <input
        type="file"
        accept={ACCEPT}
        className="sr-only"
        onChange={(e) => handle(e.target.files?.[0])}
        disabled={busy}
      />
      <div className="flex flex-col items-center justify-center gap-4 px-6 py-14 sm:py-20 text-center">
        <div className="relative">
          <div className="absolute inset-0 rounded-full bg-primary/10 blur-xl group-hover:bg-primary/20 transition" />
          <div className="relative flex h-16 w-16 items-center justify-center rounded-full bg-gradient-primary text-primary-foreground shadow-glow animate-pulse-ring">
            {busy ? <Upload className="h-7 w-7 animate-bounce" /> : <FileUp className="h-7 w-7" />}
          </div>
        </div>
        <div className="space-y-1.5">
          <h2 className="text-xl font-semibold tracking-tight sm:text-2xl">
            {busy ? "Загружаем..." : "Загрузите Gerber-файл"}
          </h2>
          <p className="text-sm text-muted-foreground max-w-sm mx-auto">
            Перетащите .gbr файл сюда или нажмите для выбора. Превью платы откроется автоматически.
          </p>
        </div>
        <div className="flex items-center gap-2 mt-2 font-mono text-[11px] uppercase tracking-widest text-muted-foreground">
          <span className="h-px w-6 bg-border" />
          <span>.gbr · .gtl · .gbl · .drl</span>
          <span className="h-px w-6 bg-border" />
        </div>

        {footer ? (
          <div
            className="mt-5 w-full max-w-sm"
            onClick={(e) => {
              // Keep footer interactive without triggering file picker.
              e.preventDefault();
              e.stopPropagation();
            }}
          >
            {footer}
          </div>
        ) : null}
      </div>
    </label>
  );
}
