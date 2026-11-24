# Rejoue le tutoriel "Fantome tirelire - Etape 1" comme un utilisateur
# (keymap Industry Compatible + extension FrWA CAD Navigation).
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, bmesh
from mathutils import Vector
from simlib import *
import simlib

S = os.path.dirname(os.path.abspath(__file__))
TAG = os.environ.get("TUTO_TAG", "run")
STOP = os.environ.get("TUTO_STOP", "")
NAV = os.environ.get("TUTO_NAV", "cad")        # cad | native_ic
simlib.SHOTDIR[0] = os.path.join(S, "shots_" + TAG)
os.makedirs(simlib.SHOTDIR[0], exist_ok=True)
ISSUES = []


def issue(msg):
    ISSUES.append(msg)
    log("ISSUE", msg)


# ---------------------------------------------------------------- etat
def obj():
    return bpy.data.objects.get("Fantome") or bpy.data.objects.get("Cylinder")


def mesh_state():
    o = obj()
    if o is None:
        return None
    if o.mode == 'EDIT':
        o.update_from_editmode()
    me = o.data
    return (len(me.vertices), len(me.faces) if hasattr(me, 'faces') else len(me.polygons),
            tuple(round(c, 3) for v in me.vertices for c in v.co),
            tuple(v.select for v in me.vertices),
            tuple(round(c, 3) for c in o.location), o.mode)


def tool_id():
    w = win()
    mode = bpy.context.mode
    m = {'EDIT_MESH': 'EDIT_MESH', 'OBJECT': 'OBJECT'}.get(mode, mode)
    t = w.workspace.tools.from_space_view3d_mode(m)
    return t.idname if t else None


def snapshot():
    return dict(mesh=mesh_state(), last=last_op(), hud=hud(), tool=tool_id(),
                mode=bpy.context.mode, objs=sorted(o.name for o in bpy.data.objects))


# ----------------------------------------------------- navigation testee
def alt_drag(btn, dx, dy):
    x, y = STATE['mx'], STATE['my']
    ev(btn, 'PRESS', alt=True); yield
    yield from move_to(x + dx, y + dy, steps=8)
    ev(btn, 'RELEASE', alt=True); yield
    yield from wait(3)


def nav_orbit(dx, dy):
    if NAV == "cad":
        yield from cad_orbit(dx, dy)
    else:
        yield from alt_drag('LEFTMOUSE', dx, dy)


def nav_pan(dx, dy):
    if NAV == "cad":
        yield from cad_pan(dx, dy)
    else:
        yield from alt_drag('MIDDLEMOUSE', dx, dy)


def nav_set(label, gestures=("pan", "orbit", "zoom", "shift", "wheel", "click")):
    """Gestes de navigation comme entre deux etapes du tuto ; verifie l'absence d'effet de bord."""
    s0 = snapshot()
    v0 = view_state()
    moved = {}
    for g in gestures:
        before = view_state()
        if NAV == "cad":
            if g == "pan":
                yield from cad_pan(50, 20)
            elif g == "orbit":
                yield from cad_orbit(50, 20)
            elif g == "zoom":
                yield from cad_zoom(-30)
                moved[g] = view_state() != before
                yield from cad_zoom(30)
                continue
            elif g == "shift":
                yield from shift_orbit(-40, -10)
            elif g == "wheel":
                yield from wheel(1, True)
                yield from wheel(1, False)
            elif g == "click":
                yield from click('MIDDLEMOUSE')
                yield from wait(8)
        else:  # navigation native Industry Compatible : Alt + boutons
            x, y = STATE['mx'], STATE['my']
            btn = {"pan": 'MIDDLEMOUSE', "orbit": 'LEFTMOUSE', "zoom": 'RIGHTMOUSE'}.get(g)
            if btn:
                ev(btn, 'PRESS', alt=True); yield
                yield from move_to(x + 50, y + 20)
                ev(btn, 'RELEASE', alt=True); yield
                yield from wait(3)
            elif g == "wheel":
                yield from wheel(1, True)
                moved[g] = view_state() != before
                yield from wheel(1, False)
                continue
            else:
                continue            # pas d'equivalent natif (Shift+molette, clic molette)
        moved[g] = view_state() != before
    yield from wait(3)
    s1 = snapshot()
    bad = [k for k in s0 if s0[k] != s1[k]]
    check(f"[{label}] navigation sans effet de bord", not bad and not modals(),
          f"change: {bad} modals={modals()} " + (f"last {s0['last']}->{s1['last']}" if 'last' in bad else ""))
    still = [g for g, m in moved.items() if not m and g != "wheel"]
    check(f"[{label}] chaque geste bouge la vue", not still, f"immobiles: {still}")


