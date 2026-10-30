# 孔子生平：水墨古風場景
# 執行：blender --background --factory-startup --python 孔子生平.py
# 座標以 three.js 的 (x, z) 規劃，T() 轉成 Blender (x, -z)；人物面向 Blender -Y（= three +z）。
import bpy, bmesh, math, random, os
from mathutils import Vector

OUT = os.path.dirname(os.path.abspath(__file__))
random.seed(7)
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
col = scene.collection

def T(x, z, y=0.0):
    return Vector((x, -z, y))

# ---------- 材質 ----------
MATS = {}
def mat(name, hexcol, rough=0.95, emit=0.0, metal=0.0):
    if name in MATS: return MATS[name]
    h = hexcol.lstrip('#'); c = [int(h[i:i+2], 16) / 255 for i in (0, 2, 4)]
    c = [((v + 0.055) / 1.055) ** 2.4 if v > 0.04045 else v / 12.92 for v in c]
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    b.inputs['Base Color'].default_value = (*c, 1)
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal
    if emit:
        b.inputs['Emission Color'].default_value = (*c, 1)
        b.inputs['Emission Strength'].default_value = emit
    MATS[name] = m
    return m

M = dict(
    ground=mat('宣紙地面', '#c4b89f'), road=mat('土路', '#a8987c'), field=mat('田畦', '#9fa088'),
    water=mat('水面', '#8e9a98', 0.25), earth=mat('夯土牆', '#a08a6c'), thatch=mat('茅草', '#7d6a4f'),
    tile=mat('青瓦', '#3e3b39', 0.8), wood=mat('木構', '#5b4434'), pillar=mat('朱柱', '#7a3e2e'),
    stone=mat('石材', '#8f8a80'), stoneD=mat('深石', '#6b665e'), mountain=mat('遠山', '#4a463f'),
    mountainL=mat('淡山', '#6e685d'), pine=mat('松針', '#2f3a30'), bark=mat('樹幹', '#3b3129'),
    blossom=mat('杏花', '#ead6cf'), leaf=mat('樹葉', '#4a5640'), willow=mat('柳葉', '#6f7a5c'),
    bamboo=mat('竹簡', '#b39b62'), cloth=mat('坐席', '#8a7a5c'), fire=mat('火光', '#ffa45a', 0.6, 3.0),
    skin=mat('膚色', '#d8bfa2'), hair=mat('墨髮', '#1e1b19'), beard=mat('白鬚', '#bdb6aa'),
    shoe=mat('布鞋', '#2a2622'), horse=mat('馬', '#5d4a3a'), grave=mat('墓土', '#6f7560'),
)

# ---------- 幾何工具 ----------
def obj_from_bm(name, bm, m, loc=(0, 0, 0), smooth=False):
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    if smooth:
        for p in me.polygons: p.use_smooth = True
    if m: me.materials.append(m)
    o = bpy.data.objects.new(name, me); col.objects.link(o); o.location = loc
    return o

def box(name, size, loc, m, rz=0.0):
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1)
    bmesh.ops.scale(bm, vec=size, verts=bm.verts)
    o = obj_from_bm(name, bm, m, loc); o.rotation_euler.z = rz
    return o

def cone(name, r1, r2, h, loc, m, seg=16, smooth=True):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r1, radius2=r2, depth=h)
    bmesh.ops.translate(bm, vec=(0, 0, h / 2), verts=bm.verts)
    return obj_from_bm(name, bm, m, loc, smooth)

def sphere(name, r, loc, m, seg=14, scale=(1, 1, 1)):
    bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=seg // 2 + 2, radius=r)
    bmesh.ops.scale(bm, vec=scale, verts=bm.verts)
    return obj_from_bm(name, bm, m, loc, True)

def apply(o):
    bpy.ops.object.select_all(action='DESELECT'); o.select_set(True)
    bpy.context.view_layer.objects.active = o
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)

