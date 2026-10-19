# MeshForge for Blender

**MeshForge** est un add-on pour Blender (testé et validé sous Blender 5.2.2 LTS) conçu pour l'analyse, la réparation, le nettoyage géométrique et la simplification intelligente des maillages 3D.

Inspiré de l'ergonomie d'outils éprouvés tout en apportant une rigueur accrue, MeshForge garantit une approche **non-destructive par défaut**, une séparation nette des responsabilités, et des mesures objectives avant/après chaque opération.

---

## Fonctionnalités principales (Phase A)

1. **Architecture Non-Destructive :**
   - Par défaut, l'objet source reste intact et masqué.
   - Les optimisations sont appliquées sur un duplicata autonome nommé `[Nom]_MF_Optimized`.
   - Bouton de restauration en un clic pour revenir à l'objet original.

2. **Panneau unifié dans le 3D Viewport (N-Panel > MeshForge) :**
   - **Bouton principal « Optimiser le maillage » :** exécute la chaîne complète des étapes activées dans un ordre méthodique.
   - **Analyser seulement :** diagnostic en lecture seule comptant les sommets, arêtes, faces réelles et triangles estimés, ainsi que les défauts non-manifold et faces dégénérées.
   - **Filaire (Wireframe) :** inspection visuelle directe de la densité topologique.

3. **Sections fonctionnelles indépendantes :**
   - **Repair (Réparation) :** suppression des sommets/arêtes orphelins (Loose Geometry), fusion des doublons avec tolérance absolue ou relative à la bounding box, dissolution des faces d'aire nulle (Zero Faces), et nettoyage des arêtes redondantes (Dispensables).
   - **Manifold (Cohérence géométrique) :** modes Diagnostic, Prudent ou Agressif, suppression des arêtes filaires (Wire), bouchage contrôlé des trous (Fill Holes avec limite de côtés), et aplanissement (Make Planar / Flatten).
   - **Dissolve (Simplification coplanaire) :** dissolution limitée par seuil angulaire avec préservation stricte des arêtes vives (Sharp), coutures de texture (UV Seams), frontières de matériaux et contours ouverts.
   - **Topology (Topologie) :** mode par défaut « Conserver la topologie existante », options de triangulation contrôlée (Beauty / Clip / Shortest Diagonal) ou quadrangulation (Tris to Quads) avec préservation des attributs.
   - **Normals (Normales & Ombrage) :** recalcul d'orientation cohérente (Outside / Inside), lissage automatique par angle compatible Blender 5.x (`shade_smooth_by_angle`), normales pondérées (Weighted Normals) et réinitialisation des normales personnalisées.
   - **Object Data (Données d'objet) :** fusion des slots de matériaux dupliqués, suppression des slots inutilisés sans toucher aux ressources globales du fichier, et nettoyage des groupes de sommets vides.

4. **Rapport & Traçabilité :**
   - Comparatif en direct avant/après : sommets, arêtes, faces, triangles estimés, ratio de réduction.
   - Mesure de la durée totale et journalisation des événements sans risque de fermeture inopinée de Blender.

---

## Installation

### Installation manuelle (Développement)
1. Téléchargez ou clonez ce dossier dans le répertoire des add-ons de Blender :
   - Sous Windows : `%APPDATA%\Blender Foundation\Blender\5.2\scripts\addons\meshforge`
   - Ou créez une jonction symbolique pointant vers ce répertoire.
2. Démarrez Blender.
3. Allez dans `Édition > Préférences > Extensions / Add-ons`.
4. Recherchez « MeshForge » et activez la case à cocher.
5. Ouvrez le panneau latéral du 3D Viewport (`Touche N`), onglet **MeshForge**.

---

## Tests automatisés

Pour exécuter la suite de tests unitaires et d'intégration sans interface graphique :

```powershell
& "C:\Program Files (x86)\Steam\steamapps\common\Blender\blender.exe" --factory-startup --background --python tests/test_runner.py
```
