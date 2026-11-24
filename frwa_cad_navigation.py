# SPDX-License-Identifier: MIT
# FrWA Conception - Navigation type FreeCAD / CATIA pour Blender
#
# Gestes hors outil (molette = bouton du milieu) :
#   - molette maintenue + deplacement ........ PAN (deplacement)
#   - molette + clic droit MAINTENU + drag ... ORBITE (rotation)
#   - molette + clic droit COURT ............. bascule ZOOM <-> PAN
#   - clic molette COURT (sans bouger) ....... recentre le pivot sous le curseur
#   - Shift + molette ........................ ORBITE (sans clic droit)
#   - Ctrl + molette ......................... ZOOM
#   - roulette ............................... zoom Blender
#
# PENDANT un outil en cours (G, R, S, Extrude E, gizmos, couteau K...) :
#   - molette ................................ PAN
#   - Shift + molette ........................ ORBITE
#   - Ctrl + molette ......................... ZOOM
#   (le clic droit reste "annuler" dans les outils Blender : on ne l'utilise
#    donc pas pour orbiter pendant un outil)
#
# Le clic droit SEUL garde le menu contextuel. Le clic gauche reste la
# selection Blender par defaut.
#
# Limite de Blender : Bevel, Inset et Loop Cut ne permettent aucune
# navigation PENDANT le reglage (meme sans l'extension). Valider l'outil puis
# ajuster dans le panneau "Ajuster la derniere operation".
#
# v0.2.0 (corrections) :
#   - la molette des OUTILS (Move, Rotate, Extrude, Knife... en carte
#     Industry Compatible) ne vole plus la navigation : avant, un clic molette
#     lancait un deplacement invisible et le clic gauche suivant (selection
#     d'arete, panneau de reglages) ne faisait que le valider ;
#   - navigation possible pendant un deplacement / une coupe au couteau ;
#   - le geste ne reste plus "colle" si la fenetre perd le focus (alt-tab)
#     et un clic / une touche le termine sans etre perdu ;
#   - le re-clic droit court revient bien du zoom au pan.
#
# v0.3.0 (bugs trouves en rejouant le tuto "Fantome tirelire") :
#   - pan exact : l'objet suit le curseur 1:1 (avant : 2,5x trop vite) ;
#   - orbite depuis une vue Face/Dessus (F1, F3...) : repasse en perspective ;
#   - respecte les preferences Blender "Orbit Around Selection",
#     "Zoom to Mouse Position", "Auto Depth", Turntable/Trackball et la
#     sensibilite d'orbite (meme sens et meme vitesse que Blender) ;
#   - un geste juste apres F / clic molette n'est plus annule par
#     l'animation de cadrage ;
#   - vue camera : orbiter la quitte, le pan decale le cadrage, le zoom
#     zoome dans le cadre ; avec "Camera to View", la camera est deplacee ;
#   - quad view : les vues verrouillees ne tournent plus (pan/zoom
#     synchronises si "Sync" est coche).

bl_info = {
    "name": "FrWA CAD Navigation",
    "author": "FrWA Conception",
    "version": (0, 3, 0),
    "blender": (4, 2, 0),
    "location": "Vue 3D",
    "description": "Navigation souris type FreeCAD / CATIA (molette=pan, molette+droit=orbite/zoom)",
    "category": "3D View",
}

import time
import math

import bpy
from bpy.props import FloatProperty, BoolProperty
from bpy.app.handlers import persistent
from mathutils import Vector, Quaternion


# --- Seuils pour distinguer un clic court d'un maintien --------------------
CLICK_TIME = 0.25   # secondes : au-dela, un appui droit est considere "maintenu"
CLICK_DIST = 6      # pixels    : mouvement tolere pour rester un "clic court"

