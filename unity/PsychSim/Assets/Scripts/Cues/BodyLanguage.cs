using Newtonsoft.Json.Linq;
using UnityEngine;

namespace Rapport.Cues
{
    /// <summary>
    /// Body language from the brain (brain_snapshot: emotion, intensity 0-10, reaction, behaviour, state) plus idle life, as small
    /// procedural bone offsets on top of whatever clip plays: lean, slump, head pitch/turn/tilt, shoulders, a bouncing knee, posture
    /// shifts every so often, nods while the doctor talks, a head turn away and back when angry, a soft laugh when happy.
    /// It also sets floors on CueDriver (slump and fidget clips, slowing), gaze (eye contact, glance pace) and the face's intensity.
    /// Everything eases in and out; it fades to nothing during exam actions and while standing (CueDriver.CanMove).
    /// </summary>
    [DefaultExecutionOrder(750)]
    public class BodyLanguage : MonoBehaviour
    {
        /// <summary>Pose targets at a given emotion and intensity. Angles in degrees; the rest 0-1 unless noted.</summary>
        public struct Targets
        {
            public float lean, headPitch, headYaw, tilt, shoulderUp, shoulderFwd, slump, fidget, knee, slow, avoid, pace, motion;
        }

        public string Emotion = "neutral", Behaviour = "", Reaction = "";
        public float Intensity;          // 0-1 (the brain's 0-10 / 10)
        public float Trust = 50f;        // 0-100
        public bool Listening;           // the doctor is speaking (EncounterManager): small nods

        Animator anim;
        CueDriver cues;
        GazeController gaze;
        FacePresets face;
        Breathing breath;
        Transform body, spine, chest, upperChest, neck, head, lClav, rClav, lThigh;
        Targets cur;
        float clock, weight, turnAwayAt = -99f, turnSide = 1f, laughAt = -99f, nodAt = -99f, nextNod, nextShift;
        float shiftLean, shiftRoll, shiftYaw, sLean, sRoll, sYaw;

        public void Setup(Animator a, CueDriver c, GazeController g, FacePresets f)
        {
            anim = a; cues = c; gaze = g; face = f; body = a.transform;
            spine = a.GetBoneTransform(HumanBodyBones.Spine);
            chest = a.GetBoneTransform(HumanBodyBones.Chest);
            upperChest = a.GetBoneTransform(HumanBodyBones.UpperChest);
            neck = a.GetBoneTransform(HumanBodyBones.Neck);
            head = a.GetBoneTransform(HumanBodyBones.Head);
            lClav = a.GetBoneTransform(HumanBodyBones.LeftShoulder);
            rClav = a.GetBoneTransform(HumanBodyBones.RightShoulder);
            lThigh = a.GetBoneTransform(HumanBodyBones.LeftUpperLeg);
            breath = a.GetComponent<Breathing>();
            nextShift = Random.Range(6f, 14f);
            cur = For("neutral", 0f, "", 50f);
        }

        /// <summary>brain_snapshot from the service (EncounterManager.OnVoiceEvent).</summary>
        public void OnSnapshot(JObject o)
        {
            var st = o["state"] as JObject;
            Mood((string)o["emotion"] ?? "neutral", o["intensity"]?.Value<float>() ?? 0f, (string)o["reaction"] ?? "", (string)o["behaviour"] ?? "",
                 st?["trust"]?.Value<float>() ?? Trust);
        }

        public void Mood(string emotion, float intensity0to10, string reaction, string behaviour, float trust)
        {
            Emotion = emotion; Reaction = reaction; Behaviour = behaviour; Trust = trust;
            Intensity = Mathf.Clamp01(intensity0to10 / 10f);
            if ((emotion == "angry" || behaviour == "hostile") && Intensity >= 0.4f)
            {
                turnAwayAt = clock + 0.3f;
                turnSide = Random.value < 0.5f ? -1f : 1f;
                if (Intensity >= 0.6f) cues?.Gesture();
            }
            if (emotion == "happy" && Intensity >= 0.6f) { laughAt = clock + 0.2f; face?.Hold("face_laugh", 1.4f); }
            if (face) { face.SetEmotion(emotion); face.EmotionGain = 0.5f + 0.7f * Intensity; }
        }

