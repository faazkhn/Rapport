"""Author PsychSim's Phase A clips on the CC3 skeleton and write the face preset JSONs.

Usage (from Med/):
  # build clips, face JSONs and preview stills, then re-import and check every FBX
  /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup --python tools/blender/make_clips.py -- \
      "art_source/Mégane_Blender/Mégane_Blender.Fbx" art/Animations [--previews]
  /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup --python tools/blender/make_clips.py -- \
      verify "art_source/Mégane_Blender/Mégane_Blender.Fbx" art/Animations

Everything is generated from code: poses are functions of time, solved with a small analytic
2-bone IK (legs and arms), sampled every frame at 30 fps, keyed as plain FK on the CC_Base_* bones
and exported one FBX per clip (armature only). Conventions used below ("armature axes"):
  +X = character's left, -Y = character's forward, +Z = up; positions in metres, world space.
  A 'rot' entry (rx, ry, rz) in degrees rotates that bone about armature axes, carried by its parent.
  Spine/neck/head: +rx bends forward, +ry tilts to her left, +rz turns to her left.
"""
import bpy, sys, os, json, math
from mathutils import Vector, Matrix, Euler, Quaternion

FPS = 30
REST_FRAME = -10
CM = 100.0  # armature space is centimetres (armature object scale 0.01)

# ---------------------------------------------------------------- rig


class Rig:
    def __init__(self, arm):
        self.arm = arm
        self.bones = [b.name for b in arm.data.bones]  # parents come before children
        self.parent = {b.name: (b.parent.name if b.parent else None) for b in arm.data.bones}
        self.rest = {b.name: b.matrix_local.copy() for b in arm.data.bones}
        self.R0 = {n: m.to_3x3() for n, m in self.rest.items()}
        self.rel = {}
        for n, p in self.parent.items():
            self.rel[n] = (self.rest[p].inverted() @ self.rest[n]) if p else self.rest[n].copy()
        self.children = {n: [c for c, p in self.parent.items() if p == n] for n in self.bones}

    def head(self, n):  # rest head, metres
        return self.rest[n].translation / CM

    def fk(self, basis, pose=None, start=None):
        """pose[name] = armature-space 4x4 (cm). Recomputes `start` and its descendants (or all)."""
        pose = {} if pose is None else pose
        order = self.bones if start is None else self._subtree(start)
        for n in order:
            p = self.parent[n]
            base = (pose[p] @ self.rel[n]) if p else self.rel[n]
            pose[n] = base @ basis[n]
        return pose

    def _subtree(self, n):
        out, stack = [], [n]
        while stack:
            b = stack.pop(0)
            out.append(b)
            stack.extend(self.children[b])
        return out

    def set_world_rot(self, basis, pose, n, R3):
        """Make bone n have armature-space orientation R3 (3x3) keeping its head; updates subtree."""
        p = self.parent[n]
        base = pose[p] @ self.rel[n]
        target = Matrix.Translation(pose[n].translation) @ R3.to_4x4()
        basis[n] = base.inverted() @ target
        self.fk(basis, pose, n)


def frame_align(u0, n0, u, n):
    """Rotation taking orthonormal frame (u0, n0) to (u, n)."""
    def basis(a, b):
        a = a.normalized()
        b = (b - a * a.dot(b)).normalized()
        return Matrix((a, b, a.cross(b))).transposed()
    return basis(u, n) @ basis(u0, n0).transposed()


def eul(r):
    return Euler([math.radians(v) for v in r], 'XYZ').to_matrix()


# ---------------------------------------------------------------- animation curves


def track(keys, period=None, tension=0.0):
    """Cardinal spline through (t, value) keys; values are floats or tuples. Ends ease (zero slope)
    unless `period` is given, in which case the curve wraps seamlessly."""
    keys = sorted(keys, key=lambda k: k[0])
    ts = [k[0] for k in keys]
    vs = [k[1] if isinstance(k[1], (tuple, list)) else (k[1],) for k in keys]
    scalar = not isinstance(keys[0][1], (tuple, list))
    dim = len(vs[0])
    n = len(keys)

    def tangent(i):
        if period:
            ip, inx = (i - 1) % n, (i + 1) % n
            tp = ts[ip] - (period if ip > i else 0)
            tn = ts[inx] + (period if inx < i else 0)
        else:
            if i == 0 or i == n - 1:
                return (0.0,) * dim
            ip, inx, tp, tn = i - 1, i + 1, ts[i - 1], ts[i + 1]
        return tuple((1 - tension) * (vs[inx][d] - vs[ip][d]) / (tn - tp) for d in range(dim))

    tans = [tangent(i) for i in range(n)]

    def f(t):
        if period:
            t = ts[0] + ((t - ts[0]) % period)
        if t <= ts[0] and not period:
            out = vs[0]
        elif t >= ts[-1] and not period:
            out = vs[-1]
        else:
            i = max(j for j in range(n) if ts[j] <= t)
            j = (i + 1) % n
            t0, t1 = ts[i], (ts[j] if j > i else ts[j] + period)
            h = t1 - t0
            s = (t - t0) / h
            h00, h10, h01, h11 = 2*s**3 - 3*s**2 + 1, s**3 - 2*s**2 + s, -2*s**3 + 3*s**2, s**3 - s**2
            out = tuple(h00*vs[i][d] + h10*h*tans[i][d] + h01*vs[j][d] + h11*h*tans[j][d] for d in range(dim))
        return out[0] if scalar else out
    return f


def wave(t, period, amp, phase=0.0):
    return amp * math.sin(2 * math.pi * (t / period + phase))


def bump(t, t0, t1, ease=0.25):
    """0 -> 1 -> 0 smooth window over [t0, t1] with eased edges (fraction `ease` of the span)."""
    if t <= t0 or t >= t1:
        return 0.0
    e = (t1 - t0) * ease
    def ss(x):
        x = max(0.0, min(1.0, x))
        return x * x * x * (x * (6 * x - 15) + 10)
    return min(ss((t - t0) / e), ss((t1 - t) / e))


def add(*vs):
    return tuple(sum(c) for c in zip(*vs))


def scale(v, k):
    return tuple(c * k for c in v)


def lerp(a, b, s):
    if isinstance(a, (tuple, list)):
        return tuple(x + (y - x) * s for x, y in zip(a, b))
    return a + (b - a) * s


def smooth(s):
    s = max(0.0, min(1.0, s))
    return s * s * (3 - 2 * s)


# ---------------------------------------------------------------- solver

B = 'CC_Base_'
FINGERS = ('Thumb', 'Index', 'Mid', 'Ring', 'Pinky')
JOINT_W = {'Thumb': (0.35, 0.8, 0.8)}  # share of the curl per joint
DEFAULT_W = (0.75, 1.1, 0.8)


