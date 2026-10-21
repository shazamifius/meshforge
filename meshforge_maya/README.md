<div align="center">

# MeshForge for Autodesk Maya ⚡
### Professional 3D Mesh Inspection, Repair & Decimation Suite

<br/>

<a href="https://github.com/shazamifius/meshforge/releases/latest/download/meshforge_maya.zip">
  <img src="https://img.shields.io/badge/📦_DOWNLOAD_SCRIPT_MAYA-DOWNLOAD_(.ZIP)-0696D7?style=for-the-badge&logo=autodesk&logoColor=white" height="52" alt="Download Script Maya" />
</a>
&nbsp;&nbsp;&nbsp;&nbsp;
<a href="https://github.com/shazamifius/meshforge/releases/latest/download/install.mel">
  <img src="https://img.shields.io/badge/⚡_DOWNLOAD_INSTALL.MEL-(DIRECT)-00A8FF?style=for-the-badge&logo=autodesk&logoColor=white" height="52" alt="Download install.mel" />
</a>

<br/><br/>

[![GitHub Release](https://img.shields.io/github/v/release/shazamifius/meshforge?color=2ecc71&style=flat-square)](https://github.com/shazamifius/meshforge/releases/latest)
[![Maya Tests](https://img.shields.io/badge/Maya%20Tests-18%2F18%20Passing-brightgreen?style=flat-square&logo=autodesk)](tests/test_maya_runner.py)
[![Documentation](https://img.shields.io/badge/Documentation-MANUAL.md-blue?style=flat-square)](../MANUAL.md)

</div>

---

**MeshForge for Maya** brings the complete 3D mesh analysis, repair, geometric cleanup, and intelligent simplification toolset of MeshForge to **Autodesk Maya (2020 through Maya 2027+)**.

Engineered with complete **1:1 feature parity with MeshForge for Blender**, MeshForge for Maya provides a non-destructive workflow, contextual target profiles, robust geometry repair, detail-preserving decimation, metrological validation, and blendshape safety guards.

---

## ⚡ Super Easy Installation (3 Methods)

### Method 1: The Zero-Effort Drag & Drop (Recommended — 0 Terminal, 1 Action)
> Compatible with **Windows, macOS, and Linux** across **Maya 2020, 2022, 2023, 2024, 2025, 2026, 2027+**.

1. Launch Autodesk Maya.
2. Drag and drop [**`install.mel`**](https://github.com/shazamifius/meshforge/releases/latest/download/install.mel) (or `meshforge_maya/install.py`) directly from your file manager into **Maya's 3D Viewport**.
3. A dialog confirms installation, and a custom **MeshForge** shelf button is instantly added to your active shelf!
4. Click the button to launch MeshForge!

---

### Method 2: Double-Click Installer (Outside Maya)

- **On Windows:**
  - Double-click `install_maya.bat` in the repository root.
  - Automatically registers the module in `%USERPROFILE%\Documents\maya\modules\meshforge_maya.mod` and adds the startup hook to `userSetup.py`.
- **On macOS & Linux:**
  - Open a terminal and run:
    ```bash
    chmod +x install_maya.sh
    ./install_maya.sh
    ```
  - Automatically registers the module into `~/Library/Preferences/Autodesk/maya/modules` (macOS) or `~/maya/modules` (Linux).

---

### Method 3: Maya Python Script Editor (1-Liner)

Open Maya's **Script Editor** (Python tab) and paste:

```python
import sys; sys.path.insert(0, r"C:/path/to/meshforge"); import meshforge_maya; meshforge_maya.show()
```

---

## 🚀 Key Features

1. **Non-Destructive Workflow by Default:**
   - Source geometry is 100% preserved and hidden.
   - Outputs an independent duplicate: `[Name]_MF_Optimized`.
   - One-click **"Restore Original Mesh"** instantly unhides the source object and removes the duplicate.

2. **Dual-Section Modern PySide UI (Section 1 CLEAN & Section 2 DECIMATE):**
   - **SECTION 1: CLEAN (Clean & Repair):**
     - **Topological Analysis:** Evaluates non-manifold edges/vertices, open boundaries, zero-area faces, n-gons (convex vs concave), sliver triangles, and complex poles.
     - **Factual Geometric Findings:** Granular table with Category (`GEOMETRY`, `TOPOLOGY`, etc.) and Severity filters (`DEFECT`, `RISK`, `OBSERVATION`), with 3D component focus (zoom) and "Mark as Intentional" options.
     - **8 Target Profiles:** `GENERAL`, `GAME_ASSET`, `RENDER_ANIM`, `DEFORMABLE_CHAR`, `EXPORT_PREP`, `MECHANICAL_CAD`, `SCULPTED_ORGANIC`, `CUSTOM`.
     - **The 4 Recommendation Categories:** 1. Conservative Recommended Repairs (safe one-click cleanup), 2. Targeted Optimizations, 3. Risky Actions (manual review & internal wall deletion), 4. Informational Observations.
     - **Direct Topology Tools:** Cut N-gons and Quadrangulate (Tris -> Quads).
   - **SECTION 2: DECIMATE (Mesh Reduction):**
     - **Dual Methods:** Edge Collapse QEM (`polyReduce` for curved/organic shapes) vs Coplanar Dissolve (`polyDissolve` for CAD/hard-surface).
     - **Live Estimation:** Dynamic real-time calculation of estimated triangles as you slide the percentage slider.
     - **Detail Preservation:** Open boundaries, hard/sharp edges, and UV texture seams.
     - **Blendshape Protection:** Detects incoming `blendShape` deformers, warns the artist, and enables creating a static copy without blendshapes so the original rigged character is never corrupted.
     - **Surface Metrology:** Objective measurement of maximum Hausdorff distance and mean surface deviation using OpenMaya spatial intersectors (`MMeshIntersector`).
   - **SECTION 3: EXPERT MODE:**
     - Full combined sequential pipeline execution.
     - Dedicated specialist operators for Repair, Internal Walls, Dissolve, Normals, and Object Shading Data.
     - JSON and TXT report export.

---

## 🧪 Automated Test Suite (16/16 Unit Tests)

MeshForge for Maya includes an exhaustive test suite covering all algorithms and 100% of the UI widgets:

```powershell
# Run the complete test suite headlessly via mayapy:
& "C:\Program Files\Autodesk\Maya2027\bin\mayapy.exe" meshforge_maya/tests/test_maya_runner.py
```

---

## 🏛️ Architecture & Code Cleanliness

The Maya package is strictly decoupled into modular layers to allow adding complex features effortlessly:

```text
meshforge_maya/
├── __init__.py                # Package entrypoint (meshforge_maya.show())
├── install.py                 # Python shelf installer & onMayaDroppedPythonFile hook
├── install.mel                # MEL drag-and-drop installer
├── meshforge_maya.mod         # Native Maya module descriptor
├── icons/
│   ├── meshforge_icon.png     # Custom 64x64 shelf icon
│   └── meshforge_icon_32.png  # Custom 32x32 shelf icon
├── core/
│   ├── snapshot.py            # Transactional undo/rollback system
│   ├── mesh_stats.py          # Fast telemetry & component counting
│   ├── structured_diagnosis.py# 8 Profiles & 4 recommendation categories
│   ├── conservative_cleaner.py# Safe orphan, zero-area face, and double cleanup
│   ├── ngon_cutter.py         # Convex/concave morphological n-gon cutter
│   ├── quadrangulator.py      # Targeted quad pairing with feature preservation
│   ├── internal_walls.py      # Internal divider detection and removal
│   ├── dissolve.py            # Coplanar normal angle edge dissolution
│   ├── simplification.py      # QEM edge collapse decimation engine
│   ├── normals.py             # Normal conform, soft/hard edge angles
│   ├── object_data.py         # Shading engine and empty set cleanup
│   ├── pipeline.py            # Non-destructive orchestrator
│   ├── validation.py          # OpenMaya MMeshIntersector surface distance
│   └── visualizer.py          # Viewport camera framing and wireframe toggle
├── ui/
│   ├── qt_compat.py           # Seamless PySide6 / PySide2 abstraction
│   ├── styles.py              # Maya dark theme QSS stylesheet
│   └── main_window.py         # Dockable Qt main window with Section 1/2/3
└── tests/
    ├── test_maya_clean.py     # Clean & repair tests
    ├── test_maya_decimate.py  # Decimation & metrology tests
    ├── test_maya_pipeline.py  # Pipeline & rollback tests
    ├── test_maya_ux_full.py   # 100% UX & widget tests
    └── test_maya_runner.py    # Automated test runner
```
