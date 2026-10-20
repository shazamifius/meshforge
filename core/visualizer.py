"""MeshForge - Module de visualisation et cadrage non-destructif (Phase D1).
Gère la sélection et le cadrage (zoom) des anomalies géométriques dans la vue 3D,
ainsi que l'attribution temporaire de couleurs d'inspection sémantiques révocables sans perte de données.
Garantit formellement la préservation et la restauration des attributs utilisateur et du mode d'affichage viewport.
"""

from __future__ import annotations
import bpy
import bmesh
from mathutils import Vector
from typing import Dict, Any, List, Optional, Tuple

# Palette de couleurs sémantiques (RGBA)
CATEGORY_COLORS = {
    'ORANGE': (1.0, 0.5, 0.05, 1.0),   # N-gones (> 4 côtés)
    'BLUE':   (0.15, 0.55, 1.0, 1.0),   # Triangles à examiner (aiguilles ou bloquant des quads)
    'RED':    (0.95, 0.15, 0.15, 1.0),  # Dégénérescences (faces nulles, micro-arêtes) & Non-manifold
    'VIOLET': (0.75, 0.25, 0.95, 1.0),  # Éléments isolés (orphelins, arêtes filaires, îlots disjoints)
    'YELLOW': (0.95, 0.85, 0.1, 1.0),   # Risques d'animation / Pôles complexes (valence >= 6)
    'NEUTRAL': (0.65, 0.65, 0.65, 1.0)  # Géométrie saine de référence
}

TEMP_ATTR_NAME = "_MF_Inspection_Temp"

# Mémorisation d'état pour restauration non-destructive
_PRIOR_ACTIVE_COLOR_ATTRS: Dict[str, Optional[str]] = {}
_PRIOR_SHADING_COLOR_TYPE: Dict[int, str] = {}


def _find_active_3d_spaces(context: Optional[bpy.types.Context] = None) -> List[Any]:
    """Retourne la liste des espaces 3D (View3D) actifs dans la fenêtre Blender."""
    spaces = []
    ctx = context or bpy.context
    if hasattr(ctx, "screen") and ctx.screen:
        for area in ctx.screen.areas:
            if area.type == 'VIEW_3D':
                for space in area.spaces:
                    if space.type == 'VIEW_3D':
                        spaces.append(space)
    return spaces


def _ensure_viewport_shading_for_colors(context: Optional[bpy.types.Context] = None) -> None:
    """Bascule le shading du viewport en mode affichage de couleurs d'attributs (VERTEX)
    en mode Solide, afin que l'utilisateur voie immédiatement les couleurs sémantiques.
    Mémorise le mode de couleur précédent pour restauration à la fermeture.
    """
    for space in _find_active_3d_spaces(context):
        shading = getattr(space, "shading", None)
        if shading and shading.type == 'SOLID':
            if shading.color_type != 'VERTEX':
                _PRIOR_SHADING_COLOR_TYPE[id(space)] = shading.color_type
                shading.color_type = 'VERTEX'


def _restore_viewport_shading(context: Optional[bpy.types.Context] = None) -> None:
    """Restaure le type de couleur de shading viewport initial."""
    for space in _find_active_3d_spaces(context):
        space_id = id(space)
        if space_id in _PRIOR_SHADING_COLOR_TYPE:
            prior_type = _PRIOR_SHADING_COLOR_TYPE.pop(space_id)
            shading = getattr(space, "shading", None)
            if shading and shading.type == 'SOLID':
                shading.color_type = prior_type


def select_defect(obj: bpy.types.Object, defect: Dict[str, Any]) -> bool:
    """Sélectionne de façon strictement non-destructive les éléments (sommets, arêtes ou faces)
    composant le défaut sélectionné. Ne modifie aucune coordonnée ni topologie.
    """
    if not obj or obj.type != 'MESH' or not obj.data:
        return False

    mesh = obj.data
    elem_type = defect.get("element_type", "FACE")
    indices = set(defect.get("indices", []))

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