# ------------------------------------------------------------- HUD
HUD_FIELD = {"Vertices": 43, "Radius": 65, "Depth": 87, "Location Z": 214}


def hud_region():
    _, a, _, _ = v3d()
    for r in a.regions:
        if r.type == 'HUD':
            return r
    return None


def set_hud_field(name, value):
    r = hud_region()
    if r is None:
        issue(f"panneau HUD absent pour regler {name}")
        return
    top = r.y + r.height
    x, y = 257, top - HUD_FIELD[name]
    yield from move_to(x, y)
    yield from dclick('LEFTMOUSE')
    yield from wait(3)
    yield from key('A', ctrl=True)
    yield from type_text(str(value))
    yield from key('RET')
    yield from wait(6)


# ------------------------------------------------------ gizmos (pixels)
def gizmo_point(kind, near):
    """Cherche la poignee d'un gizmo sur une capture d'ecran."""
    path = shot(f"gizmo_{kind}_{len(RESULTS)}")
    import numpy as np
    if kind == "plus":       # poignee + jaune de l'outil Extrude
        test = lambda r, g, b: (r > 0.85) & (g > 0.75) & (b < 0.35)
    else:                    # grand cercle blanc de l'outil Scale
        test = lambda r, g, b: (r > 0.93) & (g > 0.93) & (b > 0.93)
    xs, ys, _ = find_color_blobs(path, test, region_rect())
    if len(xs) == 0:
        return None
    nx, ny = near
    d = np.hypot(xs - nx, ys - ny)
    if kind == "plus":
        i = int(np.argmin(d))
        # centre du petit amas autour du pixel le plus proche
        sel = np.hypot(xs - xs[i], ys - ys[i]) < 12
        return float(xs[sel].mean()), float(ys[sel].mean())
    # cercle : rayon dominant autour du centre de la selection
    ok = (d > 25) & (d < 400)
    if not ok.any():
        return None
    rad = np.median(d[ok])
    ring = ok & (np.abs(d - rad) < 4)
    # point du cercle a droite du centre (le plus horizontal)
    cand = np.nonzero(ring)[0]
    j = cand[np.argmin(np.abs(ys[cand] - ny) - (xs[cand] - nx) * 0.01)]
    return float(xs[j]), float(ys[j])


def sel_center_win():
    o = obj()
    o.update_from_editmode()
    vs = [o.matrix_world @ v.co for v in o.data.vertices if v.select]
    c = sum(vs, Vector()) / len(vs)
    return to_win(c), c


def drag_gizmo(kind, value, nav_during=False):
    """Equivalent du glisser de la poignee : meme operateur modal que le gizmo,
    puis vraie souris, saisie clavier, navigation et validation."""
    (cx, cy), _ = sel_center_win()
    yield from move_to(cx, cy + 40)
    yield from wait(2)
    with ctx():
        if kind == "plus":
            bpy.ops.view3d.edit_mesh_extrude_move_normal('INVOKE_DEFAULT')
        else:
            bpy.ops.transform.resize('INVOKE_DEFAULT')
    yield from wait(3)
    yield from move_to(cx + 10, cy + 70, steps=8)
    m = modals()
    log("   modal pendant le glisser:", m)
    if not m:
        issue(f"operation '{kind}' non demarree")
        return False
    if nav_during:
        v0 = view_state()
        yield from nav_pan(40, 0)
        check(f"{kind}: molette = pan PENDANT l'operation", view_state()[0] != v0[0], f"modals={modals()}")
        v0 = view_state()
        if NAV == "cad":
            yield from shift_orbit(40, 10)
        else:
            yield from nav_orbit(40, 10)
        check(f"{kind}: Shift+molette = orbite PENDANT l'operation", view_state()[1] != v0[1], f"modals={modals()}")
        check(f"{kind}: operation toujours en cours apres navigation", modals() == m, f"{m} -> {modals()}")
    yield from type_text(str(value))
    yield from wait(3)
    yield from key('RET')
    yield from wait(6)
    return True


