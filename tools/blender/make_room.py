"""Build the outpatient consult room (stage 1) and export it for Unity.

Usage (from Med/):
  /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup --python tools/blender/make_room.py -- \
      art/Environments/OutpatientConsult [--previews "art_source/Mégane_Blender/Mégane_Blender.Fbx" art/Animations]

Writes Room_OutpatientConsult.fbx, Textures/*.png and Room_OutpatientConsult.blend, plus (with --previews)
renders previews/ with Mégane seated at PatientAnchor and mid-walk in the doorway.

Blender layout: +X east, +Y north, Z up, metres. Characters and anchors face their local -Y, which is
Unity's +Z after export (Forward -Z, Up Y, Apply Transform). Unity position = (-x, z, -y); Unity yaw = -Blender yaw.
"""
import bpy, bmesh, math, os, sys
from mathutils import Vector, Matrix

ROOM_X, ROOM_Y, ROOM_H, WALL_T = 2.0, 1.8, 2.8, 0.12   # interior half-sizes, height, wall thickness
DADO_H = 1.2

# ---- people layout (see ANIMATIONS.md: seated eyes sit 0.28 m behind the character root at 1.19 m)
DOC_EYE = Vector((1.30, 0.10, 1.20))     # doctor's seated eye point
DOC_CHAIR_YAW = -90                      # doctor's chair faces -X (west)
PAT_FROM_DOC = 200                       # direction doctor -> patient (deg, CCW from +X)
PAT_YAW = 160                            # patient faces 70 deg (NNE): 110 deg to the doctor's chair
SEATED_EYE_LOCAL = Vector((0.005, 0.282, 1.193))  # seated_neutral frame 0, character-local
WALK_DIST = 3.75                         # walk_in root travel
WALK_HEADING = PAT_YAW - 90              # she arrives side-on to the chair, then turns 90 deg left to sit


def yaw_dir(yaw):
    """Facing direction (world XY) of something whose local -Y faces forward, rotated yaw deg about Z."""
    a = math.radians(yaw)
    return Vector((math.sin(a), -math.cos(a), 0))


def rotz(v, yaw):
    return Matrix.Rotation(math.radians(yaw), 3, 'Z') @ Vector(v)


a = math.radians(PAT_FROM_DOC)
PAT_EYE = DOC_EYE + 1.5 * Vector((math.cos(a), math.sin(a), 0))
PAT_EYE.z = SEATED_EYE_LOCAL.z
PATIENT_ANCHOR = PAT_EYE - rotz(SEATED_EYE_LOCAL, PAT_YAW)
PATIENT_ANCHOR.z = 0.0
_s = (PATIENT_ANCHOR.x + ROOM_X) / yaw_dir(WALK_HEADING).x        # distance anchor -> inner west wall
DOOR_Y = PATIENT_ANCHOR.y - yaw_dir(WALK_HEADING).y * _s           # walk line crosses the west wall here
DOOR_W, DOOR_H = 0.9, 2.1
SPAWN = PATIENT_ANCHOR - WALK_DIST * yaw_dir(WALK_HEADING)
CORR_X0 = -ROOM_X - WALL_T                                            # corridor east face (room wall outer face)
CORR_X1 = -4.1                                                        # corridor west wall face
CORR_Y = (-0.8, 1.9)

# ---------------------------------------------------------------- textures / materials

SW = {  # atlas swatches (sRGB 0-255)
    'wall': (236, 226, 205), 'dado': (190, 205, 186), 'skirting': (120, 112, 100), 'ceiling': (244, 242, 236),
    'white': (240, 240, 236), 'steel': (165, 170, 172), 'steel_dark': (70, 74, 78), 'black': (28, 28, 30),
    'grey_green': (150, 165, 150), 'cushion': (64, 92, 112), 'cushion_doc': (40, 40, 44), 'alu': (200, 202, 204),
    'blind': (232, 228, 214), 'folder_blue': (60, 95, 150), 'folder_buff': (214, 190, 140), 'folder_green': (90, 140, 100),
    'folder_red': (165, 70, 60), 'paper': (248, 246, 238), 'tissue': (210, 225, 235), 'lamp': (60, 110, 100),
    'board': (225, 222, 210), 'frame_wood': (120, 85, 55), 'bin': (90, 120, 110), 'door_casing': (215, 205, 185),
    'rubber': (40, 40, 40), 'sign': (40, 90, 120), 'corr_wall': (232, 228, 214),
}
CELL = 128
SW_INDEX = {n: i for i, n in enumerate(SW)}
REGIONS = {'clock': (1024, 0, 1536, 512), 'screen': (1536, 0, 2048, 320)}  # pixel rects in the 2048 atlas


