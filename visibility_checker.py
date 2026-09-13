bl_info = {
    "name": "Visibility Checker",
    "author": "OpenCode",
    "version": (1, 0, 0),
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar > CHECK VISIBILITY",
    "description": "Find and synchronize viewport and render restriction flags",
    "category": "Scene",
}

import bpy
from bpy.props import BoolProperty, CollectionProperty, EnumProperty, PointerProperty, StringProperty
from bpy.types import Operator, Panel, PropertyGroup


def scene_collections(scene):
    """Return the non-root collections reachable from this scene."""
    collections = []
    seen = set()

    def visit(parent):
        for child in parent.children:
            pointer = child.as_pointer()
            if pointer not in seen:
                seen.add(pointer)
                collections.append(child)
                visit(child)

    visit(scene.collection)
    return collections


def refresh_issues(scene):
    settings = scene.visibility_checker
    settings.issues.clear()
    settings.has_scanned = True

    for obj in scene.objects:
        if obj.hide_viewport != obj.hide_render:
            issue = settings.issues.add()
            issue.item_type = 'OBJECT'
            issue.name = obj.name
            issue.object = obj

    for collection in scene_collections(scene):
        if collection.hide_viewport != collection.hide_render:
            issue = settings.issues.add()
            issue.item_type = 'COLLECTION'
            issue.name = collection.name
            issue.collection = collection


def item_from_issue(issue):
    if issue.item_type == 'OBJECT':
        return issue.object
    return issue.collection


class VISIBILITYCHECKER_PG_issue(PropertyGroup):
    item_type: EnumProperty(
        items=(
            ('OBJECT', "Object", ""),
            ('COLLECTION', "Collection", ""),
        )
    )
    object: PointerProperty(type=bpy.types.Object)
    collection: PointerProperty(type=bpy.types.Collection)
    name: StringProperty()


class VISIBILITYCHECKER_PG_scene_settings(PropertyGroup):
    issues: CollectionProperty(type=VISIBILITYCHECKER_PG_issue)
    has_scanned: BoolProperty(default=False)


class VISIBILITYCHECKER_OT_refresh(Operator):
    bl_idname = "visibility_checker.refresh"
    bl_label = "Refresh Visibility Check"
    bl_description = "Scan this scene for mismatched viewport and render restriction flags"

    def execute(self, context):
        refresh_issues(context.scene)
        count = len(context.scene.visibility_checker.issues)
        self.report({'INFO'}, f"Found {count} visibility mismatch(es)")
        return {'FINISHED'}


class VISIBILITYCHECKER_OT_sync_all(Operator):
    bl_idname = "visibility_checker.sync_all"
    bl_label = "Match Render to Viewport"
    bl_description = "Set Disable in Renders to match Disable in Viewports for all scene objects and collections"

    def execute(self, context):
        scene = context.scene
        updated = 0
        skipped = 0
        updated_objects = []

        for item in [*scene.objects, *scene_collections(scene)]:
            if item.hide_viewport == item.hide_render:
                continue
            try:
                item.hide_render = item.hide_viewport
                updated += 1
                if isinstance(item, bpy.types.Object):
                    updated_objects.append(item)
            except RuntimeError:
                # Linked data may not be editable in the current file.
                skipped += 1

        selectable_objects = []
        for obj in updated_objects:
            if not obj.visible_get(view_layer=context.view_layer):
                continue
            try:
                obj.hide_select = False
                selectable_objects.append(obj)
            except RuntimeError:
                skipped += 1

        if selectable_objects:
            for obj in context.selected_objects:
                obj.select_set(False)
            for obj in selectable_objects:
                obj.select_set(True)
            context.view_layer.objects.active = selectable_objects[0]

        refresh_issues(scene)
        message = f"Synchronized {updated} item(s)"
        if selectable_objects:
            message += f"; selected {len(selectable_objects)} visible object(s)"
        if skipped:
            message += f"; skipped {skipped} non-editable item(s)"
        self.report({'INFO'}, message)
        return {'FINISHED'}