def join(objs, name, origin=None):
    objs = [o for o in objs if o]
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs: o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    if len(objs) > 1: bpy.ops.object.join()
    o = bpy.context.view_layer.objects.active; o.name = name; o.data.name = name
    if origin is not None:
        scene.cursor.location = origin
        bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
    return o

def roof(name, W, D, h, loc, m, lift=0.35, rz=0.0, hip=True):
    """飛簷屋頂：四角上翹、邊中下垂；hip=False 為兩坡（茅草屋）。"""
    R = max(0.0, W - D) if hip else W
    bm = bmesh.new(); v = bm.verts.new
    c0, m0, c1 = v((-W, -D, lift)), v((0, -D, 0)), v((W, -D, lift))
    m1, c2, m2 = v((W, 0, lift * .3)), v((W, D, lift)), v((0, D, 0))
    c3, m3 = v((-W, D, lift)), v((-W, 0, lift * .3))
    r0, r1 = v((-R, 0, h)), v((R, 0, h))
    F = bm.faces.new
    F((c0, m0, r0)); F((m0, r1, r0)); F((m0, c1, r1)); F((c1, m1, r1)); F((m1, c2, r1))
    F((c2, m2, r1)); F((m2, r0, r1)); F((m2, c3, r0)); F((c3, m3, r0)); F((m3, c0, r0))
    F((c0, m3, c3, m2, c2, m1, c1, m0))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    o = obj_from_bm(name, bm, m, loc); o.rotation_euler.z = rz
    ridge = box(name + '_脊', (2 * R + .3 if R else .3, .28, .28), Vector(loc) + Vector((0, 0, h)), m)
    ridge.rotation_euler.z = rz
    return join([o, ridge], name)

