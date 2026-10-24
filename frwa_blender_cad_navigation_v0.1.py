# SPDX-License-Identifier: MIT
# FrWA Conception - Navigation type FreeCAD / CATIA pour Blender
#
# Gestes (pendant que la MOLETTE est maintenue enfoncee) :
#   - molette + deplacement ................ PAN (deplacement)
#   - molette + clic droit MAINTENU + drag . ORBITE (rotation)
#   - molette + clic droit COURT ........... bascule en mode ZOOM
#                                            (souris avant/arriere = zoom lisse)
#   - clic molette COURT (sans bouger) ..... recentre le pivot sous le curseur
#   - molette relachee ..................... fin du geste
#
# Le clic droit SEUL (sans molette) garde le comportement Blender par defaut
# (menu contextuel). Le clic gauche + drag reste la selection Blender par defaut.

bl_info = {
    "name": "FrWA CAD Navigation",
    "author": "FrWA Conception",
    "version": (0, 1, 0),
    "blender": (4, 2, 0),
    "location": "Vue 3D",
    "description": "Navigation souris type FreeCAD / CATIA (molette=pan, molette+droit=orbite/zoom)",
    "category": "3D View",
}

import time
import math

import bpy
from bpy.props import FloatProperty, BoolProperty
from mathutils import Vector, Quaternion


# --- Seuils pour distinguer un clic court d'un maintien --------------------
CLICK_TIME = 0.25   # secondes : au-dela, un appui droit est considere "maintenu"
CLICK_DIST = 6      # pixels    : mouvement tolere pour rester un "clic court"


def _prefs():
    return bpy.context.preferences.addons[__name__].preferences


class FRWA_OT_cad_navigation(bpy.types.Operator):
    """Navigation 3D type FreeCAD / CATIA (operateur modal)."""
    bl_idname = "view3d.frwa_cad_navigation"
    bl_label = "FrWA CAD Navigation"
    bl_options = {'BLOCKING'}

    # ------------------------------------------------------------------ invoke
    def invoke(self, context, event):
        if context.area is None or context.area.type != 'VIEW_3D':
            return {'CANCELLED'}
        self.rv3d = context.region_data
        self.region = context.region
        if self.rv3d is None or self.region is None:
            return {'CANCELLED'}

        self.mode = 'PAN'            # PAN | ORBIT | ZOOM
        self.last = (event.mouse_x, event.mouse_y)
        self.mmb_moved = False       # la souris a-t-elle bouge pendant le geste
        self.rmb_down = False
        self.rmb_ever = False        # le bouton droit a-t-il ete utilise
        self.rmb_moved = False
        self.rmb_press_time = 0.0
        self.rmb_press_pos = (0, 0)

        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    # ------------------------------------------------------------------- modal
    def modal(self, context, event):
        rv3d = self.rv3d

        if event.type == 'MOUSEMOVE':
            x, y = event.mouse_x, event.mouse_y
            dx = x - self.last[0]
            dy = y - self.last[1]
            self.last = (x, y)

            if dx or dy:
                self.mmb_moved = True
                if self.rmb_down:
                    self.rmb_moved = True

            if self.mode == 'PAN':
                self._pan(dx, dy)
            elif self.mode == 'ORBIT':
                self._orbit(dx, dy)
            elif self.mode == 'ZOOM':
                self._zoom(dy)

            if context.area:
                context.area.tag_redraw()
            return {'RUNNING_MODAL'}

        # --- bouton droit : maintenu = orbite, court = bascule zoom ----------
        if event.type == 'RIGHTMOUSE':
            if event.value == 'PRESS':
                self.rmb_down = True
                self.rmb_ever = True
                self.rmb_moved = False
                self.rmb_press_time = time.time()
                self.rmb_press_pos = (event.mouse_x, event.mouse_y)
                self.mode = 'ORBIT'          # a priori orbite tant qu'il est tenu
                return {'RUNNING_MODAL'}

            if event.value == 'RELEASE':
                self.rmb_down = False
                dt = time.time() - self.rmb_press_time
                dist = abs(event.mouse_x - self.rmb_press_pos[0]) + \
                       abs(event.mouse_y - self.rmb_press_pos[1])
                if dt < CLICK_TIME and dist < CLICK_DIST:
                    # clic droit COURT -> bascule zoom (re-clic -> retour pan)
                    self.mode = 'PAN' if self.mode == 'ZOOM' else 'ZOOM'
                else:
                    # c'etait un maintien (orbite) -> retour au pan
                    self.mode = 'PAN'
                return {'RUNNING_MODAL'}

        # --- fin du geste : relachement de la molette ------------------------
        if event.type == 'MIDDLEMOUSE' and event.value == 'RELEASE':
            if (not self.mmb_moved) and (not self.rmb_ever):
                # clic molette pur -> recentrage du pivot sous le curseur
                self._recenter()
            return {'FINISHED'}

        # la molette de defilement garde le zoom Blender par defaut
        if event.type in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}:
            return {'PASS_THROUGH'}

        if event.type == 'ESC':
            return {'FINISHED'}

        # on consomme le reste pour ne pas declencher d'action parasite
        return {'RUNNING_MODAL'}

    # --------------------------------------------------------------- actions
    def _pan(self, dx, dy):
        rv3d = self.rv3d
        p = _prefs()
        # unites monde par pixel a la profondeur du pivot (approximation)
        factor = (rv3d.view_distance / max(1, self.region.height)) * p.pan_sensitivity
        right = rv3d.view_rotation @ Vector((1.0, 0.0, 0.0))
        up = rv3d.view_rotation @ Vector((0.0, 1.0, 0.0))
        rv3d.view_location -= (right * dx + up * dy) * factor

    def _orbit(self, dx, dy):
        rv3d = self.rv3d
        p = _prefs()
        sens = 0.005 * p.orbit_sensitivity
        if p.invert_orbit_x:
            dx = -dx
        if p.invert_orbit_y:
            dy = -dy
        # turntable : lacet autour du Z monde, tangage autour du X local
        rot_z = Quaternion(Vector((0.0, 0.0, 1.0)), -dx * sens)
        axis_x = rv3d.view_rotation @ Vector((1.0, 0.0, 0.0))
        rot_x = Quaternion(axis_x, -dy * sens)
        rv3d.view_rotation = rot_z @ rot_x @ rv3d.view_rotation
        rv3d.view_rotation.normalize()

    def _zoom(self, dy):
        rv3d = self.rv3d
        p = _prefs()
        d = dy
        if p.invert_zoom:
            d = -d
        # zoom exponentiel -> sensation "lisse"
        factor = math.pow(1.01, -d * p.zoom_sensitivity)
        rv3d.view_distance = max(0.001, rv3d.view_distance * factor)

    def _recenter(self):
        try:
            bpy.ops.view3d.view_center_pick('INVOKE_DEFAULT')
        except Exception:
            pass


