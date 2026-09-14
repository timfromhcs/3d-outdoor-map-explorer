# 3D Outdoor Map Processing Pipeline & Asset Optimizer

A robust, headless, fully reproducible 3D asset pipeline for sanitizing, optimizing, and packaging raw/AI-reconstructed 3D outdoor environment models for real-time game engines (Unreal Engine, Unity, Godot, WebGL) and interactive browser viewing.

---

## Overview

Outdoor 3D reconstruction pipelines (such as 3D Gaussian Splatting, NeRFs, photogrammetry, and generative 3D meshes) produce dense, unorganized geometry full of defects:
- Millions of unoptimized polygons and duplicate vertices
- Embedded camera frustum gizmos (`geometry_1`)
- Floating noise particles and micro-components
- Degenerate (zero-area) triangles and non-manifold edges
- Inverted normals and missing collision representations
- No distinction between visual render mesh and physical collision bounds
- No walkable surface isolation or navigation graphs

This pipeline solves these issues automatically in a headless, non-destructive, and deterministic workflow.

---

## Input Directory Structure

The pipeline automatically discovers all 3D maps located in subfolders under `Maps/`, `input/`, or the project root. **No hardcoded file paths are required.**

```
Maps/
├── map1/
│   ├── glbscene_All_camTrue_meshTrue (2).glb   # Raw input mesh
│   ├── gaussians (2).ply                       # Gaussian point cloud
│   └── image (4).png, image (5).png           # Camera frames
├── map2/
│   ├── glbscene_All_camTrue_meshTrue (1).glb
│   └── ...
└── map3/
    ├── glbscene_All_camTrue_meshTrue.glb
    └── ...
```

---

## Output Directory Structure

For every processed map, an isolated, structured package is produced under `output/MAP_ID/`. The original input files are **never modified destructively**:

```
output/
└── map1/
    ├── cleaned/
    │   ├── map_validated.glb        # Camera gizmos removed, validated
    │   └── map_clean.glb            # Duplicates, noise & degenerate faces removed
    ├── optimized/
    │   ├── render.glb               # High-quality QEM decimated render mesh (LOD0)
    │   ├── render_lod1.glb          # Medium-distance LOD1 (~50% decimation)
    │   └── render_lod2.glb          # Long-distance LOD2 (~25% decimation)
    ├── collision/
    │   └── collision.glb            # Game-engine friendly physics mesh (~98% reduction)
    ├── navigation/
    │   ├── walkable.glb             # Isolated walkable terrain & paths (slope <= 38°)
    │   └── nav_graph.json           # Topological waypoint navigation graph with weights
    ├── segmentation/
    │   └── segmented.glb            # Semantically colorized terrain/wall/roof preview
    ├── reports/
    │   ├── validation.json          # glTF structure & topological audit
    │   ├── analysis.json            # Topography, bounds, normal distributions
    │   ├── cleanup.json             # Pruned gizmos, merged vertices, noise removal
    │   ├── optimization.json        # Decimation ratios & LOD statistics
    │   ├── collision.json           # Collision bounds & convex hulls
    │   ├── walkability.json         # Walkable surface area & nav metrics
    │   ├── segmentation.json        # Semantic classification breakdown
    │   └── process.json             # SHA-256 hashes of all inputs & outputs
    ├── scene.json                   # Standard descriptor for game engines & viewer
    └── preview/
        └── index.html               # Direct link to local browser viewer
```

---

## The 9 Quality Gates

Every map passes through nine strict quality gates:

1. **GATE 1 (File Readable)**: Verifies file existence and standard 12-byte GLB 2.0 binary header (`magic: b'glTF'`).
2. **GATE 2 (glTF Structure Valid)**: Validates JSON schema, buffer lengths, accessors, and node hierarchies.
3. **GATE 3 (Geometry Analyzed)**: Checks for finite coordinates (no `NaN`/`Inf`), bounding boxes, and normal distributions.
4. **GATE 4 (Cleanup Successful)**: Strips camera gizmos, removes degenerate faces, cleans micro-noise clusters, recomputes smooth normals.
5. **GATE 5 (Optimization Successful)**: Garland-Heckbert QEM simplification preserving vertex colors via cKDTree nearest-neighbor interpolation. Generates LOD0, LOD1, LOD2.
6. **GATE 6 (Render Mesh Generated)**: Validates `optimized/render.glb` readability and geometry.
7. **GATE 7 (Collision Geometry Generated)**: Emits simplified physics mesh (`collision.glb`) and convex hull bounds.
8. **GATE 8 (Walkable Surface Generated)**: Filters slope ($\le 38^\circ$) and builds topological waypoint graph (`nav_graph.json`).
9. **GATE 9 (Browser Viewer Verified)**: Verifies that all layers load cleanly over HTTP with zero errors.

