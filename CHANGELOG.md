# Journal des modifications (Changelog) - MeshForge

Toutes les modifications notables de ce projet seront consignées dans ce document.

## [0.1.0] - Phase A : Prototype d'interface et d'exécution modulaire

### Ajouté
- Structure de code modulaire (`core/`, `ui/`, `operators/`, `tests/`).
- Module de métriques et statistiques précises (`core/mesh_stats.py`) distinguant polygones réels et triangles estimés.
- Pipeline d'orchestration non-destructif (`core/pipeline.py`) avec duplication de l'objet et du maillage source.
- Section **Repair** (`core/repair_pipeline.py`) : suppression de loose geometry, fusion de doubles (absolue/relative), dissolution des faces dégénérées, dispensables.
- Section **Manifold** (`core/manifold.py`) : modes Diagnostic, Prudent, Agressif, suppression filaire (wire), remplissage contrôlé de trous, aplanissement.
- Section **Dissolve** (`core/dissolve.py`) : dissolution coplanaire paramétrable avec respect strict des UV, coutures, arêtes vives, matériaux et frontières.
- Section **Topology** (`core/topology.py`) : mode `KEEP` par défaut (préservation stricte), conversions `TRIS` et `QUADS`.
- Section **Normals** (`core/normals.py`) : recalcul des normales, compatibilité native Blender 5.x (`shade_smooth_by_angle`), normales pondérées.
- Section **Object Data** (`core/object_data.py`) : nettoyage des slots matériaux dupliqués/inutilisés et suppression des groupes de sommets vides.
- Interface complète 3D Viewport Sidebar (`ui/panel.py`) avec panneau principal, sous-panneaux pliables et tableau de bord de statistiques en direct.
- Opérateurs d'action globale, d'analyse en lecture seule, de bascule filaire et de restauration de l'original.
- Préférences d'add-on (`preferences.py`) et propriétés personnalisées (`properties.py`).
- Suite de tests headless automatisés pour Blender 5.2.2 LTS.
