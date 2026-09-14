# Hugging Face Deployment & Space Architecture

This document specifies the deployment architecture, configuration, and verification of the 3D Outdoor Map Explorer on Hugging Face Spaces.

---

## 1. Deployment Details

- **Space Repository**: [`https://huggingface.co/spaces/timfromhcs/3d-outdoor-map-explorer`](https://huggingface.co/spaces/timfromhcs/3d-outdoor-map-explorer)
- **Direct Web App URL**: [`https://timfromhcs-3d-outdoor-map-explorer.static.hf.space`](https://timfromhcs-3d-outdoor-map-explorer.static.hf.space)
- **Account / Author**: `timfromhcs`
- **SDK**: `static` (Static HTML/JS/WebGL Space)
- **Runtime Stage**: `RUNNING`

---

## 2. Why Static Space Architecture?

The 3D POV Walker is an entirely client-side WebGL / Three.js 3D application:
1. **Zero Cold-Start Latency**: Unlike Docker/Gradio/Streamlit spaces which sleep and require 60–90 seconds to boot up a Python container, a Static Space serves assets immediately via Hugging Face Cloudflare CDN.
2. **Instant Asset Streaming**: 3D GLBs are delivered directly with native HTTP caching and range requests.
3. **High Framerate WebGL**: Rendering occurs directly on the client's GPU, avoiding slow WebRTC/VNC remote rendering streams.

---

## 3. Automated Live Space Verification

Verified via Headless Chromium in [`scripts/test_hf_space_live.js`](file:///C:/Users/hcsme/Desktop/mapbuilder/scripts/test_hf_space_live.js):

```json
{
  "timestamp": "2026-09-14T20:39:23Z",
  "hf_space_url": "https://timfromhcs-3d-outdoor-map-explorer.static.hf.space",
  "load_time_ms": 4603,
  "stats": {
    "fps": "11 FPS",
    "pos": "0.07, -0.16, 1.22",
    "heading": "N (0°)",
    "triangles": 142440,
    "calls": 1
  },
  "console_errors": [],
  "status": "VERIFIED"
}
```

- **HTTP Status**: 200 OK across HTML, CSS, JS, catalog, and GLB buffers.
- **Console Errors**: 0 unhandled exceptions.
- **Visual Proof**: Captured directly from the live URL to `reports/screenshot_hf_space_live.png`.
