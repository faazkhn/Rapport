# Rig Report: provided patient models

**Checked:** 2026-10-18, by importing each FBX into Blender 5.2 in headless mode and reading its rig, meshes, shape keys and animations.
**Source:** `Blender.rar` (Matt) and `Megane_Blender.rar` (Mégane), extracted to `art_source/`. Preview renders are in `art_source/previews/`.
**Not yet checked:** Unity Humanoid import, and skin weights in sitting and slumped poses. Both need the Unity project (Stage 0).

## What the files are
Both are **Reallusion Character Creator 3+** exports (`RL_CC3_Plus`, exporter 1.10.1822.1). Each folder has:
- `<name>.Fbx`: the character with clothes, hair and embedded base color and normal textures
- `<name>.json`: Character Creator material data (used by Reallusion's Unity import tools)
- `<name>_Motion.Fbx`: the body with one animation take (Matt: 1,541 frames; Mégane: 827 frames)
- `textures/`: extra material maps (AO, roughness, subsurface, masks)

## Results

| Check (artist brief §3) | Matt | Mégane |
|---|---|---|
| 1. Humanoid-compatible skeleton | ✅ CC3 standard, 101 bones (hip, spine ×2, neck ×2, head, clavicles, arms, legs, toes). Same skeleton as Mégane, so animations are shared. | ✅ Same |
| 2. Finger bones | ✅ All 5 fingers × 3 joints, both hands | ✅ |
| 3. Eye bones | ✅ `CC_Base_L_Eye`, `CC_Base_R_Eye` + separate eye mesh | ✅ |
| 4. Facial blendshapes | ✅ **149** on the body (CC3 "Standard" facial profile), plus eye occlusion (137), tear line (120) and tongue (38). Not named in ARKit style, but every ARKit expression has an equivalent here (`Eye_Blink_L` = eyeBlinkLeft, `Jaw_Open` = jawOpen, `Mouth_Smile_L` = mouthSmileLeft, and so on). | ✅ Same set |
| 4b. Visemes for lip sync | ✅ 8: `V_Open, V_Explosive, V_Dental_Lip, V_Tight_O, V_Tight, V_Wide, V_Affricate, V_Lip_Open` | ✅ |
| 5. Jaw | ✅ `CC_Base_JawRoot` bone + `Jaw_Open` blendshape | ✅ |
| 6. Triangles (budget 90k) | ✅ **79,508 after the rebuild** (was 2,308,682, because it had been exported with 3 subdivision levels baked in). See "Matt rebuild" below. | ✅ **83,773**. Body 28,092; the hair is the biggest cost (`Side_part_mid` 33,377 + `Side_bangs` 2,464). |
| 6b. Materials | 23 material slots | 23 |
| 7. Skin weights in sitting poses | Not checked yet (needs Unity or a posed test) | Not checked yet |
| Scale | ✅ Meters, 1.73 m tall | ✅ Meters, 1.73 m tall |

Facial cues are **unblocked**. Everything in the cue catalog that needs a face (flat affect, tearfulness, lip smacking, self-talk, lip sync, gaze) is supported by these rigs. The tear line and eye occlusion meshes are especially useful for `tearful`.

## Problems to fix

1. ~~Matt is 29× over the triangle budget.~~ **Fixed 2026-10-18** (see "Matt rebuild" below).
2. ~~Mégane is over budget.~~ The patient budget was raised to 90k (a Character Creator body and face alone is about 35k), so she passes as-is. Trimming her hair is optional.
3. ~~Matt's boxers show through his jeans.~~ **Fixed**: the boxers mesh is removed.
4. **Textures are far larger than VR can use.** There are 232 texture files, mostly 4096 px. The `*_ResourceMap_*` files (616 MB) are Character Creator export data that Unity does not need, so don't import them. For Quest 3S, bake each material down to base color, normal and one packed mask at 2048 px (head) or 1024 px (everything else).
5. **Clothing does not fit the cases yet.** Matt wears a shirt, jeans and sneakers; Mégane wears a beautician-style uniform and high heels. Both need the variants from the artist brief §4 (`neat`, `casual`, `disheveled`, `hospital_gown`).

## Matt rebuild (fallback; no Character Creator project available)
**Output:** `art/Matt/Matt.Fbx` (textures embedded; use this for Unity) and `art/Matt/Matt.blend`.
**Script:** `tools/blender/matt_fallback.py`. Run it again to regenerate; the usage line is at the top of the file.

| Mesh | Before | After | How |
|---|---|---|---|
| CC_Base_Body | 1,797,888 | 28,092 (149 shape keys) | Base body from `Matt__Motion.Fbx`. It had UVs but no materials, so each face took its material from the nearest subdivided face. |
| CC_Base_Tongue | 37,888 | 592 (38 keys) | Base tongue from the motion file, same method |
| CC_Base_Eye | 81,920 | 1,280 (4 keys) | Un-Subdivide ×6 (Blender needs 2 passes per subdivision level); shape keys rebuilt one by one. Matches the base mesh exactly (same count as Mégane). |
| CC_Base_EyeOcclusion | 18,432 | 288 (137 keys) | Same; exact match |
| CC_Base_TearLine | 17,408 | 272 (120 keys) | Same; exact match |
| CC_Base_Teeth | 309,888 | 4,938 (2 keys) | Same; within 2% of the base mesh (4,842) |
| Boxers | 1,212 | removed | Showed through the jeans |
| Clothes and hair | 44,046 | unchanged | Already low-poly |
| **Total** | **2,308,682** | **79,508** | |

**Verified:** re-imported the exported FBX in Blender; all 10 meshes, materials, vertex groups and shape keys are present. A posed test render (`art_source/previews/matt_fixed_*.png`: head turned, jaw open, smile, brows raised, arms bent) shows correct skin materials with no seams, working expressions, and teeth and eyes following the head and jaw.
**Known small issues:**
- Eyes, eye occlusion and teeth were reduced from smoothed positions, so they may sit very slightly smaller than a true Character Creator export. The difference isn't visible in the test render.
- A little skin pokes through the shirt at the shoulder when the arm is raised far. This is normal clothing tuning.
- Not yet checked in Unity, and CC Unity Tools has not been tried on this re-exported file. If CC Unity Tools rejects it, fall back to Unity's own FBX import with a Humanoid avatar and set up the URP materials by hand.

## Gap: we need more, and more varied, patients
Both models look like Western adults in their 20s. The sim follows Indian practice, and the case library needs a teenager, people in their 50s–60s, and a mix of both sexes. **Most patients should look South Asian** for the sim to feel real to Indian learners. Because these are Character Creator characters, the cheapest way to get more is to make them in Character Creator from the same base (same skeleton, same blendshapes, so every animation and cue works on them for free). Target 6 models by Stage 2, as in `DESIGN.md`.

Suggested IDs for the current two (artist brief §6):
- Matt → `male_20s_a`
- Mégane → `female_20s_a`

## Recommended import route into Unity
Use Reallusion's free **CC Unity Tools** (CC/iC Unity Tools, URP version). It reads the `.json` next to each FBX, builds the materials, and sets up the Humanoid avatar. Then replace the heavy Digital Human shaders with URP Lit versions for Quest 3S.
