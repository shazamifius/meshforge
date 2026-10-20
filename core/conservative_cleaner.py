"""MeshForge - Module de nettoyage conservateur et transactionnel (Phase D2.1 & D2.2).
Exécute des opérations ciblées, rigoureusement réversibles et non-destructives
sur les anomalies géométriques élémentaires :
1. Sommets orphelins (Loose Vertices) - Risque Nul
2. Arêtes filaires sans face (Wire Edges) - Risque Faible (règle explicite)
3. Faces dégénérées / d'aire nulle (Zero-Area Faces) - Risque Modéré (préservation des frontières et micro-structures)
4. Fusion des sommets doublons géométriques (Merge Doubles) - Risque Contrôlé (seuil explicite et protection des discontinuités UV)

Garantit un mécanisme transactionnel avec snapshot et rollback automatique en cas de violation d'invariants.
"""

from __future__ import annotations
import bpy
import bmesh
import time
import numpy as np
from typing import Dict, Any, List, Optional, Tuple, Set

from .topology_diagnosis import diagnose_topology


class MeshSnapshot:
    """Instantané complet des données de maillage pour garantie transactionnelle de rollback.
    Capture et restaure fidèlement :
    - Coordonnées des sommets et connectivité arêtes / polygones
    - Multiples couches UV (noms et coordonnées par boucle de face)
    - Matériaux assignés et indices de matériaux par polygone
    - Groupes de sommets et pondérations d'armature (deform vertex groups)
    - Couleurs de sommets et attributs de couleur (color attributes)
    - Propriétés topologiques d'arêtes (seam, sharp, crease) et ombrage (smooth)
    - Attributs génériques du maillage
    """
    def __init__(self, mesh: bpy.types.Mesh):
        self.name = mesh.name
        self.backup_mesh = mesh.copy()
        # Inventaire formel des données capturées pour audit
        self.inventory: Dict[str, Any] = {
            "mesh_name": mesh.name,
            "vertex_count": len(mesh.vertices),
            "edge_count": len(mesh.edges),
            "face_count": len(mesh.polygons),
            "uv_layers": [l.name for l in mesh.uv_layers],
            "color_attributes": [c.name for c in mesh.color_attributes],
            "material_count": len(mesh.materials),
            "has_armature_weights": any(len(v.groups) > 0 for v in mesh.vertices),
            "has_seams": any(e.use_seam for e in mesh.edges),
            "attributes": [a.name for a in mesh.attributes]
        }

    def restore(self, mesh: bpy.types.Mesh) -> bool:
        """Restaure intégralement le maillage dans son état exact pré-opération."""
        if not self.backup_mesh:
            return False
        try:
            bm = bmesh.new()
            bm.from_mesh(self.backup_mesh)
            bm.to_mesh(mesh)
            bm.free()
            mesh.update()
            return True
        except Exception:
            return False

    def free(self):
        """Libère le maillage de secours temporaire en mémoire Blender."""
        if self.backup_mesh and self.backup_mesh.name in bpy.data.meshes:
            try:
                bpy.data.meshes.remove(self.backup_mesh)
            except Exception:
                pass
            self.backup_mesh = None

    def __del__(self):
        self.free()


