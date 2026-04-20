import { useEffect, useMemo, useRef, useState } from "react";

interface Props {
  copper?: { paths: number[][][] };
  ncc?: { paths: number[][][] };
  cncjob?: { paths: number[][][] };
  bounds?: { minX: number; minY: number; maxX: number; maxY: number };
  nccToolDiaMm?: number;
  cncToolDiaMm?: number;
  className?: string;
  empty?: React.ReactNode;
}

/** Canvas-рендер: рисуем медь как залитые полигоны, NCC и CNC — как линии. */
export function GerberPreview({ copper, ncc, cncjob, bounds, nccToolDiaMm, cncToolDiaMm, className, empty }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ w: 600, h: 400 });
  const [zoom, setZoom] = useState(1); // user zoom multiplier
  const [pan, setPan] = useState({ x: 0, y: 0 }); // user pan in px
  const pointers = useRef(new Map<number, { x: number; y: number }>());
  const gesture = useRef<null | {
    type: "pan" | "pinch";
    startZoom: number;
    startPan: { x: number; y: number };
    startMid: { x: number; y: number };
    startDist: number;
  }>(null);

  useEffect(() => {
    if (!wrapRef.current) return;
    const ro = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect;
      setSize({ w: Math.max(200, width), h: Math.max(200, height) });
    });
    ro.observe(wrapRef.current);
    return () => ro.disconnect();
  }, []);

  const hasAny = !!(copper?.paths?.length || ncc?.paths?.length || cncjob?.paths?.length);

  const fit = useMemo(() => {
    // compute bbox from provided bounds or from geometry
    let bb = bounds;
    if (!bb) {
      const all = [...(copper?.paths || []), ...(ncc?.paths || []), ...(cncjob?.paths || [])];
      if (!all.length) return null;
      let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
      for (const path of all) for (const [x, y] of path) {
        if (x < minX) minX = x; if (y < minY) minY = y;
        if (x > maxX) maxX = x; if (y > maxY) maxY = y;
      }
      if (!isFinite(minX)) return null;
      bb = { minX, minY, maxX, maxY };
    }
    const pad = 16;
    const bw = bb.maxX - bb.minX || 1;
    const bh = bb.maxY - bb.minY || 1;
    const scale = Math.min((size.w - pad * 2) / bw, (size.h - pad * 2) / bh);
    const ox = (size.w - bw * scale) / 2 - bb.minX * scale;
    const oy = (size.h - bh * scale) / 2 + bb.maxY * scale;
    return { bb, scale, ox, oy };
  }, [bounds, copper, ncc, cncjob, size]);

  useEffect(() => {
    const cv = canvasRef.current;
    if (!cv) return;
    const dpr = window.devicePixelRatio || 1;
    cv.width = Math.floor(size.w * dpr);
    cv.height = Math.floor(size.h * dpr);
    cv.style.width = `${size.w}px`;
    cv.style.height = `${size.h}px`;
    const ctx = cv.getContext("2d");
    if (!ctx) return;
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, size.w, size.h);

    if (!fit) return;
    const scale = fit.scale * zoom;
    const ox = fit.ox + pan.x;
    const oy = fit.oy + pan.y;
    const tx = (x: number) => x * scale + ox;
    const ty = (y: number) => -y * scale + oy; // Y вверх

    // copper — заливка
    if (copper?.paths?.length) {
      ctx.fillStyle = "hsl(25 75% 50% / 0.85)";
      ctx.beginPath();
      for (const poly of copper.paths) {
        if (poly.length < 2) continue;
        ctx.moveTo(tx(poly[0][0]), ty(poly[0][1]));
        for (let i = 1; i < poly.length; i++) ctx.lineTo(tx(poly[i][0]), ty(poly[i][1]));
        ctx.closePath();
      }
      ctx.fill("evenodd");
    }

    const drawLines = (paths: number[][][], color: string, widthPx: number) => {
      ctx.strokeStyle = color;
      ctx.lineWidth = widthPx;
      ctx.lineCap = "round";
      ctx.lineJoin = "round";
      ctx.beginPath();
      for (const poly of paths) {
        if (poly.length < 2) continue;
        ctx.moveTo(tx(poly[0][0]), ty(poly[0][1]));
        for (let i = 1; i < poly.length; i++) ctx.lineTo(tx(poly[i][0]), ty(poly[i][1]));
      }
      ctx.stroke();
    };

    // Line widths: scale with tool diameter (mm -> px via `scale`).
    const nccW = Math.max(1.0, (nccToolDiaMm ?? 0.2) * scale * 0.12);
    const cncW = Math.max(1.2, (cncToolDiaMm ?? 0.5) * scale * 0.12);
    if (ncc?.paths?.length) drawLines(ncc.paths, "hsl(222 90% 56% / 0.9)", nccW);
    if (cncjob?.paths?.length) drawLines(cncjob.paths, "hsl(88 70% 40% / 0.95)", cncW);
  }, [copper, ncc, cncjob, fit, nccToolDiaMm, cncToolDiaMm, pan.x, pan.y, size, zoom]);

  const isEmpty = !hasAny;

  const resetView = () => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  };

  const clampZoom = (z: number) => Math.max(0.2, Math.min(8, z));

  const zoomAt = (clientX: number, clientY: number, nextZoom: number) => {
    if (!wrapRef.current || !fit) {
      setZoom(nextZoom);
      return;
    }
    const rect = wrapRef.current.getBoundingClientRect();
    const x = clientX - rect.left;
    const y = clientY - rect.top;
    const prevScale = fit.scale * zoom;
    const newScale = fit.scale * nextZoom;
    // keep screen point stable by adjusting pan
    const dx = x - (fit.ox + pan.x);
    const dy = y - (fit.oy + pan.y);
    const ratio = newScale / (prevScale || 1);
    setPan({ x: pan.x + dx - dx * ratio, y: pan.y + dy - dy * ratio });
    setZoom(nextZoom);
  };

  const onWheel: React.WheelEventHandler<HTMLDivElement> = (e) => {
    if (!hasAny) return;
    e.preventDefault();
    const delta = e.deltaY;
    const factor = delta > 0 ? 0.92 : 1.08;
    const next = clampZoom(zoom * factor);
    zoomAt(e.clientX, e.clientY, next);
  };

  const onPointerDown: React.PointerEventHandler<HTMLDivElement> = (e) => {
    if (!hasAny) return;
    (e.currentTarget as any).setPointerCapture?.(e.pointerId);
    pointers.current.set(e.pointerId, { x: e.clientX, y: e.clientY });
    const pts = Array.from(pointers.current.values());
    if (pts.length === 1) {
      gesture.current = { type: "pan", startZoom: zoom, startPan: { ...pan }, startMid: { x: pts[0].x, y: pts[0].y }, startDist: 0 };
    } else if (pts.length >= 2) {
      const a = pts[0], b = pts[1];
      const mid = { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
      const dist = Math.hypot(a.x - b.x, a.y - b.y) || 1;
      gesture.current = { type: "pinch", startZoom: zoom, startPan: { ...pan }, startMid: mid, startDist: dist };
    }
  };

  const onPointerMove: React.PointerEventHandler<HTMLDivElement> = (e) => {
    if (!hasAny) return;
    if (!pointers.current.has(e.pointerId)) return;
    pointers.current.set(e.pointerId, { x: e.clientX, y: e.clientY });
    const g = gesture.current;
    if (!g) return;
    const pts = Array.from(pointers.current.values());
    if (g.type === "pan" && pts.length === 1) {
      const dx = pts[0].x - g.startMid.x;
      const dy = pts[0].y - g.startMid.y;
      setPan({ x: g.startPan.x + dx, y: g.startPan.y + dy });
    } else if (pts.length >= 2) {
      const a = pts[0], b = pts[1];
      const mid = { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
      const dist = Math.hypot(a.x - b.x, a.y - b.y) || 1;
      const nextZoom = clampZoom(g.startZoom * (dist / (g.startDist || 1)));
      // Zoom around start mid, then pan follows finger midpoint movement
      if (fit) {
        // compute zoom-at adjustment based on startMid
        const rect = wrapRef.current?.getBoundingClientRect();
        if (rect) {
          const x = g.startMid.x - rect.left;
          const y = g.startMid.y - rect.top;
          const prevScale = fit.scale * g.startZoom;
          const newScale = fit.scale * nextZoom;
          const dx0 = x - (fit.ox + g.startPan.x);
          const dy0 = y - (fit.oy + g.startPan.y);
          const ratio = newScale / (prevScale || 1);
          const panAfterZoom = { x: g.startPan.x + dx0 - dx0 * ratio, y: g.startPan.y + dy0 - dy0 * ratio };
          // plus translation by midpoint movement
          const mdx = mid.x - g.startMid.x;
          const mdy = mid.y - g.startMid.y;
          setPan({ x: panAfterZoom.x + mdx, y: panAfterZoom.y + mdy });
          setZoom(nextZoom);
        }
      } else {
        setZoom(nextZoom);
      }
    }
  };

  const onPointerUp: React.PointerEventHandler<HTMLDivElement> = (e) => {
    pointers.current.delete(e.pointerId);
    const pts = Array.from(pointers.current.values());
    if (pts.length === 0) gesture.current = null;
    else if (pts.length === 1) {
      // continue pan with remaining pointer
      gesture.current = { type: "pan", startZoom: zoom, startPan: { ...pan }, startMid: { x: pts[0].x, y: pts[0].y }, startDist: 0 };
    }
  };

  return (
    <div
      ref={wrapRef}
      className={className}
      onWheel={onWheel}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onPointerCancel={onPointerUp}
      style={{ touchAction: "none" }} // allow custom pan/zoom gestures inside preview
    >
      {isEmpty ? (
        <div className="w-full h-full flex items-center justify-center text-muted-foreground text-sm">
          {empty ?? "Превью появится здесь"}
        </div>
      ) : (
        <div className="relative w-full h-full">
          <canvas ref={canvasRef} />
          <div className="absolute right-3 top-3 flex items-center gap-2">
            <button
              type="button"
              onClick={() => zoomAt((wrapRef.current?.getBoundingClientRect().left ?? 0) + size.w / 2, (wrapRef.current?.getBoundingClientRect().top ?? 0) + size.h / 2, clampZoom(zoom * 1.15))}
              className="h-8 w-8 rounded-lg border border-border bg-background/80 backdrop-blur-sm hover:bg-background text-sm font-semibold"
              title="Zoom in"
            >
              +
            </button>
            <button
              type="button"
              onClick={() => zoomAt((wrapRef.current?.getBoundingClientRect().left ?? 0) + size.w / 2, (wrapRef.current?.getBoundingClientRect().top ?? 0) + size.h / 2, clampZoom(zoom / 1.15))}
              className="h-8 w-8 rounded-lg border border-border bg-background/80 backdrop-blur-sm hover:bg-background text-sm font-semibold"
              title="Zoom out"
            >
              −
            </button>
            <button
              type="button"
              onClick={resetView}
              className="h-8 px-2 rounded-lg border border-border bg-background/80 backdrop-blur-sm hover:bg-background text-[11px] font-mono"
              title="Reset view"
            >
              Reset
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
