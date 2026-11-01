# 斷在學校：讀入原始模型 src/斷在學校.glb，提高精度後匯出 斷在學校.glb
# 執行：blender --background --factory-startup --python 斷在學校.py
# 角色、警車與前端用到的物件名稱不動；新增的細部要避開 main.html planFor() 的走位路線（改完跑 ?check）。
import bpy, bmesh, math, random, os
from mathutils import Vector, Matrix, noise

OUT = os.path.dirname(os.path.abspath(__file__))
NAME = '斷在學校'
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=os.path.join(OUT, 'src', NAME + '.glb'))
scene = bpy.context.scene
OB = bpy.data.objects
random.seed(5)

# ---------- 共用工具（Blender 世界座標，z 朝上） ----------
def material(name, hexcol=None, rough=.8):
    m = bpy.data.materials.get(name)
    if m or not hexcol: return m
    h = hexcol.lstrip('#'); c = [int(h[i:i+2], 16) / 255 for i in (0, 2, 4)]
    c = [((v + 0.055) / 1.055) ** 2.4 if v > 0.04045 else v / 12.92 for v in c]
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    b.inputs['Base Color'].default_value = (*c, 1); b.inputs['Roughness'].default_value = rough
    return m

def bbox(o):
    pts = [o.matrix_world @ Vector(c) for c in o.bound_box]
    mn = Vector([min(p[i] for p in pts) for i in range(3)]); mx = Vector([max(p[i] for p in pts) for i in range(3)])
    return mn, mx, (mn + mx) / 2, mx - mn

def mat_of(o):
    return o.material_slots[0].material if o.material_slots else None

def new_obj(name, bm, m, smooth=True, parent=None):
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = smooth
    if m: me.materials.append(m)
    o = bpy.data.objects.new(name, me); scene.collection.objects.link(o)
    if parent:
        o.parent = parent; o.matrix_parent_inverse = parent.matrix_world.inverted()
    return o

def merge(objs, name, m_first=None):
    """把多個新建零件合併成一個物件（世界座標不變）。"""
    objs = [o for o in objs if o]
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs: o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    if len(objs) > 1: bpy.ops.object.join()
    o = bpy.context.view_layer.objects.active; o.name = name
    return o

def swap_mesh(target, src):
    """把 src 的網格（世界座標）換進 target：名稱、原點、父子、自訂屬性都保留。"""
    me = src.data.copy()
    me.transform(target.matrix_world.inverted() @ src.matrix_world)
    old = target.data; target.data = me; me.name = target.name
    bpy.data.objects.remove(src)
    if old.users == 0: bpy.data.meshes.remove(old)
    return target

def adopt(o, parent):
    """掛到父物件下，世界座標不變。"""
    o.parent = parent; o.matrix_parent_inverse = parent.matrix_world.inverted()
    return o

def delete(o):
    bpy.data.objects.remove(o)

def bm_box(size, center):
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1)
    bmesh.ops.scale(bm, vec=size, verts=bm.verts); bmesh.ops.translate(bm, vec=center, verts=bm.verts)
    return bm

def box(name, size, center, m, bev=None, seg=1, rz=0.0):
    bm = bm_box(size, (0, 0, 0))
    w = min(.03, min(size) * .2) if bev is None else bev
    if w > .003:
        bmesh.ops.bevel(bm, geom=bm.verts[:] + bm.edges[:], offset=w, offset_type='OFFSET', segments=seg,
                        profile=.5, affect='EDGES', clamp_overlap=True)
    bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(rz, 3, 'Z'))
    bmesh.ops.translate(bm, vec=center, verts=bm.verts)
    return new_obj(name, bm, m, seg > 1)

