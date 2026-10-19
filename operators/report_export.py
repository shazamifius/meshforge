"""MeshForge - Opérateur d'exportation de rapport (JSON ou Texte)."""

from __future__ import annotations
import bpy
from bpy_extras.io_utils import ExportHelper
from ..core.report import export_report_to_file
from ..core.mesh_stats import get_mesh_statistics

# Cache global de session pour le dernier rapport d'exécution
LAST_PIPELINE_REPORT = {}


class MESHFORGE_OT_export_report(bpy.types.Operator, ExportHelper):
    """Exporte le rapport d'analyse ou d'optimisation sur le disque"""
    bl_idname = "meshforge.export_report"
    bl_label = "Exporter le rapport"

    filename_ext: bpy.props.StringProperty(default=".json")
    filter_glob: bpy.props.StringProperty(
        default="*.json;*.txt",
        options={'HIDDEN'}
    )

    format_type: bpy.props.EnumProperty(
        name="Format d'export",
        items=[
            ('JSON', "JSON", "Format de données structuré JSON"),
            ('TXT', "Texte", "Rapport textuel lisible")
        ],
        default='JSON'
    )

    def execute(self, context):
        global LAST_PIPELINE_REPORT
        report = LAST_PIPELINE_REPORT

        # Si aucun rapport de pipeline n'a encore été généré, générer un rapport de diagnostic à la volée
        if not report:
            obj = context.active_object
            if obj and obj.type == 'MESH':
                stats = get_mesh_statistics(obj)
                report = {
                    "original_name": obj.name,
                    "result_name": obj.name,
                    "success": True,
                    "total_duration": 0.0,
                    "reduction_percentage": 0.0,
                    "initial_stats": stats,
                    "final_stats": stats,
                    "issues_detected": {
                        "loose_verts": stats.get("loose_verts", 0),
                        "loose_edges": stats.get("loose_edges", 0),
                        "potential_duplicates": stats.get("potential_duplicate_verts", 0),
                        "zero_area_faces": stats.get("zero_area_faces", 0),
                        "non_manifold_edges": stats.get("non_manifold_edges", 0),
                        "non_manifold_verts": stats.get("non_manifold_verts", 0),
                        "boundary_loops_count": stats.get("boundary_loops_count", 0),
                        "is_open_surface": stats.get("is_open_surface", False),
                    },
                    "issues_resolved": {},
                    "phase_timings": {},
                    "warnings": stats.get("risk_assessment", []),
                    "errors": [],
                    "logs": ["Rapport généré depuis le diagnostic en lecture seule."]
                }
            else:
                self.report({'ERROR'}, "Aucun rapport disponible et aucun maillage sélectionné.")
                return {'CANCELLED'}

        # Adapter l'extension du fichier selon le format
        filepath = self.filepath
        if self.format_type == 'JSON' and not filepath.lower().endswith(".json"):
            filepath += ".json"
        elif self.format_type == 'TXT' and not filepath.lower().endswith(".txt"):
            filepath += ".txt"

        try:
            saved_path = export_report_to_file(report, filepath, self.format_type)
            self.report({'INFO'}, f"Rapport exporté avec succès : {saved_path}")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Erreur lors de l'export du rapport : {e}")
            return {'CANCELLED'}
