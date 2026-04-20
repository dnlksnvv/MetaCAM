# MetaCAM Web App (NCC → CNCJob) — Implementation Prompt

You are a senior full‑stack engineer. Implement a **beautiful, minimalist, startup‑style, light theme** web app (mobile‑first) for generating **NCC toolpaths and CNC G-code** from a Gerber file, with an extremely simple UX.

This codebase already contains a working FastAPI backend and NCC + simplified Milling pipeline:

- Backend: `metacam_py/metacam/` (FastAPI)
- Current endpoints: `/api/v1/gerber/preview`, `/api/v1/ncc/generate`, `/api/v1/milling/generate_from_gerber`
- NCC implementation aligns with FlatCAM seed (`clear_polygon2` + `paint_connect` with R-tree), and “itself” selection.
- Current UI: `metacam_py/web/static/index.html` (basic demo)

Your job: turn it into a **production-quality web app UX** with **projects**, **saved configs**, and a **guided wizard**, inspired by:

- MetaSlice UI/UX: `https://github.com/dnlksnvv/MetaSlice.git`
- CybrixSolutions feel: `https://home.cybrixsolutions.net/`
- OpenClaw feel: `https://openclaw.ai/`

Do not overcomplicate. Use ready-made components. Optimize for mobile.

---

## 1) Product goal (what the user experiences)

### Mobile-first flow

1. User opens the site on mobile.
2. The center shows a **single prominent “Upload Gerber” button** (and drag&drop on desktop).
3. After upload, user immediately sees a **clean preview** of the board (copper rendering).
4. There is a single clear CTA: **“Convert to G-code”**.
5. Clicking it opens a **beautiful animated modal/wizard**:
   - Step A: “Choose milling method” (for now **only one option**: **NCC** with an icon tile)
   - Step B: Tool setup:
     - “Cutting diameter (mm)” (default 0.1)
     - “Tool type” select (default V)
     - Next
   - Step C: Overlap & Margin:
     - Overlap (%), Margin (mm)
     - “Advanced settings” collapsible section (default ON):
       - Connect
       - Contour
       - Check validity
       - Check inset
     - Next
   - Step D: Milling (CNCJob) parameters:
     - Dia (mm)
     - Cut Z
     - Travel Z
     - Feedrate X‑Y
     - Feedrate Z
     - Spindle speed
     - Dwell enable + dwell time
     - End move Z
     - Primary CTA: **Generate**

6. After Generate:
   - The app starts generation, shows **progress UI** (even if approximate), with a **nice animation**.
   - Once done:
     - Preview shows NCC path and CNCJob path overlay (different colors).
     - A **Download .nc** button appears.
     - A **“Edit parameters”** button lets the user re-open the wizard prefilled.

### Projects & Recents

- Each upload becomes a **Project** (saved server-side), including:
  - Original Gerber file
  - Cached preview (copper rendering metadata)
  - Latest generation results (NCC summary, CNCJob summary, stored `.nc` path)
  - The **last config used for this project** (so it can be reused across projects)
- Side menu (drawer) on mobile (left slide-in) and sidebar on desktop:
  - Projects list (most recent first)
  - Clicking a project loads its preview and last generated results **without starting a new generation**
  - A “New project” / “Upload” entry
  - Controls to **rename** and **delete** projects

### Saved configs behavior (critical)

- The user should **not** see NCC + Milling as “two different stages”. They pick/modify a **single unified config**.
- The app stores the **last 4 configs** (per user; simplest: global single-user store is fine for now).
- When user uploads a new file (creating a **new project**), they can:
  - Use “Default config”
  - Or pick one of the **last 4 configs** to prefill the wizard/form
  - Or pick the **last config of another project** (“Use config”) to prefill the wizard/form
- Important: picking a config **must not auto-generate**; the user explicitly presses **Generate**.
- If a new config is generated:
  - It becomes #1 in history
  - If more than 4 exist, delete the oldest
  - If the same config already exists, move it to the front (dedupe by content hash)
- Users must be able to **delete configs** from the recent list.

### Navigation rules

- Every wizard step must have **Back** and **Next** (or Generate at end).
- The wizard should be **stateful** and should restore last step state if user closes/open quickly (client state).

---

## 2) Tech constraints and preferences

### Design / UI

