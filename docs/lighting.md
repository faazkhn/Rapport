# Office lighting (DESIGN v0.3, brief §2)

Bright, warm, clinical but humane. Built in code, so `PsychSim/Build Placeholder Encounter Scene` reproduces it and bakes it:
`EncounterSceneBuilder.cs` (room extras) calls `EncounterLighting.cs` (lights, probes, post, bake settings).

## Spec and what was used

| Part | Spec | Setting |
|---|---|---|
| Key | soft daylight through the window, ~5,000 K, face lit three-quarters from the doctor's side | `KeyLight_Window`: spot, real-time, 5,000 K (colour-temperature mode), intensity 14, 70° outer / 25° inner, soft shadows 0.75, at (0.2, 1.95, 1.3) near the window, aimed at `KeyLightTarget`. About 65° off the patient's forward axis, on the doctor's side. |
| Window | window with blinds | 1.0 × 1.05 m on the south wall right of the desk, sill 0.95 m. Emissive pane (5,000 K × 2.5, baked emissive), off-white frame, 7 slats tilted 35° over the top half. `WindowDaylight_Area`: 0.95 × 1 m rectangle light, baked, 5,000 K, intensity 4. |
| Fill | warm practical lamp ~3,200 K | `FillLight_Ceiling`: point, baked, 3,200 K, intensity 0.7, range 5, at the ceiling centre. Reaches the patient through the light probes. |
| Rim | subtle, separates patient from the wall | `RimLight`: spot, real-time, 4,500 K, intensity 4, 30°, no shadows, behind the sofa at (1.3, 1.95, -1.0). |
| GI | baked GI, light probes around the chair, one reflection probe | Baked GI only (no real-time GI), GPU progressive, 12 texels/m, max 1024, non-directional, 2 bounces: one 1024 lightmap (0.46 MB EXR). `LightProbes`: coarse 0.65 m grid over the room (walk-in path) plus a dense cage around the sofa seat and head. `ReflectionProbe_Room`: baked, box-projected to the room, 128 px, solid warm background. Ambient flat (0.46, 0.46, 0.47). Sky reflection intensity stays 0, so the CC3 alpha-0 eye/hair layers no longer turn cyan: the eyes reflect the room. |
| Post | Neutral or ACES, exposure up, contrast +10, saturation +5, mild bloom, SSAO, very light vignette | `PostProcess` global volume, `Assets/Settings/PsychSim/EncounterVolume.asset`: Neutral tonemapping, post-exposure +0.35, contrast +10, saturation +5, bloom 0.25 (threshold 1.1, scatter 0.6), vignette 0.12. SSAO is the URP renderer feature already on `PC_Renderer` (intensity 0.4, radius 0.3). Post-processing is turned on for `DoctorCamera`. |
| Surfaces | off-white walls, one warm accent wall, no grey-on-grey | Room palette `T_Office_Palette.png` (Unity copy): wall cell grey → warm off-white (233, 226, 214), ceiling/cornice → (240, 236, 229), sofa-wall panelling dark grey → muted terracotta (172, 128, 110). |
| Real-time budget | key and rim real-time, fill and bounce baked | Two real-time lights (key and rim). Only the key casts real-time shadows. |

A note for anyone changing this: set light colour with `useColorTemperature` + `colorTemperature`, not with
`light.color = Mathf.CorrelatedColorTemperatureToRGB(k)`. That function returns linear RGB, but `light.color` is sRGB, so the
first pass came out far too orange: 3,200 K looked like about 2,000 K.

## Acceptance

`tools/lighting/face_luminance.py STILL.png` (numpy + PIL, for example with `server/patient-service/.venv/bin/python`).
- **Face mean** is Rec.709 relative luminance, Y = 0.2126 R + 0.7152 G + 0.0722 B, on sRGB-decoded (linear) pixel values. Luma on the encoded values is printed too, for reference.
- **Face box:** the `*.face.json` next to each still, projected from the eye bones by `PsychSim/Capture Lighting Stills` (`LightingStills.cs`). It covers brow to chin and cheek to cheek. `--box x0 y0 x1 y1` overrides it.
- **Crushed / blown:** % of all frame pixels with Y < 0.02 / Y > 0.98.
- **Setup:** `DoctorCamera` at the DoctorAnchor, 1920×1080, 4× MSAA, patient seated at the PatientAnchor on `base_sit_neutral` frame 0.

| Still | Face mean Y (target 0.45–0.60) | Luma | Crushed | Blown | Result |
|---|---|---|---|---|---|
| Before, Mégane (`female_20s_a`) | 0.624 | 0.779 | 4.01 % | 7.82 % | fail (hot face, blown whites) |
| After, Mégane (`female_20s_a`) | **0.502** | 0.696 | 3.62 % | 0.00 % | pass |
| After, Matt (`male_20s_a`) | **0.500** | 0.692 | 2.31 % | 0.00 % | pass |

The crushed pixels in the after stills are the patient's black clothing and the gaps under the shelves. None of them are on the face.
The before still was the old look: one hot spot on the face, flat grey ambient, grey walls, no tonemapping. Its frame was
dull while the face was over-exposed. The stills are compressed to stay under 1.5 MB: the before still is a 256-colour PNG
and the after stills are posterised to 7 bits per channel. They were measured after compression, which moved the face mean
by less than 0.005.

### Before
![before](media/lighting_before.png)

### After, Mégane
![after female](media/lighting_after_female.png)

### After, Matt
![after male](media/lighting_after_male.png)

## Performance (editor, M-series Mac)
- Play mode with a patient seated: about 100 fps in a 1245×1016 Game view, with editor overhead.
- Rendering the DoctorCamera off-screen at 1920×1080: 3.45 ms per frame (about 290 fps).
- Visible from the doctor view: 15 renderers and 28 material slots. The room shares 3 materials (palette, window frame, tissue box) plus the emissive pane, and is static-batched. SetPass calls: 43, counting the shadow, depth and SSAO passes. That is well under the 100 draw-call budget.
- Triangles: the room is about 14.1k (the pack's 13,960 plus primitives for the window and tissues). The patients are 83.8k (Mégane) and 79.5k (Matt), both under 90k.

## Reproduce
1. `PsychSim/Build Placeholder Encounter Scene`. It rebuilds the scene and starts the bake, then saves again when the bake is done (about 30 s).
2. `PsychSim/Capture Lighting Stills`. It writes `docs/media/lighting_after_{female,male}.png` and `.face.json`. The PNGs are full quality, about 2 MB each, so posterise them to 7 bits before you commit them.
3. `python tools/lighting/face_luminance.py docs/media/lighting_after_female.png` (exit code 1 on a fail).
