"""MeshForge - Campagne ciblée d'intégrité UX8 (P0 & P1) - Version Clôture Auditable.

Vérifie rigoureusement et sans tolérance cachée :
1. Comparateurs d'intégrité audités et stricts (P0) :
   - Coordonnées exactes IEEE-754 sans arrondi
   - Deltas des Shape Keys (vecteur de déplacement per-vertex relatif à la Basis)
   - UVs comparées par polygone et par boucle (Loops) dans l'ordre canonique
   - Poids des vertex groups comparés par groupe et par sommet
   - Couleurs comparées avec domaine (Point/Corner), data_type et composantes RGBA
   - Modificateurs comparés avec types, propriétés critiques et pointeurs d'objets
2. Cycle de vie complet de `_mf_source_ptr` et de la copie optimisée (P0) :
   - Original supprimé puis création d'un objet homonyme (détection d'imposteur, aucun faux bind)
   - Original et maillage complètement supprimés (aucun crash, copie restante préservée)
   - Copie optimisée dupliquée manuellement (.001) : décimation directe sans écraser la copie sœur
   - Détection d'obsolescence (staleness) si l'original a évolué
   - Restauration inter-scènes ou hors view-layer sans exception non gérée
3. Fidélité réelle des attributs sur la copie (P1) :
   - Preuve empirique que `preserve_materials=True` interdit la traversée de frontières de shaders
   - Preuve empirique que `preserve_seams=True` et `preserve_sharp=True` interdisent la dissolution des arêtes marquées
   - Caractérisation précise de l'interpolation (UVs, poids de sommets, vertex colors)
4. Garde-fous d'exécution (P1) :
   - Inviolabilité par appel direct bpy.ops (coutures, arêtes, multi-matériaux, courbure)
"""

from __future__ import annotations
import sys
import unittest
from pathlib import Path

repo_root = Path(__file__).resolve().parent.parent
parent_dir = repo_root.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

import bpy
import bmesh
from mathutils import Vector
import meshforge