def find_uv_discontinuity_vertices(bm: bmesh.types.BMesh) -> Set[bmesh.types.BMVert]:
    """Identifie tous les sommets participant à une frontière ou discontinuité UV :
    1. Arêtes avec coutures UV explicites (e.seam == True).
    2. Sommets coïncidents dans l'espace 3D ayant des coordonnées UV distinctes
       sur leurs boucles de faces (îlots UV séparés sans marquage seam préalable).
    3. Arêtes partagées dont les faces adjacentes ont des coordonnées UV différentes.
    """
    discontinuity_verts: Set[bmesh.types.BMVert] = set()

    # 1. Arêtes marquées explicitement seam
    for e in bm.edges:
        if getattr(e, "seam", False):
            discontinuity_verts.add(e.verts[0])
            discontinuity_verts.add(e.verts[1])

    uv_layers = list(bm.loops.layers.uv.values())
    if not uv_layers:
        return discontinuity_verts

    # 2. Arêtes partagées avec UV discontinus entre faces adjacentes
    for e in bm.edges:
        if len(e.link_faces) >= 2:
            for uv_lay in uv_layers:
                uv_map: Dict[bmesh.types.BMVert, Tuple[float, float]] = {}
                is_edge_seam = False
                for loop in e.link_loops:
                    v = loop.vert
                    uv_pt = (round(loop[uv_lay].uv.x, 5), round(loop[uv_lay].uv.y, 5))
                    if v not in uv_map:
                        uv_map[v] = uv_pt
                    elif uv_map[v] != uv_pt:
                        is_edge_seam = True
                        break
                if is_edge_seam:
                    discontinuity_verts.add(e.verts[0])
                    discontinuity_verts.add(e.verts[1])
                    break

    # 3. Sommets géométriquement coïncidents (doublons 3D) avec coordonnées UV distinctes
    grid: Dict[Tuple[float, float, float], List[bmesh.types.BMVert]] = {}
    for v in bm.verts:
        key = (round(v.co.x, 4), round(v.co.y, 4), round(v.co.z, 4))
        grid.setdefault(key, []).append(v)

    for vlist in grid.values():
        if len(vlist) > 1:
            for uv_lay in uv_layers:
                uv_sets = []
                for v in vlist:
                    s = {(round(l[uv_lay].uv.x, 5), round(l[uv_lay].uv.y, 5)) for l in v.link_loops}
                    uv_sets.append(s)
                # Si des sommets coïncidents ont des coordonnées UV non vides différentes
                has_diff = any(s1 and s2 and s1 != s2 for i, s1 in enumerate(uv_sets) for s2 in uv_sets[i + 1:])
                if has_diff:
                    discontinuity_verts.update(vlist)
                    break

    return discontinuity_verts


def clean_loose_vertices(bm: bmesh.types.BMesh) -> int:
    """Supprime les sommets strictement orphelins (aucune arête connectée).
    Opération sûre à risque nul. Retourne le nombre de sommets supprimés.
    """
    bm.verts.ensure_lookup_table()
    loose_verts = [v for v in bm.verts if not v.link_edges]
    count = len(loose_verts)
    if count > 0:
        bmesh.ops.delete(bm, geom=loose_verts, context='VERTS')
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()
    return count


def clean_wire_edges(bm: bmesh.types.BMesh) -> int:
    """Supprime les arêtes filaires ne délimitant aucune face (e.link_faces == 0).
    Règle explicite : nettoie les segments résiduels sans toucher aux sommets utiles.
    Retourne le nombre d'arêtes supprimées.
    """
    bm.edges.ensure_lookup_table()
    wire_edges = [e for e in bm.edges if not e.link_faces]
    count = len(wire_edges)
    if count > 0:
        bmesh.ops.delete(bm, geom=wire_edges, context='EDGES')
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()
    return count