def strip(name, pts, width, z, m):
    """沿 three (x,z) 點列鋪一條帶狀面（道路、河）。"""
    bm = bmesh.new(); L, Rr = [], []
    P = [T(x, zz, z) for x, zz in pts]
    for i, p in enumerate(P):
        a = P[max(0, i - 1)]; b = P[min(len(P) - 1, i + 1)]
        d = (b - a); d.z = 0; d.normalize(); n = Vector((-d.y, d.x, 0)) * width / 2
        L.append(bm.verts.new(p + n)); Rr.append(bm.verts.new(p - n))
    for i in range(len(P) - 1):
        bm.faces.new((L[i], Rr[i], Rr[i + 1], L[i + 1]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    for f in bm.faces:
        if f.normal.z < 0: f.normal_flip()
    return obj_from_bm(name, bm, m)

def smooth_path(pts, n=6):
    """Catmull-Rom 插值，讓路與河彎得自然。"""
    out = []
    P = [pts[0]] + pts + [pts[-1]]
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = [Vector(q) for q in P[i - 1:i + 3]]
        for k in range(n):
            t = k / n
            out.append(tuple(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3)))
    out.append(pts[-1])
    return out

# ---------- 地面、河、路、田 ----------
g = box('地面', (420, 420, .2), (0, 0, -.1), M['ground'])

RIVER = [(36, -120), (34, -60), (30, -30), (33, -6), (33, 6), (30, 26), (34, 60), (40, 120)]
strip('泗水', smooth_path(RIVER), 7.5, .03, M['water'])

ROAD_TRAVEL = [(24, 6), (33, 6), (40, 5), (45, 1), (50, 5), (53, 10), (57, 6), (60, 3), (63, -4), (64, -9), (72, -20), (86, -34)]
TRAVEL_S = smooth_path(ROAD_TRAVEL, 5)
strip('周遊之路', TRAVEL_S, 2.6, .04, M['road'])
roads = [strip('魯國道路_1', smooth_path([(-28, 12), (-22, 14), (-12, 6), (0, 6), (14, 6), (24, 6)]), 2.4, .04, M['road']),
         strip('魯國道路_2', smooth_path([(0, 6), (-4, -4), (-12, -9)]), 1.8, .04, M['road']),
         strip('魯國道路_3', smooth_path([(14, 6), (13, -6), (12, -9)]), 2.2, .04, M['road']),
         strip('魯國道路_4', smooth_path([(-12, -9), (-22, -16), (-30, -18)]), 1.6, .04, M['road'])]
join(roads, '魯國道路')
fields = []
for i, (x, z, w, d) in enumerate([(-40, 2, 9, 6), (-40, 9, 9, 6), (-40, 16, 9, 6), (-30, 24, 8, 6), (-20, 26, 8, 6), (-6, 18, 10, 5), (6, 18, 10, 5), (-50, 12, 7, 12)]):
    fields.append(box('田_%d' % i, (w - .5, d - .5, .06), T(x, z, .03), M['field']))
join(fields, '田畦')

# ---------- 陬邑故居（茅草屋＋籬笆＋井） ----------
hx, hz = -28, 8
parts = [box('故居_牆', (6, 4.4, 2.6), T(hx, hz, 1.3), M['earth']),
         box('故居_門', (1.1, .1, 1.8), T(hx, hz + 2.22, .9), M['wood']),
         roof('故居_頂', 3.7, 2.8, 1.9, T(hx, hz, 2.6), M['thatch'], lift=0, hip=False)]
for i in range(26):
    if i in (6, 7): continue   # 籬笆南側留門口，走出院子不穿模
    a = i / 26 * math.tau
    parts.append(box('籬_%d' % i, (.12, .12, 1.0), T(hx + math.cos(a) * 6.5, hz + 2 + math.sin(a) * 5, .5), M['wood']))
parts.append(cone('井', .7, .7, .7, T(hx + 4, hz + 4.5), M['stone'], 14))
join(parts, '陬邑故居')

# ---------- 倉廩（委吏） ----------
gx, gz = -19, 17
join([cone('倉_身', 2.0, 2.0, 2.8, T(gx, gz), M['earth'], 20),
      cone('倉_頂', 2.6, .05, 2.0, T(gx, gz, 2.8), M['thatch'], 20, False),
      box('倉_門', (.9, .1, 1.5), T(gx, gz + 2.0, .75), M['wood'])], '倉廩')

# ---------- 書齋（整理典籍、問禮） ----------
sx, sz = -12, -13
sp = [box('書齋_台', (8, 6, .5), T(sx, sz, .25), M['stone']),
      box('書齋_後牆', (7, .4, 3), T(sx, sz - 2.4, 2), M['earth']),
      box('書齋_左牆', (.4, 4.8, 3), T(sx - 3.3, sz, 2), M['earth']),
      box('書齋_右牆', (.4, 4.8, 3), T(sx + 3.3, sz, 2), M['earth']),
      box('書齋_柱1', (.3, .3, 3), T(sx - 3.3, sz + 2.4, 2), M['pillar']),
      box('書齋_柱2', (.3, .3, 3), T(sx + 3.3, sz + 2.4, 2), M['pillar']),
      roof('書齋_頂', 4.6, 3.6, 2.0, T(sx, sz, 3.5), M['tile'], lift=.45)]
join(sp, '書齋')
desk = [box('書案_面', (2.2, .9, .12), T(sx, sz - .6, 1.0), M['wood']),
        box('書案_腳1', (.12, .8, .45), T(sx - 1, sz - .6, .72), M['wood']),
        box('書案_腳2', (.12, .8, .45), T(sx + 1, sz - .6, .72), M['wood'])]
join(desk, '書案')
slips = []
for i in range(7):
    c = cone('簡_%d' % i, .13, .13, .7, T(sx - .8 + i * .26, sz - .55 + (i % 2) * .1, 1.06), M['bamboo'], 10)
    c.rotation_euler.x = math.pi / 2; apply(c); slips.append(c)
for i in range(5):
    c = cone('簡堆_%d' % i, .12, .12, .7, T(sx + 2.2, sz - 1.6 + i * .27, .5 + .13), M['bamboo'], 10)
    c.rotation_euler.y = math.pi / 2; apply(c); slips.append(c)
join(slips, '竹簡')

# ---------- 杏壇 ----------
ax, az = 0, 2
ap = [box('杏壇_台', (9, 9, .7), T(ax, az, .35), M['stone']),
      box('杏壇_緣', (9.4, 9.4, .18), T(ax, az, .79), M['stoneD']),
      box('杏壇_階', (3, 1.2, .35), T(ax, az + 5.0, .18), M['stoneD'])]
for i in range(8):
    a = i / 8 * math.tau + .2
    ap.append(box('坐席_%d' % i, (1.0, 1.0, .05), T(ax + math.cos(a) * 2.8, az + .6 + math.sin(a) * 2.8, .9), M['cloth'], a))
join(ap, '杏壇')
join([box('琴_身', (1.3, .26, .08), T(ax, az - 1.3, 1.25), M['wood']),
      box('琴_几', (1.2, .4, .35), T(ax, az - 1.3, 1.0), M['wood'])], '琴')

def tree_blossom(name, x, z, h, r, m_leaf, n=9):
    ps = [cone(name + '_幹', .35, .18, h, T(x, z), M['bark'], 10)]
    for i in range(3):
        b = cone(name + '_枝%d' % i, .14, .06, h * .55, T(x, z, h * .55), M['bark'], 8)
        b.rotation_euler = (random.uniform(.5, .9), 0, i * 2.1); apply(b); ps.append(b)
    for i in range(n):
        a = random.uniform(0, math.tau); d = random.uniform(0, r * .7)
        ps.append(sphere(name + '_冠%d' % i, random.uniform(r * .4, r * .65),
                         T(x + math.cos(a) * d, z + math.sin(a) * d, h + random.uniform(-.4, 1.4)), m_leaf, 10, (1, 1, .75)))
    return join(ps, name)

tree_blossom('杏樹', ax - 3.6, az - 3.4, 3.6, 3.0, M['blossom'], 11)

# ---------- 魯國朝堂 ----------
px, pz = 12, -17
pp = [box('朝堂_台', (19, 12, 1.6), T(px, pz, .8), M['stone']),
      box('朝堂_階', (5, 3, .8), T(px, pz + 7.4, .4), M['stoneD']),
      box('朝堂_牆', (12, 6, 4.2), T(px, pz - .4, 3.7), M['earth'])]
for i in range(8):
    pp.append(box('朝堂_柱%d' % i, (.45, .45, 4.2), T(px - 6.3 + i * 1.8, pz + 3.2, 3.7), M['pillar']))
pp.append(roof('朝堂_頂', 8.6, 5.4, 3.4, T(px, pz, 5.8), M['tile'], lift=.6))
join(pp, '魯國朝堂')

# ---------- 魯城牆與城門 ----------
wall = []
for z0, z1 in [(-38, 3), (9, 42)]:
    wall.append(box('城牆_%d' % z0, (2.6, z1 - z0, 4.6), T(24, (z0 + z1) / 2, 2.3), M['earth']))
join(wall, '魯城牆')
join([box('城門_台', (3.2, 7.4, 1.2), T(24, 6, 5.2), M['earth']),
      box('城門_樓', (2.6, 5, 2.2), T(24, 6, 6.9), M['wood']),
      roof('城門_頂', 3.6, 2.2, 1.6, T(24, 6, 8.0), M['tile'], lift=.35, rz=math.pi / 2)], '魯城門')

# ---------- 石橋 ----------
join([box('橋_面', (9, 3.2, .4), T(33, 6, .75), M['stone']),
      box('橋_欄1', (9, .2, .5), T(33, 4.5, 1.2), M['stoneD']),
      box('橋_欄2', (9, .2, .5), T(33, 7.5, 1.2), M['stoneD'])], '石橋')

# ---------- 周遊列國：匡邑、宋國大樹、鄭國東門、陳蔡營地 ----------
kx, kz = 47, -6
kp = []
for (dx, dz, w, d) in [(0, -4, 9, .6), (0, 4, 9, .6), (-4.5, 0, .6, 8.6), (4.5, -2.4, .6, 3.8)]:
    kp.append(box('匡_牆', (w, d, 2.0), T(kx + dx, kz + dz, 1.0), M['earth']))
for dx, dz in [(-1.8, -1.5), (1.8, 1.2)]:
    kp.append(box('匡_屋', (2.6, 2.2, 1.8), T(kx + dx, kz + dz, .9), M['earth']))
    kp.append(roof('匡_頂', 1.6, 1.4, 1.0, T(kx + dx, kz + dz, 1.8), M['thatch'], lift=0, hip=False))
join(kp, '匡邑')
tree_blossom('宋國大樹', 55.5, 13.5, 4.4, 4.2, M['leaf'], 13)
# 鄭國東門：城牆、城門洞、門樓。先在本地座標建（城牆沿 X、道路沿 Y），再轉到道路方向
gp = []
for sx_ in (-1, 1):
    gp.append(box('鄭門_牆', (6.8, 3.2, 5.2), (sx_ * 5.6, 0, 2.6), M['earth']))
    gp.append(box('鄭門_牆頂', (6.8, 3.5, .3), (sx_ * 5.6, 0, 5.35), M['stoneD']))
    for k in range(5):
        gp.append(box('鄭門_垛', (.7, .4, .55), (sx_ * (3.0 + k * 1.35), 1.55, 5.75), M['stoneD']))
    door = box('鄭門_門扇', (1.9, .16, 3.3), (sx_ * 2.0, -2.6, 1.65), M['wood'])   # 門扇向內打開、貼著門洞兩側
    door.rotation_euler.z = sx_ * math.radians(88); gp.append(door)
    gp.append(cone('鄭門_旗桿', .06, .05, 3.0, (sx_ * 7.6, 1.2, 5.5), M['wood'], 6))
    gp.append(box('鄭門_旗', (1.1, .05, .8), (sx_ * 7.6 + .58, 1.2, 8.0), M['pillar']))
gp.append(box('鄭門_洞頂', (4.4, 3.2, 1.6), (0, 0, 4.4), M['earth']))
gp.append(box('鄭門_牆頂中', (4.4, 3.5, .3), (0, 0, 5.35), M['stoneD']))
gp.append(box('鄭門_樓身', (6.6, 3.0, 2.4), (0, 0, 6.7), M['wood']))
for k in range(5):
    gp.append(box('鄭門_樓柱', (.28, .28, 2.4), (-3.0 + k * 1.5, 1.55, 6.7), M['pillar']))
gp.append(box('鄭門_欄', (7.4, 3.8, .2), (0, 0, 5.6), M['wood']))
gp.append(roof('鄭門_頂', 4.4, 2.5, 1.9, (0, 0, 7.9), M['tile'], lift=.5))
gate = join(gp, '鄭國東門', origin=(0, 0, 0))
gate.rotation_euler.z = math.radians(-45); gate.location = T(57.3, 5.7)

# 陳蔡之亭：六角亭，平邊朝北（three +z）當入口
cx, cz = 64.5, -9
pv = [cone('亭_台', 3.3, 3.3, .45, T(cx, cz), M['stone'], 6, False),
      box('亭_階', (2.2, .9, .22), T(cx, cz + 3.25, .11), M['stoneD']),
      cone('亭_梁', 3.0, 3.0, .28, T(cx, cz, 3.0), M['wood'], 6, False),
      box('亭_几', (.9, .6, .3), T(cx, cz, .6), M['wood']),
      cone('亭_碗', .2, .12, .14, T(cx, cz, .75), M['stoneD'], 10)]
for k in range(6):
    a = k * math.pi / 3
    pv.append(cone('亭_柱', .16, .14, 2.6, Vector((cx + 2.75 * math.cos(a), -cz + 2.75 * math.sin(a), .45)), M['pillar'], 8))
bm = bmesh.new(); ap = bm.verts.new((0, 0, 2.2))
cs = [bm.verts.new((3.9 * math.cos(k * math.pi / 3), 3.9 * math.sin(k * math.pi / 3), .5)) for k in range(6)]
ms = [bm.verts.new((3.3 * math.cos(k * math.pi / 3 + math.pi / 6), 3.3 * math.sin(k * math.pi / 3 + math.pi / 6), 0)) for k in range(6)]
for k in range(6):
    bm.faces.new((cs[k], ms[k], ap)); bm.faces.new((ms[k], cs[(k + 1) % 6], ap))
bm.faces.new([v for k in range(6) for v in (cs[k], ms[k])][::-1])
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
pv.append(obj_from_bm('亭_頂', bm, M['tile'], T(cx, cz, 3.25)))
pv.append(sphere('亭_寶頂', .28, T(cx, cz, 5.55), M['tile'], 10))
pv.append(cone('亭_尖', .12, .01, .6, T(cx, cz, 5.75), M['tile'], 8))
for o in pv[:3:2]: o.rotation_euler.z = math.radians(30)   # 台基、梁的六角與柱子、屋頂對齊，平邊朝入口
join(pv, '陳蔡之亭')

# ---------- 孔子墓（孔林）與子貢廬 ----------
mx, mz = -31, -25
mound = sphere('墓_丘', 3.6, T(mx, mz, 0), M['grave'], 20, (1, 1, .55))
join([mound], '孔子墓')
join([box('碑_身', (1.0, .28, 2.0), T(mx, mz + 4.6, 1.0), M['stone']),
      box('碑_座', (1.4, .6, .3), T(mx, mz + 4.6, .15), M['stoneD'])], '墓碑')
join([box('廬_牆', (2.6, 2.2, 1.8), T(mx + 7, mz + 1, .9), M['earth']),
      roof('廬_頂', 1.7, 1.4, 1.1, T(mx + 7, mz + 1, 1.8), M['thatch'], lift=0, hip=False)], '子貢廬')

# ---------- 松、柳 ----------
def pine(x, z, h):
    ps = [cone('松幹', .22, .12, h, T(x, z), M['bark'], 8)]
    for i in range(4):
        y = h * (.45 + i * .16); r = (1.0 - i * .2) * h * .32
        d = cone('松層', r, r * .35, h * .12, T(x + random.uniform(-.4, .4), z + random.uniform(-.4, .4), y), M['pine'], 9, False)
        d.rotation_euler = (random.uniform(-.12, .12), random.uniform(-.12, .12), 0); apply(d); ps.append(d)
    return ps

PINES = [(-36, -30), (-26, -32), (-38, -20), (-24, -19), (-34, -14), (-44, -26), (-20, -28),
         (-6, -24), (2, -26), (-18, 4), (8, -6), (20, -30), (-48, 0), (-46, 22), (-14, 28),
         (16, 22), (6, 30), (42, 18), (44, -16), (52, -18), (60, 18), (68, 6), (70, -26), (76, -14),
         (58, -24), (-56, -12), (-60, 30), (28, -46), (-10, -40), (12, -40)]
pp = []
for x, z in PINES: pp += pine(x + random.uniform(-1, 1), z + random.uniform(-1, 1), random.uniform(5, 8.5))
join(pp, '松林')
wl = []
for x, z in [(29, -22), (29, 16), (37.5, -10), (37, 18), (27, 34), (38, 40), (27, -40)]:
    wl.append(cone('柳幹', .25, .15, 3.2, T(x, z), M['bark'], 8))
    wl.append(cone('柳葉', 1.9, .5, 3.4, T(x, z, 1.4), M['willow'], 10))
join(wl, '柳')

# ---------- 遠山（層層疊疊，越遠越淡由霧處理） ----------
def mountain(name, x, z, w, d, h, m, peaks=3, seed=0):
    rnd = random.Random(seed); N = 26
    bm = bmesh.new(); grid = []
    pk = [(rnd.uniform(-.5, .5), rnd.uniform(-.3, .3), rnd.uniform(.55, 1.0)) for _ in range(peaks)]
    for j in range(N + 1):
        row = []
        for i in range(N + 1):
            u, v = i / N * 2 - 1, j / N * 2 - 1
            hh = 0
            for (px_, py_, ph) in pk:
                dd = math.hypot((u - px_) * 1.6, (v - py_) * 1.2)
                hh = max(hh, ph * math.exp(-dd * dd * 3.2))
            edge = max(0, 1 - max(abs(u), abs(v)) ** 6)
            hh = hh * edge + .04 * math.sin(u * 13 + seed) * math.sin(v * 11) * edge
            row.append(bm.verts.new((u * w, v * d, max(0, hh) * h - .5)))
        grid.append(row)
    for j in range(N):
        for i in range(N):
            bm.faces.new((grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]))
    return obj_from_bm(name, bm, m, T(x, z), True)

