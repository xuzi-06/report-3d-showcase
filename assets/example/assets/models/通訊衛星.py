# 通訊衛星：讀入原始模型 src/通訊衛星.glb，提高精度後匯出 通訊衛星.glb
# 執行：blender --background --factory-startup --python 通訊衛星.py
# 只換網格、不改物件名稱與階層。
import bpy, bmesh, math, random, os
from mathutils import Vector, Matrix, noise

OUT = os.path.dirname(os.path.abspath(__file__))
NAME = '通訊衛星'
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
GOLD, WHITE, SILVER = material('衛星｜金色隔熱膜'), material('衛星｜白色散熱板'), material('金屬｜鈦銀')
CELL, DARK = material('太陽能｜電池片'), material('設備｜石墨外殼')
TAPE = material('衛星｜銀色膠帶', '#c9ccd1', .35)

# ---------- 主體：多層隔熱毯的皺褶與銀色封邊膠帶 ----------
body = OB['衛星｜主體平台']
mn, mx, c, s = bbox(body)
bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1)
bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=14, use_grid_fill=True)
bmesh.ops.scale(bm, vec=s * .99, verts=bm.verts)
for v in bm.verts:                                    # 皺褶：沿法線方向的低頻噪聲，邊角收斂
    d = max(abs(v.co.x) / s.x, abs(v.co.y) / s.y, abs(v.co.z) / s.z) * 2
    k = noise.noise(v.co * 4.5) * .025 + noise.noise(v.co * 11) * .008
    v.co += v.co.normalized() * k * d
bmesh.ops.translate(bm, vec=c, verts=bm.verts)
wrinkled = new_obj('隔熱毯', bm, GOLD, True)
tape = []
for z in (mn.z + .15, mx.z - .15):
    for (sx, sy) in ((s.x + .02, .05), (.05, s.y + .02)):
        for sign in (-1, 1):
            off = Vector((0, sign * (s.y / 2), 0)) if sx > sy else Vector((sign * (s.x / 2), 0, 0))
            tape.append(box('膠帶', (sx, sy, .06), c + off + Vector((0, 0, z - c.z)), TAPE, .005))
swap_mesh(body, merge([wrinkled] + tape, 'tmp'))

# ---------- 拋物面天線：碟面、背部肋條、饋源支架與喇叭 ----------
dish = OB['衛星｜拋物面天線']
mn, mx, c, s = bbox(dish); R = s.x / 2; D = .32
prof = [(R * i / 16, D * (i / 16) ** 2) for i in range(17)]
outer = [(r, z - .02) for r, z in prof][::-1]
bowl = lathe('碟面', [(0, -.02)] + [(r, z - .02) for r, z in prof[1:]] + [(R + .03, D), (R + .03, D + .03)] + [(r, z + .015) for r, z in prof[::-1][:-1]] + [(0, .015)],
             (c.x, c.y, mx.z - .02), WHITE, 48, axis='-Z')
ribs = []
for k in range(8):                                    # 碟背肋條
    a = k / 8 * math.tau
    pts = [Vector((c.x + math.cos(a) * R * t, c.y + math.sin(a) * R * t, mx.z - .02 - D * t * t + .03)) for t in (.08, .4, .7, 1.0)]
    ribs.append(tube('肋', pts, .018, SILVER, 5))
ribs.append(lathe('碟緣', [(R - .02, -.02), (R + .05, -.02), (R + .05, .03), (R - .02, .03)], (c.x, c.y, mx.z - .02 - D), SILVER, 48, axis='Z'))
swap_mesh(dish, merge([bowl] + ribs, 'tmp'))
horn = OB['衛星｜饋源喇叭']
hmn, hmx, hc, hs = bbox(horn)
swap_mesh(horn, lathe('喇叭', [(0, 0), (.05, 0), (.06, .06), (.13, .22), (.15, .24), (.12, .24), (0, .24)], (hc.x, hc.y, hmn.z), GOLD, 24, axis='Z'))
strut = OB['衛星｜饋源支架']
legs = []
for k in range(4):
    a = k / 4 * math.tau + math.pi / 4
    p0 = Vector((c.x + math.cos(a) * R * .92, c.y + math.sin(a) * R * .92, mx.z - .02 - D * .85))
    legs.append(tube('支架', [p0, Vector((hc.x, hc.y, hmx.z + .02))], .02, SILVER, 6))
swap_mesh(strut, merge(legs, 'tmp'))

