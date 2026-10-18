# PsychSim demo v1: shot list

`demo/PsychSim_demo_v1.mp4`: 1920x1080, 60 fps, H.264 high, AAC 192k, 178.6 s, -15.8 LUFS integrated.

| Time (approx.) | Shot | What it shows |
|---|---|---|
| 0:00 | Title card | "PsychSim · Clinical encounter simulator · For education only" |
| 0:03 | Doctor view + brief card | Case brief, draft banner, content note |
| 0:06 | Sofa-corner tracking shot | Door opens, Kavya walks in from the corridor, turns and sits on the sofa |
| 0:16 | Doctor POV with tablet | Greeting, sleep and appetite, confidentiality and mood (tearful cue), empathy (guilt, gaze drop) |
| 1:35 | Close-up | Kind, direct question about not wanting to live; she discloses passive suicidal thoughts (tearful) |
| 1:55 | Close-up | Plan and means: none |
| 2:15 | Tablet UI | MSE ticks, primary diagnosis, sertraline on the prescription pad, outpatient referral + safety plan |
| 2:40 | Score screen | "No critical errors", domain scores, cues recorded, teaching points, draft banner |
| 2:53 | End card | Coming next (voice input, 10 cases, VR on Quest 3S), "Draft content, not yet faculty-validated", note that replies were scripted for this take |

Stills for slides: `demo/stills/still_1.png` … `still_6.png`.

## How to re-record

1. `cd server/patient-service && PSYCHSIM_DEMO_SCRIPT=$PWD/../../demo/script.json ./run.sh --mock`
2. In Unity: **PsychSim/Record Demo**, with the editor window in front (an unfocused editor drops below 60 fps and the audio drifts). The take is written to `demo/raw/PsychSim_take.mp4`.
3. `server/patient-service/.venv/bin/python tools/demo/post.py` writes the final MP4, check frames (`demo/raw/check/`) and stills.

The doctor lines, patient lines and tool actions all live in `demo/script.json`. `tests/test_mock.py::test_demo_script_reveals_every_scripted_fact` checks that every scripted fact clears the trust gates.
