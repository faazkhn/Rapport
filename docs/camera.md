# Camera (Phase H)

`unity/PsychSim/Assets/Scripts/Platform/CameraDirector.cs` builds the doctor's view at runtime through Cinemachine 3, so the scene needs no rebuild. `DesktopRig` still does the mouse-look; it now steers the doctor's virtual camera instead of the real camera.

| State | Camera | Settings | Still |
|---|---|---|---|
| Doctor (default) | `DoctorView` virtual camera, priority 10 | Seated eye height 1.20 m, vertical FOV 42°. Follows the patient's head with a 17° yaw (clear of the side panel) and a 7° pitch (her eyes in the upper third). Right-drag looks around, limited to ±70° yaw and −35° to +30° pitch. | ![](media/camera/camera_doctor.jpg) |
| Lean in | same | Scroll up over the room: 0.25 m toward the patient over 0.4 s, FOV 38°. Scroll down to sit back. Space is push-to-talk, so it is not used here. | ![](media/camera/camera_lean.jpg) |
| Hands (`hold_out_hands`) | `ExamCloseUp`, priority 20 | Midpoint of the hands, 0.85 m toward the doctor, FOV 32° | ![](media/camera/camera_hands.jpg) |
| Forearms (`roll_up_sleeves`, `show_forearms`) | same | Midpoint of the forearms, 0.9 m, FOV 34° | ![](media/camera/camera_forearms.jpg) |
| Eyes (`look_at_light`, `follow_finger`) | same | Between the eyes, 0.45 m, FOV 22° | ![](media/camera/camera_eyes.jpg) |
| Face and tongue (`open_mouth`, `stick_out_tongue`) | same | Jaw and head, 0.5 m, FOV 24° | ![](media/camera/camera_face.jpg) |
| Full body (`stand_up`, `walk_few_steps`, `sit_down`) | same | From the doctor's seat, FOV 70°. The room is about 1.1 m deep, so the camera cannot back off. | ![](media/camera/camera_body.jpg) |

- **Blends:** the Brain eases in and out over 0.6 s. A close-up starts only if its action is still running 0.3 s later, so "please have a seat" to a seated patient never cuts. It returns 0.5 s after the action ends (relax, a new command, or the 30 s hold cap).
- **Composition:** every close-up is turned so its subject sits about 35% left of centre, clear of the side panel.
- **Gaze:** the patient looks at the doctor by default. Gaze cues (`gaze_avoid`, the corner look) and exam gaze (`follow_finger`, the penlight) override it (`GazeController.Override`).
- **Demo cameras:** `DemoDirector` keeps its own separate cinematic camera (`DemoCam`) for recorded demos. The learner's camera never uses it.

Stills: Unity editor Play mode, Ananya, 1920×1080 game view with the UI, 2026-10-21.