def clean_zero_area_faces(
    bm: bmesh.types.BMesh,
    area_threshold: float = 1e-7,
    protect_boundaries: bool = True
) -> int:
    """Supprime les faces dégénérées d'aire nulle ou quasi-nulle.
    Garantie : ne détruit jamais silencieusement une frontière utile ou une micro-structure saine.
    - Supprime systématiquement les faces d'aire strictement nulle (<= 1e-9).
    - Pour les faces entre 1e-9 et area_threshold : supprime uniquement si le ratio
      isopérimétrique (p²/aire) révèle une aiguille écrasée (> 1000). Les micro-polygones
      bien proportionnés sur des frontières ouvertes sont rigoureusement préservés.
    Retourne le nombre de faces éliminées.
    """
    bm.faces.ensure_lookup_table()
    zero_faces = []

    for f in bm.faces:
        area = f.calc_area()
        if area <= 1e-9:
            # Dégénérescence absolue (sommets colinéaires ou superposés)
            zero_faces.append(f)
        elif area <= area_threshold:
            # Face de faible aire : tester si c'est une aiguille écrasée
            perim = sum(e.calc_length() for e in f.edges)
            isoperimetric_ratio = (perim * perim) / max(1e-12, area)
            is_boundary = any(e.is_boundary for e in f.edges)

            if is_boundary and protect_boundaries and isoperimetric_ratio < 1000.0:
                # Structure ou biseau valide sur frontière ouverte : préserver
                continue
            elif isoperimetric_ratio >= 1000.0:
                # Véritable aiguille aplatie dégénérée
                zero_faces.append(f)

    count = len(zero_faces)
    if count > 0:
        bmesh.ops.delete(bm, geom=zero_faces, context='FACES')
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()
    return count


def merge_duplicate_vertices(
    bm: bmesh.types.BMesh,
    distance: float = 1e-5,
    preserve_seams: bool = True
) -> int:
    """Fusionne les sommets géométriquement doublons (distance <= seuil explicite).
    Garanties :
    - Exige un seuil explicite passé en paramètre.
    - Si preserve_seams est activé, protège formellement les sommets délimitant
      des coutures UV explicites (seam) ET les sommets coïncidents possédant des coordonnées
      UV distinctes (îlots UV séparés sans marquage seam).
    - Préserve intégralement les discontinuités UV par boucle de face.
    Retourne le nombre de sommets fusionnés.
    """
    bm.verts.ensure_lookup_table()
    initial_verts = len(bm.verts)

    candidate_verts = list(bm.verts)
    if preserve_seams:
        discont_verts = find_uv_discontinuity_vertices(bm)
        candidate_verts = [v for v in candidate_verts if v not in discont_verts]

    if not candidate_verts:
        return 0

    try:
        doubles = bmesh.ops.find_doubles(
            bm,
            verts=candidate_verts,
            dist=distance
        )
        targetmap = doubles.get("targetmap", {})
        if targetmap:
            bmesh.ops.weld_verts(bm, targetmap=targetmap)
            bm.verts.ensure_lookup_table()
            bm.edges.ensure_lookup_table()
            bm.faces.ensure_lookup_table()
    except Exception:
        bmesh.ops.remove_doubles(
            bm,
            verts=candidate_verts,
            dist=distance
        )
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()

    merged_count = initial_verts - len(bm.verts)
    return max(0, merged_count)


