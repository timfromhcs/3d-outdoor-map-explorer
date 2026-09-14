# Testing & Quality Assurance Suite

This document specifies the multi-level testing architecture, coverage, and automated verification tools.

---

## 1. Testing Pyramid

```
        ▲
       / \      Level 4: Live HF Space WebGL Verification (Playwright)
      /   \     Level 3: Local POV Browser E2E Tests (Playwright, 3 maps)
     /     \    Level 2: Headless Pipeline Integration Tests (Pytest)
    /_______\   Level 1: Unit Tests (Geometry, Cleaner, Optimizer, Val)
```

---

## 2. Test Execution Commands

### A. Run Pytest Suite
```bash
.venv\Scripts\pytest -v
```
Runs 15 automated unit and integration tests verifying asset discovery, binary GLB headers, geometry statistics, cleanup, decimation, collision generation, walkability extraction, and local HTTP endpoints.

### B. Run POV Walker Automated Browser Tests
```bash
node scripts/test_pov_walker.js
```
Automates Headless Chromium:
- Navigates to `map1`, `map2`, `map3`
- Verifies state transitions: `DISCOVERING` &rarr; `LOADING` &rarr; `READY`
- Engages PointerLock and simulates WASD movement
- Tests wall collision sliding
- Toggles developer layer overlays
- Tests dynamic catalog modal map switching
- Saves 12 visual proof screenshots in `reports/visual/`

### C. Run Live Hugging Face Space Test
```bash
node scripts/test_hf_space_live.js
```
Navigates to the live deployed URL `https://timfromhcs-3d-outdoor-map-explorer.static.hf.space`, confirms 3D WebGL rendering, and captures screenshot proof `reports/screenshot_hf_space_live.png`.
