"""Rebuild a Character Creator export at base resolution (RIG_REPORT.md fallback; no Character Creator project available).

CC exports can bake subdivision into every mesh (Matt: x3 levels on the head meshes, Amber: x2 on everything).
- Body and tongue: base meshes from <name>_Motion.Fbx (same skeleton), materials copied from the subdivided body.
- Eyes, teeth, eye occlusion, tear line, 3D brows: reduced with Un-Subdivide; shape keys rebuilt.
- Clothes: Un-Subdivide when they were subdivided, otherwise decimated to --max-tris each. Hair and brow cards are kept whole.
- --drop removes meshes (underwear that shows through, a jacket the case does not want).

Usage (from Med/):
  Blender -b --disable-autoexec --factory-startup --python tools/blender/cc_rebuild.py -- \
      art_source/Blender/Matt.Fbx art_source/Blender/Matt__Motion.Fbx art/Matt --levels 3 --drop Boxers
  Blender -b --disable-autoexec --factory-startup --python tools/blender/cc_rebuild.py -- \
      art_source/Amber/Amber.Fbx art_source/Amber/Amber_Motion.Fbx art/Amber --levels 2 \
      --drop Bra Underwear_Bottoms Punk_Leather_Jacket
"""
import bpy, sys, os
from mathutils.bvhtree import BVHTree

import argparse

ap = argparse.ArgumentParser()
ap.add_argument('main_fbx'), ap.add_argument('motion_fbx'), ap.add_argument('out_dir')
ap.add_argument('--levels', type=int, default=3, help='subdivision levels baked into the export')
ap.add_argument('--drop', nargs='*', default=[])
ap.add_argument('--max-tris', type=int, default=12000, help='per clothing or hair mesh that was not subdivided')
a = ap.parse_args(sys.argv[sys.argv.index('--') + 1:])
main_fbx, motion_fbx, out_dir = a.main_fbx, a.motion_fbx, a.out_dir
name = os.path.splitext(os.path.basename(main_fbx))[0]
os.makedirs(out_dir, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=main_fbx)
main = {o.name: o for o in bpy.data.objects}
arm = main['Armature']
arm.data.pose_position = 'REST'

bpy.ops.import_scene.fbx(filepath=motion_fbx)
motion = {o.name: o for o in bpy.data.objects if o.name not in main}
motion_arm = next(o for o in motion.values() if o.type == 'ARMATURE')


def world_polys(obj):
    mw = obj.matrix_world
    return [mw @ v.co for v in obj.data.vertices], [tuple(p.vertices) for p in obj.data.polygons]


def swap_in_base(name):
    """Replace the subdivided mesh `name` with the base mesh of the same name from the motion file."""
    hi = main[name]
    lo = next(o for o in motion.values() if o.type == 'MESH' and o.name.startswith(name))
    lo.data.materials.clear()
    for m in hi.data.materials:
        lo.data.materials.append(m)
    # Each base face lies inside its 64 subdivided faces, so the nearest subdivided face gives its material.
    verts, polys = world_polys(hi)
    bvh = BVHTree.FromPolygons(verts, polys)
    hi_idx = [p.material_index for p in hi.data.polygons]
    mw = lo.matrix_world
    for p in lo.data.polygons:
        _, _, i, _ = bvh.find_nearest(mw @ p.center)
        p.material_index = hi_idx[i]
    world = lo.matrix_world.copy()  # the motion file's armature sits where the main one does; keep the base mesh where it was
    lo.parent = arm
    bpy.context.view_layer.update()  # matrix_world reads the new parent only after an update
    lo.matrix_world = world
    for m in lo.modifiers:
        if m.type == 'ARMATURE':
            m.object = arm
    bpy.data.objects.remove(hi)
    lo.name = lo.data.name = name
    return lo


def tris(obj):
    return sum(len(p.vertices) - 2 for p in obj.data.polygons)


def reduce_other(name):
    """Clothes or hair: Un-Subdivide if that lands near 1/4^levels of the faces (it was subdivided), else collapse-decimate."""
    obj = main[name]
    before = tris(obj)
    if before <= a.max_tris:
        return
    trial = unsubdivide(name, 2 * a.levels, dry=True)
    if abs(trial * 4 ** a.levels / before - 1) < 0.1:
        main[name] = unsubdivide(name, 2 * a.levels)
        return
    if obj.data.shape_keys:  # a decimate would drop them (Amber's 3D brows carry 181 face shapes): keep the mesh as is
        print(f'{name}: {before} tris kept (shape keys)')
        return
    if any(m and ('Hair' in m.name or 'Brow' in m.name) for m in obj.data.materials):
        # collapse shreds thin alpha cards: Amber's hair at 40k of ~120k tris per mesh rendered nearly bald (2026-10-31)
        print(f'{name}: {before} tris kept (hair cards)')
        return
    dec = obj.modifiers.new('collapse', 'DECIMATE')
    dec.ratio = a.max_tris / before
    obj.modifiers.move(obj.modifiers.find(dec.name), 0)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=dec.name)
    print(f'{name}: {before} -> {tris(obj)} tris (collapse)')


