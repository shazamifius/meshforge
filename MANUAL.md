# MeshForge for Blender — Complete Technical & User Manual
## The Comprehensive Guide to MeshForge Architecture, UX, Operators, Algorithms, and Workflows

> **Version:** MeshForge 0.2.0+ (Blender 4.2 LTS / 5.2+ LTS Compatible)  
> **Repository:** [github.com/shazamifius/meshforge](https://github.com/shazamifius/meshforge)  
> **Target Audience:** Technical Artists, 3D Modelers, Game Developers, Asset Optimizers, and Pipeline Engineers.

---

## Table of Contents

1. [Executive Overview & Core Architecture](#1-executive-overview--core-architecture)
   - 1.1 [Mission & Design Mandate](#11-mission--design-mandate)
   - 1.2 [The Non-Negotiable Core Principles](#12-the-non-negotiable-core-principles)
   - 1.3 [Supported Asset Categories](#13-supported-asset-categories)
   - 1.4 [System Requirements & Compatibility](#14-system-requirements--compatibility)
2. [User Experience (UX) Architecture & Layout Philosophy](#2-user-experience-ux-architecture--layout-philosophy)
   - 2.1 [The Dual-Section Design: CLEAN vs. DECIMATE](#21-the-dual-section-design-clean-vs-decimate)
   - 2.2 [Live Mesh Telemetry & Edit Mode Guard](#22-live-mesh-telemetry--edit-mode-guard)
   - 2.3 [Factual Measurements vs. Target-Driven Recommendations](#23-factual-measurements-vs-target-driven-recommendations)
   - 2.4 [Diagnosis Cache & Staleness Detection System](#24-diagnosis-cache--staleness-detection-system)
3. [Exhaustive Button & UI Controls Directory](#3-exhaustive-button--ui-controls-directory)
   - 3.1 [Global Header & Live Telemetry Box](#31-global-header--live-telemetry-box)
   - 3.2 [SECTION 1: CLEAN — Nettoyer et Réparer (Clean & Repair)](#32-section-1-clean--nettoyer-et-réparer-clean--repair)
     - Step 1: Mesh Analysis & 3D Viewport Inspection Tools
     - Step 2: Factual Geometric Findings & Detailed Findings Table
     - Step 3: Target Profile Selection (Asset Usage Target)
     - Step 4: Contextual Recommendations (The 4 Distinct Clean Categories)
     - Direct Topology Tools Subsection
     - Step 5: History & Restoration of Original Mesh
   - 3.3 [SECTION 2: DECIMATE — Réduire le Maillage (Mesh Decimation)](#33-section-2-decimate--réduire-le-maillage-mesh-decimation)
     - Step 1: Reduction Method Selection (Edge Collapse vs. Coplanar Dissolve)
     - Step 2: Decimation Objectives & Dynamic Budget Estimations
     - Step 3: Feature & Detail Preservation Options
     - Step 4: Workflow Safety & Critical Guards (Shape Keys & Aggressive Dissolve)
     - Step 5: Action Execution Controls
     - Step 6: Post-Execution Comparison Grid & Metrological Surface Validation
   - 3.4 [SECTION 3: EXPERT MODE — Advanced Controls & Combined Pipeline](#34-section-3-expert-mode--advanced-controls--combined-pipeline)
     - Full Pipeline Orchestrator
     - 1. Repair Subpanel (`VIEW3D_PT_meshforge_repair`)
     - 2. Manifold Consistency Subpanel (`VIEW3D_PT_meshforge_manifold`)
     - 3. Coplanar Dissolve Subpanel (`VIEW3D_PT_meshforge_dissolve`)
     - 4. Detailed Simplification Subpanel (`VIEW3D_PT_meshforge_simplification`)
     - 5. Topology Reconstruction Subpanel (`VIEW3D_PT_meshforge_topology`)
     - 6. Normals & Shading Subpanel (`VIEW3D_PT_meshforge_normals`)
     - 7. Object Data Cleaning Subpanel (`VIEW3D_PT_meshforge_object_data`)
     - 8. Session Report & Disk Export Subpanel (`VIEW3D_PT_meshforge_report`)
   - 3.5 [Add-on Preferences & GitHub Updater System](#35-add-on-preferences--github-updater-system)
4. [Algorithmic Engines & Under-the-Hood Mechanisms](#4-algorithmic-engines--under-the-hood-mechanisms)
   - 4.1 [Transactional Safety: The `MeshSnapshot` Rollback System](#41-transactional-safety-the-meshsnapshot-rollback-system)
   - 4.2 [3D Semantic Color-Coded Viewport Inspection](#42-3d-semantic-color-coded-viewport-inspection)
   - 4.3 [Intentional Findings Registry & Spatial Hashing](#43-intentional-findings-registry--spatial-hashing)
   - 4.4 [Conservative Cleaner & UV Seam Discontinuity Detection](#44-conservative-cleaner--uv-seam-discontinuity-detection)
   - 4.5 [Morphological N-Gon Cutter Engine](#45-morphological-n-gon-cutter-engine)
   - 4.6 [Targeted Quadrangulator & Orthogonality Scoring](#46-targeted-quadrangulator--orthogonality-scoring)
   - 4.7 [Strict Internal Walls vs. Non-Manifold T-Junctions](#47-strict-internal-walls-vs-non-manifold-t-junctions)
   - 4.8 [Rigorous Metrological Surface Validation Engine](#48-rigorous-metrological-surface-validation-engine)
   - 4.9 [Asynchronous Background Updater System](#49-asynchronous-background-updater-system)
5. [Standard Workflows & Step-by-Step Use Cases](#5-standard-workflows--step-by-step-use-cases)
   - 5.1 [Game Engine Asset Preparation (Unity / Unreal / Godot)](#51-game-engine-asset-preparation-unity--unreal--godot)
   - 5.2 [CAD / Mechanical Hard-Surface Cleanup](#52-cad--mechanical-hard-surface-cleanup)
   - 5.3 [Simulated Cloth & Open Boundary Surfaces](#53-simulated-cloth--open-boundary-surfaces)
   - 5.4 [Animated / Rigged Characters with Shape Keys](#54-animated--rigged-characters-with-shape-keys)
   - 5.5 [3D Printing & Watertight Export Preparation](#55-3d-printing--watertight-export-preparation)
6. [Troubleshooting, Edge Cases & Error Handling](#6-troubleshooting-edge-cases--error-handling)

---

## 1. Executive Overview & Core Architecture

### 1.1 Mission & Design Mandate

**MeshForge** is an advanced 3D mesh analysis, repair, cleanup, and intelligent simplification add-on for Blender. It was designed from first principles to bridge the gap between simple, automated one-click cleanup tools (like Instant Clean) and advanced, metrologically controlled geometry simplification suites.

Many conventional tools operate as "black boxes": they dissolve geometry indiscriminately, destroy delicate UV boundaries, collapse thin creases, alter vertex weights, and fail silently without providing rollback options. MeshForge solves this by providing:
1. Complete transparency over every single polygon and vertex altered.
2. Formally separated **Clean** (repair) and **Decimate** (reduction) workflows.
3. Strict non-destructive workflows by default.
4. Objective metrological verification (Hausdorff distance, normal deviation, silhouette 2D IoU) rather than unsubstantiated claims of visual perfection.

### 1.2 The Non-Negotiable Core Principles

MeshForge is built strictly around nine non-negotiable architectural mandates:

1. **Non-Destructive by Default:** Source meshes remain 100% untouched. All optimizations are carried out on an independent, decoupled duplicate object named `[OriginalName]_MF_Optimized`. The source object is hidden and preserved. Direct destructive mode requires explicit double confirmation.
2. **Proof Before Assertion:** MeshForge never promises "zero visual loss." Instead, it quantitatively measures geometric deviation (Hausdorff max distance, mean surface distance, normal angle delta) against the original geometry. If a measurement has not been run, the UI explicitly reports: *"Geometric deviation: Not measured"*.
3. **Deterministic Geometric Algorithms:** No decorative, heavy, or unpredictable machine learning models are used for topological operations. All decisions rely on deterministic geometric algorithms (QEM edge collapse, ear-clipping, planar dihedral angles, orthogonality metrics, and BVH-accelerated spatial trees).
4. **Explainable Selection:** When an automated mode recommends or rejects an operation, the user interface states exactly **why** (problem detected, affected zone, data impact, and reversibility).
5. **No Single Angle Threshold:** Planar angle deviation is treated as one signal among many. A 2° dihedral difference on an organic silhouette or long structural crease can be visually critical, whereas a 20° deviation on a micro-bevel can be negligible.
6. **No Silent Destruction of Attributes:** UV maps, vertex colors, material slot assignments, vertex weight groups, bevel weights, crease values, seams, and sharp edge marks are actively tracked, protected, or warned about before modification.
7. **Transactional Undo & Rollback:** Every topological operator uses an in-memory `MeshSnapshot` transaction mechanism. If any geometric invariant is breached (e.g., unintended hole creation, boundary collapse, or degenerate inversion), the mesh automatically rolls back to its exact pre-operation state.
8. **Scalability & Performance Benchmarking:** All core operations are profiled to ensure high-speed processing on high-density meshes (benchmarked on 1.587+ million triangle meshes within reasonable RAM and CPU bounds).
9. **Native Blender API Integrity:** MeshForge strictly adheres to the official Blender 4.2+ and 5.x Python API conventions (e.g., leveraging `shade_smooth_by_angle` instead of obsolete auto-smooth properties, native C-operator acceleration for slot deletions).

### 1.3 Supported Asset Categories

MeshForge is agnostic to model topology and handles diverse asset classes:
- **Triangulated Real-Time Meshes:** Low/Mid/High-poly models for video games with UV coordinates and normal maps.
- **Quad-Dominant Models:** Sub-d modeling assets, render meshes, and character topologies.
- **Mechanical & CAD Assemblies:** Hard-surface objects with sharp edges, boolean intersections, micro-chamfers, planar faces, and internal divider walls.
- **Organic & Sculpted Meshes:** High-density raw digital sculpts (ZBrush/Blender Sculpt) with complex curvature.
- **Open Surface Sheets & Simulated Cloth:** Non-watertight geometries, garments, flags, and sheets that must retain open boundary edges without forced hole filling.
- **Rigged & Deformable Meshes:** Animated characters with vertex groups, armature modifiers, and shape keys.

### 1.4 System Requirements & Compatibility

- **Host Application:** Blender 4.2 LTS, Blender 5.0, 5.1, or 5.2+ LTS.
- **Operating Systems:** Windows 10/11 (64-bit), Linux (glibc 2.31+), macOS (Apple Silicon & Intel).
- **Python Environment:** Python 3.10 / 3.11 / 3.13 (packaged with Blender).
- **Core Dependencies:** Standard Blender Python runtime: `bpy`, `bmesh`, `mathutils`, `numpy`. (No external C-extensions, DLLs, or pip installs required).

---

## 2. User Experience (UX) Architecture & Layout Philosophy

MeshForge organizes its user interface inside Blender's **3D Viewport Sidebar (N-Panel)** under the dedicated tab **`MeshForge`**.

```
+-------------------------------------------------------------+
| [Header] Update Notification Banner (if update available)  |
+-------------------------------------------------------------+
| [Telemetry] Active Object Info & Live Topology Counts       |
|             (Vertices, Edges, Faces, Real Triangles)        |
+-------------------------------------------------------------+
| [SECTION 1] CLEAN — Nettoyer et réparer (Expanded)          |
|  1. Analyze Mesh (3D Inspection & Wireframe overlay)        |
|  2. Factual Geometric Findings (Defects, Risks, Obs.)       |
|     [Detailed Findings Table, Filter, Zoom, Intentional]    |
|  3. Target Asset Profile (General, Game, Render, Rig, etc.) |
|  4. Contextual Recommendations (The 4 Distinct Categories)  |
|     - Category 1: Conservative Repairs (Safe One-Click)     |
|     - Category 2: Targeted Profile Optimizations            |
|     - Category 3: Risky Actions (Manual guidance & Walls)   |
|     - Category 4: Informational Observations                |
|  [Direct Topology Tools: Cut N-gons, Quadrangulate]         |
|  5. History & Restore Original (if viewing optimized copy)  |
+-------------------------------------------------------------+
| [SECTION 2] DECIMATE — Réduire le maillage (Collapsed)      |
|  1. Method: Edge Collapse (QEM) vs. Coplanar Dissolve       |
|  2. Objective: % Reduction, Target Tris, or Tolerance       |
|  3. Feature Preservation (Seams, Sharp, Materials, Normals) |
|  4. Workflow Safety & Guards (Shape Keys, Aggressive guards)|
|  5. Execution Button (Collapse / Dissolve)                  |
|  6. Real Before/After Telemetry & Metrological Verification |
+-------------------------------------------------------------+
| [SECTION 3] EXPERT MODE / Technical Settings (Collapsed)    |
|  - Combined Master Pipeline Execution                       |
|  - 7 Independent Specialist Sub-Panels (Repair to Data)     |
|  - JSON & TXT Export Reports                                |
+-------------------------------------------------------------+
| [Footer] Version Info, Check Updates, GitHub Shortcut       |
+-------------------------------------------------------------+
```

### 2.1 The Dual-Section Design: CLEAN vs. DECIMATE

Prior versions of mesh cleanup tools often grouped cleaning, hole filling, normal fixing, and mesh decimation into a single indistinct list. This created severe user errors, such as accidentally decimating a mesh while only attempting to remove orphan vertices.

MeshForge strictly divides the user journey into two self-contained sections:
1. **SECTION 1: CLEAN (Clean and Repair):**
   - **Open by default.**
   - Focuses strictly on geometric hygiene, manifold consistency, orphan cleanup, n-gon cuts, and quad formatting.
   - **Zero decimation takes place here.** The overall silhouette and density are strictly preserved while geometric bugs are resolved.
2. **SECTION 2: DECIMATE (Mesh Reduction):**
   - **Collapsed by default.**
   - Dedicated exclusively to polygon reduction.
   - Allows explicit choice between curved/organic edge contraction and hard-surface coplanar dissolution, with live budget estimation, detail preservation toggles, shape key protection, and honest before/after metrology.

### 2.2 Live Mesh Telemetry & Edit Mode Guard

At the very top of the panel, MeshForge displays instantaneous, zero-overhead telemetry:
- **Vertices:** Total raw vertex count (`len(mesh.vertices)`).
- **Edges:** Total edge count (`len(mesh.edges)`).
- **Faces:** Total polygonal face count (`len(mesh.polygons)`).
- **Real Triangles:** The true triangulated render count (`mesh.loop_triangles` or sum of polygon triangulations: $\sum \max(0, \text{verts} - 2)$).

#### The Edit Mode Guard
Blender's Python API requires distinct memory contexts: executing destructive BMesh operations while Blender is actively in `EDIT_MESH` mode causes viewport desynchronization, undo stack corruption, or crashes.
Whenever Blender is in Edit Mode, MeshForge surfaces a distinct high-visibility alert banner:
> **Mode Édition actif : actions désactivées**  
> *Switch back to Object Mode (Tab key) to run analysis and safe geometric repairs.*

All analytical and modifying operators poll `context.mode == 'OBJECT'` and will cleanly refuse execution with an informative notification if triggered from Edit Mode.

### 2.3 Factual Measurements vs. Target-Driven Recommendations

MeshForge separates **facts** from **opinions**:
- **Facts (Step 2):** Pure, objective geometric measurements that are true regardless of what the user wants to do with the mesh. For example: *Does the mesh have 3 zero-area faces? Are there 12 orphan vertices? Are there non-manifold edges?*
- **Target Recommendations (Steps 3 & 4):** Interpretation of those facts based on the user's selected **Target Profile**. For example:
  - In a **Game Asset** profile, an N-gon is a high-priority risk requiring triangulation.
  - In a **Mechanical CAD** profile, a planar N-gon is perfectly normal and desired.
  - In an **Open Cloth** profile, boundary edges are natural, whereas in an **Export Prep (3D Print)** profile, boundary edges are critical defects preventing a watertight print.

### 2.4 Diagnosis Cache & Staleness Detection System

Mesh analysis on large assets (e.g., 1.5M triangles) requires evaluating spatial trees, topological boundaries, and vertex valence. Running this on every viewport frame would cause lag.

MeshForge implements an in-memory ephemeral cache (`_ACTIVE_DIAGNOSIS_CACHE`) paired with a robust **Staleness Detection Engine**:
- When an analysis is run, MeshForge records a topological signature: `topo_signature = (len(vertices), len(edges), len(polygons))`, a rounded bounding box signature, and the mesh datablock name.
- If the user translates vertices in Edit Mode, modifies geometry with modifiers, or assigns a new mesh, MeshForge detects the signature mismatch instantly.
- **Adaptive Auto-Refresh:**
  - For small meshes ($\le 25,000$ triangles, representing $< 45\text{ ms}$ compute time), MeshForge auto-refreshes the diagnostic seamlessly.
  - For large assets ($> 25,000$ triangles), MeshForge displays a warning banner: *"Diagnostic à actualiser — La géométrie a été modifiée"* with the exact reason (e.g., *Vertices changed from 120,400 to 120,412*), and provides a one-click button to refresh.

---

## 3. Exhaustive Button & UI Controls Directory

This directory details **every button, input property, operator, and setting** present in MeshForge.

---

### 3.1 Global Header & Live Telemetry Box

#### Update Notification Banner
- **Trigger:** Appears at the very top of the panel when the background updater detects a newer release on GitHub.
- **Visual Alert:** Red/Alert box displaying `Mise à jour disponible : v{version}`.
- **Button: "Mettre à jour"**
  - **Operator ID:** `meshforge.install_update`
  - **Action:** Prompts for confirmation, downloads the latest master zipball from GitHub, backs up the current add-on version, replaces the files in the Blender addons directory, and notifies the user to restart Blender.

#### Active Object Box
- **Label:** `Objet : {object_name}` (with a green checkmark badge `[Optimisé]` if the object was created by MeshForge).
- **Telemetry Grid:** Live counters for Vertices, Edges, Faces, and Real Triangles.

---

### 3.2 SECTION 1: CLEAN — Nettoyer et Réparer (Clean & Repair)

Controlled by property `ui_section_clean_expanded` (collapsible header).

#### Step 1: Mesh Analysis & 3D Viewport Inspection Tools

1. **Button: "Analyser le maillage" (Analyze Mesh)**
   - **Operator ID:** `meshforge.analyze_topology`
   - **Icon:** `VIEWZOOM`
   - **Height Scale:** $1.3\times$ (Large primary button)
   - **Requirements:** Object Mode active, Mesh object selected.
   - **Internal Function:** Executes a 100% non-destructive read-only inspection (`core.topology_diagnosis.diagnose_topology`). Analyzes non-manifold edges, open boundaries, zero-area faces, orphan vertices, wire edges, n-gons (convex vs. concave vs. ambiguous), sliver triangles, complex poles ($\text{valence} \ge 6$), and disjoint components. Caches the diagnosis and updates topological signatures.
   - **Viewport Feedback:** Immediately applies semantic color attributes to the mesh in the 3D viewport (Orange for N-gons, Blue for suspect triangles, Red for degeneracies/non-manifold, Violet for isolated elements, Yellow for deformation risks).

2. **Button: "Afficher le filaire" / "Masquer le filaire" (Toggle Wireframe)**
   - **Operator ID:** `meshforge.toggle_wireframe`
   - **Icon:** `SHADING_WIRE` / `CHECKBOX_HLT`
   - **Internal Function:** Toggles Blender's native `obj.show_wire` and `obj.show_all_edges` properties. Crucially, MeshForge remembers the object's prior wireframe state in a module dictionary `_WIREFRAME_ENABLED_BY_MESHFORGE`. When toggled off, it restores the original user display preferences without polluting the scene.

3. **Button: "Effacer l'inspection" (Clear Inspection View)**
   - **Operator ID:** `meshforge.clear_defect_view`
   - **Icon:** `PANEL_CLOSE`
   - **Internal Function:** Removes the temporary vertex color layer (`_MF_Inspection_Temp`), restores the original active color attribute, resets the 3D viewport shading from `VERTEX` back to the user's prior solid shading mode (e.g. `MATERIAL` or `SINGLE`), deselects defect geometry, and clears the active cache.

4. **Button: "Actualiser le diagnostic maintenant" (Refresh Stale Diagnosis)**
   - **Operator ID:** `meshforge.analyze_topology`
   - **Icon:** `FILE_REFRESH`
   - **Trigger:** Surfaces only when staleness detection identifies that the mesh topology or bounding box was modified since the previous diagnostic run.

---

#### Step 2: Factual Geometric Findings & Detailed Findings Table

#### Health Status Indicator
Displays overall geometric state:
- **`HEALTHY` (Green):** "Santé : Maillage géométriquement sain" (Zero critical defects detected).
- **`CRITICAL` (Red Alert):** "Santé : {X} anomalie(s) critique(s)" (Zero-area faces, non-manifold geometry, orphan vertices, or degenerate elements present).
- **`RISKS` (Yellow/Info):** "Santé : {X} point(s) de vigilance" (Geometry has structural features that might conflict with certain target profiles, e.g., N-gons or open edges).

#### Counters Row
- **Défauts (Defects):** Critical mathematical errors requiring cleanup.
- **Risques (Risks):** Context-dependent items that may cause issues downstream.
- **Observations:** Neutral facts (e.g., triangle/quad ratio, UV island count).

#### Detailed Findings Table (`show_findings_table`)
A collapsible sub-table displaying granular finding cards.
- **Dropdown Filter "Catégorie" (`active_category_filter`):**
  - `ALL`: Display all findings across all disciplines.
  - `GEOMETRY`: Zero-area faces, orphan vertices, tiny edges, duplicate vertices.
  - `TOPOLOGY`: N-gons, wire edges, non-manifold edges, internal occluded walls.
  - `SURFACE`: Sliver triangles (needles), extreme aspect ratio triangles, curvature.
  - `UV_MATERIAL`: UV seams, texture borders, multiple material slots.
  - `NORMALS`: Split normals, sharp edges, smoothing consistency.
  - `DENSITY`: Polygon budget and quad/triangle distribution.
  - `DEFORMATION`: Edge loops, complex poles (valence $\ge 6$), rigging issues.
  - `EXPORT`: Watertight closure, export compatibility.
- **Dropdown Filter "Sévérité" (`active_severity_filter`):**
  - `ALL`: Show defects, risks, and observations.
  - `DEFECT`: Only show critical geometry corruption.
  - `RISK`: Only show vigilance items.
  - `OBSERVATION`: Only show neutral telemetry.

#### Per-Finding Card Controls
Every finding card provides:
1. **Severity Badge:** `[DÉFAUT]` (Red), `[RISQUE]` (Yellow), `[INFO]` (Gray), `[INTENTIONNEL]` (Green check), or `[INTENTIONNEL NON CONFORME]` (Alert check).
2. **Finding Title & Explanation:** Human-readable diagnosis.
3. **Impact / Consequence:** What happens if left uncorrected (e.g., *"Baking artifacts in normal maps"*, *"Engine crash during physics cooking"*).
4. **Advice / Recommendation:** Suggested fix.
5. **Manual Correction Steps:** Step-by-step guidance if automatic fixing is unadvisable.
6. **Button: "Zoomer" (Focus Defect)**
   - **Operator ID:** `meshforge.focus_defect`
   - **Parameter:** `finding_id = {finding_id}`
   - **Icon:** `ZOOM_SELECTED`
   - **Mechanism:** Calculates the 3D world centroid of the affected vertices/edges/faces, centers the 3D cursor, orients the active viewport camera, sets the zoom distance proportionally to the bounding box of the defect, transitions into Edit Mode, and selects the exact problematic sub-elements.
7. **Button: "Intentionnel" / "Rétablir" (Mark as Intentional / Unmark)**
   - **Operator ID:** `meshforge.mark_intentional`
   - **Parameters:** `finding_id = {finding_id}`, `unmark = {bool}`
   - **Icon:** `CHECKMARK` / `CANCEL`
   - **Mechanism:** Allows the artist to declare that a detected feature is deliberate (e.g., an intentional open boundary on clothing or planar n-gons on a CAD panel). Registers the item in `_mf_intentional_findings` and `_mf_intentional_registry` with its 3D centroid. Instantly re-evaluates recommendations in memory without a heavy re-scan.

---

#### Step 3: Target Profile Selection (Asset Usage Target)

Dropdown Enum property `asset_target_mode` with 8 distinct profiles:

| Profile Enum | UI Label | Icon | Focus & Re-interpretation |
| :--- | :--- | :--- | :--- |
| `GENERAL` | **1. Diagnostic général — « Je ne sais pas »** | `HELP` | Neutral, factual analysis. N-gons and open boundaries are **not** treated as defects. Only actual mathematical corruption (zero faces, loose verts) is flagged. |
| `GAME_ASSET` | **2. Jeu vidéo & Temps réel** | `PLAY` | Real-time engines (Unreal, Unity, Godot). Requires 100% triangulation or clean quad/tri mixes. N-gons are flagged as high-priority risks. Strict preservation of UV seams. |
| `RENDER_ANIM` | **3. Rendu & Animation** | `RESTRICT_RENDER_OFF` | Sub-d rendering and clean shading. Prioritizes regular quad topology and smooth pole distribution. Flags triangles and n-gons that pinch subdivision surfaces. |
| `DEFORMABLE_CHAR` | **4. Personnage déformable (Rigging)** | `OUTLINER_OB_ARMATURE` | Skeletal character animation. Strict quad topology along articulation loops. Flags poles with valence $\ge 6$, non-quad faces, and edge flow disruptions. |
| `EXPORT_PREP` | **5. Préparation export & Impression 3D** | `EXPORT` | Strict watertight (manifold) closure. Every boundary edge and non-manifold element is treated as a critical defect. Outward normal orientation enforced. |
| `MECHANICAL_CAD` | **6. Objet mécanique ou CAO** | `TOOL_SETTINGS` | Hard-surface and industrial parts. Planar N-gons are accepted and preserved. Focuses on eliminating boolean micro-edges, internal divider walls, and zero-area artifacts. |
| `SCULPTED_ORGANIC` | **7. Modèle sculpté ou organique** | `BRUSH_DATA` | High-density digital sculpts. High polygon count is recognized as normal. Focuses on curvature preservation and preventing destructive planar decimation. |
| `CUSTOM` | **8. Autre usage / Objectif personnalisé** | `PROPERTIES` | Tailored profile combined with user constraints. |

#### Complementary Constraint Checkboxes
- **`constraint_strict_manifold` ("Exiger étanchéité manifold stricte"):** Forces the diagnostic engine to treat any non-manifold edge, vertex, or open boundary loop as a critical defect, regardless of profile.
- **`constraint_quads_only` ("Exiger 100% quadrilatères (Quads)"):** Forces the engine to flag all triangles and N-gons as defects requiring quad conversion.

---

#### Step 4: Contextual Recommendations (The 4 Distinct Clean Categories)

The recommendations engine groups all actionable advice into four explicit, structured categories:

#### Category 1: Corrections conservatrices recommandées (Conservative Recommended Repairs)
Safe, lossless operations that fix proven geometric corruption.
- Displays problem description, affected zone, expected effect, data impact, and reversibility.
- **Action Buttons:**
  - **"Inspecter (Zoom)"** (`meshforge.focus_defect`): Zoom in on the defect.
  - **"Nettoyage conservateur (Sûr)"** (`meshforge.conservative_clean`):
    - **Operator ID:** `meshforge.conservative_clean`
    - **Properties:** `clean_loose_verts=True`, `clean_wire_edges=True`, `clean_zero_faces=True`, `merge_doubles=True`, `doubles_distance=0.00001m`, `preserve_seams=True`.
    - **Mechanism:** Operates under a `MeshSnapshot` transaction. Removes floating vertices and wire edges, dissolves zero-area faces ($\le 10^{-7}\text{ m}^2$), and merges coincident duplicate vertices. Crucially, it verifies UV island boundaries and seam markings, refusing to merge vertices across texture seams to prevent UV tearing. Automatically rolls back if an invariant is breached.

#### Category 2: Optimisations ciblées pour l'objectif (Targeted Optimizations for Profile)
Actions specifically recommended to fulfill the active Target Profile (e.g., cutting N-gons for game engines, or quadrangulating triangles for sub-d modeling).
- **Action Buttons:**
  - **"Inspecter (Zoom)"** (`meshforge.focus_defect`)
  - Direct operator button depending on the problem (e.g., `meshforge.cut_ngons`, `meshforge.quadrangulate`).

#### Category 3: Actions à risque à examiner individuellement (Risky Actions for Individual Review)
Alert-boxed cards highlighting modifications that could alter intended geometry (e.g., deleting ambiguous non-manifold junctions or removing internal walls).
- Displays manual recommended steps.
- **Action Buttons:**
  - **"Inspecter (Zoom)"** (`meshforge.focus_defect`)
  - **"Valider intentionnel"** (`meshforge.mark_intentional`)
  - Dedicated safe operator (e.g., `meshforge.remove_internal_walls`).

#### Category 4: Observations sans action requise (Informational Observations)
Neutral measurements requiring no action (e.g., mesh is 99% quads, texture slots are properly assigned, or features marked as intentional by the artist).
- If an item was marked intentional, provides a **"Rétablir" (Revert)** button to restore it to the defect list.

---

#### Direct Topology Tools Subsection

Exposes quick-access topological utilities directly within Section 1:

1. **Button: "Découper les N-gones (Convexes / Concaves)" (Cut N-Gons)**
   - **Operator ID:** `meshforge.cut_ngons`
   - **Properties:**
     - `cut_convex` (default: True): Cuts planar convex n-gons into balanced triangles using Beauty Delaunay-style triangulation.
     - `cut_concave` (default: True): Cuts concave n-gons using oriented Ear-Clipping that strictly respects interior reflex angles without cutting outside the polygon boundary.
     - `allow_ambiguous` (default: False): When False, safely skips self-intersecting (bow-tie) or severely warped n-gons, leaving them selected for manual knife cutting and reporting a warning.
     - `selected_only` (default: False): Restrict cut to selected faces only.
   - **Safety:** Transactional rollback via `MeshSnapshot` if triangles invert or UV loops distort.

2. **Button: "Quadranguler les triangles (Tris -> Quads)" (Targeted Quadrangulation)**
   - **Operator ID:** `meshforge.quadrangulate`
   - **Properties:**
     - `max_angle` (default: 15.0°): Maximum dihedral angle between adjacent triangle face normals to qualify for quad pairing.
     - `compare_uvs` (default: True): Refuses to merge triangles that cross UV island boundaries or UV seam discontinuities.
     - `compare_seams` (default: True): Preserves marked edge seams.
     - `compare_sharp` (default: True): Preserves sharp edge shading demarcations.
     - `compare_materials` (default: True): Never merges triangles assigned to different material slots.
   - **Algorithm:** Uses greedy quad-pairing scored by interior angle orthogonality (closest to 90°) and strictly verifies the convexity of the resulting quadrilateral.

---

#### Step 5: History & Restoration of Original Mesh

Surfaces only when the active object is a MeshForge result (contains `_MF_Optimized` or has property `_mf_source_ptr`).

- **Original Source Integrity Verification:**
  Checks the pointer `_mf_source_ptr` against `bpy.data.objects`. If the original source object was edited or changed in vertex count after the copy was generated, surfaces a warning alert:
  > **Attention : L'original a été modifié !**  
  > *Original object '{root_name}' has evolved since this copy was made.*

- **Button: "Restaurer l'original" (Restore Original)**
  - **Operator ID:** `meshforge.restore`
  - **Icon:** `RECOVER_LAST`
  - **Function:** Deletes the optimized duplicate object and its mesh datablock, unhides the original source object in the viewport, restores its active selection, and resets telemetry.

---

### 3.3 SECTION 2: DECIMATE — Réduire le Maillage (Mesh Decimation)

Controlled by property `ui_section_decimate_expanded` (collapsible header, closed by default).

#### Step 1: Reduction Method Selection

Dropdown Enum `decimate_method`:
1. **`COLLAPSE` — "Contraction d'arêtes (Surfaces courbées/organiques)" (`MOD_DECIM`):**
   - Progressive Quadric Error Metric (QEM) edge collapse algorithm.
   - Ideal for sculpted, organic, or smooth curved surfaces.
   - Contextual guidance explains that it contracts edges while preserving overall curvature and volume.
2. **`DISSOLVE` — "Dissolution coplanaire (Pièces planes/surfaces dures)" (`SNAP_FACE`):**
   - Planar coplanar edge dissolution.
   - Specialized for CAD models, hard-surface objects, and architectural planes.
   - Removes coplanar edges below a dihedral angle limit without altering silhouette boundaries.

---

#### Step 2: Decimation Objectives & Dynamic Budget Estimations

#### When Method is `COLLAPSE`:
Dropdown Enum `simplification_mode`:
- **`PERCENTAGE` ("Pourcentage de réduction (%)"):**
  - Slider `simplification_percentage` (0.0% to 99.9%, default: 50.0%).
  - **Live Dynamic Estimation Box:** Calculates and displays theoretical target triangles:
    $$\text{Target Triangles} = \max\left(4, \text{int}\left(\text{real\_tris} \times (1.0 - \frac{\text{percentage}}{100.0})\right)\right)$$
    Displays: `Estimation : ~X triangles (-Y%)` in real time before execution.
- **`BUDGET_TRIANGLES` ("Budget de triangles"):**
  - Integer input `simplification_target_triangles` (min: 4, default: 1000).
  - Displays target budget and theoretical reduction percentage.
- **`TOLERANCE_ONLY` ("Tolérance maximale seule"):**
  - Maximizes polygon reduction, stopping only when further contractions would exceed the specified geometric surface error tolerance.

#### When Method is `DISSOLVE`:
- **Angle Slider `dissolve_angle`:** Maximum dihedral angle between adjacent face normals (0.0° to 90.0°, default: 5.0°).
- **Rigor Level `dissolve_mode`:**
  - `CAREFUL`: Conservative threshold ($\le 2.0^\circ$) to preserve subtle silhouette folds.
  - `BALANCED`: Standard hard-surface reduction ($5.0^\circ$).
  - `AGGRESSIVE`: Maximum flat-face simplification ($15.0^\circ+$).

---

#### Step 3: Feature & Detail Preservation Options

#### When Method is `COLLAPSE`:
- **`collapse_triangulate` ("Trianguler avant réduction"):** Ensures uniform triangle input for the QEM solver.
- **`preserve_normals_angle` ("Préserver angles de normales"):** Prevents edge collapses across sharp shading splits.
- **`enable_simplification_tolerance` ("Plafonner par tolérance géométrique"):** Hard-stops decimation if surface deviation exceeds the defined metric threshold.
  - `simplification_max_tolerance`: Maximum admissible geometric deviation in meters (e.g. 0.005 m).
  - `tolerance_relative`: Interprets tolerance as a fraction of the object's bounding box diagonal.

#### When Method is `DISSOLVE`:
- **`preserve_sharp` ("Arêtes vives (Sharp Edges)"):** Prevents dissolution of edges marked sharp (`e.use_edge_sharp`).
- **`preserve_seams` ("Coutures UV (Seams)"):** Prevents dissolution of edges marked as UV seams (`e.use_seam`), preventing texture map distortion.
- **`preserve_materials` ("Frontières de matériaux"):** Prevents dissolution of edges shared between different material slots.
- **`preserve_uvs` ("Coordonnées UV"):** Prevents vertex dissolves that stretch UV coordinates across boundaries.
- **`preserve_boundaries` ("Frontières ouvertes"):** Prevents dissolving exterior perimeter loops on open surfaces.

---

#### Step 4: Workflow Safety & Critical Guards

- **`create_new_object` ("Créer un nouvel objet"):** Default: True. Ensures non-destructive operation on a duplicate mesh.
- **`hide_original` ("Masquer l'original"):** Default: True. Automatically hides the source object upon successful generation of the optimized mesh.
- **`destructive_mode` ("Mode destructif direct !"):** Requires `create_new_object=False`. Displays a high-visibility warning box and requires explicit modal confirmation before execution.

#### Critical Guard 1: Shape Keys Protection (UX8 Guard 1)
Blender's internal mesh architecture strictly forbids topology modification (decimation, vertex dissolution, edge contraction) on meshes that possess Shape Keys (Key Blocks). Applying decimation to a shape-keyed mesh throws a hard Blender C-level exception.
- When MeshForge detects shape keys on the active mesh, it surfaces an alert box:
  > **Attention : Shape Keys détectées !**  
  > *Blender forbids modifying the topology of a mesh with shape keys. To decimate, a static copy without shape keys is required. The original object retains 100% of its animation keys intact.*
- **Checkbox: `allow_shape_keys_removal_on_copy` ("Créer copie statique sans Shape Keys")**
  - If unchecked, decimation is blocked to protect the user from unexpected errors.
  - If checked, MeshForge duplicates the mesh, clears shape keys on the duplicate copy, and proceeds with decimation, while keeping the original object with all its animation shape keys untouched.

#### Critical Guard 2: Aggressive Dissolve Risk Detection (UX8 Guard 2)
Before running Coplanar Dissolve, MeshForge runs a real-time risk audit:
1. Detects if the mesh has UV seams and `preserve_seams` is turned off.
2. Detects if the mesh has sharp edges and `preserve_sharp` is turned off.
3. Detects if the mesh has multiple material slots and `preserve_materials` is turned off.
4. Detects if `AGGRESSIVE` mode is selected on sensitive profiles (`GAME_ASSET`, `DEFORMABLE_CHAR`).
5. Detects if a high dissolve angle ($\ge 15.0^\circ$) is applied to curved surfaces.
- If any of these risks are present, MeshForge blocks execution and surfaces an alert listing every specific risk.
- **Checkbox: `confirm_aggressive_dissolve` ("Confirmer la dissolution à risque")**
  - The artist must explicitly check this box to acknowledge the risk before MeshForge will execute the dissolve.

---

#### Step 5: Action Execution Controls

- **When Method is `COLLAPSE`:**
  - **Button: "Réduire le maillage (Contraction d'arêtes)"**
  - **Operator ID:** `meshforge.simplification`
  - **Icon:** `MOD_DECIM`
  - **Height Scale:** $1.3\times$
- **When Method is `DISSOLVE`:**
  - **Button: "Simplifier les faces (Dissolution coplanaire)"**
  - **Operator ID:** `meshforge.dissolve`
  - **Icon:** `SNAP_FACE`
  - **Height Scale:** $1.3\times$

---

#### Step 6: Post-Execution Comparison Grid & Metrological Surface Validation

Immediately after execution, the UI populates with comprehensive before/after metrics:
- **Status & Duration:** Execution status (e.g., `Succès`) and total wall-clock duration in seconds (`props.last_duration`).
- **Telemetry Delta Grid (3 Columns):**
  - **Triangles réels:** `Before -> After (-Reduction %)`
  - **Faces:** `Before -> After (-Delta faces)`
  - **Sommets:** `Before -> After (-Delta vertices)`
- **Metrology Section (Strict Metrological Honesty):**
  - If deep geometric validation was executed (`props.last_deviation_measured = True`):
    - **Écart Hausdorff max:** Maximum surface deviation in meters.
    - **Écart moyen de surface:** Average surface-to-surface distance in meters.
    - **Déviation normales max:** Maximum angular deviation of face normals in degrees.
  - If deep validation was not executed:
    - Displays: `Déviation géométrique : Non mesurée (validation approfondie non exécutée)` (Ensuring compliance with Core Principle 2: never claiming zero loss without empirical measurement).
- **Quick Restore Button:** **"Restaurer l'original"** (`meshforge.restore`).

---

### 3.4 SECTION 3: EXPERT MODE — Advanced Controls & Combined Pipeline

Controlled by property `show_expert_mode` (collapsible header, closed by default).

#### Master Pipeline Orchestrator

- **Button: "Exécuter tout le pipeline (Réparation + Décimation)"**
  - **Operator ID:** `meshforge.optimize`
  - **Icon:** `PLAY`
  - **Action:** Runs the complete sequential pipeline across all enabled sub-panels in strict order:
    1. Initial Diagnostic & Pre-checks
    2. Conservative Repair
    3. Manifold Consistency
    4. Coplanar Dissolve
    5. Intelligent Decimation (Simplification)
    6. Topology Reconstruction
    7. Normals & Shading Recalculation
    8. Object Data Cleanup
    9. Final Validation, Metric Deltas & Logging

---

#### 1. Repair Subpanel (`VIEW3D_PT_meshforge_repair`)
- **Header Checkbox:** `enable_repair`
- **Options:**
  - `repair_loose_geometry`: Master toggle for loose elements.
    - `loose_verts`: Remove vertices with 0 connected edges.
    - `loose_edges`: Remove edges with 0 connected faces.
    - `loose_faces`: Remove detached faces.
  - `repair_doubles`: Merge coincident vertices.
    - `doubles_relative`: Use relative factor based on bounding box.
    - `doubles_tolerance`: Absolute merge distance in meters (default: 0.0001 m).
    - `doubles_relative_factor`: Multiplier of bounding box diagonal.
  - `repair_zero_faces`: Dissolve faces with area below `zero_faces_threshold` (default: $10^{-6}\text{ m}^2$).
  - `repair_dispensables`: Simplify redundant collinear edges below `dispensable_angle` (default: 0.1°).
- **Execution Button: "Exécuter Réparation"** (`meshforge.repair`).

---

#### 2. Manifold Consistency Subpanel (`VIEW3D_PT_meshforge_manifold`)
- **Header Checkbox:** `enable_manifold`
- **Options:**
  - `manifold_mode`: `DIAGNOSTIC` (inspect only), `CAREFUL` (fix wire edges, planarity), `AGGRESSIVE` (delete non-manifold elements).
  - `remove_wire_geometry`: Delete wire edges without surface.
  - `fill_holes`: Fill open boundary loops up to `fill_holes_max_sides` (default: 4 sides).
  - `remove_non_manifold_faces` & `remove_non_manifold_verts`: Aggressive mode only.
  - `make_planar` (`make_planar_factor`, `make_planar_iterations`): Flattens warped polygons.
  - `flatten_faces` (`flatten_iterations`): Smooths local surface regions.
- **Dedicated Internal Walls Controls:**
  - **Button: "Inspecter (Zoom)"** (`meshforge.select_internal_walls`): Selects and frames strictly occluded internal divider faces.
  - **Button: "Supprimer"** (`meshforge.remove_internal_walls`): Prompts a modal confirmation dialog (`remove_strict_only=True`, `selected_only=False`), deletes internal divider walls, and seals non-manifold seams without opening holes.
- **Execution Button: "Exécuter Manifold complet"** (`meshforge.manifold`).

---

#### 3. Coplanar Dissolve Subpanel (`VIEW3D_PT_meshforge_dissolve`)
- **Header Checkbox:** `enable_dissolve`
- **Options:**
  - `dissolve_mode`: `CAREFUL`, `BALANCED`, `AGGRESSIVE`.
  - `dissolve_angle`: Planar angle limit.
  - Strict Preservations: `preserve_sharp`, `preserve_seams`, `preserve_materials`, `preserve_uvs`, `preserve_boundaries`.
- **Execution Button: "Exécuter Dissolution"** (`meshforge.dissolve`).

---

#### 4. Detailed Simplification Subpanel (`VIEW3D_PT_meshforge_simplification`)
- **Header Checkbox:** `enable_simplification`
- **Options:**
  - `simplification_mode`: `PERCENTAGE`, `BUDGET_TRIANGLES`, `TOLERANCE_ONLY`.
  - `simplification_percentage` & `simplification_target_triangles`.
  - `enable_simplification_tolerance`, `simplification_max_tolerance`, `tolerance_relative`.
  - `collapse_triangulate`: Triangulate before decimation.
  - `preserve_normals_angle`: Keep hard shading splits intact.
- **Execution Button: "Exécuter Simplification"** (`meshforge.simplification`).

---

#### 5. Topology Reconstruction Subpanel (`VIEW3D_PT_meshforge_topology`)
- **Header Checkbox:** `enable_topology`
- **Options:**
  - `topology_mode`:
    - `KEEP`: Preserve existing topology intact (Recommended).
    - `TRIS`: Full triangulation (`triangulate_quad_method` = `BEAUTY` or `SHORTEST_DIAGONAL`; `triangulate_ngon_method` = `BEAUTY` or `CLIP`).
    - `QUADS`: Convert triangles to quads via local pairing (`quads_face_threshold`, `quads_shape_threshold`, `preserve_topology_attributes`).
- **Execution Buttons:**
  - **"Quadrangulation ciblée sécurisée"** (`meshforge.quadrangulate`).
  - **"Exécuter Topologie complète"** (`meshforge.topology`).

---

#### 6. Normals & Shading Subpanel (`VIEW3D_PT_meshforge_normals`)
- **Header Checkbox:** `enable_normals`
- **Options:**
  - `recalculate_normals`: Enforce consistent face normals (`recalculate_direction` = `OUTSIDE` or `INSIDE`).
  - `apply_auto_smooth`: Applies angle-based smooth shading (uses `bpy.ops.mesh.shade_smooth_by_angle` in Blender 4.x/5.x) with `auto_smooth_angle` (default: 30.0°).
  - `weighted_normals`: Adds/applies the Weighted Normal modifier to improve shading on hard-surface chamfers.
  - `clear_custom_split_normals`: Clears corrupt or legacy split normal datablocks.
  - `clear_sharp_edges`: Clears all sharp edge marks.
- **Execution Button: "Exécuter Normales"** (`meshforge.normals`).

---

#### 7. Object Data Cleaning Subpanel (`VIEW3D_PT_meshforge_object_data`)
- **Header Checkbox:** `enable_object_data`
- **Options:**
  - `clean_material_doubles`: Detects duplicate material slots pointing to identical material datablocks, reassigns face indices to a single master slot, and eliminates duplicates.
  - `clean_unused_material_slots`: Uses native C acceleration (`material_slot_remove_unused`) to strip material slots not assigned to any polygon.
  - `clean_empty_vertex_groups`: Scans vertex groups across the mesh; removes any vertex group that has zero vertices with non-zero weight (preserves rigged deform groups that have active weights).
- **Execution Button: "Exécuter Nettoyage Données"** (`meshforge.object_data`).

---

#### 8. Session Report & Disk Export Subpanel (`VIEW3D_PT_meshforge_report`)
- Visible when Expert Mode is on or after any optimization run.
- Displays: Status, execution duration, telemetry before/after comparison table, reduction percentage, and execution log console.
- **Export Buttons:**
  - **Button: "Exporter (JSON)"** (`meshforge.export_report`, `format_type='JSON'`): Invokes Blender file browser to export a structured `.json` report file with complete metadata, phase timings, issues detected, and issues resolved.
  - **Button: "Exporter (Texte)"** (`meshforge.export_report`, `format_type='TXT'`): Exports a human-readable `.txt` log summary.

---

### 3.5 Add-on Preferences & GitHub Updater System

Located in Blender's user preferences: `Edit > Preferences > Add-ons > MeshForge`.

#### Workflow & Duplication Settings
- **`auto_switch_to_result` (default: True):** Automatically sets the newly generated `_MF_Optimized` object as active and selected in the 3D viewport.
- **`keep_original_collection` (default: True):** Automatically links the new object into all collections where the source object resides.
- **`result_suffix` (default: `_MF_Optimized`):** Custom string appended to the name of optimized duplicates.
- **`check_updates_on_startup` (default: True):** Asynchronously checks GitHub for newer versions when Blender launches.

#### GitHub Live Updater UI
- **Official Repository Display:** `shazamifius/meshforge`
- **Installed Version vs. Latest Version:** Displays installed semantic version (e.g. `v0.2.0`) and latest release tag fetched from GitHub.
- **Status Indicator:** `IDLE`, `CHECKING`, `UPDATE_AVAILABLE`, `UP_TO_DATE`, `DOWNLOADING`, `INSTALLED`, `ERROR`.
- **Button: "Vérifier maintenant" (Check Now):**
  - **Operator ID:** `meshforge.check_update`
  - Queries GitHub Releases API asynchronously in a background thread without freezing the Blender UI.
- **Button: "Mettre à jour vers v{version}" (Install Update):**
  - **Operator ID:** `meshforge.install_update`
  - Downloads release zipball, extracts, verifies file manifests, backs up old version, updates files in place, and prompts user to restart Blender.
- **Button: "Voir sur GitHub" (Open GitHub):**
  - **Operator ID:** `meshforge.open_github`
  - Opens `https://github.com/shazamifius/meshforge` in the system default web browser.

---

## 4. Algorithmic Engines & Under-the-Hood Mechanisms

This section provides technical documentation of the internal algorithms powering MeshForge.

---

### 4.1 Transactional Safety: The `MeshSnapshot` Rollback System

Every modifying operator in MeshForge encapsulates its logic within a transactional boundary managed by `core.conservative_cleaner.MeshSnapshot`.

```
                    +---------------------------+
                    |  Original Mesh in Scene   |
                    +---------------------------+
                                  |
                                  v
                    +---------------------------+
                    |   Create MeshSnapshot     |
                    | (Vertices, Edges, Faces,  |
                    |  UVs, Weights, Materials) |
                    +---------------------------+
                                  |
                                  v
                    +---------------------------+
                    | Execute BMesh Operations  |
                    |  (Clean, Cut, Decimate)   |
                    +---------------------------+
                                  |
                                  v
                    +---------------------------+
                    | Post-Operation Invariant  |
                    |        Validation         |
                    +---------------------------+
                                 / \
                   Invariants OK/   \ Invariant Violation
                               /     \ or Exception
                              v       v
           +--------------------+   +---------------------+
           | Commit Changes to  |   | Execute Rollback    |
           | Scene Mesh         |   | from MeshSnapshot   |
           +--------------------+   +---------------------+
                      |                        |
                      v                        v
           +--------------------+   +---------------------+
           | Free MeshSnapshot  |   | Restore 100% Source |
           | Memory & Complete  |   | State & Report Error|
           +--------------------+   +---------------------+
```

The snapshot captures:
- Vertex coordinates and edge/polygon index tables.
- All UV layers (names and 2D loop coordinates).
- Vertex color attributes (Float/Byte colors).
- Deform vertex groups and armature weights.
- Material assignments per polygon.
- Edge properties (seams, sharp edges, crease weights, bevel weights).
- Shading flags (smooth vs. flat).

If an operation throws an exception, creates self-intersections, produces inverted normals, or breaches topological invariants, `snapshot.restore(mesh)` is immediately invoked, returning the object to its exact initial state with zero data corruption.

---

### 4.2 3D Semantic Color-Coded Viewport Inspection

When `meshforge.analyze_topology` runs, it maps findings into five standardized color groups:

| Color Code | RGBA Value | Target Finding |
| :--- | :--- | :--- |
| **ORANGE** | `(1.00, 0.50, 0.05, 1.0)` | **N-Gons:** Polygons with 5 or more vertices. |
| **BLUE** | `(0.15, 0.55, 1.00, 1.0)` | **Suspect Triangles:** Needles (high aspect ratio) or triangles disrupting quad loops. |
| **RED** | `(0.95, 0.15, 0.15, 1.0)` | **Degeneracies:** Zero-area faces, micro-edges, non-manifold edges/vertices. |
| **VIOLET** | `(0.75, 0.25, 0.95, 1.0)` | **Isolated Elements:** Orphan vertices, wire edges, floating disjoint islands. |
| **YELLOW** | `(0.95, 0.85, 0.10, 1.0)` | **Deformation Risks:** Complex poles ($\text{valence} \ge 6$), high-tension animation zones. |
| **NEUTRAL** | `(0.65, 0.65, 0.65, 1.0)` | **Healthy Reference Geometry:** Baseline mesh. |

#### Non-Destructive Layer Architecture
- MeshForge creates a temporary color attribute named `_MF_Inspection_Temp`.
- It records the user's prior active color attribute and viewport shading mode.
- It switches viewport solid shading to `VERTEX` mode so colors are immediately visible.
- Running `meshforge.clear_defect_view` or applying an optimization cleans up `_MF_Inspection_Temp` and restores the user's prior viewport shading state.

---

### 4.3 Intentional Findings Registry & Spatial Hashing

A common flaw in automated linters is false positives on deliberate geometry (e.g., an artist deliberately left an open seam on a jacket, or used planar n-gons on an architectural facade).

MeshForge solves this via its **Intentional Findings Registry**:
- Findings are registered using granular composite IDs: `base_id:item_id` (e.g., `topo_ngons_convex:42`).
- The object stores two custom properties:
  - `_mf_intentional_findings`: A list of validated finding IDs.
  - `_mf_intentional_registry`: A JSON dictionary storing spatial metadata for each marked element (element type, index list, and 3D bounding box centroid).
- **Spatial Validation:** When re-evaluating, MeshForge checks whether the marked element still exists near its original 3D coordinates. If the geometry was deleted or heavily moved, the marking cleanly expires.
- **Decoupled Objective Evaluation:** Marking an opening as intentional excludes it from generic risk warnings, but if the user switches to `EXPORT_PREP` (3D print), the engine still flags it because 3D printers physically cannot print non-watertight models.

---

### 4.4 Conservative Cleaner & UV Seam Discontinuity Detection

The conservative cleaner (`core.conservative_cleaner`) eliminates orphan elements while strictly preserving surface and texture integrity.

#### UV Seam Discontinuity Detection Algorithm (`find_uv_discontinuity_vertices`)
Merging vertices by distance (`bmesh.ops.remove_doubles`) often destroys UV islands by welding together vertices that share 3D space but represent opposite sides of a 2D UV seam cut.
MeshForge protects UVs via a three-pass audit before any merge:
1. **Explicit Seams:** Gathers all vertices connected to edges where `edge.seam == True`.
2. **Loop UV Coordinate Divergence:** For every edge shared by 2 or more faces, evaluates loop UV coordinates. If adjacent face loops at the same vertex possess different UV coordinates in any UV layer, that vertex is flagged as a UV boundary.
3. **Island Perimeter Boundaries:** Detects coincident 3D vertices belonging to separate UV islands.
- All identified UV boundary vertices are added to an exclusion set and protected during double merging.

---

### 4.5 Morphological N-Gon Cutter Engine

Implemented in `core.ngon_cutter`, this engine analyzes n-gons ($\ge 5$ vertices) using 2D projection and angle analysis:

```
                          +------------------------+
                          |   N-Gon (>= 5 Verts)   |
                          +------------------------+
                                       |
                                       v
                          +------------------------+
                          | Best-Fit Normal Plane  |
                          |  Projection (2D Coords)|
                          +------------------------+
                                       |
                                       v
                          +------------------------+
                          |  Self-Intersection &   |
                          |    Planarity Audit     |
                          +------------------------+
                                      / \
                         Self-Cross? /   \ Clean Boundary
                                    /     \
                                   v       v
                       +-------------+   +-------------------+
                       |  AMBIGUOUS  |   | Interior Angles   |
                       | (Bow-Tie)   |   | Sign Verification |
                       +-------------+   +-------------------+
                              |                   / \
                              v      All Same Sign/   \ Mixed Signs
                       +-------------+           /     \
                       | Refuse Auto |          v       v
                       | Select for  |  +---------+   +----------+
                       | Manual Knife|  | CONVEX  |   | CONCAVE  |
                       +-------------+  +---------+   +----------+
                                             |             |
                                             v             v
                                        +---------+   +----------+
                                        | Beauty  |   | Ear-Clip |
                                        | Triang. |   | Triang.  |
                                        +---------+   +----------+
```

1. **Projection:** Projects the 3D polygon onto a 2D plane defined by its Newell normal.
2. **Intersection Test:** Checks for self-intersecting boundary edges ($\mathcal{O}(N^2)$ segment crossing tests).
3. **Convexity Classification:** Computes the 2D cross product of sequential edges:
   $$\text{cross}_i = (x_{i+1} - x_i)(y_{i+2} - y_{i+1}) - (y_{i+1} - y_i)(x_{i+2} - x_{i+1})$$
   - If all cross products have the same sign and planarity is within tolerance: classified as **`CONVEX`**.
   - If signs vary (reflex interior angles $> 180^\circ$ present): classified as **`CONCAVE`**.
   - If edges self-intersect or face planarity deviates severely: classified as **`AMBIGUOUS`**.
4. **Triangulation Execution:**
   - **`CONVEX`:** Triangulated using balanced Delaunay-style beauty cuts, preventing long thin needles.
   - **`CONCAVE`:** Triangulated using oriented Ear-Clipping. Ears are only clipped if the diagonal lies strictly inside the polygon interior.
   - **`AMBIGUOUS`:** Skipped by default. The polygon is kept intact, highlighted, and selected so the user can cut it manually with Blender's Knife tool (`K`).

---

### 4.6 Targeted Quadrangulator & Orthogonality Scoring

Implemented in `core.quadrangulator`, this module turns triangles into quads without disrupting topology:

1. **Candidate Pair Discovery:** Iterates over shared edges between pairs of triangles $(T_1, T_2)$.
2. **Filter Rejections:** Immediately rejects edge candidates if:
   - The dihedral angle between face normals $> \text{max\_angle}$ (default: 15.0°).
   - The shared edge is marked as a seam, sharp edge, crease, or material border.
   - Merging would produce a concave quad (tested via the cross products of the 4 perimeter vertices).
3. **Orthogonality Scoring:** Evaluates the candidate quad's interior angles against an ideal 90° rectangle:
   $$\text{Score} = 1.0 - \frac{\sum_{i=0}^3 |\theta_i - \frac{\pi}{2}|}{2\pi}$$
   A square/rectangle scores $\approx 1.0$, while a distorted trapezoid scores low.
4. **Greedy Pairing:** Candidate edges are sorted by score and dissolved sequentially. If dissolving an edge alters an adjacent candidate, the graph updates dynamically.

---

### 4.7 Strict Internal Walls vs. Non-Manifold T-Junctions

Non-manifold edges (edges shared by $\ge 3$ faces) are among the most difficult topological defects to clean automatically. Indiscriminately deleting non-manifold faces often tears holes in the outer shell.

`core.internal_walls` distinguishes three topological structures:
1. **Strict Internal Walls (`STRICT_INTERNAL_WALL`):**
   - Completely enclosed divider faces between two adjacent closed volumetric cells.
   - Every edge of the face has $\ge 3$ connected faces, and every adjacent face has an opposite outward-pointing normal.
   - **Safe to delete:** Removing strict internal walls heals the non-manifold edges back to 2-manifold edges without exposing any interior volume or creating boundary holes.
2. **T-Junctions & Attached Fins (`T_JUNCTION_OR_FIN`):**
   - Surfaces where a sheet or fin terminates against another wall.
   - Deleting these would destroy outer visible geometry. **Never deleted automatically.**
3. **Complex Junctions (`COMPLEX_JUNCTION`):**
   - Intersections with $\ge 4$ faces meeting at an edge. Flagged for manual review.

---

### 4.8 Rigorous Metrological Surface Validation Engine

Implemented in `core.validation`, this module provides mathematical verification comparing the optimized mesh ($M_{\text{opt}}$) against the source mesh ($M_{\text{orig}}$):

#### 1. Reproducible Barycentric Surface Sampling
Uniformly distributes $N$ sample points (default: 10,000) across mesh faces weighted by triangle area using a deterministic pseudo-random seed (default: 42):
$$P = (1 - \sqrt{r_1}) A + (\sqrt{r_1}(1 - r_2)) B + (\sqrt{r_1} r_2) C$$
Also samples all original vertices to guarantee feature representation.

#### 2. Bidirectional Hausdorff Distance & Quantiles
Uses BVH spatial trees (`mathutils.bvhtree.BVHTree`) to evaluate bidirectional point-to-surface distances:
- **Forward Distance:** Distance from samples on $M_{\text{orig}}$ to the surface of $M_{\text{opt}}$.
- **Backward Distance:** Distance from samples on $M_{\text{opt}}$ to the surface of $M_{\text{orig}}$.
- **Metrics Computed:**
  - $\text{Hausdorff Max} = \max(\text{forward}_{\max}, \text{backward}_{\max})$
  - $\text{Mean Surface Distance} = \frac{1}{2}(\text{forward}_{\text{mean}} + \text{backward}_{\text{mean}})$
  - $\text{P95 / P99 Quantiles:}$ Captures structural deviations while filtering out isolated point spikes.

#### 3. Normal Angular Deviation
Computes the angular difference between surface normals at matched nearest points:
$$\theta_{\text{dev}} = \arccos\left(\text{clamp}(\vec{n}_{\text{orig}} \cdot \vec{n}_{\text{opt}}, -1.0, 1.0)\right)$$
Reports maximum normal deviation in degrees.

#### 4. 2D Silhouette Intersection-over-Union (IoU)
Renders orthographic projection masks of both meshes from 6 cardinal directions ($\pm X, \pm Y, \pm Z$) onto a 2D grid:
$$\text{IoU} = \frac{\text{Area}(M_{\text{orig}} \cap M_{\text{opt}})}{\text{Area}(M_{\text{orig}} \cup M_{\text{opt}})}$$
Measures whether the visual outline of the object has been degraded from key camera angles.

#### 5. Watertight Volume Delta
For closed manifold meshes, evaluates total divergence volume via the divergence theorem:
$$V = \frac{1}{6} \sum_{i} \vec{v}_0 \cdot (\vec{v}_1 \times \vec{v}_2)$$
If the mesh is open or non-manifold, the volume calculation is safely bypassed.

---

### 4.9 Asynchronous Background Updater System

Implemented in `core.updater`, this system connects to the GitHub REST API (`shazamifius/meshforge`):
- **Non-Blocking Operation:** All network operations (release querying, tag parsing, archive streaming) run inside a Python `threading.Thread`.
- **Manifest Validation:** Downloaded archives are checked in a temporary directory for valid `__init__.py` and `blender_manifest.toml` files before installation.
- **Atomic File Swap:** Replaces add-on files while keeping local user settings intact.

---

## 5. Standard Workflows & Step-by-Step Use Cases

### 5.1 Game Engine Asset Preparation (Unity / Unreal / Godot)

**Objective:** Clean an exported high/mid-poly asset, ensure 100% triangulation, remove degenerate faces, and reduce poly count by 50% while preserving UV islands and normal maps.

1. **Selection:** Select the object in Blender's 3D Viewport in Object Mode.
2. **Analysis:** Under **SECTION 1 (CLEAN)**, click **"Analyser le maillage"**.
3. **Target Profile:** Set **"Objectif de l'Asset"** to **`2. Jeu vidéo & Temps réel`**.
4. **Conservative Cleanup:** Under Step 4 (Category 1), click **"Nettoyage conservateur (Sûr)"**.
   - Removes loose vertices, zero-area faces, and welds duplicate vertices without tearing UV seams.
5. **N-Gon Triangulation:** Under Direct Topology Tools, click **"Découper les N-gones"**.
   - Converts all planar and concave n-gons to clean triangles.
6. **Decimation:**
   - Expand **SECTION 2 (DECIMATE)**.
   - Set **"Méthode de réduction"** to **`Contraction d'arêtes (Surfaces courbées/organiques)`**.
   - Set **"Objectif"** to **`Pourcentage de réduction (%)`** and set slider to `50.0%`.
   - Ensure **"Conserver coordonnées UV"** and **"Créer un nouvel objet"** are checked.
   - Click **"Réduire le maillage (Contraction d'arêtes)"**.
7. **Verification:** Inspect the Before/After telemetry grid. Confirm real triangles reduced by ~50% and review normal deviation. The new object is named `[Name]_MF_Optimized`.

---

### 5.2 CAD / Mechanical Hard-Surface Cleanup

**Objective:** Clean up an imported STEP/IGES boolean assembly with boolean sliver faces, micro-edges, and coplanar flat faces without rounding sharp corners.

1. **Selection:** Select the mechanical assembly in Object Mode.
2. **Analysis:** Click **"Analyser le maillage"**.
3. **Target Profile:** Select **`6. Objet mécanique ou CAO`**.
4. **Repair:** Under Category 1, run **"Nettoyage conservateur (Sûr)"** to eliminate boolean micro-edges and zero-area artifacts.
5. **Internal Walls:** If boolean operations left occluded internal partitions, go to Category 3 or Expert Manifold and click **"Inspecter (Zoom)"** on internal walls, then click **"Supprimer"**.
6. **Planar Dissolve:**
   - Expand **SECTION 2 (DECIMATE)**.
   - Set **"Méthode de réduction"** to **`Dissolution coplanaire (Pièces planes/surfaces dures)`**.
   - Set **"Angle limite"** to `2.0°` (Careful) or `5.0°` (Balanced).
   - Ensure **"Arêtes vives (Sharp Edges)"** is checked.
   - Click **"Simplifier les faces (Dissolution coplanaire)"**.
7. **Shading:** In Expert Normals or Section 1 recommendations, apply **"Auto Smooth par angle"** at `30.0°` with **"Weighted Normals"** to obtain perfect reflections on chamfers.

---

### 5.3 Simulated Cloth & Open Boundary Surfaces

**Objective:** Clean a Marvelous Designer / Blender cloth simulation mesh without accidentally closing open collars, hems, or waistband boundaries.

1. **Selection:** Select the garment in Object Mode.
2. **Target Profile:** Set **"Objectif de l'Asset"** to **`1. Diagnostic général`** or **`7. Modèle sculpté ou organique`**.
3. **Hole Filling Guard:** Verify that **`Fill Holes`** is **OFF**. MeshForge defaults to `fill_holes = False` specifically to prevent closing intentional openings.
4. **Mark Open Boundaries:** If boundary edges appear under Step 2 findings, click **"Intentionnel"** to declare the open hems as deliberate design features.
5. **Clean:** Click **"Nettoyage conservateur (Sûr)"** to merge doubles along simulated stitching lines while keeping the hem open.

---

### 5.4 Animated / Rigged Characters with Shape Keys

**Objective:** Decimate an animated character model that possesses facial blendshapes (Shape Keys) without throwing errors or corrupting animation data.

1. **Selection:** Select the character mesh.
2. **Shape Key Alert:** Notice the safety alert box in Section 2: *"Shape Keys détectées !"*.
3. **Enable Static Copy:** Check **"Créer copie statique sans Shape Keys"** (`allow_shape_keys_removal_on_copy`).
4. **Decimate:** Set decimation budget (e.g. 50%). Click **"Réduire le maillage"**.
5. **Result:** MeshForge leaves the original character with all its shape keys and armature intact, and creates `Character_MF_Optimized` as a lightweight static reference mesh for LOD baking or background crowd rendering.

---

### 5.5 3D Printing & Watertight Export Preparation

**Objective:** Prepare an asset for STL export for SLA/FDM 3D printing, ensuring it is 100% watertight with zero non-manifold edges.

1. **Target Profile:** Select **`5. Préparation export & Impression 3D`**.
2. **Strict Constraint:** Enable **"Exiger étanchéité manifold stricte"** (`constraint_strict_manifold`).
3. **Analyze:** Click **"Analyser le maillage"**.
4. **Holes & Open Seams:** Any open boundary loop is now surfaced as a critical defect. Use **"Fill Holes"** (Max Sides: 1000) to cap openings.
5. **Internal Occlusions:** Click **"Supprimer les parois internes"** to hollow out or merge internal cavities.
6. **Normals:** Under Expert Normals, execute **"Recalculer les normales"** with Direction: **`Extérieur (Outside)`**.
7. **Export:** Export report as JSON for quality auditing, then export mesh to STL.

---

## 6. Troubleshooting, Edge Cases & Error Handling

### 1. "Mode Édition actif : actions désactivées"
- **Cause:** Blender is currently in Edit Mode.
- **Solution:** Press `Tab` in the 3D viewport to return to Object Mode. MeshForge requires Object Mode to ensure transactional data synchronization and rollback safety.

### 2. "Nettoyage refusé et annulé : [Reason]. Le maillage a été restauré sans aucune perte."
- **Cause:** An operator breached a geometric invariant (e.g., an edge collapse inverted face normals or created a degenerate face).
- **Behavior:** The `MeshSnapshot` engine automatically rolled back all changes. The mesh in your scene was returned to its exact pre-operation state.
- **Solution:** Check the specific reason in the info bar (e.g., *"Dihedral angle exceeds threshold"*), adjust tolerances (e.g., reduce merge distance or lower dissolve angle), and retry.

### 3. "Cet objet possède des Shape Keys... Cochez l'option 'Créer copie statique sans Shape Keys'"
- **Cause:** Blender's core engine forbids decimation modifiers on meshes with shape key blocks.
- **Solution:** Check the box **"Créer copie statique sans Shape Keys"** in Section 2. The original mesh retains all shape keys intact, while the new optimized object receives the decimation.

### 4. "Dissolution bloquée par prudence : Coutures UV non préservées..."
- **Cause:** You are running Coplanar Dissolve with `preserve_seams=False`, `preserve_sharp=False`, or high angles on a sensitive profile.
- **Solution:** Either turn on the preservation checkboxes (recommended) or check **"Confirmer la dissolution à risque"** to explicitly authorize the operation.

### 5. "N-gones ambigus refusés"
- **Cause:** An N-gon has self-intersecting boundary segments (bow-tie) or severe non-planar warping that cannot be triangulated safely without manual intent.
- **Solution:** MeshForge automatically selects these faces. Press `Tab` to enter Edit Mode and use Blender's Knife tool (`K`) to manually divide the face.

### 6. Where is the exported report saved?
- When clicking **"Exporter (JSON)"** or **"Exporter (Texte)"**, a standard Blender file dialog opens allowing you to choose the exact folder and filename on your disk.

---

## Conclusion & Architectural Summary

MeshForge is engineered to provide complete control, verifiable accuracy, and zero accidental destruction:
- **Clean** solves geometric defects with zero polygon decimation.
- **Decimate** reduces density with full detail preservation and honest metrology.
- **Expert Mode** provides granular, individual operator access for pipeline automation.
- **Every operator** is backed by automated rollback, protecting your production assets at all times.

*For bug reports, feature requests, or updates, visit the official repository:*  
[https://github.com/shazamifius/meshforge](https://github.com/shazamifius/meshforge)
