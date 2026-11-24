# FrWA CAD Navigation - reglages Blender recommandes (usage type CAO / impression 3D)
#
# Lancer UNE fois, Blender ferme :
#   blender --python appliquer_reglages_recommandes.py
# Le script applique les reglages, enregistre les preferences et le fichier de
# demarrage, puis quitte Blender.
#
# Ce qu'il fait :
#   Preferences > Navigation
#     - Zoom to Mouse Position : active (zoom vers le curseur)
#     - Auto Depth             : active (orbite autour du point sous la souris)
#     - Auto Perspective       : active
#   Extension FrWA CAD Navigation : activee, ses deux options cochees
#   Fichier de demarrage (File > Defaults) :
#     - scene vide en millimetres (Unit Scale 0.001, Length = Millimeters)
#     - vue 3D cadree pour des pieces d'environ 150 mm, clipping 0.1 mm a 10 m
#
# Pour revenir en arriere : File > Defaults > Load Factory Settings, ou
# supprimer config/startup.blend.
import bpy
import addon_utils

ADDON = "frwa_cad_navigation"
SAVE_STARTUP = True


def appliquer():
    prefs = bpy.context.preferences
    inp = prefs.inputs
    inp.use_zoom_to_mouse = True
    inp.use_mouse_depth_navigate = True
    inp.use_auto_perspective = True

    try:
        addon_utils.enable(ADDON, default_set=True, persistent=True)
        ap = prefs.addons[ADDON].preferences
        ap.tool_mmb_override = True
        ap.tool_navigation = True
    except Exception as e:  # extension absente : on garde les autres reglages
        print("FrWA : extension non activee :", e)

    if SAVE_STARTUP:
        for o in list(bpy.data.objects):
            bpy.data.objects.remove(o)
        for sc in bpy.data.scenes:
            us = sc.unit_settings
            us.system = 'METRIC'
            us.scale_length = 0.001
            us.length_unit = 'MILLIMETERS'
        for screen in bpy.data.screens:
            for area in screen.areas:
                if area.type != 'VIEW_3D':
                    continue
                for sp in area.spaces:
                    if sp.type != 'VIEW_3D':
                        continue
                    sp.clip_start = 0.1
                    sp.clip_end = 10000.0
                    rv = sp.region_3d
                    if rv is not None:
                        rv.view_location = (0.0, 0.0, 60.0)
                        rv.view_distance = 300.0

    bpy.ops.wm.save_userpref()
    if SAVE_STARTUP:
        bpy.ops.wm.save_homefile()
    print("FrWA : reglages recommandes appliques")


def _run():
    appliquer()
    bpy.ops.wm.quit_blender()


if bpy.app.background:
    appliquer()
else:
    bpy.app.timers.register(_run, first_interval=1.0)
