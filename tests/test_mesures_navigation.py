# Mesures de qualite de la navigation (CAD vs natif Industry Compatible)
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
from mathutils import Vector, Euler
from bpy_extras.view3d_utils import region_2d_to_location_3d
from simlib import *
import simlib

S = os.path.dirname(os.path.abspath(__file__))
TAG = os.environ.get("M_TAG", "m")
HAS_CAD = 'frwa_cad_navigation' in bpy.context.preferences.addons


def setup_scene():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    us = bpy.context.scene.unit_settings
    us.scale_length = 0.001
    us.length_unit = 'MILLIMETERS'
    with ctx():
        bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=40, depth=100, location=(0, 0, 50))
        bpy.context.object.name = "Fantome"
        bpy.ops.mesh.primitive_cube_add(size=20, location=(90, 0, 50))
        bpy.context.object.name = "Cible"


def reset_view(persp='PERSP', loc=(0, 0, 50), dist=300, rot=(60, 0, 30)):
    w, a, r, rv = v3d()
    rv.view_perspective = persp
    rv.view_rotation = Euler([math.radians(v) for v in rot]).to_quaternion()
    rv.view_location = loc
    rv.view_distance = dist
    rv.is_orthographic_side_view = False


def gesture(kind, dx, dy):
    """kind: cad_pan, cad_orbit, cad_zoom, nat_pan, nat_orbit, nat_zoom"""
    x, y = STATE['mx'], STATE['my']
    if kind == 'cad_pan':
        yield from cad_pan(dx, dy)
    elif kind == 'cad_orbit':
        yield from cad_orbit(dx, dy)
    elif kind == 'cad_zoom':
        yield from cad_zoom(dy)
    else:
        btn = {'nat_pan': 'MIDDLEMOUSE', 'nat_orbit': 'LEFTMOUSE', 'nat_zoom': 'RIGHTMOUSE'}[kind]
        ev(btn, 'PRESS', alt=True); yield
        yield from move_to(x + dx, y + dy, steps=8)
        ev(btn, 'RELEASE', alt=True); yield
    yield from wait(4)


def kinds(base):
    out = []
    if HAS_CAD:
        out.append('cad_' + base)
    out.append('nat_' + base)
    return out