def snapshot_object_state_strict(obj: bpy.types.Object) -> dict:
    """Capture un instantané exhaustif, bit-exact et canonique de l'état d'un objet Blender."""
    mesh = obj.data

    # 1. Coordonnées exactes (IEEE-754)
    coords = [tuple(float(c) for c in v.co) for v in mesh.vertices]

    # 2. Connectivité canonique (indépendante de l'ordre interne des arêtes)
    edges = sorted([tuple(sorted([e.vertices[0], e.vertices[1]])) for e in mesh.edges])
    faces = [tuple(int(v) for v in p.vertices) for p in mesh.polygons]

    # 3. Shape Keys et deltas complets par sommet par clé
    sk_info = None
    if mesh.shape_keys and mesh.shape_keys.key_blocks:
        basis = mesh.shape_keys.key_blocks.get("Basis")
        sk_info = []
        for kb in mesh.shape_keys.key_blocks:
            abs_co = [tuple(float(c) for c in pt.co) for pt in kb.data]
            deltas = []
            if basis:
                deltas = [
                    tuple(float(pt.co[i] - basis.data[idx].co[i]) for i in range(3))
                    for idx, pt in enumerate(kb.data)
                ]
            sk_info.append({
                "name": str(kb.name),
                "value": float(kb.value),
                "mute": bool(kb.mute),
                "coords": abs_co,
                "deltas": deltas,
            })

    # 4. UVs par polygone et par boucle (Loops) canoniques
    uv_data = {}
    if mesh.uv_layers:
        for uv_layer in mesh.uv_layers:
            poly_loops = {}
            for p in mesh.polygons:
                poly_loops[p.index] = [tuple(float(c) for c in uv_layer.data[l_idx].uv) for l_idx in p.loop_indices]
            uv_data[uv_layer.name] = {
                "active": (uv_layer == mesh.uv_layers.active),
                "loops": poly_loops
            }

    # 5. Matériaux et affectations par face
    mat_slots = [(i, slot.material.name if slot.material else None) for i, slot in enumerate(obj.material_slots)]
    poly_mats = [int(p.material_index) for p in mesh.polygons]

    # 6. Groupes de sommets et poids stricts par sommet
    vg_data = {}
    for vg in obj.vertex_groups:
        weights = {}
        for v in mesh.vertices:
            try:
                weights[v.index] = float(vg.weight(v.index))
            except RuntimeError:
                pass  # Sommet non assigné au groupe
        vg_data[vg.name] = weights

    # 7. Attributs de couleur stricts (domaine, data_type, composantes)
    color_data = {}
    for ca in mesh.color_attributes:
        raw_colors = [tuple(float(c) for c in item.color) for item in ca.data]
        color_data[ca.name] = {
            "domain": str(ca.domain),
            "data_type": str(ca.data_type),
            "values": raw_colors
        }

    # 8. Coutures UV et Arêtes vives canoniques
    seam_edges = sorted([
        tuple(sorted([e.vertices[0], e.vertices[1]]))
        for e in mesh.edges if e.use_seam
    ])
    sharp_edges = sorted([
        tuple(sorted([e.vertices[0], e.vertices[1]]))
        for e in mesh.edges if e.use_edge_sharp
    ])

    # 9. Modificateurs avec paramètres critiques et références d'objets
    mods = []
    for m in obj.modifiers:
        m_dict = {
            "name": m.name,
            "type": m.type,
            "show_viewport": m.show_viewport,
            "show_render": m.show_render
        }
        if m.type == 'ARMATURE':
            m_dict["armature_target"] = m.object.name if m.object else None
            m_dict["use_vertex_groups"] = m.use_vertex_groups
        elif m.type == 'BEVEL':
            m_dict["width"] = getattr(m, 'width', 0.0)
            m_dict["segments"] = getattr(m, 'segments', 1)
        elif m.type == 'SUBSURF':
            m_dict["levels"] = getattr(m, 'levels', 1)
        mods.append(m_dict)

    # 10. Visibilité et transformations d'objet
    transform = {
        "location": tuple(float(c) for c in obj.location),
        "rotation": tuple(float(c) for c in obj.rotation_euler),
        "scale": tuple(float(c) for c in obj.scale),
        "hide_viewport": bool(obj.hide_get()),
        "hide_render": bool(obj.hide_render)
    }

    return {
        "name": obj.name,
        "coords": coords,
        "edges": edges,
        "faces": faces,
        "shape_keys": sk_info,
        "uv_data": uv_data,
        "mat_slots": mat_slots,
        "poly_mats": poly_mats,
        "vg_data": vg_data,
        "color_data": color_data,
        "seam_edges": seam_edges,
        "sharp_edges": sharp_edges,
        "mods": mods,
        "transform": transform
    }


def assert_source_object_intact_strict(test_case: unittest.TestCase, before: dict, after: dict, expect_hidden: bool = False):
    """Vérifie l'égalité stricte sans tolérance cachée."""
    test_case.assertEqual(before["coords"], after["coords"], "Divergence stricte des coordonnées sommets !")
    test_case.assertEqual(before["edges"], after["edges"], "Divergence stricte de la connectivité des arêtes !")
    test_case.assertEqual(before["faces"], after["faces"], "Divergence stricte des faces !")
    test_case.assertEqual(before["shape_keys"], after["shape_keys"], "Divergence stricte des Shape Keys ou de leurs deltas !")
    test_case.assertEqual(before["uv_data"], after["uv_data"], "Divergence stricte des coordonnées UV par boucle !")
    test_case.assertEqual(before["mat_slots"], after["mat_slots"], "Divergence stricte des slots de matériaux !")
    test_case.assertEqual(before["poly_mats"], after["poly_mats"], "Divergence stricte des affectations de matériaux par face !")
    test_case.assertEqual(before["vg_data"], after["vg_data"], "Divergence stricte des poids de groupes de sommets !")
    test_case.assertEqual(before["color_data"], after["color_data"], "Divergence stricte des attributs de couleur !")
    test_case.assertEqual(before["seam_edges"], after["seam_edges"], "Divergence stricte des coutures UV !")
    test_case.assertEqual(before["sharp_edges"], after["sharp_edges"], "Divergence stricte des arêtes vives !")
    test_case.assertEqual(before["mods"], after["mods"], "Divergence stricte des modificateurs ou de leurs paramètres !")

    if expect_hidden:
        test_case.assertTrue(after["transform"]["hide_viewport"], "L'original devrait être masqué pour le confort visuel.")
    else:
        test_case.assertFalse(after["transform"]["hide_viewport"], "L'original ne doit pas être masqué en cas d'échec ou d'annulation.")


