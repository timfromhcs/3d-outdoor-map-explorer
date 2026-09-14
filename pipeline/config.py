"""
Configuration management for the 3D Map Pipeline.
"""
from dataclasses import dataclass, field
import json
import os
from typing import Any, Dict, List, Optional


@dataclass
class CleanupConfig:
    remove_degenerate_faces: bool = True
    remove_duplicate_vertices: bool = True
    remove_isolated_components: bool = True
    min_component_faces: int = 50
    min_component_ratio: float = 0.005
    remove_camera_gizmos: bool = True
    rebuild_normals: bool = True
    unify_winding: bool = True
    align_ground_plane: bool = True
    world_scale: float = 25.0


@dataclass
class QualityTarget:
    render_ratio: float
    collision_ratio: float
    max_render_faces: int
    max_collision_faces: int


@dataclass
class SegmentationConfig:
    walkable_max_slope_deg: float = 38.0
    ground_height_quantile: float = 0.35
    min_cluster_faces: int = 40
    use_ai: bool = False


@dataclass
class CollisionConfig:
    method: str = "simplified_mesh_and_hulls"
    convex_hulls_max: int = 24
    target_faces: int = 3000


@dataclass
class NavigationConfig:
    enabled: bool = True
    slope_threshold_deg: float = 38.0
    min_walkable_area_ratio: float = 0.01
    nav_graph_sample_points: int = 500
    nav_graph_connect_radius: float = 0.08


@dataclass
class ViewerConfig:
    host: str = "127.0.0.1"
    port: int = 8080


@dataclass
class PipelineConfig:
    version: str = "1.0.0"
    pipeline_name: str = "Outdoor 3D Map Headless Pipeline"
    input_search_dirs: List[str] = field(default_factory=lambda: ["Maps"])
    output_base_dir: str = "output"
    reports_dir: str = "reports"
    default_quality: str = "medium"
    cleanup: CleanupConfig = field(default_factory=CleanupConfig)
    optimization_profiles: Dict[str, QualityTarget] = field(default_factory=lambda: {
        "high": QualityTarget(render_ratio=0.75, collision_ratio=0.15, max_render_faces=300000, max_collision_faces=8000),
        "medium": QualityTarget(render_ratio=0.45, collision_ratio=0.08, max_render_faces=150000, max_collision_faces=4000),
        "low": QualityTarget(render_ratio=0.20, collision_ratio=0.03, max_render_faces=50000, max_collision_faces=1500),
    })
    segmentation: SegmentationConfig = field(default_factory=SegmentationConfig)
    collision: CollisionConfig = field(default_factory=CollisionConfig)
    navigation: NavigationConfig = field(default_factory=NavigationConfig)
    viewer: ViewerConfig = field(default_factory=ViewerConfig)

    @classmethod
    def load(cls, config_path: Optional[str] = None) -> "PipelineConfig":
        if not config_path:
            default_path = os.path.join(os.path.dirname(__file__), "..", "configs", "default_config.json")
            if os.path.exists(default_path):
                config_path = default_path

        if config_path and os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            cleanup = CleanupConfig(**data.get("cleanup", {}))
            seg = SegmentationConfig(**data.get("segmentation", {}))
            col = CollisionConfig(**data.get("collision", {}))
            nav = NavigationConfig(**data.get("navigation", {}))
            view = ViewerConfig(**data.get("viewer", {}))

            profiles = {}
            for q_name, q_data in data.get("optimization", {}).items():
                profiles[q_name] = QualityTarget(**q_data)

            return cls(
                version=data.get("version", "1.0.0"),
                pipeline_name=data.get("pipeline_name", "Outdoor 3D Map Headless Pipeline"),
                input_search_dirs=data.get("input_search_dirs", ["Maps", "input", "."]),
                output_base_dir=data.get("output_base_dir", "output"),
                reports_dir=data.get("reports_dir", "reports"),
                default_quality=data.get("default_quality", "medium"),
                cleanup=cleanup,
                optimization_profiles=profiles if profiles else cls().optimization_profiles,
                segmentation=seg,
                collision=col,
                navigation=nav,
                viewer=view,
            )
        return cls()

    def get_quality_profile(self, quality_name: str) -> QualityTarget:
        return self.optimization_profiles.get(quality_name.lower(), self.optimization_profiles["medium"])
