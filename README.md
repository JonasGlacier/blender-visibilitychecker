# Visibility Checker

Blender add-on for finding objects and collections whose **Disable in Viewports** and **Disable in Renders** restriction flags differ.

It compares only these direct RNA properties:

- `hide_viewport`
- `hide_render`

It deliberately does not read or change the Outliner eye icon (`Hide in Viewport` / `hide_set()`), View Layer visibility, or Layer Collection exclusion.

## Install

1. In Blender, open **Edit > Preferences > Add-ons**.
2. Click the drop-down beside **Install...** and select `visibility_checker.py`.
3. Enable **Scene: Visibility Checker**.
4. In a 3D Viewport, press `N` and open the **CHECK VISIBILITY** tab.

## Use

1. Click **Refresh** to scan the current scene.
2. Review mismatched Objects and Collections in the panel.
3. Click **Match Render** for an individual item, or **Fix All** to set every item's `hide_render` equal to its `hide_viewport` value.

Linked data that cannot be edited is skipped and reported by Blender.
