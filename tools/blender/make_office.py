"""Turn the low-poly office pack (LP_Officeroom2.blend) into the stage 1 consult room and export it for Unity.

Usage (from Med/):
  /Applications/Blender.app/Contents/MacOS/Blender -b art_source/Office/Blender/LP_Officeroom2.blend \
      --python tools/blender/make_office.py -- art/Environments/Office \
      [--previews "art_source/Mégane_Blender/Mégane_Blender.Fbx" art/Animations]

The pack is a two-wall cutaway at about 2x real size. This script scales it to real size, closes the room (two walls,
a door, ceiling, a short corridor) with the pack's own palette texture, moves the desk against the new south wall and turns
the doctor's chair to face the sofa, where the patient sits. Writes Room_Office.fbx, Textures/T_Office_Palette.png,
Room_Office.blend and (with --previews) previews/.

Layout and conventions match make_room.py: +X east, +Y north, Z up, metres; anchors face their local -Y (Unity +Z after export).
"""
import bpy, bmesh, math, os, shutil, sys
from mathutils import Vector, Matrix

S = 0.6                       # pack units -> metres (desk 0.83 m, sofa seat 0.40 m before the stretch below)
FLOOR_Z = 0.12                # pack floor surface height (pack units)
SOFA_STRETCH = 1.125          # raises the sofa seat to 0.45 m, where sit_down lands the hips
X0, X1, Y0, Y1 = -1.434, 1.50, -1.50, 1.434   # interior faces after scaling (west/north are the pack's walls)
H = (4.01 - FLOOR_Z) * S       # pack wall top = ceiling height (2.33 m)
WALL_T = 0.066
DESK_DY = -1.45 * S           # desk group slides south until it touches the new south wall
DOOR_Y0, DOOR_Y1, DOOR_H = 0.20, 1.08, 2.0   # door opening in the east wall
CORR_X1, CORR_Y = 3.4, (-0.4, 2.0)           # corridor east face and north/south faces

SEATED_EYE_LOCAL = Vector((0.005, 0.282, 1.193))  # seated_neutral frame 0, character-local (see make_room.py)
WALK_DIST = 3.3               # spawn -> approach; walk_in travels 3.75 m and the entrance scales stride within +-25%
PAT_Y = 0.18                  # patient on the sofa's north cushion
DOC_CHAIR = Vector((0.45, -0.40, 0))
DOC_EYE_Z = 1.20

DESK_GROUP = ['Office2_table', 'Office2_monitor1', 'Office2_keyboard', 'Office2_Keyboard', 'Office2_mouse', 'Office2_Mouse',
              'Office2_Pens', 'Office2_Photoframe1', 'Office2_Room_Paper', 'Office2_stand']
SOFA_GROUP = ['Office2_sofa', 'Office2_Books2', 'Office2_Books3']


def yaw_dir(yaw):
    a = math.radians(yaw)
    return Vector((math.sin(a), -math.cos(a), 0))


def heading_yaw(d):
    """Yaw that makes local -Y point along d (XY)."""
    return math.degrees(math.atan2(d.x, -d.y))


def rotz(v, yaw):
    return Matrix.Rotation(math.radians(yaw), 3, 'Z') @ Vector(v)


# ---------------------------------------------------------------- pack -> real-size, flat object list

def bake_pack():
    """Unparent every mesh, bake its world transform into the mesh, scale to metres with the floor at z=0."""
    M = Matrix.Scale(S, 4) @ Matrix.Translation((0, 0, -FLOOR_Z))
    objs = [o for o in bpy.data.objects if o.type == 'MESH']
    for o in objs:
        if o.data.users > 1:
            o.data = o.data.copy()
        o.data.transform(M @ o.matrix_world)
        o.data.uv_layers.active.name = 'map1'   # the pack mixes 'map1' and 'UVMap'; join keeps only matching names
        o.parent = None
        o.matrix_world = Matrix.Identity(4)
    for o in [o for o in bpy.data.objects if o.type != 'MESH']:
        bpy.data.objects.remove(o)   # pack camera, lights and root empty
    return {o.name: o for o in objs}


