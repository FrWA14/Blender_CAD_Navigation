# Harnais de test : pilote Blender (GUI) par evenements simules.
# Lancer avec : blender --factory-startup --enable-event-simulate --python harness.py
import bpy, sys, os, traceback, addon_utils
from mathutils import Vector
from bpy_extras.view3d_utils import location_3d_to_region_2d

OUT = os.environ.get("HARNESS_OUT", "harness_log.txt")
LOG = open(OUT, "w", encoding="utf-8")
ONLY = os.environ.get("HARNESS_ONLY", "")


def log(*a):
    s = " ".join(str(x) for x in a)
    LOG.write(s + "\n"); LOG.flush()
    print("[H]", s)


if not os.environ.get("HARNESS_NOADDON"):
    addon_utils.enable("frwa_cad_navigation", default_set=True)
log("addon loaded:", "frwa_cad_navigation" in bpy.context.preferences.addons)


def win():
    return bpy.context.window_manager.windows[0]


def v3d():
    w = win()
    for a in w.screen.areas:
        if a.type == 'VIEW_3D':
            for r in a.regions:
                if r.type == 'WINDOW':
                    return w, a, r, a.spaces.active.region_3d
    raise RuntimeError("no view3d")


def ctx():
    w, a, r, _ = v3d()
    return bpy.context.temp_override(window=w, area=a, region=r)


def ev(t, v='NOTHING', x=None, y=None, **mods):
    w = win()
    if x is None:
        x, y = STATE['mx'], STATE['my']
    STATE['mx'], STATE['my'] = x, y
    w.event_simulate(t, v, x=int(x), y=int(y), **mods)


STATE = {'mx': 0, 'my': 0}


def center():
    w, a, r, _ = v3d()
    return r.x + r.width // 2, r.y + r.height // 2


def to_win(co):
    w, a, r, rv3d = v3d()
    p = location_3d_to_region_2d(r, rv3d, co)
    return (r.x + p.x, r.y + p.y) if p else None


def modals():
    return [m.bl_idname for m in win().modal_operators]


def view_state():
    _, _, _, rv = v3d()
    return (tuple(round(c, 4) for c in rv.view_location),
            tuple(round(c, 4) for c in rv.view_rotation),
            round(rv.view_distance, 4))


def hud():
    _, a, _, _ = v3d()
    return any(r.type == 'HUD' for r in a.regions)


# --- primitives (generateurs : chaque yield laisse tourner la boucle WM) ---
def wait(n=2):
    for _ in range(n):
        yield


def move_to(x, y, steps=6):
    x0, y0 = STATE['mx'], STATE['my']
    for i in range(1, steps + 1):
        ev('MOUSEMOVE', 'NOTHING', x0 + (x - x0) * i / steps, y0 + (y - y0) * i / steps)
        yield


def click(t='LEFTMOUSE', **mods):
    ev(t, 'PRESS', **mods); yield
    ev(t, 'RELEASE', **mods); yield


def key(k, **mods):
    ev(k, 'PRESS', **mods); yield
    ev(k, 'RELEASE', **mods); yield


def mmb_drag(dx=80, dy=40, rmb=False, rmb_click=False):
    x, y = STATE['mx'], STATE['my']
    ev('MIDDLEMOUSE', 'PRESS'); yield
    if rmb_click:
        yield from click('RIGHTMOUSE')
    if rmb:
        ev('RIGHTMOUSE', 'PRESS'); yield
    yield from move_to(x + dx, y + dy)
    if rmb:
        ev('RIGHTMOUSE', 'RELEASE'); yield
    ev('MIDDLEMOUSE', 'RELEASE'); yield
    yield from wait(2)


def reset():
    for _ in range(3):
        yield from key('ESC')
    with ctx():
        if bpy.context.object and bpy.context.object.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.wm.tool_set_by_id(name="builtin.select_box")
        rv = bpy.context.region_data
        rv.view_location = (0, 0, 0)
        rv.view_distance = 15
    yield from wait(2)
    STATE['mx'], STATE['my'] = center()
    ev('MOUSEMOVE'); yield


def edit_edges():
    with ctx():
        bpy.ops.object.select_all(action='DESELECT')
        o = bpy.data.objects.get('Cube')
        if o is None:   # fichier de demarrage vide : on cree le cube de test
            bpy.ops.mesh.primitive_cube_add(size=2)
            o = bpy.context.object
            o.name = 'Cube'
            bpy.ops.object.select_all(action='DESELECT')
        bpy.context.view_layer.objects.active = o
        o.select_set(True)
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_mode(type='EDGE')
        bpy.ops.mesh.select_all(action='DESELECT')
    yield from wait(2)


