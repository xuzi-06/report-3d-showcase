# 孔子生平：水墨古風場景
# 執行：blender --background --factory-startup --python 孔子生平.py
# 座標以 three.js 的 (x, z) 規劃，T() 轉成 Blender (x, -z)；人物面向 Blender -Y（= three +z）。
# 台基、橋面高度要和 main.html 的 groundY() 一致；頂層物件名稱是前端定位用的，改名要同步改 main.html。
import bpy, bmesh, math, random, os
from mathutils import Vector, Matrix, noise

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
    lattice=mat('窗櫺', '#3f2f25'), paper=mat('窗紙', '#d9cdb4'), rock=mat('山石', '#7c766b'),
    bank=mat('河岸', '#93886f'), furrow=mat('田壟', '#86876f'), string=mat('琴弦', '#d8c9a6', 0.5),
)

# ---------- 幾何工具 ----------
def obj_from_bm(name, bm, m, loc=(0, 0, 0), smooth=False):
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    if smooth:
        for p in me.polygons: p.use_smooth = True
    if m: me.materials.append(m)
    o = bpy.data.objects.new(name, me); col.objects.link(o); o.location = loc
    return o

def box(name, size, loc, m, rz=0.0, bv=None):
    """方塊；邊緣倒角（bv=0 不倒角），水墨描邊會沿倒角畫出柔和的邊。"""
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1)
    bmesh.ops.scale(bm, vec=size, verts=bm.verts)
    w = (min(.045, min(size) * .18) if min(size) >= .1 else 0) if bv is None else bv   # 小零件不倒角，省頂點
    if w > .004:
        bmesh.ops.bevel(bm, geom=bm.verts[:] + bm.edges[:], offset=w, offset_type='OFFSET',
                        segments=1, profile=.5, affect='EDGES', clamp_overlap=True)
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

def blob(name, r, loc, m, scale=(1, 1, 1), rough=.25, sub=2, seed=0):
    """不規則團塊（樹冠、雲片松、石頭）：icosphere 加平滑噪聲。"""
    bm = bmesh.new(); bmesh.ops.create_icosphere(bm, subdivisions=sub, radius=r)
    off = Vector((seed * 3.1, seed * 1.7, seed * 2.3))
    for v in bm.verts:
        n = v.co.normalized()
        v.co += n * r * rough * noise.noise(v.co / r * 1.3 + off)
        v.co = Vector((v.co.x * scale[0], v.co.y * scale[1], v.co.z * scale[2]))
    return obj_from_bm(name, bm, m, loc, True)

def lathe(name, prof, loc, m, seg=24, smooth=True, sc=(1, 1, 1), wob=0.0, seed=0):
    """旋轉體：prof = [(半徑, 高度), …] 由下往上（r=0 為封頂點）。sc 可壓扁成橢圓，wob 加不規則起伏。"""
    bm = bmesh.new(); rings = []
    for r, z in prof:
        if r < 1e-5:
            rings.append([bm.verts.new((0, 0, z * sc[2]))]); continue
        ring = []
        for i in range(seg):
            a = i / seg * math.tau
            rr = r * (1 + wob * noise.noise(Vector((math.cos(a) * 2, math.sin(a) * 2, z * 3 + seed))))
            ring.append(bm.verts.new((rr * math.cos(a) * sc[0], rr * math.sin(a) * sc[1], z * sc[2])))
        rings.append(ring)
    for A, B in zip(rings, rings[1:]):
        for i in range(seg):
            j = (i + 1) % seg
            q = [A[i % len(A)], A[j % len(A)], B[j % len(B)], B[i % len(B)]]
            q = [v for k, v in enumerate(q) if v not in q[:k]]
            if len(q) >= 3: bm.faces.new(q)
    return obj_from_bm(name, bm, m, loc, smooth)

def tube(name, pts, r, m, seg=8, smooth=True, cap=True, flat=1.0):
    """沿點列建管（樹枝、脊、鬚、馬腿）；r 可為單值或逐點列表；flat<1 時壓扁成帶狀。"""
    P = [Vector(p) for p in pts]; R = r if isinstance(r, (list, tuple)) else [r] * len(P)
    bm = bmesh.new(); rings = []
    for i, p in enumerate(P):
        t = (P[min(i + 1, len(P) - 1)] - P[max(i - 1, 0)]).normalized()
        ref = Vector((0, 0, 1)) if abs(t.z) < .9 else Vector((1, 0, 0))
        n = t.cross(ref).normalized(); b = t.cross(n)
        rings.append([bm.verts.new(p + (n * math.cos(a) * flat + b * math.sin(a)) * R[i])
                      for a in (k / seg * math.tau for k in range(seg))])
    for A, B in zip(rings, rings[1:]):
        for k in range(seg):
            j = (k + 1) % seg
            bm.faces.new((A[k], A[j], B[j], B[k]))
    if cap:
        bm.faces.new(rings[0][::-1]); bm.faces.new(rings[-1])
    return obj_from_bm(name, bm, m, (0, 0, 0), smooth)

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

def place(o, loc, rz=0.0):
    """把以原點為中心建好的零件移到 loc 並繞 Z 轉 rz（套用變換，方便之後 join）。"""
    o.rotation_euler.z = rz; o.location = loc; apply(o)
    bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)
    return o

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

# ---------- 屋頂：凹曲面、四角起翹、瓦壟 ----------
def _slope(bm, eA, eB, rA, rB, lift, tiles, nv=9):
    """一片坡面：eA→eB 為簷口，rA→rB 為脊線。兩端（u=±1）與相鄰坡面共用同一條戧脊，焊接後不會裂開。"""
    L = (eB - eA).length
    nu = max(8, int(L / .15)) if tiles else max(6, int(L / .5))
    grid = []
    for j in range(nv + 1):
        v = j / nv; f = v * (.32 + .68 * v)            # 簷口平緩、近脊陡：凹曲面
        row = []
        for i in range(nu + 1):
            s = i / nu; u = s * 2 - 1
            e = eA.lerp(eB, s); r = rA.lerp(rB, s)
            p = e.lerp(r, v); p.z = e.z + (r.z - e.z) * f
            p.z += lift * abs(u) ** 3 * (1 - v) ** 2    # 翼角起翹
            if tiles:                                   # 瓦壟：沿簷口方向起伏，在戧脊處歸零
                p.z += tiles * math.sin(s * L / .45 * math.tau) ** 2 * (1 - abs(u) ** 8) * (.4 + .6 * (1 - v))
            row.append(bm.verts.new(p))
        grid.append(row)
    for j in range(nv):
        for i in range(nu):
            bm.faces.new((grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]))
    return [Vector(grid[j][0].co) for j in range(nv + 1)], [Vector(grid[j][-1].co) for j in range(nv + 1)]

def _finish_roof(name, bm, m, thick, hips, ridge, loc, rz, ridge_r):
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bmesh.ops.solidify(bm, geom=bm.faces[:], thickness=thick)
    o = obj_from_bm(name, bm, m, (0, 0, 0), True)
    ps = [o]
    for k, h in enumerate(hips):                       # 戧脊：沿坡面接縫，往外翹出一點
        pts = [p + Vector((0, 0, ridge_r * .6)) for p in h]
        d = (pts[0] - pts[1]); d.z = 0; d.normalize()
        pts.insert(0, pts[0] + d * .25 + Vector((0, 0, .18)))
        ps.append(tube(name + '_戧脊%d' % k, pts, ridge_r * .7, m, 6))
    if ridge:
        a, b = ridge
        ps.append(tube(name + '_正脊', [a, b], ridge_r, m, 8))
        for e, d in ((a, a - b), (b, b - a)):          # 鴟吻：正脊兩端上翹
            d.normalize()
            ps.append(tube(name + '_吻', [e, e + d * .15 + Vector((0, 0, .25)), e + d * .05 + Vector((0, 0, .5))],
                           [ridge_r * 1.3, ridge_r, ridge_r * .4], m, 6))
    o = join(ps, name)
    o.location = loc; o.rotation_euler.z = rz
    return o

