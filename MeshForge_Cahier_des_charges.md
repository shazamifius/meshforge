# Cahier des charges — MeshForge for Blender
## Add-on d’analyse, de réparation, de nettoyage et de simplification intelligente des maillages

- **Statut :** spécification initiale destinée à un agent IA de développement
- **Langue de travail :** français pour la documentation et les échanges ; noms techniques en anglais acceptés dans le code
- **Cible :** Blender, version exacte à confirmer au démarrage du projet
- **Matériel de référence :** ASUS ROG Zephyrus G16 GU605CP, Intel Core Ultra 9 285H, 32 Go RAM, NVIDIA RTX 5070 Laptop 8 Go VRAM
- **Cas de test initial :** maillage d’environ 1 587 000 triangles
- **Usage :** objets 3D génériques, notamment assets de jeu, objets durs, surfaces organiques, tissus et matelas simulés
- **Formats de topologie :** triangles en priorité dans l’usage habituel ; quads possibles. L’outil doit préserver ou produire les deux selon le choix de l’utilisateur.

---

## 1. Mission et résultat attendu

Créer un add-on Blender qui regroupe, dans une interface claire, des opérations comparables à celles d’Instant Clean, puis ajoute un moteur de simplification géométrique plus contrôlé que le simple Dissolve.

L’utilisateur apprécie le principe d’Instant Clean : des opérations Blender connues, réunies dans un panneau unique, exécutables avec un bouton principal. L’add-on doit reprendre cette ergonomie générale et la rendre plus sûre, explicite et extensible.

Le projet ne doit **pas** être spécialisé dans le tissu. Il doit convenir à une variété d’assets : maillages triangulés, quad meshes, objets organiques, surfaces planes, objets mécaniques, assets issus de scans ou de simulations, maillages avec matériaux/UV, géométries ouvertes ou fermées.

### Objectif central

Réduire les données géométriques et améliorer la qualité topologique tout en maîtrisant la perte de forme et de détails. L’outil ne doit jamais promettre une préservation parfaite. Il doit mesurer les compromis, signaler les opérations risquées et conserver l’original par défaut.

### Principes non négociables

1. **Non-destructif par défaut :** l’original reste intact. Le résultat est créé dans un nouvel objet ou via une option explicitement choisie.
2. **Preuve avant affirmation :** chaque moteur doit être testé et comparé à une référence.
3. **Pas d’IA décorative :** ne pas ajouter de modèle d’IA simplement parce que le projet se dit « intelligent ». Les algorithmes géométriques déterministes constituent la base.
4. **Sélection explicable :** lorsqu’un mode automatique choisit une stratégie, l’interface indique pourquoi.
5. **Pas de seuil d’angle unique :** l’angle est un signal parmi plusieurs, jamais la seule mesure de qualité.
6. **Pas de destruction silencieuse des attributs :** UV, matériaux, attributs, groupes de sommets et données utiles doivent être conservés ou leur perte explicitement annoncée.
7. **Annulation et récupération :** prévoir une annulation utilisateur, une gestion d’erreur et un journal du traitement.
8. **Aucune promesse de performance sans benchmark.**
9. **Implémentation progressive :** ne pas produire tout le projet en un seul bloc opaque. Chaque phase doit compiler, fonctionner et être testée avant la suivante.
10. **Compatibilité vérifiée :** inspecter l’API de la version exacte de Blender avant d’écrire le code. Ne pas inventer de noms d’opérateurs, propriétés ou fonctions API.

---

## 2. Expérience utilisateur et interface

Créer un panneau dans le 3D Viewport, catégorie dédiée, nom provisoire **MeshForge**. Le nom est provisoire et peut être modifié sans affecter l’architecture.

### 2.1 Bouton principal

Un bouton principal **Optimiser le maillage** lance la chaîne d’opérations activées. Il doit être clairement indiqué que les opérations cochées seront exécutées dans l’ordre affiché.