# Touches de modification : on les ignore pendant un geste (pas de fin de geste)
_MODIFIER_KEYS = {
    'LEFT_SHIFT', 'RIGHT_SHIFT', 'LEFT_CTRL', 'RIGHT_CTRL',
    'LEFT_ALT', 'RIGHT_ALT', 'OSKEY', 'HYPER',
}
# Evenements "systeme" a laisser passer sans rien faire
_PASS_EVENTS = {
    'TIMER', 'TIMER0', 'TIMER1', 'TIMER2', 'TIMER_JOBS', 'TIMER_AUTOSAVE',
    'TIMER_REPORT', 'TIMERREGION', 'NONE', 'WINDOW_DEACTIVATE',
    'ACTIONZONE_AREA', 'ACTIONZONE_REGION', 'ACTIONZONE_FULLSCREEN',
    'XR_ACTION',
}

# Elements de la carte modale "Transform Modal Map" qui empechent de
# naviguer a la molette pendant G / R / S / Extrude / gizmos :
#   - PASSTHROUGH_NAVIGATE : navigation seulement avec Alt enfonce
#   - AUTOCONSTRAIN(PLANE) : la molette sert a contraindre l'axe
_TRANSFORM_MODAL_ITEMS = {'PASSTHROUGH_NAVIGATE', 'AUTOCONSTRAIN', 'AUTOCONSTRAINPLANE'}


def _prefs():
    addon = bpy.context.preferences.addons.get(__name__)
    return addon.preferences if addon else None


class _DefaultPrefs:
    pan_speed = 1.0
    orbit_sensitivity = 1.0
    zoom_sensitivity = 1.0
    invert_orbit_x = False
    invert_orbit_y = False
    invert_zoom = False
    tool_navigation = True
    tool_mmb_override = True


def _p():
    return _prefs() or _DefaultPrefs


def _selection_center(context):
    """Centre de la selection (comme "Orbit Around Selection" de Blender)."""
    obj = context.edit_object
    if obj is not None and obj.type == 'MESH':
        try:
            import bmesh
            bm = bmesh.from_edit_mesh(obj.data)
            cos = [v.co for v in bm.verts if v.select]
            if cos:
                return obj.matrix_world @ (sum(cos, Vector()) / len(cos))
        except Exception:
            pass
    sel = getattr(context, "selected_objects", None) or []
    if sel:
        return sum((o.matrix_world.translation for o in sel), Vector()) / len(sel)
    return None


