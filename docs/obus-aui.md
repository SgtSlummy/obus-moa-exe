# OBus AUI

OBus AUI is the local application interface for routing, inspecting, and operating the OccultBus runtime. It is inspired by useful WarpUI patterns—action-first interaction, block-oriented output, predictable focus, and explicit accessibility announcements—but is implemented with OBus's FastAPI and static web stack.

## Surfaces

- Terminal: route composer, live route blocks, recent receipts, read-only workspace context, and the command palette.
- Operator: Terminal plus Cards & Keys, Tarot agents, persistent runtime jobs, Rooms, receipts, studios, routing, and memory.
- ADE: Operator plus Forums, Arcana Forge, and Tentacle Worm safety/hardening.

The public action contract is served by:

`GET /api/aui/manifest?surface=terminal|operator|ade`

The response is secret-free and contains stable action IDs, labels, hints, shortcuts, target controls, surface minimums, accessibility view metadata, and keyboard principles.

## Keyboard map

| Shortcut | Function |
|---|---|
| Ctrl/Cmd+K | Open the command palette |
| Ctrl/Cmd+Shift+P | Open the command palette using the alternate shortcut |
| Ctrl/Cmd+L | Focus the route composer |
| Ctrl/Cmd+R | Refresh live state |
| Enter | Run the current route |
| Shift+Enter | Insert a newline in the route composer |
| Escape | Close transient UI or return focus to the route composer |

The command palette is backed by the AUI manifest and includes navigation, runtime, workspace, receipt, route, provider, room, studio, Forge, and safety actions.

## Route blocks

A route is presented as an inspectable block containing:

- selected deck and temporary card/Key assignments;
- execution-scope information;
- specialist, synthesis, verification, and aggregate stages;
- redacted receipt state and usage metadata;
- formatted/plain output modes;
- copy, bookmark, export, re-input, and retry controls.

Re-input and retry use the latest prompt held in the current browser session. Raw prompt text is not written into public receipts by this UI feature.

Route lifecycle events are available through the bounded JSON endpoint `/api/route/events` and the loopback SSE endpoint `/api/route/events/stream`. Events contain only route IDs and safe lifecycle metadata such as planning, local start/completion, completion, and failure state. The frontend uses EventSource when available and retains polling as the fallback.

Cancellation is cooperative and confirmed: the frontend supplies a route ID, `POST /api/route/{route_id}/cancel` records the request, and the backend acknowledges it at planning/local stage boundaries. `GET /api/route/{route_id}/status` exposes the cancellation state and bounded event history. Provider threads are not force-killed.

## Responsive ergonomics

The Run workbench supports:

- collapsible sidebar;
- compact, comfortable, and spacious density modes;
- viewport-mode tracking through `ResizeObserver`;
- wide, medium, narrow, and phone layout behavior;
- collapsed action rail and stacked terminal inspector behavior on small windows;
- reduced-motion behavior through `prefers-reduced-motion`.

Density and sidebar preferences are local browser UI preferences. They do not alter provider state or runtime routing policy.

## Accessibility

AUI surfaces use semantic landmarks, live regions, visible focus states, keyboard shortcuts, and structured value/role/help metadata. The route output and workspace tree are announced as stateful regions. Workspace files remain bounded and read-only; filtering only narrows the already-safe tree returned by the backend.

## Privacy and licensing boundary

OBus does not embed Warp's Rust UI implementation or copy proprietary screens/assets. Warp remains an optional local companion through `backend/warp_companion.py`. OBus's AUI never accepts credential values, OAuth tokens, private keys, or provider secrets.
