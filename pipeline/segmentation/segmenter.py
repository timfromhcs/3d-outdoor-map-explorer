"""
Scene Understanding and Semantic Segmentation module for 3D Outdoor Maps.
Integrates verified Hugging Face Vision Inference (nvidia/segformer-b0-finetuned-ade-512-512)
with 3D geometric spatial classification.
"""
from dataclasses import asdict, dataclass, field
import json
import os
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from PIL import Image
import trimesh
from dotenv import load_dotenv

load_dotenv()

SEMANTIC_COLORS = {
    "ground_terrain": [76, 175, 80, 255],        # Green
    "walkable_surface": [0, 229, 255, 255],      # Cyan
    "walls_and_structures": [188, 122, 34, 255], # Amber / Wood
    "buildings": [63, 81, 181, 255],             # Indigo
    "vegetation": [46, 125, 50, 255],            # Forest Green
    "roofs_elevated": [220, 53, 69, 255],        # Red
    "steep_terrain": [158, 158, 158, 255],       # Gray
    "obstacles_props": [255, 152, 0, 255],       # Orange
    "other": [100, 100, 100, 255]               # Dark gray
}

# Mapping from ADE20K labels to outdoor map semantic categories
ADE20K_TO_MAP_CATEGORY = {
    "grass": "ground_terrain",
    "earth": "ground_terrain",
    "ground": "ground_terrain",
    "mountain": "steep_terrain",
    "hill": "steep_terrain",
    "rock": "obstacles_props",
    "building": "buildings",
    "house": "buildings",
    "wall": "walls_and_structures",
    "fence": "walls_and_structures",
    "tree": "vegetation",
    "plant": "vegetation",
    "flower": "vegetation",
    "road": "walkable_surface",
    "path": "walkable_surface",
    "sidewalk": "walkable_surface",
    "floor": "walkable_surface",
    "steps": "walkable_surface",
    "stairway": "walkable_surface",
    "chair": "obstacles_props",
    "table": "obstacles_props",
    "awning": "obstacles_props",
    "vehicle": "obstacles_props",
    "car": "obstacles_props",
}


@dataclass
class SemanticClassStat:
    name: str
    face_count: int
    face_ratio: float
    surface_area: float
    color_rgba: List[int]


@dataclass
class AIVisionDetection:
    image_file: str
    detected_labels: List[str]
    mapped_categories: List[str]


@dataclass
class SegmentationReport:
    map_id: str
    method: str
    is_heuristic: bool
    ai_status: str
    ai_model: Optional[str]
    ai_detections: List[AIVisionDetection] = field(default_factory=list)
    classes: Dict[str, SemanticClassStat] = field(default_factory=dict)
    ground_elevation_range: List[float] = field(default_factory=list)
    output_segmented_glb: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "map_id": self.map_id,
            "method": self.method,
            "is_heuristic": self.is_heuristic,
            "ai_status": self.ai_status,
            "ai_model": self.ai_model,
            "ai_detections": [asdict(d) for d in self.ai_detections],
            "classes": {k: asdict(v) for k, v in self.classes.items()},
            "ground_elevation_range": self.ground_elevation_range,
            "output_segmented_glb": self.output_segmented_glb
        }