def sel_edges():
    o = bpy.data.objects['Cube']
    o.update_from_editmode()
    return sum(1 for e in o.data.edges if e.select)


def visible_edge_mid():
    o = bpy.data.objects['Cube']
    o.update_from_editmode()
    me = o.data
    w, a, r, rv = v3d()
    view_dir = rv.view_rotation @ Vector((0, 0, -1))
    best = None
    for e in me.edges:
        co = o.matrix_world @ ((me.vertices[e.vertices[0]].co + me.vertices[e.vertices[1]].co) / 2)
        p = to_win(co)
        if p is None:
            continue
        depth = (co - rv.view_matrix.inverted().translation).dot(view_dir)
        if best is None or depth < best[0]:
            best = (depth, p)
    return best[1]


RESULTS = []


def check(name, cond, info=""):
    RESULTS.append((name, bool(cond)))
    log(("OK  " if cond else "FAIL"), name, info)


# --- scenarios -----------------------------------------------------------
def sc_pan():
    v0 = view_state()
    yield from mmb_drag(80, 40)
    v1 = view_state()
    check("pan: vue deplacee", v0[0] != v1[0], f"{v0[0]} -> {v1[0]}")
    check("pan: pas de modal residuel", not modals(), modals())


def sc_orbit():
    v0 = view_state()
    yield from mmb_drag(80, 40, rmb=True)
    v1 = view_state()
    check("orbite: rotation changee", v0[1] != v1[1])
    check("orbite: pas de modal residuel", not modals(), modals())


def sc_zoom():
    v0 = view_state()
    yield from mmb_drag(0, 60, rmb_click=True)
    v1 = view_state()
    check("zoom: distance changee", v0[2] != v1[2], f"{v0[2]} -> {v1[2]}")
    check("zoom: pas de modal residuel", not modals(), modals())


def sc_mmb_click():
    yield from click('MIDDLEMOUSE')
    yield from wait(10)
    check("clic molette: pas de modal residuel", not modals(), modals())


def sc_select_edge():
    yield from edit_edges()
    x, y = visible_edge_mid()
    yield from move_to(x, y)
    yield from click('LEFTMOUSE')
    yield from wait(2)
    n0 = sel_edges()
    check("selection arete (avant nav)", n0 >= 1, n0)
    yield from move_to(*center())
    yield from mmb_drag(30, 20)
    yield from mmb_drag(60, 30, rmb=True)
    with ctx():
        bpy.ops.mesh.select_all(action='DESELECT')
    yield from wait(2)
    x, y = visible_edge_mid()
    yield from move_to(x, y)
    yield from click('LEFTMOUSE')
    yield from wait(2)
    n1 = sel_edges()
    check("selection arete (apres nav)", n1 >= 1, n1)
    # shift+clic pour ajouter
    check("pas de modal residuel", not modals(), modals())


def _nav_during(start_keys, name, tool=None, prep=None, confirm_cancel="ESC", limit=False):
    def gen():
        chk = check if not limit else (lambda n, c, i="": log(("OK  " if c else "LIM "), n, i))
        yield from edit_edges()
        with ctx():
            bpy.ops.mesh.select_all(action='SELECT') if prep == 'all' else None
            if prep == 'face':
                bpy.ops.mesh.select_mode(type='FACE')
                bpy.ops.mesh.select_all(action='DESELECT')
        if prep == 'face':
            # selectionne la face du dessus
            o = bpy.data.objects['Cube']
            with ctx():
                bpy.ops.object.mode_set(mode='OBJECT')
                for f in o.data.polygons:
                    f.select = f.normal.z > 0.9
                bpy.ops.object.mode_set(mode='EDIT')
        if tool:
            with ctx():
                bpy.ops.wm.tool_set_by_id(name=tool)
        yield from wait(2)
        cx, cy = center()
        yield from move_to(cx - 40, cy - 30)
        for k, mods in start_keys:
            yield from key(k, **mods)
        yield from wait(3)
        m0 = modals()
        log("   modals apres demarrage:", m0)
        v0 = view_state()
        yield from mmb_drag(70, 30)
        v1 = view_state()
        m1 = modals()
        chk(f"{name}: la vue bouge (pan)", v0[0] != v1[0] or v0[1] != v1[1], f"modals={m1}")
        v0 = view_state()
        if os.environ.get("HARNESS_V2"):
            x, y = STATE['mx'], STATE['my']
            ev('MIDDLEMOUSE', 'PRESS', shift=True); yield
            yield from move_to(x + 70, y + 30)
            ev('MIDDLEMOUSE', 'RELEASE', shift=True); yield
            yield from wait(3)
            v1 = view_state()
            m2 = modals()
            chk(f"{name}: la vue tourne (Shift+molette)", v0[1] != v1[1], f"modals={m2}")
            v0 = view_state()
            x, y = STATE['mx'], STATE['my']
            ev('MIDDLEMOUSE', 'PRESS', ctrl=True); yield
            yield from move_to(x, y + 40)
            ev('MIDDLEMOUSE', 'RELEASE', ctrl=True); yield
            yield from wait(3)
            v1 = view_state()
            m2 = modals()
            chk(f"{name}: zoom (Ctrl+molette)", v0[2] != v1[2], f"modals={m2}")
        else:
            yield from mmb_drag(70, 30, rmb=True)
            v1 = view_state()
            m2 = modals()
            chk(f"{name}: la vue tourne (orbite)", v0[1] != v1[1], f"modals={m2}")
        check(f"{name}: l'outil est toujours actif", (not m0) or all(m in m2 for m in m0 if 'frwa' not in m.lower()), f"{m0} -> {m2}")
        for _ in range(2):
            yield from key(confirm_cancel)
        yield from wait(3)
        check(f"{name}: pas de modal residuel", not modals(), modals())
    return gen


