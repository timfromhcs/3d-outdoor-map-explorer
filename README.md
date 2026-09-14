# 3D Outdoor Map Explorer & First-Person POV Walker

An end-to-end platform for transforming raw/AI-reconstructed 3D outdoor environment models into game-ready, interactive, first-person browser worlds.

[![CI Test & Quality Verification](https://github.com/timfromhcs/3d-outdoor-map-explorer/actions/workflows/ci.yml/badge.svg)](https://github.com/timfromhcs/3d-outdoor-map-explorer/actions)
[![Hugging Face Space](https://img.shields.io/badge/%F0%9F%A4%97%20Hugging%20Face-Space%20Running-blue)](https://huggingface.co/spaces/timfromhcs/3d-outdoor-map-explorer)

- **Live Hugging Face Space**: [https://huggingface.co/spaces/timfromhcs/3d-outdoor-map-explorer](https://huggingface.co/spaces/timfromhcs/3d-outdoor-map-explorer)
- **Direct Web App**: [https://timfromhcs-3d-outdoor-map-explorer.static.hf.space](https://timfromhcs-3d-outdoor-map-explorer.static.hf.space)
- **GitHub Repository**: [https://github.com/timfromhcs/3d-outdoor-map-explorer](https://github.com/timfromhcs/3d-outdoor-map-explorer)

---

## What This Project Does

The system consists of two clear, decoupled layers:

1. **Offline Map Build Pipeline**:
   - Discovers raw 3D reconstruction files (`.glb`, `.gltf`, `.ply`, `.png`) in `Maps/*`.
   - Validates glTF binary headers, accessors, buffer views, and manifold topology.
   - Cleans up camera frustum gizmos, removes degenerate faces, and merges duplicate vertices.
   - Decimates geometry via Garland-Heckbert QEM (preserving vertex colors).
   - Generates physical collision meshes (`collision.glb`), walkable surfaces (`walkable.glb`), and topological navigation graphs (`nav_graph.json`).
   - Runs AI Vision scene understanding via Hugging Face Segformer ADE20K.
   - Calculates deterministic safe spawn points and builds manifests.

2. **Online Browser World Explorer & POV Walker**:
   - First-person kinematic character controller with PointerLock, WASD movement, sprint, jump, gravity, and floor snapping.
   - Physical collision detection preventing wall penetration and allowing smooth sliding along surfaces.
   - Real-time 2D top-down minimap with player dot and camera heading vision cone.
   - Dynamic multi-map catalog with seamless in-game map switching (`map1`, `map2`, `map3`).
   - Developer mode (`[Tab]`) toggling render, collision, walkable, nav graph, and segmentation layers with live statistics.

---

## Quick Start (Local Run)

```bash
# 1. Install dependencies
uv venv --python 3.12 .venv
.venv\Scripts\activate
uv pip install trimesh[easy] pygltflib numpy scipy pillow pytest networkx shapely fast-simplification python-dotenv huggingface_hub

# 2. Process all maps (or use cached outputs)
python -m app.process process-all

# 3. Start local Explorer server
python -m app.process preview --port 8080
```
Open your browser at `http://127.0.0.1:8080/`. Click the screen to engage First-Person POV!

---

## Controls & Keybindings

| Key | Action |
|---|---|
| **`W` `A` `S` `D`** | Walk forward, left, backward, right |
| **`Shift`** | Sprint ($2.0\times$ speed multiplier) |
| **`Space`** | Jump |
| **`Mouse`** | Look around (Yaw / Pitch) |
| **`V`** | Toggle First-Person POV / Aerial Orbit Camera |
| **`Tab`** | Toggle Developer Mode & Layer Inspection |
| **`M`** | Open Map Selection Catalog Modal |
| **`R`** | Safe Spawn Reset (respawn on ground) |
| **`Esc`** | Release mouse cursor |

---

## Real Map Inventory

| Map ID | Source File | Vertices | Render Triangles | Collision Triangles | Walkable Area | Nav Nodes |
|---|---|---|---|---|---|---|
| **`map1`** | `glbscene_All_camTrue_meshTrue (2).glb` | 160,485 | 142,440 (-55%) | 6,330 (-98%) | $0.0001\,\text{m}^2$ | 92 |
| **`map2`** | `glbscene_All_camTrue_meshTrue (1).glb` | 129,616 | 114,424 (-55%) | 6,680 (-97%) | $0.0001\,\text{m}^2$ | 115 |
| **`map3`** | `glbscene_All_camTrue_meshTrue.glb` | 67,340 | 58,454 (-55%) | 3,000 (-98%) | $0.0009\,\text{m}^2$ | 91 |

---

## Documentation Index

- [`ARCHITECTURE.md`](file:///C:/Users/hcsme/Desktop/mapbuilder/ARCHITECTURE.md) – System layout and Mermaid architecture diagrams.
- [`MAP_PIPELINE.md`](file:///C:/Users/hcsme/Desktop/mapbuilder/MAP_PIPELINE.md) – Detailed pipeline stages and configuration parameters.
- [`POV_WALKER.md`](file:///C:/Users/hcsme/Desktop/mapbuilder/POV_WALKER.md) – First-person controller kinematic equations and scale calibration.
- [`COLLISION.md`](file:///C:/Users/hcsme/Desktop/mapbuilder/COLLISION.md) – Physical collision geometry, BVH queries, and sliding mechanics.
- [`NAVIGATION.md`](file:///C:/Users/hcsme/Desktop/mapbuilder/NAVIGATION.md) – Walkable surface extraction vs topological waypoint graphs.
- [`WEB_ASSETS.md`](file:///C:/Users/hcsme/Desktop/mapbuilder/WEB_ASSETS.md) – Web optimization and compression benchmarks.
- [`HUGGINGFACE.md`](file:///C:/Users/hcsme/Desktop/mapbuilder/HUGGINGFACE.md) – Static Space architecture and live CDN endpoints.
- [`DEPLOYMENT.md`](file:///C:/Users/hcsme/Desktop/mapbuilder/DEPLOYMENT.md) – Deployment instructions for local, GitHub, and Hugging Face.
- [`TESTING.md`](file:///C:/Users/hcsme/Desktop/mapbuilder/TESTING.md) – Pytest suite and Playwright automated browser tests.
- [`PERFORMANCE.md`](file:///C:/Users/hcsme/Desktop/mapbuilder/PERFORMANCE.md) – Real frame rates, load times, and memory benchmarks.
- [`TROUBLESHOOTING.md`](file:///C:/Users/hcsme/Desktop/mapbuilder/TROUBLESHOOTING.md) – Solutions for common defects and environment issues.
- [`CAPABILITIES.md`](file:///C:/Users/hcsme/Desktop/mapbuilder/CAPABILITIES.md) – Strict classification into `VERIFIED`, `PARTIAL`, `UNAVAILABLE`.
- [`FINAL_REPORT.md`](file:///C:/Users/hcsme/Desktop/mapbuilder/FINAL_REPORT.md) – Comprehensive audit and verification report.