class Solver:
    def __init__(self, rig):
        self.rig = rig
        r = rig
        self.limb = {}
        for side in 'LR':
            for kind, (a, b, c, q0) in {'leg': ('Thigh', 'Calf', 'Foot', Vector((0, -1, 0))),
                                        'arm': ('Upperarm', 'Forearm', 'Hand', Vector((0, 1, 0)))}.items():
                A, Bn, C = (B + side + '_' + x for x in (a, b, c))
                S0, E0, W0 = (r.rest[x].translation for x in (A, Bn, C))
                u0, f0 = (E0 - S0).normalized(), (W0 - E0).normalized()
                n0 = u0.cross(-q0).normalized()
                self.limb[side + kind] = dict(bones=(A, Bn, C), l1=(E0 - S0).length, l2=(W0 - E0).length,
                                              u0=u0, f0=f0, n0=n0)
            H = B + side + '_Hand'
            D0 = (r.rest[B + side + '_Mid1'].translation - r.rest[H].translation).normalized()
            k = r.rest[B + side + '_Pinky1'].translation - r.rest[B + side + '_Index1'].translation
            N0 = D0.cross(k).normalized()
            if N0.z > 0:
                N0 = -N0
            self.limb[side + 'arm'].update(D0=D0, N0=N0)
            # finger curl axes (rest armature space): rotate the finger toward the palm
            ax = {}
            for f in FINGERS:
                j1 = r.rest[B + side + '_' + f + '1']
                j3 = r.rest[B + side + '_' + f + '3']
                d = (j3.translation - j1.translation).normalized()
                ax[f] = d.cross(N0).normalized()
            self.limb[side + 'arm']['curl_axis'] = ax

    def solve(self, P):
        r = self.rig
        I = Matrix.Identity(4)
        basis = {n: I.copy() for n in r.bones}

        def setrot(n, R3):
            R0 = r.R0[n]
            basis[n] = (R0.transposed() @ R3 @ R0).to_4x4()

        for n, rot in P.get('rot', {}).items():
            setrot(B + n, eul(rot))
        hip = B + 'Hip'
        if 'hip' in P:
            delta = (Vector(P['hip']) - r.head(hip)) * CM
            basis[hip] = Matrix.Translation(r.R0[hip].transposed() @ delta) @ basis[hip]
        for side, fs in P.get('fingers', {}).items():
            ax = self.limb[side + 'arm']['curl_axis']
            for f in FINGERS:
                c = fs.get(f, 0.0)
                spread = fs.get(f + '_spread', 0.0)
                w = JOINT_W.get(f, DEFAULT_W)
                for j in range(3):
                    R = Matrix.Rotation(math.radians(c * w[j]), 3, ax[f])
                    if j == 0 and spread:
                        R = Matrix.Rotation(math.radians(spread), 3, self.limb[side + 'arm']['N0']) @ R
                    if j == 0 and f == 'Thumb' and fs.get('Thumb_in'):
                        D0 = self.limb[side + 'arm']['D0']
                        R = Matrix.Rotation(math.radians(fs['Thumb_in'] * (1 if side == 'L' else -1)), 3, D0) @ R
                    setrot(f'{B}{side}_{f}{j + 1}', R)
        pose = r.fk(basis)
        for side in 'LR':
            for kind in ('leg', 'arm'):
                spec = P.get(kind + 's', {}).get(side)
                if spec:
                    self._ik(basis, pose, self.limb[side + kind], spec, kind)
        return basis, pose

    def _ik(self, basis, pose, L, spec, kind):
        r = self.rig
        A, Bn, C = L['bones']
        l1, l2 = L['l1'], L['l2']
        S = pose[A].translation.copy()
        W = Vector(spec['target']) * CM
        Pl = Vector(spec['pole']) * CM
        dv = W - S
        d = min(max(dv.length, abs(l1 - l2) + 1e-3), (l1 + l2) * 0.9995)
        w = dv.normalized()
        q = (Pl - S) - w * (Pl - S).dot(w)
        q.normalize()
        a = (l1 * l1 - l2 * l2 + d * d) / (2 * d)
        h = math.sqrt(max(l1 * l1 - a * a, 0.0))
        E = S + w * a + q * h
        Wc = S + w * d
        u, f = (E - S).normalized(), (Wc - E).normalized()
        n = u.cross(-q).normalized()
        r.set_world_rot(basis, pose, A, frame_align(L['u0'], L['n0'], u, n) @ r.R0[A])
        r.set_world_rot(basis, pose, Bn, frame_align(L['f0'], L['n0'], f, n) @ r.R0[Bn])
        if kind == 'leg':
            r.set_world_rot(basis, pose, C, eul(spec.get('rot', (0, 0, 0))) @ r.R0[C])
            return
        # hand: absolute orientation from fingers direction D and palm normal N; half the
        # roll goes into the forearm (what Unity's default Fore Arm Twist 0.5 does)
        Rh = frame_align(L['D0'], L['N0'], Vector(spec['D']), Vector(spec['N'])) @ r.R0[C]
        Rf = pose[Bn].to_3x3().normalized()
        Rrel = r.rel[C].to_3x3()
        dq = (Rh @ (Rf @ Rrel).transposed()).to_quaternion()
        axis = Rf.col[1].normalized()
        proj = axis * Vector((dq.x, dq.y, dq.z)).dot(axis)
        tw = Quaternion((dq.w, proj.x, proj.y, proj.z)).normalized()
        tw = Quaternion(tw.axis, tw.angle * 0.5) if tw.angle > 1e-6 else Quaternion()
        r.set_world_rot(basis, pose, Bn, tw.to_matrix() @ Rf)
        r.set_world_rot(basis, pose, C, Rh)


# ---------------------------------------------------------------- keys and export


def bake(rig, solver, name, fn, frames, loop=False):
    """Sample fn(t) on frames 0..frames (inclusive) and key every bone. Returns the action."""
    arm = rig.arm
    act = bpy.data.actions.new(name)
    act.use_fake_user = True
    arm.animation_data_create()
    arm.animation_data.action = act
    samples = {n: [] for n in rig.bones}
    locs = []
    prev = {}
    for i in range(frames + 1):
        t = i / FPS
        if loop and i == frames:
            t = 0.0  # last frame repeats the first exactly
        basis, _ = solver.solve(fn(t))
        for n in rig.bones:
            q = basis[n].to_quaternion()
            if n in prev and prev[n].dot(q) < 0:
                q.negate()
            prev[n] = q
            samples[n].append(q)
        locs.append(basis[B + 'Hip'].translation.copy())
    # a rest-pose key at REST_FRAME (outside the exported range): export_fbx() stands on it so the
    # FBX node transforms (Unity's default pose for the avatar) are the A-pose, not a seated pose
    def put(fc, values, rest_value):
        co = [REST_FRAME, rest_value] + [v for i, x in enumerate(values) for v in (i, x)]
        fc.keyframe_points.add(frames + 2)
        fc.keyframe_points.foreach_set('co', co)
        fc.keyframe_points.foreach_set('interpolation', [0] + [1] * (frames + 1))  # LINEAR between baked frames
        fc.update()
    for n in rig.bones:
        arm.pose.bones[n].rotation_mode = 'QUATERNION'
        for k in range(4):
            fc = act.fcurve_ensure_for_datablock(arm, f'pose.bones["{n}"].rotation_quaternion', index=k)
            put(fc, [q[k] for q in samples[n]], 1.0 if k == 0 else 0.0)
    for k in range(3):
        fc = act.fcurve_ensure_for_datablock(arm, f'pose.bones["{B}Hip"].location', index=k)
        put(fc, [l[k] for l in locs], 0.0)
    return act


def export_fbx(arm, act, path):
    sc = bpy.context.scene
    arm.animation_data.action = act
    sc.frame_start, sc.frame_end = 0, int(act.frame_range[1])
    sc.frame_set(REST_FRAME)
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    sc.name = act.name  # the FBX take (Unity clip) is named after the scene
    bpy.ops.export_scene.fbx(filepath=path, use_selection=True, object_types={'ARMATURE'},
                             add_leaf_bones=False, bake_anim=True, bake_anim_use_all_actions=False,
                             bake_anim_use_nla_strips=False, bake_anim_force_startend_keying=True,
                             bake_anim_simplify_factor=0.0, bake_anim_step=1.0,
                             apply_unit_scale=True, global_scale=1.0, axis_forward='-Z', axis_up='Y')
    sc.name = 'Scene'


# ---------------------------------------------------------------- reference chair and previews

SEAT_H = 0.45
SEAT_FRONT_Y = 0.10   # seat front edge, metres behind the character origin (she faces -Y)
SEAT_DEPTH = 0.46


