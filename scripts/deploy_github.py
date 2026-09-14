"""
deploy_github.py
Creates and pushes the 3D Outdoor Map Explorer to GitHub for user timfromhcs.
"""
import os
import subprocess
import urllib.request
import json
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("GITHUB_TOKEN")
USER = os.getenv("GITHUB_USERNAME", "timfromhcs")
REPO_NAME = "3d-outdoor-map-explorer"

if not TOKEN:
    raise RuntimeError("GITHUB_TOKEN not found in environment variables or .env")

# 1. Create or verify repo via GitHub API
print(f"Verifying GitHub repository: {USER}/{REPO_NAME}...")
req = urllib.request.Request(
    "https://api.github.com/user/repos",
    headers={
        "Authorization": f"token {TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "MapBuilder-Deployer"
    },
    data=json.dumps({
        "name": REPO_NAME,
        "description": "Headless 3D Outdoor Map Processing Pipeline & First-Person Browser World Explorer",
        "private": False,
        "has_issues": True,
        "has_wiki": True
    }).encode("utf-8")
)

try:
    with urllib.request.urlopen(req) as resp:
        print("Created new repository on GitHub:", resp.status)
except urllib.error.HTTPError as e:
    if e.code == 422:
        print("Repository already exists on GitHub (422).")
    else:
        print("GitHub API response:", e)

# 2. Configure git and push
print("Configuring local git repository...")
subprocess.run(["git", "init"], check=True)
subprocess.run(["git", "config", "user.name", USER], check=True)
subprocess.run(["git", "config", "user.email", f"{USER}@users.noreply.github.com"], check=True)
subprocess.run(["git", "branch", "-M", "main"], check=True)

# Add all files respecting .gitignore
subprocess.run(["git", "add", "."], check=True)

# Check if changes to commit
status = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True).stdout
if status:
    subprocess.run(["git", "commit", "-m", "feat: 3D Outdoor Map Processing Pipeline & POV Walker"], check=True)

# Remote URL with credential in temporary push command
remote_push_url = f"https://x-access-token:{TOKEN}@github.com/{USER}/{REPO_NAME}.git"
print("Pushing main branch to GitHub...")
push_res = subprocess.run(["git", "push", "-u", remote_push_url, "main", "--force"], capture_output=True, text=True)

if push_res.returncode == 0:
    print(f"\n=======================================================")
    print(f"SUCCESSFULLY PUSHED TO GITHUB!")
    print(f"Repository URL: https://github.com/{USER}/{REPO_NAME}")
    print(f"=======================================================")
else:
    print("Push error:", push_res.stderr)