def roof(name, W, D, h, loc, m, lift=0.35, rz=0.0, hip=True, tiles=.05, thick=.14):
    """廡殿／歇山感的四坡飛簷頂；hip=False 為兩坡（茅草屋，lift 通常為 0）。"""
    R = max(.3, W - D) if hip else W
    bm = bmesh.new()
    c = [Vector((-W, -D, 0)), Vector((W, -D, 0)), Vector((W, D, 0)), Vector((-W, D, 0))]
    r0, r1 = Vector((-R, 0, h)), Vector((R, 0, h))
    hips = []
    _, h1 = _slope(bm, c[0], c[1], r0, r1, lift, tiles)       # 前坡
    _slope(bm, c[2], c[3], r1, r0, lift, tiles)               # 後坡
    if hip:
        _slope(bm, c[1], c[2], r1, r1, lift, tiles)           # 側坡（三角）
        _slope(bm, c[3], c[0], r0, r0, lift, tiles)
        prof = lambda v: h * v * (.32 + .68 * v) + lift * (1 - v) ** 2
        for cc, rr in ((c[0], r0), (c[1], r1), (c[2], r1), (c[3], r0)):
            hips.append([Vector((cc.x + (rr.x - cc.x) * v, cc.y + (rr.y - cc.y) * v, prof(v))) for v in (i / 8 for i in range(9))])
    return _finish_roof(name, bm, m, thick, hips, (r0.copy(), r1.copy()), loc, rz, .16 if thick < .3 else .2)

def pyramid_roof(name, n, rad, h, loc, m, lift=.5, a0=0.0, tiles=.045, thick=.13):
    """攢尖頂（亭子）：n 邊形，角在 a0 + k·2π/n。"""
    bm = bmesh.new()
    cs = [Vector((rad * math.cos(a0 + k * math.tau / n), rad * math.sin(a0 + k * math.tau / n), 0)) for k in range(n)]
    ap = Vector((0, 0, h))
    for k in range(n):
        _slope(bm, cs[k], cs[(k + 1) % n], ap, ap, lift, tiles, nv=10)
    hips = [[Vector((cc.x * (1 - i / 8), cc.y * (1 - i / 8), h * (i / 8) * (.32 + .68 * i / 8) + lift * (1 - i / 8) ** 2))
             for i in range(9)] for cc in cs]
    return _finish_roof(name, bm, m, thick, hips, None, loc, 0, .13)

def gable(name, D, h, wd, xo, loc, m):
    """兩坡頂（脊沿 X）兩端的山牆：在 x=±xo、寬 ±wd，上緣貼著屋頂的凹曲線往下一點。"""
    bm = bmesh.new(); n = 12
    for s in (-1, 1):
        c = bm.verts.new((s * xo, 0, 0))
        top = [bm.verts.new((s * xo, y, max(0, h * (1 - abs(y) / D) * (.32 + .68 * (1 - abs(y) / D)) - .06)))
               for y in (-wd + 2 * wd * i / n for i in range(n + 1))]
        for a, b in zip(top, top[1:]):
            bm.faces.new((c, a, b) if s > 0 else (c, b, a))
    return obj_from_bm(name, bm, m, loc)

# ---------- 建築零件 ----------
def column(name, x, y, z0, hgt, r, m=None, base=True):
    """柱：微收分的圓柱＋石柱礎。"""
    ps = [lathe(name, [(0, 0), (r * 1.04, 0), (r, hgt * .5), (r * .9, hgt), (0, hgt)], (x, y, z0), m or M['pillar'], 14)]
    if base:
        ps.append(lathe(name + '_礎', [(0, 0), (r * 1.7, 0), (r * 1.7, .08), (r * 1.35, .2), (0, .2)], (x, y, z0 - .02), M['stoneD'], 14))
    return ps

def window(name, w, hh, loc, rz, n=5):
    """直櫺窗：木框＋窗紙＋直櫺，面朝本地 -Y。"""
    ps = [box(name + '_紙', (w, .04, hh), (0, 0, 0), M['paper'], bv=0)]
    for dx, dz, sw, sh in ((0, hh / 2, w + .16, .1), (0, -hh / 2, w + .16, .1), (-w / 2, 0, .1, hh), (w / 2, 0, .1, hh)):
        ps.append(box(name + '_框', (sw, .12, sh), (dx, -.03, dz), M['lattice']))
    for i in range(1, n):
        ps.append(box(name + '_櫺', (.05, .08, hh), (-w / 2 + i * w / n, -.04, 0), M['lattice'], bv=0))
    o = join(ps, name, origin=(0, 0, 0))
    return place(o, loc, rz)

def door(name, w, hh, loc, rz, m=None):
    """板門：木框、兩扇門板與門釘，底邊在 loc 高度，面朝本地 -Y。"""
    m = m or M['wood']
    ps = [box(name + '_框上', (w + .3, .16, .14), (0, 0, hh + .07), M['lattice']),
          box(name + '_框左', (.14, .16, hh), (-w / 2 - .08, 0, hh / 2), M['lattice']),
          box(name + '_框右', (.14, .16, hh), (w / 2 + .08, 0, hh / 2), M['lattice'])]
    for s in (-1, 1):
        ps.append(box(name + '_扇', (w / 2 - .02, .06, hh - .02), (s * w / 4, .02, hh / 2), m))
        for i in range(3):
            for j in range(2):
                ps.append(sphere(name + '_釘', .025, (s * w / 4 + (j - .5) * w * .2, -.02, hh * (.3 + i * .2)), M['shoe'], 6))
    o = join(ps, name, origin=(0, 0, 0))
    return place(o, loc, rz)

def stairs(name, w, depth, hh, n, loc, rz, m):
    """台階：n 級，從 loc（台階前緣、地面）往本地 +Y 升到 hh。"""
    ps = []
    for i in range(n):
        d = depth * (n - i) / n
        ps.append(box(name + '_%d' % i, (w, d, hh * (i + 1) / n), (0, depth - d / 2, hh * (i + 1) / n / 2), m))
    o = join(ps, name, origin=(0, 0, 0))
    return place(o, loc, rz)

def balustrade(name, pts, hh, m, post=.18, gap=1.4):
    """石欄杆：望柱＋上下欄板，沿 pts（Blender 座標、同一高度）。"""
    ps = []
    for a, b in zip(pts, pts[1:]):
        L = (b - a).length; n = max(1, round(L / gap))
        d = (b - a).normalized(); ang = math.atan2(d.y, d.x)
        for i in range(n + 1):
            p = a.lerp(b, i / n)
            ps.append(box(name + '_柱', (post, post, hh + .15), p + Vector((0, 0, (hh + .15) / 2)), m))
            ps.append(sphere(name + '_柱頭', post * .6, p + Vector((0, 0, hh + .2)), m, 8))
        mid = (a + b) / 2
        for z, th in ((hh - .04, .09), (.12, .08)):
            ps.append(box(name + '_欄', (L, .1, th), mid + Vector((0, 0, z)), m, ang))
        ps.append(box(name + '_板', (L, .06, hh - .3), mid + Vector((0, 0, hh / 2 + .04)), m, ang, bv=0))
    return ps