def unsubdivide(name, iterations, dry=False):  # Blender needs 2 passes per subdivision level
    """Un-subdivide `name` and rebuild its shape keys on the reduced mesh."""
    obj = main[name]
    dec = obj.modifiers.new('unsub', 'DECIMATE')
    dec.decimate_type, dec.iterations = 'UNSUBDIV', iterations
    obj.modifiers.move(obj.modifiers.find(dec.name), 0)  # run before the armature modifier
    keys = obj.data.shape_keys.key_blocks if obj.data.shape_keys else []
    obj.show_only_shape_key = True
    dg = bpy.context.evaluated_depsgraph_get()

    def evaluated(i):
        if keys:
            obj.active_shape_key_index = i
        dg.update()
        return bpy.data.meshes.new_from_object(obj.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)

    base = evaluated(0)
    if dry:
        n = sum(len(p.vertices) - 2 for p in base.polygons)
        obj.modifiers.remove(dec)
        bpy.data.meshes.remove(base)
        return n
    new = bpy.data.objects.new(name + '_new', base)
    bpy.context.scene.collection.objects.link(new)
    if not new.vertex_groups:
        for g in obj.vertex_groups:
            new.vertex_groups.new(name=g.name)
    if keys:
        new.shape_key_add(name=keys[0].name)
        for i, kb in enumerate(keys[1:], 1):
            me = evaluated(i)
            assert len(me.vertices) == len(base.vertices), f'{name}/{kb.name}: vertex count changed'
            co = [0.0] * (len(me.vertices) * 3)
            me.vertices.foreach_get('co', co)
            sk = new.shape_key_add(name=kb.name)
            sk.data.foreach_set('co', co)
            sk.slider_min, sk.slider_max = kb.slider_min, kb.slider_max
            bpy.data.meshes.remove(me)
    new.parent = arm
    new.matrix_world = obj.matrix_world.copy()
    new.matrix_parent_inverse = obj.matrix_parent_inverse.copy()
    new.modifiers.new('Armature', 'ARMATURE').object = arm
    old_tris = sum(len(p.vertices) - 2 for p in obj.data.polygons)
    bpy.data.objects.remove(obj)
    new.name = new.data.name = name
    new_tris = sum(len(p.vertices) - 2 for p in new.data.polygons)
    print(f'{name}: {old_tris} -> {new_tris} tris, {len(keys)} shape keys')
    return new


for n in a.drop:
    bpy.data.objects.remove(main.pop(n))
heads = ('CC_Base_Body', 'CC_Base_Tongue', 'CC_Base_Eye', 'CC_Base_Teeth', 'CC_Base_EyeOcclusion', 'CC_Base_TearLine')
swap_in_base('CC_Base_Body')
swap_in_base('CC_Base_Tongue')
for n in heads[2:]:
    unsubdivide(n, 2 * a.levels)
for n, o in list(main.items()):
    if n not in heads and o.type == 'MESH':  # the head meshes were replaced above
        reduce_other(n)

for o in list(bpy.data.objects):
    if o.name in motion and o.name not in ('CC_Base_Body', 'CC_Base_Tongue'):
        bpy.data.objects.remove(o)
for a in list(bpy.data.actions):
    if 'TempMotion' in a.name:
        bpy.data.actions.remove(a)
bpy.data.orphans_purge(do_recursive=True)
# export the rest pose: Amber's T-pose take rotates the root 90° (an FBX axis artefact), which laid the whole body down
arm.animation_data_clear()
for pb in arm.pose.bones:
    pb.matrix_basis.identity()
arm.data.pose_position = 'POSE'
# some exports (Amber) bind the meshes to a skeleton standing up while the rest pose lies along -Y: stand the rest pose up so
# Unity's bind poses match the mesh. The pose is the rest pose here, so the meshes do not move.
bpy.context.view_layer.update()
head = arm.matrix_world @ arm.data.bones['CC_Base_Head'].head_local
if abs(head.y) > abs(head.z):
    import math
    from mathutils import Matrix
    arm.data.transform(Matrix.Rotation(math.copysign(math.pi / 2, head.y), 4, 'X'))  # all bones at once (edit bones one by one moved connected tips twice)
    print('rest pose stood up')

total = 0
for o in sorted(bpy.data.objects, key=lambda o: o.name):
    if o.type == 'MESH':
        t = sum(len(p.vertices) - 2 for p in o.data.polygons)
        total += t
        print(f'  {o.name:22} {t:7} tris  keys {len(o.data.shape_keys.key_blocks) if o.data.shape_keys else 0}')
print('TOTAL', total)

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out_dir, name + '.blend'), compress=True)
bpy.ops.export_scene.fbx(filepath=os.path.join(out_dir, name + '.Fbx'), add_leaf_bones=False, bake_anim=False,
                         path_mode='COPY', embed_textures=True, mesh_smooth_type='FACE')