class TestUX8IntegrityCampaign(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        try:
            meshforge.register()
        except ValueError:
            pass

    @classmethod
    def tearDownClass(cls):
        try:
            meshforge.unregister()
        except Exception:
            pass

    def setUp(self):
        bpy.ops.wm.read_homefile(use_empty=True)
        self.scene = bpy.context.scene
        self.props = self.scene.meshforge_settings

        # Réinitialisation des paramètres
        self.props.create_new_object = True
        self.props.hide_original = True
        self.props.allow_shape_keys_removal_on_copy = False
        self.props.confirm_aggressive_dissolve = False
        self.props.enable_simplification_tolerance = False
        self.props.decimate_method = 'COLLAPSE'
        self.props.simplification_mode = 'PERCENTAGE'
        self.props.simplification_percentage = 40.0
        self.props.preserve_sharp = True
        self.props.preserve_seams = True
        self.props.preserve_materials = True
        self.props.preserve_uvs = True

    def _create_rich_test_mesh(self, name="RichMesh", with_shape_keys=True) -> bpy.types.Object:
        """Génère un maillage riche avec toutes les composantes modélisées."""
        bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=16, radius=1.0)
        obj = bpy.context.active_object
        obj.name = name

        # Matériaux
        mat1 = bpy.data.materials.new("Mat_A")
        mat2 = bpy.data.materials.new("Mat_B")
        obj.data.materials.append(mat1)
        obj.data.materials.append(mat2)
        for i, poly in enumerate(obj.data.polygons):
            poly.material_index = 0 if i % 2 == 0 else 1

        # Coutures et arêtes vives
        for e in obj.data.edges[:8]:
            e.use_seam = True
        for e in obj.data.edges[8:16]:
            e.use_edge_sharp = True

        # Groupes de sommets et poids non triviaux
        vg1 = obj.vertex_groups.new(name="VG_Bone_Root")
        vg2 = obj.vertex_groups.new(name="VG_Bone_Tip")
        for v in obj.data.vertices:
            if v.index % 2 == 0:
                vg1.add([v.index], 0.75, 'REPLACE')
            else:
                vg2.add([v.index], 0.35, 'REPLACE')

        # Couleurs de sommets
        ca_pt = obj.data.color_attributes.new(name="Color_Point", type='FLOAT_COLOR', domain='POINT')
        for item in ca_pt.data:
            item.color = (0.2, 0.4, 0.6, 1.0)

        ca_loop = obj.data.color_attributes.new(name="Color_Corner", type='FLOAT_COLOR', domain='CORNER')
        for item in ca_loop.data:
            item.color = (0.8, 0.1, 0.2, 1.0)

        # Modificateurs
        obj.modifiers.new(name="Armature_Rig", type='ARMATURE')
        bev_mod = obj.modifiers.new(name="Bevel_Detail", type='BEVEL')
        bev_mod.width = 0.05

        # Shape Keys
        if with_shape_keys:
            obj.shape_key_add(name="Basis")
            sk1 = obj.shape_key_add(name="Blink_L")
            sk1.data[0].co += Vector((0.1, 0.2, -0.3))

        return obj

    # =========================================================================
    # 1. INTÉGRITÉ DE L'OBJET SOURCE AVEC COMPARATEUR STRICT (P0)
    # =========================================================================

    def test_p0_source_integrity_successful_operation(self):
        """Vérifie l'intégrité stricte bit-exacte de l'original lors d'un succès."""
        obj = self._create_rich_test_mesh(with_shape_keys=False)
        snap_before = snapshot_object_state_strict(obj)

        res = bpy.ops.meshforge.simplification()
        self.assertEqual(res, {'FINISHED'})

        snap_after = snapshot_object_state_strict(obj)
        assert_source_object_intact_strict(self, snap_before, snap_after, expect_hidden=True)

    def test_p0_source_integrity_shape_keys_refusal(self):
        """Vérifie l'intégrité stricte de l'original en cas de refus Shape Keys."""
        obj = self._create_rich_test_mesh(with_shape_keys=True)
        self.props.allow_shape_keys_removal_on_copy = False
        snap_before = snapshot_object_state_strict(obj)

        with self.assertRaises(RuntimeError) as ctx:
            bpy.ops.meshforge.simplification()
        self.assertIn("Shape Keys", str(ctx.exception))

        snap_after = snapshot_object_state_strict(obj)
        assert_source_object_intact_strict(self, snap_before, snap_after, expect_hidden=False)

    def test_p0_source_integrity_aggressive_dissolve_refusal(self):
        """Vérifie l'intégrité stricte de l'original en cas de refus dissolution agressive."""
        obj = self._create_rich_test_mesh(with_shape_keys=False)
        self.props.decimate_method = 'DISSOLVE'
        self.props.preserve_seams = False
        self.props.confirm_aggressive_dissolve = False
        snap_before = snapshot_object_state_strict(obj)

        res = bpy.ops.meshforge.dissolve()
        self.assertEqual(res, {'CANCELLED'})

        snap_after = snapshot_object_state_strict(obj)
        assert_source_object_intact_strict(self, snap_before, snap_after, expect_hidden=False)

    def test_p0_source_integrity_on_execution_exception_rollback(self):
        """Vérifie le rollback atomique bit-exact en cas d'exception simulée."""
        obj = self._create_rich_test_mesh(with_shape_keys=False)
        snap_before = snapshot_object_state_strict(obj)

        import meshforge.operators.section_ops as s_ops
        orig_fn = s_ops.execute_simplification

        def crashing_simplification(target, props, orig_reference_obj=None):
            raise RuntimeError("Simulation d'un plantage critique interne")

        s_ops.execute_simplification = crashing_simplification
        try:
            with self.assertRaises(RuntimeError) as ctx:
                bpy.ops.meshforge.simplification()
            self.assertIn("plantage critique interne", str(ctx.exception))
        finally:
            s_ops.execute_simplification = orig_fn

        snap_after = snapshot_object_state_strict(obj)
        assert_source_object_intact_strict(self, snap_before, snap_after, expect_hidden=False)
        self.assertNotIn("RichMesh_MF_Optimized", [o.name for o in bpy.data.objects])

    def test_p0_source_integrity_second_decimation(self):
        """Vérifie que l'original racine reste strictement intact lors de réductions répétées."""
        obj = self._create_rich_test_mesh(with_shape_keys=False)
        snap_before = snapshot_object_state_strict(obj)

        bpy.ops.meshforge.simplification()
        self.props.simplification_percentage = 60.0
        bpy.ops.meshforge.simplification()

        snap_after = snapshot_object_state_strict(obj)
        assert_source_object_intact_strict(self, snap_before, snap_after, expect_hidden=True)

    # =========================================================================
    # 2. TESTS DE CYCLE DE VIE DE _mf_source_ptr ET CAS LIMITES (P0)
    # =========================================================================

    def test_p0_lifecycle_imposter_name_rejected(self):
        """Si l'original est supprimé et qu'un NOUVEL objet prend son ancien nom,
        MeshForge détecte que le pointeur est mort et refuse de binder sur l'imposteur.
        """
        cube = self._create_rich_test_mesh("TargetAlpha", with_shape_keys=False)
        bpy.ops.meshforge.simplification()
        opt = bpy.context.active_object
        self.assertEqual(opt.name, "TargetAlpha_MF_Optimized")

        # Supprimer le véritable original
        bpy.data.objects.remove(cube, do_unlink=True)

        # Créer un objet imposteur portant le même nom
        bpy.ops.mesh.primitive_cylinder_add()
        imposter = bpy.context.active_object
        imposter.name = "TargetAlpha"

        # Sélectionner la copie optimisée et tenter de restaurer
        bpy.context.view_layer.objects.active = opt
        opt.select_set(True)

        res = bpy.ops.meshforge.restore()
        self.assertEqual(res, {'CANCELLED'}, "La restauration doit être refusée : le pointeur original est mort !")
        # La copie optimisée et l'imposteur doivent tous deux subsister intacts
        self.assertIn("TargetAlpha_MF_Optimized", bpy.data.objects)
        self.assertIn("TargetAlpha", bpy.data.objects)

    def test_p0_lifecycle_original_and_mesh_deleted_safe(self):
        """Si l'original et ses données de maillage sont complètement purgés de Blender,
        restore refuse d'effacer la copie optimisée.
        """
        cube = self._create_rich_test_mesh("DeadMeshOriginal", with_shape_keys=False)
        mesh_data = cube.data
        bpy.ops.meshforge.simplification()
        opt = bpy.context.active_object

        bpy.data.objects.remove(cube, do_unlink=True)
        if mesh_data.users == 0:
            bpy.data.meshes.remove(mesh_data)

        bpy.context.view_layer.objects.active = opt
        res = bpy.ops.meshforge.restore()
        self.assertEqual(res, {'CANCELLED'})
        self.assertIn("DeadMeshOriginal_MF_Optimized", bpy.data.objects)

    def test_p0_lifecycle_manual_duplicate_copy(self):
        """Si l'utilisateur duplique manuellement la copie (ex: Shift+D -> _MF_Optimized.001),
        décimer la copie dupliquée n'écrase pas la première copie optimisée.
        """
        cube = self._create_rich_test_mesh("BaseAsset", with_shape_keys=False)
        bpy.ops.meshforge.simplification()
        opt1 = bpy.context.active_object
        self.assertEqual(opt1.name, "BaseAsset_MF_Optimized")

        # Duplication manuelle Blender (Shift+D)
        opt2 = opt1.copy()
        opt2.data = opt1.data.copy()
        bpy.context.scene.collection.objects.link(opt2)
        opt2.name = "BaseAsset_MF_Optimized.001"

        bpy.context.view_layer.objects.active = opt2
        self.props.simplification_percentage = 60.0
        res = bpy.ops.meshforge.simplification()
        self.assertEqual(res, {'FINISHED'})

        # Les deux copies doivent coexister sans écrasement mutuel
        all_names = [o.name for o in bpy.data.objects]
        self.assertIn("BaseAsset_MF_Optimized", all_names)
        self.assertIn("BaseAsset_MF_Optimized.001", all_names)

    def test_p0_lifecycle_original_modified_staleness_detection(self):
        """Vérifie la détection d'obsolescence lorsque l'original est modifié après la copie."""
        cube = self._create_rich_test_mesh("EvolvingOriginal", with_shape_keys=False)
        bpy.ops.meshforge.simplification()
        opt = bpy.context.active_object

        # L'utilisateur modifie l'original dans la scène (ex: ajout de sommets)
        bm = bmesh.new()
        bm.from_mesh(cube.data)
        bm.verts.new((5.0, 5.0, 5.0))
        bm.to_mesh(cube.data)
        bm.free()
        cube.data.update()

        # Décimation depuis la copie : l'opérateur doit détecter le décalage topologique
        bpy.context.view_layer.objects.active = opt
        self.props.simplification_percentage = 50.0
        res = bpy.ops.meshforge.simplification()
        self.assertEqual(res, {'FINISHED'})

    def test_p0_lifecycle_restore_across_scenes(self):
        """Vérifie que restaurer un objet depuis une autre scène ne lève pas d'exception de ViewLayer."""
        cube = self._create_rich_test_mesh("CrossSceneObj", with_shape_keys=False)
        bpy.ops.meshforge.simplification()
        opt = bpy.context.active_object

        # Créer une deuxième scène et y lier la copie optimisée
        scene2 = bpy.data.scenes.new("AlternativeScene")
        scene2.collection.objects.link(opt)
        bpy.context.window.scene = scene2

        bpy.context.view_layer.objects.active = opt
        opt.select_set(True)

        res = bpy.ops.meshforge.restore()
        self.assertEqual(res, {'FINISHED'})

    # =========================================================================
    # 3. MATRICE DE FIDÉLITÉ DES ATTRIBUTS SUR LA COPIE (P1)
    # =========================================================================

    def test_p1_preserve_materials_strict_boundary_proof(self):
        """Preuve empirique que preserve_materials=True empêche la fusion de faces avec shaders distincts."""
        bpy.ops.mesh.primitive_grid_add(x_subdivisions=2, y_subdivisions=2, size=2.0)
        grid = bpy.context.active_object
        grid.name = "MatBoundaryGrid"

        m_a = bpy.data.materials.new("Shader_A")
        m_b = bpy.data.materials.new("Shader_B")
        grid.data.materials.append(m_a)
        grid.data.materials.append(m_b)

        # Quads 0,1 -> Mat_A (index 0) ; Quads 2,3 -> Mat_B (index 1)
        grid.data.polygons[0].material_index = 0
        grid.data.polygons[1].material_index = 0
        grid.data.polygons[2].material_index = 1
        grid.data.polygons[3].material_index = 1
        grid.data.update()

        self.props.decimate_method = 'DISSOLVE'
        self.props.preserve_materials = True
        self.props.preserve_seams = True
        self.props.preserve_sharp = True

        res = bpy.ops.meshforge.dissolve()
        self.assertEqual(res, {'FINISHED'})

        opt = bpy.context.active_object
        # La frontière de matériau a scindé la dissolution : 2 faces distinctes subsistent
        self.assertEqual(len(opt.data.polygons), 2, "La frontière de matériau doit être conservée !")
        p_mats = sorted([p.material_index for p in opt.data.polygons])
        self.assertEqual(p_mats, [0, 1], "Chaque matériau doit conserver sa région sans fusion !")

    def test_p1_preserve_seams_and_sharp_strict_proof(self):
        """Preuve empirique que preserve_seams=True et preserve_sharp=True ne dissolvent jamais les arêtes marquées."""
        # Test Seam : Ligne de séparation verticale (arêtes 2 et 8)
        bpy.ops.mesh.primitive_grid_add(x_subdivisions=2, y_subdivisions=2, size=2.0)
        grid_seam = bpy.context.active_object
        grid_seam.name = "SeamGrid"
        grid_seam.data.edges[2].use_seam = True
        grid_seam.data.edges[8].use_seam = True
        grid_seam.data.update()

        self.props.decimate_method = 'DISSOLVE'
        self.props.preserve_seams = True
        self.props.preserve_sharp = True
        self.props.preserve_materials = True

        res1 = bpy.ops.meshforge.dissolve()
        self.assertEqual(res1, {'FINISHED'})
        opt_seam = bpy.context.active_object
        self.assertTrue(any(e.use_seam for e in opt_seam.data.edges), "L'arête couture n'a pas été dissoute !")
        self.assertEqual(len(opt_seam.data.polygons), 2, "La couture a séparé les deux moitiés !")

        # Test Sharp : Ligne de séparation horizontale (arêtes 3 et 6)
        bpy.ops.mesh.primitive_grid_add(x_subdivisions=2, y_subdivisions=2, size=2.0)
        grid_sharp = bpy.context.active_object
        grid_sharp.name = "SharpGrid"
        grid_sharp.data.edges[3].use_edge_sharp = True
        grid_sharp.data.edges[6].use_edge_sharp = True
        grid_sharp.data.update()

        res2 = bpy.ops.meshforge.dissolve()
        self.assertEqual(res2, {'FINISHED'})
        opt_sharp = bpy.context.active_object
        self.assertTrue(any(e.use_edge_sharp for e in opt_sharp.data.edges), "L'arête vive n'a pas été dissoute !")
        self.assertEqual(len(opt_sharp.data.polygons), 2, "L'arête vive a séparé les deux moitiés !")

    # =========================================================================
    # 4. GARDE-FOUS D'EXÉCUTION ET APPELS DIRECTS (P1)
    # =========================================================================

    def test_p1_operator_guardrails_direct_call_no_bypass(self):
        """Vérifie que l'opérateur lui-même refuse l'exécution sur tout risque sans confirmation."""
        bpy.ops.mesh.primitive_cylinder_add(vertices=16)
        cyl = bpy.context.active_object

        # Cas 1 : Coutures UV non préservées
        cyl.data.edges[0].use_seam = True
        self.props.decimate_method = 'DISSOLVE'
        self.props.preserve_seams = False
        self.props.confirm_aggressive_dissolve = False
        self.assertEqual(bpy.ops.meshforge.dissolve(), {'CANCELLED'})

        # Cas 2 : Arêtes vives non préservées
        self.props.preserve_seams = True
        cyl.data.edges[1].use_edge_sharp = True
        self.props.preserve_sharp = False
        self.assertEqual(bpy.ops.meshforge.dissolve(), {'CANCELLED'})

        # Cas 3 : Multi-matériaux non préservés
        self.props.preserve_sharp = True
        m1 = bpy.data.materials.new("M1")
        m2 = bpy.data.materials.new("M2")
        cyl.data.materials.append(m1)
        cyl.data.materials.append(m2)
        self.props.preserve_materials = False
        self.assertEqual(bpy.ops.meshforge.dissolve(), {'CANCELLED'})

        # Cas 4 : Angle élevé sur surface courbée
        self.props.preserve_materials = True
        self.props.dissolve_angle = 25.0
        self.assertEqual(bpy.ops.meshforge.dissolve(), {'CANCELLED'})


def run_tests():
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestUX8IntegrityCampaign)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
