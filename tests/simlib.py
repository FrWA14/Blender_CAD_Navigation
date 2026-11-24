# Bibliotheque de simulation d'evenements pour Blender (GUI + --enable-event-simulate)
import bpy, os, traceback
from mathutils import Vector
from bpy_extras.view3d_utils import location_3d_to_region_2d

STATE = {'mx': 0, 'my': 0}
RESULTS = []
_LOG = [None]
SHOTDIR = [None]


def set_log(path):
    _LOG[0] = open(path, "w", encoding="utf-8")


def log(*a):
    s = " ".join(str(x) for x in a)
    if _LOG[0]:
        _LOG[0].write(s + "\n"); _LOG[0].flush()
    print("[T]", s)


def check(name, cond, info=""):
    RESULTS.append((name, bool(cond)))
    log(("OK  " if cond else "FAIL"), name, info)
    return bool(cond)


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


def ev(t, v='NOTHING', x=None, y=None, **kw):
    if x is None:
        x, y = STATE['mx'], STATE['my']
    STATE['mx'], STATE['my'] = x, y
    win().event_simulate(t, v, x=int(x), y=int(y), **kw)


def center():
    w, a, r, _ = v3d()
    return r.x + r.width // 2, r.y + r.height // 2


def region_rect():
    w, a, r, _ = v3d()
    return r.x, r.y, r.width, r.height


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
            round(rv.view_distance, 4), rv.view_perspective)


def hud():
    _, a, _, _ = v3d()
    return any(r.type == 'HUD' for r in a.regions)


def last_op():
    ops = bpy.context.window_manager.operators
    return ops[-1].bl_idname if len(ops) else None


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


def dclick(t='LEFTMOUSE'):
    ev(t, 'PRESS'); yield
    ev(t, 'RELEASE'); yield
    ev(t, 'PRESS'); yield
    ev(t, 'RELEASE'); yield


def key(k, **mods):
    ev(k, 'PRESS', **mods); yield
    ev(k, 'RELEASE', **mods); yield


_CH = {'.': 'PERIOD', ' ': 'SPACE', '-': 'MINUS', ',': 'COMMA'}
_DIG = ['ZERO', 'ONE', 'TWO', 'THREE', 'FOUR', 'FIVE', 'SIX', 'SEVEN', 'EIGHT', 'NINE']


def type_text(s):
    for ch in s:
        if ch.isdigit():
            t = _DIG[int(ch)]
        elif ch.isalpha():
            t = ch.upper()
        else:
            t = _CH[ch]
        ev(t, 'PRESS', unicode=ch); yield
        ev(t, 'RELEASE'); yield


# --- gestes de navigation CAD ---------------------------------------------
def cad_pan(dx=60, dy=25):
    x, y = STATE['mx'], STATE['my']
    ev('MIDDLEMOUSE', 'PRESS'); yield
    yield from move_to(x + dx, y + dy)
    ev('MIDDLEMOUSE', 'RELEASE'); yield
    yield from wait(2)


def cad_orbit(dx=60, dy=25):
    x, y = STATE['mx'], STATE['my']
    ev('MIDDLEMOUSE', 'PRESS'); yield
    ev('RIGHTMOUSE', 'PRESS'); yield
    yield from move_to(x + dx, y + dy, steps=8)
    ev('RIGHTMOUSE', 'RELEASE'); yield
    ev('MIDDLEMOUSE', 'RELEASE'); yield
    yield from wait(2)


def cad_zoom(dy=40):
    x, y = STATE['mx'], STATE['my']
    ev('MIDDLEMOUSE', 'PRESS'); yield
    yield from click('RIGHTMOUSE')
    yield from move_to(x, y + dy)
    ev('MIDDLEMOUSE', 'RELEASE'); yield
    yield from wait(2)


def shift_orbit(dx=60, dy=20):
    x, y = STATE['mx'], STATE['my']
    ev('MIDDLEMOUSE', 'PRESS', shift=True); yield
    yield from move_to(x + dx, y + dy)
    ev('MIDDLEMOUSE', 'RELEASE', shift=True); yield
    yield from wait(2)


def wheel(n=1, up=True):
    for _ in range(n):
        ev('WHEELUPMOUSE' if up else 'WHEELDOWNMOUSE', 'PRESS'); yield
    yield from wait(2)


# --- captures d'ecran ----------------------------------------------------
def shot(name):
    if not SHOTDIR[0]:
        return None
    path = os.path.join(SHOTDIR[0], name + ".png")
    w = win()
    with bpy.context.temp_override(window=w, screen=w.screen, area=w.screen.areas[0]):
        bpy.ops.screen.screenshot(filepath=path, check_existing=False)
    return path


def find_color_blobs(path, test, region=None):
    """Retourne la liste des pixels (x, y en coords fenetre) verifiant test(r,g,b)."""
    import numpy as np
    img = bpy.data.images.load(path, check_existing=False)
    w, h = img.size
    px = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    bpy.data.images.remove(img)
    px = px.reshape(h, w, 4)
    r, g, b = px[..., 0], px[..., 1], px[..., 2]
    mask = test(r, g, b)
    if region:
        x0, y0, rw, rh = region
        m2 = np.zeros_like(mask)
        m2[y0:y0 + rh, x0:x0 + rw] = mask[y0:y0 + rh, x0:x0 + rw]
        mask = m2
    ys, xs = np.nonzero(mask)
    return xs, ys, (w, h)


def run(gen_fn, log_path, done_cb=None):
    """Execute un generateur pas a pas dans un timer puis quitte Blender."""
    set_log(log_path)
    G = gen_fn()

    def tick():
        try:
            next(G)
        except StopIteration:
            finish()
            return None
        except Exception:
            log(traceback.format_exc())
            finish()
            return None
        return 0.03

    def finish():
        ok = sum(1 for _, r in RESULTS if r)
        log(f"TOTAL {ok}/{len(RESULTS)}")
        for n, r in RESULTS:
            if not r:
                log("  echec:", n)
        if done_cb:
            try:
                done_cb()
            except Exception:
                log(traceback.format_exc())
        _LOG[0].close()
        bpy.ops.wm.quit_blender()

    bpy.app.timers.register(tick, first_interval=0.5)
