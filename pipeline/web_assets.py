"""
Web Asset Optimizer module.
Transforms processed offline assets into ultra-lean, web-ready GLBs and web manifests.
"""
from dataclasses import asdict, dataclass
import json
import os
import shutil
from typing import Any, Dict, List, Optional
import trimesh
from pipeline.discovery import compute_sha256


@dataclass
class WebAssetStat:
    asset_name: str
    original_size_bytes: int
    web_size_bytes: int
    reduction_percentage: float
    triangles: int
    vertices: int


@dataclass
class WebPackageReport:
    map_id: str
    total_original_bytes: int
    total_web_bytes: int
    overall_reduction_pct: float
    assets: List[WebAssetStat]
    output_dir: str

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["assets"] = [asdict(a) for a in self.assets]
        return data


class WebAssetOptimizer:
    """Optimizes 3D assets specifically for fast web delivery and low VRAM footprint."""

    def optimize_map_for_web(self, map_id: str, map_dir: str) -> WebPackageReport:
        web_dir = os.path.join(map_dir, "web")
        os.makedirs(web_dir, exist_ok=True)

        asset_stats: List[WebAssetStat] = []
        total_orig = 0
        total_web = 0

        # 1. Web Render Mesh
        render_src = os.path.join(map_dir, "optimized", "render.glb")
        web_render = os.path.join(web_dir, "render.glb")
        if os.path.exists(render_src):
            orig_sz = os.path.getsize(render_src)
            m = trimesh.load(render_src, process=False)
            if isinstance(m, trimesh.Scene):
                submeshes = [g for g in m.geometry.values() if isinstance(g, trimesh.Trimesh)]
                m = trimesh.util.concatenate(submeshes) if submeshes else trimesh.Trimesh()

            # Clean and compact
            m.remove_unreferenced_vertices()
            m.export(web_render, file_type="glb")
            web_sz = os.path.getsize(web_render)
            red = round(100.0 * (1.0 - (web_sz / max(1, orig_sz))), 2)

            asset_stats.append(WebAssetStat(
                "render.glb", orig_sz, web_sz, red, len(m.faces), len(m.vertices)
            ))
            total_orig += orig_sz
            total_web += web_sz

        # 2. Web Collision Mesh
        col_src = os.path.join(map_dir, "collision", "collision.glb")
        web_col = os.path.join(web_dir, "collision.glb")
        if os.path.exists(col_src):
            orig_sz = os.path.getsize(col_src)
            m = trimesh.load(col_src, process=False)
            if isinstance(m, trimesh.Scene):
                submeshes = [g for g in m.geometry.values() if isinstance(g, trimesh.Trimesh)]
                m = trimesh.util.concatenate(submeshes) if submeshes else trimesh.Trimesh()
            m.remove_unreferenced_vertices()
            m.export(web_col, file_type="glb")
            web_sz = os.path.getsize(web_col)
            red = round(100.0 * (1.0 - (web_sz / max(1, orig_sz))), 2)

            asset_stats.append(WebAssetStat(
                "collision.glb", orig_sz, web_sz, red, len(m.faces), len(m.vertices)
            ))
            total_orig += orig_sz
            total_web += web_sz

        # 3. Web Walkable Mesh
        walk_src = os.path.join(map_dir, "navigation", "walkable.glb")
        web_walk = os.path.join(web_dir, "walkable.glb")
        if os.path.exists(walk_src):
            orig_sz = os.path.getsize(walk_src)
            m = trimesh.load(walk_src, process=False)
            if isinstance(m, trimesh.Scene):
                submeshes = [g for g in m.geometry.values() if isinstance(g, trimesh.Trimesh)]
                m = trimesh.util.concatenate(submeshes) if submeshes else trimesh.Trimesh()
            m.remove_unreferenced_vertices()
            m.export(web_walk, file_type="glb")
            web_sz = os.path.getsize(web_walk)
            red = round(100.0 * (1.0 - (web_sz / max(1, orig_sz))), 2)

            asset_stats.append(WebAssetStat(
                "walkable.glb", orig_sz, web_sz, red, len(m.faces), len(m.vertices)
            ))
            total_orig += orig_sz
            total_web += web_sz

        # Copy nav_graph.json to web directory for easy browser consumption
        nav_graph_src = os.path.join(map_dir, "navigation", "nav_graph.json")
        if os.path.exists(nav_graph_src):
            shutil.copyfile(nav_graph_src, os.path.join(web_dir, "nav_graph.json"))

        # Write web package report
        overall_red = round(100.0 * (1.0 - (total_web / max(1, total_orig))), 2) if total_orig > 0 else 0.0
        rep = WebPackageReport(
            map_id=map_id,
            total_original_bytes=total_orig,
            total_web_bytes=total_web,
            overall_reduction_pct=overall_red,
            assets=asset_stats,
            output_dir=web_dir
        )

        with open(os.path.join(map_dir, "reports", "web_package.json"), "w", encoding="utf-8") as fp:
            json.dump(rep.to_dict(), fp, indent=2)

        return rep