mts = []
random.seed(11)
RANGE = [(-110, -110, 50, 26, 46), (-40, -125, 55, 28, 58), (40, -130, 60, 30, 64), (120, -110, 55, 28, 52),
         (-160, -40, 40, 50, 40), (160, -30, 40, 50, 44), (130, 40, 36, 40, 34), (-140, 60, 40, 40, 30),
         (-70, -70, 28, 18, 26), (10, -80, 30, 16, 24), (80, -70, 26, 18, 30), (100, 10, 22, 26, 24),
         (-80, 30, 18, 22, 16), (-30, -55, 16, 10, 12)]
for i, (x, z, w, d, h) in enumerate(RANGE):
    far = math.hypot(x, z) > 120
    mts.append(mountain('山_%d' % i, x, z, w, d, h, M['mountainL'] if far else M['mountain'], 3 + i % 3, i * 7))
join(mts, '遠山')

# ---------- 人物 ----------
def person(name, robe, trim, hat='bun', beard=False, k=1.0):
    """身體為父物件（原點在腳底）；四肢為子物件，原點在關節。面向 Blender -Y。"""
    ps = [cone(name + '_袍', .36 * k, .2 * k, 1.28 * k, (0, 0, .07 * k), robe, 16),
          cone(name + '_領', .21 * k, .14 * k, .12 * k, (0, 0, 1.3 * k), trim, 14),
          box(name + '_帶', (.5 * k, .44 * k, .08 * k), (0, 0, .82 * k), trim),
          sphere(name + '_頭', .17 * k, (0, 0, 1.56 * k), M['skin'], 14),
          sphere(name + '_髮', .175 * k, (0, .03 * k, 1.6 * k), M['hair'], 14, (1, 1, .85))]
    if hat == 'guan':
        ps.append(box(name + '_冠', (.12 * k, .3 * k, .16 * k), (0, .02 * k, 1.8 * k), M['hair']))
        ps.append(box(name + '_簪', (.4 * k, .03 * k, .03 * k), (0, .02 * k, 1.82 * k), M['bamboo']))
    elif hat == 'bun':
        ps.append(sphere(name + '_髻', .08 * k, (0, .05 * k, 1.78 * k), M['hair'], 10))
    elif hat == 'veil':
        ps.append(cone(name + '_巾', .2 * k, .12 * k, .14 * k, (0, .02 * k, 1.66 * k), trim, 12))
    if beard:
        b = cone(name + '_鬚', .1 * k, .01 * k, .32 * k, (0, -.12 * k, 1.18 * k), M['beard'], 10)
        b.rotation_euler.x = math.pi; b.location.z = 1.5 * k; apply(b); ps.append(b)
    body = join(ps, name, origin=(0, 0, 0))
    for side, sx_ in (('左', -1), ('右', 1)):
        leg = join([cone(name + '_腿', .07 * k, .07 * k, .5 * k, (0, 0, .05 * k), M['shoe'], 8),
                    box(name + '_鞋', (.13 * k, .26 * k, .08 * k), (0, -.05 * k, .04 * k), M['shoe'])],
                   name + '_' + side + '腳', origin=(0, 0, .55 * k))
        leg.location = (sx_ * .11 * k, 0, .55 * k)
        arm = join([cone(name + '_袖', .12 * k, .08 * k, .6 * k, (0, 0, .7 * k), robe, 10),
                    sphere(name + '_掌', .055 * k, (0, 0, .66 * k), M['skin'], 8)],
                   name + '_' + side + '手', origin=(0, 0, 1.3 * k))
        arm.location = (sx_ * .27 * k, 0, 1.3 * k)
        for o in (leg, arm):
            o.parent = body
    return body