class FRWA_OT_cad_navigation(bpy.types.Operator):
    """Navigation 3D type FreeCAD / CATIA (operateur modal)."""
    bl_idname = "view3d.frwa_cad_navigation"
    bl_label = "FrWA CAD Navigation"
    bl_options = {'BLOCKING'}

    # ------------------------------------------------------------------ invoke
    def invoke(self, context, event):
        if context.area is None or context.area.type != 'VIEW_3D':
            return {'PASS_THROUGH'}
        self.rv3d = context.region_data
        self.region = context.region
        self.area = context.area
        self.space = context.space_data
        if self.rv3d is None or self.region is None:
            return {'PASS_THROUGH'}

        self._finish_smooth_view()
        self._start_gesture(context, event)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def _finish_smooth_view(self):
        """Termine une animation de vue en cours (F, clic molette, vues F1...).

        Sinon l'animation ecrase le geste qui commence juste apres.
        view_roll(0) est le seul operateur expose a Python qui force la fin de
        l'animation ; il efface l'etat "vue de face/dessus", qu'on restaure.
        """
        rv3d = self.rv3d
        if rv3d.view_perspective == 'CAMERA' or rv3d.lock_rotation:
            return
        side = rv3d.is_orthographic_side_view
        try:
            bpy.ops.view3d.view_roll(angle=0.0, type='ANGLE')
        except Exception:
            return
        if side and not rv3d.is_orthographic_side_view:
            try:
                rv3d.is_orthographic_side_view = True
            except Exception:
                pass

    def _start_gesture(self, context, event):
        rv3d = self.rv3d
        self.mode = 'PAN'            # PAN | ORBIT | ZOOM
        self.mode_before_rmb = 'PAN'
        self.last = (event.mouse_x, event.mouse_y)
        self.mmb_moved = False       # la souris a-t-elle bouge pendant le geste
        self.rmb_down = False
        self.rmb_ever = False        # le bouton droit a-t-il ete utilise
        self.rmb_press_time = 0.0
        self.rmb_press_pos = (0, 0)
        # vue de face/dessus... en ortho automatique -> perspective a l'orbite
        self.side_view = (rv3d.view_perspective == 'ORTHO'
                          and rv3d.is_orthographic_side_view)
        # vue camera verrouillee ("Camera to View") : on deplace la camera
        self.camera = None
        if rv3d.view_perspective == 'CAMERA':
            cam = self._scene_camera(context)
            if cam is not None and self.space.lock_camera:
                self.camera = cam
        # pivot d'orbite et profondeur de travail (preferences Blender)
        inputs = context.preferences.inputs
        self.pivot = None
        self.depth_point = None
        if rv3d.view_perspective != 'CAMERA' or self.camera is not None:
            if inputs.use_mouse_depth_navigate:
                hit = self._raycast(context, event)
                if hit is not None:
                    self.pivot = hit
                    self.depth_point = hit
            if inputs.use_rotate_around_active:
                c = _selection_center(context)
                if c is not None:
                    self.pivot = c
        self.zoom_target = None
        self.pan_anchor = None

    def _scene_camera(self, context):
        sp = self.space
        if getattr(sp, "use_local_camera", False) and sp.camera is not None:
            return sp.camera
        return context.scene.camera

    def _raycast(self, context, event):
        from bpy_extras.view3d_utils import region_2d_to_origin_3d, region_2d_to_vector_3d
        co = (event.mouse_x - self.region.x, event.mouse_y - self.region.y)
        try:
            origin = region_2d_to_origin_3d(self.region, self.rv3d, co)
            vec = region_2d_to_vector_3d(self.region, self.rv3d, co)
            hit, loc, *_ = context.scene.ray_cast(
                context.evaluated_depsgraph_get(), origin, vec)
            return loc.copy() if hit else None
        except Exception:
            return None

    def _finish(self):
        try:
            self.area.tag_redraw()
        except Exception:
            pass
        return {'FINISHED'}

    # ------------------------------------------------------------------- modal
    def modal(self, context, event):
        etype = event.type
        evalue = event.value

        try:
            # la vue 3D a pu etre fermee / changee pendant le geste
            if self.area.type != 'VIEW_3D':
                return {'CANCELLED'}
        except ReferenceError:
            return {'CANCELLED'}

        if etype in {'MOUSEMOVE', 'INBETWEEN_MOUSEMOVE'}:
            x, y = event.mouse_x, event.mouse_y
            dx = x - self.last[0]
            dy = y - self.last[1]
            self.last = (x, y)

            if dx or dy:
                self.mmb_moved = True
                rx, ry = x - self.region.x, y - self.region.y
                if self.mode == 'PAN':
                    self._pan(rx, ry, dx, dy)
                elif self.mode == 'ORBIT':
                    self._orbit(context, dx, dy)
                elif self.mode == 'ZOOM':
                    self._zoom(context, rx, ry, dy)
                self._sync_quad()
                self.area.tag_redraw()
            return {'RUNNING_MODAL'}

        # --- bouton droit : maintenu = orbite, court = bascule zoom ----------
        if etype == 'RIGHTMOUSE':
            if evalue in {'PRESS', 'DOUBLE_CLICK'}:
                self.rmb_down = True
                self.rmb_ever = True
                self.rmb_press_time = time.time()
                self.rmb_press_pos = (event.mouse_x, event.mouse_y)
                self.mode_before_rmb = self.mode
                self.mode = 'ORBIT'          # a priori orbite tant qu'il est tenu
                self.pan_anchor = None
                return {'RUNNING_MODAL'}

            if evalue == 'RELEASE':
                if not self.rmb_down:
                    return {'RUNNING_MODAL'}
                self.rmb_down = False
                dt = time.time() - self.rmb_press_time
                dist = abs(event.mouse_x - self.rmb_press_pos[0]) + \
                    abs(event.mouse_y - self.rmb_press_pos[1])
                if dt < CLICK_TIME and dist < CLICK_DIST:
                    # clic droit COURT -> bascule zoom (re-clic -> retour pan)
                    self.mode = 'PAN' if self.mode_before_rmb == 'ZOOM' else 'ZOOM'
                    self.zoom_target = None     # recalcule au 1er mouvement
                else:
                    # c'etait un maintien (orbite) -> retour au pan
                    self.mode = 'PAN'
                self.pan_anchor = None
                return {'RUNNING_MODAL'}
            return {'RUNNING_MODAL'}

        if etype == 'MIDDLEMOUSE':
            # --- fin du geste : relachement de la molette --------------------
            if evalue == 'RELEASE':
                if (not self.mmb_moved) and (not self.rmb_ever):
                    # clic molette pur -> recentrage du pivot sous le curseur
                    self._recenter(context)
                return self._finish()
            # nouvel appui alors qu'on n'a jamais recu le relachement
            # (fenetre quittee, alt-tab...) : on repart sur un geste neuf
            if evalue in {'PRESS', 'DOUBLE_CLICK'}:
                self._start_gesture(context, event)
            return {'RUNNING_MODAL'}

        # --- securites : ne jamais rester "colle" ----------------------------
        # La fenetre perd le focus : le relachement de la molette sera perdu.
        if etype == 'WINDOW_DEACTIVATE':
            self._finish()
            return {'CANCELLED', 'PASS_THROUGH'}

        if etype == 'ESC':
            return self._finish()

        # Un clic gauche / une touche pendant le geste = le relachement de la
        # molette a ete perdu. On termine ET on laisse passer l'evenement pour
        # que la selection / le raccourci fonctionne normalement.
        # (CANCELLED + PASS_THROUGH : avec FINISHED, Blender ne genere pas le
        #  "clic" de selection derriere et le premier clic serait perdu.)
        if etype == 'LEFTMOUSE' or (
                evalue == 'PRESS' and etype not in _MODIFIER_KEYS
                and not etype.startswith(('WHEEL', 'TRACKPAD', 'NDOF', 'EVT_', 'TIMER'))):
            self._finish()
            return {'CANCELLED', 'PASS_THROUGH'}

        # la roulette garde le zoom Blender par defaut ; evenements systeme
        if etype.startswith(('WHEEL', 'TRACKPAD', 'NDOF')) or etype in _PASS_EVENTS:
            return {'PASS_THROUGH'}

        # le reste (relachement de touches, modificateurs...) est ignore
        return {'RUNNING_MODAL'}

    def cancel(self, context):
        try:
            self.area.tag_redraw()
        except Exception:
            pass

    # --------------------------------------------------- etat de vue virtuel
    # En vue camera verrouillee ("Camera to View"), on deplace la camera ;
    # sinon la vue elle-meme.
    def _view_get(self):
        rv3d = self.rv3d
        if self.camera is not None:
            mw = self.camera.matrix_world
            rot = mw.to_quaternion()
            dist = rv3d.view_distance
            loc = mw.translation - rot @ Vector((0.0, 0.0, dist))
            return loc, rot, dist
        return rv3d.view_location.copy(), rv3d.view_rotation.copy(), rv3d.view_distance

    def _view_set(self, loc, rot, dist):
        rv3d = self.rv3d
        if self.camera is not None:
            from mathutils import Matrix
            cam = self.camera
            scale = cam.matrix_world.to_scale()
            pos = loc + rot @ Vector((0.0, 0.0, dist))
            cam.matrix_world = Matrix.LocRotScale(pos, rot, scale)
            rv3d.view_distance = dist
            return
        rv3d.view_rotation = rot
        rv3d.view_location = loc
        rv3d.view_distance = dist

    def _camera_view_unlocked(self):
        return self.rv3d.view_perspective == 'CAMERA' and self.camera is None

    def _leave_camera_view(self, context):
        """Orbiter depuis la vue camera la quitte (comme Blender)."""
        rv3d = self.rv3d
        cam = self._scene_camera(context)
        rv3d.view_perspective = 'PERSP'
        if cam is not None:
            mw = cam.matrix_world
            rot = mw.to_quaternion()
            rv3d.view_rotation = rot
            rv3d.view_location = mw.translation - rot @ Vector((0.0, 0.0, rv3d.view_distance))

    # --------------------------------------------------------------- actions
    def _pan(self, rx, ry, dx, dy):
        from bpy_extras.view3d_utils import region_2d_to_location_3d
        rv3d = self.rv3d
        p = _p()
        if self._camera_view_unlocked():
            # vue camera : on decale le cadrage (meme formule que Blender)
            zoomfac = ((math.sqrt(2.0) + rv3d.view_camera_zoom / 50.0) ** 2) / 4.0 * 2.0
            off = rv3d.view_camera_offset
            rv3d.view_camera_offset = (
                off[0] - dx * p.pan_speed / (self.region.width * zoomfac),
                off[1] - dy * p.pan_speed / (self.region.height * zoomfac))
            return
        loc, rot, dist = self._view_get()
        if self.pan_anchor is None:
            # Ancrage au debut du pan : vecteurs monde d'un pixel a la
            # profondeur du point vise (relation affine exacte en perspective
            # comme en ortho, tant que la vue ne fait que translater).
            depth = self.depth_point if self.depth_point is not None else loc
            sx, sy = rx - dx, ry - dy
            o = region_2d_to_location_3d(self.region, rv3d, (sx, sy), depth)
            ex = region_2d_to_location_3d(self.region, rv3d, (sx + 100, sy), depth)
            ey = region_2d_to_location_3d(self.region, rv3d, (sx, sy + 100), depth)
            if o is None or ex is None or ey is None:
                return
            self.pan_anchor = ((sx, sy), loc.copy(), (ex - o) / 100.0, (ey - o) / 100.0)
        (sx, sy), loc0, ex, ey = self.pan_anchor
        # deplacement exact : le point sous le curseur suit la souris (1:1)
        delta = ex * (rx - sx) + ey * (ry - sy)
        self._view_set(loc0 - delta * p.pan_speed, rot, dist)

    def _orbit(self, context, dx, dy):
        rv3d = self.rv3d
        if rv3d.lock_rotation:
            return                      # quad view : vues Dessus/Face/Droite fixes
        if self._camera_view_unlocked():
            self._leave_camera_view(context)
        p = _p()
        inputs = context.preferences.inputs
        if p.invert_orbit_x:
            dx = -dx
        if p.invert_orbit_y:
            dy = -dy
        loc, rot, dist = self._view_get()
        if inputs.view_rotate_method == 'TRACKBALL':
            sens = 0.007 * inputs.view_rotate_sensitivity_trackball * p.orbit_sensitivity
            q = Quaternion(rot @ Vector((0.0, 1.0, 0.0)), -dx * sens) @ \
                Quaternion(rot @ Vector((1.0, 0.0, 0.0)), -dy * sens)
        else:
            # turntable : lacet autour du Z monde, tangage autour du X local
            sens = inputs.view_rotate_sensitivity_turntable * p.orbit_sensitivity
            q = Quaternion(Vector((0.0, 0.0, 1.0)), -dx * sens) @ \
                Quaternion(rot @ Vector((1.0, 0.0, 0.0)), -dy * sens)
        new_rot = (q @ rot).normalized()
        if self.pivot is not None:
            # orbite autour de la selection / du point sous la souris
            loc = self.pivot + q @ (loc - self.pivot)
        self._view_set(loc, new_rot, dist)
        # vue de face/dessus en ortho automatique -> perspective
        if self.side_view:
            self.side_view = False
            try:
                rv3d.is_orthographic_side_view = False
                if inputs.use_auto_perspective and rv3d.view_perspective == 'ORTHO':
                    rv3d.view_perspective = 'PERSP'
            except (AttributeError, TypeError):
                pass

    def _zoom(self, context, rx, ry, dy):
        from bpy_extras.view3d_utils import region_2d_to_location_3d
        rv3d = self.rv3d
        p = _p()
        d = -dy if p.invert_zoom else dy
        if self._camera_view_unlocked():
            rv3d.view_camera_zoom = max(-30.0, min(600.0, rv3d.view_camera_zoom + d * 0.5 * p.zoom_sensitivity))
            return
        loc, rot, dist = self._view_get()
        if self.zoom_target is None:
            # zoom vers la souris (preference Blender) ou vers le point vise
            if context.preferences.inputs.use_zoom_to_mouse:
                depth = self.depth_point if self.depth_point is not None else loc
                self.zoom_target = region_2d_to_location_3d(self.region, rv3d, (rx, ry), depth)
            elif self.depth_point is not None:
                self.zoom_target = self.depth_point
            else:
                self.zoom_target = False
        # zoom exponentiel -> sensation "lisse"
        new_dist = max(0.001, dist * math.pow(1.01, -d * p.zoom_sensitivity))
        f = new_dist / dist
        if self.zoom_target:
            loc = self.zoom_target + (loc - self.zoom_target) * f
        self._view_set(loc, rot, new_dist)

    def _sync_quad(self):
        """Quad view avec 'Sync' : pan/zoom partages entre les vues verrouillees."""
        rv3d = self.rv3d
        if not (rv3d.lock_rotation and rv3d.show_sync_view):
            return
        for other in getattr(self.space, "region_quadviews", []):
            if other != rv3d and other.lock_rotation:
                other.view_location = rv3d.view_location
                other.view_distance = rv3d.view_distance

    def _recenter(self, context):
        try:
            with context.temp_override(area=self.area, region=self.region):
                bpy.ops.view3d.view_center_pick('INVOKE_DEFAULT')
        except Exception:
            pass


