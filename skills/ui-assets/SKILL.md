---
name: ui-assets
title: UI Assets Management
description: Guidance for managing UI asset files and updating dropdown icons in the OBus interface.
tags: [ui, assets, design]
---

# Purpose
This skill covers the steps required to add, update, and reference visual assets used in the OBus UI—including placeholder icons for keys and tarot cards, cleaning up dropdown menus, and ensuring consistent styling across the application.

## How to use
- Load this skill when you need to modify icon references or add new assets.
- The skill uses the `references/` folder to store explanation documents, and the `templates/` folder for example SVG files.

## Example
- Add `assets/card-placeholder.svg` and `assets/key-placeholder.svg` as shown in the implementation.
- Update the HTML template in `build/index-head.html` to reference these images.