- Light theme, clean, minimal, “startup” feel.
- Mobile-first; responsive.
- Use **ready-made components**:
  - Prefer **Next.js + TypeScript + Tailwind + shadcn/ui** (Radix) OR equivalent modern stack.
  - Use Framer Motion (or similar) for wizard transitions (card flip / slide).
- Keep preview fast:
  - Don’t create thousands of SVG DOM nodes; use a single merged path or Canvas/WebGL layer.

### Backend

- Keep FastAPI.
- Current endpoints are not sufficient for the new UX; update/extend the API.
- Add persistence on server:
  - simplest: filesystem-based JSON + file storage inside `metacam_py/data/`
  - no authentication for now (single-user).

### Performance / payload size

- Never send megabytes of polyline JSON from client to server.
- Generate CNCJob/G-code **from the Gerber + config on the server**.
- Client should send only:
  - Project ID
  - Config ID (or config object)
  - “Generate” command

---

## 3) Data model (server-side)

Implement a minimal persistent store:

### Project

- `id`: string (uuid)
- `name`: string (default: uploaded filename)
- `created_at`, `updated_at`
- `source`:
  - `filename`
  - `path` to stored file
  - `size_bytes`
- `preview_path` (cached copper preview JSON path, stored on disk)
- `last_config` (the unified config object used most recently for this project; must stay small)
- `last_config_id` (optional reference to a global recent config id)
- `latest_run` (small summary only; never embed megabytes of toolpath/G-code):
  - `id`
  - `status`: running/done/error
  - `started_at`, `finished_at`, `error`
  - `result`:
    - `ncc_summary` (counts, bounds)
    - `cncjob_summary` (counts, bounds)
    - `gcode_path` (stored `.nc`)

Hard limits:
- Keep **max 4 projects** total (delete the oldest project directory when creating a new one).

### Unified Config (Method = NCC for now)

Store a single object, e.g.:

```json
{
  "id": "cfg_...",
  "method": "ncc",
  "ncc": {
    "toolDiameter": 0.1,
    "overlapPct": 40,
    "margin": 1.0,
    "connect": true,
    "contour": true,
    "checkValidity": true,
    "checkInset": true,
    "toolType": "V"
  },
  "milling": {
    "toolDiameter": 0.5,
    "cutZ": -0.05,
    "travelZ": 2.0,
    "feedrateXY": 120,
    "feedrateZ": 60,
    "spindleSpeed": 0,
    "dwell": false,
    "dwellTime": 1.0,
    "endMoveZ": 15.0
  },
  "created_at": "...",
  "updated_at": "..."
}
```

Maintain:

- `config_history`: array of last 4 configs, most recent first
- Deduplicate by stable hash of the normalized config JSON.
- Allow deletion by config id/hash.

---

## 4) New API (final contract)

Implement these endpoints under `/api/v1` (adjust if needed). Return JSON for metadata. For file downloads, return file responses.

### Projects

- `POST /projects`
  - multipart: `file`, optional `name`
  - response: `{ project, preview }`
  - store file on disk, create project record
  - compute preview and store as `preview.json` in project folder
  - enforce **max 4 projects** (delete oldest)

- `GET /projects`
  - response: `{ projects: ProjectSummary[] }`

- `GET /projects/{id}`
  - response: `{ project, preview?, latest?, config? }`
  - `latest` should contain stored artifacts if present (NCC/CNCJob previews), but must stay reasonably sized

- `GET /projects/{id}/source`
  - returns original file download

- `PATCH /projects/{id}`
  - multipart: `name`
  - response: `{ project }`

- `DELETE /projects/{id}`
  - deletes project directory including source + runs
  - response: `{ ok: true }`

### Configs

- `GET /configs/recent`
  - response: `{ configs: UnifiedConfig[] }` (max 4)

- `POST /configs`
  - multipart: `config` (JSON string)
  - response: `{ config, configs }`
  - server normalizes + hashes + saves + updates recents list (max 4)

- `DELETE /configs/{config_id_or_hash}`
  - response: `{ ok: true, configs }`

### Generation (single action)

- `POST /projects/{id}/generate`
  - multipart: optional `config_id`, optional `config` (JSON string)
  - behavior:
    - if `config` provided: save it as new config (dedupe), use it
    - run NCC + CNCJob generation server-side
    - store run artifacts on disk:
      - `runs/<run_id>/ncc.json`
      - `runs/<run_id>/cncjob.json` (without embedding gcode text)
      - `runs/<run_id>/job.nc`
    - update `project.last_config` and `project.last_config_id`
  - response: `{ project, config, configs, run, copper, ncc, cncjob, downloadUrl }`
  - keep payload reasonable; never embed huge strings inside `project.json`

