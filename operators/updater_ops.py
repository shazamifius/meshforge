"""MeshForge - Opérateurs de mise à jour automatique."""

from __future__ import annotations
import bpy

from ..core.updater import (
    check_for_updates_async,
    check_for_updates_sync,
    install_update_sync,
    get_update_state,
    GITHUB_PAGE_URL
)


class MESHFORGE_OT_check_update(bpy.types.Operator):
    """Vérifie si une nouvelle version de MeshForge est disponible sur GitHub."""
    bl_idname = "meshforge.check_update"
    bl_label = "Vérifier les mises à jour"
    bl_options = {'REGISTER'}

    sync_check: bpy.props.BoolProperty(
        name="Vérification synchrone",
        description="Si True, bloque jusqu'à obtention du résultat (pour les tests)",
        default=False
    )

    def execute(self, context):
        if self.sync_check:
            res = check_for_updates_sync()
            if res.get("has_update"):
                self.report({'INFO'}, f"Mise à jour disponible : v{res.get('latest_version')} (actuelle: v{res.get('current_version')})")
            elif res.get("status") == "UP_TO_DATE":
                self.report({'INFO'}, f"MeshForge est à jour (v{res.get('current_version')}).")
            else:
                self.report({'WARNING'}, f"Vérification impossible : {res.get('error_message', 'Erreur réseau')}")
            return {'FINISHED'}

        self.report({'INFO'}, "Recherche de mise à jour MeshForge sur GitHub...")
        check_for_updates_async()
        return {'FINISHED'}


class MESHFORGE_OT_install_update(bpy.types.Operator):
    """Télécharge et installe la mise à jour disponible depuis GitHub."""
    bl_idname = "meshforge.install_update"
    bl_label = "Installer la mise à jour"
    bl_description = "Télécharge la dernière version depuis GitHub et met à jour l'add-on"
    bl_options = {'REGISTER'}

    confirm: bpy.props.BoolProperty(
        name="Confirmer",
        description="Confirmer l'installation",
        default=False
    )

    def invoke(self, context, event):
        state = get_update_state()
        if not state.get("has_update") and not state.get("download_url"):
            # Si pas encore vérifié, lancer une vérification synchrone d'abord
            res = check_for_updates_sync()
            if not res.get("has_update") and not res.get("download_url"):
                self.report({'INFO'}, "Aucune mise à jour plus récente n'a été trouvée sur GitHub.")
                return {'CANCELLED'}

        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        state = get_update_state()
        latest = state.get("latest_version", "suivante")
        self.report({'INFO'}, f"Téléchargement et installation de la mise à jour v{latest}...")

        success, msg = install_update_sync()
        if success:
            self.report({'INFO'}, msg)
            return {'FINISHED'}
        else:
            self.report({'ERROR'}, msg)
            return {'CANCELLED'}


class MESHFORGE_OT_open_github(bpy.types.Operator):
    """Ouvre le dépôt officiel MeshForge sur GitHub."""
    bl_idname = "meshforge.open_github"
    bl_label = "Ouvrir GitHub"
    bl_description = "Ouvre la page GitHub du projet MeshForge dans le navigateur"
    bl_options = {'REGISTER'}

    url: bpy.props.StringProperty(
        name="URL",
        default=GITHUB_PAGE_URL
    )

    def execute(self, context):
        target_url = self.url or GITHUB_PAGE_URL
        bpy.ops.wm.url_open(url=target_url)
        return {'FINISHED'}
