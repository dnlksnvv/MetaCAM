import { useEffect, useMemo, useState } from "react";
import QRCode from "qrcode";
import { Github } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";

export const GITHUB_URL = "https://github.com/dnlksnvv/MetaCAM";

export function AboutDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (v: boolean) => void }) {
  const [qr, setQr] = useState<string>("");

  const payload = useMemo(() => GITHUB_URL, []);

  useEffect(() => {
    if (!open) return;
    let alive = true;
    (async () => {
      const url = await QRCode.toDataURL(payload, {
        margin: 1,
        width: 520,
        color: { dark: "#0f172a", light: "#ffffff" },
      });
      if (alive) setQr(url);
    })();
    return () => {
      alive = false;
    };
  }, [open, payload]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>О приложении</DialogTitle>
          <DialogDescription>Ссылка на репозиторий и QR‑код для быстрого перехода.</DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="rounded-2xl border bg-white p-3 flex items-center justify-center">
            {qr ? (
              <img
                src={qr}
                alt="GitHub QR"
                className="w-full max-w-[320px] h-auto rounded-xl"
              />
            ) : (
              <div className="h-[320px] w-[320px] rounded-xl bg-muted animate-pulse" />
            )}
          </div>

          <div className="text-xs text-muted-foreground break-all">{GITHUB_URL}</div>

          <Button asChild className="w-full">
            <a href={GITHUB_URL} target="_blank" rel="noreferrer">
              <Github className="h-4 w-4 mr-2" />
              Открыть GitHub
            </a>
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