def sc_toolbar(tool, name):
    def gen():
        yield from edit_edges()
        with ctx():
            bpy.ops.wm.tool_set_by_id(name=tool)
        yield from wait(2)
        yield from move_to(*center())
        v0 = view_state()
        yield from mmb_drag(60, 20)
        v1 = view_state()
        check(f"outil {name}: pan", v0[0] != v1[0], f"modals={modals()}")
        v0 = view_state()
        yield from mmb_drag(60, 20, rmb=True)
        v1 = view_state()
        check(f"outil {name}: orbite", v0[1] != v1[1], f"modals={modals()}")
        check(f"outil {name}: pas de modal residuel", not modals(), modals())
        # selection avec l'outil select box : clic sur une arete
        with ctx():
            bpy.ops.wm.tool_set_by_id(name="builtin.select_box")
        yield from wait(2)
        x, y = visible_edge_mid()
        yield from move_to(x, y)
        yield from click('LEFTMOUSE')
        yield from wait(2)
        check(f"outil {name}: selection arete ensuite", sel_edges() >= 1, sel_edges())
    return gen


def sc_hud():
    yield from edit_edges()
    with ctx():
        bpy.ops.mesh.select_all(action='SELECT')
    yield from move_to(*center())
    # Subdivide via F3 serait complexe : on utilise extrude E + clic
    yield from key('E')
    yield from move_to(STATE['mx'] + 10, STATE['my'] + 30)
    yield from click('LEFTMOUSE')
    yield from wait(5)
    h0 = hud()
    last = [o.bl_idname for o in bpy.context.window_manager.operators][-1:]
    log("   last op:", last, "hud:", h0)
    yield from move_to(*center())
    yield from mmb_drag(40, 20)
    yield from mmb_drag(40, 20, rmb=True)
    yield from click('MIDDLEMOUSE')
    yield from wait(10)
    h1 = hud()
    last2 = [o.bl_idname for o in bpy.context.window_manager.operators][-1:]
    check("panneau 'Ajuster derniere operation' conserve apres nav", h0 == h1 and last == last2, f"hud {h0}->{h1} last {last}->{last2}")


def sc_stuck():
    # Molette appuyee mais le relachement est perdu (alt-tab, sortie fenetre...)
    yield from edit_edges()
    yield from move_to(*center())
    ev('MIDDLEMOUSE', 'PRESS'); yield
    ev('WINDOW_DEACTIVATE', 'NOTHING'); yield
    yield from wait(3)
    m = modals()
    check("perte focus pendant geste: modal termine", not m, m)
    if m:
        # consequences : clic gauche avale ?
        x, y = visible_edge_mid()
        yield from move_to(x, y)
        yield from click('LEFTMOUSE')
        yield from wait(2)
        log("   selection pendant modal bloque:", sel_edges())
        yield from key('ESC')


