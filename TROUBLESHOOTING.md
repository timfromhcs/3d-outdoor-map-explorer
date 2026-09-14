# Troubleshooting Guide

Common issues, diagnostic procedures, and resolutions when processing raw 3D outdoor models.

---

## 1. Input Meshes with Camera Gizmos / Frustums
- **Symptom**: The scene contains small pyramids or wireframe camera pyramids floating in the sky.
- **Cause**: AI reconstruction tools (like 3D Gaussian Splatting, NeRF, InstantMesh, LGM) export the estimated camera poses alongside the world geometry (e.g. `geometry_1` with 14 vertices).
- **Resolution**: The pipeline automatically detects nodes with `cam`, `camera`, `gizmo`, or mesh primitives with $< 50$ vertices during `cleanup`. You can verify this in `output/MAP_ID/reports/cleanup.json`.

---

## 2. Windows Console Unicode Encoding (`UnicodeEncodeError`)
- **Symptom**: `UnicodeEncodeError: 'charmap' codec can't encode character ...`
- **Cause**: Standard Windows command prompt or PowerShell using legacy `cp1252` encoding cannot print Unicode checkmarks (`✓`).
- **Resolution**: The CLI automatically reconfigures `sys.stdout` to UTF-8 on Windows and defaults to ASCII status tags (`[PASS]`, `[WARN]`, `[FAIL]`, `[OK]`).

---

## 3. WebGL Context or CORS Issues in Viewer
- **Symptom**: Viewer shows "Failed to fetch" or black screen.
- **Cause**: Opening `index.html` directly via `file://` protocol triggers browser CORS security blocks against binary GLB files.
- **Resolution**: Always serve the viewer through the local HTTP server:
  ```bash
  python -m app.process preview
  ```
  The built-in server sends `Access-Control-Allow-Origin: *` and serves files with the official `model/gltf-binary` MIME type.

---

## 4. Non-Manifold AI Geometries
- **Symptom**: glTF validator warns about non-manifold edges.
- **Cause**: Marching-cubes surfaces from volumetric reconstruction frequently have self-intersections, T-junctions, or edges sharing $> 2$ triangles.
- **Resolution**: The pipeline runs `mesh.merge_vertices()`, removes zero-area triangles, and re-orients face normals during Gate 4. The resulting `map_clean.glb` achieves `Status: PASS` across all structural checks.

---

## 5. Walkable Area is Small or Empty
- **Symptom**: `walkable.glb` contains few triangles.
- **Cause**: The model may represent a vertical cliff, steep ravine, or cave wall where slopes exceed $38^\circ$.
- **Resolution**: Adjust `walkable_max_slope_deg` in `configs/default_config.json` (e.g. increase from 38.0 to 45.0 degrees) and re-run with `--force`:
  ```bash
  python -m app.process process --map map1 --force
  ```
