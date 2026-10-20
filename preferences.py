"""MeshForge - Préférences globales de l'Add-on."""

from __future__ import annotations
import bpy
from bpy.props import BoolProperty, StringProperty

from .core.updater import (
    get_update_state,
    GITHUB_REPO,
    GITHUB_PAGE_URL,
    get_current_version_str
)


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

    check_updates_on_startup: BoolProperty(
        name="Vérifier les mises à jour au démarrage",
        description="Interroge silencieusement GitHub au lancement de Blender pour notifier les nouvelles versions",
        default=True
    )

    def draw(self, context):
        layout = self.layout

        # 1. Workflow & Duplication
        box = layout.box()
        box.label(text="Options de duplication et workflow :", icon='PREFERENCES')
        box.prop(self, "auto_switch_to_result")
        box.prop(self, "keep_original_collection")
        box.prop(self, "result_suffix")

        # 2. Système de Mises à jour & GitHub
        box_up = layout.box()
        row_title = box_up.row(align=True)
        row_title.label(text="Mises à jour MeshForge (GitHub)", icon='FILE_REFRESH')
        row_title.operator("meshforge.open_github", text="Voir sur GitHub", icon='URL')

        state = get_update_state()
        curr_ver = state.get("current_version") or get_current_version_str()
        latest_ver = state.get("latest_version") or curr_ver
        status = state.get("status", "IDLE")

        col = box_up.column(align=True)
        row_info = col.row()
        row_info.label(text=f"Dépôt officiel : {GITHUB_REPO}")
        row_info.label(text=f"Version installée : v{curr_ver}")

        row_status = col.row()
        if status == "CHECKING":
            row_status.label(text="Recherche de mise à jour en cours sur GitHub...", icon='TIME')
        elif status == "DOWNLOADING":
            prog = state.get("download_progress", 0)
            row_status.label(text=f"Téléchargement de la mise à jour ({prog} %)...", icon='IMPORT')
        elif status == "INSTALLED":
            row_status.label(text=f"Version {latest_ver} installée ! Redémarrez Blender.", icon='CHECKMARK')
        elif status == "UPDATE_AVAILABLE":
            row_status.label(text=f"Nouvelle version disponible : v{latest_ver}", icon='SOLO_ON')
        elif status == "UP_TO_DATE":
            row_status.label(text="MeshForge est à jour.", icon='CHECKMARK')
        elif status == "ERROR":
            err = state.get("error_message", "Erreur réseau")
            row_status.label(text=f"Statut : {err}", icon='ERROR')
        else:
            row_status.label(text="Statut : Non vérifié pour cette session", icon='INFO')

        last_str = state.get("last_check_str", "Jamais")
        col.label(text=f"Dernière vérification : {last_str}")

        row_actions = box_up.row(align=True)
        row_actions.operator("meshforge.check_update", text="Vérifier maintenant", icon='FILE_REFRESH')
        if state.get("has_update"):
            row_actions.operator("meshforge.install_update", text=f"Mettre à jour vers v{latest_ver}", icon='IMPORT')

        box_up.prop(self, "check_updates_on_startup")


from .core.registration_utils import safe_register_class, safe_unregister_class


def register_preferences():
    safe_register_class(MeshForgePreferences)


def unregister_preferences():
    safe_unregister_class(MeshForgePreferences)