def build_chair():
    if 'REF_Chair' in bpy.data.objects:
        return bpy.data.objects['REF_Chair']
    import bmesh
    me = bpy.data.meshes.new('REF_Chair')
    bm = bmesh.new()

    def box(cx, cy, cz, sx, sy, sz):
        m = Matrix.Translation((cx, cy, cz)) @ Matrix.Diagonal((sx, sy, sz, 1))
        bmesh.ops.create_cube(bm, size=1.0, matrix=m)
    y0, d, w = SEAT_FRONT_Y, SEAT_DEPTH, 0.48
    box(0, y0 + d / 2, SEAT_H - 0.025, w, d, 0.05)                 # seat, top at 0.45
    box(0, y0 + d - 0.02, SEAT_H + 0.22, w, 0.04, 0.44)            # backrest
    for sx in (-1, 1):
        for yy in (y0 + 0.03, y0 + d - 0.03):
            box(sx * (w / 2 - 0.03), yy, (SEAT_H - 0.05) / 2, 0.04, 0.04, SEAT_H - 0.05)
    bm.to_mesh(me)
    ob = bpy.data.objects.new('REF_Chair', me)
    bpy.context.scene.collection.objects.link(ob)
    mat = bpy.data.materials.new('REF_Chair')
    mat.diffuse_color = (0.35, 0.45, 0.6, 1)
    me.materials.append(mat)
    return ob


def setup_preview(scene):
    for eng in ('BLENDER_WORKBENCH',):
        try:
            scene.render.engine = eng
        except TypeError as e:
            print(e)
    sh = scene.display.shading
    sh.light = 'STUDIO'
    sh.color_type = 'TEXTURE'
    sh.show_shadows = True
    sh.show_cavity = False
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = 'PNG'
    if 'REF_Floor' not in bpy.data.objects:
        bpy.ops.mesh.primitive_plane_add(size=8)
        bpy.context.active_object.name = 'REF_Floor'
    if 'REF_Cam' not in bpy.data.objects:
        cam = bpy.data.objects.new('REF_Cam', bpy.data.cameras.new('REF_Cam'))
        scene.collection.objects.link(cam)
    scene.camera = bpy.data.objects['REF_Cam']


VIEWS = {'front': Vector((0, -1, 0.08)), 'threeq': Vector((-0.75, -0.7, 0.15)),
         'side': Vector((-1, 0, 0.03)), 'face': Vector((0, -1, 0.0)), 'face34': Vector((-0.6, -0.8, 0.05))}


def render_views(path, target, views=('front', 'threeq', 'side'), size=(320, 400), ortho=1.9):
    """Render each view of `target` (world point) and save them side by side as one PNG."""
    import numpy as np
    sc = bpy.context.scene
    cam = bpy.data.objects['REF_Cam']
    cam.data.type = 'ORTHO'
    cam.data.ortho_scale = ortho
    sc.render.resolution_x, sc.render.resolution_y = size
    sc.render.resolution_percentage = 100
    tiles = []
    tmp = path + '.tmp.png'
    for v in views:
        d = VIEWS[v].normalized()
        cam.location = Vector(target) + d * 6
        cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
        sc.render.filepath = tmp
        bpy.ops.render.render(write_still=True)
        img = bpy.data.images.load(tmp)
        a = np.array(img.pixels[:], dtype=np.float32).reshape(size[1], size[0], 4)
        bpy.data.images.remove(img)
        tiles.append(a)
    os.remove(tmp)
    sheet = np.concatenate(tiles, axis=1)
    h, w = sheet.shape[:2]
    out = bpy.data.images.new('sheet', w, h, alpha=True)
    out.pixels.foreach_set(sheet.ravel())
    out.filepath_raw = path
    out.file_format = 'PNG'
    out.save()
    bpy.data.images.remove(out)


# ---------------------------------------------------------------- shared poses

SEAT_HIP = (0.0, 0.40, 0.569)       # CC_Base_Hip head when seated: buttocks rest on the 0.45 m seat
LEGS_SEATED = {'L': {'target': (0.11, -0.16, 0.155), 'pole': (0.13, -1.0, 0.5), 'rot': (0, 0, 4)},
               'R': {'target': (-0.12, -0.12, 0.155), 'pole': (-0.13, -1.0, 0.5), 'rot': (0, 0, -3)}}
STAND_HIP_Z = 1.047                 # 1 cm below rest: knees soft, not locked
FINGERS_RELAXED = {'L': {'Thumb': 14, 'Index': 18, 'Mid': 24, 'Ring': 29, 'Pinky': 34, 'Index_spread': 2},
                   'R': {'Thumb': 16, 'Index': 21, 'Mid': 26, 'Ring': 30, 'Pinky': 36, 'Pinky_spread': -2}}
# hands loosely together in the lap; both seated bases share this layout so the Hands-mask cue fits either
LAP = {'L': {'target': (0.09, 0.17, 0.665), 'pole': (0.6, 0.6, 0.6), 'D': (-0.6, -0.75, -0.25), 'N': (-0.45, 0, -1)},
       'R': {'target': (-0.085, 0.145, 0.675), 'pole': (-0.6, 0.6, 0.6), 'D': (0.55, -0.8, -0.2), 'N': (0.45, 0, -1)}}
LAP_SLUMP = {'L': {'target': (0.08, 0.11, 0.65), 'pole': (0.5, 0.6, 0.45), 'D': (-0.65, -0.65, -0.3), 'N': (-0.4, 0, -1)},
             'R': {'target': (-0.07, 0.085, 0.665), 'pole': (-0.5, 0.6, 0.45), 'D': (0.6, -0.7, -0.3), 'N': (0.4, 0, -1)}}


def copy_pose(P):
    return json.loads(json.dumps(P))


def addrot(P, extra, k=1.0):
    rot = P.setdefault('rot', {})
    for n, v in extra.items():
        rot[n] = add(rot.get(n, (0, 0, 0)), scale(v, k))
    return P


def breath(t, period):
    """0..1 breathing curve: quicker inhale (40 %), longer exhale; periodic and smooth."""
    x = (t / period) % 1.0
    return smooth(x / 0.4) if x < 0.4 else 1.0 - smooth((x - 0.4) / 0.6)


def seated_neutral(t):
    L = 8.0
    b = breath(t, 4.0)
    sw = math.sin(2 * math.pi * t / L)
    P = {'hip': add(SEAT_HIP, (0.004 * math.sin(2 * math.pi * (t / L - 0.05)), 0, 0)),
         'rot': {'Hip': (0, 0.9 * sw, 0.7 * math.sin(2 * math.pi * (t / L + 0.3))),
                 'Waist': (2 - 0.3 * b, -0.5 * math.sin(2 * math.pi * (t / L - 0.06)), 0),
                 'Spine01': (3 - 0.6 * b, -0.3 * math.sin(2 * math.pi * (t / L - 0.10)), 0.4 * math.sin(2 * math.pi * (t / L + 0.4))),
                 'Spine02': (2 - 0.9 * b, -0.2 * math.sin(2 * math.pi * (t / L - 0.14)), 0.5 * math.sin(2 * math.pi * (t / L + 0.45))),
                 'NeckTwist01': (2 + 0.4 * b, 0, 0),
                 'NeckTwist02': (0.3 * b, -0.4 * math.sin(2 * math.pi * (t / L - 0.2)), 0),
                 'Head': (6 + 0.3 * b + 1.2 * math.sin(2 * math.pi * (t / L + 0.15)) ** 2,
                          -0.6 * math.sin(2 * math.pi * (t / L - 0.25)) + 1.8 * bump(t, 4.6, 7.4),
                          1.8 * math.sin(2 * math.pi * (t / L + 0.6))),
                 'L_Clavicle': (0, -1.3 * b, -3), 'R_Clavicle': (0, 1.0 * b, 3)},
         'legs': copy_pose(LEGS_SEATED), 'arms': copy_pose(LAP), 'fingers': copy_pose(FINGERS_RELAXED)}
    # a small settle forward around 2-3.6 s, overlapping down the spine
    for n, d, k in (('Waist', 0.0, 0.6), ('Spine01', 0.08, 0.8), ('Spine02', 0.16, 0.6), ('Head', 0.3, -0.8)):
        addrot(P, {n: (1.6 * bump(t, 2.0 + d, 3.6 + d), 0, 0)}, k)
    # right hand slides a little on the thigh, fingers drift
    s = bump(t, 4.4, 6.6, 0.4)
    P['arms']['R']['target'] = add(P['arms']['R']['target'], (0.006 * s, -0.012 * s, 0.003 * s))
    P['arms']['R']['D'] = add(P['arms']['R']['D'], (0, -0.08 * s, 0))
    for side, ph in (('L', 0.0), ('R', 0.35)):
        for f, k in (('Index', 1.0), ('Mid', 0.7), ('Ring', 0.5), ('Pinky', 0.6), ('Thumb', 0.5)):
            P['fingers'][side][f] += 3.0 * k * math.sin(2 * math.pi * (t / L + ph + 0.05 * k))
    P['fingers']['R']['Index'] += 7 * bump(t, 5.0, 5.9)
    return P