def lathe(name, prof, center, m, seg=24, sc=(1, 1, 1), axis='Z', smooth=True):
    """旋轉體：prof=[(r,z)…] 由下往上，r=0 封頂；axis 可為 Z、X、Y。"""
    bm = bmesh.new(); rings = []
    for r, z in prof:
        if r < 1e-6: rings.append([bm.verts.new((0, 0, z * sc[2]))]); continue
        rings.append([bm.verts.new((r * math.cos(i / seg * math.tau) * sc[0], r * math.sin(i / seg * math.tau) * sc[1], z * sc[2])) for i in range(seg)])
    for A, B in zip(rings, rings[1:]):
        for i in range(seg):
            j = (i + 1) % seg
            q = [A[i % len(A)], A[j % len(A)], B[j % len(B)], B[i % len(B)]]
            q = [v for k, v in enumerate(q) if v not in q[:k]]
            if len(q) >= 3: bm.faces.new(q)
    if axis == 'X': bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, 'Y'))
    if axis == 'Y': bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(-math.pi / 2, 3, 'X'))
    if axis == '-Z': bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi, 3, 'X'))
    bmesh.ops.translate(bm, vec=center, verts=bm.verts)
    return new_obj(name, bm, m, smooth)

def tube(name, pts, r, m, seg=8, cap=True, smooth=True):
    P = [Vector(p) for p in pts]; R = r if isinstance(r, (list, tuple)) else [r] * len(P)
    bm = bmesh.new(); rings = []
    for i, p in enumerate(P):
        t = (P[min(i + 1, len(P) - 1)] - P[max(i - 1, 0)]).normalized()
        ref = Vector((0, 0, 1)) if abs(t.z) < .9 else Vector((1, 0, 0))
        n = t.cross(ref).normalized(); b = t.cross(n)
        rings.append([bm.verts.new(p + (n * math.cos(a) + b * math.sin(a)) * R[i]) for a in (k / seg * math.tau for k in range(seg))])
    for A, B in zip(rings, rings[1:]):
        for k in range(seg):
            j = (k + 1) % seg; bm.faces.new((A[k], A[j], B[j], B[k]))
    if cap: bm.faces.new(rings[0][::-1]); bm.faces.new(rings[-1])
    return new_obj(name, bm, m, smooth)

def blob(name, r, center, m, sc=(1, 1, 1), rough=.25, sub=2, seed=0):
    bm = bmesh.new(); bmesh.ops.create_icosphere(bm, subdivisions=sub, radius=r)
    off = Vector((seed * 3.1, seed * 1.7, seed * 2.3))
    for v in bm.verts:
        v.co += v.co.normalized() * r * rough * noise.noise(v.co / r * 1.3 + off)
        v.co = Vector((v.co.x * sc[0], v.co.y * sc[1], v.co.z * sc[2])) + Vector(center)
    return new_obj(name, bm, m, True)

def leaf(name, center, size, yaw, pitch, m):
    """一片葉：壓扁的橢球，方便組成植栽。"""
    bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=8, v_segments=5, radius=1)
    bmesh.ops.scale(bm, vec=(size, size * .45, size * .08), verts=bm.verts)
    bmesh.ops.translate(bm, vec=(size * .9, 0, 0), verts=bm.verts)
    bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(yaw, 3, 'Z') @ Matrix.Rotation(-pitch, 3, 'Y'))
    bmesh.ops.translate(bm, vec=center, verts=bm.verts)
    return new_obj(name, bm, m, True)

