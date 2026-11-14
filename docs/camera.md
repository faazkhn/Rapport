# Camera (Phase H)

`unity/PsychSim/Assets/Scripts/Platform/CameraDirector.cs` builds the doctor's view at runtime through Cinemachine 3, so the scene needs no rebuild. `DesktopRig` still does the mouse-look; it now steers the doctor's virtual camera instead of the real camera.

| State | Camera | Settings | Still |
|---|---|---|---|
| Doctor (default) | `DoctorView` virtual camera, priority 10 | Seated eye height 1.20 m, about 1.5 m from the patient's eyes (conversation distance), vertical FOV 30° (v0.3; was 42°): head to waist, the face about 200 px tall at 1080p. Follows the patient's head so it sits 30% from the left edge (clear of the side panel) and on the upper third: `DesktopRig.FollowRotation`, which the lighting stills use too, so stills and play mode frame her the same way. Right-drag looks around, limited to ±70° yaw and −35° to +30° pitch. | ![](media/v0.3/after/female_20s_a.png) |
| Lean in | same | Scroll up over the room: 0.25 m toward the patient over 0.4 s, FOV 26° (was 38°). Scroll down to sit back. Space is push-to-talk, so it is not used here. | ![](media/camera/camera_lean.jpg) |
| Hands (`hold_out_hands`) | `ExamCloseUp`, priority 20 | Midpoint of the hands, 0.85 m toward the doctor, FOV 32° | ![](media/camera/camera_hands.jpg) |
| Forearms (`roll_up_sleeves`, `show_forearms`) | same | Midpoint of the forearms, 0.9 m, FOV 34° | ![](media/camera/camera_forearms.jpg) |
| Eyes (`look_at_light`, `follow_finger`) | same | Between the eyes, 0.45 m, FOV 22° | ![](media/camera/camera_eyes.jpg) |
| Face and tongue (`open_mouth`, `stick_out_tongue`) | same | Jaw and head, 0.5 m, FOV 24° | ![](media/camera/camera_face.jpg) |
| Full body (`stand_up`, `walk_few_steps`, `sit_down`) | same | From the doctor's seat, FOV 70°. The room is about 1.1 m deep, so the camera cannot back off. | ![](media/camera/camera_body.jpg) |

- **Blends:** the Brain eases in and out over 0.6 s. A close-up starts only if its action is still running 0.3 s later, so "please have a seat" to a seated patient never cuts. It returns 0.5 s after the action ends (relax, a new command, or the 30 s hold cap).
- **Composition:** every close-up is turned so its subject sits about 35% left of centre, clear of the side panel.
- **Gaze:** the patient looks at the doctor by default. Gaze cues (`gaze_avoid`, the corner look) and exam gaze (`follow_finger`, the penlight) override it (`GazeController.Override`).
- **Demo cameras:** `DemoDirector` keeps its own separate cinematic camera (`DemoCam`) for recorded demos. The learner's camera never uses it.

Stills: Unity editor Play mode, Ananya, 1920×1080 game view with the UI, 2026-10-21 (the doctor row: `LightingStills`, v0.3).

**Seats (v0.3):** the patient's seat and the doctor's chair face 110° apart (brief: 90–120°; the exported room had about 156°). `EncounterSceneBuilder.AngleSeats` turns the patient about her hips, which stay on the sofa cushion, to face 10° past the doctor toward the desk side, and turns the `DoctorAnchor` 60° off the line toward the desk. The live view does not depend on the doctor's chair angle: it follows her head. `ExamController.WalkTurnDeg` moved from −45° to −77° so `walk_few_steps` keeps the same clear floor.
