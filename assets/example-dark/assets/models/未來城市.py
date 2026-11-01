# 未來城市：讀入原始模型 src/未來城市.glb，提高精度後匯出 未來城市.glb
# 執行：blender --background --factory-startup --python 未來城市.py
# 前端靠物件名稱定位；會動的物件（自駕車_、無人機_、風機葉片、營運中心_全息環）原點與方向不可變。
import bpy, bmesh, math, random, os
from mathutils import Vector, Matrix, noise

OUT = os.path.dirname(os.path.abspath(__file__))
NAME = '未來城市'
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
GLASS, WHITE, METAL = material('深色玻璃'), material('白色結構'), material('金屬')
NEON_C, NEON_M, NEON_A = material('霓虹青'), material('霓虹洋紅'), material('霓虹琥珀')
PLANT, CARBODY, CABINET = material('植栽'), material('車身'), material('儲能櫃')
PLANT2 = material('植栽｜淺', '#5f8f4e', .85)
TIRE = material('輪胎', '#151619', .7)

def islands(o, mat_name):
    """回傳物件中某材質的每一塊獨立零件（世界座標 bbox），並把它們從網格刪掉。"""
    idx = [i for i, s in enumerate(o.material_slots) if s.material and s.material.name == mat_name]
    if not idx: return []
    bm = bmesh.new(); bm.from_mesh(o.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)   # 匯入的 GLB 每個面頂點分開，先接回來才分得出零件
    bm.faces.ensure_lookup_table()
    todo = {f for f in bm.faces if f.material_index in idx}; out = []
    while todo:
        f0 = todo.pop(); stack = [f0]; grp = {f0}
        while stack:
            f = stack.pop()
            for e in f.edges:
                for g in e.link_faces:
                    if g in todo: todo.remove(g); grp.add(g); stack.append(g)
            for v in f.verts:
                for g in v.link_faces:
                    if g in todo: todo.remove(g); grp.add(g); stack.append(g)
        pts = [o.matrix_world @ v.co for f in grp for v in f.verts]
        mn = Vector([min(p[i] for p in pts) for i in range(3)]); mx = Vector([max(p[i] for p in pts) for i in range(3)])
        out.append((mn, mx, (mn + mx) / 2, mx - mn));
        bmesh.ops.delete(bm, geom=list(grp), context='FACES')
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    bm.to_mesh(o.data); bm.free()
    return out

def join_into(target, parts):
    """把新零件併入既有物件（保留 target 的名稱與原點）。"""
    parts = [p for p in parts if p]
    for p in parts:
        for s in p.material_slots:
            if s.material and s.material.name not in [t.material.name for t in target.material_slots if t.material]:
                target.data.materials.append(s.material)
    bpy.ops.object.select_all(action='DESELECT')
    for p in parts: p.select_set(True)
    target.select_set(True); bpy.context.view_layer.objects.active = target
    bpy.ops.object.join()
    return target

# ---------- 一般大樓：直向金屬鰭條、屋頂設備、航空警示燈 ----------
for o in sorted([o for o in OB if o.name.startswith('城市大樓_')], key=lambda o: o.name):
    mn, mx, c, s = bbox(o); rnd = random.Random(o.name)
    parts = []
    H = s.z - .6
    for axis in (0, 1):                                # 四面的直向鰭條
        L = s[axis]; n = max(3, int(L / 1.25))
        for side in (-1, 1):
            for k in range(1, n):
                t = -L / 2 + k * L / n
                if axis == 0: p, sz = Vector((c.x + t, c.y + side * (s.y / 2 + .04), mn.z + .4 + H / 2)), (.1, .12, H)
                else:         p, sz = Vector((c.x + side * (s.x / 2 + .04), c.y + t, mn.z + .4 + H / 2)), (.12, .1, H)
                parts.append(box('鰭', sz, p, METAL, 0))
    roof = mx.z
    parts.append(box('女兒牆', (s.x - .2, s.y - .2, .35), (c.x, c.y, roof + .17), WHITE, .03))
    parts.append(box('屋頂板', (s.x - .6, s.y - .6, .1), (c.x, c.y, roof + .2), METAL, 0))
    for k in range(rnd.randint(2, 4)):                 # 空調機組
        p = Vector((c.x + rnd.uniform(-.3, .3) * s.x, c.y + rnd.uniform(-.3, .3) * s.y, roof + .25))
        parts.append(box('空調', (rnd.uniform(.8, 1.4), rnd.uniform(.6, 1.0), .6), p + Vector((0, 0, .3)), WHITE, .04))
        parts.append(lathe('風扇', [(0, 0), (.25, 0), (.25, .06), (0, .06)], p + Vector((0, 0, .6)), METAL, 16))
    if rnd.random() < .6:                              # 水塔
        p = Vector((c.x - s.x * .25, c.y + s.y * .2, roof + .25))
        parts.append(lathe('水塔', [(0, 0), (.6, 0), (.6, 1.1), (.4, 1.35), (0, 1.4)], p + Vector((0, 0, .5)), WHITE, 20))
        for a in range(4):
            parts.append(tube('塔腳', [p + Vector((math.cos(a * 1.57) * .45, math.sin(a * 1.57) * .45, 0)), p + Vector((math.cos(a * 1.57) * .45, math.sin(a * 1.57) * .45, .55))], .05, METAL, 5))
    if s.z > 15:                                       # 高樓的天線與警示燈
        p = Vector((c.x + s.x * .25, c.y - s.y * .25, roof + .25))
        h = rnd.uniform(3, 5)
        parts.append(tube('天線', [p, p + Vector((0, 0, h))], [.08, .03], METAL, 6))
        parts.append(blob('警示燈', .12, p + Vector((0, 0, h + .05)), NEON_M, (1, 1, 1), 0, 1))
    join_into(o, parts)

