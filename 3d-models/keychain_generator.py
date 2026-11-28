"""
Hebrew name keychain generator (Blender + shapely + HarfBuzz).

Usage:
    python keychain_generator.py "<name>" <out_dir> [font.ttf]

Output: base.stl (magenta), letters.stl (white), keychain.3mf (both as parts
of one object, ready for multi-color AMS), preview images.
All units are millimetres. Flat bottom at Z=0, no supports needed.
"""
import sys, os, math, zipfile
import uharfbuzz as hb
from fontTools.ttLib import TTFont
from fontTools.pens.basePen import BasePen
from shapely.geometry import Polygon, MultiPolygon, Point, box
from shapely.ops import unary_union
import bpy
import bmesh
from mathutils import Vector

# ---------------- parameters ----------------
TOTAL_WIDTH = 60.0      # overall width of the keychain
BASE_H = 3.0            # magenta base thickness
LETTER_H = 1.0          # raised white letters
BORDER = 1.5            # magenta frame around the letters
HOLE_D = 4.2            # key-ring hole
HOLE_WALL = 2.5         # material around the hole
CLOSE_R = 2.5           # morphological closing -> solid joins between letters
MIN_HE_GAP = 1.0        # minimum gap between the ה leg and its roof (mm)

name = sys.argv[1]
out_dir = sys.argv[2]
font_path = sys.argv[3] if len(sys.argv) > 3 else os.path.join(os.path.dirname(__file__), "fonts", "Fredoka-Bold.ttf")
os.makedirs(out_dir, exist_ok=True)


# ---------------- glyph outlines ----------------
class FlatPen(BasePen):
    def __init__(self, gs, steps=24):
        super().__init__(gs); self.contours = []; self.cur = []; self.n = steps
    def _moveTo(self, p): self.cur = [p]
    def _lineTo(self, p): self.cur.append(p)
    def _qCurveToOne(self, p1, p2):
        p0 = self.cur[-1]
        for i in range(1, self.n + 1):
            t = i / self.n; u = 1 - t
            self.cur.append((u*u*p0[0] + 2*u*t*p1[0] + t*t*p2[0], u*u*p0[1] + 2*u*t*p1[1] + t*t*p2[1]))
    def _curveToOne(self, p1, p2, p3):
        p0 = self.cur[-1]
        for i in range(1, self.n + 1):
            t = i / self.n; u = 1 - t
            self.cur.append(tuple(u**3*a + 3*u*u*t*b + 3*u*t*t*c + t**3*d for a, b, c, d in zip(p0, p1, p2, p3)))
    def _closePath(self):
        if len(self.cur) >= 3: self.contours.append(self.cur)
        self.cur = []
    _endPath = _closePath


def glyph_shape(gs, gname, dx, dy):
    pen = FlatPen(gs); gs[gname].draw(pen)
    outers, holes = [], []
    for c in pen.contours:
        p = Polygon([(x + dx, y + dy) for x, y in c]).buffer(0)
        if p.is_empty: continue
        # TrueType: outer contours are clockwise (non-zero winding)
        (holes if Polygon(c).exterior.is_ccw else outers).append(p)
    return unary_union(outers).difference(unary_union(holes)) if holes else unary_union(outers)


# Shape with HarfBuzz: correct RTL order (output glyphs are in visual left->right order)
blob = hb.Blob.from_file_path(font_path); face = hb.Face(blob); font = hb.Font(face)
buf = hb.Buffer(); buf.add_str(name); buf.guess_segment_properties()
buf.direction = "rtl"; buf.script = "Hebr"; buf.language = "he"
hb.shape(font, buf, {"kern": True, "liga": True})
tt = TTFont(font_path); gs = tt.getGlyphSet(); order = tt.getGlyphOrder()

glyphs, x = [], 0
for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
    shp = glyph_shape(gs, order[info.codepoint], x + pos.x_offset, pos.y_offset)
    glyphs.append((name[info.cluster], shp)); x += pos.x_advance

# ---------------- scale to final width ----------------
def layout(scale):
    from shapely import affinity
    gl = [(ch, affinity.scale(g, scale, scale, origin=(0, 0))) for ch, g in glyphs]
    return gl

