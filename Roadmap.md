# Pie Menus Plus - Roadmap

This document outlines future improvements and development goals for Pie Menus Plus.

## Keymap System Improvements

- [ ] Add user-defined keymap profiles (save/load keymap configurations)
- [ ] Implement keymap conflict detection and resolution
- [ ] Add keyboard shortcut editor in preferences

## Addon Integration Robustness

- [ ] Add dynamic addon detection (scan for installed addons and adapt UI)
- [ ] Create fallback UI when integrated addons aren't available
- [ ] Add optional dependency checks at startup

## UI/UX Enhancements

- [ ] Add customizable pie menu themes (colors, icons)
- [ ] Implement pie menu preview/editor
- [ ] Add context-aware menu filtering based on selection/mode

## Completed

- [x] Replace deprecated `paint.brush_select` operator with Blender 5.0+ brush asset API
- [x] Implement preferences-based custom sculpt brush system
- [x] Move custom sculpt brushes to keymaps section
- [x] Fix LoopTools and BoolTool detection to use operator existence checks
- [x] Remove external links and author references for clean distribution
- [x] Fix rna_keymap_ui implementation for Blender 5.0+