def edit_layout(P):
    for n in DESK_GROUP:
        if n in P:
            P[n].data.transform(Matrix.Translation((0, DESK_DY, 0)))
    for n in SOFA_GROUP:
        P[n].data.transform(Matrix.Diagonal((1, 1, SOFA_STRETCH, 1)))
    chair = P['Office2_chair']
    c = bbox_centre(chair)
    to_pat = patient_eye() - DOC_CHAIR
    to_pat.z = 0
    yaw = heading_yaw(to_pat)                       # the pack chair faces -Y, so its yaw is the heading
    chair.data.transform(Matrix.Translation((DOC_CHAIR.x, DOC_CHAIR.y, 0)) @ Matrix.Rotation(math.radians(yaw), 4, 'Z')
                         @ Matrix.Translation((-c.x, -c.y, 0)))
    return yaw


def bbox_centre(o):
    vs = [v.co for v in o.data.vertices]
    return Vector((sum(v.x for v in vs) / len(vs), sum(v.y for v in vs) / len(vs), 0))


def sofa_front_x(P):
    return max(v.co.x for v in P['Office2_sofa'].data.vertices if v.co.z < 0.47)


# ---------------------------------------------------------------- palette

def palette_uvs(P):
    """UVs of palette cells, taken from faces of the pack itself so new parts match exactly."""
    def face_uv(name, test):
        o = P[name]
        uv = o.data.uv_layers.active.data
        for f in o.data.polygons:
            if test(f):
                return tuple(uv[f.loop_indices[0]].uv)
        raise RuntimeError(f'no face on {name} matched')
    base = 'Office2_base'
    return {
        'wall': face_uv(base, lambda f: f.normal.y < -0.9 and f.center.z > 0.5 and f.center.y > 1.3 and f.area > 1),
        'trim': face_uv(base, lambda f: f.normal.z > 0.9 and f.center.z > H - 0.01),
        'floor': face_uv('Office2_parquet1', lambda f: f.normal.z > 0.9),
        'white': face_uv('Office2_table', lambda f: f.normal.z > 0.9),
        'dark': face_uv('Office2_monitor1', lambda f: True),
        'sofa_base': face_uv('Office2_sofa', lambda f: f.center.z < 0.15 and abs(f.normal.z) < 0.5),
    }


class Builder:
    """Boxes with every face mapped to one palette cell, joined into one object."""

    def __init__(self, name, mat, uvs):
        self.name, self.mat, self.uvs = name, mat, uvs
        self.bm = bmesh.new()
        self.uv = self.bm.loops.layers.uv.new('map1')

    def box(self, lo, hi, cell):
        lo, hi = Vector(lo), Vector(hi)
        r = bmesh.ops.create_cube(self.bm, size=1.0)
        for v in r['verts']:
            v.co = Vector(lo[i] + (v.co[i] + 0.5) * (hi[i] - lo[i]) for i in range(3))
        faces = {f for v in r['verts'] for f in v.link_faces}
        for f in faces:
            for l in f.loops:
                l[self.uv].uv = self.uvs[cell]

    def build(self):
        me = bpy.data.meshes.new(self.name)
        bmesh.ops.recalc_face_normals(self.bm, faces=self.bm.faces)
        self.bm.to_mesh(me)
        self.bm.free()
        me.materials.append(self.mat)
        o = bpy.data.objects.new(self.name, me)
        bpy.context.scene.collection.objects.link(o)
        return o


