using System;
using System.Collections.Generic;
using System.Linq;
using PsychSim.Data;
using PsychSim.Patient;
using UnityEngine;

namespace PsychSim.Cues
{
    /// <summary>
    /// Live cue intensities (brief 3.5): live = clamp01(base + gains·state/100 + time_gain·minutes) + active event boosts,
    /// sent each frame to the Animator layers, gaze, tremor, face and material controllers.
    /// </summary>
    public class CueDriver : MonoBehaviour
    {
        public event Action<string, float> CueFired;    // event boosts and one-shot clips
        public event Action<string, float> CueChanged;  // live intensity moved by >= 0.1 (for SessionLog)
        public readonly Dictionary<string, float> Live = new();
        public bool Seated;                              // false during the entrance: no seated layers or gaze
        public bool ExamBusy;                            // an ExamController action is running or held: no talk gestures, nods or tear wipes

        CaseFile caseFile;
        PatientState state;
        Func<float> minutes;
        Animator anim;
        GazeController gaze;
        TremorController tremor;
        MaterialCueController materials;
        FacePresets face;
        readonly List<(string id, float boost, float until)> boosts = new();
        readonly Dictionary<string, float> logged = new();
        readonly Dictionary<int, float> layerTarget = new();
        int lFidget, lTalk, lArms, lHead;
        float nextWipe, talkingUntil;
        // ExamController aims the fingertips under the eye with IK (the shared clip alone touched Mégane's nose and sank into Matt's cheek)
        public static bool WipeTears = true;
        HashSet<string> clips;

        public void Init(CaseFile c, PatientState s, Func<float> sessionMinutes, Animator animator, GazeController g, TremorController t, MaterialCueController m, FacePresets f)
        {
            caseFile = c; state = s; minutes = sessionMinutes; anim = animator; gaze = g; tremor = t; materials = m; face = f;
            clips = new HashSet<string>(anim.runtimeAnimatorController.animationClips.Select(x => x.name));
            lFidget = anim.GetLayerIndex("Fidget"); lTalk = anim.GetLayerIndex("Talk"); lArms = anim.GetLayerIndex("ArmsOneShot"); lHead = anim.GetLayerIndex("Head");
            nextWipe = Time.time + 20f;
            foreach (var cue in c.cues) Live[cue.id] = 0;
        }

        public bool HasClip(string name) => clips != null && clips.Contains(name);
        public float Get(string id) => Live.TryGetValue(id, out var v) ? v : 0f;

        public static float Compute(CaseCue c, PatientState s, float minutes, float boosts) =>
            Mathf.Clamp01(Mathf.Clamp01(c.@base + c.trust_gain * s["trust"] / 100f + c.distress_gain * s["distress"] / 100f + c.agitation_gain * s["agitation"] / 100f
                                        + c.engagement_gain * s["engagement"] / 100f + c.time_gain_per_min * minutes) + boosts);

        public void OnPatientReplied(PatientTurn turn)
        {
            foreach (var e in turn.reply.event_cues) Boost(e.id, e.intensity, e.duration_s);
            foreach (var c in caseFile.cues)
                if (c.on_facts.Intersect(turn.reply.revealed_fact_ids).Any()) Boost(c.id, c.event_boost ?? 0.4f, c.event_duration_s ?? 4f);
            face?.SetEmotion(turn.reply.emotion);
        }

        public void Boost(string id, float amount, float seconds)
        {
            if (!Live.ContainsKey(id)) return;
            boosts.Add((id, amount, Time.time + seconds));
            CueFired?.Invoke(id, amount);
        }

        /// <summary>Talk gestures (and a nod or head shake on a plain yes/no) while the patient's audio plays.</summary>
        public void OnSpeechStarted(string utterance, float seconds)
        {
            talkingUntil = Time.time + seconds;
            if (HasClip("gesture_talk_small_01")) anim.CrossFade(UnityEngine.Random.value < 0.5f ? "gesture_talk_small_01" : "gesture_talk_small_02", 0.3f, lTalk);
            var u = utterance.TrimStart().ToLowerInvariant();
            if (InExamAction || ExamBusy) return;
            if (u.StartsWith("yes") || u.StartsWith("yeah") || u.StartsWith("hmm, yes")) PlayOneShot(lHead, "gesture_nod");
            else if (u.StartsWith("no") && !u.StartsWith("not")) PlayOneShot(lHead, "gesture_head_shake");
        }