def execute_conservative_cleanup(
    obj: bpy.types.Object,
    clean_loose_v: bool = True,
    clean_wire_e: bool = True,
    clean_zero_f: bool = True,
    merge_doubles: bool = True,
    doubles_distance: float = 1e-5,
    preserve_seams: bool = True,
    target_mode: str = 'HYBRID_CLEANUP'
) -> Dict[str, Any]:
    """Exécute la transaction de nettoyage conservateur avec garantie formelle de rollback.
    Contrôle les données sensibles, valide les invariants et relance le diagnostic topologique.
    """
    t0 = time.perf_counter()

    result: Dict[str, Any] = {
        "success": False,
        "rolled_back": False,
        "object_name": obj.name if obj else "Inconnu",
        "counts_before": {},
        "counts_after": {},
        "elements_removed": {
            "loose_verts": 0,
            "wire_edges": 0,
            "zero_faces": 0,
            "doubles_merged": 0
        },
        "post_diagnosis": {},
        "execution_time_ms": 0.0,
        "logs": [],
        "warnings": [],
        "error": None
    }

    if not obj or obj.type != 'MESH' or not obj.data:
        result["error"] = "Objet sélectionné invalide ou sans maillage."
        return result

    mesh = obj.data

    # 1. Prise d'instantané (Snapshot de sécurité)
    snapshot = MeshSnapshot(mesh)

    counts_before = {
        "vertices": len(mesh.vertices),
        "edges": len(mesh.edges),
        "faces": len(mesh.polygons),
        "materials": len(mesh.materials),
        "has_uv": len(mesh.uv_layers) > 0
    }
    result["counts_before"] = counts_before

    # 2. Exécution transactionnelle sur BMesh
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    try:
        # A. Sommets orphelins
        if clean_loose_v:
            lv_removed = clean_loose_vertices(bm)
            result["elements_removed"]["loose_verts"] = lv_removed
            if lv_removed > 0:
                result["logs"].append(f"{lv_removed} sommet(s) orphelin(s) supprimé(s).")

        # B. Arêtes filaires sans face
        if clean_wire_e:
            we_removed = clean_wire_edges(bm)
            result["elements_removed"]["wire_edges"] = we_removed
            if we_removed > 0:
                result["logs"].append(f"{we_removed} arête(s) filaire(s) supprimée(s).")

        # C. Faces d'aire nulle
        if clean_zero_f:
            zf_removed = clean_zero_area_faces(bm, area_threshold=1e-7, protect_boundaries=True)
            result["elements_removed"]["zero_faces"] = zf_removed
            if zf_removed > 0:
                result["logs"].append(f"{zf_removed} face(s) dégénérée(s) dissoute(s).")

        # D. Fusion des sommets doublons
        if merge_doubles:
            dm_count = merge_duplicate_vertices(
                bm,
                distance=doubles_distance,
                preserve_seams=preserve_seams
            )
            result["elements_removed"]["doubles_merged"] = dm_count
            if dm_count > 0:
                result["logs"].append(f"{dm_count} sommet(s) doublon(s) fusionné(s) (seuil {doubles_distance*1000:.3f} mm).")

        # 3. Contrôle des invariants de sécurité géométrique
        if counts_before["faces"] > 0 and len(bm.faces) == 0:
            raise ValueError("Invariant critique violé : toutes les faces ont été détruites par l'opération.")

        for v in bm.verts:
            if not np.all(np.isfinite(v.co)):
                raise ValueError("Invariant critique violé : coordonnées de sommet corrompues (NaN ou infinies).")

        expected_min_faces = max(0, counts_before["faces"] - result["elements_removed"]["zero_faces"])
        if len(bm.faces) < expected_min_faces:
            raise ValueError(
                f"Invariant critique violé : perte inattendue de faces valides "
                f"({counts_before['faces']} -> {len(bm.faces)}, attendu au moins {expected_min_faces})."
            )

        # Appliquer les modifications au maillage Blender
        bm.to_mesh(mesh)
        bm.free()
        mesh.update()
        snapshot.free()

        counts_after = {
            "vertices": len(mesh.vertices),
            "edges": len(mesh.edges),
            "faces": len(mesh.polygons),
            "materials": len(mesh.materials),
            "has_uv": len(mesh.uv_layers) > 0
        }
        result["counts_after"] = counts_after

        # 4. Relancer le diagnostic topologique complet post-traitement
        post_diag = diagnose_topology(obj, mode=target_mode)
        result["post_diagnosis"] = post_diag
        result["success"] = True
        result["execution_time_ms"] = (time.perf_counter() - t0) * 1000.0

    except Exception as e:
        # 5. Déclenchement du Rollback automatique en cas d'erreur ou d'invariant violé
        bm.free()
        ok_rollback = snapshot.restore(mesh)
        snapshot.free()
        result["success"] = False
        result["rolled_back"] = ok_rollback
        result["error"] = str(e)
        result["logs"].append(f"ÉCHEC ET ROLLBACK DÉCLENCHÉ : {e}. Le maillage a été restauré dans son état initial.")
        result["execution_time_ms"] = (time.perf_counter() - t0) * 1000.0

    return result
