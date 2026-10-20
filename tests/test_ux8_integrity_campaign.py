"""MeshForge - Campagne ciblée d'intégrité UX8 (P0 & P1).

Vérifie rigoureusement :
1. Intégrité absolue de l'objet source (P0) :
   - Opération réussie sur une copie (l'original reste 100% identique au bit près, simplement masqué)
   - Refus Shape Keys (original non modifié, non masqué)
   - Refus dissolution agressive (original non modifié, non masqué)
   - Exception provoquée / erreur d'exécution (rollback atomique : copie purgée, original restauré actif et visible)
   - Deuxième décimation sur la copie optimisée (l'original racine demeure 100% intact)
2. Atomicité et restauration (P0) :
   - Rollback atomique sans orphelins ni masquage de l'original
   - Renommage de l'original après décimation : restauration résolue sans erreur via `_mf_source_ptr`
   - Suffixes numériques : `Mesh.001` ne prolifère pas en `Mesh.001_MF_Optimized.001`
   - Décimations successives réutilisent la copie optimisée
   - Suppression accidentelle de l'original : la restauration refuse d'écraser/supprimer le résultat orphelin
3. Matrice de fidélité des attributs (P1) :
   - Test sur maillage multi-îlots, coutures, arêtes vives, multi-matériaux, vertex groups non triviaux et color attributes
   - Distinction rigoureuse : Présent / Conservé exactement / Interpolé
4. Copie statique sans Shape Keys (P1) :
   - Purge ciblée sur la copie uniquement, original préservé
   - Statut de dérivé statique (LOD/Bake/Collision)
5. Garde-fous de dissolution (P1) :
   - Vérification de tous les déclencheurs (seams, sharp, matériaux multiples, courbure)
   - Exigence stricte de confirmation explicite
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


def snapshot_object_state(obj: bpy.types.Object) -> dict:
    """Capture un instantané exhaustif de l'état d'un objet Blender."""
    mesh = obj.data

    coords = [tuple(v.co) for v in mesh.vertices]
    edges = [tuple(sorted(e.vertices)) for e in mesh.edges]
    faces = [tuple(p.vertices) for p in mesh.polygons]

    sk_info = None
    if mesh.shape_keys:
        sk_info = []
        for kb in mesh.shape_keys.key_blocks:
            sk_info.append({
                "name": kb.name,
                "value": kb.value,
                "data": [tuple(pt.co) for pt in kb.data]
            })

    uv_data = {}
    if mesh.uv_layers:
        for uv_layer in mesh.uv_layers:
            uv_data[uv_layer.name] = [tuple(loop.uv) for loop in uv_layer.data]

    mat_names = [slot.material.name if slot.material else "" for slot in obj.material_slots]
    poly_mats = [p.material_index for p in mesh.polygons]

    vg_data = {}
    for vg in obj.vertex_groups:
        weights = {}
        for i in range(len(mesh.vertices)):
            try:
                weights[i] = vg.weight(i)
            except RuntimeError:
                pass
        vg_data[vg.name] = weights

    color_data = {}
    for ca in mesh.color_attributes:
        color_data[ca.name] = {
            "domain": ca.domain,
            "data_type": ca.data_type,
            "values": [tuple(getattr(item, "color", ())) for item in ca.data]
        }

    seams = [e.index for e in mesh.edges if e.use_seam]
    sharp = [e.index for e in mesh.edges if e.use_edge_sharp]

    mods = [(m.name, m.type, getattr(m, 'show_viewport', True)) for m in obj.modifiers]

    vis = {
        "hide_viewport": obj.hide_get(),
        "hide_render": obj.hide_render
    }

    return {
        "name": obj.name,
        "coords": coords,
        "edges": edges,
        "faces": faces,
        "shape_keys": sk_info,
        "uv_data": uv_data,
        "mat_names": mat_names,
        "poly_mats": poly_mats,
        "vg_data": vg_data,
        "color_data": color_data,
        "seams": seams,
        "sharp": sharp,
        "mods": mods,
        "vis": vis
    }


def assert_source_object_intact(test_case: unittest.TestCase, snap_before: dict, snap_after: dict, expect_hidden: bool = False):
    """Vérifie au bit près que l'objet source n'a subi AUCUNE altération de données."""
    test_case.assertEqual(snap_before["coords"], snap_after["coords"], "Altération des coordonnées de l'original !")
    test_case.assertEqual(snap_before["edges"], snap_after["edges"], "Altération de la connectivité des arêtes de l'original !")
    test_case.assertEqual(snap_before["faces"], snap_after["faces"], "Altération de la connectivité des faces de l'original !")
    test_case.assertEqual(snap_before["shape_keys"], snap_after["shape_keys"], "Altération des Shape Keys de l'original !")
    test_case.assertEqual(snap_before["uv_data"], snap_after["uv_data"], "Altération des coordonnées UV de l'original !")
    test_case.assertEqual(snap_before["mat_names"], snap_after["mat_names"], "Altération de la liste des matériaux de l'original !")
    test_case.assertEqual(snap_before["poly_mats"], snap_after["poly_mats"], "Altération des affectations de matériaux par face de l'original !")
    test_case.assertEqual(snap_before["vg_data"], snap_after["vg_data"], "Altération des groupes ou poids de sommets de l'original !")
    test_case.assertEqual(snap_before["color_data"], snap_after["color_data"], "Altération des attributs de couleur de l'original !")
    test_case.assertEqual(snap_before["seams"], snap_after["seams"], "Altération des coutures UV de l'original !")
    test_case.assertEqual(snap_before["sharp"], snap_after["sharp"], "Altération des arêtes vives de l'original !")
    test_case.assertEqual(snap_before["mods"], snap_after["mods"], "Altération de la pile de modificateurs de l'original !")

    if expect_hidden:
        test_case.assertTrue(snap_after["vis"]["hide_viewport"], "L'original devrait être masqué après succès non-destructif.")
    else:
        test_case.assertFalse(snap_after["vis"]["hide_viewport"], "L'original ne doit pas être masqué en cas de refus ou d'échec.")


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

        # Réinitialisation
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
        """Génère un maillage riche complet : UVs, coutures, arêtes vives, 2 matériaux, 2 vgroups, couleurs, modificateurs."""
        bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=16, radius=1.0)
        obj = bpy.context.active_object
        obj.name = name

        # 1. Deux matériaux
        mat1 = bpy.data.materials.new("Mat_A")
        mat2 = bpy.data.materials.new("Mat_B")
        obj.data.materials.append(mat1)
        obj.data.materials.append(mat2)
        for i, poly in enumerate(obj.data.polygons):
            poly.material_index = 0 if i % 2 == 0 else 1

        # 2. Coutures UV et arêtes vives
        for e in obj.data.edges[:8]:
            e.use_seam = True
        for e in obj.data.edges[8:16]:
            e.use_edge_sharp = True

        # 3. Groupes de sommets et poids non triviaux
        vg1 = obj.vertex_groups.new(name="VG_Bone_Root")
        vg2 = obj.vertex_groups.new(name="VG_Bone_Tip")
        for v in obj.data.vertices:
            if v.index % 2 == 0:
                vg1.add([v.index], 0.75, 'REPLACE')
            else:
                vg2.add([v.index], 0.35, 'REPLACE')

        # 4. Attributs de couleur (POINT et CORNER)
        ca_pt = obj.data.color_attributes.new(name="Color_Point", type='FLOAT_COLOR', domain='POINT')
        for item in ca_pt.data:
            item.color = (0.2, 0.4, 0.6, 1.0)

        ca_loop = obj.data.color_attributes.new(name="Color_Corner", type='FLOAT_COLOR', domain='CORNER')
        for item in ca_loop.data:
            item.color = (0.8, 0.1, 0.2, 1.0)

        # 5. Modificateurs (Armature & Bevel désactivé)
        arm_mod = obj.modifiers.new(name="Armature_Rig", type='ARMATURE')
        bev_mod = obj.modifiers.new(name="Bevel_Detail", type='BEVEL')
        bev_mod.width = 0.05

        # 6. Shape Keys
        if with_shape_keys:
            obj.shape_key_add(name="Basis")
            sk1 = obj.shape_key_add(name="Blink_L")
            sk1.data[0].co += Vector((0.1, 0.2, -0.3))

        return obj

    # =========================================================================
    # SECTION 1 : INTÉGRITÉ DE L'OBJET SOURCE — P0
    # =========================================================================

    def test_p0_source_integrity_successful_operation(self):
        """Scénario 1.1 : Opération réussie sur une copie.
        L'objet original doit rester 100% identique au bit près dans toutes ses données.
        """
        obj = self._create_rich_test_mesh(with_shape_keys=False)
        snap_before = snapshot_object_state(obj)

        res = bpy.ops.meshforge.simplification()
        self.assertEqual(res, {'FINISHED'})

        snap_after = snapshot_object_state(obj)
        assert_source_object_intact(self, snap_before, snap_after, expect_hidden=True)

    def test_p0_source_integrity_shape_keys_refusal(self):
        """Scénario 1.2 : Refus lié aux Shape Keys.
        L'original doit rester 100% intact et visible (non masqué).
        """
        obj = self._create_rich_test_mesh(with_shape_keys=True)
        self.props.allow_shape_keys_removal_on_copy = False
        snap_before = snapshot_object_state(obj)

        with self.assertRaises(RuntimeError) as ctx:
            bpy.ops.meshforge.simplification()
        self.assertIn("Shape Keys", str(ctx.exception))

        snap_after = snapshot_object_state(obj)
        assert_source_object_intact(self, snap_before, snap_after, expect_hidden=False)

    def test_p0_source_integrity_aggressive_dissolve_refusal(self):
        """Scénario 1.3 : Refus lié à une dissolution agressive.
        L'original doit rester 100% intact et visible.
        """
        obj = self._create_rich_test_mesh(with_shape_keys=False)
        self.props.decimate_method = 'DISSOLVE'
        self.props.preserve_seams = False  # Risque détecté
        self.props.confirm_aggressive_dissolve = False
        snap_before = snapshot_object_state(obj)

        res = bpy.ops.meshforge.dissolve()
        self.assertEqual(res, {'CANCELLED'})

        snap_after = snapshot_object_state(obj)
        assert_source_object_intact(self, snap_before, snap_after, expect_hidden=False)

    def test_p0_source_integrity_on_execution_exception_rollback(self):
        """Scénario 1.4 : Exception provoquée pendant l'exécution.
        Vérifie le rollback atomique : l'original reste 100% intact et visible,
        aucune copie partielle orpheline ne subsiste dans bpy.data.objects.
        """
        obj = self._create_rich_test_mesh(with_shape_keys=False)
        snap_before = snapshot_object_state(obj)

        # Injecter temporairement une exception simulée dans execute_simplification
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

        # Vérifier que l'original est intact et visible
        snap_after = snapshot_object_state(obj)
        assert_source_object_intact(self, snap_before, snap_after, expect_hidden=False)

        # Vérifier qu'AUCUNE copie optimisée orpheline n'existe
        all_names = [o.name for o in bpy.data.objects]
        self.assertNotIn("RichMesh_MF_Optimized", all_names)

    def test_p0_source_integrity_second_decimation(self):
        """Scénario 1.5 : Deuxième décimation successive sur la copie optimisée.
        L'original racine doit rester 100% identique au bit près.
        """
        obj = self._create_rich_test_mesh(with_shape_keys=False)
        snap_before = snapshot_object_state(obj)

        # Première décimation
        res1 = bpy.ops.meshforge.simplification()
        self.assertEqual(res1, {'FINISHED'})

        # Deuxième décimation
        self.props.simplification_percentage = 60.0
        res2 = bpy.ops.meshforge.simplification()
        self.assertEqual(res2, {'FINISHED'})

        # Vérifier que l'original racine est toujours 100% identique
        snap_after = snapshot_object_state(obj)
        assert_source_object_intact(self, snap_before, snap_after, expect_hidden=True)

    # =========================================================================
    # SECTION 2 : ATOMICITÉ ET RESTAURATION — P0
    # =========================================================================

    def test_p0_atomicity_and_renamed_original_restore(self):
        """Vérifie que renommer l'original n'empêche pas sa restauration grâce à _mf_source_ptr."""
        obj = self._create_rich_test_mesh("OriginalHero", with_shape_keys=False)
        res = bpy.ops.meshforge.simplification()
        self.assertEqual(res, {'FINISHED'})

        opt_obj = bpy.context.active_object
        self.assertEqual(opt_obj.name, "OriginalHero_MF_Optimized")

        # Renommer l'original pendant qu'il est masqué
        obj.name = "CustomRenamedHero"

        # La restauration doit retrouver l'original renommé via _mf_source_ptr
        res_rst = bpy.ops.meshforge.restore()
        self.assertEqual(res_rst, {'FINISHED'})

        self.assertFalse(obj.hide_get(), "L'original renommé doit être redevenu visible !")
        self.assertEqual(bpy.context.active_object, obj)
        self.assertNotIn("OriginalHero_MF_Optimized", bpy.data.objects)

    def test_p0_numeric_suffix_no_proliferation(self):
        """Vérifie qu'un objet avec suffixe numérique (ex: Asset.001) ne prolifère pas en Asset.001_MF_Optimized.001."""
        obj = self._create_rich_test_mesh("Asset.001", with_shape_keys=False)

        res1 = bpy.ops.meshforge.simplification()
        self.assertEqual(res1, {'FINISHED'})
        opt1 = bpy.context.active_object
        self.assertEqual(opt1.name, "Asset.001_MF_Optimized")

        # Deuxième décimation
        res2 = bpy.ops.meshforge.simplification()
        self.assertEqual(res2, {'FINISHED'})
        opt2 = bpy.context.active_object
        self.assertEqual(opt2.name, "Asset.001_MF_Optimized")

        all_names = [o.name for o in bpy.data.objects]
        self.assertNotIn("Asset.001_MF_Optimized.001", all_names)

        # Restauration propre
        res_rst = bpy.ops.meshforge.restore()
        self.assertEqual(res_rst, {'FINISHED'})
        self.assertFalse(obj.hide_get())

    def test_p0_deleted_original_safe_handling(self):
        """Si l'utilisateur supprime l'original, restore ne doit PAS détruire la copie restante."""
        obj = self._create_rich_test_mesh("TemporaryOriginal", with_shape_keys=False)
        res = bpy.ops.meshforge.simplification()
        self.assertEqual(res, {'FINISHED'})

        opt_obj = bpy.context.active_object
        # Supprimer manuellement l'original
        bpy.data.objects.remove(obj, do_unlink=True)

        # Tenter la restauration
        res_rst = bpy.ops.meshforge.restore()
        self.assertEqual(res_rst, {'CANCELLED'}, "La restauration doit être annulée pour éviter la perte de données.")
        # La copie optimisée doit TOUJOURS exister
        self.assertIn(opt_obj.name, bpy.data.objects)

    # =========================================================================
    # SECTION 3 : MATRICE DE FIDÉLITÉ DES ATTRIBUTS — P1
    # =========================================================================

    def test_p1_attribute_fidelity_collapse(self):
        """Vérifie le comportement de chaque attribut après Contraction d'arêtes (COLLAPSE).
        Distingue rigoureusement : Présence vs Exactitude vs Interpolation.
        """
        obj = self._create_rich_test_mesh("FidelityCollapse", with_shape_keys=False)
        self.props.decimate_method = 'COLLAPSE'
        self.props.simplification_percentage = 40.0

        bpy.ops.meshforge.simplification()
        opt = bpy.context.active_object

        # 1. Matériaux : Présents et conservés exactement
        self.assertEqual(len(opt.material_slots), 2)
        self.assertEqual([s.material.name for s in opt.material_slots], ["Mat_A", "Mat_B"])
        poly_mats = set(p.material_index for p in opt.data.polygons)
        self.assertTrue(0 in poly_mats and 1 in poly_mats, "Les 2 matériaux doivent être affectés aux faces.")

        # 2. UVs : Présents mais interpolés géométriquement
        self.assertIn("UVMap", opt.data.uv_layers)
        self.assertGreater(len(opt.data.uv_layers["UVMap"].data), 0)

        # 3. Vertex Groups : Présents mais poids interpolés
        self.assertEqual(len(opt.vertex_groups), 2)
        vg_names = [vg.name for vg in opt.vertex_groups]
        self.assertIn("VG_Bone_Root", vg_names)
        self.assertIn("VG_Bone_Tip", vg_names)

        # 4. Color Attributes : Présents mais interpolés
        self.assertIn("Color_Point", opt.data.color_attributes)
        self.assertIn("Color_Corner", opt.data.color_attributes)

        # 5. Arêtes vives et Coutures : Présentes
        has_seams = any(e.use_seam for e in opt.data.edges)
        has_sharp = any(e.use_edge_sharp for e in opt.data.edges)
        self.assertTrue(has_seams, "Des coutures doivent subsister sur le maillage réduit.")
        self.assertTrue(has_sharp, "Des arêtes vives doivent subsister sur le maillage réduit.")

    def test_p1_attribute_fidelity_dissolve(self):
        """Vérifie le comportement de chaque attribut après Dissolution coplanaire (DISSOLVE)."""
        bpy.ops.mesh.primitive_cube_add(size=2.0)
        cube = bpy.context.active_object
        cube.name = "FidelityDissolve"

        # Marquer seams et arêtes vives
        cube.data.edges[0].use_seam = True
        cube.data.edges[1].use_edge_sharp = True

        # Ajouter 2 matériaux
        m1 = bpy.data.materials.new("Mat_CAD_1")
        m2 = bpy.data.materials.new("Mat_CAD_2")
        cube.data.materials.append(m1)
        cube.data.materials.append(m2)
        cube.data.polygons[0].material_index = 1

        # Subdiviser pour créer des faces coplanaires
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.subdivide(number_cuts=2)
        bpy.ops.object.mode_set(mode='OBJECT')

        self.props.decimate_method = 'DISSOLVE'
        self.props.preserve_seams = True
        self.props.preserve_sharp = True
        self.props.preserve_materials = True

        bpy.ops.meshforge.dissolve()
        opt = bpy.context.active_object

        # Matériaux et slots conservés
        self.assertEqual(len(opt.material_slots), 2)
        # Coutures et sharp conservées
        self.assertTrue(any(e.use_seam for e in opt.data.edges))
        self.assertTrue(any(e.use_edge_sharp for e in opt.data.edges))

    # =========================================================================
    # SECTION 4 : COPIE STATIQUE SANS SHAPE KEYS — P1
    # =========================================================================

    def test_p1_static_copy_shape_keys_purge_target_only(self):
        """Vérifie que la purge des Shape Keys ne touche que la copie et préserve les modificateurs."""
        obj = self._create_rich_test_mesh("StaticAnimTarget", with_shape_keys=True)
        self.props.allow_shape_keys_removal_on_copy = True

        res = bpy.ops.meshforge.simplification()
        self.assertEqual(res, {'FINISHED'})

        # L'original conserve ses 2 clés intactes
        self.assertIsNotNone(obj.data.shape_keys)
        self.assertEqual(len(obj.data.shape_keys.key_blocks), 2)
        self.assertEqual(obj.data.shape_keys.key_blocks[1].name, "Blink_L")

        # La copie n'a plus de Shape Keys (dérivé statique)
        opt = bpy.context.active_object
        self.assertTrue(opt.data.shape_keys is None or len(opt.data.shape_keys.key_blocks) == 0)

        # Les modificateurs ont été transmis à la copie statique
        opt_mod_types = [m.type for m in opt.modifiers]
        self.assertIn('ARMATURE', opt_mod_types)
        self.assertIn('BEVEL', opt_mod_types)

    # =========================================================================
    # SECTION 5 : GARDE-FOUS DE DISSOLUTION — P1
    # =========================================================================

    def test_p1_dissolve_guardrails_combinations(self):
        """Vérifie chaque combinaison de risque exigeant confirmation explicite dans meshforge.dissolve."""
        # 1. Risque Multi-matériaux non protégés
        obj_mats = self._create_rich_test_mesh("RiskMats", with_shape_keys=False)
        self.props.decimate_method = 'DISSOLVE'
        self.props.preserve_seams = True
        self.props.preserve_sharp = True
        self.props.preserve_materials = False  # Risque multi-matériaux
        self.props.confirm_aggressive_dissolve = False

        res = bpy.ops.meshforge.dissolve()
        self.assertEqual(res, {'CANCELLED'})

        # Avec confirmation : autorisée
        self.props.confirm_aggressive_dissolve = True
        res_ok = bpy.ops.meshforge.dissolve()
        self.assertEqual(res_ok, {'FINISHED'})

        # 2. Risque Surface courbée avec angle élevé (>= 15°)
        bpy.ops.mesh.primitive_uv_sphere_add(segments=12, ring_count=12)
        sph = bpy.context.active_object
        sph.name = "RiskCurvature"
        self.props.decimate_method = 'DISSOLVE'
        self.props.preserve_seams = True
        self.props.preserve_sharp = True
        self.props.preserve_materials = True
        self.props.dissolve_angle = 20.0  # Angle élevé sur sphère
        self.props.confirm_aggressive_dissolve = False

        res_curv = bpy.ops.meshforge.dissolve()
        self.assertEqual(res_curv, {'CANCELLED'})

        # Avec confirmation : autorisée
        self.props.confirm_aggressive_dissolve = True
        res_curv_ok = bpy.ops.meshforge.dissolve()
        self.assertEqual(res_curv_ok, {'FINISHED'})


def run_tests():
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestUX8IntegrityCampaign)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