CAST = [
    ('孔子', mat('孔子袍', '#3c342d'), mat('孔子緣', '#8a6f4e'), 'guan', True, 1.06, (0, 1)),
    ('母親', mat('母親袍', '#76675a'), mat('母親緣', '#a89279'), 'veil', False, .96, (-27, 12)),
    ('老子', mat('老子袍', '#cfc8ba'), mat('老子緣', '#6e675c'), 'bun', True, 1.0, (-12, -8)),
    ('顏回', mat('顏回袍', '#8b9294'), mat('顏回緣', '#4f5658'), 'bun', False, 1.0, (2, 4)),
    ('子路', mat('子路袍', '#7b4a36'), mat('子路緣', '#3d2a20'), 'guan', False, 1.04, (-2, 4)),
    ('子貢', mat('子貢袍', '#6a6a4a'), mat('子貢緣', '#3b3b2a'), 'guan', False, 1.0, (3, 0)),
]
for i in range(5):
    CAST.append(('弟子_%d' % (i + 1), mat('弟子袍_%d' % i, ['#6e6458', '#5d625e', '#857563', '#4f4a44', '#77705f'][i]),
                 mat('弟子緣', '#3a352f'), 'bun', False, .97, (-4 + i * 2, 6)))
for name, robe, trim, hat, beard, k, (x, z) in CAST:
    b = person(name, robe, trim, hat, beard, k)
    b.location = T(x, z)