def seated_slumped(t):
    L = 10.0
    sigh = bump(t, 5.2, 9.0, 0.35)
    b = breath(t, 5.0) * (1 + 0.9 * sigh)
    sw = math.sin(2 * math.pi * t / L)
    P = {'hip': add(SEAT_HIP, (0.003 * math.sin(2 * math.pi * (t / L - 0.05)), -0.02, -0.008)),
         'rot': {'Hip': (10, 0.7 * sw, 0.6 * math.sin(2 * math.pi * (t / L + 0.3))),
                 'Waist': (6 - 0.3 * b, -0.4 * math.sin(2 * math.pi * (t / L - 0.06)), 0),
                 'Spine01': (9 - 0.6 * b, -0.2 * math.sin(2 * math.pi * (t / L - 0.1)), 0.3 * math.sin(2 * math.pi * (t / L + 0.4))),
                 'Spine02': (9 - 0.8 * b, 0, 0.4 * math.sin(2 * math.pi * (t / L + 0.45))),
                 'NeckTwist01': (6 + 0.3 * b, 0, 0),
                 'NeckTwist02': (3 + 0.2 * b, -0.4 * math.sin(2 * math.pi * (t / L - 0.2)), 0),
                 'Head': (4 + 0.4 * b - 2.0 * bump(t, 5.6, 8.0), 2.0 - 0.8 * math.sin(2 * math.pi * (t / L - 0.25)),
                          -2.5 + 1.2 * math.sin(2 * math.pi * (t / L + 0.6))),
                 'L_Clavicle': (0, 4 - 1.4 * b, -10), 'R_Clavicle': (0, -4 + 1.1 * b, 10)},
         'legs': copy_pose(LEGS_SEATED), 'arms': copy_pose(LAP_SLUMP), 'fingers': copy_pose(FINGERS_RELAXED)}
    for side, ph in (('L', 0.1), ('R', 0.55)):
        for f, k in (('Index', 1.0), ('Mid', 0.8), ('Ring', 0.6), ('Pinky', 0.6), ('Thumb', 0.6)):
            P['fingers'][side][f] += 6 + 2.5 * k * math.sin(2 * math.pi * (t / L + ph + 0.05 * k))
    return P


ANKLE_REST = {'L': (0.0749, 0.0267, 0.1552), 'R': (-0.0749, 0.0267, 0.1552)}


def stand_pose(t, y0=0.0):
    """Relaxed standing, feet together, at y offset y0 (used at the end of walk_in and start of sit_down)."""
    b = breath(t, 4.0)
    P = {'hip': (0.0, y0, STAND_HIP_Z),
         'rot': {'Waist': (1 - 0.3 * b, 0, 0), 'Spine01': (1.5 - 0.5 * b, 0, 0), 'Spine02': (1 - 0.7 * b, 0, 0),
                 'NeckTwist01': (4 + 0.4 * b, 0, 0), 'Head': (6 + 0.3 * b, 1.0, 0),
                 'L_Clavicle': (0, -1.0 * b, -3), 'R_Clavicle': (0, 0.8 * b, 3)},
         'legs': {s: {'target': add(ANKLE_REST[s], (0, y0, 0)), 'pole': (0.2 * (1 if s == 'L' else -1), y0 - 1.0, 0.5),
                      'rot': (0, 0, 3 if s == 'L' else -3)} for s in 'LR'},
         'arms': {s: hang_arm(s, (0.0, y0, STAND_HIP_Z), 0.0, 0.0) for s in 'LR'},
         'fingers': copy_pose(FINGERS_RELAXED)}
    return P


def hang_arm(side, hip, swing, yaw):
    """Hand hanging by the thigh; swing +1 = forward. Offsets are taken relative to the hips."""
    sx = 1 if side == 'L' else -1
    R = Matrix.Rotation(math.radians(yaw), 3, 'Z')
    off = Vector((sx * 0.212, -0.02 - 0.11 * swing, -0.045 + 0.025 * swing * swing + 0.01 * max(swing, 0)))
    tgt = Vector(hip) + R @ off
    pole = Vector(hip) + R @ Vector((sx * 0.45, 0.6, 0.35))
    D = R @ Vector((sx * 0.03, -0.12 - 0.3 * swing, -1))
    N = R @ Vector((-sx, 0.35, 0.0))
    return {'target': tuple(tgt), 'pole': tuple(pole), 'D': tuple(D), 'N': tuple(N)}


# ---- walk_in: ~3.75 m toward -Y, root motion on the hips

WALK_STEPS = [  # foot, lift-off, landing, landing y
    ('R', 0.14, 0.58, -0.38),
    ('L', 0.68, 1.10, -0.96),
    ('R', 1.21, 1.63, -1.54),
    ('L', 1.74, 2.16, -2.12),
    ('R', 2.27, 2.69, -2.70),
    ('L', 2.80, 3.22, -3.28),
    ('R', 3.33, 3.78, -3.75),
    ('L', 3.90, 4.28, -3.75),
]
WALK_END = 4.5
WALK_DIST = 3.75
TOE_PIVOT = 0.086   # ball of the foot, metres in front of the ankle (y)
HEEL_PIVOT = 0.050  # shoe heel tip, metres behind the ankle


def _foot(side, t):
    """Ankle position and pitch for one foot (pitch > 0 = heel up / toe down)."""
    steps = [s for s in WALK_STEPS if s[0] == side]
    y, lift, pitch, toe = ANKLE_REST[side][1], 0.0, 0.0, 0.0
    for i, (_, t0, t1, y1) in enumerate(steps):
        y0 = ANKLE_REST[side][1] if i == 0 else steps[i - 1][3] + ANKLE_REST[side][1]
        y1 = y1 + ANKLE_REST[side][1]
        last = t0 == WALK_STEPS[-1][1]
        k = 0.5 if last or i == 0 else 1.0
        if t >= t1:
            y = y1
        elif t > t0:
            s = (t - t0) / (t1 - t0)
            y = y0 + (y1 - y0) * (s * s * s * (s * (6 * s - 15) + 10))
            lift = (0.075 if not last else 0.04) * math.sin(math.pi * min(1.0, s ** 0.85))
        # heel rise before lift-off, toe up before landing, flatten after landing
        pitch += k * (40 * bump(t, t0 - 0.30, t0 + 0.24, 0.55) - 7 * bump(t, t1 - 0.22, t1 + 0.12, 0.5))
        toe += k * -26 * bump(t, t0 - 0.30, t0 + 0.08, 0.6)
        if t < t0:
            break
    x = ANKLE_REST[side][0] * (0.85 if 0.6 < t < 3.9 else 1.0)
    rel = Vector((0, -TOE_PIVOT, -ANKLE_REST[side][2])) if pitch > 0 else Vector((0, HEEL_PIVOT, -ANKLE_REST[side][2]))
    piv = Vector((x, y, ANKLE_REST[side][2])) + rel
    ankle = piv + Matrix.Rotation(math.radians(pitch), 3, 'X') @ (-rel) + Vector((0, 0, lift))
    return ankle, pitch, toe