        /// <summary>What each emotion does to the body, scaled by intensity (0-1). Trust moves eye contact for every emotion.</summary>
        public static Targets For(string emotion, float i, string behaviour, float trust)
        {
            var t = new Targets { pace = 1f, motion = 1f };
            switch (behaviour == "hostile" ? "angry" : emotion)
            {
                case "angry":      t.lean = 8f; t.headPitch = 3f; t.shoulderUp = 0.3f; t.avoid = 0.1f; t.pace = 0.8f; break;  // forward, chin down
                case "suspicious": t.lean = -3f; t.headPitch = 4f; t.headYaw = 8f; t.avoid = 0.1f; break;                    // back, side-on
                case "anxious":    t.lean = 2f; t.shoulderUp = 1f; t.fidget = 0.7f; t.knee = 1f; t.avoid = 0.25f; t.pace = 0.5f; t.motion = 1.3f; break;
                case "sad":        t.slump = 0.7f; t.headPitch = 12f; t.shoulderFwd = 0.6f; t.slow = 0.5f; t.avoid = 0.45f; t.pace = 1.4f; t.motion = 0.7f; break;
                case "ashamed":    t.slump = 0.5f; t.headPitch = 15f; t.headYaw = 10f; t.shoulderFwd = 0.5f; t.slow = 0.3f; t.avoid = 0.6f; t.pace = 1.3f; break;
                case "flat":       t.slump = 0.2f; t.headPitch = 3f; t.slow = 0.4f; t.motion = 0.3f; break;
                case "happy":      t.lean = 3f; t.headPitch = -2f; t.avoid = -0.15f; t.motion = 1.1f; break;
                case "confused":   t.tilt = 8f; t.headPitch = -2f; t.lean = 1f; break;
            }
            // intensity scales the emotion; pace and motion stay near 1 at low intensity
            t.lean *= i; t.headPitch *= i; t.headYaw *= i; t.tilt *= i; t.shoulderUp *= i; t.shoulderFwd *= i; t.slump *= i;
            t.fidget *= i; t.knee *= i; t.slow *= i; t.avoid *= i;
            t.pace = Mathf.Lerp(1f, t.pace, i); t.motion = Mathf.Lerp(1f, t.motion, i);
            t.avoid = Mathf.Clamp(t.avoid + (50f - trust) / 100f * 0.4f, -0.3f, 0.7f);  // trust 100 -> 0.2 more eye contact, 0 -> 0.2 less
            return t;
        }

        /// <summary>Envelope 0-1 of a gesture t seconds after it starts: ease in over `inT`, hold, ease out over `outT`.</summary>
        public static float Envelope(float t, float inT, float hold, float outT)
        {
            if (t < 0f || t > inT + hold + outT) return 0f;
            if (t < inT) return Mathf.SmoothStep(0f, 1f, t / inT);
            if (t < inT + hold) return 1f;
            return Mathf.SmoothStep(1f, 0f, (t - inT - hold) / outT);
        }

        void LateUpdate() => Step(Time.deltaTime);