def zoom_to_defect(
    defect: Dict[str, Any],
    context: bpy.types.Context,
    obj: Optional[bpy.types.Object] = None
) -> Tuple[bool, str]:
    """Cadre la vue 3D avec précision millimétrique directement sur l'anomalie géométrique.
    Prend en compte la transformation monde de l'objet (position, rotation, échelle),
    le rayon englobant du défaut, et ajuste le point focal (view_location) et la distance
    de caméra (view_distance) dans les viewports 3D actifs. Place également le curseur 3D
    sur le centre précis du défaut comme repère visuel immédiat.
    """
    if obj is None:
        obj = context.active_object

    if not obj or obj.type != 'MESH' or not obj.data:
        return False, "Aucun maillage actif valide pour effectuer le cadrage visuel."

    mesh = obj.data
    matrix_world = obj.matrix_world
    elem_type = defect.get("element_type", "FACE")
    indices = defect.get("indices", [])

    world_coords: List[Vector] = []

    # 1. Extraction des coordonnées monde des sommets composants le défaut
    if elem_type == "FACE":
        num_faces = len(mesh.polygons)
        num_verts = len(mesh.vertices)
        for idx in indices:
            if 0 <= idx < num_faces:
                poly = mesh.polygons[idx]
                for v_idx in poly.vertices:
                    if 0 <= v_idx < num_verts:
                        world_coords.append(matrix_world @ mesh.vertices[v_idx].co)
    elif elem_type == "EDGE":
        num_edges = len(mesh.edges)
        num_verts = len(mesh.vertices)
        for idx in indices:
            if 0 <= idx < num_edges:
                edge = mesh.edges[idx]
                for v_idx in edge.vertices:
                    if 0 <= v_idx < num_verts:
                        world_coords.append(matrix_world @ mesh.vertices[v_idx].co)
    elif elem_type == "VERT":
        num_verts = len(mesh.vertices)
        for idx in indices:
            if 0 <= idx < num_verts:
                world_coords.append(matrix_world @ mesh.vertices[idx].co)

    # Repli si aucun sommet n'a pu être extrait des indices (ex: maillage modifié depuis le diagnostic)
    center_local = defect.get("center")
    if not world_coords:
        if center_local:
            world_coords.append(matrix_world @ Vector(center_local))
        else:
            return False, "Coordonnées de l'anomalie introuvables ou géométrie modifiée."

    # 2. Calcul du centre monde et du rayon englobant de l'anomalie
    world_center = sum(world_coords, Vector((0.0, 0.0, 0.0))) / len(world_coords)

    if len(world_coords) > 1:
        radius = max((co - world_center).length for co in world_coords)
    else:
        obj_diag = max(obj.dimensions) if hasattr(obj, "dimensions") and any(obj.dimensions) else 1.0
        radius = max(0.02, obj_diag * 0.03)

    # 3. Positionnement du curseur 3D sur le centre du défaut (repère visuel immédiat)
    try:
        if hasattr(context, "scene") and context.scene:
            context.scene.cursor.location = world_center
    except Exception:
        pass

    # 4. Recherche des espaces 3D (View3D)
    spaces_3d = _find_active_3d_spaces(context)
    if not spaces_3d:
        return False, "Aucune vue 3D active trouvée pour effectuer le cadrage visuel (mode arrière-plan ou panneau détaché)."

    # 5. Ajustement précis de la caméra viewport (view_location et view_distance)
    framed = False
    for space in spaces_3d:
        r3d = getattr(space, "region_3d", None)
        if not r3d:
            continue

        clip_start = getattr(space, "clip_start", 0.01)
        min_dist = max(0.15, clip_start * 3.0)
        target_dist = max(min_dist, radius * 3.5)

        r3d.view_location = world_center
        r3d.view_distance = target_dist
        framed = True

    # Déclencher le redessin des zones 3D
    if hasattr(context, "screen") and context.screen:
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()

    if framed:
        return True, "Cadrage 3D précis effectué sur l'anomalie."
    return False, "Impossible d'accéder au contrôleur 3D de la vue."