def build(scale):
    gl = layout(scale)
    # ensure the ה leg is clearly separated from its roof
    fixed = []
    for ch, g in gl:
        if ch == "ה" and isinstance(g, MultiPolygon) and len(g.geoms) >= 2:
            parts = sorted(g.geoms, key=lambda p: p.area, reverse=True)
            roof, leg = parts[0], unary_union(parts[1:])
            gap = roof.distance(leg)
            if gap < MIN_HE_GAP:
                leg = leg.difference(roof.buffer(MIN_HE_GAP))
            g = unary_union([roof, leg])
        fixed.append((ch, g))
    letters = unary_union([g for _, g in fixed])
    minx, miny, maxx, maxy = letters.bounds
    # ring tab on the LEFT side, vertically centred on the leftmost letter
    left_letter = min(fixed, key=lambda cg: cg[1].bounds[0])[1]
    lb = left_letter.bounds
    hole_r = HOLE_D / 2; tab_r = hole_r + HOLE_WALL
    cy = (lb[1] + lb[3]) / 2
    # x of the left edge of the letters around the hole height
    band = letters.intersection(box(minx - 1, cy - tab_r, maxx + 1, cy + tab_r))
    edge_x = band.bounds[0] if not band.is_empty else minx
    cx = edge_x - BORDER - hole_r - 0.6
    tab = Point(cx, cy).buffer(tab_r, 64)
    bridge = box(cx, cy - tab_r, edge_x + 2, cy + tab_r)
    raw = unary_union([letters.buffer(BORDER, 32), tab, bridge])
    base = raw.buffer(CLOSE_R, 32).buffer(-CLOSE_R, 32)          # solid joins
    if isinstance(base, MultiPolygon):                            # last resort
        base = unary_union([base, box(*letters.bounds)]).buffer(CLOSE_R).buffer(-CLOSE_R)
    base = Polygon(base.exterior)                                  # fill any inner holes
    base = base.difference(Point(cx, cy).buffer(hole_r, 96))
    return letters, base, fixed, (cx, cy)

# iterate scale so that overall width == TOTAL_WIDTH
scale = 0.05
for _ in range(30):
    letters, base, fixed, hole_c = build(scale)
    w = base.bounds[2] - base.bounds[0]
    scale *= (TOTAL_WIDTH - (w - (letters.bounds[2] - letters.bounds[0]))) / (letters.bounds[2] - letters.bounds[0])
letters, base, fixed, hole_c = build(scale)

# shift so bottom-left of base is at the origin
from shapely import affinity
ox, oy = base.bounds[0], base.bounds[1]
letters = affinity.translate(letters, -ox, -oy); base = affinity.translate(base, -ox, -oy)
hole_c = (hole_c[0] - ox, hole_c[1] - oy)
fixed = [(c, affinity.translate(g, -ox, -oy)) for c, g in fixed]

# ---------------- printability checks ----------------
report = []
bw, bh = base.bounds[2] - base.bounds[0], base.bounds[3] - base.bounds[1]
report.append(f"Overall size: {bw:.2f} x {bh:.2f} x {BASE_H + LETTER_H:.1f} mm")
report.append(f"Base single piece: {isinstance(base, Polygon)}")
opened = base.buffer(-1.0).buffer(1.0)
report.append(f"Base necks >= 2mm (stays one piece after 1mm opening): {isinstance(opened, Polygon)}")
for ch, g in fixed:
    if ch == "ה":
        parts = sorted(g.geoms, key=lambda p: p.area, reverse=True) if isinstance(g, MultiPolygon) else [g]
        if len(parts) >= 2:
            report.append(f"ה: leg separate from roof, gap = {parts[0].distance(unary_union(parts[1:])):.2f} mm")
        else:
            report.append("ה: WARNING leg is joined to roof!")
thin = letters.area - letters.buffer(-0.4).buffer(0.4).area
report.append(f"Letter area thinner than 0.8mm: {thin:.2f} mm² of {letters.area:.1f} mm²")
d_hole_letters = Point(hole_c).buffer(HOLE_D / 2).distance(letters)
report.append(f"Hole Ø{HOLE_D} at x={hole_c[0]:.2f}, y={hole_c[1]:.2f}; distance to letters {d_hole_letters:.2f} mm")
print("\n".join(report))

