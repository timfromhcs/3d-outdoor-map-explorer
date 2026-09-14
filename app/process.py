"""
Headless CLI and Main Entrypoint for 3D Outdoor Map Pipeline.
Supports scan, validate, process, process-all, report, clean, and preview.
"""
import argparse
import json
import os
import sys
import webbrowser
from typing import List, Optional

# Ensure safe UTF-8 output on Windows consoles
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from pipeline.config import PipelineConfig
from pipeline.discovery import AssetScanner, MapAssetInfo
from pipeline.validation.validator import GLBValidator
from pipeline.orchestrator import PipelineOrchestrator
from pipeline.viewer.server import start_server


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.process",
        description="Headless 3D Outdoor Map Processing Pipeline & Asset Optimizer"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # scan
    p_scan = subparsers.add_parser("scan", help="Scan and discover all 3D map files in input folders")
    p_scan.add_argument("--input", default=None, help="Custom input directory to scan")
    p_scan.add_argument("--export-md", default="reports/inventory.md", help="Path to export markdown inventory")
    p_scan.add_argument("--export-json", default="reports/inventory.json", help="Path to export JSON inventory")

    # validate
    p_val = subparsers.add_parser("validate", help="Validate raw GLB assets against glTF specs and geometry integrity")
    p_val.add_argument("--map", default=None, help="Specific Map ID to validate")
    p_val.add_argument("--input", default=None, help="Input directory")

    # clean
    p_clean = subparsers.add_parser("clean", help="Run conservative cleanup without decimation")
    p_clean.add_argument("--map", default=None, help="Specific Map ID to clean")
    p_clean.add_argument("--input", default=None, help="Input directory")
    p_clean.add_argument("--output", default=None, help="Output directory")

    # process
    p_proc = subparsers.add_parser("process", help="Process a specific 3D map through the full pipeline")
    p_proc.add_argument("--map", required=True, help="Map ID to process")
    p_proc.add_argument("--input", default=None, help="Input directory")
    p_proc.add_argument("--output", default=None, help="Output directory")
    p_proc.add_argument("--quality", choices=["high", "medium", "low"], default="medium", help="Target optimization quality")
    p_proc.add_argument("--force", action="store_true", help="Force reprocessing ignoring cache")
    p_proc.add_argument("--no-ai", action="store_true", help="Disable semantic segmentation")
    p_proc.add_argument("--no-navigation", action="store_true", help="Disable walkable surface and nav graph generation")

    # process-all (default)
    p_all = subparsers.add_parser("process-all", help="Automatically process all discovered 3D maps")
    p_all.add_argument("--input", default=None, help="Input directory")
    p_all.add_argument("--output", default=None, help="Output directory")
    p_all.add_argument("--quality", choices=["high", "medium", "low"], default="medium", help="Target optimization quality")
    p_all.add_argument("--force", action="store_true", help="Force reprocessing ignoring cache")
    p_all.add_argument("--no-ai", action="store_true", help="Disable semantic segmentation")
    p_all.add_argument("--no-navigation", action="store_true", help="Disable walkable surface and nav graph generation")

    # report
    p_rep = subparsers.add_parser("report", help="Generate summary report for processed maps")
    p_rep.add_argument("--output", default=None, help="Output directory containing processed maps")

    # preview
    p_prev = subparsers.add_parser("preview", help="Start local 3D viewer server")
    p_prev.add_argument("--host", default="127.0.0.1", help="Host interface")
    p_prev.add_argument("--port", type=int, default=8080, help="Port to listen on")
    p_prev.add_argument("--no-browser", action="store_true", help="Do not automatically open web browser")

    return parser


def cmd_scan(args, config: PipelineConfig):
    scanner = AssetScanner([args.input] if args.input else config.input_search_dirs)
    maps = scanner.scan()
    print(f"\nDiscovered {len(maps)} 3D Map Asset(s):")
    for m in maps:
        print(f"  • [{m.map_id}] {m.source_filename} ({m.file_size_mb} MB, {m.vertex_count:,} vertices, {m.triangle_count:,} triangles)")

    md_path = scanner.export_inventory_markdown(maps, args.export_md)
    json_path = scanner.export_inventory_json(maps, args.export_json)
    print(f"\nInventory exported to:\n  - {md_path}\n  - {json_path}")
    return 0


def cmd_validate(args, config: PipelineConfig):
    scanner = AssetScanner([args.input] if args.input else config.input_search_dirs)
    validator = GLBValidator()
    maps = scanner.scan()

    if args.map:
        maps = [m for m in maps if m.map_id.lower() == args.map.lower()]

    if not maps:
        print("No matching maps found to validate.")
        return 1

    print(f"\nValidating {len(maps)} Map(s)...")
    all_ok = True
    for m in maps:
        rep = validator.validate(m.source_path, m.map_id)
        status_symbol = "[OK]" if rep.overall_status == "PASS" else ("[WARN]" if rep.overall_status == "WARN" else "[FAIL]")
        print(f"  {status_symbol} Map '{m.map_id}': Status = {rep.overall_status}")
        for c in rep.checks:
            if c.status != "PASS":
                print(f"      [{c.status}] {c.name}: {c.message}")
        if rep.overall_status == "FAIL":
            all_ok = False

    return 0 if all_ok else 1