# ---------- 太陽能電池翼：三片面板、邊框、電池格、連接臂 ----------
for side in ('右', '左'):
    wing, grid = OB['衛星｜太陽能電池翼' + side], OB['衛星｜電池翼格線' + side]
    mn, mx, c, s = bbox(wing); sg = 1 if side == '右' else -1
    pw = (s.x - .16) / 3; panels, frames = [], []
    for i in range(3):
        px = mn.x + pw / 2 + i * (pw + .08)
        panels.append(box('板', (pw - .06, .03, s.z - .06), (px, c.y, c.z), CELL, .004))
        for dz in (-(s.z / 2 - .03), s.z / 2 - .03):
            frames.append(box('框', (pw, .05, .05), (px, c.y, c.z + dz), SILVER, .008))
        for dx in (-(pw / 2 - .025), pw / 2 - .025):
            frames.append(box('框', (.05, .05, s.z), (px + dx, c.y, c.z), SILVER, .008))
        for k in range(1, 6):                          # 電池格線（正反面）
            for y in (c.y - .018, c.y + .018):
                frames.append(box('格', (.012, .006, s.z - .08), (px - pw / 2 + k * pw / 6, y, c.z), SILVER, 0))
        for k in range(1, 4):
            for y in (c.y - .018, c.y + .018):
                frames.append(box('格', (pw - .08, .006, .012), (px, y, c.z - s.z / 2 + k * s.z / 4), SILVER, 0))
        if i < 2:                                      # 板間鉸鏈
            for dz in (-.6, .6):
                frames.append(tube('鉸鏈', [(px + pw / 2 - .02, c.y, c.z + dz), (px + pw / 2 + .1, c.y, c.z + dz)], .025, SILVER, 6))
    swap_mesh(wing, merge(panels, 'tmp')); swap_mesh(grid, merge(frames, 'tmp'))
    near = mn.x if side == '右' else mx.x                # Y 形連接臂：轉軸末端分叉到面板上下緣
    root = Vector((near - sg * .35, c.y, c.z))
    arm = [tube('臂', [root, Vector((near, c.y, c.z + s.z * .35))], .03, SILVER, 6),
           tube('臂', [root, Vector((near, c.y, c.z - s.z * .35))], .03, SILVER, 6)]
    shaft = OB['衛星｜太陽能板轉軸' + ('.001' if side == '右' else '')]
    smn, smx, sc_, ss = bbox(shaft)
    arm.append(tube('軸', [Vector((smn.x, sc_.y, sc_.z)), Vector((smx.x, sc_.y, sc_.z))], .045, SILVER, 12))
    arm.append(lathe('驅動', [(0, 0), (.1, 0), (.1, .14), (0, .14)], (smn.x if side == '右' else smx.x - .14, sc_.y, sc_.z), DARK, 16, axis='X'))
    swap_mesh(shaft, merge(arm, 'tmp'))

# ---------- 小零件：噴嘴、星追蹤儀、側向天線、平台 ----------
for nm in ('衛星｜姿態控制噴嘴', '衛星｜姿態控制噴嘴.001'):
    o = OB[nm]; mn, mx, c, s = bbox(o)
    swap_mesh(o, lathe('噴嘴', [(0, 0), (.04, 0), (.04, .05), (.03, .07), (.07, .2), (.065, .2), (0, .1)], (c.x, c.y, mn.z), SILVER, 20))
o = OB['衛星｜星追蹤儀']; mn, mx, c, s = bbox(o)
swap_mesh(o, merge([box('本體', (.14, .14, .1), (c.x, c.y, mn.z + .05), DARK, .01),
                    lathe('遮光罩', [(.05, 0), (.06, 0), (.1, .14), (.09, .14), (.045, .01)], (c.x, c.y, mn.z + .1), DARK, 20)], 'tmp'))
o = OB['衛星｜側向小天線']; mn, mx, c, s = bbox(o); R = s.y / 2
small = lathe('小碟', [(0, -.01)] + [(R * i / 10, .1 * (i / 10) ** 2 - .01) for i in range(1, 11)] + [(R, .11)] + [(R * i / 10, .1 * (i / 10) ** 2 + .01) for i in range(10, 0, -1)] + [(0, .01)],
              (mn.x + .12, c.y, c.z), WHITE, 32, axis='X')
small_arm = tube('臂', [(mn.x - .05, c.y, c.z), (mn.x + .12, c.y, c.z)], .02, SILVER, 6)
swap_mesh(o, merge([small, small_arm], 'tmp'))
for nm in ('衛星｜頂部平台', '衛星｜底部平台'):
    o = OB[nm]; mn, mx, c, s = bbox(o)
    swap_mesh(o, box('平台', tuple(s), c, mat_of(o), .02, 2))
top = OB['衛星｜頂部平台']; tmn, tmx, tc, ts = bbox(top)
extra = [tube('全向天線', [(tc.x - .5, tc.y + .5, tmx.z), (tc.x - .5, tc.y + .5, tmx.z + .45)], .012, SILVER, 6),
         lathe('天線頭', [(0, 0), (.035, 0), (.035, .08), (0, .1)], (tc.x - .5, tc.y + .5, tmx.z + .45), WHITE, 12),
         box('太陽感測器', (.12, .08, .05), (tc.x + .55, tc.y + .55, tmx.z + .025), DARK, .008)]
adopt(merge(extra, '衛星｜頂部天線'), OB['通訊衛星｜模型根節點'])
for nm in ('衛星｜散熱板', '衛星｜散熱板.001'):        # 散熱板：加上散熱鰭條
    o = OB[nm]; mn, mx, c, s = bbox(o)
    fins = [box('板', tuple(s), c, WHITE, .01)]
    out = -1 if c.y < 0 else 1
    for k in range(7):
        fins.append(box('鰭', (.025, .03, s.z - .1), (mn.x + .08 + k * (s.x - .16) / 6, c.y + out * .02, c.z), SILVER, .004))
    swap_mesh(o, merge(fins, 'tmp'))

export()
