"""MeshForge Maya - Orchestration Pipeline Engine.
Manages non-destructive duplication, sequential phase execution, and full rollback guarantees.
"""

from __future__ import annotations
import maya.cmds as cmds
import time
from typing import Dict, Any, Optional

from .mesh_stats import get_mesh_statistics
from .conservative_cleaner import execute_conservative_cleanup
from .internal_walls import execute_remove_internal_walls
from .dissolve import execute_dissolve
from .simplification import execute_simplification
from .ngon_cutter import execute_ngon_cut
from .quadrangulator import execute_targeted_quadrangulation
from .normals import execute_normals
from .object_data import execute_object_data

def duplicate_object_non_destructive(source_name: str, suffix: str = "_MF_Optimized") -> str:
    """Creates an independent duplicate copy and hides the source object."""
    if suffix in source_name:
        return source_name

    root_name = source_name.split(suffix)[0]
    target_name = f"{root_name}{suffix}"

    # If an old optimized result already exists, remove it
    if cmds.objExists(target_name) and target_name != source_name:
        cmds.delete(target_name)

    new_obj = cmds.duplicate(source_name, name=target_name)[0]

    # Tag with custom attribute pointing to source
    if not cmds.attributeQuery("_mf_source_ptr", node=new_obj, exists=True):
        cmds.addAttr(new_obj, longName="_mf_source_ptr", dataType="string")
    cmds.setAttr(f"{new_obj}._mf_source_ptr", source_name, type="string")

    # Hide source
    if cmds.attributeQuery("visibility", node=source_name, exists=True):
        cmds.setAttr(f"{source_name}.visibility", False)

    return new_obj

def restore_original_object(optimized_name: str) -> Optional[str]:
    """Deletes the optimized object and unhides/restores the original source object."""
    if not cmds.objExists(optimized_name):
        return None

    source_name = None
    if cmds.attributeQuery("_mf_source_ptr", node=optimized_name, exists=True):
        source_name = cmds.getAttr(f"{optimized_name}._mf_source_ptr")

    if not source_name or not cmds.objExists(source_name):
        root = optimized_name.split("_MF_Optimized")[0]
        if cmds.objExists(root):
            source_name = root

    if source_name and cmds.objExists(source_name):
        cmds.setAttr(f"{source_name}.visibility", True)
        cmds.select(source_name)

    cmds.delete(optimized_name)
    return source_name