# --- Preferences (sensibilites reglables) ---------------------------------
class FRWA_CADNav_Prefs(bpy.types.AddonPreferences):
    bl_idname = __name__

    pan_sensitivity: FloatProperty(
        name="Sensibilite pan", default=2.0, min=0.05, max=20.0)
    orbit_sensitivity: FloatProperty(
        name="Sensibilite orbite", default=1.0, min=0.05, max=10.0)
    zoom_sensitivity: FloatProperty(
        name="Sensibilite zoom", default=1.0, min=0.05, max=10.0)
    invert_orbit_x: BoolProperty(name="Inverser orbite X", default=False)
    invert_orbit_y: BoolProperty(name="Inverser orbite Y", default=False)
    invert_zoom: BoolProperty(name="Inverser zoom", default=False)

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.prop(self, "pan_sensitivity")
        col.prop(self, "orbit_sensitivity")
        col.prop(self, "zoom_sensitivity")
        row = layout.row(align=True)
        row.prop(self, "invert_orbit_x", toggle=True)
        row.prop(self, "invert_orbit_y", toggle=True)
        row.prop(self, "invert_zoom", toggle=True)


# --- Enregistrement --------------------------------------------------------
addon_keymaps = []


def register():
    bpy.utils.register_class(FRWA_CADNav_Prefs)
    bpy.utils.register_class(FRWA_OT_cad_navigation)

    kc = bpy.context.window_manager.keyconfigs.addon
    if kc:
        km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')
        kmi = km.keymap_items.new(
            FRWA_OT_cad_navigation.bl_idname, 'MIDDLEMOUSE', 'PRESS')
        addon_keymaps.append((km, kmi))


def unregister():
    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()

    bpy.utils.unregister_class(FRWA_OT_cad_navigation)
    bpy.utils.unregister_class(FRWA_CADNav_Prefs)


if __name__ == "__main__":
    register()
