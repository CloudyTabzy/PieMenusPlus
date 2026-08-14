# Pie Menus Plus - Roadmap

This document outlines future improvements and development goals for Pie Menus Plus.

## Keymap System Improvements

- [ ] Add user-defined keymap profiles (save/load keymap configurations)
- [ ] Implement keymap conflict detection and resolution
- [ ] Add keyboard shortcut editor in preferences

## Addon Integration Robustness

- [x] Add dynamic addon detection (scan for installed addons and adapt UI)
- [x] Create fallback UI when integrated addons aren't available
- [x] Add optional dependency checks at startup

## UI/UX Enhancements

- [ ] Add customizable pie menu themes (colors, icons)
- [ ] Implement pie menu preview/editor
- [ ] Add context-aware menu filtering based on selection/mode

## Animation Tools

- [x] Integrate configurable timeline scrubbing with keyframe snapping and rolling mode
- [x] Add optional Smart Scrub with context-aware targets and proximity snapping
- [x] Refactor configurable sculpt brushes with presets, slot controls, and asset-path fallbacks

## Completed

- [x] Prefer brush assets with a legacy `paint.brush_select` fallback for Blender 4.2+
- [x] Implement preferences-based custom sculpt brush system
- [x] Move custom sculpt brushes to keymaps section with per-slot controls and presets
- [x] Fix LoopTools and BoolTool detection to use operator existence checks
- [x] Remove external links and author references for clean distribution
- [x] Keep keymap UI optional with a plain-string fallback
- [x] Add EdgeFlow addon integration with context-aware pie menu (Shift+Alt+F)
- [x] Add Blender 4.2-5.2+ API compatibility fallbacks
- [x] Add dynamic optional dependency detection and integration status UI
- [x] Integrate configurable timeline scrub with viewport HUD and editor keymaps