def run_meshforge_pipeline(source_name: str, settings: Dict[str, Any]) -> Dict[str, Any]:
    """Executes the complete MeshForge sequential pipeline with rollback on failure."""
    t0_total = time.perf_counter()
    report: Dict[str, Any] = {
        "success": False,
        "original_name": source_name,
        "result_name": "",
        "initial_stats": {},
        "final_stats": {},
        "phase_timings": {},
        "reduction_percentage": 0.0,
        "logs": [],
        "errors": []
    }

    if not source_name or not cmds.objExists(source_name):
        report["errors"].append(f"Object '{source_name}' does not exist.")
        return report

    # 1. Initial Diagnostic
    t0 = time.perf_counter()
    stats_before = get_mesh_statistics(source_name)
    report["initial_stats"] = stats_before
    report["phase_timings"]["diagnostic_initial"] = time.perf_counter() - t0

    # 2. Non-Destructive Duplication
    create_new = settings.get("create_new_object", True)
    if create_new:
        target_name = duplicate_object_non_destructive(source_name)
        report["logs"].append(f"Created duplicate object '{target_name}'. Original hidden.")
    else:
        target_name = source_name
        report["logs"].append("Direct destructive mode active on selected object.")

    report["result_name"] = target_name

    try:
        # 3. Conservative Repair
        if settings.get("enable_repair", True):
            t0 = time.perf_counter()
            r_rep = execute_conservative_cleanup(
                target_name,
                clean_loose_verts=settings.get("clean_loose_verts", True),
                clean_wire_edges=settings.get("clean_wire_edges", True),
                clean_zero_faces=settings.get("clean_zero_faces", True),
                merge_doubles=settings.get("merge_doubles", True),
                doubles_distance=settings.get("doubles_distance", 0.0001),
                preserve_seams=settings.get("preserve_seams", True)
            )
            report["phase_timings"]["repair"] = time.perf_counter() - t0
            report["logs"].append(f"Repair: {r_rep['elements_removed']}")

        # 4. Internal Walls
        if settings.get("enable_internal_walls", False):
            t0 = time.perf_counter()
            r_iw = execute_remove_internal_walls(target_name)
            report["phase_timings"]["internal_walls"] = time.perf_counter() - t0
            report["logs"].append(f"Internal walls removed: {r_iw.get('faces_removed', 0)}")

        # 5. Dissolve (Coplanar)
        if settings.get("enable_dissolve", False):
            t0 = time.perf_counter()
            r_dis = execute_dissolve(
                target_name,
                dissolve_angle=settings.get("dissolve_angle", 5.0),
                preserve_sharp=settings.get("preserve_sharp", True),
                preserve_seams=settings.get("preserve_seams", True)
            )
            report["phase_timings"]["dissolve"] = time.perf_counter() - t0
            report["logs"].append(f"Dissolved {r_dis['edges_dissolved']} coplanar edges.")

        # 6. Simplification (Decimate)
        if settings.get("enable_simplification", False):
            t0 = time.perf_counter()
            r_simp = execute_simplification(
                target_name,
                mode=settings.get("simplification_mode", "PERCENTAGE"),
                percentage=settings.get("simplification_percentage", 50.0),
                target_triangles=settings.get("simplification_target_triangles", 1000),
                preserve_boundaries=settings.get("preserve_boundaries", True),
                preserve_sharp=settings.get("preserve_sharp", True),
                preserve_seams=settings.get("preserve_seams", True)
            )
            report["phase_timings"]["simplification"] = time.perf_counter() - t0
            report["logs"].append(f"Decimated to {r_simp['triangles_after']} triangles (-{r_simp['reduction_percentage']}%).")

        # 7. Topology (N-Gons & Quads)
        if settings.get("enable_topology", False):
            t0 = time.perf_counter()
            topo_mode = settings.get("topology_mode", "KEEP")
            if topo_mode == "TRIS":
                execute_ngon_cut(target_name)
            elif topo_mode == "QUADS":
                execute_targeted_quadrangulation(target_name)
            report["phase_timings"]["topology"] = time.perf_counter() - t0

        # 8. Normals
        if settings.get("enable_normals", True):
            t0 = time.perf_counter()
            execute_normals(
                target_name,
                recalculate=settings.get("recalculate_normals", True),
                direction=settings.get("recalculate_direction", "OUTSIDE"),
                apply_soft_edge=settings.get("apply_soft_edge", True),
                soft_edge_angle=settings.get("soft_edge_angle", 30.0)
            )
            report["phase_timings"]["normals"] = time.perf_counter() - t0

        # 9. Object Data
        if settings.get("enable_object_data", True):
            t0 = time.perf_counter()
            execute_object_data(target_name)
            report["phase_timings"]["object_data"] = time.perf_counter() - t0

        # Final stats
        stats_after = get_mesh_statistics(target_name)
        report["final_stats"] = stats_after

        tri_before = stats_before.get("triangles", 0)
        tri_after = stats_after.get("triangles", 0)
        if tri_before > 0:
            report["reduction_percentage"] = round(((tri_before - tri_after) / float(tri_before)) * 100.0, 2)

        report["success"] = True
    except Exception as exc:
        report["errors"].append(str(exc))
        # Rollback duplicate
        if create_new and target_name != source_name and cmds.objExists(target_name):
            cmds.delete(target_name)
            cmds.setAttr(f"{source_name}.visibility", True)
        report["success"] = False

    total_time = time.perf_counter() - t0_total
    report["total_duration"] = total_time
    report["phase_timings"]["total"] = total_time

    return report