def apply_color_inspection(
    obj: bpy.types.Object,
    defects: List[Dict[str, Any]],
    context: Optional[bpy.types.Context] = None
) -> bool:
    """Attribue temporairement des couleurs d'inspection sémantiques sur un calque dédié.
    Ce calque est strictement temporaire et n'écrase jamais les attributs de couleur existants.
    Mémorise l'attribut actif d'origine pour le restaurer lors de la fermeture.
    Active également le mode d'affichage couleur dans la vue 3D.
    """
    if not obj or obj.type != 'MESH' or not obj.data:
        return False

    mesh = obj.data
    color_attrs = mesh.color_attributes

    # Mémoriser l'attribut de couleur utilisateur actif avant d'activer l'attribut temporaire
    prior_attr = color_attrs.active_color
    if prior_attr and prior_attr.name != TEMP_ATTR_NAME:
        _PRIOR_ACTIVE_COLOR_ATTRS[obj.name] = prior_attr.name
    elif obj.name not in _PRIOR_ACTIVE_COLOR_ATTRS:
        # Trouver un éventuel premier attribut préexistant non temporaire
        user_attrs = [a.name for a in color_attrs if a.name != TEMP_ATTR_NAME]
        _PRIOR_ACTIVE_COLOR_ATTRS[obj.name] = user_attrs[0] if user_attrs else None

    # Récupérer ou créer l'attribut temporaire dédié
    temp_attr = color_attrs.get(TEMP_ATTR_NAME)
    if temp_attr:
        # Vérifier que le format est compatible
        if getattr(temp_attr, "data_type", None) != 'FLOAT_COLOR' or getattr(temp_attr, "domain", None) != 'CORNER':
            color_attrs.remove(temp_attr)
            temp_attr = None

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

    # Priorité sémantique pour la coloration des faces :
    # RED (Erreur critique) > ORANGE (N-gone) > YELLOW (Risque déformation) > BLUE (Triangle) > VIOLET (Îlot isolé)
    category_priority = {
        'RED': 5,
        'ORANGE': 4,
        'YELLOW': 3,
        'BLUE': 2,
        'VIOLET': 1,
        'NEUTRAL': 0
    }

    # Déterminer la catégorie prioritaire pour chaque face
    face_category: Dict[int, str] = {}
    for d in defects:
        cat = d.get("category", "NEUTRAL")
        prio = category_priority.get(cat, 0)
        # Prendre les indices de faces directes ou incidentes (pour arêtes et sommets)
        f_list = d.get("face_indices") if d.get("face_indices") else d.get("indices", [])
        if d.get("element_type") == "FACE" or d.get("face_indices"):
            for f_idx in f_list:
                curr_cat = face_category.get(f_idx)
                if not curr_cat or prio > category_priority.get(curr_cat, 0):
                    face_category[f_idx] = cat

    for poly in mesh.polygons:
        cat = face_category.get(poly.index)
        if cat:
            col = CATEGORY_COLORS.get(cat, neutral)
            for l_idx in poly.loop_indices:
                if l_idx < len(temp_attr.data):
                    temp_attr.data[l_idx].color = col

    # Activer l'attribut temporaire pour le viewport
    color_attrs.active_color = temp_attr

    # Activer l'affichage des couleurs d'attributs dans le viewport 3D
    _ensure_viewport_shading_for_colors(context)
    return True


def clear_inspection_view(
    obj: bpy.types.Object,
    context: Optional[bpy.types.Context] = None
) -> bool:
    """Supprime l'attribut de couleur temporaire et nettoie la sélection sans altérer le maillage.
    Garantit formellement qu'aucun attribut utilisateur n'est supprimé, et restaure
    l'attribut de couleur actif d'origine ainsi que le shading viewport.
    """
    if not obj or obj.type != 'MESH' or not obj.data:
        return False

    mesh = obj.data

    # 1. Désélectionner
    if obj.mode == 'EDIT':
        bm = bmesh.from_edit_mesh(mesh)
        for v in bm.verts: v.select = False
        for e in bm.edges: e.select = False
        for f in bm.faces: f.select = False
        bmesh.update_edit_mesh(mesh)
    else:
        # Optimisation vectorielle C-API pour les gros maillages
        n_v = len(mesh.vertices)
        n_e = len(mesh.edges)
        n_f = len(mesh.polygons)
        if n_v > 0:
            mesh.vertices.foreach_set("select", [False] * n_v)
        if n_e > 0:
            mesh.edges.foreach_set("select", [False] * n_e)
        if n_f > 0:
            mesh.polygons.foreach_set("select", [False] * n_f)

    # 2. Restaurer l'attribut actif utilisateur d'origine
    prior_name = _PRIOR_ACTIVE_COLOR_ATTRS.pop(obj.name, None)
    if prior_name and prior_name in mesh.color_attributes and prior_name != TEMP_ATTR_NAME:
        mesh.color_attributes.active_color = mesh.color_attributes[prior_name]
    elif len(mesh.color_attributes) > 0:
        remaining_user_attrs = [a for a in mesh.color_attributes if a.name != TEMP_ATTR_NAME]
        if remaining_user_attrs:
            mesh.color_attributes.active_color = remaining_user_attrs[0]

    # 3. Supprimer UNIQUEMENT l'attribut temporaire
    temp_attr = mesh.color_attributes.get(TEMP_ATTR_NAME)
    if temp_attr:
        mesh.color_attributes.remove(temp_attr)

    # 4. Restaurer le mode de shading viewport
    _restore_viewport_shading(context)

    # 5. Restaurer le mode filaire s'il avait été activé par MeshForge
    try:
        from ..operators.restore import restore_wireframe_if_meshforge_enabled
        restore_wireframe_if_meshforge_enabled(obj)
    except Exception:
        pass

    return True
