import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { useEffect } from "react";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import Index from "./pages/Index.tsx";
import NotFound from "./pages/NotFound.tsx";

const queryClient = new QueryClient();

const App = () => {
  useEffect(() => {
    // PWA detection for iOS/Chrome:
    // - iOS Safari: navigator.standalone
    // - Others: display-mode: standalone
    const isStandalone =
      // @ts-expect-error iOS Safari standalone
      (typeof navigator !== "undefined" && (navigator as any).standalone) ||
      (typeof window !== "undefined" &&
        window.matchMedia &&
        window.matchMedia("(display-mode: standalone)").matches);
    document.documentElement.dataset.pwa = isStandalone ? "1" : "0";
  }, []);

  useEffect(() => {
    // iOS Safari sometimes still zooms with pinch/gesture even if viewport disables it.
    // Prevent page-level zoom; in-app preview uses pointer events for pinch-zoom.
    const isIOS =
      typeof navigator !== "undefined" &&
      /iP(hone|ad|od)/.test(navigator.userAgent || "");
    if (!isIOS) return;
    const prevent = (e: Event) => {
      e.preventDefault();
    };
    document.addEventListener("gesturestart", prevent, { passive: false } as any);
    document.addEventListener("gesturechange", prevent, { passive: false } as any);
    document.addEventListener("gestureend", prevent, { passive: false } as any);
    return () => {
      document.removeEventListener("gesturestart", prevent as any);
      document.removeEventListener("gesturechange", prevent as any);
      document.removeEventListener("gestureend", prevent as any);
    };
  }, []);

  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <Toaster />
        <Sonner />
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<Index />} />
            {/* ADD ALL CUSTOM ROUTES ABOVE THE CATCH-ALL "*" ROUTE */}
            <Route path="*" element={<NotFound />} />
          </Routes>
        </BrowserRouter>
      </TooltipProvider>
    </QueryClientProvider>
  );
};

export default App;