# --- Corrections des raccourcis Blender -------------------------------------
# Les raccourcis des OUTILS (barre d'outils) et des operateurs modaux sont
# traites AVANT ceux de la vue 3D : s'ils utilisent la molette, le geste CAD
# n'est jamais declenche. C'est le cas de la carte "Industry Compatible"
# (molette = utiliser l'outil Move / Rotate / Extrude / Knife..., facon Maya).
#
# Les modifications sont faites dans la keyconfig "utilisateur" (les
# extensions ne peuvent pas ajouter de cartes modales) et sont annulees quand
# l'option est decochee ou que l'extension est desactivee.

def _user_keyconfig():
    return bpy.context.window_manager.keyconfigs.user


def _is_tool_keymap(km):
    return (not km.is_modal) and (
        km.name.startswith("3D View Tool:")
        or km.name.startswith("Generic Tool: Annotate"))


def _is_mmb_conflict(kmi):
    # molette seule, Shift+molette, Ctrl+molette : utilises par la navigation
    # CAD. Les combinaisons avec Alt (navigation Industry Compatible) sont
    # conservees.
    return kmi.type == 'MIDDLEMOUSE' and (kmi.any or kmi.alt != 1) \
        and kmi.oskey != 1


def _set_tool_mmb_override(enable):
    """Coupe (ou retablit) la molette dans les raccourcis des outils."""
    kc = _user_keyconfig()
    if kc is None or kc.keymaps.get('3D View') is None:
        return False
    for km in kc.keymaps:
        if _is_tool_keymap(km):
            for kmi in km.keymap_items:
                if _is_mmb_conflict(kmi):
                    kmi.active = not enable
    return True


