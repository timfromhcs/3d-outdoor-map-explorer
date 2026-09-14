"""
deploy_huggingface.py
Prepares and deploys the 3D Outdoor Map Explorer & POV Walker
as an official Hugging Face Static Space for user timfromhcs.
"""
import os
import shutil
from dotenv import load_dotenv
from huggingface_hub import HfApi

load_dotenv()

HF_TOKEN = os.getenv("HF_TOKEN")
if not HF_TOKEN:
    raise RuntimeError("HF_TOKEN not found in environment variables or .env")

api = HfApi(token=HF_TOKEN)
user = api.whoami()["name"]
repo_name = "3d-outdoor-map-explorer"
repo_id = f"{user}/{repo_name}"

print(f"Target Hugging Face Space: https://huggingface.co/spaces/{repo_id}")

# 1. Prepare clean deployment directory
dist_dir = os.path.abspath("build_hf_space")
if os.path.exists(dist_dir):
    shutil.rmtree(dist_dir)
os.makedirs(dist_dir, exist_ok=True)

# 2. Write Space README.md with YAML frontmatter
readme_content = """---
title: 3D Outdoor Map Explorer & POV Walker
emoji: 🌐
colorFrom: blue
colorTo: green
sdk: static
pinned: false
---

# 3D Outdoor Map Explorer & POV Walker

Interactive browser-based first-person 3D reconstruction explorer powered by Three.js and WebGL.

- **First-Person POV**: Pointer Lock, WASD movement, sprint, jump, gravity.
- **Physical Collision**: Kinematic character controller sliding against physical collision meshes.
- **Walkable Surface & Nav Graph**: Reconstructed terrain pathfinding.
- **Real Maps**: Reconstructed outdoor environments (`map1`, `map2`, `map3`).
"""

with open(os.path.join(dist_dir, "README.md"), "w", encoding="utf-8") as fp:
    fp.write(readme_content)

# 3. Copy public static assets (HTML, CSS, JS, Vendor)
shutil.copytree("public/css", os.path.join(dist_dir, "css"))
shutil.copytree("public/js", os.path.join(dist_dir, "js"))
shutil.copytree("public/vendor", os.path.join(dist_dir, "vendor"))

# Adapt index.html with relative paths (e.g. "./css/style.css" instead of "/css/style.css")
with open("public/index.html", "r", encoding="utf-8") as fp:
    html = fp.read()

# Replace root-relative paths with relative paths for Space hosting
html = html.replace('href="/css/', 'href="./css/')
html = html.replace('src="/vendor/', 'src="./vendor/')
html = html.replace('src="/js/', 'src="./js/')

with open(os.path.join(dist_dir, "index.html"), "w", encoding="utf-8") as fp:
    fp.write(html)

# 4. Copy required map assets (render, collision, walkable, segmentation, nav_graph, manifests, catalog)
dist_output = os.path.join(dist_dir, "output")
os.makedirs(dist_output, exist_ok=True)

shutil.copyfile("output/catalog.json", os.path.join(dist_output, "catalog.json"))

for map_id in ["map1", "map2", "map3"]:
    src_map_dir = os.path.join("output", map_id)
    dst_map_dir = os.path.join(dist_output, map_id)
    os.makedirs(dst_map_dir, exist_ok=True)

    # Manifest
    if os.path.exists(os.path.join(src_map_dir, "manifest.json")):
        shutil.copyfile(os.path.join(src_map_dir, "manifest.json"), os.path.join(dst_map_dir, "manifest.json"))

    # Render GLB
    os.makedirs(os.path.join(dst_map_dir, "optimized"), exist_ok=True)
    shutil.copyfile(os.path.join(src_map_dir, "optimized", "render.glb"), os.path.join(dst_map_dir, "optimized", "render.glb"))

    # Collision GLB
    os.makedirs(os.path.join(dst_map_dir, "collision"), exist_ok=True)
    shutil.copyfile(os.path.join(src_map_dir, "collision", "collision.glb"), os.path.join(dst_map_dir, "collision", "collision.glb"))

    # Walkable & Nav Graph
    os.makedirs(os.path.join(dst_map_dir, "navigation"), exist_ok=True)
    shutil.copyfile(os.path.join(src_map_dir, "navigation", "walkable.glb"), os.path.join(dst_map_dir, "navigation", "walkable.glb"))
    shutil.copyfile(os.path.join(src_map_dir, "navigation", "nav_graph.json"), os.path.join(dst_map_dir, "navigation", "nav_graph.json"))

    # Segmentation GLB
    os.makedirs(os.path.join(dst_map_dir, "segmentation"), exist_ok=True)
    if os.path.exists(os.path.join(src_map_dir, "segmentation", "segmented.glb")):
        shutil.copyfile(os.path.join(src_map_dir, "segmentation", "segmented.glb"), os.path.join(dst_map_dir, "segmentation", "segmented.glb"))

print(f"Prepared deployment package in {dist_dir}")

# 5. Create or verify Hugging Face Space
print(f"Creating / verifying space {repo_id}...")
space_url = api.create_repo(
    repo_id=repo_id,
    repo_type="space",
    space_sdk="static",
    exist_ok=True
)
print(f"Space confirmed: {space_url}")

# 6. Upload files to Space
print("Uploading space files to Hugging Face...")
api.upload_folder(
    folder_path=dist_dir,
    repo_id=repo_id,
    repo_type="space",
    commit_message="Deploy 3D Outdoor Map Explorer and POV Walker"
)

print(f"\n=======================================================")
print(f"SUCCESSFULLY DEPLOYED TO HUGGING FACE SPACE!")
print(f"Space URL: https://huggingface.co/spaces/{repo_id}")
print(f"Direct Web App: https://{user.lower()}-{repo_name.lower().replace('_', '-')}.hf.space")
print(f"=======================================================")