def build_shell(mat, uvs):
    b = Builder('Office_NewShell', mat, uvs)
    T = WALL_T
    # east wall with the door opening, plus the cornice band the pack's walls have under the ceiling
    b.box((X1, Y0 - T, 0), (X1 + T, DOOR_Y0, H), 'wall')
    b.box((X1, DOOR_Y1, 0), (X1 + T, Y1 + T, H), 'wall')
    b.box((X1, DOOR_Y0, DOOR_H), (X1 + T, DOOR_Y1, H), 'wall')
    b.box((X0 - T, Y0 - T, 0), (X1 + T, Y0, H), 'wall')                       # south wall
    b.box((X0 - T, Y0 - T, H), (X1 + T, Y1 + T, H + 0.04), 'trim')             # ceiling
    b.box((X1 - 0.05, Y0, H - 0.1), (X1, Y1, H), 'trim')                       # cornice east
    b.box((X0, Y0, H - 0.1), (X1, Y0 + 0.05, H), 'trim')                       # cornice south
    b.box((X1 - 0.012, Y0, 0), (X1, DOOR_Y0 - 0.06, 0.07), 'white')            # skirting
    b.box((X1 - 0.012, DOOR_Y1 + 0.06, 0), (X1, Y1, 0.07), 'white')
    b.box((X0, Y0, 0), (X1, Y0 + 0.012, 0.07), 'white')
    for x in (X1 - 0.02, X1 + T):                                              # door casing, both faces
        b.box((x, DOOR_Y0 - 0.06, 0), (x + 0.02, DOOR_Y0, DOOR_H + 0.06), 'white')
        b.box((x, DOOR_Y1, 0), (x + 0.02, DOOR_Y1 + 0.06, DOOR_H + 0.06), 'white')
        b.box((x, DOOR_Y0 - 0.06, DOOR_H), (x + 0.02, DOOR_Y1 + 0.06, DOOR_H + 0.06), 'white')
    b.box((-0.3, -0.3, H - 0.03), (0.3, 0.3, H), 'white')                      # ceiling light panel
    # corridor
    cx0, (cy0, cy1) = X1 + T, CORR_Y
    b.box((cx0, cy0, -0.02), (CORR_X1, cy1, 0), 'floor')
    b.box((CORR_X1, cy0 - T, 0), (CORR_X1 + T, cy1 + T, H), 'wall')
    b.box((cx0, cy0 - T, 0), (CORR_X1, cy0, H), 'wall')
    b.box((cx0, cy1, 0), (CORR_X1, cy1 + T, H), 'wall')
    b.box((cx0, cy0 - T, H), (CORR_X1 + T, cy1 + T, H + 0.04), 'trim')
    b.box((2.3, 0.5, H - 0.03), (2.9, 1.1, H), 'white')
    # waiting bench on the corridor's far wall, out of the walk line
    b.box((CORR_X1 - 0.42, 1.2, 0.42), (CORR_X1, 1.95, 0.46), 'sofa_base')
    for y in (1.25, 1.85):
        b.box((CORR_X1 - 0.38, y, 0), (CORR_X1 - 0.34, y + 0.04, 0.42), 'dark')
    return b.build()


def build_door(mat, uvs):
    """Leaf hinged on the south jamb; +Z rotation (Unity: negative local Y) swings it into the room, clear of desk and chair."""
    hinge = Vector((X1 + WALL_T / 2, DOOR_Y0 + 0.02, 0))
    door = bpy.data.objects.new('Door', None)
    bpy.context.scene.collection.objects.link(door)
    door.empty_display_type = 'ARROWS'
    door.location = hinge
    b = Builder('Door_Leaf', mat, uvs)
    L = DOOR_Y1 - DOOR_Y0 - 0.03
    b.box((-0.02, 0, 0.01), (0.02, L, DOOR_H - 0.01), 'floor')
    for x0, x1 in ((-0.07, -0.02), (0.02, 0.07)):                 # lever handles both faces
        b.box((x0, L - 0.1, 0.98), (x1, L - 0.07, 1.06), 'dark')
        b.box((x0 if x0 < 0 else x1 - 0.015, L - 0.22, 1.0), (x0 + 0.015 if x0 < 0 else x1, L - 0.07, 1.03), 'dark')
    leaf = b.build()
    leaf.parent = door
    return door


def add_wall_art(P):
    """Copy the pack's mountain picture onto the new south wall, above the desk."""
    src = P['Office2_picture']
    o = src.copy()
    o.data = src.data.copy()
    o.name = 'Office2_picture_south'
    bpy.context.scene.collection.objects.link(o)
    c = bbox_centre(src)
    zc = sum(v.co.z for v in src.data.vertices) / len(src.data.vertices)
    # the source hangs on the west wall facing +X; turn it to face +Y and shrink it to fit above the desk
    o.data.transform(Matrix.Translation((0.9, Y0 + 0.02, 1.75)) @ Matrix.Rotation(math.radians(90), 4, 'Z')
                     @ Matrix.Scale(0.7, 4) @ Matrix.Translation((-(X0 + 0.01), -c.y, -zc)))
    return o


# ---------------------------------------------------------------- anchors

def patient_anchor_pos(front_x):
    return Vector((front_x + 0.10, PAT_Y, 0))


PAT_YAW = 90.0   # faces +X, away from the sofa back


def patient_eye():
    return ANCHOR + rotz(SEATED_EYE_LOCAL, PAT_YAW)


