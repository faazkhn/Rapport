# Brief: 3D Artist Agent

**Read first:** `DESIGN.md`, sections 1, 4 and 10. That document is the source of truth.
**Tools you can use:** the Blender MCP for modelling, rigging fixes and animation; the Unity MCP to import assets and check them in the project.
**Engine target:** Unity 6 LTS, URP. Build everything to **Quest 3S standalone budgets from the start**, even though the first builds run on Mac. Cutting detail later costs more than building lean now.

---

## 1. Your job in one paragraph
Build four small, believable clinical rooms and a hub. Prepare the provided rigged human models so they can sit, talk, show emotion and play every cue in the cue catalog. Deliver everything as Unity-ready assets with consistent names, so the developer can drive it all from code. **You are not building an open world.**

## 2. Environments

| Room | Stage | Must contain | Notes |
|---|---|---|---|
| Outpatient consult room | 1 | Desk, 2–3 chairs (patient chair angled 90–120° to the doctor, not straight across), box of tissues, wall clock, window with blinds, door, a bare corner (used for `internal_stimuli` looks) | Warm and calm. This is the main room for the vertical slice. |
| Emergency bay | 2 | Trolley bed, curtain on rails, vitals monitor (screen is a texture the developer can update), IV stand, wall sharps bin | Harsher light, more noise and clutter |
| Detox / inpatient ward room | 2 | Hospital bed, side chair, bedside table, window, en-suite door | Calm, institutional |
| Community clinic | 3 | Small office, two soft chairs, low table, plant | Least clinical; used for the PTSD case |
| Hub lobby | 4 | Reception desk, signs to each room, case-selection board (UI screen surface) | Small. It is a menu you can walk around in, nothing more. |

