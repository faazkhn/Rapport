"""Copy a rebuilt patient (tools/blender/cc_rebuild.py or arp_to_cc.py output) into the Unity project as Art/Patients/<id>/.

Only the maps Unity's URP Lit materials use: <Material>_Diffuse and _Normal. Alpha-clipped materials (hair, scalp, lashes, brows)
get <Material>_Diffuse_A.png, the diffuse with the _Opacity map in its alpha when the diffuse has none. Textures are capped at
2048 px (LFS budget). Then run the Unity menu Rapport > Import New Patients.

Usage (from Med/): python3 tools/blender/stage_patient.py art/Amber/Amber.Fbx art/Amber/textures female_20s_b
"""
import shutil
import sys
from pathlib import Path

from PIL import Image

MAX = 2048
CLIP = ('Hair_Transparency', 'Scalp_Transparency', 'Std_Eyelash', 'Brow')


def main(fbx, tex_dir, model_id):
    dst = Path('unity/PsychSim/Assets/Art/Patients') / model_id
    (dst / 'Textures').mkdir(parents=True, exist_ok=True)
    shutil.copy(fbx, dst / f'{model_id}.fbx')
    tex = {p.stem: p for p in Path(tex_dir).iterdir() if p.suffix.lower() in ('.png', '.jpg', '.jpeg', '.tga')}
    n = 0
    for stem, p in sorted(tex.items()):
        mat, _, kind = stem.rpartition('_')
        if kind not in ('Diffuse', 'Normal'):
            continue
        im = Image.open(p)
        if im.width > MAX:
            im = im.resize((MAX, MAX * im.height // im.width), Image.LANCZOS)
        if kind == 'Diffuse' and any(c in mat for c in CLIP):
            if im.mode != 'RGBA' and f'{mat}_Opacity' in tex:
                im = im.convert('RGB')
                im.putalpha(Image.open(tex[f'{mat}_Opacity']).convert('L').resize(im.size, Image.LANCZOS))
            im.save(dst / 'Textures' / f'{mat}_Diffuse_A.png')
        else:
            out = dst / 'Textures' / (p.stem + ('.png' if im.mode == 'RGBA' or p.suffix.lower() == '.tga' else p.suffix.lower()))
            (im if out.suffix == '.png' else im.convert('RGB')).save(out, quality=92)
        n += 1
    print(f'{model_id}: fbx + {n} textures -> {dst}')


if __name__ == '__main__':
    main(*sys.argv[1:])