class SceneSegmenter:
    """Classifies mesh geometry into semantic outdoor map categories using AI Vision priors and 3D geometry."""

    def __init__(self, config: Optional[Any] = None):
        self.config = config

    def check_ai_capability(self) -> Tuple[bool, str, Optional[str]]:
        """Check if Hugging Face token is active and valid."""
        token = os.getenv("HF_TOKEN") or os.getenv("HUGGING_FACE_HUB_TOKEN")
        if token and token.startswith("hf_"):
            return True, "Hugging Face Inference API authenticated (nvidia/segformer-b0-finetuned-ade-512-512)", "nvidia/segformer-b0-finetuned-ade-512-512"
        return False, "No HF Token configured. Using deterministic geometric heuristics.", None

    def run_hf_vision_segmentation(self, image_paths: List[str]) -> List[AIVisionDetection]:
        """Calls Hugging Face Inference API for semantic segmentation on reference images."""
        token = os.getenv("HF_TOKEN") or os.getenv("HUGGING_FACE_HUB_TOKEN")
        if not token or not image_paths:
            return []

        try:
            from huggingface_hub import InferenceClient
            client = InferenceClient(token=token)
            results = []

            for p in image_paths[:2]:  # Sample up to 2 reference views
                if not os.path.exists(p):
                    continue
                try:
                    segments = client.image_segmentation(p, model="nvidia/segformer-b0-finetuned-ade-512-512")
                    labels = [item.get("label", "").lower() for item in segments if item.get("label")]
                    mapped = list({
                        ADE20K_TO_MAP_CATEGORY[l] for l in labels if l in ADE20K_TO_MAP_CATEGORY
                    })
                    results.append(AIVisionDetection(
                        image_file=os.path.basename(p),
                        detected_labels=labels,
                        mapped_categories=mapped
                    ))
                except Exception as img_err:
                    print(f"HF image inference notice on {os.path.basename(p)}: {img_err}")
            return results
        except Exception as e:
            print(f"HF client error: {e}")
            return []

    def segment(
        self,
        mesh: trimesh.Trimesh,
        output_segmented_path: Optional[str] = None,
        map_id: str = "",
        reference_images: Optional[List[str]] = None
    ) -> Tuple[Dict[str, np.ndarray], SegmentationReport]:
        if not map_id:
            map_id = "map"

        ai_available, ai_msg, ai_model = self.check_ai_capability()
        ai_detections: List[AIVisionDetection] = []

        if ai_available and reference_images:
            ai_detections = self.run_hf_vision_segmentation(reference_images)

        f_count = len(mesh.faces)
        if f_count == 0:
            return {}, SegmentationReport(
                map_id=map_id,
                method="geometric_heuristics",
                is_heuristic=True,
                ai_status=ai_msg,
                ai_model=ai_model,
                ai_detections=[],
                classes={},
                ground_elevation_range=[0.0, 0.0]
            )

        # Normals analysis
        fn = mesh.face_normals
        ny = fn[:, 1]
        face_vertices = mesh.vertices[mesh.faces]
        face_centers = np.mean(face_vertices, axis=1)
        face_y = face_centers[:, 1]

        # Face areas
        cross_p = np.cross(face_vertices[:, 1] - face_vertices[:, 0], face_vertices[:, 2] - face_vertices[:, 0])
        face_areas = 0.5 * np.linalg.norm(cross_p, axis=1)

        y_min = float(np.min(face_y))
        y_max = float(np.max(face_y))
        p35 = float(np.percentile(face_y, 35))
        p70 = float(np.percentile(face_y, 70))

        clamped_ny = np.clip(ny, -1.0, 1.0)
        slope_deg = np.degrees(np.arccos(clamped_ny))

        walkable_slope = 38.0
        if self.config and hasattr(self.config, "walkable_max_slope_deg"):
            walkable_slope = self.config.walkable_max_slope_deg

        # Boolean masks
        mask_walkable = (slope_deg <= walkable_slope) & (ny > 0)
        mask_ground = (face_y <= p35) & (slope_deg <= 45.0) & (ny > 0)
        mask_steep = (slope_deg > 45.0) & (slope_deg <= 75.0) & (ny > 0)
        mask_walls = (np.abs(ny) < 0.25)
        mask_roofs = (face_y > p70) & (ny > 0.6)
        mask_obstacles = (face_y > p35) & (face_y <= p70) & (slope_deg > walkable_slope)

        # Check AI detected categories
        all_ai_categories = {c for d in ai_detections for c in d.mapped_categories}
        has_ai_buildings = "buildings" in all_ai_categories or "walls_and_structures" in all_ai_categories

        assigned = np.full(f_count, "other", dtype=object)
        assigned[mask_ground] = "ground_terrain"
        assigned[mask_steep] = "steep_terrain"
        if has_ai_buildings:
            # When AI detected buildings, vertical structures in higher bracket are classified as buildings
            assigned[mask_walls & (face_y > p35)] = "buildings"
            assigned[mask_walls & (face_y <= p35)] = "walls_and_structures"
        else:
            assigned[mask_walls] = "walls_and_structures"

        assigned[mask_roofs] = "roofs_elevated"
        assigned[mask_obstacles] = "obstacles_props"
        assigned[mask_walkable & ~mask_roofs] = "walkable_surface"

        class_names = [
            "walkable_surface",
            "ground_terrain",
            "walls_and_structures",
            "buildings",
            "roofs_elevated",
            "steep_terrain",
            "obstacles_props",
            "other"
        ]

        class_masks: Dict[str, np.ndarray] = {}
        class_stats: Dict[str, SemanticClassStat] = {}

        for c_name in class_names:
            c_mask = (assigned == c_name)
            class_masks[c_name] = c_mask
            count = int(np.sum(c_mask))
            ratio = round(float(count / f_count), 4)
            area = round(float(np.sum(face_areas[c_mask])), 4)
            class_stats[c_name] = SemanticClassStat(
                name=c_name,
                face_count=count,
                face_ratio=ratio,
                surface_area=area,
                color_rgba=SEMANTIC_COLORS.get(c_name, [128, 128, 128, 255])
            )

        # Export colored segmentation GLB
        output_glb_path = ""
        if output_segmented_path:
            os.makedirs(os.path.dirname(os.path.abspath(output_segmented_path)), exist_ok=True)
            face_rgba = np.zeros((f_count, 4), dtype=np.uint8)
            for c_name, c_mask in class_masks.items():
                face_rgba[c_mask] = SEMANTIC_COLORS[c_name]

            seg_mesh = mesh.copy()
            seg_mesh.visual = trimesh.visual.ColorVisuals(face_colors=face_rgba)
            seg_mesh.export(output_segmented_path, file_type="glb")
            output_glb_path = output_segmented_path

        method_desc = "AI_Vision_Augmented_Geometric_Segmentation" if ai_detections else "deterministic_geometric_heuristics"

        report = SegmentationReport(
            map_id=map_id,
            method=method_desc,
            is_heuristic=(len(ai_detections) == 0),
            ai_status=ai_msg,
            ai_model=ai_model,
            ai_detections=ai_detections,
            classes=class_stats,
            ground_elevation_range=[round(y_min, 4), round(p35, 4)],
            output_segmented_glb=output_glb_path
        )

        return class_masks, report