# ---------- 地面、河、路、田 ----------
g = box('地面', (420, 420, .2), (0, 0, -.1), M['ground'], bv=0)

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

RIVER = [(36, -120), (34, -60), (30, -30), (33, -6), (33, 6), (30, 26), (34, 60), (40, 120)]
RIVER_S = smooth_path(RIVER)
join([strip('泗水_面', RIVER_S, 7.5, .03, M['water']), strip('泗水_岸', RIVER_S, 9.6, .02, M['bank'])], '泗水')

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
    fields.append(box('田_%d' % i, (w - .5, d - .5, .06), T(x, z, .03), M['field'], bv=0))
    for k in range(int((d - 1) / .55)):                 # 田壟：一行行隆起
        fields.append(tube('壟_%d_%d' % (i, k), [T(x - w / 2 + .5, z - d / 2 + .6 + k * .55, .07), T(x + w / 2 - .5, z - d / 2 + .6 + k * .55, .07)],
                           .07, M['furrow'], 5, True, False, .6))
join(fields, '田畦')

# ---------- 陬邑故居（夯土茅屋＋籬笆＋井） ----------
hx, hz = -28, 8
parts = [box('故居_牆', (6, 4.4, 2.6), T(hx, hz, 1.3), M['earth']),
         box('故居_基', (6.4, 4.8, .25), T(hx, hz, .12), M['stoneD']),
         door('故居_門', 1.0, 1.85, T(hx, hz + 2.22, 0), 0),
         window('故居_窗1', .9, .7, T(hx - 1.8, hz + 2.22, 1.5), 0, 6),
         window('故居_窗2', .9, .7, T(hx + 1.8, hz + 2.22, 1.5), 0, 6),
         gable('故居_山牆', 2.8, 1.9, 2.2, 2.99, T(hx, hz, 2.6), M['earth']),
         roof('故居_頂', 3.7, 2.8, 1.9, T(hx, hz, 2.6), M['thatch'], lift=0, hip=False, tiles=0, thick=.32)]
# 籬笆：尖頭木樁＋兩道橫木，南側留門口
FN = 26; post_pts = {}
for i in range(FN):
    if i in (6, 7): continue
    a = i / FN * math.tau
    p = T(hx + math.cos(a) * 6.5, hz + 2 + math.sin(a) * 5)
    post_pts[i] = p
    parts.append(cone('籬_%d' % i, .07, .07, .95, p, M['wood'], 6, False))
    parts.append(cone('籬尖_%d' % i, .07, .0, .18, p + Vector((0, 0, .95)), M['wood'], 6, False))
for i in range(FN):
    j = (i + 1) % FN
    if i in post_pts and j in post_pts:
        for zz in (.35, .75):
            parts.append(tube('籬橫', [post_pts[i] + Vector((0, 0, zz)), post_pts[j] + Vector((0, 0, zz))], .035, M['wood'], 5))
# 井：石井欄、轆轤架、水桶
wx, wz = hx + 4, hz + 4.5
parts.append(lathe('井', [(0, .3), (.55, .3), (.55, 0), (.75, 0), (.78, .7), (.7, .78), (.55, .74), (0, .74)], T(wx, wz), M['stone'], 20))
for s in (-1, 1):
    parts.append(box('井架', (.12, .12, 1.7), T(wx + s * .62, wz, .85), M['wood']))
parts.append(tube('井軸', [T(wx - .7, wz, 1.45), T(wx + .7, wz, 1.45)], .07, M['wood'], 8))
parts.append(tube('井繩', [T(wx + .1, wz, 1.4), T(wx + .1, wz, .95)], .015, M['bamboo'], 4))
parts.append(lathe('井桶', [(0, 0), (.13, 0), (.16, .25), (0, .25)], T(wx + .1, wz, .7), M['wood'], 10))
join(parts, '陬邑故居')

# ---------- 倉廩（委吏） ----------
gx, gz = -19, 17
join([lathe('倉_身', [(0, 0), (2.0, 0), (2.08, 1.2), (2.0, 2.8), (0, 2.8)], T(gx, gz), M['earth'], 28),
      lathe('倉_箍', [(2.06, .9), (2.12, .95), (2.12, 1.05), (2.06, 1.1)], T(gx, gz), M['wood'], 28, False),
      lathe('倉_箍2', [(2.04, 2.1), (2.1, 2.15), (2.1, 2.25), (2.04, 2.3)], T(gx, gz), M['wood'], 28, False),
      lathe('倉_頂', [(0, 0), (2.75, 0), (2.7, .12), (1.6, .9), (.6, 1.65), (.15, 2.05), (0, 2.1)], T(gx, gz, 2.7), M['thatch'], 28, True, wob=.04),
      lathe('倉_頂尖', [(0, 0), (.22, 0), (.14, .25), (.06, .45), (0, .5)], T(gx, gz, 4.75), M['thatch'], 10),
      door('倉_門', .8, 1.5, T(gx, gz + 2.02, 0), 0)], '倉廩')

# ---------- 書齋（整理典籍、問禮） ----------
sx, sz = -12, -13
sp = [box('書齋_台', (8, 6, .5), T(sx, sz, .25), M['stone']),
      box('書齋_台緣', (8.2, 6.2, .08), T(sx, sz, .49), M['stoneD']),
      box('書齋_後牆', (7, .4, 3), T(sx, sz - 2.4, 2), M['earth']),
      box('書齋_左牆', (.4, 4.8, 3), T(sx - 3.3, sz, 2), M['earth']),
      box('書齋_右牆', (.4, 4.8, 3), T(sx + 3.3, sz, 2), M['earth']),
      box('書齋_額枋', (7.2, .3, .35), T(sx, sz + 2.4, 3.3), M['wood']),
      window('書齋_窗L', 2.2, 1.0, T(sx - 3.52, sz - .2, 2.1), -math.pi / 2, 9),
      window('書齋_窗R', 2.2, 1.0, T(sx + 3.52, sz - .2, 2.1), math.pi / 2, 9),
      roof('書齋_頂', 4.6, 3.6, 2.0, T(sx, sz, 3.48), M['tile'], lift=.45)]
sp += column('書齋_柱1', *T(sx - 3.3, sz + 2.4)[:2], .5, 3.0, .17)
sp += column('書齋_柱2', *T(sx + 3.3, sz + 2.4)[:2], .5, 3.0, .17)
for k in range(3):                                    # 書架與成捆竹簡
    sp.append(box('書架_%d' % k, (2.2, .5, .06), T(sx + 1.5, sz - 1.95, .9 + k * .55), M['wood']))
    for q in range(6):
        b = cone('架簡', .09, .09, .5, T(sx + .65 + q * .32, sz - 1.95, .93 + k * .55 + .09), M['bamboo'], 8)
        b.rotation_euler.x = math.pi / 2; apply(b); sp.append(b)
for s in (-1, 1):
    sp.append(box('書架_側', (.06, .5, 1.75), T(sx + 1.5 + s * 1.1, sz - 1.95, 1.37), M['wood']))
join(sp, '書齋')
desk = [box('書案_面', (2.2, .9, .1), T(sx, sz - .6, 1.0), M['wood']),
        box('書案_翹1', (.12, .9, .08), T(sx - 1.1, sz - .6, 1.08), M['wood']),
        box('書案_翹2', (.12, .9, .08), T(sx + 1.1, sz - .6, 1.08), M['wood'])]