- `GET /projects/{id}/runs/{run_id}`
  - response: status polling `{ run, progress? }`

- `GET /projects/{id}/runs/{run_id}/download`
  - returns `.nc` file download

### Notes about existing endpoints

You may keep existing:

- `/gerber/preview`
- `/ncc/generate`
- `/milling/generate_from_gerber`

But the new frontend should primarily use the **project-based** endpoints.

---

## 5) Backend implementation details

### Persistence

- Create `metacam_py/data/`:
  - `projects/PROJECT_ID/<original_filename>`
  - `projects/PROJECT_ID/project.json` (small)
  - `projects/PROJECT_ID/preview.json`
  - `projects/PROJECT_ID/runs/RUN_ID/run.json`
  - `projects/PROJECT_ID/runs/RUN_ID/ncc.json`
  - `projects/PROJECT_ID/runs/RUN_ID/cncjob.json`
  - `projects/PROJECT_ID/runs/RUN_ID/job.nc`
  - `configs/configs.json` (recent list + stored configs)

Use atomic writes (write temp then rename).

Never store huge toolpath arrays or gcode strings inside `project.json`. If legacy data exists, compact it automatically.

### Generation pipeline (server)

When generating:

- Parse preview for copper (existing `parse_gerber_preview`)
- Run NCC: `generate_ncc_from_gerber_bytes(data, ncc_params)`
- Run milling: `generate_cncjob_gcode(tp.lines, milling_params)`
- Store `job.nc` and return metadata + optional toolpath previews.

### Progress UI

Even if the generation is synchronous initially, implement:

- Return quickly with a `run_id` and status `running`
- Execute generation in background (threadpool) OR keep sync but at least expose “in progress” state.

If background is too much, keep it synchronous but provide a spinner animation client-side.

### File size limits

Do not send `toolpath` as multipart part from client.
Always compute from Gerber server-side.

---

## 6) Frontend implementation (recommended)

### Stack

- Next.js (App Router) + TypeScript
- Tailwind CSS
- shadcn/ui components
- Framer Motion for animated wizard

### Layout

- Top bar: app name + hamburger menu (mobile) + actions (desktop)
- Left drawer: Projects list + Recent configs
- Main canvas: preview (copper + overlays)
- Primary action: Convert to G-code

### Wizard UX

- Modal full-screen on mobile
- Step transitions: slide left/right with easing
- Always show:
  - Step title
  - Back button
  - Next/Generate button

### Preview rendering

- Use a single SVG path per layer (copper, NCC, CNCJob) OR Canvas.
- Avoid thousands of DOM nodes.

### Recents

- After uploading, show “Use a recent config” carousel (up to 4), plus “Default”.
- Selecting a config **prefills the wizard only**. Generation starts only when user presses **Generate**.
- Add “Use config” action on each project card to prefill current project without switching projects.

---

## 7) Acceptance criteria

1. Mobile: open → upload → preview shows → convert → wizard → generate → preview overlays → download `.nc`.
2. User can go back/forward in wizard without losing inputs.
3. Last 4 unified configs are persisted on server and offered to user next time.
4. Projects persist on server; user can reopen a project from the side menu and regenerate using a recent config.
5. No request fails due to 1MB multipart part limit (no huge toolpath JSON uploads).
6. UI looks modern, minimalist, light, startup style and feels similar in polish to the references.
7. User can rename/delete projects; deleting removes stored source and runs.
8. User can delete recent configs.

---

## 8) Implementation notes (codebase specifics)

- Backend currently serves static files from `metacam_py/web/static`. You may:
  - Replace it with a Next.js app in a sibling folder, OR
  - Keep FastAPI as API only and serve Next.js separately.

For simplicity:

- Create `frontend/` Next.js app.
- Keep FastAPI on `:8081` and frontend on `:3000` with proxy `/api` routes.

---

## 9) Deliverables

- Implement backend persistence + new endpoints.
- Implement new frontend app with described UX.
- Update README with run instructions for both.
- Ensure code is clean and works on macOS.

