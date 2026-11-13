"""Move a Character Creator body that was re-rigged with Auto-Rig Pro + Faceit back onto its CC skeleton, for Unity.

The Realistic Man .blend skins every mesh to the ARP rig (537 bones, Rigify-style face bones), but it still holds the original CC
armature, whose rest pose matches the ARP deform bones to ~6 mm. Its face is all shape keys (CC Standard + the 52 ARKit names +
5 Faceit presets), so the face bones are not needed: they fold into the CC head and jaw. On the CC skeleton the patient shares
the humanoid clips, CC_Base_JawRoot, the Std_* materials and the face code with the other patients.

Usage (from Med/):
  Blender -b --disable-autoexec --factory-startup --python tools/blender/arp_to_cc.py -- \
      "art_source/RealisticMan/Realistic man_Blend/Realistic man.blend" art/RealisticMan RealisticMan "Vest/Key 1"
Trailing "mesh/key" arguments bake that shape key fully on (the vest's "Key 1" puts the hood down).
"""
import os
import re
import sys

import bpy

src, out_dir, name, *bake = sys.argv[sys.argv.index('--') + 1:]
os.makedirs(out_dir, exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=src)
rig, cc = bpy.data.objects['rig'], bpy.data.objects['Realistic man']
if cc.name not in bpy.context.scene.collection.objects:  # it sat in a hidden collection, and the FBX exporter skips hidden objects
    bpy.context.scene.collection.objects.link(cc)
cc.hide_viewport = cc.hide_render = False
cc.hide_set(False)

BODY = {'root.x': 'CC_Base_Pelvis', 'spine_01.x': 'CC_Base_Waist', 'spine_02.x': 'CC_Base_Spine01', 'spine_03.x': 'CC_Base_Spine02',
        'neck.x': 'CC_Base_NeckTwist01', 'head.x': 'CC_Base_Head'}
SIDE = {'shoulder': 'Clavicle', 'arm_stretch': 'Upperarm', 'c_arm_twist_offset': 'UpperarmTwist01', 'forearm_stretch': 'Forearm',
        'forearm_twist': 'ForearmTwist02', 'hand': 'Hand', 'thigh_stretch': 'Thigh', 'thigh_twist': 'ThighTwist01',
        'leg_stretch': 'Calf', 'leg_twist': 'CalfTwist01', 'foot': 'Foot', 'toes_01': 'ToeBase'}
FINGER = {'thumb': 'Thumb', 'index': 'Index', 'middle': 'Mid', 'ring': 'Ring', 'pinky': 'Pinky'}


def cc_bone(g):
    """CC bone for an ARP deform group, or None for a non-bone group (Faceit masks)."""
    if g in BODY:
        return BODY[g]
    m = re.fullmatch(r'(.+)\.([lr])', g)
    if m and m[1] in SIDE:
        return f'CC_Base_{m[2].upper()}_{SIDE[m[1]]}'
    m = re.fullmatch(r'c?_?(thumb|index|middle|ring|pinky)(\d)(_base)?\.([lr])', g)
    if m:
        side = m[4].upper()
        return f'CC_Base_{side}_Hand' if m[3] else f'CC_Base_{side}_{FINGER[m[1]]}{m[2]}'  # the metacarpal base bones stay with the hand
    if g.startswith(('DEF_eye.', 'DEF-eye.')):
        return f'CC_Base_{g[-1].upper()}_Eye'
    if g.startswith('DEF-teeth'):
        return 'CC_Base_Teeth02' if g.endswith('.B') else 'CC_Base_Teeth01'
    if g.startswith('DEF-tongue'):
        return {'DEF-tongue': 'CC_Base_Tongue01', 'DEF-tongue.001': 'CC_Base_Tongue02'}.get(g, 'CC_Base_Tongue03')
    if g.startswith(('DEF-jaw', 'DEF-chin', 'DEF-lip.B')):
        return 'CC_Base_JawRoot'  # lower face rides the jaw, as on a CC export
    if g.startswith(('DEF-', 'DEF_')):
        return 'CC_Base_Head'  # lids, brows, nose, cheeks, upper lip: shape keys move them
    return None


deform = {b.name for b in rig.data.bones if b.use_deform}
missing = set()
meshes = [o for o in bpy.data.objects if o.type == 'MESH' and o.parent == rig]
for o in meshes:
    groups = {g.index: g.name for g in o.vertex_groups}
    target = {i: cc_bone(n) for i, n in groups.items() if n in deform}
    missing |= {groups[i] for i, t in target.items() if t is None or t not in cc.data.bones}
    weights = []
    for v in o.data.vertices:
        acc = {}
        for g in v.groups:
            t = target.get(g.group)
            if t and t in cc.data.bones:
                acc[t] = acc.get(t, 0.0) + g.weight
        weights.append(acc)
    for g in list(o.vertex_groups):
        o.vertex_groups.remove(g)
    made = {}
    for vi, acc in enumerate(weights):
        s = sum(acc.values())
        for t, w in acc.items():
            if t not in made:
                made[t] = o.vertex_groups.new(name=t)
            made[t].add([vi], w / s, 'REPLACE')
    for m in list(o.modifiers):  # Blender-only looks (eye displace, UV warp) and subdivision do not export
        if m.type != 'ARMATURE':
            o.modifiers.remove(m)
    world = o.matrix_world.copy()
    o.parent = cc
    bpy.context.view_layer.update()  # matrix_world reads the new parent only after an update
    o.matrix_world = world
    o.modifiers[0].object = cc
    unweighted = sum(1 for acc in weights if not acc)
    print(f'{o.name}: {len(made)} CC groups, {unweighted} unweighted verts')
print('ARP groups with no CC bone:', sorted(missing))

for b in bake:
    mesh, key = b.split('/', 1)
    o = bpy.data.objects[mesh]
    kb = o.data.shape_keys.key_blocks
    co = [0.0] * (len(o.data.vertices) * 3)
    base = [0.0] * len(co)
    kb[key].data.foreach_get('co', co)
    kb[0].data.foreach_get('co', base)
    for k in kb:  # the baked key becomes the rest shape; every other key keeps its offset from the old basis
        if k.name != key:
            d = [0.0] * len(co)
            k.data.foreach_get('co', d)
            k.data.foreach_set('co', [c + (x - b0) for c, x, b0 in zip(co, d, base)])
    o.shape_key_remove(kb[key])
    o.data.vertices.foreach_set('co', co)  # the FBX exporter reads the mesh's own coordinates, not the basis key
    o.data.update()
    print(f'baked {mesh}/{key}')

cc.animation_data_clear()
for pb in cc.pose.bones:
    pb.matrix_basis.identity()
keep = set(meshes) | {cc}
for o in list(bpy.data.objects):
    if o not in keep:
        bpy.data.objects.remove(o)
bpy.data.orphans_purge(do_recursive=True)
total = 0
for o in sorted(meshes, key=lambda o: o.name):
    t = sum(len(p.vertices) - 2 for p in o.data.polygons)
    total += t
    print(f'  {o.name:22} {t:7} tris  keys {len(o.data.shape_keys.key_blocks) if o.data.shape_keys else 0}')
print('TOTAL', total)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out_dir, name + '.blend'), compress=True)
bpy.ops.file.unpack_all(method='WRITE_LOCAL')  # the textures are packed in the .blend; the FBX can embed only files on disk
bpy.ops.export_scene.fbx(filepath=os.path.join(out_dir, name + '.Fbx'), add_leaf_bones=False, bake_anim=False,
                         path_mode='COPY', embed_textures=True, mesh_smooth_type='FACE')
