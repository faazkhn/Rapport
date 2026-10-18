"""Rebuild Matt at base resolution (RIG_REPORT.md fallback; no Character Creator project available).

- Body and tongue: base meshes from Matt__Motion.Fbx (same skeleton), materials copied from the subdivided body.
- Eyes, teeth, eye occlusion, tear line: subdivided x3 in Matt.Fbx, reduced with Un-Subdivide; shape keys rebuilt.
- Boxers removed (they showed through the jeans).

Usage (from Med/):
  Blender -b --disable-autoexec --factory-startup --python tools/blender/matt_fallback.py -- \
      art_source/Blender/Matt.Fbx art_source/Blender/Matt__Motion.Fbx art/Matt
"""
import bpy, sys, os
from mathutils.bvhtree import BVHTree

main_fbx, motion_fbx, out_dir = sys.argv[sys.argv.index('--') + 1:]
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
    lo.parent = arm
    lo.matrix_parent_inverse = hi.matrix_parent_inverse.copy()
    for m in lo.modifiers:
        if m.type == 'ARMATURE':
            m.object = arm
    bpy.data.objects.remove(hi)
    lo.name = lo.data.name = name
    return lo


def unsubdivide(name, iterations=6):  # Blender needs 2 passes per subdivision level
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


swap_in_base('CC_Base_Body')
swap_in_base('CC_Base_Tongue')
for n in ('CC_Base_Eye', 'CC_Base_Teeth', 'CC_Base_EyeOcclusion', 'CC_Base_TearLine'):
    unsubdivide(n)

bpy.data.objects.remove(main['Boxers'])
for o in list(bpy.data.objects):
    if o.name in motion and o.name not in ('CC_Base_Body', 'CC_Base_Tongue'):
        bpy.data.objects.remove(o)
for a in list(bpy.data.actions):
    if 'TempMotion' in a.name:
        bpy.data.actions.remove(a)
bpy.data.orphans_purge(do_recursive=True)
arm.data.pose_position = 'POSE'

total = 0
for o in sorted(bpy.data.objects, key=lambda o: o.name):
    if o.type == 'MESH':
        t = sum(len(p.vertices) - 2 for p in o.data.polygons)
        total += t
        print(f'  {o.name:22} {t:7} tris  keys {len(o.data.shape_keys.key_blocks) if o.data.shape_keys else 0}')
print('TOTAL', total)

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out_dir, 'Matt.blend'), compress=True)
bpy.ops.export_scene.fbx(filepath=os.path.join(out_dir, 'Matt.Fbx'), add_leaf_bones=False, bake_anim=False,
                         path_mode='COPY', embed_textures=True, mesh_smooth_type='FACE')