for s in (-1, 1):
    desk.append(box('書案_腳', (.1, .75, .42), T(sx + s * .95, sz - .6, .74), M['wood']))
    desk.append(box('書案_足', (.16, .9, .06), T(sx + s * .95, sz - .6, .53), M['wood']))
join(desk, '書案')
slips = []
for i in range(7):                                    # 攤開的竹簡：一片片並排，兩道編繩
    for q in range(9):
        c = box('簡_%d_%d' % (i, q), (.035, .62, .012), T(sx - .9 + i * .3 + q * .036, sz - .55 + (i % 2) * .08, 1.06), M['bamboo'], bv=0)
        slips.append(c)
    for yy in (-.18, .18):
        slips.append(box('簡繩', (.33, .02, .016), T(sx - .9 + i * .3 + .144, sz - .55 + (i % 2) * .08 + yy, 1.068), M['wood'], bv=0))
for i in range(5):                                    # 成捆的竹簡
    c = lathe('簡捆_%d' % i, [(0, 0), (.12, 0), (.13, .35), (.12, .7), (0, .7)], T(sx + 2.2, sz - 1.6 + i * .27, .63), M['bamboo'], 10)
    c.rotation_euler.y = math.pi / 2; apply(c); slips.append(c)
join(slips, '竹簡')

# ---------- 杏壇 ----------
ax, az = 0, 2
ap = [box('杏壇_座', (9.6, 9.6, .16), T(ax, az, .08), M['stoneD']),
      box('杏壇_台', (9, 9, .6), T(ax, az, .43), M['stone']),
      box('杏壇_腰', (8.8, 8.8, .08), T(ax, az, .3), M['stoneD'], bv=0),
      box('杏壇_緣', (9.4, 9.4, .18), T(ax, az, .79), M['stoneD']),
      stairs('杏壇_階', 3, 1.1, .88, 3, T(ax, az + 5.6, 0), 0, M['stoneD'])]   # z=7.6 升到台面（main.html 的 groundY 同步成斜坡）
for i in range(8):
    a = i / 8 * math.tau + .2
    ap.append(box('坐席_%d' % i, (1.0, 1.0, .05), T(ax + math.cos(a) * 2.8, az + .6 + math.sin(a) * 2.8, .9), M['cloth'], a, bv=.02))
for k in range(4):                                    # 台面石板縫
    ap.append(box('杏壇_縫x', (9, .03, .012), T(ax, az - 4.5 + (k + 1) * 1.8, .885), M['stoneD'], bv=0))
    ap.append(box('杏壇_縫z', (.03, 9, .012), T(ax - 4.5 + (k + 1) * 1.8, az, .885), M['stoneD'], bv=0))
join(ap, '杏壇')
qin = [box('琴_几', (1.2, .4, .05), T(ax, az - 1.3, 1.14), M['wood'])]
for s in (-1, 1):
    qin.append(box('琴_几腳', (.06, .36, .26), T(ax + s * .52, az - 1.3, 1.0), M['wood']))
body = lathe('琴_身', [(0, 0), (.13, 0), (.14, .05), (.12, .085), (0, .09)], (0, 0, 0), M['wood'], 16, sc=(1, 1, 1))
body.scale = (5.0, 1, 1); apply(body); qin.append(place(body, T(ax, az - 1.3, 1.165)))
for k in range(7):
    qin.append(tube('琴弦', [T(ax - .6, az - 1.39 + k * .028, 1.26), T(ax + .58, az - 1.39 + k * .028, 1.26)], .004, M['string'], 3, True, False))
join(qin, '琴')

def branchy(name, x, z, h, spread, m_leaf, n_cl, cl_r, seed):
    """有枝幹的闊葉樹（杏、宋國大樹）：彎曲主幹分出幾枝，枝端掛團狀樹冠。"""
    rnd = random.Random(seed); base = T(x, z)
    trunk = [base, base + Vector((.1, .05, h * .35)), base + Vector((-.15, .1, h * .7)), base + Vector((0, 0, h))]
    ps = [tube(name + '_幹', trunk, [h * .1, h * .08, h * .065, h * .05], M['bark'], 10)]
    tips = []
    for i in range(5):
        a = i / 5 * math.tau + rnd.uniform(-.3, .3)
        st = trunk[2].lerp(trunk[3], rnd.uniform(0, 1))
        d = Vector((math.cos(a), math.sin(a), 0))
        mid = st + d * spread * .45 + Vector((0, 0, h * .25))
        tip = st + d * spread * rnd.uniform(.75, .95) + Vector((0, 0, h * rnd.uniform(.25, .45)))
        ps.append(tube(name + '_枝', [st, mid, tip], [h * .04, h * .025, h * .012], M['bark'], 7))
        tips += [tip, mid]
    tips.append(trunk[-1] + Vector((0, 0, h * .2)))
    for i in range(n_cl):
        c = tips[i % len(tips)] + Vector((rnd.uniform(-.6, .6), rnd.uniform(-.6, .6), rnd.uniform(-.1, .5)))
        ps.append(blob(name + '_冠', cl_r * rnd.uniform(.7, 1.15), c, m_leaf, (1, 1, .72), .3, 2, seed * 10 + i))
    return join(ps, name)

branchy('杏樹', ax - 3.6, az - 3.4, 3.6, 3.0, M['blossom'], 15, 1.1, 3)

# ---------- 魯國朝堂 ----------
px, pz = 12, -17
pp = [box('朝堂_座', (19.6, 12.6, .3), T(px, pz, .15), M['stoneD']),
      box('朝堂_台', (19, 12, 1.3), T(px, pz, .95), M['stone']),
      box('朝堂_腰', (18.8, 11.8, .1), T(px, pz, .55), M['stoneD'], bv=0),
      box('朝堂_緣', (19.3, 12.3, .14), T(px, pz, 1.53), M['stoneD']),
      stairs('朝堂_階', 4.6, 3.4, 1.6, 8, T(px, pz + 9.4, 0), 0, M['stoneD']),   # z=-7.6 升到 -11 的台面
      box('朝堂_牆', (12, 6, 4.2), T(px, pz - .4, 3.7), M['earth']),
      box('朝堂_額枋', (13.4, .4, .5), T(px, pz + 3.2, 5.55), M['pillar']),
      box('朝堂_平板枋', (13.6, .5, .18), T(px, pz + 3.2, 5.88), M['wood'])]
for i in range(8):
    pp += column('朝堂_柱%d' % i, *T(px - 6.3 + i * 1.8, pz + 3.2)[:2], 1.6, 4.2, .24)
    pp.append(box('朝堂_斗拱%d' % i, (.6, .6, .22), T(px - 6.3 + i * 1.8, pz + 3.2, 6.05), M['wood']))
for i in range(7):                                    # 柱間的格扇門
    xx = px - 5.4 + i * 1.8
    pp.append(window('朝堂_格扇%d' % i, 1.3, 3.1, T(xx, pz + 2.62, 3.3), 0, 6))
eb = pz + 6                                            # 台前石欄，中間留台階口
pp += balustrade('朝堂_欄', [T(px - 9.3, eb, 1.6), T(px - 2.8, eb, 1.6)], .75, M['stone'])
pp += balustrade('朝堂_欄', [T(px + 2.8, eb, 1.6), T(px + 9.3, eb, 1.6)], .75, M['stone'])
pp.append(roof('朝堂_頂', 8.6, 5.4, 3.4, T(px, pz, 5.95), M['tile'], lift=.7))
join(pp, '魯國朝堂')