def _set_tool_navigation(enable):
    """Navigation molette PENDANT une transformation / le couteau.

    Renvoie False si les cartes modales n'existent pas encore (demarrage).
    """
    kc = _user_keyconfig()
    if kc is None:
        return False
    km = kc.keymaps.get('Transform Modal Map')
    knife = kc.keymaps.get('Knife Tool Modal Map')
    if km is None or knife is None:
        return False
    for kmi in km.keymap_items:
        if kmi.propvalue in _TRANSFORM_MODAL_ITEMS:
            # enable -> on coupe ces raccourcis ; sinon on les retablit
            kmi.active = not enable

    # Couteau : "PANNING" = laisse passer la molette vers la navigation.
    # Carte par defaut : molette (toutes touches). Industry Compatible : Alt
    # obligatoire -> on ajoute la molette seule.
    def plain_panning(kmi):
        return kmi.propvalue == 'PANNING' and kmi.type == 'MIDDLEMOUSE' \
            and (kmi.any or kmi.alt != 1)

    ours = [k for k in knife.keymap_items if plain_panning(k) and k.is_user_defined]
    native = [k for k in knife.keymap_items if plain_panning(k) and not k.is_user_defined]
    if enable and not native and not ours:
        knife.keymap_items.new_modal('PANNING', 'MIDDLEMOUSE', 'ANY', any=True)
    elif not enable:
        for k in ours:
            knife.keymap_items.remove(k)
    return True