        /// <summary>One frame (LateUpdate, or an editor render loop that drives the clock itself).</summary>
        public void Step(float dt)
        {
            if (!body) return;
            clock += dt;
            var tgt = For(Emotion, Intensity, Behaviour, Trust);
            float k = 1f - Mathf.Exp(-dt / 0.7f);  // ~0.7 s ease: moods change, they never pop
            cur.lean += (tgt.lean - cur.lean) * k; cur.headPitch += (tgt.headPitch - cur.headPitch) * k; cur.headYaw += (tgt.headYaw - cur.headYaw) * k;
            cur.tilt += (tgt.tilt - cur.tilt) * k; cur.shoulderUp += (tgt.shoulderUp - cur.shoulderUp) * k; cur.shoulderFwd += (tgt.shoulderFwd - cur.shoulderFwd) * k;
            cur.knee += (tgt.knee - cur.knee) * k; cur.motion += (tgt.motion - cur.motion) * k;
            weight = Mathf.MoveTowards(weight, cues == null || cues.CanMove ? 1f : 0f, dt * 1.5f);

            if (cues != null) { cues.MoodSlump = tgt.slump; cues.MoodFidget = tgt.fidget; cues.MoodSlow = tgt.slow; }
            if (gaze) { gaze.MoodAvoid = tgt.avoid; gaze.Pace = tgt.pace; }
            if (breath) { breath.Rate = 14f + 8f * (Emotion == "anxious" || Emotion == "angry" ? Intensity : 0f); breath.Depth = cur.motion; }

            // posture shifts: every 8-20 s (rarer when flat), settle somewhere slightly different over about a second
            if (clock > nextShift)
            {
                shiftLean = Random.Range(-2f, 2f); shiftRoll = Random.Range(-2.5f, 2.5f); shiftYaw = Random.Range(-3f, 3f);
                nextShift = clock + Random.Range(8f, 20f) / Mathf.Max(0.3f, cur.motion);
            }
            float ks = 1f - Mathf.Exp(-dt / 0.45f);
            sLean += (shiftLean * cur.motion - sLean) * ks; sRoll += (shiftRoll * cur.motion - sRoll) * ks; sYaw += (shiftYaw * cur.motion - sYaw) * ks;

            // nods while the doctor talks (not when angry, suspicious or flat)
            bool nods = Listening && Emotion != "angry" && Emotion != "suspicious" && Emotion != "flat" && Behaviour != "hostile";
            if (nods && clock > nextNod) { nodAt = clock; nextNod = clock + Random.Range(2.5f, 5.5f) * (Trust < 30f ? 1.6f : 1f); }
            float nod = Mathf.Sin(Mathf.Clamp01((clock - nodAt) / 0.7f) * Mathf.PI) * 5f * (clock - nodAt < 0.7f ? 1f : 0f);

            float away = Envelope(clock - turnAwayAt, 0.35f, 1.3f, 0.8f) * 22f * Intensity * turnSide;
            float laughT = clock - laughAt, laugh = Envelope(laughT, 0.15f, 0.9f, 0.4f);
            float bounce = laugh * Mathf.Abs(Mathf.Sin(laughT * Mathf.PI * 5f));   // shoulders shake about 5 times a second
            float knee = cur.knee * Mathf.Abs(Mathf.Sin(clock * Mathf.PI * 4.5f));  // heel bounce, ~4.5 Hz

            float w = weight;
            float lean = (cur.lean + sLean - 3f * laugh) * w;
            Rot(spine, body.right, lean * 0.4f); Rot(chest, body.right, lean * 0.35f); Rot(upperChest, body.right, lean * 0.25f);
            Rot(spine, body.forward, sRoll * 0.5f * w); Rot(spine, body.up, sYaw * 0.5f * w);
            Rot(neck, body.right, -lean * 0.5f);  // keep the eyes up on the doctor when leaning in
            Rot(head, body.up, (cur.headYaw * turnSide + away - sYaw * 0.5f) * w);
            Rot(head, body.right, (cur.headPitch + nod - 4f * laugh) * w);
            Rot(head, body.forward, -cur.tilt * w);
            float up = (cur.shoulderUp * 4f + bounce * 3f) * w, fwd = cur.shoulderFwd * 6f * w;
            Rot(lClav, body.forward, -up); Rot(rClav, body.forward, up);
            Rot(lClav, body.up, fwd); Rot(rClav, body.up, -fwd);
            Rot(lThigh, body.right, -1.5f * knee * w);
        }

        static void Rot(Transform t, Vector3 axis, float deg)
        {
            if (t && deg != 0f) t.rotation = Quaternion.AngleAxis(deg, axis) * t.rotation;
        }
    }
}