**Shared rules:**
- Real-world scale, 1 unit = 1 m. Doors 0.9 × 2.1 m. Seat height 0.45 m.
- Each room has a **DoctorAnchor** empty (where the doctor stands or sits) and a **PatientAnchor** empty (the patient's seat). Patient head is about 1.5 m from the doctor's head when seated. That is the distance cues must read at.
- **Lighting (DESIGN v0.3; the earlier look was too dull).** Bright, warm, clinical but humane:
  - **Key:** soft daylight through the window, about 5,000 K, lighting the patient's face three-quarters from the doctor's side.
  - **Fill:** a warm practical desk or ceiling lamp, about 3,200 K.
  - **Rim:** a subtle light separating the patient from the wall.
  - **GI and reflections:** baked GI, light probes around the patient chair, and one reflection probe so eyes and tears catch highlights.
  - **Post-processing volume:** Neutral or ACES tonemapping, post-exposure raised, contrast +10, saturation +5, mild bloom, SSAO, very light vignette.
  - **Surfaces:** off-white walls with one warm accent wall. No grey-on-grey.
  - **Acceptance:** in a 1080p frame from the DoctorAnchor, the patient's face has a **mean luminance of 0.45–0.60**, with no large area crushed black or blown white. Measure with a script on stills before and after, and put both stills in `docs/lighting.md`.
  - Real-time lights stay few (Quest budget): key and rim may be real-time; fill and room bounce are baked.
- Add 2–3 small sound-source empties (door, corridor, monitor). The developer uses the door one for the `startle` cue.

**Budgets per room (Quest 3S safe):**
- At most 150k triangles for the room, plus at most 90k for the patient, including hair and clothes. A Character Creator body and face alone is about 35k; both provided models are about 80k after fixes.
- At most 100 draw calls. Use texture atlases and shared materials.
- Textures 2048 max for the room, 4096 allowed for the patient's head only (then made smaller for VR).
- Use URP Lit or Simple Lit only. No custom shaders unless listed in section 5.

## 3. Rig check for the provided models (Stage 0)
**Already done for the two provided models. Read `RIG_REPORT.md` first.** Summary: both are Character Creator 3+ characters (Matt, Mégane) in `art_source/`. Rig, fingers, eyes, jaw and 149 facial blendshapes all pass. Your Stage 0 jobs from that report:
1. ~~Get Matt under budget~~ and ~~hide Matt's boxers~~: **done**. Use `art/Matt/Matt.Fbx` (rebuilt by `tools/blender/cc_rebuild.py`), not the original `art_source/Blender/Matt.Fbx`.
2. Mégane is within budget as-is; trimming her hair is optional.
3. Fix the small spot where skin pokes through Matt's shirt at the shoulder at extreme arm raises.
4. Import both through Reallusion's **CC Unity Tools (URP)**. Skip the `*_ResourceMap_*` textures.
5. Check items 1 and 7 below in Unity, which were not covered.

Re-run this checklist for every new model and add a row to `RIG_REPORT.md`:

1. Imports into Unity as a **Humanoid** avatar with no bone-mapping errors.
2. Has **finger bones** (needed for tremor and fidgeting).
3. Has **separate eye bones** or separate eye meshes that can rotate (needed for gaze).
4. Has **facial blendshapes**: the Character Creator standard set (or ARKit 52). Also list any visemes (for lip sync).
5. Has a **jaw bone** or jaw blendshape.
6. Triangle count, and number of materials.
7. Skin weights hold up when seated, crossing arms, hands to face, and slumped forward.

**If facial blendshapes are missing:** report it straight away and stop facial work. The fix (adding a face rig in Blender, or swapping models) is the project owner's call. Facial cues (`flat_affect`, `labile_affect`, `tearful`, `lip_smacking`, `self_talk`, lip sync) depend on it.

## 4. Patient models: what to deliver

For the vertical slice, use **both** Mégane (`female_20s_a`) and Matt (`male_20s_a`): every case has a female and a male variant chosen at the start (DESIGN §6.1 `variants`), so every clip and cue must look right on both. By Stage 2, at least 6 models covering a range of ages (teen, 20s, 30s–40s, 50s–60s) and both sexes, matching the case table in `DESIGN.md` 10.1. The sim is set in India, so **most new patients should be South Asian**, with everyday Indian clothing as well as the variants below. Make new patients in Character Creator from the same CC3+ base, so the skeleton, blendshapes and every animation carry over.

For each model:
- **Clothing variants:** `neat`, `casual`, `disheveled` (wrinkled and stained clothes, messy hair), `hospital_gown`. Sleeves must be able to roll up or be removed for the arm exam.
- **Skin decals** (off by default, turned on by code): `track_marks` (inside of the forearm), `self_harm_scars` (healed, pale, horizontal lines on the forearm; keep it realistic and not graphic). Use decal projectors or a detail mask on the skin material, so the developer can turn each one on with a single toggle.
- **Skin material** with a `_Wetness` value from 0 to 1 (sweat: more gloss, a subtle normal-map bead pattern on forehead, upper lip and neck).
- **Eye material** with `_Tearfulness` from 0 to 1 (wetter eyes, slight red rims, a tear-line mesh or decal at the lower lid) and `_PupilScale` from 0.5 to 1.6.

## 5. Animation list
All clips: **Humanoid, 30 fps, in place (no root motion) unless marked.** The default base is seated. Every clip must blend with any other base pose.

### 5.1 Base poses (full-body loops, 6–10 s)
| Clip | Description |
|---|---|
| `base_sit_neutral` | Upright, relaxed, small breathing and weight shifts |
| `base_sit_slumped` | Shoulders forward, head low, hands in lap |
| `base_sit_guarded` | Arms crossed, torso turned about 20° away, legs crossed |
| `base_sit_tense` | Upright on the edge of the seat, hands gripping the knees |
| `base_lie_bed` | Lying semi-upright on a bed (for the ward room) |
| `base_stand_idle` | Standing (for the agitated "tries to leave" moment) |

### 5.2 Additive cue layers (loops unless marked "one-shot")
Masks: **UpperBody**, **Arms**, **Hands**, **Legs**, **Head**. Name the mask in each file name.

| Clip | Mask | Cue id |
|---|---|---|
| `cue_fidget_nails_Hands` | Hands | `fidget` |
| `cue_fidget_sleeve_Arms` | Arms | `fidget` |
| `cue_leg_bounce_Legs` | Legs | `leg_bounce` |
| `cue_restless_shift` (one-shot, 3 variations) | Full body | `restless` |
| `cue_stand_and_pace` (root motion allowed) | Full body | `restless` (high intensity) |
| `cue_twitch_shoulder` / `cue_twitch_head` (one-shot) | UpperBody / Head | `twitch_tic` |
| `cue_yawn` (one-shot) | Head + UpperBody | `yawning` |
| `cue_sniff_wipe_nose` (one-shot) | Arms + Head | `sniffing` |
| `cue_scratch_forearm` / `cue_scratch_face` | Arms | `scratching` |
| `cue_startle` (one-shot) | Full body | `startle` |
| `cue_listen_to_voices` (one-shot: head tilts and pauses toward the empty corner) | Head + UpperBody | `internal_stimuli` |
| `cue_wipe_tears` (one-shot) | Arms | `tearful` |
| `gesture_talk_small` / `gesture_talk_animated` (3 each) | Arms | normal talking, and `pressured_speech` |
| `gesture_shrug`, `gesture_head_shake`, `gesture_nod` (one-shot) | UpperBody / Head | used by dialogue |
| `gesture_cover_face` (one-shot) | Arms + Head | distress |

### 5.2b Exam actions (one-shot, Stage 1; DESIGN §4.4)
| Clip | Mask | Action id |
|---|---|---|
| `action_hold_out_hands` | Arms + Hands (hold the pose ~4 s, palms down, so tremor can be seen) | `hold_out_hands` |
| `action_roll_up_sleeves` | Arms (ends with forearms exposed and turned up) | `roll_up_sleeves` |
| `action_look_at_light` | Head (chin level, eyes forward toward the doctor's penlight, hold ~3 s) | `look_at_light` |

Stage 2 adds `action_stand_up` and `action_walk_to_door`.

**Do not animate** gaze, tremors or slowed movement. The developer does those in code (look-at IK, noise on bones, animation speed). Your job is to make sure the rig supports them (section 3).

### 5.3 Facial expressions (blendshape presets; the provided rigs support them)
Save as Unity animation clips that only touch blendshapes: `face_neutral`, `face_sad`, `face_anxious`, `face_angry`, `face_ashamed`, `face_happy`, `face_flat` (neutral with less movement), `face_suspicious`, `face_confused`. These match the `emotion` field the dialogue system sends (`DESIGN.md` 7.2). Also `face_lip_smack` (a loop, for `lip_smacking`).

## 6. File layout and naming

```
Assets/Art/
  Environments/<Room>/         Room_<Room>.prefab, meshes, materials, textures
  Patients/<ModelId>/          <ModelId>.prefab, variants, materials
  Animations/Base/
  Animations/Cues/
  Animations/Gestures/
  Animations/Face/
  Masks/                       UpperBody.mask, Arms.mask, Hands.mask, Legs.mask, Head.mask
  RIG_REPORT.md
  ASSET_LIST.md                every delivered asset, its triangle count and its stage
```

- Use PascalCase for prefabs and snake_case for clips, exactly as in this brief. The developer's code looks them up by name.
- `<ModelId>` follows the pattern `<sex>_<agegroup>_<letter>`, for example `male_50s_a`. This must match `model_id` in case files.

## 7. Done means
- [ ] `RIG_REPORT.md` delivered at Stage 0, with any blockers raised.
- [ ] The consult room and one patient are in the Unity project, prefabs work, and the Unity console shows no import errors.
- [ ] Every clip in 5.1 and 5.2 plays on every patient model with no hand or arm passing through the body or chair.
- [ ] Every cue is clearly readable from the DoctorAnchor at 1.5 m, at 1080p on a Mac, with the cue at intensity 0.5. Send screenshots or short captures for each.
- [ ] Budgets in section 2 are met. List the numbers in `ASSET_LIST.md`.
- [ ] No content that looks graphic or mocking. Patients should look like real people having a bad day, not caricatures.
