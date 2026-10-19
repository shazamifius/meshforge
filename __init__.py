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
    "doc_url": "",
    "category": "Mesh",
}

from .preferences import register_preferences, unregister_preferences
from .properties import register_properties, unregister_properties
from .operators import register_operators, unregister_operators
from .ui import register_ui, unregister_ui


def register():
    register_preferences()
    register_properties()
    register_operators()
    register_ui()


def unregister():
    unregister_ui()
    unregister_operators()
    unregister_properties()
    unregister_preferences()


if __name__ == "__main__":
    register()