À côté ou en dessous :
- bouton **Analyser seulement** ;
- bouton **Prévisualiser / Comparer** si techniquement réalisable ;
- bouton **Restaurer / Supprimer le résultat** lorsque le résultat est séparé ;
- bouton **Paramètres avancés** repliable.

L’interface doit rester lisible et éviter de montrer trop d’options aux débutants, sans retirer le contrôle aux utilisateurs avancés.

### 2.2 Ordre d’exécution

Ordre initial recommandé, configurable :
1. Diagnostic initial.
2. Réparation prudente.
3. Nettoyage.
4. Dissolve / simplification des régions planes.
5. Réduction adaptative.
6. Reconstruction de topologie optionnelle.
7. Recalcul/gestion des normales.
8. Nettoyage des données d’objet.
9. Validation et rapport.

Ne pas exécuter une étape désactivée. Ne pas supposer que toutes les étapes conviennent à chaque mesh. Chaque étape doit déclarer ses préconditions, ses effets et ses risques.

### 2.3 Préservation de l’original

Comportement par défaut : produire un nouvel objet nommé par exemple `Original_MF_Optimized`, conserver le maillage source et placer le résultat dans la même collection ou dans une collection de résultats configurable.

Options :
- `Créer un nouvel objet` (par défaut activé).
- `Dupliquer le mesh avant traitement`.
- `Traiter l’objet directement` (mode destructif, confirmation obligatoire).
- `Conserver le mesh original masqué` (facultatif).
- `Remplacer l’objet sélectionné après validation` (facultatif, confirmation obligatoire).

Ne jamais supprimer automatiquement l’objet source ou ses données.

---

## 3. Reproduction fonctionnelle des catégories d’Instant Clean

Recréer une interface équivalente sur le plan fonctionnel, en réutilisant les opérateurs natifs Blender lorsque c’est raisonnable. Le but est de reproduire les fonctionnalités observables, pas de copier le code source, les ressources, les icônes propriétaires ou l’implémentation interne d’Instant Clean.

Les libellés ci-dessous sont ceux à exposer dans l’interface. Les noms exacts des opérateurs Blender doivent être vérifiés dans la version ciblée.

### 3.1 Repair

Options activables indépendamment :

- **Loose Geometry** : retirer les sommets, arêtes ou éléments isolés ne contribuant à aucune surface utile. Modes séparés si possible : sommets isolés, arêtes isolées, îlots isolés.
- **Doubles** : fusionner les sommets superposés ou suffisamment proches selon une tolérance configurable en unités Blender. Valeur de départ indicative : 0,0001 m, mais la valeur doit être interprétée avec prudence selon l’échelle de l’objet. Proposer une option relative à la taille de l’objet.
- **Zero Faces** : détecter et retirer les faces dégénérées ou d’aire quasi nulle selon une tolérance configurable.
- **Dispensables** : simplifier les arêtes/faces redondantes sans perdre les caractéristiques au-delà d’une tolérance définie. Ne pas assimiler ce terme à un simple dissolve d’angle fixe.

Bouton de section : **Réparer**. Le bouton principal global peut exécuter cette section si elle est activée.

#### Sécurité pour les doublons

- Afficher le seuil en unités Blender.
- Proposer `Absolu` ou `Relatif à la bounding box`.
- Ne jamais choisir une tolérance très grande par défaut.
- Compter et rapporter le nombre d’éléments supprimés/fusionnés.

### 3.2 Manifold

Options activables indépendamment :

- **Fill Holes** : remplir les ouvertures détectées, avec limite de nombre de côtés.
- **Max Sides** : nombre maximal de côtés pour les trous remplis.
- **Remove Non-Manifold Faces** : supprimer les faces problématiques uniquement si le mode choisi le demande ; l’action est risquée et doit être décrite.
- **Remove Non-Manifold Vertices** : traiter les sommets non-manifold selon une stratégie explicite.
- **Remove Wire Geometry** : retirer les éléments filaires sans surface.
- **Make Planar / Undistort Faces** : réduire la distorsion de faces qui devraient être planes, sous une tolérance.
- **Flatten Faces** : aplanir les régions ciblées avec intensité configurable.
- **Flatten Iterations** : nombre d’itérations.

