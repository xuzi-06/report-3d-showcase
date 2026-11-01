# 智慧住宅：讀入原始模型 src/智慧住宅.glb，提高精度後匯出 智慧住宅.glb
# 執行：blender --background --factory-startup --python 智慧住宅.py
# 前端靠物件名稱定位（DEVICES、flows、cutaway），所以只換網格、不改名稱、位置與階層。
import bpy, bmesh, math, random, os
from mathutils import Vector, Matrix, noise

OUT = os.path.dirname(os.path.abspath(__file__))
NAME = '智慧住宅'
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
LEAF, LEAF_D, TRUNK = material('植物｜葉綠'), material('植物｜深綠'), material('戶外｜樹幹')
POT, OAK, WALNUT = material('陶土｜花盆'), material('木作｜淺橡木'), material('木作｜胡桃木')
BLACK, WHITE_DEV, WARM = material('金屬｜炭黑框'), material('設備｜霧白外殼'), material('燈光｜暖白')
SOIL = material('盆土', '#5a4636', .95)
FLOWER = [material('花｜珊瑚', '#e9876f', .7), material('花｜奶黃', '#efd27a', .7), material('花｜淡紫', '#b9a3d6', .7)]
GRASS = material('戶外｜草叢', '#8fb67a', .9)

# ---------- 庭院大樹：彎曲主幹分枝，樹冠是一團團不規則葉叢 ----------
yard = OB['庭院｜戶外景觀']
for tag, seed in (('大樹A', 1), ('大樹B', 2), ('小樹C', 3)):
    crowns = [o for o in OB if o.name.startswith('庭院｜%s｜樹冠' % tag)]
    trunk = OB['庭院｜%s｜樹幹' % tag]
    tmn, tmx, tc, _ = bbox(trunk)
    pts = [bbox(o) for o in crowns]
    cmn = Vector([min(p[0][i] for p in pts) for i in range(3)]); cmx = Vector([max(p[1][i] for p in pts) for i in range(3)])
    cc, cs = (cmn + cmx) / 2, cmx - cmn
    rnd = random.Random(seed); base = Vector((tc.x, tc.y, 0)); H = cc.z - cs.z * .15
    tr = [base, base + Vector((.05, .03, H * .4)), base + Vector((-.08, .05, H * .75)), Vector((cc.x, cc.y, H))]
    parts = [tube('樹幹', tr, [.2, .15, .12, .08], TRUNK, 10)]
    for i in range(5):                                  # 主枝
        a = i / 5 * math.tau + rnd.uniform(-.3, .3); d = Vector((math.cos(a), math.sin(a), 0))
        st = tr[1].lerp(tr[3], rnd.uniform(.45, .9)); tip = Vector((cc.x, cc.y, 0)) + d * cs.x * .32 + Vector((0, 0, cc.z + rnd.uniform(-.3, .4)))
        parts.append(tube('樹枝', [st, st.lerp(tip, .5) + Vector((0, 0, .3)), tip], [.07, .045, .02], TRUNK, 6))
    canopy = []
    for i in range(16):                                 # 葉叢：大小不一、外圈較低
        a = rnd.uniform(0, math.tau); rr = rnd.uniform(0, .38) * cs.x
        c = Vector((cc.x + math.cos(a) * rr, cc.y + math.sin(a) * rr * cs.y / cs.x, cc.z + rnd.uniform(-.25, .32) * cs.z - rr * .25))
        canopy.append(blob('葉叢', cs.x * rnd.uniform(.16, .24), c, LEAF_D if i % 3 else LEAF, (1, 1, .8), .32, 2, seed * 20 + i))
    swap_mesh(trunk, merge(parts, 'tmp'))
    keep = crowns[0]
    swap_mesh(keep, merge(canopy, 'tmp')); keep.name = '庭院｜%s｜樹冠' % tag
    for o in crowns[1:]: delete(o)

# ---------- 灌木：幾團小葉叢加幾朵花 ----------
for o in [o for o in OB if o.name.startswith('庭院｜灌木')]:
    mn, mx, c, s = bbox(o); rnd = random.Random(hash(o.name) % 999)
    parts = []
    for i in range(6):
        p = c + Vector((rnd.uniform(-.25, .25) * s.x, rnd.uniform(-.25, .25) * s.y, rnd.uniform(-.2, .15) * s.z))
        parts.append(blob('灌', s.x * rnd.uniform(.25, .34), p, mat_of(o), (1, 1, .8), .3, 2, rnd.randint(0, 99)))
    swap_mesh(o, merge(parts, 'tmp'))
for k, (x, y) in enumerate([(-3.4, -4.9), (-1.9, -4.8), (4.7, -4.6), (5.6, -2.0), (-5.6, 2.4), (-0.4, -4.9)]):   # 灌木邊的花
    rnd = random.Random(40 + k); fl = []
    for i in range(7):
        p = Vector((x + rnd.uniform(-.35, .35), y + rnd.uniform(-.2, .2), .25 + rnd.uniform(0, .2)))
        fl.append(tube('莖', [Vector((p.x, p.y, 0)), p], .01, LEAF, 4, False))
        fl.append(blob('花', .06, p, FLOWER[(k + i) % 3], (1, 1, .7), .2, 1, k * 10 + i))
    adopt(merge(fl, '庭院｜花叢%d' % k), yard)
