##### Table of Contents
- [Introduction](#introduction)
- [Project layout](#project-layout)
- [Building](#building)
- [Functionality](#functionality)
  - [Available Pie Menus](#available-pie-menus)
  - [Made for industry artists](#made-for-industry-artists)
  - [Built-in add-on integration](#built-in-add-on-integration)
  - [Non-intrusive default keymaps](#non-intrusive-default-keymaps)
  - [Stability](#stability)
  - [Extras](#extras)
    - [Extended origin and cursor manipulation](#extended-origin-and-cursor-manipulation)
    - [Improved Separate](#improved-separate)

&nbsp;
&nbsp;

# Introduction
Welcome to Pie Menus Plus! This is a free and open-source add-on providing improved pie menus for Blender 4.2+.

**Compatibility:** Version 2.4.0 supports Blender 4.2 through current Blender releases, including Blender 5.2+.

# Project layout
- `addon/` contains the Blender-installable add-on package and its `blender_manifest.toml`.
- `build.bat` builds the package from `addon/` and writes the installable zip to `dist/`.
- `README.md`, `Roadmap.md`, `ops.md`, and `pie_ops.md` are project documentation.

# Building
Run `build.bat` from Windows with Blender available on `PATH`, or set the `BLENDER_EXE` environment variable to the Blender executable before running it. The generated `dist\PieMenusPlus-2.4.0.zip` can be installed through Blender’s Extensions preferences.

## Recent Updates (v2.4.0)
- **Optional Smart Scrub**: Adds opt-in context-aware animation targets, active/selected/visible object scopes, marker and Sequencer boundary targets, proximity snapping, adaptive sensitivity, and target-source HUD status
- **Timeline Scrub**: Integrated configurable modal timeline scrubbing with keyframe snapping, rolling mode, viewport HUD, and timeline-editor options
- **Optional Dependency Detection**: Dynamically detects LoopTools, Bool Tool, and EdgeFlow availability, reports status in preferences, and provides useful fallback messages in their pies
- **EdgeFlow Integration**: Added context-aware pie menu for EdgeFlow addon (Shift+Alt+F) with smart vertex/edge mode detection
- **Cross-version Blender API Compatibility**: Added guarded fallbacks for Blender 4.2-5.2+ snapping, selection, brush, shading, Grease Pencil, and import APIs
- **Custom Sculpt Brushes**: Added preferences-based custom sculpt brush system allowing users to assign their own brush asset paths
- **Improved Addon Detection**: Fixed BoolTool and LoopTools detection to use operator existence checks instead of addon registry lookups
- **Clean Distribution**: Removed external links and author references for professional distribution

# Available pie menus
- Select Modes (UV compatible)
- Origin / Cursor
- Transforms & Relations
- Mesh / Curve Delete
- Shading & Overlays
- Selection
- Animation Playback
- Keyframing
- Select Active Tool
- Select Sculpt Tool
- Snapping (UV compatible)
- Proportional Editing
- LoopTools Integration
- BoolTool Integration
- EdgeFlow Integration
- Mesh Align
- Save

# Made for industry artists and advanced hobbyists
Pie menus are by far the most efficient way to interact within the Blender viewport. The built-in pie menu add-on is good, but it doesn't consider certain aspects of modern modeling workflows. There is a ton of extremely useful operators that deserve to exist within pies that are simply left out in the default and built-in add-on pies, forcing you to compromise and sift through dropdowns or use the operator search.

# Built-in add-on integration
Some functionality is locked behind optional add-ons you can enable within Blender. This add-on attempts to fill some of the gaps where this extra functionality lacks pie support, while staying true a "vanilla" experience.

# Non-intrusive default keymaps
Pie Menus Plus overlays keymaps over the standard Blender keymap configuration, meaning uninstalling will maintain the original keymaps. This add-on does not accommodate industry standard keymaps but you can use it at the minor risk of other keymaps becoming "conflicted".

# Stability
Pie Menus Plus is fundamentally stable due to its inherent simplicity. It often does no more than convert existing operators into a digestible menu of contextually relevant functionality.

# Extras
Pie Menus Plus includes extra functionality for improved workflow. Here are the important features:

### Extended origin and cursor manipulation
Most operators contained within the Origin / Cursor pie have access to the `Copy Active Rotation` tick within the Redo Panel of the operators.

### Improved Separate
Added `Remove Modifiers` tick to the Redo Panel of the operator for situations where modifiers make separated objects completely unselectable in the 3D View.