def main():
    yield from wait(25)
    STATE['mx'], STATE['my'] = center()
    x0, y0, rw, rh = region_rect()
    yield from move_to(x0 + 150, y0 + 150)
    yield from click('LEFTMOUSE')
    yield from wait(5)
    setup_scene()
    ip = bpy.context.preferences.inputs
    log("CAD actif:", HAS_CAD, "smooth_view ms:", bpy.context.preferences.view.smooth_view,
        "rotate_sens:", round(ip.view_rotate_sensitivity_turntable, 5))

    # ---------- M1 : pan 1:1 (l'objet suit le curseur)
    for persp in ('PERSP', 'ORTHO'):
        for k in kinds('pan'):
            reset_view(persp)
            yield from wait(3)
            yield from move_to(*center())
            p = Vector((0, 0, 50))
            s0 = to_win(p)
            yield from gesture(k, 100, 0)
            s1 = to_win(p)
            log(f"M1 pan {persp:5s} {k:8s}: curseur +100 px -> objet {s1[0]-s0[0]:+.1f} px")
            check(f"M1 {k} {persp}: l'objet suit le curseur (100 px +/-3)", abs((s1[0] - s0[0]) - 100) < 3, f"{s1[0]-s0[0]:+.1f}")

    # ---------- M1b : pan quand on est tres pres (zoom fort)
    for k in kinds('pan'):
        reset_view('PERSP', dist=8)
        yield from wait(3)
        yield from move_to(*center())
        p = Vector((0, 0, 50)); s0 = to_win(p)
        yield from gesture(k, 100, 0)
        s1 = to_win(p)
        log(f"M1b pan rapproche {k}: {s1[0]-s0[0]:+.1f} px")

    # ---------- M2 : orbite depuis une vue de face ortho (F1)
    for k in kinds('orbit'):
        reset_view('PERSP')
        yield from move_to(*center())
        yield from key('F1')
        yield from wait(12)
        w, a, r, rv = v3d()
        before = (rv.view_perspective, rv.is_orthographic_side_view)
        yield from gesture(k, 80, 0)
        log(f"M2 {k}: vue face {before} -> {rv.view_perspective} side={rv.is_orthographic_side_view}")
        check(f"M2 {k}: repasse en perspective apres orbite depuis F1", rv.view_perspective == 'PERSP' and not rv.is_orthographic_side_view)

    # ---------- M3 : orbite autour de la selection (preference)
    ip.use_rotate_around_active = True
    for k in kinds('orbit'):
        reset_view('PERSP')
        with ctx():
            bpy.ops.object.select_all(action='DESELECT')
        cible = bpy.data.objects['Cible']
        cible.select_set(True)
        bpy.context.view_layer.objects.active = cible
        yield from wait(3)
        yield from move_to(*center())
        s0 = to_win(cible.location)
        yield from gesture(k, 80, 0)
        s1 = to_win(cible.location)
        dpx = math.hypot(s1[0] - s0[0], s1[1] - s0[1])
        log(f"M3 {k}: orbite autour de la selection ON -> la cible bouge de {dpx:.1f} px")
        check(f"M3 {k}: respecte 'Orbit Around Selection'", dpx < 3, f"{dpx:.1f}px")
    ip.use_rotate_around_active = False

    # ---------- M4 : zoom vers la souris (preference)
    ip.use_zoom_to_mouse = True
    for k in kinds('zoom'):
        reset_view('PERSP')
        yield from wait(3)
        w, a, r, rv = v3d()
        mx, my = r.x + r.width * 0.75, r.y + r.height * 0.7
        yield from move_to(mx, my)
        target = region_2d_to_location_3d(r, rv, (mx - r.x, my - r.y), rv.view_location)
        d0 = rv.view_distance
        yield from gesture(k, 0, -60 if k.startswith('cad') else -60)
        st = to_win(target)
        drift = math.hypot(st[0] - mx, st[1] - my)
        log(f"M4 {k}: zoom {d0:.0f}->{rv.view_distance:.0f}, le point sous la souris derive de {drift:.1f} px")
        check(f"M4 {k}: respecte 'Zoom to Mouse Position'", drift < 15 and rv.view_distance != d0, f"{drift:.1f}px")
    # roulette
    reset_view('PERSP')
    yield from wait(3)
    w, a, r, rv = v3d()
    mx, my = r.x + r.width * 0.75, r.y + r.height * 0.7
    yield from move_to(mx, my)
    target = region_2d_to_location_3d(r, rv, (mx - r.x, my - r.y), rv.view_location)
    yield from wheel(3, True)
    st = to_win(target)
    log(f"M4 roulette: derive {math.hypot(st[0]-mx, st[1]-my):.1f} px")
    ip.use_zoom_to_mouse = False

    # ---------- M5 : geste juste apres F (animation de cadrage)
    if HAS_CAD:
        res = {}
        for mode, pause in (("apres pause", 30), ("immediat", 1)):
            reset_view('PERSP', loc=(200, 0, 0))
            with ctx():
                bpy.ops.object.select_all(action='DESELECT')
            bpy.data.objects['Fantome'].select_set(True)
            bpy.context.view_layer.objects.active = bpy.data.objects['Fantome']
            yield from wait(3)
            yield from move_to(*center())
            yield from key('F')
            yield from wait(pause)
            yield from cad_pan(120, 0)
            yield from wait(30)
            res[mode] = view_state()[0]
            log(f"M5 F puis pan ({mode}): view_location {res[mode]}")
        check("M5 pan juste apres F pas annule par l'animation", res["immediat"] == res["apres pause"], f"{res}")

    # ---------- M6 : vue camera
    for k in kinds('orbit'):
        reset_view('PERSP')
        with ctx():
            bpy.ops.object.camera_add(location=(0, -400, 100), rotation=(math.radians(85), 0, 0))
        cam = bpy.context.object
        bpy.context.scene.camera = cam
        w, a, r, rv = v3d()
        rv.view_perspective = 'CAMERA'
        yield from wait(4)
        yield from move_to(*center())
        yield from gesture(k, 80, 0)
        log(f"M6 {k}: vue camera -> {rv.view_perspective}")
        check(f"M6 {k}: orbiter sort de la vue camera", rv.view_perspective != 'CAMERA')
        bpy.data.objects.remove(cam)
    for k in kinds('pan'):
        reset_view('PERSP')
        with ctx():
            bpy.ops.object.camera_add(location=(0, -400, 100), rotation=(math.radians(85), 0, 0))
        cam = bpy.context.object
        bpy.context.scene.camera = cam
        w, a, r, rv = v3d()
        rv.view_perspective = 'CAMERA'
        rv.view_camera_offset = (0, 0)
        yield from wait(4)
        yield from move_to(*center())
        loc0 = tuple(rv.view_location)
        yield from gesture(k, 80, 0)
        log(f"M6 {k}: pan en vue camera offset={tuple(round(c,3) for c in rv.view_camera_offset)} persp={rv.view_perspective}")
        check(f"M6 {k}: pan en vue camera deplace le cadrage", tuple(rv.view_camera_offset) != (0.0, 0.0) or rv.view_perspective != 'CAMERA')
        bpy.data.objects.remove(cam)

    # ---------- M8 : Auto Depth (orbite autour du point sous la souris)
    ip.use_mouse_depth_navigate = True
    for k in kinds('orbit'):
        reset_view('PERSP')
        yield from wait(3)
        cible = bpy.data.objects['Cible']
        p = cible.location + Vector((0, -10, 0))       # face avant du cube
        yield from move_to(*to_win(p))
        yield from wait(2)
        s0 = to_win(p)
        yield from gesture(k, 60, 0)
        s1 = to_win(p)
        dpx = math.hypot(s1[0] - s0[0], s1[1] - s0[1])
        log(f"M8 {k}: auto depth -> le point vise bouge de {dpx:.1f} px")
        check(f"M8 {k}: respecte 'Auto Depth' (pivot sous la souris)", dpx < 5, f"{dpx:.1f}px")
    ip.use_mouse_depth_navigate = False

    # ---------- M9 : sens de l'orbite (meme sens que Blender ?)
    if HAS_CAD:
        res = {}
        for k in ('cad_orbit', 'nat_orbit'):
            reset_view('PERSP')
            yield from wait(3)
            yield from move_to(*center())
            p = Vector((90, 0, 50))
            s0 = to_win(p)
            yield from gesture(k, 60, 0)
            s1 = to_win(p)
            res[k] = (round(s1[0] - s0[0], 1), round(s1[1] - s0[1], 1))
        log(f"M9 sens orbite (deplacement ecran d'un point a droite) : CAD {res['cad_orbit']} / natif {res['nat_orbit']}")
        check("M9 orbite dans le meme sens que Blender", (res['cad_orbit'][0] > 0) == (res['nat_orbit'][0] > 0), res)

    # ---------- M10 : vue camera verrouillee (Camera to View)
    if HAS_CAD:
        reset_view('PERSP')
        with ctx():
            bpy.ops.object.camera_add(location=(0, -400, 100), rotation=(math.radians(85), 0, 0))
        cam = bpy.context.object
        bpy.context.scene.camera = cam
        w, a, r, rv = v3d()
        a.spaces.active.lock_camera = True
        rv.view_perspective = 'CAMERA'
        yield from wait(4)
        yield from move_to(*center())
        m0 = cam.matrix_world.copy()
        yield from gesture('cad_orbit', 60, 0)
        m1 = cam.matrix_world.copy()
        yield from gesture('cad_pan', 60, 0)
        m2 = cam.matrix_world.copy()
        check("M10 Camera to View : l'orbite deplace la camera", m0 != m1 and rv.view_perspective == 'CAMERA')
        check("M10 Camera to View : le pan deplace la camera", m1 != m2)
        a.spaces.active.lock_camera = False
        bpy.data.objects.remove(cam)

    # ---------- M11 : methode trackball
    if HAS_CAD:
        ip.view_rotate_method = 'TRACKBALL'
        reset_view('PERSP')
        yield from wait(3)
        yield from move_to(*center())
        q0 = view_state()[1]
        yield from gesture('cad_orbit', 60, 30)
        check("M11 orbite en mode Trackball", view_state()[1] != q0 and not modals())
        ip.view_rotate_method = 'TURNTABLE'

    # ---------- M7 : quad view verrouillee
    reset_view('PERSP')
    with ctx():
        bpy.ops.screen.region_quadview()
    yield from wait(10)
    w, a, r_, rv_ = v3d()
    locked = [(r, r.data) for r in a.regions if r.type == 'WINDOW' and r.data and r.data.lock_rotation]
    log("M7 quadrants verrouilles:", len(locked))
    if locked:
        r, rv = locked[0]
        for k in kinds('orbit'):
            STATE['mx'], STATE['my'] = r.x + r.width // 2, r.y + r.height // 2
            yield from move_to(STATE['mx'], STATE['my'])
            q0 = tuple(round(c, 4) for c in rv.view_rotation)
            yield from gesture(k, 80, 30)
            q1 = tuple(round(c, 4) for c in rv.view_rotation)
            check(f"M7 {k}: quadrant verrouille non tourne", q0 == q1, f"{q0} -> {q1}")
    with ctx():
        bpy.ops.screen.region_quadview()
    yield from wait(5)


run(main, os.path.join(S, f"measure_{TAG}.txt"))