# ---------- 垂直森林：方塊植栽換成垂掛的樹叢 ----------
for nm in ('垂直森林大樓', '垂直森林大樓_副棟'):
    o = OB[nm]; isl = islands(o, '植栽'); rnd = random.Random(nm); parts = []
    for i, (mn, mx, c, s) in enumerate(isl):
        r = max(s.x, s.y) * .45
        for k in range(3):
            p = c + Vector((rnd.uniform(-.35, .35) * s.x, rnd.uniform(-.35, .35) * s.y, rnd.uniform(0, .3) * s.z))
            parts.append(blob('葉', r * rnd.uniform(.5, .75), p, PLANT if (i + k) % 3 else PLANT2, (1, 1, .85), .35, 2, i * 3 + k))
        if i % 2 == 0:                                 # 一些枝葉垂到陽台外
            p = c + Vector((0, 0, -s.z * .3))
            parts.append(blob('垂', r * .45, p + Vector((0, 0, -r * .5)), PLANT2, (.8, .8, 1.4), .3, 1, 500 + i))
    join_into(o, parts)

# ---------- 儲能站：櫃體散熱鰭片與門縫 ----------
o = OB['儲能站']; isl = islands(o, '儲能櫃'); parts = []
for i, (mn, mx, c, s) in enumerate(isl):
    parts.append(box('櫃', tuple(s), c, CABINET, .05, 2))
    long_x = s.x >= s.y
    L = s.x if long_x else s.y; n = int(L / .45)
    for side in (-1, 1):
        for k in range(1, n):
            t = -L / 2 + k * L / n
            if long_x: p, sz = Vector((c.x + t, c.y + side * (s.y / 2 + .02), c.z + s.z * .1)), (.05, .05, s.z * .55)
            else:      p, sz = Vector((c.x + side * (s.x / 2 + .02), c.y + t, c.z + s.z * .1)), (.05, .05, s.z * .55)
            parts.append(box('鰭', sz, p, METAL, 0))
        for k in (1, 2):                               # 門縫
            t = -L / 2 + k * L / 3
            if long_x: p, sz = Vector((c.x + t, c.y + side * (s.y / 2 + .01), c.z)), (.03, .02, s.z * .85)
            else:      p, sz = Vector((c.x + side * (s.x / 2 + .01), c.y + t, c.z)), (.02, .03, s.z * .85)
            parts.append(box('縫', sz, p, METAL, 0))
    parts.append(box('頂', (s.x - .1, s.y - .1, .08), c + Vector((0, 0, s.z / 2 + .04)), WHITE, .02))
join_into(o, parts)

