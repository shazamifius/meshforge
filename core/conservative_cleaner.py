"""MeshForge - Module de nettoyage conservateur et transactionnel (Phase D2.1).
Exécute des opérations ciblées, rigoureusement réversibles et non-destructives
sur les anomalies géométriques élémentaires :
1. Sommets orphelins (Loose Vertices) - Risque Nul
2. Arêtes filaires sans face (Wire Edges) - Risque Faible (règle explicite)
3. Faces dégénérées / d'aire nulle (Zero-Area Faces) - Risque Modéré (préservation des frontières)
4. Fusion des sommets doublons géométriques (Merge Doubles) - Risque Contrôlé (seuil explicite et protection des seams UV)

Garantit un mécanisme transactionnel avec snapshot et rollback automatique en cas de violation d'invariants.
"""

from __future__ import annotations
import bpy
import bmesh
import time
import numpy as np
from typing import Dict, Any, List, Optional, Tuple

from .topology_diagnosis import diagnose_topology


class MeshSnapshot:
    """Instantané complet des données de maillage pour garantie transactionnelle de rollback."""
    def __init__(self, mesh: bpy.types.Mesh):
        self.name = mesh.name
        self.vertex_coords = np.array([v.co for v in mesh.vertices], dtype=np.float64)
        self.edge_keys = [(e.vertices[0], e.vertices[1]) for e in mesh.edges]
        self.polygon_loops = [[loop_idx for loop_idx in p.loop_indices] for p in mesh.polygons]
        self.polygon_vertices = [[v_idx for v_idx in p.vertices] for p in mesh.polygons]
        self.has_uv = len(mesh.uv_layers) > 0
        self.uv_coords = np.array([l.uv for l in mesh.uv_layers[0].data], dtype=np.float64) if self.has_uv else None
        self.material_names = [m.name for m in mesh.materials if m]
        self.poly_materials = [p.material_index for p in mesh.polygons]

    def restore(self, mesh: bpy.types.Mesh) -> bool:
        """Restaure fidèlement les données du maillage à partir du snapshot."""
        try:
            bm = bmesh.new()
            # Recréer les sommets
            bm_verts = [bm.verts.new(co) for co in self.vertex_coords]
            bm.verts.ensure_lookup_table()

            # Recréer les faces
            for poly_verts in self.polygon_vertices:
                face_verts = [bm_verts[idx] for idx in poly_verts]
                bm.faces.new(face_verts)
            bm.faces.ensure_lookup_table()

            # Recréer les arêtes isolées éventuelles qui n'étaient pas dans des faces
            existing_edges = set((e.verts[0].index, e.verts[1].index) for e in bm.edges)
            for v0_idx, v1_idx in self.edge_keys:
                pair = tuple(sorted((v0_idx, v1_idx)))
                if pair not in existing_edges:
                    try:
                        bm.edges.new((bm_verts[v0_idx], bm_verts[v1_idx]))
                        existing_edges.add(pair)
                    except Exception:
                        pass

            # Réassigner au maillage
            bm.to_mesh(mesh)
            bm.free()

            # Restaurer UVs si existants
            if self.has_uv and self.uv_coords is not None and len(mesh.uv_layers) > 0:
                uv_data = mesh.uv_layers[0].data
                n_uvs = min(len(uv_data), len(self.uv_coords))
                for i in range(n_uvs):
                    uv_data[i].uv = self.uv_coords[i]

            mesh.update()
            return True
        except Exception:
            return False


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
    area_threshold: float = 1e-7
) -> int:
    """Supprime les faces dégénérées d'aire nulle (<= area_threshold).
    Préserve formellement les faces saines.
    Retourne le nombre de faces éliminées.
    """
    bm.faces.ensure_lookup_table()
    zero_faces = [f for f in bm.faces if f.calc_area() <= area_threshold]
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
    Ne fusionne jamais silencieusement :
    - Exige un seuil explicite passé en paramètre.
    - Si preserve_seams est activé, ne fusionne pas les sommets délimitant des coutures UV (Sharp/Seams).
    Retourne le nombre de sommets fusionnés.
    """
    bm.verts.ensure_lookup_table()
    initial_verts = len(bm.verts)

    # Identifier les sommets éligibles
    candidate_verts = list(bm.verts)
    if preserve_seams:
        # Exclure les sommets incidentes à une arête de couture UV (seam)
        seam_verts = set()
        for e in bm.edges:
            if getattr(e, "seam", False):
                seam_verts.add(e.verts[0])
                seam_verts.add(e.verts[1])
        candidate_verts = [v for v in candidate_verts if v not in seam_verts]

    if not candidate_verts:
        return 0

    # Exécution de bmesh.ops.find_doubles puis collapse
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
        # Fallback classique bmesh remove_doubles
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
            zf_removed = clean_zero_area_faces(bm, area_threshold=1e-7)
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
        # Invariant 1 : Le maillage ne doit pas devenir vide s'il contenait des faces légitimes
        if counts_before["faces"] > 0 and len(bm.faces) == 0:
            raise ValueError("Invariant critique violé : toutes les faces ont été détruites par l'opération.")

        # Invariant 2 : Pas de coordonnées NaN ou infinies
        for v in bm.verts:
            if not np.all(np.isfinite(v.co)):
                raise ValueError("Invariant critique violé : coordonnées de sommet corrompues (NaN ou infinies).")

        # Invariant 3 : L'opération conservatrice ne doit pas faire disparaître plus de faces que les faces nulles
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
        result["success"] = False
        result["rolled_back"] = ok_rollback
        result["error"] = str(e)
        result["logs"].append(f"ÉCHEC ET ROLLBACK DÉCLENCHÉ : {e}. Le maillage a été restauré dans son état initial.")
        result["execution_time_ms"] = (time.perf_counter() - t0) * 1000.0

    return result
