# Live demo guide: running Rapport in front of your mentors

Everything runs on this Mac: no internet is needed once the models are downloaded. Allow 10 minutes for setup and 10–15 minutes for the demo.

> **Status (2026-10-21, end of Phase G):** the app in `unity/Rapport/Builds/` is rebuilt with the Digital Twin and the new voice (Option A). To rebuild it, use the Unity menu **Rapport > Build macOS (Development)**. Clinical content is a draft and not faculty-validated: say so at the start.

## 1. The day before

- [ ] Charge the Mac and keep it on power during the demo (the model runs on the GPU).
- [ ] Close heavy apps (browsers with many tabs, video calls). The patient answers in about 2.3 s (p50), up to about 3 s. The new emotional voice and the language model share the GPU.
- [ ] Run one full rehearsal using the script in section 4.
- [ ] Check the microphone: System Settings > Privacy & Security > Microphone, allowed for Unity (or for Rapport/PsychSim once rebuilt).
- [ ] Use a headset or earphones with a mic if the room echoes. Speakers plus an open mic can make the patient hear herself.

## 2. Start everything (15 minutes before)

Open Terminal in the project folder (`~/Documents/Med`).

1. **Start the patient service** (it starts the local language model too; the first start takes about 20–40 s):
   ```bash
   server/patient-service/run.sh
   ```
   Leave this window open. It is ready when this prints `{"ok":true,...}`. In the service window, check for `TTS backend qwen3-design loaded`. If it says `failed to load ... using KittenTTS`, the patient still talks, but in the older, flatter voice. To force the old voice, start with `RAPPORT_TTS=kitten server/patient-service/run.sh`.
   ```bash
   curl -s http://127.0.0.1:8765/health
   ```
2. **Open the patient:**
   - **Option A:** double-click `Rapport.command`. It starts the service if needed and opens the app.
   - **Option B (editor):** open Unity Hub, then the project `unity/PsychSim`, then the scene `Assets/Scenes/Encounter.unity`, and press **Play**. Maximise the Game view (Shift+Space).
3. **Open the Digital Twin view** on a second screen or projector (`Rapport.command` opens it for you):
   `http://127.0.0.1:8765/twin/`
   It fills in when the session starts. This is the examiner's view; position it where the mentors can see it.
   - **On a second laptop on the same Wi-Fi:** open `http://<this Mac's IP>:8765/twin/`. `run.sh` and `Rapport.command` print the address (`ipconfig getifaddr en0`). Allow incoming connections if macOS asks. Only the Twin view is shared; the voice session and everything else answer this Mac only. The Twin shows the conversation text, so on a public network start with `RAPPORT_HOST=127.0.0.1` to keep it local.

## 3. During the demo

- On the start screen pick a case (**Tired all the time**, **Shaky in the mornings** for alcohol, or a ward station), the **Patient**, optionally a **Look** (each sex has two bodies), and **Practice** mode, then **Continue**.
- **Hold Space while you speak** (push-to-talk, the default), and let go when you finish. The bar shows **Hold Space to talk → Hearing you → Thinking → Speaking**.
- With a headset in a quiet room you can switch to **hands-free** (the button in the voice bar; the choice is remembered). With speakers, stay on push-to-talk: an open mic hears the patient and cuts her off. You can also type into the box at the bottom.
- To show the Twin, point out after a few turns:
  - **Trust** rising when you are kind and open,
  - a **memory unlocking** (grey chip turns green),
  - the **why** line ("Touched something locked (needs trust 55)…") when you ask about suicide too early,
  - the patient's **reaction**, **behaviour** and **mood dot** changing.
- **Exam commands** work in your own words, typed or spoken: "Kindly hold out your hands", "Show me your tongue", "Roll up your sleeves", "Look at the light", "Follow my finger", "Stand up and walk a few steps", then "Sit down".
  - She does them in order and holds until you say "relax" (or 30 s), and the camera cuts to a close-up.
  - At low trust or high agitation she refuses in words.
  - "Hold out your hand" makes her ask "Which hand?".
  - The full list and accuracy are in `docs/exam-actions.md`.
- **Lean in:** scroll up over the room. Scroll down to sit back. Right-drag to look around.
- Finish with the tabs: **MSE**, **Diagnosis**, **Prescription**, **Disposition**, then **Finish** to show the scored debrief: a global rating, the three things to do next time, your MSE against what the patient actually showed (ticking signs that were not there now costs marks), and AI examiner notes that fill in after a few seconds. Method and sources: `docs/literature/evaluation-and-assessment.md`.
- Exam on the alcohol case: ask them to hold their hands out (coarse tremor) and roll up their sleeves (forearms, no marks).

## 4. A 6-minute script that shows everything

| You say | What to point out |
|---|---|
| "Hello, I'm Dr. ___, one of the doctors here. Please have a seat. What brings you in today?" | Guarded, short first answer; low trust |
| "Before we start: what you tell me stays between us and the care team, unless I'm worried about your safety." | Trust rises (confidentiality) |
| "How have you been sleeping?" | Sleep memory unlocks: wakes at 4 a.m. |
| "That sounds exhausting. How has your mood been?" | Empathy raises trust; mood memory |
| "Are there things you used to enjoy that you've stopped?" | Stopped singing; more open |
| "Sometimes when people feel this low, they have thoughts of not wanting to be alive. Have you had thoughts like that?" | Asked early: a locked memory is touched, she is evasive, the Twin shows why |
| (Later, at higher trust) ask the same question again, gently | She discloses passive death wishes, with no plan |
| "Can you hold your hands out in front of you for me?" | Hands out toward you with a fine tremor; close-up of the hands. She holds them until you say "Okay, you can relax" (trust 10 or more) |
| "Show me your tongue" | Face close-up, tongue out (trust 15 or more) |
| "Could you stand up and walk a few steps for me? Then sit down." | Stands, walks out and back, sits; wide shot |

## 5. If something goes wrong

| Problem | Fix |
|---|---|
| The patient doesn't answer | Check the service window for errors and `curl -s http://127.0.0.1:8765/health`. Restart `run.sh`. |
| Answers take 4 s or more | Close other apps; make sure the Mac is on power. The first answer after start is slower. As a last resort, use the lighter voice: `RAPPORT_TTS=kitten`. |
| The voice stutters or breaks mid-sentence | Should not happen any more: the service now holds each sentence until it can play through. If replies get slow instead, the GPU is overloaded: close other apps (and screen recorders), restart `run.sh` if it has been up for days, or use `RAPPORT_TTS=kitten`. |
| She sounds like a different woman from line to line | Note which lines and tell the developer: this is a known risk of the designed voice. |
| She hears herself or interrupts | Use a headset, or switch to push-to-talk. |
| The Twin view is empty | Reload the page after the session starts; it catches up automatically. On the second laptop, check both are on the same Wi-Fi and that the service was started by the current `run.sh` (it prints the network address). |
| Unity shows "Service error" | The service isn't running or crashed: restart `run.sh`, then press Play again. |
| Something odd mid-demo | Use the typed input; it goes through the same patient brain. |

## 6. What to say about limits (honest framing)

- The clinical case is a draft written for the simulator and not yet faculty-validated.
- Voices are synthetic: designed from a text description, never cloned from a real person. The tone follows the patient's emotion and the Digital Twin's reaction on each line.
- Exam commands are matched by rules, not understood by the model. Unusual phrasings may be missed; rephrase plainly. The walk is short because the room is small.