def sc_stuck2():
    # relachement perdu, puis clic gauche sur une arete : la selection doit marcher
    yield from edit_edges()
    yield from move_to(*center())
    ev('MIDDLEMOUSE', 'PRESS'); yield
    yield from move_to(STATE['mx'] + 20, STATE['my'] + 10)
    yield from wait(2)
    x, y = visible_edge_mid()
    STATE['mx'], STATE['my'] = x, y
    ev('LEFTMOUSE', 'PRESS'); yield
    yield from wait(2)
    log("   apres PRESS: modals", modals(), "sel", sel_edges())
    ev('LEFTMOUSE', 'RELEASE'); yield
    yield from wait(3)
    log("   apres RELEASE: modals", modals(), "sel", sel_edges())
    if sel_edges() == 0:
        yield from click('LEFTMOUSE')
        yield from wait(3)
        log("   apres 2e clic: sel", sel_edges())
    check("relachement perdu + clic gauche: arete selectionnee", sel_edges() >= 1, sel_edges())
    check("relachement perdu + clic gauche: plus de modal", not modals(), modals())
    # relachement perdu puis touche Tab : le changement de mode doit marcher
    yield from move_to(*center())
    ev('MIDDLEMOUSE', 'PRESS'); yield
    yield from wait(2)
    yield from key('TAB')
    yield from wait(3)
    check("relachement perdu + Tab: mode objet", bpy.data.objects['Cube'].mode == 'OBJECT', bpy.data.objects['Cube'].mode)
    check("relachement perdu + Tab: plus de modal", not modals(), modals())
    # double appui molette (relachement perdu entre les deux)
    ev('MIDDLEMOUSE', 'PRESS'); yield
    ev('MIDDLEMOUSE', 'PRESS'); yield
    v0 = view_state()
    yield from move_to(STATE['mx'] + 40, STATE['my'])
    ev('MIDDLEMOUSE', 'RELEASE'); yield
    yield from wait(3)
    check("double appui molette: pan puis fin", view_state()[0] != v0[0] and not modals(), modals())


def sc_zoom_toggle():
    # clic droit court = zoom, re-clic court = retour au pan
    yield from move_to(*center())
    x, y = STATE['mx'], STATE['my']
    ev('MIDDLEMOUSE', 'PRESS'); yield
    yield from click('RIGHTMOUSE')
    v0 = view_state()
    yield from move_to(x, y + 40)
    v1 = view_state()
    yield from click('RIGHTMOUSE')
    yield from move_to(x + 40, y + 40)
    v2 = view_state()
    ev('MIDDLEMOUSE', 'RELEASE'); yield
    yield from wait(3)
    check("bascule zoom: zoom actif", v0[2] != v1[2], f"{v0[2]}->{v1[2]}")
    check("bascule zoom: re-clic -> retour pan", v1[0] != v2[0] and v1[2] == v2[2], f"loc {v1[0]}->{v2[0]} dist {v1[2]}->{v2[2]}")
    check("bascule zoom: pas de modal residuel", not modals(), modals())


def sc_context_menu():
    # clic droit seul -> menu contextuel (doit rester natif)
    yield from move_to(*center())
    yield from click('RIGHTMOUSE')
    yield from wait(5)
    w = win()
    has_menu = any(m.bl_idname for m in w.modal_operators) or len(bpy.context.window_manager.windows) > 0
    log("   modals apres clic droit:", modals())
    yield from key('ESC')
    yield from wait(2)
    check("clic droit seul: pas de modal CAD", 'VIEW3D_OT_frwa_cad_navigation' not in modals(), modals())


def sc_prefs_restore():
    km = bpy.context.window_manager.keyconfigs.user.keymaps['Transform Modal Map']
    st = lambda: sorted((k.propvalue, k.active) for k in km.keymap_items if k.propvalue in ('PASSTHROUGH_NAVIGATE', 'AUTOCONSTRAIN', 'AUTOCONSTRAINPLANE'))
    s_on = st()
    check("pref active: raccourcis transform coupes", all(not a for _, a in s_on), s_on)
    p = bpy.context.preferences.addons['frwa_cad_navigation'].preferences
    p.tool_navigation = False
    s_off = st()
    check("pref desactivee: raccourcis transform retablis", all(a for _, a in s_off), s_off)
    p.tool_navigation = True
    addon_utils.disable("frwa_cad_navigation", default_set=True)
    yield from wait(3)
    s_dis = st()
    check("extension desactivee: raccourcis transform retablis", all(a for _, a in s_dis), s_dis)
    addon_utils.enable("frwa_cad_navigation", default_set=True)
    yield from wait(30)
    s_re = st()
    check("extension reactivee: raccourcis transform coupes", all(not a for _, a in s_re), s_re)


def sc_gizmo_drag():
    # outil Extrude de la barre d'outils : drag du gizmo puis navigation pendant le drag
    yield from edit_edges()
    with ctx():
        bpy.ops.mesh.select_mode(type='FACE')
        bpy.ops.object.mode_set(mode='OBJECT')
        for f in bpy.data.objects['Cube'].data.polygons:
            f.select = f.normal.z > 0.9
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.wm.tool_set_by_id(name="builtin.move")
    yield from wait(3)
    # clic-glisse sur la face selectionnee (outil Move : tweak = translation)
    o = bpy.data.objects['Cube']
    p = to_win(o.matrix_world @ Vector((0, 0, 1)))
    yield from move_to(*p)
    ev('LEFTMOUSE', 'PRESS'); yield
    yield from move_to(p[0] + 30, p[1] + 30, steps=8)
    yield from wait(3)
    m0 = modals()
    log("   modals pendant drag:", m0)
    v0 = view_state()
    yield from mmb_drag(60, 20)
    v1 = view_state()
    check("drag outil Move + molette: pan", v0[0] != v1[0], f"modals={modals()}")
    check("drag outil Move + molette: outil toujours actif", modals() == m0, f"{m0} -> {modals()}")
    ev('LEFTMOUSE', 'RELEASE'); yield
    yield from wait(3)
    yield from key('ESC')
    check("drag outil Move: termine proprement", not modals(), modals())


