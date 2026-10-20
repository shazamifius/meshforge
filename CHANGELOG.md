# Journal des modifications (Changelog) - MeshForge

Toutes les modifications notables de ce projet seront consignées dans ce document.

## [Unreleased] - Mises à jour autonomes GitHub et diagnostic de haute précision

### Ajouté
- Système complet de mise à jour automatique depuis GitHub (`core/updater.py`, `operators/updater_ops.py`) lié au dépôt officiel `shazamifius/meshforge`.
- Détection asynchrone et non-bloquante des nouvelles versions sur GitHub Releases et tags.
- Téléchargement, validation d'archive et mise à jour en un clic directement depuis les Préférences Blender ou le panneau N-Panel.
- Notification visuelle et badge d'alerte en cas de version disponible dans la vue 3D.
- Granularité stricte du marquage intentionnel (`base_id:item_id`), partition des composantes connexes et validation par métrologie spatiale.
- Dissociation entre géométrie intentionnelle et conformité aux objectifs stricts (ex. `EXPORT_PREP`).
- Suite de tests unitaires dédiés (`tests/test_updater.py`, `tests/test_granular_and_cache_coherence.py`).

## [0.2.0] - Phase B : Sécurité, diagnostics renforcés et traçabilité

### Ajouté
- Diagnostic préalable enrichi (`core/mesh_stats.py`) : détection des composantes connexes disjointes (islands), comptage des ouvertures/trous (`boundary_loops`), détection non destructive des doublons géométriques via KDTree, évaluation des risques pour surfaces ouvertes et maillages non-manifold.
- Module de rapport et d'exportation (`core/report.py`) : formats JSON et texte, distinction explicite entre les problèmes détectés et les problèmes résolus, enregistrement des paramètres appliqués et des chronométrages par phase.
- Opérateur d'exportation de rapport (`operators/report_export.py`) et boutons d'export intégrés à l'interface (`ui/panel.py`).
- Mécanisme de rollback garanti en cas d'erreur dans le pipeline (`core/pipeline.py`) : suppression immédiate de l'objet dupliqué échoué, réactivation de l'original, et restauration par sauvegarde mémoire en mode destructif.
- Optimisation des performances du nettoyage de matériaux (`core/object_data.py`) via l'opérateur C natif `material_slot_remove_unused()`.
- Suite de tests Phase B (`tests/test_phase_b.py`) couvrant surfaces ouvertes/tissus, objets watertight, topologie tris vs quads, îlots disjoints, préservation des attributs (UV, matériaux, VGs, Sharp), résistance aux erreurs et benchmark de scalabilité sur 1,587 million de triangles.

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