def _apply_keymap_fixes(prefs=None):
    p = prefs or _prefs()
    if p is None:
        return False
    ok = _set_tool_navigation(p.tool_navigation)
    ok = _set_tool_mmb_override(p.tool_mmb_override) and ok
    return ok


def _restore_keymaps():
    _set_tool_navigation(False)
    _set_tool_mmb_override(False)


def _apply_keymap_fixes_deferred():
    if _prefs() is None:
        return None
    if not _apply_keymap_fixes():
        return 0.5   # la keyconfig utilisateur n'est pas encore prete
    return None


@persistent
def _on_load_post(*_args):
    if not bpy.app.timers.is_registered(_apply_keymap_fixes_deferred):
        bpy.app.timers.register(_apply_keymap_fixes_deferred, first_interval=0.1)


def _update_keymap_fixes(self, context):
    _apply_keymap_fixes(self)


class FRWA_OT_cad_nav_reapply(bpy.types.Operator):
    """Reapplique les corrections de raccourcis (apres un changement de carte de raccourcis)"""
    bl_idname = "preferences.frwa_cad_nav_reapply"
    bl_label = "Reappliquer les corrections de raccourcis"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        if _apply_keymap_fixes():
            self.report({'INFO'}, "Corrections de raccourcis appliquees")
            return {'FINISHED'}
        self.report({'WARNING'}, "Raccourcis pas encore disponibles")
        return {'CANCELLED'}