def empty(name, pos, yaw=0.0):
    e = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(e)
    e.empty_display_type = 'ARROWS'
    e.empty_display_size = 0.25
    e.location = pos
    e.rotation_euler = (0, 0, math.radians(yaw))
    return e


def build_anchors(chair_yaw):
    doc_eye = DOC_CHAIR + yaw_dir(chair_yaw) * -0.05 + Vector((0, 0, DOC_EYE_Z))
    door_c = Vector((X1 + WALL_T / 2, (DOOR_Y0 + DOOR_Y1) / 2, 0))
    walk = door_c - ANCHOR
    walk.z = 0
    spawn = ANCHOR + walk.normalized() * WALK_DIST
    to_pat = patient_eye() - doc_eye
    to_pat.z = 0
    E = {
        'DoctorAnchor': empty('DoctorAnchor', doc_eye, heading_yaw(to_pat)),
        'PatientAnchor': empty('PatientAnchor', ANCHOR, PAT_YAW),
        'ChairApproach': empty('ChairApproach', ANCHOR, PAT_YAW),
        'PatientSpawn': empty('PatientSpawn', spawn, heading_yaw(-walk)),
        'CornerLookTarget': empty('CornerLookTarget', Vector((0.4, Y1 - 0.25, 0.9))),   # shelves, away from the doctor
        'SoundSource_Door': empty('SoundSource_Door', door_c + Vector((0, 0, 1.1))),
        'SoundSource_Corridor': empty('SoundSource_Corridor', Vector(((X1 + CORR_X1) / 2, sum(CORR_Y) / 2, 1.6))),
        'KeyLightTarget': empty('KeyLightTarget', patient_eye()),
    }
    return E


# ---------------------------------------------------------------- export

def setup_material(out_dir, P):
    tex_dir = os.path.join(out_dir, 'Textures')
    os.makedirs(tex_dir, exist_ok=True)
    mat = P['Office2_base'].data.materials[0]
    mat.name = 'M_Office_Palette'
    img = next(n.image for n in mat.node_tree.nodes if n.type == 'TEX_IMAGE')
    dst = os.path.join(tex_dir, 'T_Office_Palette.png')
    shutil.copyfile(os.path.normpath(bpy.path.abspath(img.filepath)), dst)  # pack path runs through a missing FBX/ folder
    img.filepath = dst
    img.name = 'T_Office_Palette'
    for n in [n for n in mat.node_tree.nodes if n.type == 'NORMAL_MAP']:
        mat.node_tree.nodes.remove(n)   # unused, no normal texture in the pack
    for m in [m for m in bpy.data.materials if m.users == 0]:
        bpy.data.materials.remove(m)
    return mat


def join(name, objs):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    objs[0].name = objs[0].data.name = name
    return objs[0]


def export(out_dir, objs, door, anchors):
    keep = objs + [door] + list(door.children) + list(anchors.values())
    bpy.context.view_layer.update()
    for o in bpy.context.view_layer.objects:
        o.select_set(o in keep)
    path = os.path.join(out_dir, 'Room_Office.fbx')
    bpy.ops.export_scene.fbx(filepath=path, use_selection=True, object_types={'MESH', 'EMPTY'},
                             apply_unit_scale=True, global_scale=1.0, axis_forward='-Z', axis_up='Y',
                             bake_space_transform=True, mesh_smooth_type='FACE',
                             path_mode='RELATIVE', embed_textures=False, bake_anim=False, add_leaf_bones=False)
    return path


def unity(v):
    return (round(-v.x, 3), round(v.z, 3), round(-v.y, 3))


def report(objs, door, anchors):
    tris = sum(len(p.vertices) - 2 for o in objs + list(door.children) for p in o.data.polygons)
    print(f'ROOM tris={tris} objects={[o.name for o in objs]}')
    for n, e in anchors.items():
        print(f'ANCHOR {n}: blender={tuple(round(c, 3) for c in e.location)} yaw={math.degrees(e.rotation_euler.z):.1f} '
              f'| unity pos={unity(e.location)} rotY={(-math.degrees(e.rotation_euler.z)) % 360:.1f}')
    d = (anchors['DoctorAnchor'].location - anchors['KeyLightTarget'].location).length
    w = (anchors['PatientSpawn'].location - anchors['ChairApproach'].location).length
    print(f'CHECK doctor eye -> patient eye {d:.3f} m; walk spawn->approach {w:.3f} m')
    assert 1.2 < d < 1.7, d
    assert 0.75 * 3.75 <= w <= 3.75, w