Important : « rendre manifold » et « supprimer les éléments non-manifold » ne sont pas équivalents. Une suppression peut créer des trous ou détruire des parties utiles. Fournir au moins deux modes :
- `Diagnostic seulement` ;
- `Correction prudente` ;
- `Suppression agressive` (désactivée par défaut, avertissement explicite).

Le remplissage de trous n’est pas toujours souhaitable pour un mesh volontairement ouvert, une feuille de tissu ou une surface sans épaisseur. Ne pas remplir automatiquement sans option activée.

### 3.3 Dissolve

Options :
- activer/désactiver la simplification de régions coplanaires ;
- angle maximal configurable ;
- conserver les arêtes marquées Sharp ;
- préserver les coutures UV et les frontières de matériaux si demandé ;
- préserver les arêtes de frontière ;
- préserver les arêtes marquées comme caractéristiques ;
- mode prudent / équilibré / agressif ;
- estimation du nombre de faces supprimées avant exécution si faisable.

Ne pas traiter l’angle comme une mesure suffisante. Un faible angle peut être important pour une silhouette ou un pli long ; un angle élevé peut être insignifiant sur un minuscule détail. Le dissolve doit être suivi d’une validation si la préservation de forme est activée.

### 3.4 Topology

Options :
- **Convert to Tris** : triangulation optionnelle.
- **Quad remesh / conversion en quads** : option seulement si une méthode adaptée est réellement intégrée et testée.
- Méthode de triangulation si plusieurs options existent.
- Méthode de reconstruction de quads si plusieurs options existent.
- Préserver les UV, matériaux et attributs quand la méthode le permet.
- Afficher clairement que le remeshing peut modifier la topologie, les coutures, les détails ou le volume.

Le mode de topologie par défaut doit être **Conserver la topologie existante**, donc ni triangulation ni conversion en quads automatiques.

L’utilisateur travaille le plus souvent avec une topologie triangulée, mais utilise aussi des quads. L’addon doit donc gérer les deux sans supposer que l’un est toujours préférable.

Ne pas appeler « quad remesh » une simple conversion de triangles en quads par regroupement local si elle ne produit pas une topologie de qualité. Distinguer :
- conversion locale en quads ;
- quadrangulation/remeshing guidé ;
- conservation du mesh d’origine.

### 3.5 Normals

Options :
- **Recalculate** : recalculer l’orientation des normales lorsque pertinent.
- Direction `Outside` / `Inside` lorsque l’opération le permet.
- **Auto Smooth / angle de lissage** : implémentation conforme à l’API de la version Blender cible ; ne pas supposer que l’ancien mécanisme existe encore.
- **Weighted Normals** : option si compatible avec la version cible et le type de mesh.
- **Clear Custom Split Normals**.
- **Clear Sharp Edges**.

Attention : recalculer les normales vers l’extérieur n’est pas correct pour toutes les géométries, notamment les surfaces ouvertes ou les éléments à faces orientées volontairement. Les options qui modifient les données de normales doivent être indépendantes et documentées.

### 3.6 Object Data

Options :
- **Material Doubles** : fusionner les slots de matériaux identiques ou réellement équivalents sans changer le rendu.
- **Material Slots** : retirer les slots inutilisés ou nettoyer les références vides selon un mode choisi.
- **Vertex Groups** : supprimer les groupes vides en option.
- nettoyage optionnel d’autres données inutilisées, uniquement si l’opération est sûre et précisément définie.

Ne jamais supprimer globalement des matériaux, images, actions ou datablocks du fichier Blender sans action explicite. Nettoyer les slots d’un objet n’est pas la même chose que supprimer les ressources partagées du fichier.

### 3.7 Résultat du bouton global

Le bouton principal doit respecter toutes les cases cochées, les seuils et l’ordre affiché. Chaque section doit aussi pouvoir être exécutée individuellement si cela simplifie le débogage.

Les paramètres doivent être conservés entre les sessions selon les pratiques habituelles des préférences d’add-on Blender, si compatible avec la version cible.

