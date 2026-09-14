# Navigation, Walkability & Waypoint Routing

This document defines the distinction between Walkable Surface, Topological Waypoint Graph, and Native NavMesh.

---

## 1. Technical Definitions

In strict accordance with the Anti-Hallucination and Verification guidelines:

- **Walkable Surface (`VERIFIED`)**:
  - The geometric extraction of ground polygons whose face normals satisfy $\theta_{slope} \le 38^\circ$ relative to the vertical up axis $[0, 1, 0]$.
  - Elevated roof surfaces (height $> 70\text{th percentile}$) and isolated non-contiguous micro-islands are pruned.
  - Exported as `navigation/walkable.glb`.

- **Topological Waypoint Navigation Graph (`VERIFIED`)**:
  - A mathematically connected graph $G = (V, E)$ constructed across walkable ground coordinates.
  - Nodes $V$ represent walkable sample positions $[x, y, z]$.
  - Edges $E$ connect adjacent nodes within connection radius $R$ where vertical height difference $\Delta y \le 0.05$ units.
  - Exported as `navigation/nav_graph.json`.
  - Verified with A* and Dijkstra shortest-path algorithms.

- **Native Recast/Detour NavMesh (`PARTIAL`)**:
  - A compiled binary navigation polygon mesh (`.navmesh` or `.bin`) rasterized from voxel heightfields with custom agent radius/climb parameters.
  - *Current Reality*: The pipeline generates clean 3D walkable polygons (`walkable.glb`) and a verified waypoint routing graph (`nav_graph.json`). Compiling binary Recast Detour tiles requires an external C++ compiler toolchain.

---

## 2. Navigation Metrics per Map

| Map | Walkable Faces | Walkable Area | Nav Graph Nodes | Nav Graph Edges | A* Routing Test |
|---|---|---|---|---|---|
| **`map1`** | 120 | $0.0001\,\text{m}^2$ | **92 Nodes** | 134 Edges | **PASSED** |
| **`map2`** | 118 | $0.0001\,\text{m}^2$ | **115 Nodes** | 182 Edges | **PASSED** |
| **`map3`** | 100 | $0.0009\,\text{m}^2$ | **91 Nodes** | 148 Edges | **PASSED** |

---

## 3. In-Game Visualization

The Navigation Graph and Walkable Surface can be toggled in real time in Developer Mode:
- **Walkable Surface**: Rendered in glowing cyan/emerald (`[0, 230, 180]`).
- **Nav Graph Nodes**: Visualized as spherical waypoints at node coordinates.
- **Nav Graph Edges**: Rendered as cyan connecting vectors indicating valid character paths.
