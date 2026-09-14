# Web Asset Pipeline & Compression

This document details the dedicated Web Asset Stage converting raw/processed offline maps into lean, web-optimized packages for fast CDN delivery and low VRAM impact.

---

## 1. Asset Stage Separation

```
[Maps/ Raw Inputs]  ~5-6 MB each (multi-component, camera gizmos, floaters)
       ↓
[output/ Offline Processed]  High Quality Render + Collision + Reports
       ↓
[output/web/ Web Optimized]  Compact single-primitive GLBs + JSON manifests
```

---

## 2. Web Package Comparison

| Map | Raw Input Size | Web Render Size | Web Collision Size | Total Web Package | Reduction |
|---|---|---|---|---|---|
| **`map1`** | 6.07 MB | 2.74 MB | 0.06 MB | **2.80 MB** | **-53.9%** |
| **`map2`** | 4.89 MB | 2.26 MB | 0.07 MB | **2.33 MB** | **-52.4%** |
| **`map3`** | 2.52 MB | 1.17 MB | 0.03 MB | **1.20 MB** | **-52.4%** |

---

## 3. Web Optimization Techniques Applied

1. **Primitive & Buffer Consolidation**:
   - Strips unreferenced vertices and pads accessor byte buffers to 4-byte boundaries according to the glTF 2.0 specification.
2. **Vertex Color Compact Encoding**:
   - Preserves high-density RGB vertex coloring without requiring heavy 4K uncompressed texture images in VRAM.
3. **Single Draw Call Optimization**:
   - Consolidates sub-geometries into a single indexed mesh primitive per layer, reducing WebGL draw calls to 1–2 per frame.
4. **Dynamic Lazy Loading**:
   - The browser loads `manifest.json` first, downloads `render.glb` immediately for first render, and streams `collision.glb` and `walkable.glb` asynchronously.