def cmd_process(args, config: PipelineConfig):
    orchestrator = PipelineOrchestrator(config)
    scanner = AssetScanner([args.input] if args.input else config.input_search_dirs)
    maps = scanner.scan()

    target = next((m for m in maps if m.map_id.lower() == args.map.lower()), None)
    if not target:
        print(f"Error: Map '{args.map}' not found in discovered assets.")
        return 1

    print(f"Processing map: {target.map_id}...")
    report = orchestrator.process_map(
        asset=target,
        output_base_dir=args.output,
        quality=args.quality,
        force=args.force,
        no_ai=args.no_ai,
        no_navigation=args.no_navigation
    )

    print(f"\nQuality Gates for {report.map_id}:")
    for g in report.quality_gates:
        symbol = "[PASS]" if g.status in ["PASSED", "HEALED"] else "[FAIL]"
        print(f"  {symbol} GATE {g.gate_number}: {g.name} - {g.status} ({g.message})")

    return 0 if report.all_gates_passed else 1


def cmd_process_all(args, config: PipelineConfig):
    orchestrator = PipelineOrchestrator(config)
    if args.input:
        orchestrator.scanner = AssetScanner([args.input])

    reports = orchestrator.process_all(
        quality=args.quality,
        force=args.force,
        no_ai=args.no_ai,
        no_navigation=args.no_navigation
    )

    print("\n=======================================================")
    print("ALL MAPS PROCESSING SUMMARY")
    print("=======================================================")
    success_count = sum(1 for r in reports if r.all_gates_passed)
    print(f"Total Maps: {len(reports)} | Successfully Processed: {success_count} | Failed: {len(reports) - success_count}")

    for r in reports:
        status_text = "PASSED (Gates 1-9)" if r.all_gates_passed else "FAILED"
        print(f"  * {r.map_id}: {status_text} | SHA-256: {r.input_sha256[:10]}...")

    # Generate / update central catalog.json and individual manifests
    try:
        from pipeline.export.manifest import ManifestGenerator
        mg = ManifestGenerator()
        out_base = getattr(args, "output", None) or config.output_base_dir
        mg.generate_catalog(out_base)
    except Exception as e:
        print(f"Warning: Failed to regenerate catalog.json: {e}")

    return 0 if success_count == len(reports) else 1


def cmd_report(args, config: PipelineConfig):
    out_base = args.output or config.output_base_dir
    if not os.path.exists(out_base):
        print(f"Output directory does not exist: {out_base}")
        return 1

    print(f"\nMap Processing Reports in {out_base}:")
    for m_id in sorted(os.listdir(out_base)):
        proc_p = os.path.join(out_base, m_id, "reports", "process.json")
        if os.path.exists(proc_p):
            with open(proc_p, "r", encoding="utf-8") as f:
                d = json.load(f)
            opt = d.get("metrics", {}).get("optimization", {})
            col = d.get("metrics", {}).get("collision", {})
            walk = d.get("metrics", {}).get("walkability", {})
            print(f"\nMap: {m_id}")
            print(f"  - All Gates Passed: {d.get('all_gates_passed')}")
            print(f"  - Render Triangles: {opt.get('faces_after', 0):,} (-{opt.get('face_reduction_percentage', 0)}%)")
            print(f"  - Collision Triangles: {col.get('triangle_count', 0):,} (-{col.get('reduction_percentage', 0)}%)")
            print(f"  - Walkable Faces: {walk.get('walkable_faces_count', 0):,} (Area: {walk.get('walkable_area', 0)} m²)")
            print(f"  - Navigation Nodes: {walk.get('nav_graph', {}).get('total_nodes', 0)}")
    return 0


def cmd_clean(args, config: PipelineConfig):
    orchestrator = PipelineOrchestrator(config)
    scanner = AssetScanner([args.input] if args.input else config.input_search_dirs)
    maps = scanner.scan()

    if args.map:
        maps = [m for m in maps if m.map_id.lower() == args.map.lower()]

    out_base = args.output or config.output_base_dir
    for m in maps:
        val_path = os.path.join(out_base, m.map_id, "cleaned", "map_validated.glb")
        clean_path = os.path.join(out_base, m.map_id, "cleaned", "map_clean.glb")
        _, rep = orchestrator.cleaner.clean(m.source_path, val_path, clean_path, m.map_id)
        print(f"Cleaned {m.map_id}: {rep.faces_before:,} -> {rep.faces_after:,} faces (removed {rep.camera_gizmos_removed} gizmos)")
    return 0


def cmd_preview(args, config: PipelineConfig):
    url = f"http://{args.host}:{args.port}/"
    print(f"\nStarting 3D Map Viewer at {url}")
    if not args.no_browser:
        webbrowser.open(url)

    server = start_server(args.host, args.port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping viewer server.")
        server.server_close()
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    config = PipelineConfig.load()

    if not args.command:
        # Default run: process all discovered maps as requested in specification
        print("No command specified. Running default: process-all...")
        class DefaultArgs:
            input = None
            output = None
            quality = "medium"
            force = False
            no_ai = False
            no_navigation = False
        return cmd_process_all(DefaultArgs(), config)

    handlers = {
        "scan": cmd_scan,
        "validate": cmd_validate,
        "clean": cmd_clean,
        "process": cmd_process,
        "process-all": cmd_process_all,
        "report": cmd_report,
        "preview": cmd_preview,
    }

    handler = handlers.get(args.command)
    if handler:
        return handler(args, config)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