# ---------- 魯城牆與城門 ----------
wall = []
for z0, z1 in [(-38, 3), (9, 42)]:
    wall.append(box('城牆_%d' % z0, (2.6, z1 - z0, 4.6), T(24, (z0 + z1) / 2, 2.3), M['earth']))
    wall.append(box('城牆頂_%d' % z0, (2.9, z1 - z0, .2), T(24, (z0 + z1) / 2, 4.7), M['stoneD']))
    for k in range(int((z1 - z0) / 1.6)):              # 垛口
        zz = z0 + .8 + k * 1.6
        wall.append(box('垛', (.35, .9, .6), T(22.85, zz, 5.1), M['stoneD']))
    for lv in range(1, 5):
        wall.append(box('夯層', (2.64, z1 - z0, .04), T(24, (z0 + z1) / 2, lv * .92), M['stoneD'], bv=0))
join(wall, '魯城牆')
gt = [box('城門_台', (3.2, 7.4, 1.2), T(24, 6, 5.2), M['earth']),
      box('城門_台緣', (3.5, 7.7, .16), T(24, 6, 5.85), M['stoneD']),
      box('城門_樓', (2.4, 4.8, 2.0), T(24, 6, 6.95), M['wood']),
      box('城門_額', (2.9, 5.4, .3), T(24, 6, 7.85), M['pillar'])]
for dz in (-2.5, -1.25, 0, 1.25, 2.5):
    for dx in (-1.35, 1.35):
        gt += column('城門_柱', *T(24 + dx, 6 + dz)[:2], 5.93, 1.95, .1, base=False)
for dz in (-1.8, 0, 1.8):
    gt.append(window('城門_窗', .9, .8, T(22.79, 6 + dz, 7.0), -math.pi / 2, 5))
gt.append(roof('城門_頂', 3.6, 2.2, 1.6, T(24, 6, 8.0), M['tile'], lift=.45, rz=math.pi / 2))
join(gt, '魯城門')

# ---------- 石橋 ----------
br = [box('橋_面', (9, 3.2, .4), T(33, 6, .75), M['stone'])]
for s, zz in ((-1, 4.5), (1, 7.5)):
    br.append(box('橋_欄', (9, .2, .14), T(33, zz, 1.38), M['stoneD']))
    br.append(box('橋_欄板', (9, .1, .35), T(33, zz, 1.13), M['stoneD'], bv=0))
    for k in range(7):
        br.append(box('橋_望柱', (.24, .24, .7), T(28.6 + k * 1.47, zz, 1.25), M['stoneD']))
        br.append(sphere('橋_柱頭', .14, T(28.6 + k * 1.47, zz, 1.65), M['stoneD'], 8))
    # 拱：橋側的拱圈（只是外觀，地面以下被地面蓋住）
    arch = lathe('橋_拱', [(2.6, 0), (2.9, 0), (2.9, .25), (2.6, .25)], (0, 0, 0), M['stone'], 28, False)
    arch.rotation_euler.x = math.pi / 2; apply(arch)
    br.append(place(arch, T(33, zz - .125, -2.05)))
join(br, '石橋')

# ---------- 周遊列國：匡邑、宋國大樹、鄭國東門、陳蔡之亭 ----------
kx, kz = 47, -6
kp = []
for (dx, dz, w, d) in [(0, -4, 9, .6), (0, 4, 9, .6), (-4.5, 0, .6, 8.6), (4.5, -2.4, .6, 3.8)]:
    kp.append(box('匡_牆', (w, d, 2.0), T(kx + dx, kz + dz, 1.0), M['earth']))
    kp.append(roof('匡_牆帽', max(w, d) / 2 + .15, .45, .25, T(kx + dx, kz + dz, 2.0), M['thatch'], 0, 0 if w > d else math.pi / 2, False, 0, .1))
for dx, dz in [(-1.8, -1.5), (1.8, 1.2)]:
    kp.append(box('匡_屋', (2.6, 2.2, 1.8), T(kx + dx, kz + dz, .9), M['earth']))
    kp.append(door('匡_門', .7, 1.3, T(kx + dx, kz + dz + 1.11, 0), 0))
    kp.append(gable('匡_山牆', 1.4, 1.0, 1.1, 1.29, T(kx + dx, kz + dz, 1.8), M['earth']))
    kp.append(roof('匡_頂', 1.6, 1.4, 1.0, T(kx + dx, kz + dz, 1.8), M['thatch'], lift=0, hip=False, tiles=0, thick=.22))
join(kp, '匡邑')
branchy('宋國大樹', 55.5, 13.5, 4.4, 4.2, M['leaf'], 20, 1.45, 9)
# 鄭國東門：城牆、城門洞、門樓。先在本地座標建（城牆沿 X、道路沿 Y），再轉到道路方向
gp = []
for sx_ in (-1, 1):
    gp.append(box('鄭門_牆', (6.8, 3.2, 5.2), (sx_ * 5.6, 0, 2.6), M['earth']))
    gp.append(box('鄭門_牆頂', (6.8, 3.5, .3), (sx_ * 5.6, 0, 5.35), M['stoneD']))
    for lv in range(1, 5):
        gp.append(box('鄭門_夯層', (6.84, 3.24, .04), (sx_ * 5.6, 0, lv * 1.04), M['stoneD'], bv=0))
    for k in range(5):
        gp.append(box('鄭門_垛', (.7, .4, .55), (sx_ * (3.0 + k * 1.35), 1.55, 5.75), M['stoneD']))
    leaf = [box('鄭門_門扇', (1.9, .16, 3.3), (0, 0, 1.65), M['wood'])]   # 門扇向內打開、貼著門洞兩側
    for i in range(5):
        for j in range(4):
            leaf.append(sphere('鄭門_門釘', .05, (-.65 + j * .43, -.09, .6 + i * .55), M['shoe'], 6))
    dr = join(leaf, '鄭門_門扇', origin=(0, 0, 0))
    gp.append(place(dr, (sx_ * 2.0, -2.6, 0), sx_ * math.radians(88)))
    gp.append(cone('鄭門_旗桿', .06, .05, 3.0, (sx_ * 7.6, 1.2, 5.5), M['wood'], 6))
    gp.append(box('鄭門_旗', (1.1, .05, .8), (sx_ * 7.6 + .58, 1.2, 8.0), M['pillar'], bv=.01))
gp.append(box('鄭門_洞頂', (4.4, 3.2, 1.6), (0, 0, 4.4), M['earth']))
gp.append(box('鄭門_牆頂中', (4.4, 3.5, .3), (0, 0, 5.35), M['stoneD']))
gp.append(box('鄭門_樓身', (6.2, 2.6, 2.2), (0, 0, 6.65), M['wood']))
gp.append(box('鄭門_額枋', (7.0, 3.3, .28), (0, 0, 7.75), M['pillar']))
for k in range(5):
    for yy in (-1.55, 1.55):
        gp += column('鄭門_樓柱', -3.0 + k * 1.5, yy, 5.55, 2.2, .13, base=False)
gp.append(window('鄭門_窗', 1.2, .9, (0, -1.32, 6.7), 0, 6))
gp += balustrade('鄭門_欄', [Vector((-3.6, -1.62, 5.5)), Vector((3.6, -1.62, 5.5))], .45, M['wood'], .12, 1.2)
gp.append(roof('鄭門_頂', 4.4, 2.5, 1.9, (0, 0, 7.88), M['tile'], lift=.55))
gate = join(gp, '鄭國東門', origin=(0, 0, 0))
gate.rotation_euler.z = math.radians(-45); gate.location = T(57.3, 5.7)