# ======================= scenarios Industry Compatible =====================
def mesh_snap():
    o = bpy.data.objects['Cube']
    o.update_from_editmode()
    return [tuple(round(c, 5) for c in v.co) for v in o.data.vertices] + [tuple(round(c, 5) for c in o.location)]


def last_op():
    ops = bpy.context.window_manager.operators
    return ops[-1].bl_idname if len(ops) else None


def ic_tool_idle(tool):
    def gen():
        yield from edit_edges()
        with ctx():
            bpy.ops.mesh.select_all(action='SELECT')
            bpy.ops.wm.tool_set_by_id(name=tool)
        yield from wait(3)
        yield from move_to(*center())
        m0, op0 = mesh_snap(), last_op()
        cur0 = tuple(bpy.context.scene.cursor.location)
        v0 = view_state()
        yield from mmb_drag(60, 20)
        v1 = view_state()
        check(f"[{tool}] molette = pan", v0[0] != v1[0], f"modals={modals()}")
        v0 = view_state()
        yield from mmb_drag(60, 20, rmb=True)
        v1 = view_state()
        check(f"[{tool}] molette+droit = orbite", v0[1] != v1[1], f"modals={modals()}")
        yield from click('MIDDLEMOUSE')
        yield from wait(8)
        check(f"[{tool}] aucun operateur bloque", not modals(), modals())
        yield from key('ESC')
        check(f"[{tool}] maillage/objet NON modifie par la molette", mesh_snap() == m0)
        check(f"[{tool}] curseur 3D non deplace", tuple(bpy.context.scene.cursor.location) == cur0)
        check(f"[{tool}] derniere operation inchangee (panneau reglages)", last_op() == op0, f"{op0} -> {last_op()}")
        with ctx():
            bpy.ops.mesh.select_all(action='DESELECT')
            bpy.ops.wm.tool_set_by_id(name="builtin.select_box")
        yield from wait(2)
        x, y = visible_edge_mid()
        yield from move_to(x, y)
        yield from click('LEFTMOUSE')
        yield from wait(3)
        check(f"[{tool}] selection d'arete ensuite", sel_edges() >= 1, sel_edges())
    return gen


def ic_move_drag():
    yield from edit_edges()
    with ctx():
        bpy.ops.mesh.select_mode(type='FACE')
        bpy.ops.object.mode_set(mode='OBJECT')
        for f in bpy.data.objects['Cube'].data.polygons:
            f.select = f.normal.z > 0.9
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.wm.tool_set_by_id(name="builtin.move")
    yield from wait(3)
    o = bpy.data.objects['Cube']
    p = to_win(o.matrix_world @ Vector((0.3, 0.3, 1)))
    yield from move_to(*p)
    ev('LEFTMOUSE', 'PRESS'); yield
    yield from move_to(p[0] + 30, p[1] + 30, steps=8)
    yield from wait(3)
    m0 = modals()
    log("   modals pendant drag:", m0)
    v0 = view_state()
    yield from mmb_drag(60, 20)
    v1 = view_state()
    check("drag Move + molette: pan", v0[0] != v1[0], f"modals={modals()}")
    v0 = view_state()
    x, y = STATE['mx'], STATE['my']
    ev('MIDDLEMOUSE', 'PRESS', shift=True); yield
    yield from move_to(x + 60, y + 20)
    ev('MIDDLEMOUSE', 'RELEASE', shift=True); yield
    yield from wait(3)
    check("drag Move + Shift+molette: orbite", view_state()[1] != v0[1], f"modals={modals()}")
    check("drag Move: deplacement toujours en cours", bool(m0) and modals() == m0, f"{m0} -> {modals()}")
    ev('LEFTMOUSE', 'RELEASE'); yield
    yield from wait(3)
    yield from key('ESC')
    check("drag Move: termine proprement", not modals(), modals())