---

## 4. Nouveau moteur : simplification intelligente de maillage

Cette partie constitue la valeur ajoutée par rapport à un simple regroupement d’opérateurs natifs.

### 4.1 Modes de simplification

Prévoir trois modes utilisateurs :

1. **Prudent** : préserver au maximum les détails ; réduction modérée.
2. **Équilibré** : compromis entre réduction et erreur.
3. **Agressif** : réduction plus forte, avec risque accru d’altération.
4. **Contrôle personnalisé** : l’utilisateur définit un budget de faces/triangles ou une tolérance maximale.

Ces profils sont des préréglages, pas des promesses. Leur effet réel doit être testé.

### 4.2 Budget de sortie

L’utilisateur doit pouvoir choisir :
- nombre maximal de triangles ;
- ratio cible (par exemple 75 %, 50 %, 25 %, 10 % du nombre initial) ;
- tolérance maximale d’erreur ;
- ou mode `Qualité d’abord`, où le moteur s’arrête lorsqu’aucune opération supplémentaire n’est acceptée par les critères de qualité.

Préciser si le compteur affiché correspond aux faces polygonales ou aux triangles de rendu. Pour les quads et les n-gons, afficher les deux :
- `Faces Blender` ;
- `Triangles estimés pour triangulation`.

Ne pas prétendre qu’un mesh de 10 000 quads a exactement 10 000 triangles.

### 4.3 Algorithme de base

Évaluer un algorithme de simplification par contraction d’arêtes basé sur **Quadric Error Metrics (QEM)** ou une implémentation éprouvée équivalente.

Le moteur doit :
- calculer les coûts des contractions candidates ;
- sélectionner les opérations les moins coûteuses ;
- actualiser les coûts affectés par chaque contraction ;
- préserver les frontières et caractéristiques configurées ;
- rejeter les contractions qui produisent des faces dégénérées, des retournements de triangles, des intersections évidentes ou des défauts topologiques interdits ;
- s’arrêter au budget ou à la tolérance définie ;
- enregistrer le motif d’arrêt.

Ne pas réécrire QEM de zéro si une bibliothèque adaptée, compatible avec la licence du projet et la version cible de Blender, satisfait les exigences. Faire un audit des dépendances avant intégration.

### 4.4 Métrique d’erreur enrichie

La version avancée peut enrichir le coût géométrique de base avec :
- distance de surface ;
- déviation de normale ;
- courbure locale ;
- conservation de frontières et de caractéristiques ;
- silhouette approximée depuis plusieurs directions ;
- protection des coutures UV, frontières de matériaux et arêtes marquées ;
- importance locale configurable par l’utilisateur.

Exemple conceptuel :

`cost = w_position * E_position + w_normal * E_normal + w_curvature * E_curvature + w_feature * E_feature + w_boundary * E_boundary`

Cette formule est une architecture conceptuelle, pas une formule directement exploitable sans définition mathématique des termes, unités et normalisations. L’agent doit définir chacun des termes, leurs bornes, leurs coûts de calcul et les tests correspondants.

Ne pas activer toutes les contraintes au prix d’une explosion du temps de calcul. Prévoir des profils de validation et mesurer leur coût.

### 4.5 Analyse multi-échelle

Étudier la géométrie à plusieurs échelles pour distinguer :
- grandes formes ;
- plis ou détails intermédiaires ;
- petits détails locaux.

Une méthode possible est d’analyser les écarts à des surfaces lissées, les normales et les estimations de courbure à différents rayons. Ce n’est pas une classification parfaite : un petit détail peut être essentiel et une grande déformation peut être secondaire. Les résultats doivent guider les coûts, jamais décider seuls.

### 4.6 Validation de surface

Conserver la référence originale et comparer le résultat avec des mesures telles que :
- distance de surface bidirectionnelle, par exemple avec des échantillons de surface et un BVH ;
- erreur maximale ou percentile élevé, pas seulement moyenne ;
- déviation des normales ;
- variation de silhouette depuis un ensemble configurable de directions ;
- changement de volume si le mesh est fermé et que ce calcul est valide ;
- détection de composantes perdues ;
- détection des changements topologiques non souhaités.

