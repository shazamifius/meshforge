"""MeshForge - Module de visualisation et cadrage non-destructif (Phase D1).
Gère la sélection et le cadrage (zoom) des anomalies géométriques dans la vue 3D,
ainsi que l'attribution temporaire de couleurs d'inspection sémantiques révocables sans perte de données.
"""

from __future__ import annotations
import bpy
import bmesh
from typing import Dict, Any, List, Optional

# Palette de couleurs sémantiques (RGBA)
CATEGORY_COLORS = {
    'ORANGE': (1.0, 0.5, 0.05, 1.0),   # N-gones
    'BLUE':   (0.15, 0.55, 1.0, 1.0),   # Triangles à examiner
    'RED':    (0.95, 0.15, 0.15, 1.0),  # Dégénérescences & Non-manifold
    'VIOLET': (0.75, 0.25, 0.95, 1.0),  # Éléments isolés / Loose
    'NEUTRAL': (0.6, 0.6, 0.6, 1.0)     # Géométrie saine
}

TEMP_ATTR_NAME = "_MF_Inspection_Temp"


def select_defect(obj: bpy.types.Object, defect: Dict[str, Any]) -> bool:
    """Sélectionne de façon non-destructive les éléments (sommets, arêtes ou faces)
    composant le défaut sélectionné.
    """
    if not obj or obj.type != 'MESH' or not obj.data:
        return False

    mesh = obj.data
    elem_type = defect.get("element_type", "FACE")
    indices = set(defect.get("indices", []))

    prev_mode = obj.mode
    bpy.context.view_layer.objects.active = obj

    if obj.mode == 'EDIT':
        bm = bmesh.from_edit_mesh(mesh)
        # Tout désélectionner
        for v in bm.verts: v.select = False
        for e in bm.edges: e.select = False
        for f in bm.faces: f.select = False

        if elem_type == 'FACE':
            bm.faces.ensure_lookup_table()
            for idx in indices:
                if 0 <= idx < len(bm.faces):
                    bm.faces[idx].select = True
        elif elem_type == 'EDGE':
            bm.edges.ensure_lookup_table()
            for idx in indices:
                if 0 <= idx < len(bm.edges):
                    bm.edges[idx].select = True
        elif elem_type == 'VERT':
            bm.verts.ensure_lookup_table()
            for idx in indices:
                if 0 <= idx < len(bm.verts):
                    bm.verts[idx].select = True

        bmesh.update_edit_mesh(mesh)
    else:
        # En mode Objet
        for v in mesh.vertices: v.select = False
        for e in mesh.edges: e.select = False
        for f in mesh.polygons: f.select = False

        if elem_type == 'FACE':
            for idx in indices:
                if 0 <= idx < len(mesh.polygons):
                    mesh.polygons[idx].select = True
        elif elem_type == 'EDGE':
            for idx in indices:
                if 0 <= idx < len(mesh.edges):
                    mesh.edges[idx].select = True
        elif elem_type == 'VERT':
            for idx in indices:
                if 0 <= idx < len(mesh.vertices):
                    mesh.vertices[idx].select = True

    return True


def zoom_to_defect(defect: Dict[str, Any], context: bpy.types.Context) -> Tuple[bool, str]:
    """Cadre la vue 3D (Frame Selected / Zoom) sur la sélection ou le centre du défaut.
    Gère explicitement le contexte pour éviter toute erreur si aucune fenêtre 3D n'est active.
    """
    center = defect.get("center")
    if not center:
        return False, "Aucune coordonnée de centre disponible pour ce défaut."

    # Recherche d'une zone 3D Viewport dans l'écran actif
    view3d_area = None
    view3d_region = None

    if hasattr(context, "screen") and context.screen:
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                view3d_area = area
                for region in area.regions:
                    if region.type == 'WINDOW':
                        view3d_region = region
                        break
                break

    if not view3d_area or not view3d_region:
        return False, "Aucune vue 3D active trouvée pour effectuer le cadrage visuel (mode arrière-plan ou panneau détaché)."

    # Exécution sécurisée avec temp_override
    try:
        with context.temp_override(area=view3d_area, region=view3d_region):
            if bpy.ops.view3d.view_selected.poll():
                bpy.ops.view3d.view_selected()
                return True, "Cadrage 3D effectué avec succès."
    except Exception as e:
        return False, f"Impossible de cadrer la vue 3D : {e}"

    return True, "Cadrage 3D effectué."


def apply_color_inspection(obj: bpy.types.Object, defects: List[Dict[str, Any]]) -> bool:
    """Attribue temporairement des couleurs d'inspection sémantiques sur un calque dédié.
    Ce calque est strictement temporaire et n'écrase jamais les attributs de couleur existants.
    """
    if not obj or obj.type != 'MESH' or not obj.data:
        return False

    mesh = obj.data
    color_attrs = mesh.color_attributes

    # Récupérer ou créer l'attribut temporaire dédié
    temp_attr = color_attrs.get(TEMP_ATTR_NAME)
    if not temp_attr:
        try:
            temp_attr = color_attrs.new(
                name=TEMP_ATTR_NAME,
                type='FLOAT_COLOR',
                domain='CORNER'
            )
        except Exception:
            return False

    # Couleur neutre de base pour tous les coins de face
    neutral = CATEGORY_COLORS['NEUTRAL']
    for col in temp_attr.data:
        col.color = neutral

    # Colorer les faces concernées selon leur catégorie
    loop_offset = 0
    face_colors = {}
    for d in defects:
        if d.get("element_type") == "FACE":
            color = CATEGORY_COLORS.get(d.get("category", "ORANGE"), neutral)
            for f_idx in d.get("indices", []):
                face_colors[f_idx] = color

    for poly in mesh.polygons:
        col = face_colors.get(poly.index)
        if col:
            for l_idx in poly.loop_indices:
                if l_idx < len(temp_attr.data):
                    temp_attr.data[l_idx].color = col

    # Activer l'attribut temporaire pour le rendu viewport
    color_attrs.active_color = temp_attr
    return True


def clear_inspection_view(obj: bpy.types.Object) -> bool:
    """Supprime l'attribut de couleur temporaire et nettoie la sélection sans altérer le maillage."""
    if not obj or obj.type != 'MESH' or not obj.data:
        return False

    mesh = obj.data

    # Désélectionner
    if obj.mode == 'EDIT':
        bm = bmesh.from_edit_mesh(mesh)
        for v in bm.verts: v.select = False
        for e in bm.edges: e.select = False
        for f in bm.faces: f.select = False
        bmesh.update_edit_mesh(mesh)
    else:
        for v in mesh.vertices: v.select = False
        for e in mesh.edges: e.select = False
        for f in mesh.polygons: f.select = False

    # Supprimer l'attribut temporaire
    temp_attr = mesh.color_attributes.get(TEMP_ATTR_NAME)
    if temp_attr:
        mesh.color_attributes.remove(temp_attr)

    return True