def _walk_speed_table():
    n = int(WALK_END * 300) + 1
    v = [smooth((i / 300 - 0.05) / 0.85) * (1 - smooth((i / 300 - 3.25) / 1.1)) for i in range(n)]
    acc, out = 0.0, []
    for x in v:
        out.append(acc)
        acc += x
    return [o / acc for o in out]


_WALK_Y = None


def walk_in(t):
    global _WALK_Y
    if _WALK_Y is None:
        _WALK_Y = _walk_speed_table()
    yprog = _WALK_Y[max(0, min(int((t - 0.07) * 300), len(_WALK_Y) - 1))]  # hips trail the feet slightly
    hy = -WALK_DIST * yprog
    speed = smooth((t - 0.05) / 0.6) * (1 - smooth((t - 3.6) / 0.7))
    # vertical bob (high at mid-swing), lateral sway toward the stance foot, pelvis yaw / roll
    bob, sway_keys, yaw_keys, swing_keys = 0.0, [(0.0, 0.0)], [(0.0, 0.0)], [(0.0, 0.0)]
    for side, t0, t1, _ in WALK_STEPS:
        s = (t - t0) / (t1 - t0)
        if 0 < s < 1:
            bob += math.sin(math.pi * s)
        sgn = 1 if side == 'R' else -1   # R swinging -> stance on L (+X)
        sway_keys.append(((t0 + t1) / 2, 0.022 * sgn))
        yaw_keys.append((t1, 4.5 * sgn))
        swing_keys.append((t1 + 0.05, sgn))
    last = WALK_STEPS[-1][2]
    for keys in (sway_keys, yaw_keys, swing_keys):
        keys[-1] = (keys[-1][0], keys[-1][1] * 0.35)
        keys.append((last + 0.2, 0.0))
        keys.append((WALK_END, 0.0))
    sway, yaw, swing = track(sway_keys)(t), track(yaw_keys)(t) * speed, track(swing_keys)(t) * speed
    swing_lag = track(swing_keys)(t - 0.08) * speed
    # hip height: as high as both legs comfortably reach (gives the bob: low in double support)
    feet = {s: _foot(s, t) for s in 'LR'}
    reach = []
    for s_, (ank, _, _) in feet.items():
        sx = 1 if s_ == 'L' else -1
        hz = math.hypot(sway + sx * 0.09 - ank.x, hy + 0.012 - ank.y)
        reach.append(ank.z + math.sqrt(max(0.872 ** 2 - hz * hz, 0.0)) + 0.016)
    k = 0.008
    softmin = lambda a, b: -k * math.log(math.exp(-a / k) + math.exp(-b / k))
    z = softmin(softmin(*reach), STAND_HIP_Z + 0.02)
    w = smooth((t - 0.02) / 0.25) * (1 - smooth((t - 4.2) / 0.3))
    z = lerp(STAND_HIP_Z, z, w)
    z -= 0.005 * bump(t, last - 0.05, last + 0.35)   # settle at the stop
    hip = (sway, hy, z)
    roll = -2.5 * sway / 0.022 * speed
    b = breath(t, 2.6)
    P = {'hip': hip,
         'rot': {'Hip': (2.5 * speed, roll, yaw),
                 'Waist': (1.5 * speed + 1, -0.8 * roll, -0.3 * yaw),
                 'Spine01': (1.5 - 0.4 * b, 0, -0.5 * yaw),
                 'Spine02': (1 - 0.6 * b, 0.3 * roll, -0.6 * track(yaw_keys)(t - 0.05) * speed),
                 'NeckTwist01': (5, 0, 0.25 * yaw),
                 'NeckTwist02': (1 - 1.5 * bob * speed, 0, 0.2 * yaw),
                 'Head': (6 + 1.2 * track(sway_keys)(t - 0.1) * 0, 1.0 - 0.3 * roll, 0.15 * yaw),
                 'L_Clavicle': (0, -0.8 * b, -3 - 2 * swing_lag), 'R_Clavicle': (0, 0.6 * b, 3 - 2 * swing_lag)},
         'legs': {}, 'arms': {}, 'fingers': copy_pose(FINGERS_RELAXED)}
    for side in 'LR':
        ankle, pitch, toe = feet[side]
        sx = 1 if side == 'L' else -1
        P['legs'][side] = {'target': tuple(ankle), 'pole': (0.2 * sx, ankle.y - 1.0, 0.5), 'rot': (pitch, 0, 3 * sx)}
        P['rot'][side + '_ToeBase'] = (toe, 0, 0)
        arm_swing = (swing if side == 'L' else -swing) * (0.85 if side == 'L' else 1.0)
        P['arms'][side] = hang_arm(side, hip, arm_swing, yaw * 0.4)
        lag = (swing_lag if side == 'L' else -swing_lag)
        P['arms'][side]['D'] = tuple(Vector(P['arms'][side]['D']) + Vector((0, 0.12 * (arm_swing - lag), 0)))
    P['fingers']['L']['Index'] += 4 * swing_lag
    P['fingers']['R']['Index'] -= 4 * swing_lag
    return P


# ---------------------------------------------------------------- blending helpers


