"""MeshForge - Add-on Blender d’analyse, de réparation, de nettoyage et de simplification intelligente des maillages.
Cible : Blender 5.x LTS.
"""

bl_info = {
    "name": "MeshForge",
    "author": "MeshForge Project",
    "version": (0, 1, 0),
    "blender": (4, 2, 0),  # Compatible Blender 4.2+ et Blender 5.x LTS
    "location": "View3D > Sidebar (N) > MeshForge",
    "description": "Analyse, réparation, nettoyage et simplification intelligente des maillages",
    "warning": "",
    "doc_url": "https://github.com/shazamifius/meshforge",
    "category": "Mesh",
}

from .preferences import register_preferences, unregister_preferences
from .properties import register_properties, unregister_properties
from .operators import register_operators, unregister_operators
from .ui import register_ui, unregister_ui


def _check_updates_delayed():
    try:
        import bpy
        from .core.updater import check_for_updates_async
        prefs = bpy.context.preferences.addons.get(__package__ or "meshforge")
        if prefs and getattr(prefs.preferences, "check_updates_on_startup", True):
            check_for_updates_async()
    except Exception:
        pass
    return None


def register():
    registered_modules = []
    try:
        register_preferences()
        registered_modules.append(unregister_preferences)

        register_properties()
        registered_modules.append(unregister_properties)

        register_operators()
        registered_modules.append(unregister_operators)

        register_ui()
        registered_modules.append(unregister_ui)

        # Lancement différé et silencieux de la vérification de mise à jour au démarrage
        try:
            import bpy
            if hasattr(bpy.app, "timers") and not getattr(bpy.app, "background", False):
                bpy.app.timers.register(_check_updates_delayed, first_interval=3.0)
        except Exception:
            pass
    except Exception:
        # Rollback automatique ordonné en cas d'échec partiel
        for rollback_fn in reversed(registered_modules):
            try:
                rollback_fn()
            except Exception:
                pass
        raise


def unregister():
    for unreg_fn in (unregister_ui, unregister_operators, unregister_properties, unregister_preferences):
        try:
            unreg_fn()
        except Exception:
            pass


if __name__ == "__main__":
    register()
