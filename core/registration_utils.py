"""MeshForge - Fonctions utilitaires d'enregistrement robuste des classes Blender.
Garantit l'idempotence, la tolérance aux classes non inscrites et la restauration
propre en cas d'échec partiel (Phase UX6 / BUG-02).
"""

from __future__ import annotations
import bpy
from typing import Iterable, Type, List


def is_class_registered(cls: Type) -> bool:
    """Vérifie de manière fiable si une classe Blender est actuellement enregistrée."""
    return getattr(cls, "is_registered", False) is True


def safe_unregister_class(cls: Type) -> bool:
    """Désenregistre une classe Blender de manière sûre et idempotente.
    Ne lève jamais d'exception si la classe est déjà désenregistrée ou absente.
    """
    if not is_class_registered(cls):
        return False

    try:
        bpy.utils.unregister_class(cls)
        return True
    except (RuntimeError, ValueError, AttributeError):
        return False


def safe_register_class(cls: Type) -> bool:
    """Enregistre une classe Blender en nettoyant toute version résiduelle préalable."""
    if is_class_registered(cls):
        safe_unregister_class(cls)

    bpy.utils.register_class(cls)
    return True


def register_classes_safely(classes: Iterable[Type]) -> List[Type]:
    """Enregistre une suite de classes avec garantie transactionnelle de rollback.
    En cas d'exception sur une classe, toutes les classes déjà enregistrées lors
    de cet appel sont proprement désenregistrées avant de propager l'erreur.
    """
    registered = []
    try:
        for cls in classes:
            safe_register_class(cls)
            registered.append(cls)
        return registered
    except Exception:
        for cls in reversed(registered):
            safe_unregister_class(cls)
        raise


def unregister_classes_safely(classes: Iterable[Type]) -> None:
    """Désenregistre dans l'ordre inverse une suite de classes sans lever d'exception."""
    for cls in reversed(list(classes)):
        safe_unregister_class(cls)
