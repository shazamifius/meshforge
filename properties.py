"""MeshForge - Définition des propriétés Blender (PropertyGroup).
Contient tous les paramètres des sections Repair, Manifold, Dissolve,
Topology, Normals, Object Data et du système de rapport.
"""

from __future__ import annotations
import bpy
from bpy.props import (
    BoolProperty,
    FloatProperty,
    IntProperty,
    EnumProperty,
    StringProperty,
    PointerProperty
)


class MeshForgeSettings(bpy.types.PropertyGroup):
    # --- Assistant intelligent de préparation d'assets (Phase D) ---
    asset_target_mode: EnumProperty(
        name="Objectif de l'Asset",
        description="Définit l'objectif prioritaire de l'asset pour guider l'analyse et les corrections",
        items=[
            ('GAME_TRIANGLES', "Asset de jeu — Triangles", "Pour les décors, rochers et objets statiques : réduction de triangles, préservation de silhouette et d'UV"),
            ('DEFORMABLE_QUADS', "Asset déformable — Quads", "Pour les personnages, vêtements et objets articulés : flux de boucles régulier et déformation optimale"),
            ('HYBRID_CLEANUP', "Asset hybride — Diagnostic", "Pour les objets mécaniques et mixtes : diagnostic complet et nettoyage conservateur sans conversion forcée")
        ],
        default='HYBRID_CLEANUP'
    )
    validation_depth: EnumProperty(
        name="Niveau de validation",
        description="Choisit la profondeur d'analyse pour équilibrer vitesse et précision métrologique",
        items=[
            ('QUICK', "Rapide", "Vérifications immédiates peu coûteuses (invariants géométriques)"),
            ('THOROUGH', "Approfondi", "Mesures géométriques complètes, silhouette 2D IoU et quantiles d'écart"),
            ('PRE_EXPORT', "Avant export", "Validation stricte de conformité avant envoi vers le moteur cible")
        ],
        default='QUICK'
    )
    active_defect_filter: EnumProperty(
        name="Filtrer les anomalies",
        description="Filtre la liste interactive des défauts par catégorie sémantique",
        items=[
            ('ALL', "Toutes les anomalies", "Afficher tous les défauts détectés"),
            ('ORANGE', "N-gones (Orange)", "Faces à plus de 4 côtés"),
            ('BLUE', "Triangles suspects (Bleu)", "Triangles en zone déformable"),
            ('RED', "Dégénérescences (Rouge)", "Faces nulles, arêtes minuscules, non-manifold"),
            ('VIOLET', "Éléments isolés (Violet)", "Composantes disjointes et géométrie flottante")
        ],
        default='ALL'
    )
    active_defect_index: IntProperty(
        name="Anomalie sélectionnée",
        description="Index de l'anomalie active à examiner dans la liste",
        default=0,
        min=0
    )
    show_expert_mode: BoolProperty(
        name="Mode Expert / Réglages techniques",
        description="Déploie les panneaux de contrôle techniques avancés",
        default=False
    )

    # --- Workflow et sécurité non-destructive (Section 1 & 2) ---
    create_new_object: BoolProperty(
        name="Créer un nouvel objet",
        description="Conserve le maillage source intact et produit une copie optimisée",
        default=True
    )
    hide_original: BoolProperty(
        name="Masquer l'original",
        description="Masque le maillage original dans la vue 3D après optimisation",
        default=True
    )
    destructive_mode: BoolProperty(
        name="Mode destructif direct",
        description="Avertissement : applique les modifications directement sur l'objet sélectionné",
        default=False
    )
    show_advanced: BoolProperty(
        name="Paramètres avancés",
        description="Affiche les options de contrôle avancées",
        default=False
    )
    show_report: BoolProperty(
        name="Afficher le rapport",
        description="Affiche les statistiques détaillées et journaux d'exécution",
        default=True
    )

    # --- Section 3.1 : Repair ---
    enable_repair: BoolProperty(
        name="Activer Réparation",
        description="Nettoie les éléments isolés, fusionne les doublons et supprime les faces nulles",
        default=True
    )
    repair_loose_geometry: BoolProperty(
        name="Loose Geometry",
        description="Supprime les sommets ou arêtes flottants sans surface",
        default=True
    )
    loose_verts: BoolProperty(
        name="Sommets isolés",
        description="Retirer les sommets sans aucune arête connectée",
        default=True
    )
    loose_edges: BoolProperty(
        name="Arêtes isolées",
        description="Retirer les arêtes sans aucune face connectée",
        default=True
    )
    loose_faces: BoolProperty(
        name="Faces isolées",
        description="Retirer les faces détachées",
        default=False
    )
    repair_doubles: BoolProperty(
        name="Doubles",
        description="Fusionne les sommets coïncidents selon une tolérance",
        default=True
    )
    doubles_relative: BoolProperty(
        name="Relatif à la bounding box",
        description="Calcule la tolérance proportionnellement aux dimensions de l'objet",
        default=False
    )
    doubles_tolerance: FloatProperty(
        name="Tolérance absolue",
        description="Distance maximale de fusion en mètres",
        default=0.0001,
        min=0.0,
        step=0.001,
        precision=6,
        unit='LENGTH'
    )
    doubles_relative_factor: FloatProperty(
        name="Facteur relatif",
        description="Facteur multiplicateur de la diagonale de la boîte englobante",
        default=0.0001,
        min=0.0,
        step=0.001,
        precision=6
    )
    repair_zero_faces: BoolProperty(
        name="Zero Faces",
        description="Dissout les faces d'aire quasi-nulle ou dégénérées",
        default=True
    )
    zero_faces_threshold: FloatProperty(
        name="Seuil aire nulle",
        description="Aire en dessous de laquelle une face est considérée nulle",
        default=0.000001,
        min=0.0,
        step=0.0001,
        precision=7
    )
    repair_dispensables: BoolProperty(
        name="Dispensables",
        description="Simplifie les arêtes redondantes sous une déviation minime",
        default=False
    )
    dispensable_angle: FloatProperty(
        name="Angle limite",
        description="Angle maximal de déviation coplanaire en degrés",
        default=0.1,
        min=0.0,
        max=10.0,
        unit='ROTATION'
    )

    # --- Section 3.2 : Manifold ---
    enable_manifold: BoolProperty(
        name="Activer Manifold",
        description="Gestion et correction de la consistance géométrique",
        default=True
    )
    manifold_mode: EnumProperty(
        name="Mode Manifold",
        items=[
            ('DIAGNOSTIC', "Diagnostic seul", "Inspecte les non-manifold et frontières sans altérer"),
            ('CAREFUL', "Correction prudente", "Nettoie les arêtes filaires et aplanit sans supprimer de surfaces utiles"),
            ('AGGRESSIVE', "Suppression agressive", "Supprime les éléments non-manifold complexes (risqué)")
        ],
        default='CAREFUL'
    )
    fill_holes: BoolProperty(
        name="Fill Holes",
        description="Comble les ouvertures détectées (ne pas activer sur des surfaces ouvertes voulues)",
        default=False
    )
    fill_holes_max_sides: IntProperty(
        name="Max Sides",
        description="Nombre maximal d'arêtes pour combler un trou",
        default=4,
        min=3,
        max=1000
    )
    remove_wire_geometry: BoolProperty(
        name="Remove Wire Geometry",
        description="Retire les arêtes isolées filaires sans face",
        default=True
    )
    remove_non_manifold_faces: BoolProperty(
        name="Remove NM Faces",
        description="Supprime les faces non-manifold (mode agressif requis)",
        default=False
    )
    remove_non_manifold_verts: BoolProperty(
        name="Remove NM Vertices",
        description="Supprime les sommets non-manifold (mode agressif requis)",
        default=False
    )
    make_planar: BoolProperty(
        name="Make Planar / Undistort",
        description="Réduit la distorsion des faces proches d'un plan",
        default=False
    )
    make_planar_factor: FloatProperty(
        name="Facteur planar",
        default=1.0,
        min=0.0,
        max=1.0
    )
    make_planar_iterations: IntProperty(
        name="Itérations planar",
        default=1,
        min=1,
        max=20
    )
    flatten_faces: BoolProperty(
        name="Flatten Faces",
        description="Aplanit doucement les régions ciblées",
        default=False
    )
    flatten_iterations: IntProperty(
        name="Itérations flatten",
        default=3,
        min=1,
        max=20
    )

    # --- Section 3.3 : Dissolve ---
    enable_dissolve: BoolProperty(
        name="Activer Dissolve",
        description="Dissout les arêtes coplanaires sous un seuil d'angle",
        default=False
    )
    dissolve_mode: EnumProperty(
        name="Mode Dissolve",
        items=[
            ('CAREFUL', "Prudent (<= 2°)", "Préserve au maximum les silhouettes et détails"),
            ('BALANCED', "Équilibré", "Bonne réduction sans distorsion visible"),
            ('AGGRESSIVE', "Agressif", "Réduction poussée des régions plates")
        ],
        default='BALANCED'
    )
    dissolve_angle: FloatProperty(
        name="Angle limite",
        description="Angle maximal entre normales de faces adjacentes",
        default=5.0,
        min=0.0,
        max=90.0,
        unit='ROTATION'
    )
    preserve_sharp: BoolProperty(
        name="Conserver Sharp Edges",
        description="Empêche la dissolution des arêtes marquées vives",
        default=True
    )
    preserve_seams: BoolProperty(
        name="Conserver Seams UV",
        description="Empêche la dissolution des arêtes de découpe UV",
        default=True
    )
    preserve_materials: BoolProperty(
        name="Conserver frontières matériaux",
        description="Empêche la dissolution des arêtes entre deux matériaux distincts",
        default=True
    )
    preserve_uvs: BoolProperty(
        name="Conserver coordonnées UV",
        description="Empêche la déformation des îlots UV",
        default=True
    )
    preserve_boundaries: BoolProperty(
        name="Conserver frontières ouvertes",
        description="Empêche la modification du contour extérieur des maillages ouverts",
        default=True
    )

    # --- Section 4 : Simplification intelligente (Phase C) ---
    enable_simplification: BoolProperty(
        name="Activer Simplification",
        description="Moteur de réduction adaptative contrôlé par budget ou tolérance géométrique",
        default=False
    )
    simplification_mode: EnumProperty(
        name="Mode Réduction",
        items=[
            ('PERCENTAGE', "Pourcentage de réduction (%)", "Réduire d'un pourcentage cible (ex. 50%)"),
            ('BUDGET_TRIANGLES', "Budget de triangles", "Atteindre un nombre cible de triangles de rendu"),
            ('TOLERANCE_ONLY', "Tolérance maximale seule", "Réduction maximale sous une déviation géométrique maximale")
        ],
        default='PERCENTAGE'
    )
    simplification_percentage: FloatProperty(
        name="Pourcentage cible",
        description="Pourcentage de réduction du nombre initial de triangles",
        default=50.0,
        min=0.0,
        max=99.9,
        step=1.0,
        precision=1
    )
    simplification_target_triangles: IntProperty(
        name="Triangles cibles",
        description="Nombre cible de triangles estimés après simplification",
        default=1000,
        min=4,
        step=100
    )
    enable_simplification_tolerance: BoolProperty(
        name="Plafonner par tolérance",
        description="Arrête la simplification si la déviation de surface dépasse la tolérance",
        default=False
    )
    simplification_max_tolerance: FloatProperty(
        name="Tolérance max (m)",
        description="Déviation géométrique maximale admissible en mètres",
        default=0.005,
        min=0.0,
        step=0.001,
        precision=5,
        unit='LENGTH'
    )
    tolerance_relative: BoolProperty(
        name="Tolérance relative",
        description="Interprète la tolérance en proportion de la diagonale de la boîte englobante",
        default=False
    )
    collapse_triangulate: BoolProperty(
        name="Trianguler avant réduction",
        description="Force la triangulation préalable (désactiver pour préserver les quads où possible)",
        default=False
    )
    preserve_normals_angle: BoolProperty(
        name="Préserver angles de normales",
        description="Empêche les contractions d'arêtes à travers les arêtes d'ombrage marquées",
        default=False
    )

    # --- Section 3.4 : Topology ---
    enable_topology: BoolProperty(
        name="Activer Topology",
        description="Reconstruction topologique contrôlée",
        default=False
    )
    topology_mode: EnumProperty(
        name="Format Topologique",
        items=[
            ('KEEP', "Conserver la topologie existante", "Préserve le maillage tel quel (recommandé)"),
            ('TRIS', "Convert to Tris", "Triangulation complète"),
            ('QUADS', "Convert to Quads", "Reconstruction en quadrilatères par regroupement local")
        ],
        default='KEEP'
    )
    triangulate_quad_method: EnumProperty(
        name="Méthode Quad",
        items=[
            ('BEAUTY', "Beauty", "Découpe harmonieuse"),
            ('SHORTEST_DIAGONAL', "Plus courte diagonale", "Diagonale minimale")
        ],
        default='BEAUTY'
    )
    triangulate_ngon_method: EnumProperty(
        name="Méthode N-gon",
        items=[
            ('BEAUTY', "Beauty", "Découpe équilibrée"),
            ('CLIP', "Clip", "Découpe par oreilles")
        ],
        default='BEAUTY'
    )
    quads_face_threshold: FloatProperty(
        name="Seuil de face",
        default=0.698,
        min=0.0,
        max=3.14159
    )
    quads_shape_threshold: FloatProperty(
        name="Seuil de forme",
        default=0.698,
        min=0.0,
        max=3.14159
    )
    preserve_topology_attributes: BoolProperty(
        name="Préserver attributs",
        description="Préserver UVs, VCols, Seams et Matériaux lors de la quadrangulation",
        default=True
    )

    # --- Section 3.5 : Normals ---
    enable_normals: BoolProperty(
        name="Activer Normals",
        description="Recalcul et lissage des normales",
        default=True
    )
    recalculate_normals: BoolProperty(
        name="Recalculer les normales",
        description="Rend l'orientation des faces cohérente",
        default=True
    )
    recalculate_direction: EnumProperty(
        name="Direction",
        items=[
            ('OUTSIDE', "Extérieur (Outside)", "Normals pointant vers l'extérieur"),
            ('INSIDE', "Intérieur (Inside)", "Normals pointant vers l'intérieur")
        ],
        default='OUTSIDE'
    )
    apply_auto_smooth: BoolProperty(
        name="Auto Smooth par angle",
        description="Applique le lissage d'ombrage selon un seuil angulaire",
        default=True
    )
    auto_smooth_angle: FloatProperty(
        name="Angle de lissage",
        description="Angle limite pour les arêtes vives",
        default=30.0,
        min=0.0,
        max=180.0,
        unit='ROTATION'
    )
    weighted_normals: BoolProperty(
        name="Weighted Normals",
        description="Applique le modificateur de normales pondérées",
        default=False
    )
    clear_custom_split_normals: BoolProperty(
        name="Clear Custom Split Normals",
        description="Supprime les normales scindées personnalisées",
        default=False
    )
    clear_sharp_edges: BoolProperty(
        name="Clear Sharp Edges",
        description="Efface les marquages d'arêtes vives",
        default=False
    )

    # --- Section 3.6 : Object Data ---
    enable_object_data: BoolProperty(
        name="Activer Object Data",
        description="Nettoyage des données associées à l'objet",
        default=True
    )
    clean_material_doubles: BoolProperty(
        name="Material Doubles",
        description="Fusionne les slots pointant vers le même matériau",
        default=True
    )
    clean_unused_material_slots: BoolProperty(
        name="Material Slots inutilisés",
        description="Supprime les slots de matériaux non assignés aux polygones",
        default=True
    )
    clean_empty_vertex_groups: BoolProperty(
        name="Vertex Groups vides",
        description="Supprime les groupes de sommets sans poids positif",
        default=True
    )

    # --- Résultats et rapport de session ---
    last_status: StringProperty(name="Statut", default="Non exécuté")
    last_duration: FloatProperty(name="Durée (s)", default=0.0)
    last_verts_before: IntProperty(default=0)
    last_verts_after: IntProperty(default=0)
    last_edges_before: IntProperty(default=0)
    last_edges_after: IntProperty(default=0)
    last_faces_before: IntProperty(default=0)
    last_faces_after: IntProperty(default=0)
    last_tris_before: IntProperty(default=0)
    last_tris_after: IntProperty(default=0)
    last_reduction: FloatProperty(default=0.0)
    last_result_obj_name: StringProperty(default="")
    last_logs: StringProperty(default="")


def register_properties():
    bpy.utils.register_class(MeshForgeSettings)
    bpy.types.Scene.meshforge_settings = PointerProperty(type=MeshForgeSettings)


def unregister_properties():
    if hasattr(bpy.types.Scene, "meshforge_settings"):
        del bpy.types.Scene.meshforge_settings
    bpy.utils.unregister_class(MeshForgeSettings)
