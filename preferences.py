"""MeshForge - Préférences globales de l'Add-on."""

from __future__ import annotations
import bpy
from bpy.props import BoolProperty, StringProperty


class MeshForgePreferences(bpy.types.AddonPreferences):
    bl_idname = __package__ or "meshforge"

    auto_switch_to_result: BoolProperty(
        name="Sélectionner automatiquement le résultat",
        description="Active et sélectionne le nouvel objet généré",
        default=True
    )
    keep_original_collection: BoolProperty(
        name="Garder dans la même collection",
        description="Place l'objet résultat dans les mêmes collections que l'original",
        default=True
    )
    result_suffix: StringProperty(
        name="Suffixe du résultat",
        description="Suffixe ajouté au nom de l'objet résultat",
        default="_MF_Optimized"
    )

    def draw(self, context):
        layout = self.layout
        box = layout.box()
        box.label(text="Options de duplication et workflow :", icon='PREFERENCES')
        box.prop(self, "auto_switch_to_result")
        box.prop(self, "keep_original_collection")
        box.prop(self, "result_suffix")


from .core.registration_utils import safe_register_class, safe_unregister_class


def register_preferences():
    safe_register_class(MeshForgePreferences)


def unregister_preferences():
    safe_unregister_class(MeshForgePreferences)