def ic_knife_cut():
    yield from edit_edges()
    with ctx():
        bpy.ops.wm.tool_set_by_id(name="builtin.knife")
    yield from wait(3)
    o = bpy.data.objects['Cube']
    p = to_win(o.matrix_world @ Vector((0.0, -1.0, 0.5)))
    yield from move_to(*p)
    yield from click('LEFTMOUSE')
    yield from move_to(p[0] + 30, p[1] + 10)
    yield from wait(3)
    m0 = modals()
    log("   modals couteau:", m0)
    v0 = view_state()
    yield from mmb_drag(60, 20)
    check("couteau en cours + molette: pan", view_state()[0] != v0[0], f"modals={modals()}")
    v0 = view_state()
    yield from mmb_drag(60, 20, rmb=True)
    check("couteau en cours + molette+droit: orbite", view_state()[1] != v0[1], f"modals={modals()}")
    check("couteau toujours actif", 'MESH_OT_knife_tool' in modals(), modals())
    yield from key('ESC')
    yield from key('ESC')
    yield from wait(3)
    check("couteau: termine proprement", not modals(), modals())


def ic_hud():
    # une vraie operation (deplacement par drag) puis navigation avec l'outil Move actif
    yield from edit_edges()
    with ctx():
        bpy.ops.mesh.select_mode(type='FACE')
        bpy.ops.object.mode_set(mode='OBJECT')
        for f in bpy.data.objects['Cube'].data.polygons:
            f.select = f.normal.z > 0.9
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.wm.tool_set_by_id(name="builtin.move")
    yield from wait(3)
    o = bpy.data.objects['Cube']
    p = to_win(o.matrix_world @ Vector((0.3, 0.3, 1)))
    yield from move_to(*p)
    ev('LEFTMOUSE', 'PRESS'); yield
    yield from move_to(p[0] + 20, p[1] + 25, steps=8)
    ev('LEFTMOUSE', 'RELEASE'); yield
    yield from wait(6)
    op0, h0, m0 = last_op(), hud(), mesh_snap()
    log("   apres drag: last op", op0, "hud", h0)
    yield from move_to(*center())
    yield from click('MIDDLEMOUSE')
    yield from wait(8)
    yield from mmb_drag(40, 20)
    yield from mmb_drag(40, 20, rmb=True)
    yield from wait(5)
    check("panneau 'Ajuster derniere operation' conserve (outil Move actif)",
          h0 and hud() and last_op() == op0, f"{op0}/{h0} -> {last_op()}/{hud()}")
    check("rien n'a bouge apres navigation (outil Move actif)", mesh_snap() == m0)


def ic_stuck():
    yield from edit_edges()
    yield from move_to(*center())
    ev('MIDDLEMOUSE', 'PRESS'); yield
    ev('WINDOW_DEACTIVATE', 'NOTHING'); yield
    yield from wait(3)
    check("perte focus pendant geste: plus de modal", not modals(), modals())
    ev('MIDDLEMOUSE', 'PRESS'); yield
    yield from move_to(STATE['mx'] + 20, STATE['my'] + 10)
    x, y = visible_edge_mid()
    STATE['mx'], STATE['my'] = x, y
    yield from click('LEFTMOUSE')
    yield from wait(3)
    check("relachement perdu + clic gauche: arete selectionnee", sel_edges() >= 1, sel_edges())
    check("relachement perdu + clic gauche: plus de modal", not modals(), modals())
    ev('MIDDLEMOUSE', 'PRESS'); yield
    yield from key('THREE')
    yield from wait(3)
    sm = tuple(bpy.context.scene.tool_settings.mesh_select_mode)
    check("relachement perdu + touche 3: mode face", sm == (False, False, True), sm)
    check("relachement perdu + touche: plus de modal", not modals(), modals())


def ic_prefs_restore():
    kc = bpy.context.window_manager.keyconfigs.user
    def tool_mmb():
        return [k.active for km in kc.keymaps if (not km.is_modal) and km.name.startswith("3D View Tool:")
                for k in km.keymap_items if k.type == 'MIDDLEMOUSE' and (k.any or k.alt != 1)]
    def knife_pan():
        return [k.is_user_defined for k in kc.keymaps['Knife Tool Modal Map'].keymap_items
                if k.propvalue == 'PANNING' and k.type == 'MIDDLEMOUSE' and (k.any or k.alt != 1)]
    t = tool_mmb()
    check("outils: raccourcis molette coupes", t and not any(t), f"{sum(t)}/{len(t)} actifs")
    check("couteau: panning molette ajoute", len(knife_pan()) == 1, knife_pan())
    addon_utils.disable("frwa_cad_navigation", default_set=True)
    yield from wait(3)
    t = tool_mmb()
    check("desactivation: raccourcis molette des outils retablis", t and all(t), f"{sum(t)}/{len(t)} actifs")
    kp = knife_pan()
    check("desactivation: panning couteau retire (si ajoute)", not any(kp), kp)
    addon_utils.enable("frwa_cad_navigation", default_set=True)
    yield from wait(30)
    t = tool_mmb()
    check("reactivation: raccourcis molette coupes", t and not any(t), f"{sum(t)}/{len(t)} actifs")