def bevel_mesh(o, w, seg=1):
    """把既有的方塊網格倒角（原地修改）。"""
    bm = bmesh.new(); bm.from_mesh(o.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bmesh.ops.bevel(bm, geom=bm.verts[:] + bm.edges[:], offset=w, offset_type='OFFSET', segments=seg,
                    profile=.5, affect='EDGES', clamp_overlap=True)
    bm.to_mesh(o.data); bm.free()
    for p in o.data.polygons: p.use_smooth = seg > 1

def export():
    bpy.ops.object.select_all(action='SELECT')
    glb = os.path.join(OUT, NAME + '.glb')
    bpy.ops.export_scene.gltf(filepath=glb, export_format='GLB', use_selection=True, export_extras=True,
                              export_apply=True, export_lights=False, export_cameras=False)
    print('EXPORTED', glb, os.path.getsize(glb))

# ---------- 材質 ----------
WALL, BAND, ROOF, GLASS = material('校舍牆'), material('校舍飾帶'), material('屋頂'), material('窗玻璃')
FENCE, TRUNK, LEAF, LEAF2 = material('圍牆'), material('樹幹'), material('樹葉'), material('樹葉2')
OLDWALL, OLDROOF, PLANK, STAIN = material('舊牆'), material('舊屋頂'), material('木板'), material('舊牆污')
APT, CAFE, BG = material('公寓牆'), material('網咖牆'), material('背景樓')
POLE = material('旗桿')
METAL = material('鐵件', '#5b5f64', .5)
BGWIN = material('背景窗', '#3d434b', .4)
AC = material('冷氣外機', '#c9c7c0', .6)
RUST = material('鏽鐵', '#6e4a36', .8)

def islands(o, mat_name, remove=True):
    """某材質的每一塊獨立零件（世界座標 bbox）；remove=True 時從網格刪掉。"""
    idx = [i for i, s in enumerate(o.material_slots) if s.material and s.material.name == mat_name]
    if not idx: return []
    bm = bmesh.new(); bm.from_mesh(o.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)   # 匯入的 GLB 每個面頂點分開，先接回來才分得出零件
    bm.faces.ensure_lookup_table()
    todo = {f for f in bm.faces if f.material_index in idx}; out = []; dead = []
    while todo:
        f0 = todo.pop(); stack = [f0]; grp = {f0}
        while stack:
            f = stack.pop()
            for v in f.verts:
                for g in v.link_faces:
                    if g in todo: todo.remove(g); grp.add(g); stack.append(g)
        pts = [o.matrix_world @ v.co for f in grp for v in f.verts]
        mn = Vector([min(p[i] for p in pts) for i in range(3)]); mx = Vector([max(p[i] for p in pts) for i in range(3)])
        out.append((mn, mx, (mn + mx) / 2, mx - mn)); dead += list(grp)
    if remove:
        bmesh.ops.delete(bm, geom=dead, context='FACES')
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
        bm.to_mesh(o.data)
    bm.free()
    return sorted(out, key=lambda t: (round(t[2].z, 1), t[2].x))

def join_into(target, parts):
    parts = [p for p in parts if p]
    if not parts: return target
    bpy.ops.object.select_all(action='DESELECT')
    for p in parts: p.select_set(True)
    target.select_set(True); bpy.context.view_layer.objects.active = target
    bpy.ops.object.join()
    return target

# ---------- 校舍：窗台、窗楣、壁柱；屋頂女兒牆、水塔、欄杆 ----------
main = OB['學校主樓']; mn, mx, c, s = bbox(main)
body = max(islands(main, '校舍牆', remove=False), key=lambda t: t[3].x * t[3].y)   # 主體量體（外框含鐘塔，不能拿來當屋頂高）
mx = Vector((mx.x, mx.y, body[1].z)); s = mx - mn
wins = islands(OB['學校_窗'], '窗玻璃', remove=False)
front = min(w[0].y for w in wins) - .02               # 正面（-Y）牆面
parts = []
cls = bbox(OB['教室'])                                  # 一樓教室正面開放、角色會走進去：這一段一樓不加任何東西
OPEN = (cls[0].x - .3, cls[1].x + .3, mn.z + 3.0)
blocked = lambda x0, x1, z0: z0 < OPEN[2] and x1 > OPEN[0] and x0 < OPEN[1]
for (wmn, wmx, wc, ws) in wins:
    if blocked(wmn.x - .15, wmx.x + .15, wmn.z - .2): continue
    parts.append(box('窗台', (ws.x + .3, .28, .1), (wc.x, front - .1, wmn.z - .08), BAND, .02))
    parts.append(box('窗楣', (ws.x + .2, .18, .12), (wc.x, front - .07, wmx.z + .12), WALL, .02))
cols = sorted({round(w[2].x, 1) for w in wins})
gaps = [(a + b) / 2 for a, b in zip(cols, cols[1:])]
for x in [mn.x + .35] + gaps + [mx.x - .35]:
    z0 = OPEN[2] if blocked(x - .2, x + .2, mn.z) else mn.z
    parts.append(box('壁柱', (.4, .25, s.z - 1.2 - (z0 - mn.z)), (x, front - .1, z0 + (s.z - 1.2 - (z0 - mn.z)) / 2), WALL, .03))
for x0, x1 in ((mn.x - .05, OPEN[0]), (OPEN[1], mx.x + .05)):   # 勒腳分兩段，讓出教室
    parts.append(box('勒腳', (x1 - x0, .2, 1.2), ((x0 + x1) / 2, front - .08, mn.z + .6), BAND, .02))
roof = mx.z
tank = Vector((c.x + s.x * .3, c.y + 1, roof))
parts.append(box('水塔台', (2.2, 2.2, .4), tank + Vector((0, 0, .2)), BAND, .03))
parts.append(lathe('水塔', [(0, 0), (.85, 0), (.85, 1.3), (.6, 1.6), (0, 1.65)], tank + Vector((0, 0, .4)), APT, 24))
for k in range(14):                                   # 屋頂欄杆
    x = mn.x + 1 + k * (s.x - 2) / 13
    parts.append(tube('欄杆柱', [(x, front + .25, roof), (x, front + .25, roof + .9)], .03, METAL, 5))
parts.append(tube('欄杆扶手', [(mn.x + 1, front + .25, roof + .9), (mx.x - 1, front + .25, roof + .9)], .035, METAL, 6))
join_into(main, parts)

# ---------- 圍牆：牆柱與壓頂 ----------
fw = OB['學校圍牆']; parts = []
for (wmn, wmx, wc, ws) in islands(fw, '圍牆', remove=False):
    L = max(ws.x, ws.y); along_x = ws.x >= ws.y; thick = min(ws.x, ws.y)
    if L < 1: continue
    n = max(1, round(L / 3))
    for k in range(n + 1):
        t = -L / 2 + .2 + k * (L - .4) / n
        p = Vector((wc.x + t, wc.y, 0)) if along_x else Vector((wc.x, wc.y + t, 0))
        parts.append(box('牆柱', (.42, .42, ws.z + .25), p + Vector((0, 0, (ws.z + .25) / 2)), FENCE, .03))
        parts.append(box('柱帽', (.52, .52, .1), p + Vector((0, 0, ws.z + .3)), BAND, .02))
    parts.append(box('壓頂', (ws.x + (.1 if along_x else .12), ws.y + (.12 if along_x else .1), .08), Vector((wc.x, wc.y, wmx.z + .04)), BAND, .02))
join_into(fw, parts)

# ---------- 學校的樹：主幹分枝＋葉叢 ----------
tr = OB['學校_樹']
leaves = islands(tr, '樹葉') + islands(tr, '樹葉2')
trunks = islands(tr, '樹幹')
parts = []
for i, (tmn, tmx, tc, ts) in enumerate(trunks):
    rnd = random.Random(i)
    near = [l for l in leaves if (Vector((l[2].x, l[2].y, 0)) - Vector((tc.x, tc.y, 0))).length < 2.5]
    if not near: continue
    cmn = Vector([min(l[0][k] for l in near) for k in range(3)]); cmx = Vector([max(l[1][k] for l in near) for k in range(3)])
    cc, cs = (cmn + cmx) / 2, cmx - cmn
    base = Vector((tc.x, tc.y, 0)); top = Vector((cc.x, cc.y, cc.z - cs.z * .1))
    parts.append(tube('幹', [base, base.lerp(top, .5) + Vector((.05, -.03, 0)), top], [.14, .1, .07], TRUNK, 8))
    for k in range(4):
        a = k / 4 * math.tau + rnd.uniform(-.4, .4); d = Vector((math.cos(a), math.sin(a), 0))
        st = base.lerp(top, rnd.uniform(.55, .85)); tip = top + d * cs.x * .3 + Vector((0, 0, rnd.uniform(0, .4)))
        parts.append(tube('枝', [st, tip], [.05, .02], TRUNK, 5))
    for k in range(9):
        a = rnd.uniform(0, math.tau); rr = rnd.uniform(0, .3) * cs.x
        p = Vector((cc.x + math.cos(a) * rr, cc.y + math.sin(a) * rr, cc.z + rnd.uniform(-.2, .3) * cs.z))
        parts.append(blob('葉', cs.x * rnd.uniform(.2, .28), p, LEAF if k % 3 else LEAF2, (1, 1, .85), .3, 2, i * 20 + k))
join_into(tr, parts)

# ---------- 枯樹：分叉的枯枝 ----------
dt = OB['枯樹']; mn, mx, c, s = bbox(dt)
def branch(p, d, L, r, depth, rnd, out):
    q = p + d * L
    out.append(tube('枝', [p, p.lerp(q, .5) + Vector((rnd.uniform(-.1, .1), rnd.uniform(-.1, .1), 0)), q], [r, r * .8, r * .55], TRUNK, 6))
    if depth == 0: return
    for k in range(2 if depth > 1 else 3):
        nd = (d + Vector((rnd.uniform(-.8, .8), rnd.uniform(-.5, .5), rnd.uniform(-.1, .5)))).normalized()
        branch(q, nd, L * rnd.uniform(.55, .7), r * .6, depth - 1, rnd, out)
out = []; rnd = random.Random(9)
branch(Vector((c.x, c.y, 0)), Vector((.08, 0, 1)).normalized(), s.z * .45, .16, 3, rnd, out)
swap_mesh(dt, merge(out, 'tmp'))

# ---------- 破舊房屋：屋脊、封簷板、煙囪、雨水管、歪掉的木板 ----------
hs = OB['破舊房屋']; mn, mx, c, s = bbox(hs); parts = []
walls = islands(hs, '舊牆', remove=False)
wmn = Vector([min(w[0][k] for w in walls) for k in range(3)]); wmx = Vector([max(w[1][k] for w in walls) for k in range(3)])
eave = wmx.z
parts.append(box('屋脊', (s.x + .1, .3, .25), (c.x, c.y, mx.z - .05), OLDROOF, .05))
for sy in (-1, 1):
    parts.append(box('封簷板', (s.x, .08, .3), (c.x, c.y + sy * (s.y / 2 - .05), eave - .05), PLANK, .02))
    parts.append(tube('簷溝', [(mn.x + .1, c.y + sy * (s.y / 2), eave - .2), (mx.x - .1, c.y + sy * (s.y / 2), eave - .25)], .08, RUST, 6))
parts.append(tube('落水管', [(mx.x - .2, mn.y + .05, eave - .25), (mx.x - .2, mn.y + .05, .3), (mx.x - .2, mn.y - .2, .05)], .06, RUST, 6))
ch = Vector((c.x - s.x * .25, c.y + s.y * .15, 0))
parts.append(box('煙囪', (.7, .7, 2.4), ch + Vector((0, 0, mx.z - 1.0)), OLDWALL, .03))
parts.append(box('煙囪帽', (.9, .9, .12), ch + Vector((0, 0, mx.z + .25)), OLDROOF, .02))
parts.append(box('牆腳', (wmx.x - wmn.x + .1, wmx.y - wmn.y + .1, .5), Vector(((wmn.x + wmx.x) / 2, (wmn.y + wmx.y) / 2, .25)), STAIN, .02))
for k, (dx, dz, a) in enumerate(((-2.4, 4.2, .25), (-1.7, 4.0, -.2), (2.6, 1.9, .12))):   # 二樓窗上釘的歪木板
    parts.append(box('釘板', (1.3, .06, .16), (c.x + dx, wmn.y - .05, dz), PLANK, .01, rz=0))
    parts[-1].rotation_euler.y = a
join_into(hs, parts)

# ---------- 繭居公寓：樓層線、冷氣外機、雨水管、側窗、屋頂水塔 ----------
ap = OB['繭居公寓']; mn, mx, c, s = bbox(ap); parts = []
for k in range(1, 4):
    z = k * 3.25
    parts.append(box('樓層線', (s.x + .2, s.y + .2, .18), (c.x, c.y, z), BAND, .03))
for (x, z) in ((mn.x + .9, 4.2), (mn.x + .9, 7.5), (mx.x - .6, 10.7), (mn.x + .9, 10.7)):   # 正面冷氣外機（避開窗光那扇窗）
    parts.append(box('外機', (.85, .35, .6), (x, mn.y - .2, z), AC, .04))
    parts.append(lathe('風扇', [(0, 0), (.2, 0), (.2, .02), (0, .02)], (x, mn.y - .38, z), METAL, 16, axis='Y'))
    parts.append(box('支架', (.85, .4, .05), (x, mn.y - .2, z - .33), METAL, 0))
parts.append(tube('落水管', [(mx.x + .1, mn.y + .1, mx.z), (mx.x + .1, mn.y + .1, .2)], .07, METAL, 6))
for side in (-1, 1):                                   # 兩側的窗
    x = c.x + side * (s.x / 2 + .02)
    for z in (1.8, 5.0, 8.3, 11.5):
        for y in (c.y - 1.4, c.y + 1.4):
            parts.append(box('側窗', (.06, 1.0, 1.2), (x, y, z), BGWIN, 0))
            parts.append(box('側窗台', (.2, 1.2, .08), (x + side * .06, y, z - .65), BAND, .01))
parts.append(lathe('水塔', [(0, 0), (.7, 0), (.7, 1.1), (.5, 1.4), (0, 1.45)], (c.x - 1.2, c.y + 1, mx.z), APT, 20))
for k in range(9):
    x = mn.x + .3 + k * (s.x - .6) / 8
    parts.append(tube('欄杆', [(x, mn.y + .2, mx.z), (x, mn.y + .2, mx.z + .9)], .025, METAL, 5))
parts.append(tube('扶手', [(mn.x + .3, mn.y + .2, mx.z + .9), (mx.x - .3, mn.y + .2, mx.z + .9)], .03, METAL, 5))
join_into(ap, parts)

# ---------- 網咖：雨遮、側邊冷氣、屋頂招牌架 ----------
cf = OB['網咖']; mn, mx, c, s = bbox(cf); parts = []
parts.append(box('雨遮', (s.x - .6, 1.4, .12), (c.x, mn.y - .7, 2.95), CAFE, .03))
parts[-1].rotation_euler.x = -.12
for x in (mn.x + .5, mx.x - .5):
    parts.append(tube('拉桿', [(x, mn.y - 1.35, 2.95), (x, mn.y, 4.0)], .03, METAL, 5))
parts.append(box('樓層線', (s.x + .2, s.y + .2, .2), (c.x, c.y, 3.6), BAND, .03))
parts.append(box('女兒牆', (s.x + .1, s.y + .1, .4), (c.x, c.y, mx.z + .2), CAFE, .03))
for y in (c.y - 2, c.y + 1.5):
    parts.append(box('外機', (.35, .85, .6), (mx.x + .2, y, 4.6), AC, .04))
for x in (c.x - 3, c.x + 2.5):
    parts.append(box('屋頂外機', (1.1, .8, .7), (x, c.y + 1.5, mx.z + .75), AC, .04))
join_into(cf, parts)

# ---------- 背景大樓：朝向學校的窗格與屋頂設備 ----------
bg = OB['城市背景']; parts = []
for i, (bmn, bmx, bc, bs) in enumerate(islands(bg, '背景樓', remove=False)):
    if bs.z < 3 or bs.x < 2: continue
    nx = max(1, int(bs.x / 1.6)); nz = max(1, int((bs.z - 1) / 2.2))
    for a in range(nx):
        for b in range(nz):
            x = bmn.x + (a + .5) * bs.x / nx; z = bmn.z + 1 + (b + .5) * (bs.z - 1.2) / nz
            parts.append(box('窗', (bs.x / nx * .55, .08, 1.1), (x, bmn.y - .03, z), BGWIN, 0))
    rnd = random.Random(i)
    if rnd.random() < .7:
        parts.append(box('屋頂', (min(2, bs.x * .3), min(2, bs.y * .3), 1.0), (bc.x + rnd.uniform(-.2, .2) * bs.x, bc.y, bmx.z + .5), BG, .03))
join_into(bg, parts)

export()