# --- Preferences (sensibilites reglables) ---------------------------------
class FRWA_CADNav_Prefs(bpy.types.AddonPreferences):
    bl_idname = __name__

    pan_speed: FloatProperty(
        name="Vitesse pan",
        description="1.0 = l'objet suit exactement le curseur",
        default=1.0, min=0.1, max=10.0)
    orbit_sensitivity: FloatProperty(
        name="Sensibilite orbite",
        description="Multiplie la sensibilite d'orbite reglee dans Blender (Preferences > Navigation)",
        default=1.0, min=0.05, max=10.0)
    zoom_sensitivity: FloatProperty(
        name="Sensibilite zoom", default=1.0, min=0.05, max=10.0)
    invert_orbit_x: BoolProperty(name="Inverser orbite X", default=False)
    invert_orbit_y: BoolProperty(name="Inverser orbite Y", default=False)
    invert_zoom: BoolProperty(name="Inverser zoom", default=False)
    tool_navigation: BoolProperty(
        name="Naviguer a la molette PENDANT une transformation / le couteau",
        description=(
            "Molette = pan, Shift+molette = orbite, Ctrl+molette = zoom pendant "
            "un deplacement (G, gizmo, outil Move...) ou une coupe au couteau, "
            "sans Alt. La contrainte d'axe a la molette est alors desactivee "
            "(utiliser X / Y / Z)"),
        default=True, update=_update_keymap_fixes)
    tool_mmb_override: BoolProperty(
        name="La molette navigue meme quand un outil est actif",
        description=(
            "Desactive les raccourcis molette des outils de la barre d'outils "
            "(Move, Rotate, Extrude, Knife, Bevel... en carte Industry "
            "Compatible, la molette lance l'outil au lieu de naviguer)"),
        default=True, update=_update_keymap_fixes)

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.prop(self, "pan_speed")
        col.prop(self, "orbit_sensitivity")
        col.prop(self, "zoom_sensitivity")
        row = layout.row(align=True)
        row.prop(self, "invert_orbit_x", toggle=True)
        row.prop(self, "invert_orbit_y", toggle=True)
        row.prop(self, "invert_zoom", toggle=True)
        layout.prop(self, "tool_mmb_override")
        layout.prop(self, "tool_navigation")
        layout.operator(FRWA_OT_cad_nav_reapply.bl_idname, icon='FILE_REFRESH')
        box = layout.box()
        box.label(text="Hors outil : molette = pan, molette+droit maintenu = orbite,")
        box.label(text="molette+droit court = zoom, clic molette = recentrer.")
        box.label(text="Pendant un outil : molette = pan, Shift+molette = orbite, Ctrl+molette = zoom.")
        box.label(text="Bevel / Inset / Loop cut : Blender ne permet pas de naviguer pendant ces outils.")


