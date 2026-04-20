import { useEffect, useState } from "react";
import { Smartphone, X } from "lucide-react";
import { Button } from "@/components/ui/button";

interface BIPEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

export function PWAInstallBanner() {
  const [evt, setEvt] = useState<BIPEvent | null>(null);
  const [hidden, setHidden] = useState(false);

  useEffect(() => {
    const dismissed = localStorage.getItem("metacam.pwa.dismissed");
    if (dismissed) setHidden(true);
    const handler = (e: Event) => {
      e.preventDefault();
      setEvt(e as BIPEvent);
    };
    window.addEventListener("beforeinstallprompt", handler);
    return () => window.removeEventListener("beforeinstallprompt", handler);
  }, []);

  if (hidden || !evt) return null;

  return (
    <div className="fixed bottom-4 left-1/2 z-40 -translate-x-1/2 animate-fade-in">
      <div className="glass flex items-center gap-3 rounded-full border border-border px-4 py-2 shadow-lg">
        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-gradient-primary text-primary-foreground">
          <Smartphone className="h-4 w-4" />
        </div>
        <div className="text-sm">
          <div className="font-medium">Установить MetaCAM</div>
          <div className="text-[11px] text-muted-foreground">Работает как обычное приложение</div>
        </div>
        <Button size="sm" onClick={async () => { await evt.prompt(); setEvt(null); }}>Установить</Button>
        <button onClick={() => { localStorage.setItem("metacam.pwa.dismissed", "1"); setHidden(true); }}
          className="text-muted-foreground hover:text-foreground">
          <X className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