class VISIBILITYCHECKER_OT_sync_one(Operator):
    bl_idname = "visibility_checker.sync_one"
    bl_label = "Match Render to Viewport"
    bl_description = "Set this item's Disable in Renders flag to its Disable in Viewports flag"

    item_type: EnumProperty(items=(('OBJECT', "Object", ""), ('COLLECTION', "Collection", "")))
    item_name: StringProperty()

    def execute(self, context):
        item = (
            bpy.data.objects.get(self.item_name)
            if self.item_type == 'OBJECT'
            else bpy.data.collections.get(self.item_name)
        )
        if item is None:
            self.report({'WARNING'}, "Item no longer exists")
            refresh_issues(context.scene)
            return {'CANCELLED'}

        try:
            item.hide_render = item.hide_viewport
        except RuntimeError:
            self.report({'ERROR'}, "Item is not editable")
            return {'CANCELLED'}

        refresh_issues(context.scene)
        return {'FINISHED'}


class VISIBILITYCHECKER_OT_select_object(Operator):
    bl_idname = "visibility_checker.select_object"
    bl_label = "Select Object"
    bl_description = "Select this object in the active view layer"

    object_name: StringProperty()

    def execute(self, context):
        obj = bpy.data.objects.get(self.object_name)
        if obj is None or context.view_layer.objects.get(obj.name) is None:
            self.report({'WARNING'}, "Object is not available in the active view layer")
            return {'CANCELLED'}

        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        context.view_layer.objects.active = obj
        return {'FINISHED'}


class VISIBILITYCHECKER_PT_panel(Panel):
    bl_label = "Visibility Checker"
    bl_idname = "VISIBILITYCHECKER_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "CHECK VISIBILITY"

    def draw(self, context):
        layout = self.layout
        settings = context.scene.visibility_checker

        controls = layout.row(align=True)
        controls.operator(VISIBILITYCHECKER_OT_refresh.bl_idname, text="Refresh", icon='FILE_REFRESH')
        controls.operator(VISIBILITYCHECKER_OT_sync_all.bl_idname, text="Fix All", icon='CHECKMARK')

        if not settings.issues:
            text = "No mismatches found." if settings.has_scanned else "Click Refresh to scan this scene."
            layout.label(text=text, icon='CHECKMARK' if settings.has_scanned else 'INFO')
            return

        layout.label(text=f"{len(settings.issues)} mismatch(es)", icon='ERROR')
        for issue in settings.issues:
            item = item_from_issue(issue)
            if item is None:
                continue

            box = layout.box()
            header = box.row(align=True)
            icon = 'OBJECT_DATA' if issue.item_type == 'OBJECT' else 'OUTLINER_COLLECTION'
            header.label(text=issue.name, icon=icon)
            header.label(text=issue.item_type.title())

            states = box.row(align=True)
            states.label(
                text="Viewport: Disabled" if item.hide_viewport else "Viewport: Enabled",
                icon='RESTRICT_VIEW_ON' if item.hide_viewport else 'RESTRICT_VIEW_OFF',
            )
            states.label(
                text="Render: Disabled" if item.hide_render else "Render: Enabled",
                icon='RESTRICT_RENDER_ON' if item.hide_render else 'RESTRICT_RENDER_OFF',
            )

            actions = box.row(align=True)
            sync = actions.operator(VISIBILITYCHECKER_OT_sync_one.bl_idname, text="Match Render")
            sync.item_type = issue.item_type
            sync.item_name = issue.name
            if issue.item_type == 'OBJECT':
                select = actions.operator(VISIBILITYCHECKER_OT_select_object.bl_idname, text="Select")
                select.object_name = issue.name


classes = (
    VISIBILITYCHECKER_PG_issue,
    VISIBILITYCHECKER_PG_scene_settings,
    VISIBILITYCHECKER_OT_refresh,
    VISIBILITYCHECKER_OT_sync_all,
    VISIBILITYCHECKER_OT_sync_one,
    VISIBILITYCHECKER_OT_select_object,
    VISIBILITYCHECKER_PT_panel,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.visibility_checker = PointerProperty(type=VISIBILITYCHECKER_PG_scene_settings)


def unregister():
    del bpy.types.Scene.visibility_checker
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