# 陳蔡之亭：六角亭，平邊朝北（three +z）當入口
cx, cz = 64.5, -9
pv = [cone('亭_台', 3.3, 3.3, .45, T(cx, cz), M['stone'], 6, False),
      cone('亭_台緣', 3.42, 3.42, .1, T(cx, cz, .38), M['stoneD'], 6, False),
      box('亭_階', (2.2, .9, .22), T(cx, cz + 3.25, .11), M['stoneD']),
      cone('亭_梁', 3.0, 3.0, .28, T(cx, cz, 3.0), M['pillar'], 6, False),
      lathe('亭_几', [(0, 0), (.25, 0), (.18, .2), (.42, .3), (.42, .36), (0, .36)], T(cx, cz, .45), M['wood'], 6, False),
      lathe('亭_碗', [(0, 0), (.1, 0), (.2, .12), (.18, .13), (0, .03)], T(cx, cz, .81), M['stoneD'], 12)]
for k in range(6):
    a = k * math.pi / 3
    pv += column('亭_柱', cx + 2.75 * math.cos(a), -cz + 2.75 * math.sin(a), .45, 2.6, .15)
    pv.append(box('亭_雀替', (.9, .1, .22), Vector((cx + 2.75 * math.cos(a), -cz + 2.75 * math.sin(a), 2.92)), M['wood'], a + math.pi / 2))
pv.append(pyramid_roof('亭_頂', 6, 3.9, 2.2, T(cx, cz, 3.25), M['tile'], lift=.55))
pv.append(lathe('亭_寶頂', [(0, 0), (.3, 0), (.32, .15), (.2, .3), (.28, .45), (.12, .7), (.05, .95), (0, 1.0)], T(cx, cz, 5.4), M['tile'], 12))
for o in (pv[0], pv[1], pv[3]): o.rotation_euler.z = math.radians(30)   # 台基、梁的六角與柱子、屋頂對齊，平邊朝入口
join(pv, '陳蔡之亭')

# ---------- 孔子墓（孔林）與子貢廬 ----------
mx, mz = -31, -25
join([lathe('墓_丘', [(0, 0), (3.7, 0), (3.5, .45), (2.8, 1.25), (1.6, 1.8), (0, 2.0)], T(mx, mz), M['grave'], 32, wob=.05),
      lathe('墓_基', [(0, 0), (3.85, 0), (3.85, .22), (0, .22)], T(mx, mz), M['stoneD'], 32, False)], '孔子墓')
join([box('碑_身', (1.0, .28, 2.0), T(mx, mz + 4.6, 1.15), M['stone']),
      lathe('碑_首', [(0, 0), (.5, 0), (.5, .12), (.3, .32), (0, .38)], T(mx, mz + 4.6, 2.12), M['stone'], 16, sc=(1, .28, 1)),
      box('碑_座', (1.5, .7, .2), T(mx, mz + 4.6, .1), M['stoneD']),
      box('碑_座2', (1.25, .55, .12), T(mx, mz + 4.6, .25), M['stoneD']),
      box('供案', (1.4, .6, .5), T(mx, mz + 3.6, .25), M['stone'])], '墓碑')
join([box('廬_牆', (2.6, 2.2, 1.8), T(mx + 7, mz + 1, .9), M['earth']),
      door('廬_門', .7, 1.3, T(mx + 7, mz + 2.11, 0), 0),
      gable('廬_山牆', 1.4, 1.1, 1.1, 1.29, T(mx + 7, mz + 1, 1.8), M['earth']),
      roof('廬_頂', 1.7, 1.4, 1.1, T(mx + 7, mz + 1, 1.8), M['thatch'], lift=0, hip=False, tiles=0, thick=.22)], '子貢廬')
# ---------- 松、柳 ----------
def pine(x, z, h, seed):
    """雲片松：彎曲主幹＋橫伸的枝，枝端是扁平的針葉雲片（古畫常見的畫法）。"""
    rnd = random.Random(seed); base = T(x, z)
    lean = Vector((rnd.uniform(-.5, .5), rnd.uniform(-.5, .5), 0))
    trunk = [base + lean * (k / 4) ** 2 * 1.5 + Vector((rnd.uniform(-.15, .15), rnd.uniform(-.15, .15), h * k / 4)) for k in range(5)]
    trunk[0] = base
    ps = [tube('松幹', trunk, [.26, .2, .15, .11, .06], M['bark'], 8)]
    ps.append(blob('松頂', h * .2, trunk[-1] + Vector((0, 0, .25)), M['pine'], (1, 1, .38), .3, 2, seed))
    for i in range(4):
        y = .45 + i * .13
        st = trunk[1].lerp(trunk[4], (y - .25) / .75)
        a = i * 2.4 + rnd.uniform(-.4, .4); L = h * (.34 - i * .05)
        d = Vector((math.cos(a), math.sin(a), 0))
        tip = st + d * L + Vector((0, 0, h * .06))
        ps.append(tube('松枝', [st, st.lerp(tip, .5) + Vector((0, 0, h * .05)), tip], [.09, .06, .03], M['bark'], 6))
        ps.append(blob('松片', L * .62, tip + Vector((0, 0, .15)), M['pine'], (1, 1, .32), .3, 2, seed * 7 + i))
    return ps

PINES = [(-36, -30), (-26, -32), (-38, -20), (-24, -19), (-34, -14), (-44, -26), (-20, -28),
         (-6, -24), (2, -26), (-18, 4), (2, -9), (20, -30), (-48, 0), (-46, 22), (-14, 28),
         (16, 22), (6, 30), (42, 18), (44, -16), (52, -18), (60, 18), (68, 6), (70, -26), (76, -14),
         (58, -24), (-56, -12), (-60, 30), (28, -46), (-10, -40), (12, -40)]
# 封面（半徑 27.5）與「一生」頁（半徑 19.2）的環繞鏡頭繞著杏壇轉：這一圈帶狀範圍內不放松樹，往外推
pp = []
for k, (x, z) in enumerate(PINES):
    x += random.uniform(-1, 1); z += random.uniform(-1, 1)
    d = math.hypot(x, z - 1.5)
    if 13 < d < 34:
        x, z = x * 34 / d, 1.5 + (z - 1.5) * 34 / d
    pp += pine(x, z, random.uniform(5, 8.5), k + 1)
join(pp, '松林')
wl = []
for k, (x, z) in enumerate([(29, -22), (29, 16), (37.5, -10), (37, 18), (27, 34), (38, 40), (27, -40)]):
    rnd = random.Random(100 + k); b = T(x, z)
    top = b + Vector((rnd.uniform(-.4, .4), rnd.uniform(-.4, .4), 3.3))
    wl.append(tube('柳幹', [b, b + Vector((.15, 0, 1.6)), top], [.3, .2, .13], M['bark'], 8))
    wl.append(blob('柳冠', 1.3, top + Vector((0, 0, .3)), M['willow'], (1, 1, .55), .25, 2, k + 50))
    for i in range(22):                                # 垂下的柳條
        a = i / 22 * math.tau + rnd.uniform(-.1, .1); r0 = rnd.uniform(.6, 1.3)
        p0 = top + Vector((math.cos(a) * r0, math.sin(a) * r0, rnd.uniform(0, .4)))
        out = Vector((math.cos(a), math.sin(a), 0))
        L = rnd.uniform(1.6, 2.5)
        pts = [p0 + out * (.6 * math.sin(t * 1.4)) + Vector((0, 0, -L * t * t)) for t in (0, .3, .6, .85, 1.0)]
        wl.append(tube('柳條', pts, [.07, .06, .05, .04, .02], M['willow'], 4, True, False))