def swatch_uv(name):
    i = SW_INDEX[name]
    cx, cy = (i % 8) * CELL + CELL / 2, (i // 8) * CELL + CELL / 2
    return (cx / 2048, 1 - cy / 2048)


def region_uv(name):
    x0, y0, x1, y1 = REGIONS[name]
    return (x0 / 2048, 1 - y1 / 2048, x1 / 2048, 1 - y0 / 2048)


def make_textures(tex_dir):
    import numpy as np
    os.makedirs(tex_dir, exist_ok=True)
    rng = np.random.default_rng(7)

    def save(name, arr):  # arr: HxWx3 float 0..1, row 0 = top
        h, w = arr.shape[:2]
        img = bpy.data.images.new(name, w, h)
        rgba = np.concatenate([arr[::-1], np.ones((h, w, 1))], axis=2).astype(np.float32)
        img.pixels.foreach_set(rgba.ravel())
        img.filepath_raw = os.path.join(tex_dir, name + '.png')
        img.file_format = 'PNG'
        img.save()
        return img

    # atlas: flat swatches + clock face + monitor screen (generic, no text or logos)
    A = np.full((2048, 2048, 3), 0.5)
    for n, c in SW.items():
        i = SW_INDEX[n]
        x, y = (i % 8) * CELL, (i // 8) * CELL
        A[y:y + CELL, x:x + CELL] = np.array(c) / 255
    x0, y0, x1, y1 = REGIONS['clock']
    yy, xx = np.mgrid[0:512, 0:512]
    r = np.hypot(xx - 256, yy - 256) / 256
    th = np.arctan2(xx - 256, -(yy - 256))  # 0 = 12 o'clock, clockwise
    face = np.ones((512, 512, 3)) * 0.97
    face[r > 0.93] = (0.15, 0.15, 0.16)
    for k in range(60):
        ang = k * 2 * math.pi / 60
        d = np.abs(np.angle(np.exp(1j * (th - ang)))) * r
        long = k % 5 == 0
        face[(d < (0.022 if long else 0.008)) & (r > (0.74 if long else 0.82)) & (r < 0.9)] = 0.1

    def hand(ang, length, width, col):
        d = np.abs(np.angle(np.exp(1j * (th - ang)))) * r
        face[(d < width) & (r < length) & (np.cos(th - ang) > 0)] = col
    hand(math.radians(10 * 30 + 9 * 0.5), 0.5, 0.03, (0.08, 0.08, 0.08))   # 10:09
    hand(math.radians(9 * 6), 0.75, 0.02, (0.08, 0.08, 0.08))
    hand(math.radians(35 * 6), 0.8, 0.007, (0.7, 0.1, 0.1))
    face[r < 0.04] = 0.08
    A[y0:y1, x0:x1] = face
    x0, y0, x1, y1 = REGIONS['screen']
    scr = np.ones((y1 - y0, x1 - x0, 3)) * np.array((0.16, 0.22, 0.30))
    scr[0:28] = (0.24, 0.36, 0.48)
    for (a0, b0, a1, b1, c) in ((20, 50, 160, 300, (0.85, 0.87, 0.88)), (180, 50, 490, 170, (0.92, 0.93, 0.94)),
                                (180, 185, 490, 300, (0.88, 0.90, 0.92)), (30, 70, 150, 80, (0.5, 0.6, 0.7))):
        scr[b0:b1, a0:a1] = c
    for k in range(6):  # list rows
        scr[200 + k * 16:208 + k * 16, 195:470] = (0.7, 0.74, 0.78)
    A[y0:y1, x0:x1] = scr
    save('T_Room_Atlas', A)

    # vinyl floor: 2x2 tiles of 0.6 m per texture (1.2 m repeat), mottled beige, thin grout
    n = 1024
    base = np.array((0.78, 0.72, 0.62))
    noise = rng.normal(0, 1, (n // 8, n // 8))
    noise = np.kron(noise, np.ones((8, 8)))
    fine = rng.normal(0, 1, (n, n))
    F = base * (1 + 0.035 * noise[..., None] + 0.02 * fine[..., None])
    g = np.zeros((n, n), bool)
    for k in (0, n // 2):
        g[k:k + 3, :] = True
        g[:, k:k + 3] = True
    F[g] = (0.55, 0.52, 0.47)
    save('T_Floor_Vinyl', np.clip(F, 0, 1))

    # wood: warm teak-like grain
    yy, xx = np.mgrid[0:n, 0:n] / n
    w = rng.normal(0, 1, 64)
    wob = sum(0.02 * w[i] * np.sin(2 * math.pi * (i + 1) * yy + w[i + 32]) for i in range(8))
    grain = np.sin(2 * math.pi * (xx * 9 + 3 * wob + 0.15 * np.sin(2 * math.pi * yy * 2))) * 0.5 + 0.5
    grain = grain ** 2
    W = np.array((0.42, 0.28, 0.17)) * (0.9 + 0.15 * grain[..., None] + 0.02 * rng.normal(0, 1, (n, n, 1)))
    save('T_Wood', np.clip(W, 0, 1))


def make_materials(tex_dir):
    def mat(name, tex=None, color=(0.8, 0.8, 0.8), rough=0.7, alpha=1.0, emit=None):
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        nt = m.node_tree
        bsdf = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
        bsdf.inputs['Roughness'].default_value = rough
        if tex:
            im = nt.nodes.new('ShaderNodeTexImage')
            im.image = bpy.data.images.load(os.path.join(tex_dir, tex + '.png'), check_existing=True)
            nt.links.new(im.outputs['Color'], bsdf.inputs['Base Color'])
        else:
            bsdf.inputs['Base Color'].default_value = (*color, 1)
        if alpha < 1:
            bsdf.inputs['Alpha'].default_value = alpha
            try:
                m.surface_render_method = 'BLENDED'
            except (AttributeError, TypeError):
                pass
        if emit:
            bsdf.inputs['Emission Color'].default_value = (*emit, 1)
            bsdf.inputs['Emission Strength'].default_value = 6.0
        return m
    return {'atlas': mat('M_Room_Atlas', 'T_Room_Atlas', rough=0.75),
            'floor': mat('M_Floor_Vinyl', 'T_Floor_Vinyl', rough=0.45),
            'wood': mat('M_Wood', 'T_Wood', rough=0.5),
            'glass': mat('M_Glass', color=(0.75, 0.85, 0.9), rough=0.05, alpha=0.18),
            'light': mat('M_LightPanel', color=(1, 1, 0.97), emit=(1.0, 0.96, 0.88))}


# ---------------------------------------------------------------- geometry helpers

TILE = {'floor': 1.2, 'wood': 0.6}   # metres per texture repeat


class Part:
    """One exported object built from boxes, cylinders and cones."""

    def __init__(self, name, static=True):
        self.name, self.static = name, static
        self.bm = bmesh.new()
        self.uv = self.bm.loops.layers.uv.verify()
        self.mats = []

    def _mi(self, m):
        if m not in self.mats:
            self.mats.append(m)
        return self.mats.index(m)

    def _finish(self, geom_faces, mat, sw, faces_uv=None):
        mi = self._mi(mat)
        for f in geom_faces:
            f.material_index = mi
            nrm = f.normal
            if mat in TILE:
                ax = max(range(3), key=lambda i: abs(nrm[i]))
                u, v = [i for i in range(3) if i != ax]
                for l in f.loops:
                    l[self.uv].uv = (l.vert.co[u] / TILE[mat], l.vert.co[v] / TILE[mat])
                continue
            reg = None
            if faces_uv:
                for (direction, region) in faces_uv:
                    if nrm.dot(direction) > 0.9:
                        reg = region
            if reg:
                u0, v0, u1, v1 = region_uv(reg)
                # planar map the face's own extent into the region
                tang = Vector((0, 0, 1)).cross(nrm)
                tang = tang.normalized() if tang.length > 1e-6 else Vector((1, 0, 0))
                bit = nrm.cross(tang)
                pts = [(l.vert.co.dot(tang), l.vert.co.dot(bit)) for l in f.loops]
                a0, a1 = min(p[0] for p in pts), max(p[0] for p in pts)
                b0, b1 = min(p[1] for p in pts), max(p[1] for p in pts)
                for l, (pa, pb) in zip(f.loops, pts):
                    l[self.uv].uv = (u0 + (u1 - u0) * (pa - a0) / (a1 - a0 or 1),
                                     v0 + (v1 - v0) * (pb - b0) / (b1 - b0 or 1))
            else:
                uv = swatch_uv(sw)
                for l in f.loops:
                    l[self.uv].uv = uv

    def box(self, lo, hi, mat='atlas', sw='white', M=None, faces_uv=None):
        lo, hi = Vector(lo), Vector(hi)
        c, s = (lo + hi) / 2, hi - lo
        T = (M or Matrix.Identity(4)) @ Matrix.Translation(c) @ Matrix.Diagonal((*s, 1))
        r = bmesh.ops.create_cube(self.bm, size=1.0, matrix=T)
        faces = list({f for v in r['verts'] for f in v.link_faces})
        bmesh.ops.recalc_face_normals(self.bm, faces=faces)
        if faces_uv and M:
            faces_uv = [((M.to_3x3() @ Vector(d)).normalized(), reg) for d, reg in faces_uv]
        elif faces_uv:
            faces_uv = [(Vector(d), reg) for d, reg in faces_uv]
        self._finish(faces, mat, sw, faces_uv)

    def cyl(self, center, radius, depth, mat='atlas', sw='steel', axis='Z', segs=16, M=None, r2=None, faces_uv=None):
        rot = {'Z': Matrix.Identity(4), 'X': Matrix.Rotation(math.pi / 2, 4, 'Y'), 'Y': Matrix.Rotation(math.pi / 2, 4, 'X')}[axis]
        T = (M or Matrix.Identity(4)) @ Matrix.Translation(center) @ rot
        r = bmesh.ops.create_cone(self.bm, cap_ends=True, segments=segs, radius1=radius,
                                  radius2=radius if r2 is None else r2, depth=depth, matrix=T)
        faces = list({f for v in r['verts'] for f in v.link_faces})
        bmesh.ops.recalc_face_normals(self.bm, faces=faces)
        if faces_uv:
            faces_uv = [(((M or Matrix.Identity(4)).to_3x3() @ rot.to_3x3() @ Vector(d)).normalized(), reg) for d, reg in faces_uv]
        self._finish(faces, mat, sw, faces_uv)

    def build(self, mats, parent=None, matrix=None):
        me = bpy.data.meshes.new(self.name)
        self.bm.to_mesh(me)
        self.bm.free()
        for m in self.mats:
            me.materials.append(mats[m])
        ob = bpy.data.objects.new(self.name, me)
        bpy.context.scene.collection.objects.link(ob)
        ob['static'] = self.static
        if parent:
            ob.parent = parent
        if matrix:
            ob.matrix_world = matrix
        return ob


def wall(p, x0, x1, y0, y1, z0, z1, upper='wall', lower='dado'):
    """Wall block, painted with the dado colour below DADO_H."""
    if z0 < DADO_H < z1:
        p.box((x0, y0, z0), (x1, y1, DADO_H), sw=lower)
        p.box((x0, y0, DADO_H), (x1, y1, z1), sw=upper)
    else:
        p.box((x0, y0, z0), (x1, y1, z1), sw=lower if z1 <= DADO_H else upper)


def place(yaw, pos):
    return Matrix.Translation(pos) @ Matrix.Rotation(math.radians(yaw), 4, 'Z')


# ---------------------------------------------------------------- the room


def build_shell(mats):
    X, Y, H, T = ROOM_X, ROOM_Y, ROOM_H, WALL_T
    p = Part('Room_Shell')
    p.box((-X, -Y, -0.02), (X, Y, 0), mat='floor')
    wall(p, -X - T, X + T, -Y - T, -Y, 0, H)                       # south
    wall(p, X, X + T, -Y, Y, 0, H)                                 # east
    wx0, wx1, sill, top = -0.1, 1.3, 0.95, 2.15                    # north, window hole
    wall(p, -X - T, wx0, Y, Y + T, 0, H)
    wall(p, wx1, X + T, Y, Y + T, 0, H)
    wall(p, wx0, wx1, Y, Y + T, 0, sill)
    wall(p, wx0, wx1, Y, Y + T, top, H)
    d0, d1 = DOOR_Y - DOOR_W / 2, DOOR_Y + DOOR_W / 2              # west, door hole
    wall(p, -X - T, -X, -Y, d0, 0, H)
    wall(p, -X - T, -X, d1, Y, 0, H)
    wall(p, -X - T, -X, d0, d1, DOOR_H, H)
    # skirting
    s, sh = 0.012, 0.09
    p.box((-X, -Y, 0), (X, -Y + s, sh), sw='skirting')
    p.box((X - s, -Y, 0), (X, Y, sh), sw='skirting')
    p.box((-X, Y - s, 0), (X, Y, sh), sw='skirting')
    p.box((-X, -Y, 0), (-X + s, d0, sh), sw='skirting')
    p.box((-X, d1, 0), (-X + s, Y, sh), sw='skirting')
    # window: sill, aluminium frame, mullion, glass
    p.box((wx0 - 0.03, Y - 0.06, sill - 0.03), (wx1 + 0.03, Y + 0.02, sill), sw='white')
    for (a0, a1, b0, b1) in ((wx0, wx0 + 0.05, sill, top), (wx1 - 0.05, wx1, sill, top),
                             ((wx0 + wx1) / 2 - 0.025, (wx0 + wx1) / 2 + 0.025, sill, top),
                             (wx0, wx1, sill, sill + 0.05), (wx0, wx1, top - 0.05, top)):
        p.box((a0, Y + 0.04, b0), (a1, Y + 0.09, b1), sw='alu')
    p.box((wx0, Y + 0.06, sill), (wx1, Y + 0.07, top), mat='glass')
    # outside the window: a plain light backdrop so it does not read as a void
    p.box((wx0 - 1, Y + 1.5, -0.5), (wx1 + 1, Y + 1.55, H + 1), sw='white')
    # door: jamb lining and casing on the room side
    c = 0.07
    p.box((-X - T, d0 - 0.0, 0), (-X, d0 + 0.02, DOOR_H), sw='door_casing')
    p.box((-X - T, d1 - 0.02, 0), (-X, d1, DOOR_H), sw='door_casing')
    p.box((-X - T, d0, DOOR_H - 0.02), (-X, d1, DOOR_H), sw='door_casing')
    p.box((-X, d0 - c, 0), (-X + 0.015, d0, DOOR_H + c), sw='door_casing')
    p.box((-X, d1, 0), (-X + 0.015, d1 + c, DOOR_H + c), sw='door_casing')
    p.box((-X, d0, DOOR_H), (-X + 0.015, d1, DOOR_H + c), sw='door_casing')
    # clock (west wall, behind the patient from the doctor's seat)
    p.cyl(Vector((-X + 0.02, -1.0, 2.05)), 0.16, 0.04, sw='black', axis='X', segs=32,
          faces_uv=[((0, 0, 1), 'clock')])
    # blank pin board behind the doctor (east wall), no text
    p.box((X - 0.02, -0.35, 1.25), (X, 0.55, 1.9), sw='frame_wood')
    p.box((X - 0.025, -0.32, 1.28), (X - 0.02, 0.52, 1.87), sw='board')
    for (y, z, sw) in ((-0.2, 1.7, 'paper'), (0.05, 1.62, 'tissue'), (0.3, 1.72, 'paper')):
        p.box((X - 0.03, y - 0.08, z - 0.1), (X - 0.025, y + 0.08, z + 0.1), sw=sw)
    return p.build(mats)


def build_ceiling(mats):
    X, Y, H, T = ROOM_X, ROOM_Y, ROOM_H, WALL_T
    p = Part('Room_Ceiling')
    p.box((-X - T, -Y - T, H), (X + T, Y + T, H + 0.05), sw='ceiling')
    for y in (-0.7, 0.9):
        p.box((-0.6, y - 0.15, H - 0.02), (0.6, y + 0.15, H), sw='white')
        p.box((-0.57, y - 0.12, H - 0.025), (0.57, y + 0.12, H - 0.02), mat='light')
    return p.build(mats)


def build_fan(mats):
    p = Part('CeilingFan')
    c = Vector((-0.2, 0.1, ROOM_H))
    p.cyl(c + Vector((0, 0, -0.2)), 0.012, 0.4, sw='white', segs=8)
    p.cyl(c + Vector((0, 0, -0.42)), 0.11, 0.09, sw='white', segs=20)
    for k in range(3):
        M = Matrix.Translation(c + Vector((0, 0, -0.42))) @ Matrix.Rotation(math.radians(30 + k * 120), 4, 'Z')
        p.box((0.09, -0.06, -0.008), (0.62, 0.06, 0.004), sw='white', M=M @ Matrix.Rotation(math.radians(8), 4, 'X'))
    return p.build(mats)


def build_blinds(mats):
    p = Part('Window_Blinds')
    wx0, wx1, Y = -0.1, 1.3, ROOM_Y
    p.box((wx0 + 0.02, Y - 0.06, 2.1), (wx1 - 0.02, Y - 0.01, 2.14), sw='blind')
    z = 2.08
    while z > 1.42:   # lowered about half way, slats tilted open
        M = Matrix.Translation((0, Y - 0.035, z)) @ Matrix.Rotation(math.radians(-25), 4, 'X')
        p.box((wx0 + 0.03, -0.025, -0.002), (wx1 - 0.03, 0.025, 0.002), sw='blind', M=M)
        z -= 0.03
    p.box((wx0 + 0.03, Y - 0.06, z - 0.01), (wx1 - 0.03, Y - 0.01, z + 0.01), sw='blind')
    p.box(((wx0 + wx1) / 2 + 0.3, Y - 0.04, z - 0.25), ((wx0 + wx1) / 2 + 0.31, Y - 0.03, z), sw='white')  # cord
    return p.build(mats)


def build_desk(mats):
    p = Part('Desk')
    x0, x1, y0, y1, h = 0.25, 0.95, -0.55, 0.95, 0.75
    p.box((x0, y0, h - 0.03), (x1, y1, h), mat='wood')
    p.box((x0 + 0.02, y0 + 0.03, 0.3), (x0 + 0.04, y1 - 0.03, h - 0.03), sw='steel')       # modesty panel (patient side)
    for (a, b) in ((x0 + 0.02, y0 + 0.02), (x1 - 0.06, y0 + 0.02)):
        p.box((a, b, 0), (a + 0.04, b + 0.04, h - 0.03), sw='steel')
    p.box((x0 + 0.03, y1 - 0.45, 0), (x1 - 0.03, y1 - 0.03, h - 0.03), sw='steel')        # drawer pedestal
    for z in (0.12, 0.33, 0.52):
        p.box((x1 - 0.031, y1 - 0.43, z), (x1 - 0.025, y1 - 0.05, z + 0.17), sw='steel_dark')
        p.box((x1 - 0.04, y1 - 0.30, z + 0.13), (x1 - 0.025, y1 - 0.18, z + 0.15), sw='alu')
    return p.build(mats)


def build_props(mats):
    p = Part('Desk_Props')
    h = 0.75
    # monitor facing the doctor (+X), away from the doctor-patient sight line
    # monitor at the far end of the desk, turned to the doctor; keeps the patient, door and corner in view
    Mm = place(-35, Vector((0.62, 0.74, h)))
    p.box((-0.09, -0.1, 0), (0.09, 0.1, 0.012), sw='black', M=Mm)
    p.box((-0.02, -0.02, 0), (0.01, 0.02, 0.2), sw='black', M=Mm)
    p.box((-0.005, -0.27, 0.12), (0.025, 0.27, 0.45), sw='black', M=Mm, faces_uv=[((1, 0, 0), 'screen')])
    p.box((0.78, 0.12, h), (0.92, 0.56, h + 0.02), sw='black')                    # keyboard
    p.box((0.80, -0.15, h), (0.86, -0.09, h + 0.03), sw='black')                   # mouse
    for i, sw in enumerate(('folder_buff', 'folder_blue', 'folder_green', 'folder_buff', 'folder_red')):
        M = place(4 * math.sin(i * 1.7), Vector((0.47, 0.12, h + i * 0.022)))
        p.box((-0.12, -0.16, 0), (0.12, 0.16, 0.02), sw=sw, M=M)
    p.box((0.6, -0.35, h), (0.78, -0.1, h + 0.004), sw='paper')                     # prescription pad
    p.box((0.62, -0.33, h + 0.004), (0.76, -0.12, h + 0.008), sw='white')
    p.cyl(Vector((0.42, 0.45, h + 0.05)), 0.035, 0.1, sw='steel_dark', segs=12)     # pen holder
    for k in range(3):
        p.cyl(Vector((0.42 + 0.01 * k - 0.01, 0.45, h + 0.12)), 0.004, 0.08, sw=('folder_blue', 'black', 'folder_red')[k], segs=6)
    # tissue box at the patient's corner
    p.box((0.30, -0.52, h), (0.42, -0.28, h + 0.09), sw='tissue')
    p.box((0.34, -0.44, h + 0.09), (0.38, -0.36, h + 0.13), sw='white')
    # desk lamp
    lx, ly = 0.36, 0.88
    p.cyl(Vector((lx, ly, h + 0.012)), 0.08, 0.024, sw='lamp', segs=20)
    M1 = Matrix.Translation((lx, ly, h + 0.02)) @ Matrix.Rotation(math.radians(-20), 4, 'X')
    p.box((-0.01, -0.01, 0), (0.01, 0.01, 0.34), sw='steel', M=M1)
    top = M1 @ Vector((0, 0, 0.34))
    M2 = Matrix.Translation(top) @ Matrix.Rotation(math.radians(-110), 4, 'X')
    p.box((-0.01, -0.01, 0), (0.01, 0.01, 0.26), sw='steel', M=M2)
    tip = M2 @ Vector((0, 0, 0.26))
    p.cyl(tip + Vector((0, 0, -0.05)), 0.075, 0.12, sw='lamp', segs=20, r2=0.03)
    # waste bin by the desk
    p.cyl(Vector((1.0, -0.75, 0.16)), 0.13, 0.32, sw='bin', segs=20, r2=0.15)
    return p.build(mats)


def build_cupboard(mats):
    p = Part('Cupboard')
    x0, x1, y0, y1, h = 1.55, 1.99, -1.78, -0.88, 1.9
    p.box((x0, y0, 0.05), (x1, y1, h), sw='grey_green')
    p.box((x0 - 0.004, (y0 + y1) / 2 - 0.003, 0.12), (x0, (y0 + y1) / 2 + 0.003, h - 0.07), sw='steel_dark')
    for y in ((y0 + y1) / 2 - 0.06, (y0 + y1) / 2 + 0.04):
        p.box((x0 - 0.03, y, 1.0), (x0, y + 0.02, 1.15), sw='alu')
    p.box((x0 + 0.02, y0 + 0.02, 0), (x1 - 0.02, y1 - 0.02, 0.05), sw='steel_dark')
    return p.build(mats)


def chair_steel(name, mats, yaw, pos, cushion='cushion'):
    """Armless steel-frame OPD chair. Local frame: front edge at y=-0.23 from centre, seat top 0.45 m."""
    p = Part(name)
    M = place(yaw, pos)
    w, d, h = 0.48, 0.46, 0.45
    p.box((-w / 2, -d / 2, h - 0.06), (w / 2, d / 2, h), sw=cushion, M=M)               # seat cushion
    p.box((-w / 2 + 0.01, -d / 2 + 0.01, h - 0.08), (w / 2 - 0.01, d / 2 - 0.01, h - 0.06), sw='steel_dark', M=M)
    for sx in (-1, 1):
        for sy in (-1, 1):
            p.cyl(Vector((sx * (w / 2 - 0.03), sy * (d / 2 - 0.03), (h - 0.08) / 2)), 0.012, h - 0.08, sw='steel', segs=8, M=M)
            p.cyl(Vector((sx * (w / 2 - 0.03), sy * (d / 2 - 0.03), 0.005)), 0.016, 0.01, sw='rubber', segs=8, M=M)
        p.cyl(Vector((sx * (w / 2 - 0.03), 0, 0.12)), 0.009, d - 0.06, sw='steel', axis='Y', segs=8, M=M)
        # back uprights, slightly reclined
        Mb = M @ Matrix.Translation((sx * (w / 2 - 0.03), d / 2 - 0.03, h - 0.08)) @ Matrix.Rotation(math.radians(-8), 4, 'X')
        p.cyl(Vector((0, 0, 0.27)), 0.012, 0.54, sw='steel', segs=8, M=Mb)
    Mb = M @ Matrix.Translation((0, d / 2 - 0.02, h + 0.17)) @ Matrix.Rotation(math.radians(-8), 4, 'X')
    p.box((-w / 2 + 0.02, -0.02, 0), (w / 2 - 0.02, 0.025, 0.3), sw=cushion, M=Mb)
    return p.build(mats)


def build_doctor_chair(mats):
    p = Part('Chair_Doctor')
    M = place(DOC_CHAIR_YAW, Vector((DOC_EYE.x + 0.12, DOC_EYE.y, 0)))
    for k in range(5):
        Mk = M @ Matrix.Rotation(math.radians(k * 72), 4, 'Z')
        p.box((-0.02, 0, 0.04), (0.02, 0.3, 0.07), sw='black', M=Mk)
        p.cyl(Vector((0, 0.3, 0.025)), 0.025, 0.04, sw='rubber', axis='X', segs=8, M=Mk)
    p.cyl(Vector((0, 0, 0.25)), 0.025, 0.4, sw='steel', segs=12, M=M)
    p.box((-0.25, -0.25, 0.42), (0.25, 0.25, 0.5), sw='cushion_doc', M=M)
    Mb = M @ Matrix.Translation((0, 0.24, 0.5)) @ Matrix.Rotation(math.radians(-10), 4, 'X')
    p.box((-0.03, -0.02, 0), (0.03, 0.02, 0.18), sw='black', M=Mb)
    p.box((-0.23, -0.03, 0.15), (0.23, 0.04, 0.62), sw='cushion_doc', M=Mb)
    for sx in (-1, 1):
        p.box((sx * 0.25 - 0.02, -0.12, 0.5), (sx * 0.25 + 0.02, 0.05, 0.68), sw='black', M=M)
        p.box((sx * 0.25 - 0.035, -0.2, 0.68), (sx * 0.25 + 0.035, 0.08, 0.71), sw='black', M=M)
    return p.build(mats)


def build_door(mats):
    X = ROOM_X
    hinge = Vector((-X, DOOR_Y + DOOR_W / 2 - 0.02, 0))
    door = bpy.data.objects.new('Door', None)
    bpy.context.scene.collection.objects.link(door)
    door.empty_display_type = 'ARROWS'
    door.empty_display_size = 0.3
    door.location = hinge
    door['static'] = False
    p = Part('Door_Leaf', static=False)
    L = DOOR_W - 0.04 - 0.01                     # leaf width inside the linings
    p.box((-0.05, -L, 0.01), (-0.01, 0, DOOR_H - 0.025), mat='wood')
    p.box((-0.052, -L + 0.02, 0.02), (-0.008, -0.02, 0.22), sw='steel')            # kick plate (both faces)
    for sx in (1, -1):                                                               # lever handles both sides
        x = -0.01 if sx > 0 else -0.05
        p.box((x + (0 if sx > 0 else -0.05), -L + 0.05, 0.98), (x + (0.05 if sx > 0 else 0), -L + 0.08, 1.1), sw='alu')
        p.box((x + (0.03 if sx > 0 else -0.05), -L + 0.06, 1.03), (x + (0.05 if sx > 0 else -0.03), -L + 0.2, 1.05), sw='alu')
    for z in (0.25, 1.0, 1.85):
        p.box((-0.012, -0.02, z), (0.004, 0.0, z + 0.1), sw='alu')                  # hinges
    leaf = p.build(mats)
    leaf.parent = door
    return door


def build_corridor(mats):
    p = Part('Corridor')
    x0, x1, (y0, y1), H, T = CORR_X0, CORR_X1, CORR_Y, ROOM_H, WALL_T
    p.box((x1, y0, -0.02), (x0, y1, 0), mat='floor')
    wall(p, x1 - T, x1, y0 - T, y1 + T, 0, H, upper='corr_wall')
    wall(p, x1, x0, y0 - T, y0, 0, H, upper='corr_wall')
    wall(p, x1, x0, y1, y1 + T, 0, H, upper='corr_wall')
    p.box((x1 - T, y0 - T, H), (x0, y1 + T, H + 0.05), sw='ceiling')
    p.box((x1 + 0.5, (y0 + y1) / 2 - 0.6, H - 0.02), (x1 + 0.8, (y0 + y1) / 2 + 0.6, H), sw='white')
    p.box((x1 + 0.53, (y0 + y1) / 2 - 0.57, H - 0.025), (x1 + 0.77, (y0 + y1) / 2 + 0.57, H - 0.02), mat='light')
    # steel waiting bench against the far wall
    by0, by1 = y0 + 0.25, y0 + 1.45
    p.box((x1 + 0.02, by0, 0.42), (x1 + 0.45, by1, 0.45), sw='steel')
    p.box((x1 + 0.02, by0, 0.5), (x1 + 0.06, by1, 0.85), sw='steel')
    for y in (by0 + 0.05, by1 - 0.08):
        p.box((x1 + 0.05, y, 0), (x1 + 0.4, y + 0.03, 0.42), sw='steel_dark')
    # blank direction sign (no text) above the door, corridor side
    p.box((x0 - 0.02, DOOR_Y - 0.3, 2.25), (x0, DOOR_Y + 0.3, 2.45), sw='sign')
    p.box((x1 + 0.0, 0.6, 1.3), (x1 + 0.02, 1.4, 1.9), sw='board')
    return p.build(mats)


def empty(name, pos, yaw=0.0):
    e = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(e)
    e.empty_display_type = 'ARROWS'
    e.empty_display_size = 0.25
    e.location = pos
    e.rotation_euler = (0, 0, math.radians(yaw))
    e['static'] = False
    return e


def heading_yaw(direction):
    """Yaw that makes local -Y point along `direction` (XY)."""
    return math.degrees(math.atan2(direction.x, -direction.y))


def build_anchors():
    to_pat = (PAT_EYE - DOC_EYE)
    to_pat.z = 0
    E = {}
    E['DoctorAnchor'] = empty('DoctorAnchor', DOC_EYE, heading_yaw(to_pat))
    E['PatientAnchor'] = empty('PatientAnchor', PATIENT_ANCHOR, PAT_YAW)
    E['ChairApproach'] = empty('ChairApproach', PATIENT_ANCHOR, PAT_YAW)
    E['PatientSpawn'] = empty('PatientSpawn', SPAWN, WALK_HEADING)
    E['CornerLookTarget'] = empty('CornerLookTarget', Vector((-ROOM_X + 0.25, ROOM_Y - 0.25, 1.3)))
    E['SoundSource_Door'] = empty('SoundSource_Door', Vector((-ROOM_X + 0.1, DOOR_Y, 1.1)))
    E['SoundSource_Corridor'] = empty('SoundSource_Corridor', Vector(((CORR_X0 + CORR_X1) / 2, sum(CORR_Y) / 2, 1.6)))
    E['KeyLightTarget'] = empty('KeyLightTarget', PAT_EYE.copy())
    return E


def build_all(out_dir):
    tex_dir = os.path.join(out_dir, 'Textures')
    make_textures(tex_dir)
    mats = make_materials(tex_dir)
    objs = [build_shell(mats), build_ceiling(mats), build_fan(mats), build_blinds(mats), build_desk(mats),
            build_props(mats), build_cupboard(mats), build_doctor_chair(mats),
            chair_steel('Chair_Patient', mats, PAT_YAW, PATIENT_ANCHOR + rotz((0, 0.10 + 0.23, 0), PAT_YAW)),
            chair_steel('Chair_Visitor', mats, 180 + 15, Vector((-1.2, -1.42, 0))),
            build_corridor(mats)]
    door = build_door(mats)
    anchors = build_anchors()
    return objs, door, anchors


def export(out_dir, objs, door, anchors):
    os.makedirs(out_dir, exist_ok=True)
    keep = objs + [door] + list(door.children) + list(anchors.values())
    bpy.context.view_layer.update()
    for o in bpy.context.view_layer.objects:
        o.select_set(o in keep)
    print('EXPORT selected', len(bpy.context.selected_objects), 'of', len(keep))
    path = os.path.join(out_dir, 'Room_OutpatientConsult.fbx')
    bpy.ops.export_scene.fbx(filepath=path, use_selection=True, object_types={'MESH', 'EMPTY'},
                             apply_unit_scale=True, global_scale=1.0, axis_forward='-Z', axis_up='Y',
                             bake_space_transform=True, use_custom_props=True, mesh_smooth_type='FACE',
                             path_mode='RELATIVE', embed_textures=False, bake_anim=False, add_leaf_bones=False)
    return path


def unity(v):
    return (round(-v.x, 3), round(v.z, 3), round(-v.y, 3))


def report(objs, door, anchors):
    tris = 0
    mats = set()
    for o in objs + list(door.children):
        tris += sum(len(p.vertices) - 2 for p in o.data.polygons)
        mats |= {m.name for m in o.data.materials}
    draw_calls = sum(len(o.data.materials) for o in objs + list(door.children))
    print(f'ROOM tris={tris} materials={len(mats)} {sorted(mats)} draw_calls~{draw_calls}')
    for n, e in anchors.items():
        print(f'ANCHOR {n}: blender={tuple(round(c, 3) for c in e.location)} yaw={math.degrees(e.rotation_euler.z):.1f} '
              f'| unity pos={unity(e.location)} rotY={(-math.degrees(e.rotation_euler.z)) % 360:.1f}')
    print(f'ANCHOR Door (hinge): unity pos={unity(door.location)} (open inward: local Y 0 -> -95)')
    d = (anchors['DoctorAnchor'].location - anchors['KeyLightTarget'].location).length
    print(f'CHECK doctor eye -> patient eye {d:.3f} m; walk spawn->approach '
          f'{(anchors["PatientSpawn"].location - anchors["ChairApproach"].location).length:.3f} m; door centre y={DOOR_Y:.3f}')
    return tris, sorted(mats), draw_calls


# ---------------------------------------------------------------- previews


def previews(out_dir, megane_fbx, anim_dir, anchors, door):
    sc = bpy.context.scene
    pdir = os.path.join(out_dir, 'previews')
    os.makedirs(pdir, exist_ok=True)
    for eng in ('BLENDER_EEVEE', 'BLENDER_EEVEE_NEXT'):
        try:
            sc.render.engine = eng
            break
        except TypeError:
            pass
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = 640, 400, 100
    sc.render.fps = 30
    sc.view_settings.view_transform = 'AgX' if 'AgX' in [i.identifier for i in
                                                          type(sc.view_settings).bl_rna.properties['view_transform'].enum_items] else 'Standard'
    world = sc.world or bpy.data.worlds.new('World')
    sc.world = world
    world.use_nodes = True
    bg = next(n for n in world.node_tree.nodes if n.type == 'BACKGROUND')
    bg.inputs['Color'].default_value = (0.9, 0.92, 1.0, 1)
    bg.inputs['Strength'].default_value = 0.25

    def light(name, kind, loc, energy, color=(1, 0.95, 0.88), size=1.0, rot=None, target=None):
        ld = bpy.data.lights.new(name, kind)
        ld.energy, ld.color = energy, color
        if kind == 'AREA':
            ld.size = size
        if kind == 'SPOT':
            ld.spot_size = math.radians(35)
            ld.spot_blend = 0.6
        lo = bpy.data.objects.new(name, ld)
        sc.collection.objects.link(lo)
        lo.location = loc
        if target is not None:
            lo.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
        elif rot:
            lo.rotation_euler = rot
        return lo
    light('PV_Ceiling1', 'AREA', (0, -0.7, 2.7), 70, size=1.2)
    light('PV_Ceiling2', 'AREA', (0, 0.9, 2.7), 70, size=1.2)
    light('PV_Window', 'AREA', (0.6, ROOM_Y + 0.3, 1.6), 120, color=(0.95, 0.97, 1.0), size=1.4, target=(0.6, 0, 1.0))
    light('PV_Corridor', 'AREA', (-3.4, 0.55, 2.7), 50, size=1.0)
    key = anchors['KeyLightTarget'].location
    light('PV_Key', 'SPOT', key + Vector((1.0, 0.9, 0.9)), 20, target=key)

    # Mégane seated (base_sit_neutral) at PatientAnchor
    def import_char(anim, frame, anchor):
        before = set(bpy.data.objects)
        bpy.ops.import_scene.fbx(filepath=megane_fbx)
        new = [o for o in bpy.data.objects if o not in before]
        arm = next(o for o in new if o.type == 'ARMATURE')
        before = set(bpy.data.objects)
        bpy.ops.import_scene.fbx(filepath=os.path.join(anim_dir, anim + '.fbx'), anim_offset=0.0)
        tmp = [o for o in bpy.data.objects if o not in before]
        act = next(o for o in tmp if o.type == 'ARMATURE').animation_data.action
        for o in tmp:
            bpy.data.objects.remove(o)
        arm.animation_data_create()
        arm.animation_data.action = act
        if act.slots:
            arm.animation_data.action_slot = act.slots[0]
        # the clip also keys the Armature node itself, so place the character through a parent
        holder = bpy.data.objects.new('PV_Holder', None)
        sc.collection.objects.link(holder)
        holder.matrix_world = anchor.matrix_world
        arm.parent = holder
        return new + [holder], arm, frame
    seated, arm_s, f_s = import_char('base_sit_neutral', 0, anchors['PatientAnchor'])
    sc.frame_set(f_s)

    cam = bpy.data.objects.new('PV_Cam', bpy.data.cameras.new('PV_Cam'))
    sc.collection.objects.link(cam)
    sc.camera = cam

    def shot(name, loc, target, lens=20):
        cam.location = loc
        cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
        cam.data.lens = lens
        sc.render.filepath = os.path.join(pdir, name + '.png')
        bpy.ops.render.render(write_still=True)

    doc = anchors['DoctorAnchor']
    look = doc.location + Vector((-1.0, 0.02, -0.10))    # centre between patient, door and corner
    door.rotation_euler.z = math.radians(70)
    shot('doctor_view', doc.location, look, lens=18)
    shot('doctor_view_patient', doc.location, key + Vector((0, 0, -0.25)), lens=35)
    shot('establishing', Vector((1.9, 1.7, 2.45)), Vector((-0.9, -0.7, 0.7)), lens=14)
    shot('corner_from_patient_eye', key + Vector((0, 0, 0.02)), anchors['CornerLookTarget'].location, lens=24)
    for o in seated:
        bpy.data.objects.remove(o)
    # mid-walk in the doorway (walk_in, root at PatientSpawn)
    walker, arm_w, _ = import_char('walk_in', 0, anchors['PatientSpawn'])
    s_door = (Vector((-ROOM_X, DOOR_Y, 0)) - anchors['PatientSpawn'].location).length
    frame = 0
    for f in range(0, 136):
        sc.frame_set(f)
        hip = arm_w.matrix_world @ arm_w.pose.bones['CC_Base_Hip'].head
        if (hip.xy - anchors['PatientSpawn'].location.xy).length >= s_door - 0.1:
            frame = f
            break
    sc.frame_set(frame)
    door.rotation_euler.z = math.radians(95)
    shot('walk_doorway', doc.location, Vector((-ROOM_X, DOOR_Y, 1.1)), lens=24)
    shot('walk_doorway_wide', Vector((1.0, -1.5, 1.7)), Vector((-2.2, 0.8, 1.0)), lens=18)
    door.rotation_euler.z = 0
    print('PREVIEW walk frame at doorway:', frame)


if __name__ == '__main__':
    argv = sys.argv[sys.argv.index('--') + 1:]
    out = argv[0]
    if bpy.app.background:
        bpy.ops.wm.read_factory_settings(use_empty=True)
    objs, door, anchors = build_all(out)
    path = export(out, objs, door, anchors)
    report(objs, door, anchors)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(os.path.abspath(out), 'Room_OutpatientConsult.blend'))
    if '--previews' in argv:
        i = argv.index('--previews')
        previews(out, argv[i + 1], argv[i + 2], anchors, door)
