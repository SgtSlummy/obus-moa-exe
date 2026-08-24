# OBus AUI Research and Design Provenance

Date: 2026-08-24

## Scope

This note records the design patterns used for the OBus AUI upgrade. OBus adopts interaction principles only; it does not copy Warp source, brand assets, proprietary screens, or provider behavior.

## Local Warp source evidence

Source root: `third_party/warpdotdev-warp/`

- `crates/warpui_core/src/core/app.rs`: app-owned views, action dispatch, focus, invalidation, foreground/background tasks, and window lifecycle are treated as first-class runtime concerns.
- `crates/warpui_core/src/actions.rs`: platform actions are separated from application-specific actions.
- `crates/warpui_core/src/accessibility.rs`: accessibility content is structured as concise `value`, optional `help`, and a semantic `role`; announcements cover focused views, performed actions, and background events.
- `crates/warpui_core/src/keymap.rs`: bindings carry descriptions and context; discoverability and deterministic precedence matter as much as the key itself.

## Public reference research

Sources retrieved through agent-reach/Exa on 2026-08-24:

- Warp Command Palette: https://docs.warp.dev/terminal/command-palette/
  - Global search should find actions, settings, workflows, sessions, and other workspace objects.
  - Search results benefit from type filters rather than one undifferentiated list.
- Warp Accessibility: https://docs.warp.dev/terminal/more-features/accessibility/
  - The command input and output history form the primary interaction model.
  - Blocks are independently navigable and meaningful state changes are announced.
  - Accessibility actions should be discoverable from the command palette.
- Warp Keyboard Shortcuts: https://docs.warp.dev/getting-started/keyboard-shortcuts/
  - Input focus, command palette, block navigation, pane navigation, resize, bookmarks, copy, and accessibility verbosity are explicit actions.
  - Shortcuts are searchable and remappable rather than hidden in documentation.
- Warp Terminal Blocks: https://docs.warp.dev/terminal/blocks/
  - A block groups command and output atomically and supports copy, search, filtering, bookmarking, sharing, and navigation.
- Warp modern terminal overview: https://www.warp.dev/modern-terminal
  - IDE-like editing, structured output, command search, and keyboard-first operation are core differentiators.

## Adopted OBus principles

1. AUI actions are data: each action has a stable ID, label, hint, shortcut, target, surface minimum, and handler.
2. Route results are blocks: prompt, plan, specialists, synthesis, verification, aggregate, receipt, and status remain inspectable.
3. Focus is predictable: Ctrl/Cmd+K and Ctrl/Cmd+Shift+P open actions; Ctrl/Cmd+L focuses routing; Escape returns to routing when no modal is open.
4. Accessibility is explicit: OBus exposes value/role/help metadata and live-region announcements without exposing private transcripts or credentials.
5. Information density is progressive: glanceable status first, detailed traces and configuration behind expandable/secondary surfaces.
6. Responsive layout is operational: sidebar, inspector, and action rail collapse or resize based on available width rather than using a fixed desktop canvas.
7. OBus remains original: Tarot personas, Solomon's Keys, Chymeria, local-first routing, and Tentacle Worm safety remain the product identity.

## Rejected or adapted patterns

- No copied Warp UI framework or Rust implementation.
- No provider credential fields or remote account workflows in the AUI.
- No decorative dashboard metrics without a corresponding live OBus value.
- No hero-style marketing composition for operational screens.
- Warp's platform-specific VoiceOver terminology is adapted to browser/Windows semantics using ARIA roles, live regions, visible focus, and keyboard actions.

## Design direction

Primary surface: **Command / Inspect** for the Run workbench, with **Monitor** behavior for live route status and **Operate** behavior for Keys, agents, Rooms, and safety. Use dark neutral surfaces, one cyan operational accent, gold Tarot/decision accents, semantic green/warn/error states, compact monospace metadata, progressive disclosure, and responsive pane composition.