        /// <summary>Exam action (plan B1) the service accepted: plays its clip; the fine tremor shows on the held-out hands, a squint on the light.</summary>
        public float PlayExamAction(string action)
        {
            int layer = action == "look_at_light" ? lHead : lArms;
            var state = "action_" + action;
            if (!HasClip(state)) return 0f;
            PlayOneShot(layer, state);
            examUntil = Time.time + anim.runtimeAnimatorController.animationClips.First(c => c.name == state).length;
            if (action == "hold_out_hands") Boost("tremor_fine", 0.35f, 6f);
            if (action == "look_at_light") face?.Hold("face_squint", 4.5f);
            return examUntil - Time.time;
        }

        float examUntil;
        public bool InExamAction => Time.time < examUntil;

        void PlayOneShot(int layer, string state)
        {
            if (!HasClip(state) || layer < 0) return;
            anim.CrossFade(state, 0.2f, layer, 0f);
            layerTarget[layer] = 1f;
        }

        void Update()
        {
            if (caseFile == null) return;
            float now = Time.time, mins = minutes();
            boosts.RemoveAll(b => b.until < now);
            foreach (var c in caseFile.cues)
            {
                float v = Compute(c, state, mins, boosts.Where(b => b.id == c.id).Sum(b => b.boost));
                Live[c.id] = v;
                if (!logged.TryGetValue(c.id, out var last) || Mathf.Abs(v - last) >= 0.1f) { logged[c.id] = v; CueChanged?.Invoke(c.id, v); }
            }

            float slowed = Get("slowed"), tearful = Get("tearful");
            if (Seated) anim.speed = Mathf.Lerp(1f, 0.7f, slowed);  // the entrance owns speed until seated
            anim.SetFloat("Slumped", Get("slumped"), 0.5f, Time.deltaTime);
            gaze.AvoidShare = Get("gaze_avoid");
            tremor.FineTremor = Get("tremor_fine");
            tremor.Restless = Seated ? Get("restless") : 0f;
            materials.Tearfulness = tearful;
            if (face) face.Scale = 1f - 0.7f * Get("flat_affect");

            // layer weights: fidget follows intensity, talk while speaking, one-shots until their clip ends
            if (lFidget >= 0) layerTarget[lFidget] = Seated && HasClip("cue_fidget_nails_Hands") ? Get("fidget") : 0f;
            if (lTalk >= 0) layerTarget[lTalk] = Seated && !InExamAction && !ExamBusy && now < talkingUntil && HasClip("gesture_talk_small_01") ? 0.8f : 0f;
            foreach (var l in new[] { lArms, lHead })
                if (l >= 0 && layerTarget.TryGetValue(l, out var w) && w > 0 && !anim.IsInTransition(l) && anim.GetCurrentAnimatorStateInfo(l).normalizedTime >= 0.95f
                    && !anim.GetCurrentAnimatorStateInfo(l).IsName("Empty"))
                {
                    layerTarget[l] = 0f;
                    anim.CrossFade("Empty", 0.25f, l);
                }
            if (!Seated) { layerTarget[lArms] = 0; layerTarget[lHead] = 0; }

            // tearful: wipe the tears now and then, more often as it rises
            if (WipeTears && Seated && tearful > 0.45f && now > nextWipe && now > talkingUntil && !InExamAction && !ExamBusy)
            {
                PlayOneShot(lArms, "cue_wipe_tears");
                CueFired?.Invoke("tearful", tearful);
                nextWipe = now + Mathf.Lerp(45f, 12f, (tearful - 0.45f) / 0.55f);
            }

            foreach (var kv in layerTarget)
                if (kv.Key >= 0) anim.SetLayerWeight(kv.Key, Mathf.MoveTowards(anim.GetLayerWeight(kv.Key), kv.Value, Time.deltaTime * 3f));
        }
    }

    /// <summary>Psychomotor slowing on the voice: up to 1.2 s before replying and TTS speed lowered toward 0.9 (mirrors the service).</summary>
    public static class SpeechTiming
    {
        public static float PreReplyDelay(float slowed) => slowed < 0.1f ? 0f : 0.4f + 0.8f * slowed;  // mirrors brain.slowed_pause_s: at most 1.2 s
        public static float TtsSpeed(float baseSpeed, float slowed) => Mathf.Lerp(baseSpeed, Mathf.Min(baseSpeed, 0.9f), slowed);
    }
}