def _zero(v):
    if isinstance(v, dict):
        return {k: _zero(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return tuple(0.0 for _ in v)
    return 0.0


def blend_pose(A, Bp, w):
    """Linear blend of two pose dicts (w=0 -> A, w=1 -> Bp); missing entries count as zero."""
    if w <= 0.0:
        return copy_pose(A)
    if w >= 1.0:
        return copy_pose(Bp)
    if isinstance(A, dict) or isinstance(Bp, dict):
        A = A if isinstance(A, dict) else {}
        Bp = Bp if isinstance(Bp, dict) else {}
        keys = list(A) + [k for k in Bp if k not in A]
        return {k: blend_pose(A.get(k, _zero(Bp.get(k))), Bp.get(k, _zero(A.get(k))), w) for k in keys}
    if isinstance(A, (list, tuple)):
        return tuple(a + (b - a) * w for a, b in zip(A, Bp))
    return A + (Bp - A) * w


def vec_track(keys, **kw):
    f = track(keys, **kw)
    return lambda t: Vector(f(t))


# ---------------------------------------------------------------- sit_down

SIT_END = 2.9
_SOLVER = None  # set by main(); wipe_tears needs it to place the fingertips


def sit_down(t):
    st, se = stand_pose(0.0), seated_neutral(0.0)
    hip = track([(0.0, st['hip']), (0.30, (0.004, 0.006, 1.044)), (0.75, (0.010, 0.10, 0.93)),
                 (1.10, (0.008, 0.25, 0.73)), (1.38, (0.003, 0.36, 0.61)), (1.56, (0.0, 0.392, 0.562)),
                 (1.85, (0.0, 0.401, 0.572)), (2.3, SEAT_HIP), (SIT_END, SEAT_HIP)])(t)
    lean = track([(0, 0), (0.3, 1.5), (0.8, 15), (1.15, 27), (1.42, 22), (1.85, 6), (2.4, 0), (SIT_END, 0)])
    P = blend_pose(st, se, smooth((t - 0.9) / 1.6))
    P['hip'] = hip
    addrot(P, {'Hip': (lean(t) * 0.75, 0, 0), 'Waist': (lean(t - 0.05) * 0.15, 0, 0),
               'Spine01': (lean(t - 0.1) * 0.12, 0, 0), 'Spine02': (lean(t - 0.15) * 0.08, 0, 0),
               'NeckTwist01': (-lean(t - 0.18) * 0.30, 0, 0), 'Head': (-lean(t - 0.25) * 0.25, 0, 0)})
    # little sideways settle on landing
    addrot(P, {'Hip': (0, 1.5 * bump(t, 1.3, 2.4), 0), 'Spine02': (0, -1.2 * bump(t, 1.4, 2.5), 0)})
    # feet stay planted while she lowers, then slide forward one after the other
    for side, t0, t1 in (('R', 1.80, 2.25), ('L', 2.10, 2.62)):
        a = Vector(ANKLE_REST[side])
        b = Vector(LEGS_SEATED[side]['target'])
        s_ = smooth((t - t0) / (t1 - t0))
        pos = a.lerp(b, s_) + Vector((0, 0, 0.018 * math.sin(math.pi * s_)))
        P['legs'][side]['target'] = tuple(pos)
        P['legs'][side]['pole'] = tuple(Vector(st['legs'][side]['pole']).lerp(Vector(LEGS_SEATED[side]['pole']), smooth((t - 0.4) / 1.2)))
        P['legs'][side]['rot'] = tuple(Vector(st['legs'][side]['rot']).lerp(Vector(LEGS_SEATED[side]['rot']), s_))
    # hands: hang -> reach toward the thighs while lowering -> rest on thighs -> settle into the lap
    for side, lag in (('L', 0.0), ('R', 0.06)):
        sx = 1 if side == 'L' else -1
        h0, h1 = st['arms'][side], se['arms'][side]
        tgt = track([(0.0, h0['target']), (0.35 + lag, h0['target']),
                     (0.95 + lag, (sx * 0.20, -0.02, 0.80)), (1.40 + lag, (sx * 0.14, 0.02, 0.66)),
                     (1.75 + lag, (sx * 0.13, 0.06, 0.665)), (2.45 + lag, h1['target']), (SIT_END, h1['target'])])(t)
        mid_D, mid_N = (sx * -0.1, -0.7, -0.7), (sx * 0.1, -0.2, -1)
        D = track([(0.0, h0['D']), (0.45 + lag, h0['D']), (1.1 + lag, mid_D), (1.6 + lag, (sx * -0.35, -0.9, -0.3)),
                   (2.5 + lag, h1['D']), (SIT_END, h1['D'])])(t - 0.05)
        N = track([(0.0, h0['N']), (0.45 + lag, h0['N']), (1.1 + lag, mid_N), (1.6 + lag, (sx * 0.15, 0, -1)),
                   (2.5 + lag, h1['N']), (SIT_END, h1['N'])])(t - 0.05)
        pole = Vector(h0['pole']).lerp(Vector(h1['pole']), smooth((t - 0.5) / 1.4))
        P['arms'][side] = {'target': tgt, 'pole': tuple(pole), 'D': D, 'N': N}
    if t >= SIT_END:
        return se
    return P


# ---------------------------------------------------------------- gestures on top of the neutral seated pose


def base_static():
    return seated_neutral(0.0)


def overlay_arm(P, side, keys_pos, keys_D=None, keys_N=None, t=0.0, period=None, orient_lag=0.07):
    """Offset an arm from its base pose by keyed deltas (position in metres, D/N deltas)."""
    a = P['arms'][side]
    a['target'] = add(a['target'], track(keys_pos, period=period)(t))
    if keys_D:
        a['D'] = add(a['D'], track(keys_D, period=period)(t - orient_lag))
    if keys_N:
        a['N'] = add(a['N'], track(keys_N, period=period)(t - orient_lag))


def talk_small_01(t):
    L = 4.0
    P = base_static()
    Z = (0, 0, 0)
    # right hand lifts a few cm, palm turns up-in, two small beats, settles
    overlay_arm(P, 'R', [(0.0, Z), (0.45, (0.02, -0.04, 0.055)), (0.95, (0.012, -0.05, 0.035)), (1.3, (0.022, -0.05, 0.06)),
                         (1.85, (0.015, -0.045, 0.032)), (2.5, (0.006, -0.02, 0.018)), (3.2, Z)],
                [(0.0, Z), (0.5, (-0.15, -0.2, 0.25)), (1.3, (-0.2, -0.2, 0.3)), (2.4, (-0.08, -0.1, 0.12)), (3.3, Z)],
                [(0.0, Z), (0.5, (0.45, 0, 0.75)), (1.3, (0.55, 0, 0.9)), (1.85, (0.4, 0, 0.6)), (2.6, (0.15, 0, 0.2)), (3.3, Z)],
                t=t, period=L)
    # left hand answers with a smaller lift, late and brief
    overlay_arm(P, 'L', [(0.0, Z), (1.1, Z), (1.6, (-0.008, -0.015, 0.018)), (2.3, (-0.004, -0.008, 0.008)), (2.9, Z)],
                [(0.0, Z), (1.2, Z), (1.7, (0.05, -0.1, 0.1)), (2.8, Z)], None, t=t, period=L)
    o = track([(0.0, 0.0), (0.55, 1.0), (1.4, 0.9), (2.0, 0.6), (2.9, 0.1), (3.4, 0.0)], period=L)(t - 0.12)
    for f, k in (('Thumb', -6), ('Index', -14), ('Mid', -12), ('Ring', -9), ('Pinky', -7)):
        P['fingers']['R'][f] += k * o
    P['fingers']['R']['Index_spread'] = 4 * o
    P['fingers']['L']['Index'] += -4 * track([(0, 0), (1.3, 0), (1.8, 1), (2.8, 0)], period=L)(t - 0.1)
    return P


def talk_small_02(t):
    L = 5.0
    P = base_static()
    Z = (0, 0, 0)
    # left hand leads a small open-palm offer, then both hands open slightly outward together
    overlay_arm(P, 'L', [(0.0, Z), (0.6, (-0.015, -0.035, 0.05)), (1.2, (-0.01, -0.04, 0.03)), (1.8, Z),
                         (2.8, (0.012, -0.03, 0.04)), (3.4, (0.02, -0.035, 0.045)), (4.2, Z)],
                [(0.0, Z), (0.7, (0.15, -0.2, 0.25)), (1.9, Z), (2.9, (0.25, -0.15, 0.2)), (3.5, (0.3, -0.15, 0.25)), (4.3, Z)],
                [(0.0, Z), (0.7, (-0.4, 0, 0.7)), (1.9, Z), (2.9, (-0.2, 0, 0.6)), (3.5, (-0.3, 0, 0.8)), (4.3, Z)],
                t=t, period=L)
    overlay_arm(P, 'R', [(0.0, Z), (2.6, Z), (2.95, (-0.012, -0.03, 0.035)), (3.5, (-0.02, -0.035, 0.04)), (4.35, Z)],
                [(0.0, Z), (2.7, Z), (3.05, (-0.25, -0.15, 0.2)), (3.6, (-0.3, -0.15, 0.25)), (4.45, Z)],
                [(0.0, Z), (2.7, Z), (3.05, (0.2, 0, 0.55)), (3.6, (0.3, 0, 0.75)), (4.45, Z)],
                t=t, period=L)
    oL = track([(0, 0), (0.7, 1), (1.6, 0.3), (2.0, 0), (3.0, 0.7), (3.6, 0.8), (4.4, 0)], period=L)(t - 0.12)
    oR = track([(0, 0), (2.7, 0), (3.1, 0.6), (3.7, 0.8), (4.5, 0)], period=L)(t - 0.15)
    for side, o in (('L', oL), ('R', oR)):
        for f, k in (('Thumb', -5), ('Index', -12), ('Mid', -11), ('Ring', -9), ('Pinky', -8)):
            P['fingers'][side][f] += k * o
        P['fingers'][side]['Pinky_spread'] = P['fingers'][side].get('Pinky_spread', 0) - 4 * o
    return P


def fidget_nails(t):
    """Thumbs worry at the index/middle nails of the same hand (fingers only, so any lap pose works)."""
    L = 6.0
    P = base_static()
    fr, fl = P['fingers']['R'], P['fingers']['L']
    # right hand: thumb rubs and picks across the index nail in irregular strokes
    rt = track([(0, 0), (0.4, 1), (0.7, 0.55), (1.0, 1), (1.25, 0.6), (1.7, 1), (2.4, 0.2), (3.4, 0.15),
                (3.9, 0.9), (4.2, 0.5), (4.6, 1), (5.4, 0.2)], period=L)
    ri = track([(0, 0), (0.35, 1), (1.3, 0.85), (1.9, 1), (2.6, 0.2), (3.5, 0.3), (3.8, 1), (4.9, 0.9), (5.6, 0.1)], period=L)
    fr['Thumb'] += 34 * rt(t)
    fr['Thumb_in'] = 30 * ri(t - 0.05) + 6 * rt(t)
    fr['Index'] += 32 * ri(t)
    fr['Mid'] += 14 * ri(t - 0.1)
    fr['Index_spread'] = -4 * rt(t)
    # left hand: slower, runs the thumb over the middle and index nails, pauses
    lt = track([(0, 0.2), (0.8, 0.2), (1.4, 1), (1.8, 0.6), (2.2, 1), (2.9, 0.4), (3.6, 0.9), (4.4, 0.2)], period=L)
    li = track([(0, 0.3), (1.2, 0.9), (2.6, 1), (3.0, 0.5), (3.8, 1), (4.8, 0.3)], period=L)
    fl['Thumb'] += 30 * lt(t)
    fl['Thumb_in'] = 26 * li(t - 0.05) + 5 * lt(t)
    fl['Index'] += 26 * li(t)
    fl['Mid'] += 22 * li(t - 0.08)
    fl['Ring'] += 8 * li(t - 0.15)
    return P


def wipe_tears(t, solver=None):
    """Right hand comes up, fingertips wipe under the right eye from the inside out, back to the lap."""
    P = base_static()
    solver = solver or _SOLVER
    pose = solver.solve(P)[1]
    H = pose[B + 'Head']
    eye = pose[B + 'R_Eye'].translation / CM
    Rh = H.to_3x3().normalized()
    # contact path in front of the lower lid, from inner to outer corner (world axes, head-relative offsets)
    def face_pt(dx, dz, dy):
        return eye + Vector((dx, -0.029 + dy, -0.027 + dz))  # 5 mm spare so it also clears the slumped head
    T0 = 0.2
    contact = track([(T0 + 0.55, (0.008, 0.002, -0.004)), (T0 + 0.85, (0.002, 0.0, 0.0)), (T0 + 1.15, (-0.016, -0.004, 0.0)),
                     (T0 + 1.3, (-0.024, -0.010, -0.018))])
    D_wipe, N_wipe = Vector((0.45, -0.25, 1.0)), Vector((0.25, 1.0, 0.1))
    lap = P['arms']['R']
    w_up = smooth((t - T0) / 0.6)                  # hand rising
    w_dn = smooth((t - (T0 + 1.3)) / 0.85)         # hand returning
    w = w_up * (1 - w_dn)
    D = Vector(lap['D']).lerp(D_wipe, smooth((t - T0 - 0.08) / 0.6) * (1 - smooth((t - T0 - 1.25) / 0.85)))
    N = Vector(lap['N']).lerp(N_wipe, smooth((t - T0 - 0.08) / 0.6) * (1 - smooth((t - T0 - 1.25) / 0.85)))
    c = contact(t)
    tip_goal = face_pt(*c)
    # place the wrist so the middle fingertip lands on tip_goal (two fixed-point iterations)
    arm = dict(lap, D=tuple(D), N=tuple(N), pole=(-0.45, 0.35, 0.3))
    P['arms']['R'] = arm
    fr = P['fingers']['R']
    k = w
    fr.update(Index=lerp(fr['Index'], 14, k), Mid=lerp(fr['Mid'], 16, k), Ring=lerp(fr['Ring'], 55, k),
              Pinky=lerp(fr['Pinky'], 62, k), Thumb=lerp(fr['Thumb'], 25, k))
    goal = Vector(lap['target'])
    if w > 0:
        wrist = tip_goal - D.normalized() * 0.16
        for _ in range(3):
            arm['target'] = tuple(wrist)
            pz = solver.solve(P)[1]
            tip = pz[B + 'R_Mid3'] @ Vector((0, solver.rig.arm.data.bones[B + 'R_Mid3'].length, 0))
            wrist += tip_goal - tip / CM
        # arc out (elbow leads) between the lap and the face
        arc = Vector((-0.015, -0.06, 0.0)) * math.sin(math.pi * w) * (1 - bump(t, T0 + 0.5, T0 + 1.35, 0.3))
        goal = Vector(lap['target']).lerp(wrist, w) + arc
    arm['target'] = tuple(goal)
    # small sympathetic reaction in the left hand
    P['fingers']['L']['Index'] += 6 * bump(t, 0.3, 2.1)
    P['fingers']['L']['Mid'] += 4 * bump(t, 0.35, 2.2)
    P['arms']['L']['target'] = add(P['arms']['L']['target'], (0, -0.006 * bump(t, 0.3, 2.1), 0.004 * bump(t, 0.3, 2.1)))
    return P


def nod(t):
    P = base_static()
    a = track([(0, 0), (0.15, -0.6), (0.42, 7.5), (0.68, -0.8), (0.88, 2.2), (1.15, 0.0), (1.4, 0.0)])
    addrot(P, {'NeckTwist01': (0.35 * a(t), 0, 0), 'NeckTwist02': (0.2 * a(t - 0.03), 0, 0), 'Head': (0.55 * a(t - 0.06), 0.0, 0.0)})
    return P


def head_shake(t):
    P = base_static()
    a = track([(0, 0), (0.15, 0), (0.55, 6.5), (1.05, -6.0), (1.5, 4.0), (1.9, -1.5), (2.25, 0.0), (2.4, 0.0)])
    down = 2.0 * bump(t, 0.05, 2.35, 0.3)
    addrot(P, {'NeckTwist01': (0.3 * down, 0, 0.35 * a(t)), 'NeckTwist02': (0.2 * down, 0, 0.2 * a(t - 0.04)),
               'Head': (0.5 * down, 0.12 * a(t - 0.1), 0.45 * a(t - 0.07))})
    return P


# name: (function, seconds, loop, mask, root motion)
CLIPS = {
    'walk_in': (walk_in, WALK_END, False, 'Full body', 'yes (hips travel -Y)'),
    'sit_down': (sit_down, SIT_END, False, 'Full body', 'no'),
    'base_sit_neutral': (seated_neutral, 8.0, True, 'Full body', 'no'),
    'base_sit_slumped': (seated_slumped, 10.0, True, 'Full body', 'no'),
    'cue_fidget_nails_Hands': (fidget_nails, 6.0, True, 'Hands', 'no'),
    'cue_wipe_tears': (wipe_tears, 2.5, False, 'Arms', 'no'),
    'gesture_talk_small_01': (talk_small_01, 4.0, True, 'Arms', 'no'),
    'gesture_talk_small_02': (talk_small_02, 5.0, True, 'Arms', 'no'),
    'gesture_nod': (nod, 1.4, False, 'Head', 'no'),
    'gesture_head_shake': (head_shake, 2.4, False, 'Head', 'no'),
}


# ---------------------------------------------------------------- face presets (Unity blendshape weights 0-100)

FACE = {
    'face_sad': {'Brow_Raise_Inner_L': 42, 'Brow_Raise_Inner_R': 38, 'Brow_Compress_L': 14, 'Brow_Compress_R': 16,
                 'Eye_Blink_L': 14, 'Eye_Blink_R': 12, 'Eye_Squint_L': 10, 'Eye_Squint_R': 12,
                 'Mouth_Frown_L': 32, 'Mouth_Frown_R': 26, 'Mouth_Shrug_Lower': 18, 'Mouth_Press_L': 10, 'Mouth_Press_R': 8,
                 'Mouth_Down_Lower_L': 6, 'Mouth_Down_Lower_R': 5},
    'face_flat': {'Eye_Blink_L': 20, 'Eye_Blink_R': 18, 'Brow_Drop_L': 6, 'Brow_Drop_R': 5,
                  'Mouth_Frown_L': 5, 'Mouth_Frown_R': 4, 'Mouth_Close': 4},
    'face_anxious': {'Brow_Raise_Inner_L': 36, 'Brow_Raise_Inner_R': 40, 'Brow_Raise_Outer_L': 12, 'Brow_Raise_Outer_R': 10,
                     'Brow_Compress_L': 24, 'Brow_Compress_R': 22, 'Eye_Wide_L': 14, 'Eye_Wide_R': 16,
                     'Mouth_Stretch_L': 14, 'Mouth_Stretch_R': 12, 'Mouth_Press_L': 18, 'Mouth_Press_R': 20,
                     'Mouth_Roll_In_Lower_L': 10, 'Mouth_Roll_In_Lower_R': 12, 'Neck_Tighten_L': 18, 'Neck_Tighten_R': 15},
    'face_ashamed': {'Eye_Blink_L': 26, 'Eye_Blink_R': 24, 'Brow_Raise_Inner_L': 26, 'Brow_Raise_Inner_R': 22,
                     'Brow_Drop_L': 10, 'Brow_Drop_R': 12, 'Mouth_Press_L': 24, 'Mouth_Press_R': 20,
                     'Mouth_Roll_In_Lower_L': 14, 'Mouth_Roll_In_Lower_R': 16, 'Mouth_Frown_L': 14, 'Mouth_Frown_R': 18,
                     'Mouth_Pull_Lower_R': 8, 'Cheek_Suck_L': 6},
}
FACE_KEYS = sorted({k for w in FACE.values() for k in w})
FACE['face_neutral'] = {}


def face_weights(name):
    """Every preset lists every key any preset uses, so playing one fully resets the others."""
    return {k: FACE[name].get(k, 0) for k in FACE_KEYS}


def apply_face(weights):
    for o in bpy.data.objects:
        if o.type == 'MESH' and o.data.shape_keys:
            kb = o.data.shape_keys.key_blocks
            for k, v in weights.items():
                if k in kb:  # eyelash/occlusion/tear-line meshes share the eye key names
                    kb[k].value = v / 100.0


def write_faces(out_dir, body, previews):
    os.makedirs(os.path.join(out_dir, 'Face'), exist_ok=True)
    valid = set(body.data.shape_keys.key_blocks.keys())
    for name in ('face_neutral', 'face_sad', 'face_flat', 'face_anxious', 'face_ashamed'):
        w = face_weights(name)
        bad = [k for k in w if k not in valid]
        assert not bad, f'{name}: unknown shape keys {bad}'
        with open(os.path.join(out_dir, 'Face', name + '.json'), 'w') as f:
            json.dump({'mesh': 'CC_Base_Body', 'weights': w}, f, indent=2)
        if previews:
            for n in ('CC_Base_EyeOcclusion', 'CC_Base_TearLine'):  # Workbench draws these opaque white
                bpy.data.objects[n].hide_render = True
            try:
                bpy.context.scene.display.shading.studio_light = 'paint.sl'
            except TypeError:
                pass
            apply_face(w)
            head = bpy.data.objects['Armature'].pose.bones[B + 'Head']
            hp = bpy.data.objects['Armature'].matrix_world @ head.head
            render_views(os.path.join(out_dir, 'previews', name + '.png'), hp + Vector((0, -0.02, 0.075)),
                         views=('face', 'face34'), size=(320, 320), ortho=0.22)
    apply_face(face_weights('face_neutral'))


# ---------------------------------------------------------------- main


def load(fbx, clear_action=True):
    if bpy.app.background:
        bpy.ops.wm.read_factory_settings(use_empty=True)
    else:  # live session: never reset factory settings (it would stop add-ons), just clear
        for o in list(bpy.data.objects):
            bpy.data.objects.remove(o)
    bpy.ops.import_scene.fbx(filepath=fbx, anim_offset=0.0)
    sc = bpy.context.scene
    sc.render.fps, sc.render.fps_base = FPS, 1.0
    arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
    arm.animation_data_create()
    if clear_action:
        arm.animation_data.action = None
    return arm


def preview_frames(name, frames):
    if name == 'walk_in':
        return [0, 20, 40, 60, 80, 110, frames]
    if name == 'sit_down':
        return [0, 24, 36, 48, 66, frames]
    return [round(frames * k / 3) for k in range(4)]


def make_all(fbx, out_dir, previews=False, only=None):
    global _SOLVER
    arm = load(fbx)
    rig = Rig(arm)
    _SOLVER = Solver(rig)
    sc = bpy.context.scene
    if previews:
        build_chair()
        setup_preview(sc)
        os.makedirs(os.path.join(out_dir, 'previews'), exist_ok=True)
    report = {}
    for name, (fn, secs, loop, mask, root) in CLIPS.items():
        if only and name not in only:
            continue
        frames = round(secs * FPS)
        act = bake(rig, _SOLVER, name, fn, frames, loop=loop)
        export_fbx(arm, act, os.path.join(out_dir, name + '.fbx'))
        report[name] = frames
        if previews:
            bpy.data.objects['REF_Chair'].hide_render = name == 'walk_in'
            close = name.startswith(('cue_', 'gesture_'))
            for f in preview_frames(name, frames):
                sc.frame_set(f)
                hp = arm.matrix_world @ arm.pose.bones[B + 'Hip'].head
                if name == 'cue_fidget_nails_Hands':
                    tgt, ortho, size = (0, 0.05, 0.66), 0.32, (213, 200)
                elif close:
                    tgt, ortho, size = (0, 0.25, 0.95), 1.0, (213, 260)
                else:
                    tgt, ortho, size = (0, hp.y if name == 'walk_in' else 0.15, 0.88), 2.0, (213, 320)
                render_views(os.path.join(out_dir, 'previews', f'{name}_f{f:03d}.png'), tgt, size=size, ortho=ortho)
    if not only:
        arm.animation_data.action = None
        for pb in arm.pose.bones:
            pb.matrix_basis = Matrix.Identity(4)
        bpy.context.view_layer.update()
        write_faces(out_dir, bpy.data.objects['CC_Base_Body'], previews)
    return report


def verify(fbx_ref, out_dir):
    """Re-import every clip into an empty scene; check bones, frame range, fps and hip travel."""
    load(fbx_ref)
    ref_arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
    ref = sorted(b.name for b in ref_arm.data.bones)
    ref_rest = {b.name: b.head_local.copy() for b in ref_arm.data.bones}
    ok = True
    for name, (fn, secs, loop, mask, root) in CLIPS.items():
        path = os.path.join(out_dir, name + '.fbx')
        load(path, clear_action=False)
        objs = list(bpy.data.objects)
        arm = next(o for o in objs if o.type == 'ARMATURE')
        act = arm.animation_data.action if arm.animation_data else None
        bones = sorted(b.name for b in arm.data.bones)
        fr = tuple(int(x) for x in act.frame_range) if act else None
        sc = bpy.context.scene
        rest_ok = max((b.head_local - rb).length for b, rb in ((b, ref_rest[b.name]) for b in arm.data.bones)) < 0.01
        sc.frame_set(fr[0])
        h0 = arm.matrix_world @ arm.pose.bones[B + 'Hip'].head
        sc.frame_set(fr[1])
        h1 = arm.matrix_world @ arm.pose.bones[B + 'Hip'].head
        good = (rest_ok and act.name.split('|')[-1] == name and bones == ref and len(bones) == 101 and fr == (0, round(secs * FPS)) and sc.render.fps == FPS
                and all(o.type == 'ARMATURE' for o in objs))
        ok &= good
        print(f'VERIFY {name}: {"OK" if good else "FAIL"} action={act.name if act else None} frames={fr} '
              f'fps={sc.render.fps} bones={len(bones)} rest_pose_matches={rest_ok} objects={[o.type for o in objs]} '
              f'hip_travel=({h1.x - h0.x:+.3f}, {h1.y - h0.y:+.3f}, {h1.z - h0.z:+.3f}) m')
    print('VERIFY ALL OK' if ok else 'VERIFY FAILED')
    return ok


if __name__ == '__main__':
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    if argv and argv[0] == 'verify':
        verify(argv[1], argv[2])
    else:
        print(make_all(argv[0], argv[1], previews='--previews' in argv))