---

## Installation

The project uses Python 3.12 (via `uv` or standard virtual environment).

```bash
# Clone or open workspace
cd mapbuilder

# Create virtual environment with uv or python
uv venv --python 3.12 .venv
# Windows:
.venv\Scripts\activate

# Install dependencies
uv pip install trimesh[easy] pygltflib numpy scipy pillow pytest networkx shapely fast-simplification
```

---

## Headless CLI Usage

All operations can be run headless from the terminal:

### 1. Scan and Discover Maps
```bash
python -m app.process scan
```
Discovers all maps, checks dimensions, vertex counts, and exports `reports/inventory.md` and `reports/inventory.json`.

### 2. Validate Raw Files
```bash
python -m app.process validate
```
Performs a deep structural and topological audit without modifying any files.

### 3. Process All Maps (Default)
```bash
python -m app.process process-all
# Or simply:
python -m app.process
```
Runs the full 9-stage pipeline on every discovered map. Supports caching (skips unchanged maps based on SHA-256 hashes).

### 4. Process a Specific Map
```bash
python -m app.process process --map map1 --quality high
python -m app.process process --map map3 --force
```

### 5. View Summary Reports
```bash
python -m app.process report
```

### 6. Start Local 3D Browser Viewer
```bash
python -m app.process preview
```
Starts the viewer server at `http://127.0.0.1:8080/` and opens the default web browser.

---

## Local 3D Browser Viewer

The viewer is built with Three.js (WebGL) and includes:
- **Map Selection**: Seamlessly switch between any processed map (`map1`, `map2`, `map3`).
- **Layer Toggles**:
  - `Render Mesh` (high-fidelity visual model)
  - `Collision Geometry` (translucent rust/orange physics mesh)
  - `Walkable Surface` (glowing cyan navigation surface)
  - `Semantic Segmentation` (color-coded terrain, walls, roofs)
  - `Wireframe Mode`
  - `Bounding Box Helper`
- **Realtime Statistics**: Live FPS counter, visible vertex count, visible triangle count, draw calls, and map extents (width, height, depth in meters).
- **Camera Controls**: Orbit, Pan, Zoom, and Reset Camera to fit the scene bounding box.

---

## Testing & Verification

Run the comprehensive test suite:

```bash
.venv\Scripts\pytest -v
```

All 15 tests pass across unit, integration, server, and end-to-end stages:
```
tests/test_analysis.py::test_analyzer_metrics PASSED
tests/test_cleanup.py::test_cleanup_gizmos_and_noise PASSED
tests/test_collision.py::test_collision_generation PASSED
tests/test_discovery.py::test_asset_scanner_discovers_all_maps PASSED
tests/test_discovery.py::test_map_asset_properties PASSED
tests/test_discovery.py::test_sha256_computation PASSED
tests/test_end_to_end.py::test_full_pipeline_end_to_end_on_real_map PASSED
tests/test_optimization.py::test_optimizer_and_lods PASSED
tests/test_validation.py::test_validator_on_raw_glb PASSED
tests/test_validation.py::test_validator_on_nonexistent_file PASSED
tests/test_viewer_server.py::test_server_health_endpoint PASSED
tests/test_viewer_server.py::test_server_maps_catalog_endpoint PASSED
tests/test_viewer_server.py::test_server_verify_assets_endpoint PASSED
tests/test_viewer_server.py::test_server_viewer_html_serving PASSED
tests/test_walkability.py::test_walkable_surface_and_nav_graph PASSED
```

Automated visual verification via Playwright Headless Chromium renders all maps and saves visual proof screenshots into `reports/`:
- `reports/screenshot_map1_render.png`
- `reports/screenshot_map1_collision.png`
- `reports/screenshot_map1_walkable.png`
- `reports/screenshot_map3_render.png`
- `reports/visual_verification.json`

---

## Reproducibility & SHA-256 Hashes

Every run writes `output/MAP_ID/reports/process.json` recording:
- Operating system, Python version, processor, and dependency versions
- SHA-256 hash of the exact input source file
- SHA-256 hash and size of every generated file (`render.glb`, `collision.glb`, `walkable.glb`, etc.)
- Configuration parameters and quality profile
- Gate results, warnings, and error logs