join(wl, '柳')

# 山石：河岸與山腳點綴，離走位路線遠一點
rocks = []
rr = random.Random(21)
for i in range(46):
    t = rr.uniform(0, 1); p = Vector(RIVER_S[int(t * (len(RIVER_S) - 1))])
    if abs(p.y - 6) < 6 or abs(p.y) > 70: continue
    side = rr.choice((-1, 1))
    rocks.append(blob('河石', rr.uniform(.35, .8), T(p.x + side * rr.uniform(4.0, 5.2), p.y + rr.uniform(-1, 1), .05), M['rock'], (1, 1, .55), .35, 1, i))
for (x, z) in [(-40, -32), (-30, -36), (-46, -16), (4, -32), (18, -36), (46, -24), (70, -16), (74, 2), (-52, 28), (-20, 32), (10, 26), (50, 22)]:
    for q in range(3):
        rocks.append(blob('山石', rr.uniform(.5, 1.3), T(x + rr.uniform(-2, 2), z + rr.uniform(-2, 2), .1), M['rock'], (1, rr.uniform(.7, 1), .6), .35, 1, 200 + len(rocks)))
join(rocks, '山石')

# ---------- 遠山（層層疊疊，越遠越淡由霧處理） ----------
def mountain(name, x, z, w, d, h, m, peaks=3, seed=0):
    rnd = random.Random(seed); N = 32
    bm = bmesh.new(); grid = []
    pk = [(rnd.uniform(-.5, .5), rnd.uniform(-.3, .3), rnd.uniform(.55, 1.0)) for _ in range(peaks)]
    off = Vector((seed * 1.3, seed * .7, 0))
    for j in range(N + 1):
        row = []
        for i in range(N + 1):
            u, v = i / N * 2 - 1, j / N * 2 - 1
            hh = 0
            for (px_, py_, ph) in pk:
                dd = math.hypot((u - px_) * 1.6, (v - py_) * 1.2)
                hh = max(hh, ph * math.exp(-dd * dd * 3.2))
            edge = max(0, 1 - max(abs(u), abs(v)) ** 6)
            ridge = 1 - abs(noise.noise(Vector((u * 3, v * 3, 0)) + off))      # 山脊紋：皴法的感覺
            hh = hh * (.82 + .25 * ridge) * edge + .05 * noise.noise(Vector((u * 9, v * 9, 1)) + off) * edge * hh
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
ROBE = [(0, .04), (.41, .04), (.43, .1), (.39, .34), (.34, .6), (.3, .82), (.29, 1.0), (.31, 1.16), (.27, 1.28), (.17, 1.36), (.08, 1.4), (0, 1.4)]
def robe_r(z):
    for (r0, z0), (r1, z1) in zip(ROBE[1:], ROBE[2:]):
        if z0 <= z <= z1: return r0 + (r1 - r0) * (z - z0) / (z1 - z0)
    return .3

