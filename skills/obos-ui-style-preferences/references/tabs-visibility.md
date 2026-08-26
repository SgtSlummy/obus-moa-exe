# tabs-visibility.md

**Issue**
During recent sessions the OBus UI sidebar navigation tabs were disappearing because the `data-sidebar-collapsed` attribute on the `<body>` element was accidentally set to true on page reloads. The navigation container is rendered behind the attribute, so the entire nav pane was hidden.

**Fix**
Add the following CSS rule to the UI stylesheet where the root variables are defined or bundle it in the style change:

```css
body[data-sidebar-collapsed="false"] .side{display:block!important;}
```

This rule forces the `.side` element to be displayed once the body no longer indicates a collapsed state. It preserves the manual toggle behaviour because the attribute change is still respected when set to `true`.

**How to apply**
Place it *before* the `:root{...}` block in the UI page's `<style>` tag or in a dedicated CSS file loaded by the page.

**Result**
The sidebar navigation no longer disappears on page reload; users can toggle it manually as before.