La distance de Hausdorff exacte peut être coûteuse. Une approximation par échantillonnage doit être décrite comme telle, et sa qualité doit être évaluée.

La validation doit comparer les résultats à la géométrie originale, et non uniquement vérifier que le mesh final est techniquement valide.

---

## 5. Rôle de l’IA : limites et opportunités

Ne pas entraîner ou embarquer un modèle d’IA lors de la première version.

Les résultats doivent d’abord être obtenus par des algorithmes géométriques reproductibles et testables. Une éventuelle version future peut utiliser un modèle pour recommander des paramètres ou estimer l’importance perceptuelle de régions, à condition de démontrer un gain mesuré sur un corpus d’assets diversifiés.

L’IA ne doit pas :
- inventer de géométrie sans contrôle ;
- écraser le maillage original ;
- choisir des seuils opaques sans les afficher ;
- remplacer les tests de validation ;
- annoncer une « fidélité parfaite ».

Toute fonctionnalité d’IA future doit être facultative, explicable autant que possible et fonctionner sans connexion externe si l’architecture le permet.

---

## 6. Architecture logicielle recommandée

L’agent doit proposer une structure de fichiers concise, puis la justifier. Structure initiale possible :

```text
meshforge/
├── __init__.py
├── preferences.py
├── properties.py
├── ui/
│   ├── __init__.py
│   └── panel.py
├── operators/
│   ├── __init__.py
│   ├── analyze.py
│   ├── optimize.py
│   ├── repair.py
│   └── validate.py
├── core/
│   ├── __init__.py
│   ├── mesh_stats.py
│   ├── repair_pipeline.py
│   ├── dissolve.py
│   ├── simplification.py
│   ├── topology.py
│   ├── normals.py
│   ├── object_data.py
│   └── validation.py
├── native/                 # uniquement si un module natif est justifié
├── tests/
│   ├── test_repair.py
│   ├── test_simplification.py
│   ├── test_attributes.py
│   └── test_validation.py
├── README.md
├── CHANGELOG.md
└── LICENSES.md
```

Cette arborescence est indicative. Ne pas créer artificiellement un fichier par fonction minuscule. Garder une architecture maintenable et adaptée à la taille réelle du projet.

### 6.1 Couche Blender

Responsable de :
- l’interface ;
- la lecture des paramètres ;
- la duplication des objets ;
- la création du résultat ;
- la coordination des opérateurs ;
- la gestion des rapports et erreurs.

Ne pas mélanger la logique d’interface avec le cœur des algorithmes géométriques.

### 6.2 Cœur géométrique

Responsable de :
- l’analyse de topologie ;
- les algorithmes de simplification ;
- la validation ;
- la conservation des attributs ;
- les statistiques.

Si les opérations natives Blender sont suffisantes pour une fonctionnalité, les utiliser plutôt que de réimplémenter inutilement le même comportement.

### 6.3 Module natif facultatif

Le C++ est envisagé pour les parties où les benchmarks démontrent un problème de performance. L’agent doit d’abord mesurer les coûts du prototype Python/BMesh et des opérateurs Blender. Ne pas introduire une compilation complexe avant d’avoir prouvé sa nécessité.

Si un module natif est requis, documenter :
- compilateurs et versions supportés ;
- processus de compilation ;
- compatibilité Windows/Linux ;
- compatibilité avec les versions Blender ciblées ;
- licence de chaque dépendance ;
- méthode de test et solution de repli si le module n’est pas disponible.

---

## 7. Performance et mémoire

### Matériel de référence

- CPU : Intel Core Ultra 9 285H, 16 cœurs logiques indiqués par le système ;
- RAM : 32 Go ;
- GPU : NVIDIA RTX 5070 Laptop, 8 Go VRAM ;
- GPU intégré : Intel Arc 140T ;
- cas initial : environ 1 587 000 triangles.