# --- Enregistrement --------------------------------------------------------
addon_keymaps = []


def register():
    bpy.utils.register_class(FRWA_CADNav_Prefs)
    bpy.utils.register_class(FRWA_OT_cad_navigation)
    bpy.utils.register_class(FRWA_OT_cad_nav_reapply)

    kc = bpy.context.window_manager.keyconfigs.addon
    if kc:
        km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')
        # 1) operateurs NATIFS : c'est eux que Blender utilise pour naviguer
        #    PENDANT G/R/S/Extrude/gizmos (il ne sait pas lancer un operateur
        #    Python a l'interieur d'une transformation).
        kmi = km.keymap_items.new('view3d.move', 'MIDDLEMOUSE', 'PRESS')
        addon_keymaps.append((km, kmi))
        kmi = km.keymap_items.new('view3d.rotate', 'MIDDLEMOUSE', 'PRESS', shift=True)
        addon_keymaps.append((km, kmi))
        kmi = km.keymap_items.new('view3d.zoom', 'MIDDLEMOUSE', 'PRESS', ctrl=True)
        addon_keymaps.append((km, kmi))
        # 2) le geste CAD complet, ajoute EN DERNIER : Blender fusionne les
        #    raccourcis d'extension en ordre inverse, il passe donc en premier
        #    et masque view3d.move hors outil.
        kmi = km.keymap_items.new(
            FRWA_OT_cad_navigation.bl_idname, 'MIDDLEMOUSE', 'PRESS')
        addon_keymaps.append((km, kmi))

    if _on_load_post not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_on_load_post)
    bpy.app.timers.register(_apply_keymap_fixes_deferred, first_interval=0.1)


def unregister():
    if bpy.app.timers.is_registered(_apply_keymap_fixes_deferred):
        bpy.app.timers.unregister(_apply_keymap_fixes_deferred)
    if _on_load_post in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_on_load_post)
    # retablit les raccourcis d'origine (outils, transformation, couteau)
    _restore_keymaps()

    for km, kmi in addon_keymaps:
        try:
            km.keymap_items.remove(kmi)
        except Exception:
            pass
    addon_keymaps.clear()

    bpy.utils.unregister_class(FRWA_OT_cad_nav_reapply)
    bpy.utils.unregister_class(FRWA_OT_cad_navigation)
    bpy.utils.unregister_class(FRWA_CADNav_Prefs)


if __name__ == "__main__":
    register()