def orbit_until(pred, label, step=(0, 60), maxn=8):
    for _ in range(maxn):
        w, a, r, rv = v3d()
        if pred(rv.view_rotation @ Vector((0, 0, -1))):
            return True
        yield from nav_orbit(*step)
    w, a, r, rv = v3d()
    ok = pred(rv.view_rotation @ Vector((0, 0, -1)))
    check(f"orbite CAD : {label}", ok)
    return ok


def ring_stats():
    """(z, rayon) des boucles du maillage, en coordonnees monde."""
    o = obj()
    o.update_from_editmode()
    rings = {}
    for v in o.data.vertices:
        w = o.matrix_world @ v.co
        rings.setdefault(round(w.z, 2), []).append(math.hypot(w.x, w.y))
    return sorted((z, round(max(rs), 2)) for z, rs in rings.items())


def select_face_by_click(world_pt, label):
    p = to_win(world_pt)
    yield from move_to(*p)
    yield from click('LEFTMOUSE')
    yield from wait(4)
    o = obj()
    o.update_from_editmode()
    sel = [f for f in o.data.polygons if f.select]
    log(f"   {label}: faces selectionnees {len(sel)} normales {[tuple(round(c,2) for c in f.normal) for f in sel]}")
    return sel


# ================================================================ TUTO
def main():
    yield from wait(25)
    log("keymap", bpy.context.window_manager.keyconfigs.active.name, "nav", NAV)
    STATE['mx'], STATE['my'] = center()
    x0, y0, rw, rh = region_rect()
    yield from move_to(x0 + 150, y0 + 150)
    yield from click('LEFTMOUSE')          # ferme le splash
    yield from wait(5)
    yield from move_to(*center())

    # ---- 1.1 tout supprimer
    yield from key('A', ctrl=True)
    yield from wait(3)
    yield from key('DEL')
    yield from wait(5)
    check("1.1 Ctrl+A + Suppr : scene vide", len(bpy.data.objects) == 0, [o.name for o in bpy.data.objects])
    yield from nav_set("scene vide", ("pan", "orbit", "zoom", "shift"))

    # ---- 1.2 unites (panneau Scene : fait par script)
    us = bpy.context.scene.unit_settings
    us.scale_length = 0.001
    us.length_unit = 'MILLIMETERS'
    with ctx():
        bpy.ops.ed.undo_push(message="Unites mm")   # comme un reglage fait dans l'interface

    # ---- 2.1 ajouter un cylindre (recherche Tab)
    yield from move_to(*center())
    yield from key('TAB')
    yield from wait(5)
    yield from type_text("cylinder")
    yield from wait(5)
    yield from key('RET')
    yield from wait(8)
    check("2.1 cylindre ajoute", obj() is not None and last_op() == 'MESH_OT_primitive_cylinder_add', last_op())
    shot("s021_cylindre_ajoute")

    # ---- 2.2 panneau Add Cylinder
    r = hud_region()
    yield from move_to(r.x + 40, r.y + r.height - 12)
    yield from click('LEFTMOUSE')
    yield from wait(6)
    yield from move_to(*center())
    yield from nav_set("panneau Add Cylinder ouvert")
    check("2.2 panneau Add Cylinder toujours la apres navigation", hud() and last_op() == 'MESH_OT_primitive_cylinder_add')
    yield from set_hud_field("Vertices", 24)
    yield from set_hud_field("Radius", 40)
    yield from move_to(*center())
    yield from nav_set("entre deux champs du panneau", ("pan", "orbit", "click"))
    yield from set_hud_field("Depth", 100)
    yield from set_hud_field("Location Z", 50)
    o = obj()
    check("2.2 cylindre 24 / 40 / 100 / Z=50",
          o and len(o.data.vertices) == 48 and tuple(round(d, 2) for d in o.dimensions) == (80.0, 80.0, 100.0)
          and round(o.location.z, 2) == 50.0,
          f"verts={len(o.data.vertices)} dims={tuple(round(d,2) for d in o.dimensions)} loc={tuple(o.location)}")
    shot("s022_cylindre_regle")

    # ---- 2.3 renommer : double-clic Outliner non simulable (Blender ne
    # fabrique pas de double-clic a partir d'evenements simules) -> script
    obj().name = "Fantome"
    check("2.3 objet renomme Fantome", bpy.data.objects.get("Fantome") is not None)

    # cadrer comme le ferait l'utilisateur (F) puis naviguer
    yield from move_to(*center())
    yield from key('F')
    yield from wait(15)
    shot("s024_cadre")
    log("   vue apres F:", view_state())
    yield from nav_set("objet Fantome", ("orbit", "pan", "zoom"))
    yield from key('F')
    yield from wait(15)
    log("   vue avant mode edition:", view_state())

    # ---- 3.1 mode edition faces + clic face du dessus
    yield from key('THREE')
    yield from wait(5)
    check("3.1 touche 3 : mode edition faces", bpy.context.mode == 'EDIT_MESH'
          and tuple(bpy.context.scene.tool_settings.mesh_select_mode) == (False, False, True))
    yield from move_to(*center())
    yield from orbit_until(lambda d: d.z < -0.5, "vue plongeante sur le dessus", (0, -50))
    if os.environ.get("TUTO_REFRAME"):
        yield from key('A'); yield from wait(12)      # recadrer (Industry : A = tout voir)
    sel = yield from select_face_by_click(Vector((0, 0, 100)), "face du haut")
    check("3.1 clic : face du dessus selectionnee", len(sel) == 1 and sel[0].normal.z > 0.99)
    yield from move_to(*center())
    yield from nav_set("face du haut selectionnee")
    shot("s031_face_haut")
    if STOP == "3.1":
        return

    # ---- 3.2 a 3.4 extrusions + echelles
    for i, (h, sc) in enumerate(((25, 0.85), (15, 0.7), (7, 0.5)), 1):
        yield from key('E', ctrl=True)
        yield from wait(5)
        check(f"3.{i+1} Ctrl+E : outil Extrude actif", tool_id() == 'builtin.extrude_region', tool_id())
        yield from move_to(*center())
        yield from nav_set(f"outil Extrude actif (etage {i})", ("pan", "orbit", "click", "zoom"))
        z_before = max(z for z, _ in ring_stats())
        ok = yield from drag_gizmo("plus", h, nav_during=(i == 1))
        z_after = max(z for z, _ in ring_stats())
        check(f"etage {i}: extrusion de {h} mm", ok and abs(z_after - z_before - h) < 0.01, f"{z_before} -> {z_after}")
        yield from move_to(*center())
        yield from nav_set(f"apres extrusion {i} (panneau)")
        yield from key('Q')
        yield from key('R')
        yield from wait(5)
        check(f"etage {i}: Q puis R : outil Scale", tool_id() == 'builtin.scale', tool_id())
        r_before = dict(ring_stats())[z_after]
        ok = yield from drag_gizmo("circle", sc)
        r_after = dict(ring_stats())[z_after]
        check(f"etage {i}: echelle {sc}", ok and abs(r_after / r_before - sc) < 0.002, f"{r_before} -> {r_after}")
        yield from move_to(*center())
        yield from nav_set(f"apres echelle {i}")
    shot("s034_tete")
    check("3.4 hauteur de la tete = 147 mm", abs(max(z for z, _ in ring_stats()) - 147) < 0.01, ring_stats())
    if STOP == "3.4":
        return

    # ---- 4.1 tourner la vue pour voir dessous et supprimer la face
    yield from key('Q')
    yield from move_to(*center())
    yield from key('A')            # Industry : A = tout voir
    yield from wait(10)
    yield from orbit_until(lambda d: d.z > 0.45, "vue par en dessous", (0, 60), 10)
    if os.environ.get("TUTO_REFRAME"):
        yield from key('A'); yield from wait(12)
    w, a, r, rv = v3d()
    view_dir = rv.view_rotation @ Vector((0, 0, -1))
    check("4.1 orbite : la vue regarde le dessous", view_dir.z > 0.2, f"dir={tuple(round(c,2) for c in view_dir)}")
    sel = yield from select_face_by_click(Vector((0, 0, 0)), "face du dessous")
    check("4.1 clic : face du dessous selectionnee", len(sel) == 1 and sel[0].normal.z < -0.99)
    nf0 = len(obj().data.polygons)
    x0, y0, rw, rh = region_rect()
    mx, my = x0 + rw // 2, y0 + rh - 200      # menu ouvert en haut : pas decale
    yield from move_to(mx, my)
    yield from key('DEL')
    yield from wait(8)
    yield from move_to(mx + 20, my - 44)       # 1re ligne "Vertices" sous le curseur -> "Faces"
    yield from wait(3)
    shot("s041_menu_delete")
    yield from click('LEFTMOUSE')
    yield from wait(6)
    obj().update_from_editmode()
    check("4.1 face du dessous supprimee", len(obj().data.polygons) == nf0 - 1, f"{nf0} -> {len(obj().data.polygons)}")
    yield from move_to(*center())
    yield from nav_set("dessous ouvert")

    # ---- 4.2 boucle du bas
    yield from key('TWO')
    yield from wait(4)
    o = obj(); o.update_from_editmode()
    bottom = [e for e in o.data.edges if all(abs((o.matrix_world @ o.data.vertices[i].co).z) < 0.01 for i in e.vertices)]
    e = bottom[len(bottom) // 3]
    mid = o.matrix_world @ ((o.data.vertices[e.vertices[0]].co + o.data.vertices[e.vertices[1]].co) / 2)
    yield from move_to(*to_win(mid))
    yield from wait(2)
    # double-clic = mesh.loop_select (keymap Industry) : appele a la position souris
    with ctx():
        bpy.ops.mesh.loop_select('INVOKE_DEFAULT')
    yield from wait(5)
    o.update_from_editmode()
    nsel = sum(1 for e in o.data.edges if e.select)
    check("4.2 double-clic : boucle du bas selectionnee (24 aretes)", nsel == 24, nsel)
    yield from move_to(*center())
    yield from nav_set("boucle du bas selectionnee")

    # ---- 4.3 evaser 1.3
    yield from key('Q')
    yield from key('R')
    yield from wait(5)
    rb = dict(ring_stats())[0.0]
    ok = yield from drag_gizmo("circle", 1.3)
    ra = dict(ring_stats())[0.0]
    check("4.3 evasement 1.3 (rayon 40 -> 52)", ok and abs(ra - 52) < 0.05, f"{rb} -> {ra}")
    yield from move_to(*center())
    yield from nav_set("apres evasement")
    shot("s043_evase")

    # ---- 5 lisser
    yield from key('FOUR')
    yield from wait(5)
    check("5.1 touche 4 : mode objet", bpy.context.mode == 'OBJECT')
    o = obj()
    m = o.modifiers.new("Subdivision", 'SUBSURF')
    m.levels = 2; m.render_levels = 2
    yield from wait(3)
    yield from move_to(*center())
    yield from click('RIGHTMOUSE')
    yield from wait(6)
    shot("s052_menu_contextuel")
    yield from key('RET')
    yield from wait(6)
    smooth = all(p.use_smooth for p in o.data.polygons)
    check("5.2 clic droit > Shade Smooth", smooth, last_op())
    yield from nav_set("resultat final")
    dg = bpy.context.evaluated_depsgraph_get()
    dims = tuple(round(d, 1) for d in o.evaluated_get(dg).dimensions)
    log("dimensions finales", dims, "brut", tuple(round(d, 1) for d in o.dimensions))
    check("fin : environ 104 x 104 x 147 mm", abs(o.dimensions.x - 104) < 0.5 and abs(o.dimensions.z - 147) < 0.5, dims)
    shot("s060_final")
    us = bpy.context.scene.unit_settings
    log("unites en fin de tuto:", us.system, us.scale_length, us.length_unit)
    if us.length_unit != 'MILLIMETERS':
        issue(f"Length est repasse sur {us.length_unit} (Unit Scale = {us.scale_length})")
    log("outil de selection en fin:", tool_id())
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(S, f"tuto_{TAG}.blend"), copy=True)


def done():
    log("ISSUES:", len(ISSUES))
    for i in ISSUES:
        log("  -", i)


run(main, os.path.join(S, f"tuto_{TAG}.txt"), done)