# ---------------------------------------------------------------- previews

def previews(out_dir, megane_fbx, anim_dir, anchors, door):
    sc = bpy.context.scene
    pdir = os.path.join(out_dir, 'previews')
    os.makedirs(pdir, exist_ok=True)
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = 800, 450, 100
    world = sc.world or bpy.data.worlds.new('World')
    sc.world = world
    world.use_nodes = True
    bg = next(n for n in world.node_tree.nodes if n.type == 'BACKGROUND')
    bg.inputs['Strength'].default_value = 0.3

    def light(name, kind, loc, energy, size=1.0):
        ld = bpy.data.lights.new(name, kind)
        ld.energy = energy
        if kind == 'AREA':
            ld.size = size
        lo = bpy.data.objects.new(name, ld)
        sc.collection.objects.link(lo)
        lo.location = loc
    light('PV_Ceiling', 'AREA', (0, 0, H - 0.05), 150, size=0.6)
    light('PV_Fill', 'POINT', (0.8, 0.6, 1.8), 40)
    light('PV_Corridor', 'AREA', (2.6, 0.8, H - 0.05), 60, size=0.6)

    def import_char(anim, anchor):
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
        holder = bpy.data.objects.new('PV_Holder', None)   # the clip keys the armature node, so place through a parent
        sc.collection.objects.link(holder)
        holder.matrix_world = anchor.matrix_world
        arm.parent = holder
        return new + [holder], arm

    cam = bpy.data.objects.new('PV_Cam', bpy.data.cameras.new('PV_Cam'))
    sc.collection.objects.link(cam)
    sc.camera = cam

    def shot(name, loc, target, lens=20):
        cam.location = loc
        cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
        cam.data.lens = lens
        sc.render.filepath = os.path.join(pdir, name + '.png')
        bpy.ops.render.render(write_still=True)

    seated, _ = import_char('base_sit_neutral', anchors['PatientAnchor'])
    sc.frame_set(0)
    doc = anchors['DoctorAnchor'].location
    eye = anchors['KeyLightTarget'].location
    shot('doctor_view', doc, eye + Vector((0, 0, -0.35)), lens=22)
    shot('doctor_view_patient', doc, eye + Vector((0, 0, -0.25)), lens=35)
    shot('establishing', Vector((1.3, -1.35, 2.2)), Vector((-0.6, 0.4, 0.6)), lens=14)
    shot('from_patient', eye, doc, lens=20)
    for o in seated:
        bpy.data.objects.remove(o)
    walker, arm = import_char('walk_in', anchors['PatientSpawn'])
    door_x = X1 + WALL_T / 2
    for f in range(0, 136):
        sc.frame_set(f)
        hip = arm.matrix_world @ arm.pose.bones['CC_Base_Hip'].head
        if hip.x <= door_x + 0.1:
            break
    door.rotation_euler.z = math.radians(95)
    shot('walk_doorway', doc, Vector((X1, 0.6, 1.1)), lens=22)
    door.rotation_euler.z = 0


# ---------------------------------------------------------------- main

if __name__ == '__main__':
    argv = sys.argv[sys.argv.index('--') + 1:]
    out = os.path.abspath(argv[0])
    os.makedirs(out, exist_ok=True)
    P = bake_pack()
    ANCHOR = patient_anchor_pos(sofa_front_x(P))
    mat = setup_material(out, P)
    chair_yaw = edit_layout(P)
    uvs = palette_uvs(P)
    shell = build_shell(mat, uvs)
    add_wall_art(P)
    door = build_door(mat, uvs)
    chair = P.pop('Office2_chair')
    chair.name = chair.data.name = 'Chair_Doctor'
    static = join('Office_Static', [o for o in bpy.data.objects if o.type == 'MESH' and o not in (chair, shell)
                                    and o.parent is None])
    anchors = build_anchors(chair_yaw)
    objs = [static, shell, chair]
    export(out, objs, door, anchors)
    report(objs, door, anchors)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, 'Room_Office.blend'))
    if '--previews' in argv:
        i = argv.index('--previews')
        previews(out, argv[i + 1], argv[i + 2], anchors, door)
