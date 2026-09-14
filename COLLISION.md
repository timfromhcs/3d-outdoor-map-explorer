# Collision Geometry & Physics System

This document specifies the physical collision geometry generation, spatial structures, and runtime collision resolution against outdoor 3D maps.

---

## 1. Separation of Visual Render vs Physical Collision

| Attribute | Render Map (`render.glb`) | Collision Map (`collision.glb`) |
|---|---|---|
| **Objective** | Maximum visual fidelity & photorealism | Ultra-fast physics queries & zero snagging |
| **Polygon Count** | 58,000 – 142,000 Triangles | 2,500 – 6,000 Triangles |
| **Reduction vs Raw** | 55.0% Reduction | **97.0% – 99.0% Reduction** |
| **Visual Appearance** | Reconstructed Vertex Colors (`COLOR_0`) | Distinctive translucent rust material |
| **Topology** | Fine surface detail & sharp corners | Simplified convex structures & watertight bounds |

---

## 2. Collision Mesh Statistics

| Map | Raw Input Faces | Collision Mesh Faces | Reduction Ratio | Bounds ($X \times Y \times Z$) |
|---|---|---|---|---|
| **`map1`** | 316,572 | **6,330** | **-98.00%** | $0.55m \times 0.30m \times 0.52m$ |
| **`map2`** | 254,362 | **6,680** | **-97.37%** | $0.59m \times 0.28m \times 1.31m$ |
| **`map3`** | 130,436 | **3,000** | **-97.69%** | $1.33m \times 0.56m \times 1.11m$ |

---

## 3. Spatial Acceleration Structure

- **Bounding Volume Hierarchy (BVH)**:
  - When available via `three-mesh-bvh`, the collision geometry computes an AABB bounding volume hierarchy (`computeBoundsTree()`).
  - Accelerates horizontal multi-ray queries and downward floor snapping from $O(N)$ triangle scans to $O(\log N)$ tree traversals.

---

## 4. Collision Validation Scenarios

Verified during automated Playwright browser testing:
1. **Walk Straight**: Character traverses flat terrain smoothly without sinking or stuttering.
2. **Walk into Wall**: Character detects obstacle at radius $r$, deflects velocity along wall tangent, preventing wall penetration.
3. **Walk over Slope**: Character climbs upward up to $45^\circ$; slopes $> 45^\circ$ restrict climbing.
4. **Out-of-Bounds Fall Recovery**: If a character falls below map bounds ($y < \text{minY} - 0.5$), the engine automatically teleports the character back to the deterministic safe spawn point.