IC_SCENARIOS = [
    ("pan", sc_pan),
    ("orbit", sc_orbit),
    ("zoom", sc_zoom),
    ("zoom_toggle", sc_zoom_toggle),
    ("mmb_click", sc_mmb_click),
    ("select_edge", sc_select_edge),
    ("context_menu", sc_context_menu),
] + [(f"tool_{t}", ic_tool_idle(f"builtin.{t}")) for t in (
    "move", "rotate", "scale", "transform", "cursor", "measure", "annotate",
    "extrude_region", "inset_faces", "bevel", "loop_cut", "knife", "edge_slide",
    "spin", "poly_build", "shrink_fatten", "rip_region")] + [
    ("move_drag", ic_move_drag),
    ("knife_cut", ic_knife_cut),
    ("hud", ic_hud),
    ("stuck", ic_stuck),
    ("prefs_restore", ic_prefs_restore),
]


def sc_mods():
    for mods, label in (({'shift': True}, 'shift+molette'), ({'ctrl': True}, 'ctrl+molette')):
        yield from move_to(*center())
        v0 = view_state()
        x, y = STATE['mx'], STATE['my']
        ev('MIDDLEMOUSE', 'PRESS', **mods); yield
        yield from move_to(x + 60, y + 40)
        ev('MIDDLEMOUSE', 'RELEASE', **mods); yield
        yield from wait(3)
        check(f"{label}: navigation Blender native ok", view_state() != v0 and not modals(), modals())


def sc_probe():
    starts = [("G", [('G', {})], 'all'), ("E", [('E', {})], 'face'), ("CtrlR", [('R', {'ctrl': True})], None),
              ("CtrlB", [('B', {'ctrl': True})], 'all'), ("I", [('I', {})], 'face'), ("K", [('K', {})], None)]
    gestures = [("MMB", {}, False), ("MMB+RMB", {}, True), ("Shift+MMB", {'shift': True}, False),
                ("Ctrl+MMB", {'ctrl': True}, False), ("Alt+MMB", {'alt': True}, False)]
    for sname, keys, prep in starts:
        for gname, mods, rmb in gestures:
            yield from reset()
            yield from edit_edges()
            with ctx():
                if prep == 'all':
                    bpy.ops.mesh.select_all(action='SELECT')
                if prep == 'face':
                    bpy.ops.mesh.select_mode(type='FACE')
                    bpy.ops.object.mode_set(mode='OBJECT')
                    for f in bpy.data.objects['Cube'].data.polygons:
                        f.select = f.normal.z > 0.9
                    bpy.ops.object.mode_set(mode='EDIT')
            cx, cy = center()
            yield from move_to(cx - 40, cy - 30)
            for k, m in keys:
                yield from key(k, **m)
            yield from wait(3)
            m0 = modals()
            v0 = view_state()
            x, y = STATE['mx'], STATE['my']
            ev('MIDDLEMOUSE', 'PRESS', **mods); yield
            if rmb:
                ev('RIGHTMOUSE', 'PRESS'); yield
            yield from move_to(x + 70, y + 30)
            if rmb:
                ev('RIGHTMOUSE', 'RELEASE'); yield
            ev('MIDDLEMOUSE', 'RELEASE', **mods); yield
            yield from wait(3)
            v1 = view_state()
            what = [n for n, i in (("pan", 0), ("rot", 1), ("dist", 2)) if v0[i] != v1[i]]
            log(f"PROBE {sname:6s} {gname:10s} vue={what or 'immobile'} modal_avant={m0} apres={modals()}")
            yield from key('ESC'); yield from key('ESC')


def native_setup(variant):
    wm = bpy.context.window_manager
    ku = wm.keyconfigs.user
    ka = wm.keyconfigs.addon
    km = ka.keymaps.new(name='3D View', space_type='VIEW_3D')
    km.keymap_items.new('view3d.move', 'MIDDLEMOUSE', 'PRESS')
    for name, prop, val in (('View3D Move Modal', 'SWITCH_TO_ROTATE', 'PRESS'),
                            ('View3D Rotate Modal', 'SWITCH_TO_MOVE', 'RELEASE')):
        kmu = ku.keymaps[name]
        log(name, [(k.propvalue, k.type, k.value) for k in kmu.keymap_items])
        for k in kmu.keymap_items:
            if k.type == 'RIGHTMOUSE':
                k.active = False
        try:
            kma = ka.keymaps.new(name=name, space_type='EMPTY', region_type='WINDOW', modal=True)
            kma.keymap_items.new_modal(prop, 'RIGHTMOUSE', val, any=True)
            log("added", name, prop)
        except Exception as e:
            log("ERR", name, e)
            k = kmu.keymap_items.new_modal(prop, 'RIGHTMOUSE', val, any=True)
            log("added on user", name, prop)
    if 'noalt' in variant:
        kt = ku.keymaps['Transform Modal Map']
        for k in kt.keymap_items:
            if k.propvalue in ('PASSTHROUGH_NAVIGATE', 'AUTOCONSTRAIN', 'AUTOCONSTRAINPLANE'):
                k.active = False
        log("transform: passthrough/autoconstrain disabled")
    if 'nocons' in variant:
        kt = ku.keymaps['Transform Modal Map']
        for k in kt.keymap_items:
            if k.propvalue in ('AUTOCONSTRAIN', 'AUTOCONSTRAINPLANE'):
                k.active = False
        log("transform: autoconstrain disabled")
    ku.keymaps['3D View'].keymap_items  # touch
    wm.keyconfigs.update()