def person(name, robe, trim, hat='bun', beard=False, k=1.0):
    """身體為父物件（原點在腳底）；四肢為子物件，原點在關節。面向 Blender -Y。"""
    K = lambda *v: Vector(v) * k
    ey = .82                                            # 身體前後較扁
    front = lambda x, z, d=.012: K(x, -(robe_r(z) * ey + d) * math.sqrt(max(0, 1 - (x / max(robe_r(z), .01)) ** 2 * .9)), z)
    ps = [lathe(name + '_袍', [(r * k, z * k) for r, z in ROBE], (0, 0, 0), robe, 28, sc=(1, ey, 1)),
          lathe(name + '_襬', [(.425 * k, .035 * k), (.44 * k, .06 * k), (.44 * k, .12 * k), (.41 * k, .14 * k)], (0, 0, 0), trim, 28, sc=(1, ey, 1)),
          lathe(name + '_帶', [(.302 * k, .8 * k), (.312 * k, .82 * k), (.312 * k, .88 * k), (.3 * k, .9 * k)], (0, 0, 0), trim, 28, sc=(1, ey, 1)),
          # 交領右衽：外襟從左肩斜到右腰
          tube(name + '_襟', [front(.13, 1.33), front(.07, 1.18), front(-.03, 1.02), front(-.12, .9)], .045 * k, trim, 6, True, True, .3),
          tube(name + '_內襟', [front(-.12, 1.33), front(-.04, 1.22), front(.02, 1.14)], .04 * k, trim, 6, True, True, .3),
          box(name + '_佩', (.07 * k, .03 * k, .34 * k), K(-.06, -(robe_r(.66) * ey + .02), .66), trim, bv=.008),
          lathe(name + '_頸', [(0, 1.34 * k), (.07 * k, 1.34 * k), (.07 * k, 1.46 * k), (0, 1.46 * k)], (0, 0, 0), M['skin'], 12),
          sphere(name + '_頭', .17 * k, K(0, 0, 1.58), M['skin'], 24, (.94, .97, 1.08))]
    for s in (-1, 1):
        ps.append(sphere(name + '_眼', .019 * k, K(s * .055, -.158, 1.6), M['hair'], 8, (1, .6, .8)))
        ps.append(box(name + '_眉', (.06 * k, .02 * k, .014 * k), K(s * .058, -.156, 1.645), M['hair'], bv=0))
        ps.append(sphere(name + '_耳', .035 * k, K(s * .158, .0, 1.58), M['skin'], 8, (.5, 1, 1.3)))
    nose = cone(name + '_鼻', .028 * k, .01 * k, .05 * k, (0, 0, 0), M['skin'], 8)
    nose.rotation_euler.x = math.pi / 2; apply(nose); ps.append(place(nose, K(0, -.155, 1.565)))
    # 髮：只蓋住頭頂與後腦，露出臉
    bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=14, radius=.178 * k)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.y < -.06 * k and v.co.z < .07 * k], context='VERTS')
    bmesh.ops.scale(bm, vec=(.96, 1.0, 1.08), verts=bm.verts)
    ps.append(obj_from_bm(name + '_髮', bm, M['hair'], K(0, .012, 1.6), True))
    if hat == 'guan':
        ps.append(sphere(name + '_髻', .075 * k, K(0, .03, 1.79), M['hair'], 12))
        ps.append(lathe(name + '_冠', [(0, 0), (.07 * k, 0), (.075 * k, .1 * k), (.05 * k, .17 * k), (0, .18 * k)], K(0, .03, 1.78), M['hair'], 12, sc=(.7, 1.6, 1)))
        ps.append(tube(name + '_簪', [K(-.2, .03, 1.86), K(.2, .03, 1.86)], .011 * k, M['bamboo'], 5))
        for s in (-1, 1):
            ps.append(tube(name + '_纓', [K(s * .07, .03, 1.82), K(s * .15, -.02, 1.6), K(s * .1, -.1, 1.42)], .008 * k, M['hair'], 4, True, False))
    elif hat == 'bun':
        ps.append(sphere(name + '_髻', .085 * k, K(0, .05, 1.79), M['hair'], 12))
        ps.append(lathe(name + '_髮帶', [(.088 * k, -.02 * k), (.09 * k, .02 * k)], K(0, .05, 1.76), trim, 12, False))
    elif hat == 'veil':                                 # 頭巾：同髮的做法，露出臉
        bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=14, radius=.2 * k)
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.y < -.07 * k and v.co.z < .09 * k], context='VERTS')
        ps.append(obj_from_bm(name + '_巾', bm, trim, K(0, .02, 1.6), True))
        ps.append(sphere(name + '_髻', .08 * k, K(0, .08, 1.78), trim, 12))
        ps.append(tube(name + '_巾尾', [K(0, .18, 1.62), K(0, .25, 1.4), K(0, .24, 1.2)], [.07 * k, .06 * k, .04 * k], trim, 6, True, True, .3))
    if beard:
        ps.append(tube(name + '_鬚', [K(0, -.13, 1.5), K(0, -.17, 1.38), K(0, -.18, 1.25), K(0, -.15, 1.12)],
                       [.055 * k, .06 * k, .04 * k, .008 * k], M['beard'], 8, True, True, .55))
        for s in (-1, 1):
            ps.append(tube(name + '_髭', [K(0, -.168, 1.535), K(s * .05, -.165, 1.52), K(s * .075, -.14, 1.48)],
                           [.012 * k, .01 * k, .004 * k], M['beard'], 5))
    body = join(ps, name, origin=(0, 0, 0))
    for side, sx_ in (('左', -1), ('右', 1)):
        leg = join([tube(name + '_腿', [K(0, 0, .56), K(0, 0, .1)], .065 * k, M['shoe'], 8),
                    box(name + '_鞋', (.12 * k, .25 * k, .09 * k), K(0, -.04, .045), M['shoe']),
                    tube(name + '_鞋尖', [K(0, -.15, .05), K(0, -.19, .1)], [.04 * k, .02 * k], M['shoe'], 6)],
                   name + '_' + side + '腳', origin=(0, 0, .55 * k))
        leg.location = (sx_ * .11 * k, 0, .55 * k)
        arm = join([lathe(name + '_袖', [(0, .62 * k), (.15 * k, .62 * k), (.17 * k, .68 * k), (.14 * k, .9 * k), (.105 * k, 1.15 * k), (.085 * k, 1.29 * k), (0, 1.34 * k)],
                          (0, 0, 0), robe, 16, sc=(1, 1.3, 1)),
                    lathe(name + '_袖口', [(.152 * k, .6 * k), (.172 * k, .62 * k), (.172 * k, .7 * k), (.15 * k, .7 * k)], (0, 0, 0), trim, 16, False, sc=(1, 1.3, 1)),
                    sphere(name + '_掌', .05 * k, K(0, -.03, .6), M['skin'], 10, (.8, 1, 1.25))],
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
cart = [box('車_廂', (1.4, 1.8, .14), (0, .4, .72), M['wood']),
        box('車_軫', (1.5, 1.9, .1), (0, .4, .64), M['lattice'])]
for sx_ in (-1, 1):                                    # 車欄
    cart.append(box('車_欄', (.06, 1.8, .06), (sx_ * .68, .4, 1.2), M['wood']))
    for q in range(6):
        cart.append(box('車_欄柱', (.05, .05, .42), (sx_ * .68, -.45 + q * .34, .99), M['wood']))
cart.append(box('車_前欄', (1.36, .06, .06), (0, -.48, 1.2), M['wood']))
cart.append(box('車_軾', (1.3, .08, .08), (0, -.2, 1.35), M['wood']))
for sx_ in (-1, 1):                                    # 轅：從車底向前上彎到馬頸
    cart.append(tube('車_轅', [(sx_ * .35, .6, .62), (sx_ * .35, -1.0, .75), (sx_ * .3, -2.4, 1.15), (sx_ * .25, -3.2, 1.75)],
                     .05, M['wood'], 6))
cart.append(tube('車_衡', [(-.5, -3.2, 1.78), (.5, -3.2, 1.78)], .045, M['wood'], 6))
cart.append(tube('車_軸', [(-1.0, .4, .7), (1.0, .4, .7)], .05, M['wood'], 6))
cart.append(cone('車_傘柄', .03, .03, 1.6, (0, .4, .78), M['wood'], 6))
cart.append(lathe('車_傘', [(0, 2.28), (1.3, 2.12), (1.36, 2.14), (1.0, 2.3), (.5, 2.42), (0, 2.46)], (0, .4, 0), M['tile'], 20))
for q in range(10):                                    # 傘骨
    a = q / 10 * math.tau
    cart.append(tube('車_傘骨', [(0, .4, 2.28), (math.cos(a) * 1.3, .4 + math.sin(a) * 1.3, 2.1)], .012, M['wood'], 4))
for dx in (-.85, .85):                                 # 車輪：輪輞、輻條、轂
    rim = lathe('車_輪', [(.62, -.05), (.7, -.05), (.7, .05), (.62, .05)], (0, 0, 0), M['shoe'], 28, False)
    hub = lathe('車_轂', [(0, -.16), (.1, -.16), (.13, 0), (.1, .16), (0, .16)], (0, 0, 0), M['wood'], 10)
    whl = [rim, hub]
    for q in range(12):
        a = q / 12 * math.tau
        whl.append(tube('車_輻', [(math.cos(a) * .1, math.sin(a) * .1, 0), (math.cos(a) * .63, math.sin(a) * .63, 0)], .018, M['wood'], 4))
    w = join(whl, '車輪')
    w.rotation_euler.y = math.pi / 2; w.location = (dx, .4, .7); apply(w)
    bpy.ops.object.transform_apply(location=True, rotation=False, scale=False); cart.append(w)
# 馬：橢圓身軀、頸、頭、四腿、鬃與尾
hb = lathe('馬_身', [(0, 0), (.22, .05), (.33, .3), (.36, .8), (.33, 1.3), (.2, 1.55), (0, 1.6)], (0, 0, 0), M['horse'], 18, sc=(.85, 1, 1))
hb.rotation_euler.x = math.pi / 2; apply(hb); cart.append(place(hb, (0, -1.8, 1.25)))
cart.append(tube('馬_頸', [(0, -3.2, 1.35), (0, -3.45, 1.75), (0, -3.6, 2.05)], [.26, .2, .15], M['horse'], 10))
cart.append(tube('馬_頭', [(0, -3.55, 2.12), (0, -3.8, 1.98), (0, -4.05, 1.78)], [.15, .12, .085], M['horse'], 10))
for s in (-1, 1):
    cart.append(cone('馬_耳', .04, .0, .14, (s * .07, -3.55, 2.2), M['horse'], 5))
    cart.append(sphere('馬_眼', .025, (s * .1, -3.78, 2.03), M['hair'], 6))
cart.append(tube('馬_鬃', [(0, -3.15, 1.62), (0, -3.38, 1.92), (0, -3.52, 2.18)], [.07, .06, .04], M['hair'], 5, True, True, .35))
cart.append(tube('馬_尾', [(0, -1.75, 1.45), (0, -1.6, 1.2), (0, -1.6, .75)], [.07, .06, .03], M['hair'], 6))
for dx in (-.2, .2):
    for dy in (-3.05, -2.0):
        cart.append(tube('馬_腿', [(dx, dy, 1.1), (dx, dy + .04, .55), (dx, dy, .12)], [.08, .055, .05], M['horse'], 6))
        cart.append(cone('馬_蹄', .065, .07, .12, (dx, dy, 0), M['shoe'], 8))
cartO = join(cart, '馬車', origin=(0, 0, 0))
cartO.location = T(20, 6)

# ---------- 匯出 ----------
bpy.ops.object.select_all(action='SELECT')
glb = os.path.join(OUT, '孔子生平.glb')
bpy.ops.export_scene.gltf(filepath=glb, export_format='GLB', use_selection=True, export_extras=True,
                          export_apply=True, export_lights=False, export_cameras=False)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, '孔子生平.blend'))
print('EXPORTED', glb, os.path.getsize(glb))
