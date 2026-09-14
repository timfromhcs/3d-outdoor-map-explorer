"""
Walkable Surface and Navigation Graph generation module for 3D Outdoor Maps.
Extracts slope-filtered walkable geometry and constructs topological waypoint navigation graphs.
"""
from dataclasses import asdict, dataclass, field
import json
import os
from typing import Any, Dict, List, Optional, Tuple
import networkx as nx
import numpy as np
from scipy.spatial import cKDTree
import trimesh
from pipeline.config import NavigationConfig


@dataclass
class NavGraphStats:
    total_nodes: int
    total_edges: int
    connected_components: int
    largest_component_nodes: int
    sample_path_found: bool
    sample_path_length: float
    sample_path_nodes: int


@dataclass
class WalkabilityReport:
    map_id: str
    walkable_faces_count: int
    walkable_area: float
    walkable_ratio: float
    slope_threshold_deg: float
    elevation_min: float
    elevation_max: float
    nav_graph: NavGraphStats
    output_walkable_glb: str
    output_nav_graph_json: str
    status: str  # "VERIFIED", "PARTIAL", "NO_WALKABLE_SURFACE"

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["nav_graph"] = asdict(self.nav_graph)
        return data


class WalkabilityAnalyzer:
    """Extracts walkable surfaces and computes waypoint navigation graphs."""

    def __init__(self, config: Optional[NavigationConfig] = None):
        self.config = config or NavigationConfig()

    def generate_walkable_surface(
        self,
        clean_mesh: trimesh.Trimesh,
        output_walkable_path: str,
        output_nav_graph_path: str,
        map_id: str = ""
    ) -> Tuple[Optional[trimesh.Trimesh], WalkabilityReport]:
        if not map_id:
            map_id = "map"

        os.makedirs(os.path.dirname(os.path.abspath(output_walkable_path)), exist_ok=True)
        os.makedirs(os.path.dirname(os.path.abspath(output_nav_graph_path)), exist_ok=True)

        f_count = len(clean_mesh.faces)
        if f_count == 0:
            empty_stats = NavGraphStats(0, 0, 0, 0, False, 0.0, 0)
            rep = WalkabilityReport(
                map_id=map_id,
                walkable_faces_count=0,
                walkable_area=0.0,
                walkable_ratio=0.0,
                slope_threshold_deg=self.config.slope_threshold_deg,
                elevation_min=0.0,
                elevation_max=0.0,
                nav_graph=empty_stats,
                output_walkable_glb="",
                output_nav_graph_json="",
                status="NO_WALKABLE_SURFACE"
            )
            return None, rep

        # 1. Slope & Elevation Filtering
        fn = clean_mesh.face_normals
        ny = fn[:, 1]
        clamped_ny = np.clip(ny, -1.0, 1.0)
        slope_deg = np.degrees(np.arccos(clamped_ny))

        face_vertices = clean_mesh.vertices[clean_mesh.faces]
        face_centers = np.mean(face_vertices, axis=1)
        face_y = face_centers[:, 1]

        # Calculate areas
        cross_p = np.cross(face_vertices[:, 1] - face_vertices[:, 0], face_vertices[:, 2] - face_vertices[:, 0])
        face_areas = 0.5 * np.linalg.norm(cross_p, axis=1)
        total_mesh_area = float(np.sum(face_areas))

        # Ground elevation upper bound (exclude roof structures)
        p70 = float(np.percentile(face_y, 70))

        # Walkable mask: slope <= threshold and upward normal and not extreme roof elevation
        walkable_mask = (slope_deg <= self.config.slope_threshold_deg) & (ny > 0.1) & (face_y <= p70)

        # 2. Extract Submesh of Walkable Faces
        walkable_face_indices = np.where(walkable_mask)[0]
        if len(walkable_face_indices) < 20:
            # Fallback: if p70 was too restrictive, check all low slope faces
            walkable_mask = (slope_deg <= self.config.slope_threshold_deg) & (ny > 0.1)
            walkable_face_indices = np.where(walkable_mask)[0]

        if len(walkable_face_indices) == 0:
            empty_stats = NavGraphStats(0, 0, 0, 0, False, 0.0, 0)
            rep = WalkabilityReport(
                map_id=map_id,
                walkable_faces_count=0,
                walkable_area=0.0,
                walkable_ratio=0.0,
                slope_threshold_deg=self.config.slope_threshold_deg,
                elevation_min=0.0,
                elevation_max=0.0,
                nav_graph=empty_stats,
                output_walkable_glb="",
                output_nav_graph_json="",
                status="NO_WALKABLE_SURFACE"
            )
            return None, rep

        # Submesh extraction
        walkable_faces = clean_mesh.faces[walkable_face_indices]
        unique_v_idx, new_faces = np.unique(walkable_faces, return_inverse=True)
        new_faces = new_faces.reshape(-1, 3)
        walkable_verts = clean_mesh.vertices[unique_v_idx]

        walkable_mesh = trimesh.Trimesh(vertices=walkable_verts, faces=new_faces, process=False)

        # Filter out micro-patches of walkable faces
        try:
            comps = trimesh.graph.connected_components(walkable_mesh.face_adjacency, min_len=10)
            if comps:
                # Keep components with at least 15 faces
                keep_f = []
                for c in comps:
                    if len(c) >= 15:
                        keep_f.extend(c)
                if keep_f:
                    f_mask = np.zeros(len(walkable_mesh.faces), dtype=bool)
                    f_mask[keep_f] = True
                    walkable_mesh.update_faces(f_mask)
                    walkable_mesh.remove_unreferenced_vertices()
        except Exception:
            pass

        # Give walkable mesh a distinctive glowing cyan/emerald green navigation material
        # RGBA: [0, 230, 180, 220]
        walkable_mesh.visual = trimesh.visual.ColorVisuals(
            face_colors=np.full((len(walkable_mesh.faces), 4), [0, 230, 180, 220], dtype=np.uint8)
        )

        walkable_mesh.export(output_walkable_path, file_type="glb")

        w_area = float(walkable_mesh.area)
        w_ratio = round(w_area / max(1e-5, total_mesh_area), 4)
        y_min_w = float(np.min(walkable_mesh.vertices[:, 1]))
        y_max_w = float(np.max(walkable_mesh.vertices[:, 1]))

        # 3. Generate Topological Waypoint Navigation Graph
        nav_stats = self._build_nav_graph(walkable_mesh, output_nav_graph_path)

        rep = WalkabilityReport(
            map_id=map_id,
            walkable_faces_count=len(walkable_mesh.faces),
            walkable_area=round(w_area, 4),
            walkable_ratio=w_ratio,
            slope_threshold_deg=self.config.slope_threshold_deg,
            elevation_min=round(y_min_w, 4),
            elevation_max=round(y_max_w, 4),
            nav_graph=nav_stats,
            output_walkable_glb=output_walkable_path,
            output_nav_graph_json=output_nav_graph_path,
            status="VERIFIED" if len(walkable_mesh.faces) > 0 else "PARTIAL"
        )

        return walkable_mesh, rep

    def _build_nav_graph(self, walkable_mesh: trimesh.Trimesh, output_json_path: str) -> NavGraphStats:
        """Constructs a waypoint graph from walkable mesh vertices and tests pathfinding."""
        if len(walkable_mesh.vertices) == 0:
            return NavGraphStats(0, 0, 0, 0, False, 0.0, 0)

        # Sample points on walkable surface or use decimated vertices
        n_verts = len(walkable_mesh.vertices)
        if n_verts > self.config.nav_graph_sample_points:
            sample_step = max(1, n_verts // self.config.nav_graph_sample_points)
            sample_indices = np.arange(0, n_verts, sample_step)
            nodes_xyz = walkable_mesh.vertices[sample_indices]
        else:
            nodes_xyz = walkable_mesh.vertices

        G = nx.Graph()
        for idx, pt in enumerate(nodes_xyz):
            G.add_node(int(idx), pos=[round(float(x), 4) for x in pt])

        # Connect nearby nodes using KDTree
        tree = cKDTree(nodes_xyz)
        radius = self.config.nav_graph_connect_radius
        pairs = tree.query_pairs(r=radius)

        for i, j in pairs:
            p1 = nodes_xyz[i]
            p2 = nodes_xyz[j]
            dist = float(np.linalg.norm(p1 - p2))
            height_diff = abs(float(p1[1] - p2[1]))
            # Only connect if height step is reasonable (e.g. not a vertical cliff edge)
            if height_diff < 0.05:
                G.add_edge(int(i), int(j), weight=round(dist, 4))

        # Analyze graph connectivity
        num_comps = nx.number_connected_components(G)
        largest_comp_nodes = 0
        sample_path_found = False
        sample_path_len = 0.0
        sample_path_nodes_count = 0

        if len(G) > 1 and num_comps > 0:
            largest_comp = max(nx.connected_components(G), key=len)
            largest_comp_nodes = len(largest_comp)

            # Test A* / shortest path between two distant nodes in largest component
            if largest_comp_nodes >= 2:
                comp_nodes = list(largest_comp)
                start_node = comp_nodes[0]
                end_node = comp_nodes[-1]
                try:
                    path = nx.shortest_path(G, source=start_node, target=end_node, weight="weight")
                    sample_path_found = True
                    sample_path_nodes_count = len(path)
                    sample_path_len = round(float(nx.path_weight(G, path, weight="weight")), 4)
                except Exception:
                    pass

        # Export navigation graph JSON
        graph_data = {
            "node_count": len(G.nodes),
            "edge_count": len(G.edges),
            "connected_components": num_comps,
            "largest_component_size": largest_comp_nodes,
            "nodes": [
                {"id": int(n), "x": G.nodes[n]["pos"][0], "y": G.nodes[n]["pos"][1], "z": G.nodes[n]["pos"][2]}
                for n in G.nodes
            ],
            "edges": [
                {"source": int(u), "target": int(v), "weight": G[u][v]["weight"]}
                for u, v in G.edges
            ]
        }

        with open(output_json_path, "w", encoding="utf-8") as f:
            json.dump(graph_data, f, indent=2)

        return NavGraphStats(
            total_nodes=len(G.nodes),
            total_edges=len(G.edges),
            connected_components=num_comps,
            largest_component_nodes=largest_comp_nodes,
            sample_path_found=sample_path_found,
            sample_path_length=sample_path_len,
            sample_path_nodes=sample_path_nodes_count
        )