# ---------- 自駕車：流線車身、車窗、車輪與霓虹燈條 ----------
def car(c, s):
    long_x = s.x >= s.y; L, W = (s.x, s.y) if long_x else (s.y, s.x); rz = 0 if long_x else math.pi / 2
    ps = []
    def P(x, y, z): v = Matrix.Rotation(rz, 3, 'Z') @ Vector((x, y, z)); return Vector((c.x, c.y, 0)) + v
    body = box('車身', (L, W * .96, .55), (0, 0, 0), CARBODY, .2, 4)
    body.location = P(0, 0, .55); body.rotation_euler.z = rz; ps.append(body)
    cab = box('車艙', (L * .55, W * .84, .45), (0, 0, 0), GLASS, .18, 4)
    cab.location = P(-L * .05, 0, 1.0); cab.rotation_euler.z = rz; ps.append(cab)
    for sx in (-1, 1):
        for sy in (-1, 1):
            w = lathe('輪', [(0, -.13), (.33, -.13), (.36, -.08), (.36, .08), (.33, .13), (0, .13)], (0, 0, 0), TIRE, 20, axis='Y')
            w.location = P(sx * L * .32, sy * W * .46, .36); w.rotation_euler.z = rz; ps.append(w)
            hub = lathe('轂', [(0, -.01), (.2, -.01), (.2, .01), (0, .01)], (0, 0, 0), NEON_C, 16, axis='Y')
            hub.location = P(sx * L * .32, sy * (W * .46 + .14), .36); hub.rotation_euler.z = rz; ps.append(hub)
    for sy in (-1, 1):                                 # 側邊霓虹燈條
        st = box('燈條', (L * .8, .03, .04), (0, 0, 0), NEON_C, 0)
        st.location = P(0, sy * W * .485, .5); st.rotation_euler.z = rz; ps.append(st)
    fr = box('前燈', (.04, W * .7, .06), (0, 0, 0), NEON_C, 0); fr.location = P(L / 2 - .02, 0, .65); fr.rotation_euler.z = rz; ps.append(fr)
    lid = box('光達', (.3, .3, .12), (0, 0, 0), GLASS, .05, 2); lid.location = P(-L * .05, 0, 1.28); lid.rotation_euler.z = rz; ps.append(lid)
    for p in ps:
        bpy.ops.object.select_all(action='DESELECT'); p.select_set(True); bpy.context.view_layer.objects.active = p
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    return merge(ps, 'tmp')
for o in [o for o in OB if o.name.startswith('自駕車_')]:
    mn, mx, c, s = bbox(o)
    swap_mesh(o, car(c, s))

# ---------- 風力發電機：漸縮塔身、機艙；葉片為扭轉的翼型 ----------
tw = OB['風力發電機']; bl = OB['風機葉片']
hub = bl.matrix_world.translation.copy()
tmn, tmx, tc, ts = bbox(tw)
axis_y = 1 if hub.y > tc.y else -1                    # 葉片在機艙哪一側
top = tmx.z - 1.2
tower = lathe('塔', [(0, 0), (1.0, 0), (.95, .3), (.7, top * .5), (.45, top), (0, top)], (tc.x, tc.y, 0), WHITE, 32)
nac = lathe('機艙', [(0, 0), (.55, 0), (.75, .5), (.75, 2.6), (.6, 3.2), (0, 3.3)], (0, 0, 0), WHITE, 24, axis='Y')
for v in nac.data.vertices: v.co.y *= -axis_y
nac.location = (tc.x, hub.y - axis_y * .2, hub.z)
bpy.ops.object.select_all(action='DESELECT'); nac.select_set(True); bpy.context.view_layer.objects.active = nac
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
swap_mesh(tw, merge([tower, nac], 'tmp'))
bmn, bmx, bc, bs = bbox(bl)
R = max((Vector(p) - hub).length for p in (bmn, bmx)) * .62
blades = []
for k in range(3):
    a0 = k * math.tau / 3 + math.pi / 2
    bm = bmesh.new(); rings = []
    for i in range(11):                                # 翼型斷面沿葉長收窄並扭轉
        t = i / 10; r = .9 + t * (R - .9)
        chord = (1.1 - .75 * t) if t > .15 else .6 + t * 3.3
        twist = .5 * (1 - t); th = .16 * (1 - .7 * t)
        ring = []
        for j in range(10):
            u = j / 10 * math.tau
            x = math.cos(u) * chord / 2; yv = math.sin(u) * th / 2 * (1.4 if math.cos(u) > 0 else 1)
            xr = x * math.cos(twist) - yv * math.sin(twist); yr = x * math.sin(twist) + yv * math.cos(twist)
            d = Vector((math.cos(a0), 0, math.sin(a0))); side = Vector((-math.sin(a0), 0, math.cos(a0)))
            ring.append(bm.verts.new(hub + d * r + side * xr + Vector((0, yr, 0))))
        rings.append(ring)
    for A, B in zip(rings, rings[1:]):
        for j in range(10): bm.faces.new((A[j], A[(j + 1) % 10], B[(j + 1) % 10], B[j]))
    bm.faces.new(rings[-1]); bm.faces.new(rings[0][::-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    blades.append(new_obj('葉', bm, WHITE, True))
cone = lathe('鼻錐', [(0, 0), (.75, 0), (.7, .5), (.4, 1.1), (0, 1.4)], (0, 0, 0), WHITE, 24, axis='Y')
for v in cone.data.vertices: v.co.y *= axis_y
cone.location = hub - Vector((0, axis_y * .3, 0))
bpy.ops.object.select_all(action='DESELECT'); cone.select_set(True); bpy.context.view_layer.objects.active = cone
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
blades.append(cone)
swap_mesh(bl, merge(blades, 'tmp'))

export()