def noconstraint():
    _kmu = bpy.context.window_manager.keyconfigs.user.keymaps.get('Transform Modal Map')
    if _kmu:
        for _k in _kmu.keymap_items:
            if _k.type in ('MIDDLEMOUSE',):
                _k.active = False
        log("MMB transform constraint disabled")
    else:
        log("no Transform Modal Map yet")


SCENARIOS = [
    ("probe", sc_probe),
    ("pan", sc_pan),
    ("orbit", sc_orbit),
    ("zoom", sc_zoom),
    ("mmb_click", sc_mmb_click),
    ("mods", sc_mods),
    ("select_edge", sc_select_edge),
    ("grab_G", _nav_during([('G', {})], "Grab G", prep='all')),
    ("rotate_R", _nav_during([('R', {})], "Rotate R", prep='all')),
    ("extrude_E", _nav_during([('E', {})], "Extrude E", prep='face')),
    ("knife_K", _nav_during([('K', {})], "Couteau K")),
    ("loopcut", _nav_during([('R', {'ctrl': True})], "Loop cut Ctrl+R", limit=True)),
    ("bevel", _nav_during([('B', {'ctrl': True})], "Bevel Ctrl+B", prep='all', limit=True)),
    ("inset", _nav_during([('I', {})], "Inset I", prep='face', limit=True)),
    ("tool_move", sc_toolbar("builtin.move", "Move")),
    ("tool_extrude", sc_toolbar("builtin.extrude_region", "Extrude")),
    ("tool_knife", sc_toolbar("builtin.knife", "Knife")),
    ("tool_loopcut", sc_toolbar("builtin.loop_cut", "Loop Cut")),
    ("tool_bevel", sc_toolbar("builtin.bevel", "Bevel")),
    ("tool_measure", sc_toolbar("builtin.measure", "Measure")),
    ("tool_cursor", sc_toolbar("builtin.cursor", "Cursor")),
    ("hud", sc_hud),
    ("stuck", sc_stuck),
    ("stuck2", sc_stuck2),
    ("zoom_toggle", sc_zoom_toggle),
    ("context_menu", sc_context_menu),
    ("gizmo_drag", sc_gizmo_drag),
    ("prefs_restore", sc_prefs_restore),
]


if os.environ.get("HARNESS_IC"):
    SCENARIOS = IC_SCENARIOS


def main():
    yield from wait(20)
    w = win()
    log("window", w.width, w.height, "screen", w.screen.name)
    _km = bpy.context.window_manager.keyconfigs.user.keymaps['3D View']
    log("user 3D View MMB order:", [(k.idname, k.shift, k.ctrl, k.active) for k in _km.keymap_items if k.type == 'MIDDLEMOUSE'][:8])
    if os.environ.get("HARNESS_NOCONSTRAINT"):
        noconstraint()
    if os.environ.get("HARNESS_NATIVE"):
        native_setup(os.environ.get("HARNESS_NATIVE"))
    for name, sc in SCENARIOS:
        if ONLY and name not in ONLY.split(","):
            continue
        if not ONLY and name == "probe":
            continue
        log("==", name)
        try:
            yield from reset()
            yield from sc()
        except Exception:
            log(traceback.format_exc())
            RESULTS.append((name + " (exception)", False))
    ok = sum(1 for _, r in RESULTS if r)
    log(f"TOTAL {ok}/{len(RESULTS)}")
    for n, r in RESULTS:
        if not r:
            log("  echec:", n)
    LOG.close()
    bpy.ops.wm.quit_blender()


GEN = main()


def tick():
    try:
        next(GEN)
    except StopIteration:
        return None
    except Exception:
        log(traceback.format_exc())
        LOG.close()
        bpy.ops.wm.quit_blender()
        return None
    return 0.03


bpy.app.timers.register(tick, first_interval=0.5)