# ---------------- Blender meshes ----------------
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.unit_settings.system = 'METRIC'; sc.unit_settings.scale_length = 0.001


def extrude(shape, z0, h, label):
    cu = bpy.data.curves.new(label, 'CURVE'); cu.dimensions = '2D'; cu.fill_mode = 'BOTH'
    cu.extrude = h / 2
    polys = shape.geoms if isinstance(shape, MultiPolygon) else [shape]
    for p in polys:
        for ring in [p.exterior] + list(p.interiors):
            pts = list(ring.coords)[:-1]
            sp = cu.splines.new('POLY'); sp.points.add(len(pts) - 1)
            for i, (px, py) in enumerate(pts): sp.points[i].co = (px, py, 0, 1)
            sp.use_cyclic_u = True
    ob = bpy.data.objects.new(label, cu); sc.collection.objects.link(ob)
    ob.location.z = z0 + h / 2
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.select_all(action='DESELECT'); ob.select_set(True)
    bpy.ops.object.convert(target='MESH')
    ob = bpy.context.object
    bpy.ops.object.transform_apply(location=True)
    bm = bmesh.new(); bm.from_mesh(ob.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    manifold = all(e.is_manifold for e in bm.edges)
    vol = bm.calc_volume()
    bm.to_mesh(ob.data); bm.free()
    print(f"{label}: manifold={manifold} volume={vol:.1f} mm³")
    return ob


base_ob = extrude(base, 0.0, BASE_H, "base_magenta")
let_ob = extrude(letters, BASE_H, LETTER_H, "letters_white")
base_ob.color = (0.93, 0.0, 0.55, 1); let_ob.color = (0.97, 0.97, 0.97, 1)

for ob, fn in [(base_ob, "base_magenta.stl"), (let_ob, "letters_white.stl")]:
    bpy.ops.object.select_all(action='DESELECT'); ob.select_set(True)
    bpy.ops.wm.stl_export(filepath=os.path.join(out_dir, fn), export_selected_objects=True)


# ---------------- 3MF (one object, two parts) ----------------
def mesh_xml(ob, oid):
    m = ob.data; m.calc_loop_triangles()
    v = "".join(f'<vertex x="{p.co.x:.4f}" y="{p.co.y:.4f}" z="{p.co.z:.4f}"/>' for p in m.vertices)
    t = "".join(f'<triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in (tri.vertices for tri in m.loop_triangles))
    return f'<object id="{oid}" name="{ob.name}" type="model"><mesh><vertices>{v}</vertices><triangles>{t}</triangles></mesh></object>'

model = ('<?xml version="1.0" encoding="UTF-8"?>'
         '<model unit="millimeter" xml:lang="en-US" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">'
         '<resources>' + mesh_xml(base_ob, 1) + mesh_xml(let_ob, 2) +
         f'<object id="3" name="keychain_{name}" type="model"><components><component objectid="1"/><component objectid="2"/></components></object>'
         '</resources><build><item objectid="3"/></build></model>')
with zipfile.ZipFile(os.path.join(out_dir, "keychain.3mf"), "w", zipfile.ZIP_DEFLATED) as z:
    z.writestr("[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/></Types>')
    z.writestr("_rels/.rels", '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>')
    z.writestr("3D/3dmodel.model", model)

# ---------------- previews ----------------
sc.render.engine = 'BLENDER_WORKBENCH'
sc.display.shading.light = 'STUDIO'; sc.display.shading.color_type = 'OBJECT'
sc.display.shading.show_cavity = True
sc.render.resolution_x, sc.render.resolution_y = 1200, 800
center = Vector((bw / 2, bh / 2, 2))
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); sc.collection.objects.link(cam); sc.camera = cam
for tag, loc, lens in [("preview_top", (bw / 2, bh / 2, 120), 60), ("preview_3d", (bw / 2, -80, 75), 50)]:
    cam.location = loc; cam.data.lens = lens
    cam.rotation_euler = (center - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    sc.render.filepath = os.path.join(out_dir, tag + ".png"); bpy.ops.render.render(write_still=True)

with open(os.path.join(out_dir, "report.txt"), "w") as f:
    f.write("\n".join(report) + "\n")