Ne pas supposer que le GPU doit exécuter tous les calculs. De nombreux algorithmes topologiques utilisent des structures irrégulières et des dépendances qui se prêtent mieux au CPU. Une accélération GPU ne doit être ajoutée que si elle est techniquement appropriée et mesurée.

### Exigences

- éviter les copies de maillage inutiles ;
- surveiller les pics mémoire ;
- afficher la progression lorsque l’opération peut être découpée en étapes ;
- fournir une annulation sûre lorsque l’algorithme le permet ;
- ne jamais figer l’interface plus longtemps que nécessaire sans retour utilisateur ;
- prévoir des tests sur des tailles croissantes ;
- enregistrer les durées par phase.

Le temps de 10 minutes est un budget souhaité pour certains traitements, pas une garantie. La première version doit établir des benchmarks reproductibles sur le mesh de référence.

---

## 8. Rapport et interface de comparaison

Après traitement, afficher au minimum :

- nom de l’objet ;
- nombre de sommets, arêtes, faces et triangles estimés avant/après ;
- réduction en pourcentage ;
- durée totale et durée par phase ;
- erreurs ou avertissements détectés ;
- validation réussie, partielle ou échouée ;
- paramètres et stratégie utilisés ;
- raison de l’arrêt ;
- état de conservation des UV, matériaux et attributs.

Prévoir une comparaison visuelle :
- original / résultat ;
- affichage filaire ;
- possibilité de revenir à l’objet original ;
- comparaison de l’erreur sur une carte de couleurs si techniquement réalisable.

Les résultats de validation doivent rester accessibles après le traitement, idéalement exportables dans un rapport texte ou JSON.

---

## 9. Tests obligatoires

Créer des maillages synthétiques et utiliser des fichiers de test autorisés pour vérifier les cas suivants :

1. Cube triangulé.
2. Cube en quads.
3. Surface plane dense.
4. Sphère dense.
5. Surface organique avec plis.
6. Maillage ouvert.
7. Maillage fermé et manifold.
8. Maillage non-manifold.
9. Sommets doublons.
10. Faces dégénérées.
11. Plusieurs composantes disjointes.
12. UV et plusieurs matériaux.
13. Groupes de sommets.
14. Maillage avec arêtes Sharp ou normales personnalisées, selon l’API ciblée.
15. Objet à environ 1,587 million de triangles.
16. Objet pour lequel la simplification doit s’arrêter tôt, car toute réduction supplémentaire dépasserait la tolérance.

Pour chaque test, vérifier :
- absence de crash ;
- respect du mode non destructif ;
- validité des résultats ;
- préservation des attributs exigés ;
- statistiques exactes ou clairement étiquetées comme estimées ;
- respect des budgets et tolérances ;
- reproductibilité avec les mêmes paramètres.

Les tests de performance ne doivent pas être présentés comme réussis sans exécution effective.

---

## 10. Critères d’acceptation par phase

### Phase A — Prototype d’interface

Accepté lorsque :
- l’add-on s’installe et s’active dans la version Blender cible ;
- les sections Repair, Manifold, Dissolve, Topology, Normals et Object Data existent ;
- les options activées et désactivées sont respectées ;
- le bouton global exécute les opérations dans l’ordre défini ;
- les erreurs sont affichées sans fermer Blender.

### Phase B — Sécurité et diagnostics

Accepté lorsque :
- le traitement non destructif fonctionne ;
- l’analyse initiale rapporte les caractéristiques du mesh ;
- les cas risqués sont détectés ;
- les résultats et paramètres sont consignés ;
- les tests automatisés passent.

### Phase C — Simplification adaptative

Accepté lorsque :
- un moteur de simplification réel est intégré ;
- l’utilisateur peut définir un budget ou une tolérance ;
- les triangles et faces sont comptés distinctement ;
- la validation compare le résultat à l’original ;
- les résultats sont comparés à une ou plusieurs références sur les mêmes modèles.

### Phase D — Optimisation avancée