# 草叢：沿房子周邊零星分布
gr = []
rnd = random.Random(77)
for i in range(60):
    a = rnd.uniform(0, math.tau); d = rnd.uniform(6.5, 11)
    p = Vector((math.cos(a) * d * 1.1, -2 + math.sin(a) * d * .8, 0))
    if abs(p.x - 2.5) < 1.4 and p.y < -4: continue    # 避開石板步道
    for j in range(4):
        q = p + Vector((rnd.uniform(-.1, .1), rnd.uniform(-.1, .1), 0))
        gr.append(tube('草', [q, q + Vector((rnd.uniform(-.08, .08), rnd.uniform(-.08, .08), rnd.uniform(.18, .32)))], [.025, .004], GRASS, 3, False))
adopt(merge(gr, '庭院｜草叢'), yard)

# ---------- 室內植栽：枝條＋一片片葉子 ----------
def foliage(o, n, big):
    mn, mx, c, s = bbox(o); rnd = random.Random(hash(o.name) % 997)
    base = Vector((c.x, c.y, mn.z - s.z * .2)); parts = []
    for i in range(n):
        a = rnd.uniform(0, math.tau); up = rnd.uniform(.2, 1)
        tip = Vector((c.x + math.cos(a) * s.x * .35 * rnd.uniform(.3, 1), c.y + math.sin(a) * s.y * .35 * rnd.uniform(.3, 1), mn.z + up * s.z))
        if big and i % 3 == 0: parts.append(tube('枝', [base, tip], [.012, .006], TRUNK, 4, False))
        parts.append(leaf('葉', tip, s.x * rnd.uniform(.08, .13), a, rnd.uniform(-.3, .6), mat_of(o)))
    swap_mesh(o, merge(parts, 'tmp'))
for nm in [n.name for n in OB if ('葉叢' in n.name or '植栽' in n.name or '小盆栽' in n.name) and '枝幹' not in n.name and n.type == 'MESH' and not n.name.startswith('庭院')]:
    o = OB[nm]
    foliage(o, 34 if '葉叢' in nm else 16, '葉叢' in nm)

# ---------- 花器、燈罩：改成旋轉體 ----------
for o in [o for o in OB if o.type == 'MESH' and ('花器' in o.name or '盆栽盆' in o.name)]:
    mn, mx, c, s = bbox(o); R, H = s.x / 2, s.z
    pot = lathe('盆', [(0, 0), (R * .72, 0), (R * .74, .04 * H), (R * .97, .88 * H), (R, .9 * H), (R * 1.04, H), (R * .9, H), (R * .88, .93 * H), (0, .93 * H)],
                (c.x, c.y, mn.z), mat_of(o), 28)
    soil = lathe('土', [(0, 0), (R * .88, 0), (0, .001)], (c.x, c.y, mn.z + .9 * H), SOIL, 20)
    swap_mesh(o, merge([pot, soil], 'tmp'))
for o in [o for o in OB if o.type == 'MESH' and o.name.startswith('一樓｜吊燈燈罩')]:
    mn, mx, c, s = bbox(o); R, H = s.x / 2, s.z
    swap_mesh(o, lathe('罩', [(R, 0), (R * .98, H * .12), (R * .7, H * .55), (R * .3, H * .9), (R * .12, H), (0, H)], (c.x, c.y, mn.z), mat_of(o), 32))
for nm in ('二樓｜立燈燈罩', '三樓｜邊几檯燈'):
    o = OB[nm]; mn, mx, c, s = bbox(o); R, H = s.x / 2, s.z
    swap_mesh(o, lathe('罩', [(0, 0), (R, 0), (R * .72, H), (0, H)], (c.x, c.y, mn.z), mat_of(o), 32))

# ---------- 布面家具：軟墊感的圓角 ----------
for o in [o for o in OB if o.type == 'MESH' and mat_of(o) and mat_of(o).name.startswith('布料') and len(o.data.vertices) <= 96]:
    mn, mx, c, s = bbox(o)
    if min(s) > .05: swap_mesh(o, box('墊', tuple(s), c, mat_of(o), min(.06, min(s) * .3), 3))
# ---------- 方塊類（牆、櫃、設備）：倒一點角 ----------
for o in [o for o in OB if o.type == 'MESH' and len(o.data.vertices) == 24]:
    m = mat_of(o); s = bbox(o)[3]
    if not m or any(k in m.name for k in ('玻璃', '顯示', '地板', '礫石')) or min(s) < .05: continue
    bevel_mesh(o, min(.025, min(s) * .15))

# ---------- 細部：踢腳板、窗台、信箱 ----------
house = OB['住宅｜建築外殼']
det = []
for z in (.32, 3.52, 6.72):                            # 三層樓的踢腳板（後牆、兩側牆內側）
    det.append(box('踢腳板', (8.5, .03, .1), (0, 3.27, z + .05), WALNUT, .005))
    for x in (-4.27, 4.27):
        det.append(box('踢腳板', (.03, 6.5, .1), (x, 0, z + .05), WALNUT, .005))
adopt(merge(det, '住宅｜踢腳板'), house)
mb = [box('信箱', (.35, .25, .45), (4.2, -6.1, .95), BLACK, .02),
      tube('信箱柱', [(4.2, -6.1, 0), (4.2, -6.1, .74)], .04, BLACK, 8),
      box('信箱口', (.25, .02, .04), (4.2, -6.23, 1.08), WHITE_DEV, .005)]
adopt(merge(mb, '庭院｜信箱'), yard)

export()
