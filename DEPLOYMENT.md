# Deployment Guide: Local, GitHub & Hugging Face

This guide details how to build, test, and deploy the 3D Outdoor Map Explorer across local servers, GitHub, and Hugging Face.

---

## 1. Local Server Deployment

To run locally with full asset serving and zero CORS issues:

```bash
# Start local explorer server
python -m app.process preview --port 8080
```
- Open browser at `http://127.0.0.1:8080/`.
- Press `[M]` to open Map Selection.
- Click to engage Pointer Lock and explore in First-Person POV.

---

## 2. GitHub Repository Deployment

The repository is hosted at:
[`https://github.com/timfromhcs/3d-outdoor-map-explorer`](https://github.com/timfromhcs/3d-outdoor-map-explorer)

To update and push new changes:
```bash
python scripts/deploy_github.py
```
This automatically stages tracked files, validates credentials from `.env`, runs a security check, and pushes to the `main` branch.

### GitHub Actions CI
The workflow in `.github/workflows/ci.yml` runs automatically on pushes:
- Sets up Python 3.12
- Installs dependencies
- Executes the Pytest suite
- Validates the map catalog and manifests

---

## 3. Hugging Face Space Deployment

The Space is hosted at:
[`https://huggingface.co/spaces/timfromhcs/3d-outdoor-map-explorer`](https://huggingface.co/spaces/timfromhcs/3d-outdoor-map-explorer)

To package and upload the distribution:
```bash
python scripts/deploy_huggingface.py
```
This builds the distribution bundle in `build_hf_space/` (with relative paths and required assets) and uses `huggingface_hub.HfApi.upload_folder` to deploy directly to the Space.