Accepté lorsque :
- les métriques avancées sont documentées ;
- le système protège les caractéristiques configurées ;
- les performances sont mesurées ;
- les régressions de qualité sont couvertes par des tests ;
- les dépendances et leur licence sont documentées.

Aucune phase ne doit être déclarée terminée sur la seule base d’une inspection visuelle du code ou d’un message de l’agent.

---

## 11. Instructions de travail destinées à l’agent IA

L’agent doit respecter les consignes suivantes :

1. Commencer par examiner le dépôt existant, s’il y en a un, ainsi que la version de Blender ciblée.
2. Ne pas remplacer ou supprimer des fichiers sans comprendre leur rôle.
3. Présenter un plan de travail bref et les risques techniques avant la première modification.
4. Implémenter une phase à la fois.
5. Après chaque phase, exécuter les tests disponibles et donner les résultats réels.
6. Ne jamais prétendre qu’un test a réussi s’il n’a pas été exécuté.
7. Ne jamais inventer une API Blender. Vérifier la documentation correspondant à la version ciblée.
8. Séparer les opérations de réparation, de topologie, de simplification et de validation.
9. Expliquer toute dépendance ajoutée, sa licence et son intérêt.
10. Éviter les abstractions prématurées, les architectures surdimensionnées et les dépendances inutiles.
11. Maintenir un `README.md`, un `CHANGELOG.md` et des instructions d’installation.
12. Signaler les compromis, limites et cas non pris en charge.
13. Ne pas ajouter d’IA tant qu’un gain démontrable n’est pas identifié.
14. En cas de doute sur une opération destructive, préférer l’analyse et l’avertissement à la modification silencieuse.
15. À chaque étape, fournir : fichiers modifiés, résumé technique, commandes de test, résultats observés et problèmes restants.

### Questions que l’agent doit résoudre avant l’implémentation

- Quelle version exacte de Blender est ciblée ?
- Quelles opérations sont déjà disponibles dans l’API de cette version ?
- Quelle bibliothèque de simplification est compatible avec la licence du projet ?
- Quels attributs sont préservés par chaque opération ?
- Le premier prototype peut-il rester entièrement en Python et utiliser les opérateurs Blender ?
- À partir de quels benchmarks un module natif devient-il justifié ?
- Quelle stratégie de validation fournit un bon compromis entre fiabilité et temps de calcul ?

Ne pas bloquer toute progression pour une question secondaire. Faire des choix prudents, documenter les hypothèses et demander confirmation uniquement lorsqu’une décision modifie substantiellement le comportement ou la compatibilité du projet.

---

## 12. Ce que la première version ne doit pas faire

- Ne pas prétendre battre tous les outils existants sur tous les maillages.
- Ne pas promettre zéro perte visuelle.
- Ne pas forcer une conversion en triangles ou en quads.
- Ne pas confondre réparation manifold, dissolution et réduction polygonale.
- Ne pas supprimer automatiquement les données partagées du fichier Blender.
- Ne pas ajouter un modèle d’IA gourmand en mémoire sans preuve de bénéfice.
- Ne pas compiler un moteur C++ avant d’avoir identifié un besoin mesuré.
- Ne pas lancer une chaîne d’opérations irréversible sans préserver l’original.
- Ne pas présenter une simple succession de modificateurs natifs comme une « IA de retopologie ».

---

## 13. Définition de réussite du projet

Le projet est réussi si l’utilisateur dispose d’un seul panneau Blender qui rassemble les outils de réparation et de nettoyage attendus, permet d’en contrôler précisément les options, et offre un moteur de simplification supplémentaire qui réduit effectivement la géométrie tout en mesurant les erreurs par rapport à l’original.

La qualité doit être démontrée sur plusieurs familles d’assets, et pas seulement sur le tissu simulé. Les performances doivent être mesurées sur le matériel de référence, et la topologie de sortie doit respecter le choix de l’utilisateur entre triangles, quads et conservation de la topologie existante.

**Priorité de développement : fiabilité et traçabilité, puis qualité géométrique, puis performances, puis fonctionnalités expérimentales d’IA.**
