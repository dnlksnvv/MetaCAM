export type ToolType = "V" | "C1" | "C2" | "C3" | "C4" | "B";

export interface NCCParams {
  toolDiameter: number;
  overlapPct: number;
  margin: number;
  connect: boolean;
  contour: boolean;
  checkValidity: boolean;
  checkInset: boolean;
  toolType: ToolType;
}

export interface MillingParams {
  toolDiameter: number;
  cutZ: number;
  travelZ: number;
  feedrateXY: number;
  feedrateZ: number;
  spindleSpeed: number;
  dwell: boolean;
  dwellTime: number;
  endMoveZ: number;
}

export interface UnifiedConfig {
  id?: string;
  hash?: string;
  method: "ncc";
  ncc: NCCParams;
  milling: MillingParams;
  created_at?: string;
  updated_at?: string;
}

export interface ProjectSummary {
  id: string;
  name: string;
  created_at: string;
  updated_at: string;
  source?: { filename: string; size_bytes: number };
  has_run?: boolean;
}

export interface PreviewData {
  bounds?: { minX: number; minY: number; maxX: number; maxY: number };
  copper?: { paths: number[][][] }; // массив полигонов: [ [x,y], ... ]
  width_mm?: number;
  height_mm?: number;
  // допускаем произвольные дополнительные поля от бэка
  [k: string]: any;
}

export interface RunSummary {
  id: string;
  status: "running" | "done" | "error";
  started_at?: string;
  finished_at?: string;
  error?: string;
  result?: {
    ncc_summary?: any;
    cncjob_summary?: any;
    gcode_path?: string;
  };
}

export interface ProjectDetails {
  project: ProjectSummary;
  preview?: PreviewData;
  latest?: RunSummary & { ncc?: any; cncjob?: any };
  config?: UnifiedConfig;
}

export interface GenerateResponse {
  project: ProjectSummary;
  config: UnifiedConfig;
  configs: UnifiedConfig[];
  run: RunSummary;
  copper?: PreviewData["copper"];
  ncc?: { paths: number[][][] };
  cncjob?: { paths: number[][][] };
  downloadUrl?: string;
}

export const DEFAULT_CONFIG: UnifiedConfig = {
  method: "ncc",
  ncc: {
    toolDiameter: 0.1,
    overlapPct: 40,
    margin: 1.0,
    connect: true,
    contour: true,
    checkValidity: true,
    checkInset: true,
    toolType: "V",
  },
  milling: {
    toolDiameter: 0.5,
    cutZ: -0.05,
    travelZ: 2.0,
    feedrateXY: 120,
    feedrateZ: 60,
    spindleSpeed: 0,
    dwell: false,
    dwellTime: 1.0,
    endMoveZ: 15.0,
  },
};