# ---------- 馬車（周遊列國） ----------
cart = [box('車_廂', (1.4, 1.8, .6), (0, .4, .95), M['wood']),
        box('車_轅', (.12, 3.2, .1), (-.35, -1.6, .9), M['wood']),
        box('車_轅2', (.12, 3.2, .1), (.35, -1.6, .9), M['wood']),
        cone('車_傘柄', .03, .03, 1.4, (0, .4, 1.2), M['wood'], 6),
        cone('車_傘', 1.3, .05, .45, (0, .4, 2.4), M['tile'], 16, False),
        box('馬_身', (.6, 1.6, .7), (0, -2.6, 1.25), M['horse']),
        box('馬_頸', (.35, .5, .8), (0, -3.4, 1.75), M['horse']),
        box('馬_頭', (.3, .7, .3), (0, -3.75, 2.1), M['horse'])]
for dx in (-.35, .35):
    for dy in (-3.1, -2.1):
        cart.append(box('馬_腿', (.16, .16, .95), (dx, dy, .47), M['horse']))
for dx in (-.85, .85):
    w = cone('車_輪', .7, .7, .1, (dx - .05, .4, .7), M['shoe'], 18, False)
    w.rotation_euler.y = math.pi / 2; w.location = (dx - .05, .4, .7); apply(w); cart.append(w)
cartO = join(cart, '馬車', origin=(0, 0, 0))
cartO.location = T(20, 6)

# ---------- 匯出 ----------
bpy.ops.object.select_all(action='SELECT')
glb = os.path.join(OUT, '孔子生平.glb')
bpy.ops.export_scene.gltf(filepath=glb, export_format='GLB', use_selection=True, export_extras=True,
                          export_apply=True, export_lights=False, export_cameras=False)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, '孔子生平.blend'))
print('EXPORTED', glb, os.path.getsize(glb))
