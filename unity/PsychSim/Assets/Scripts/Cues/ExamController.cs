using System;
using System.Collections;
using System.Collections.Generic;
using Newtonsoft.Json.Linq;
using UnityEngine;

namespace Rapport.Cues
{
    /// <summary>
    /// Plays the exam actions the service routed (Phase H) from an ExamQueue:
    /// - hold_out_hands: humanoid hand IK toward the doctor, the hand turned palm up or down;
    /// - sleeves, forearms, the penlight: clips frozen at their hold pose; the sleeves follow the rolling strokes (SleeveRoller);
    /// - mouth and tongue: jaw bone and blendshapes;
    /// - follow_finger: a moving gaze target;
    /// - stand, sit and a short walk out and back.
    /// Holds until relax, a new command or 30 s, and the fine tremor stays visible during the hold.
    /// Also aims the wipe_tears fingertips under the eye with IK.
    /// Must sit on the Animator's GameObject (OnAnimatorIK).
    /// </summary>
    [DefaultExecutionOrder(200)]  // after default-order scripts; FacePresets, TremorController and LipSyncBridge run later, so the tremor stays on the presented hands
    public class ExamController : MonoBehaviour
    {
        public event Action<string> ExamStarted, ExamEnded;
        public readonly ExamQueue Queue = new();
        public float WalkTurnDeg = -77f;    // Encounter room: the clear floor (world yaw -135°, toward -z), away from the doctor's chair; her seat faces about -58° since the seat-angle fix (was -90° and -45 here)
        public float WalkSeconds = 1.1f;    // per leg, about 1.2 m of walk_in

        // normalized hold poses: action_hold_out_hands 1.5-5.7 s of 8, action_roll_up_sleeves 7.75-10.8 s of 13, action_look_at_light 1.0-4.7 s of 6
        const float HandsHold = 0.3f, RollHold = 0.62f, LightHold = 0.3f;
        // where each clip starts lowering (end of its hold section): on release it jumps there, the pose is the same, so the hands come down now
        const float HandsLower = 0.71f, RollLower = 0.83f, LightLower = 0.78f;
        // the strokes that roll each sleeve (make_clips.py roll_up_sleeves: left 1.35-3.45 s, right 4.9-6.6 s of 13)
        const float ForearmsUpAt = 6.9f;  // s into the clip: both forearms start turning up for the hold
        static readonly Vector2 RollLeft = new(1.35f / 13f, 3.45f / 13f), RollRight = new(4.9f / 13f, 6.6f / 13f);
        Animator anim;
        CueDriver cues;
        GazeController gaze;
        FacePresets face;
        SleeveRoller sleeves;
        Transform doctor, jaw, followTarget;
        readonly List<(SkinnedMeshRenderer smr, int idx)> jawShapes = new(), tongueShapes = new();
        int lArms, lHead;
        float stepStart, handW, mouthW, tongueW, forearmW, nextRefresh;
        bool motionDone, skipPosture;
        string handsWhich = "both", palms = "down";
        Coroutine walk;
        readonly (Vector3 fingers, Vector3 palm)[] handAxes = new (Vector3, Vector3)[2];

        public void Setup(Animator a, CueDriver c, GazeController g, FacePresets f, Transform doctorFace, SleeveRoller s = null)
        {
            anim = a; cues = c; gaze = g; face = f; doctor = doctorFace; sleeves = s;
            lArms = a.GetLayerIndex("ArmsOneShot"); lHead = a.GetLayerIndex("Head");
            foreach (var t in GetComponentsInChildren<Transform>()) if (t.name == "CC_Base_JawRoot") jaw = t;
            foreach (var smr in GetComponentsInChildren<SkinnedMeshRenderer>())
            {
                int j = smr.sharedMesh.GetBlendShapeIndex("Jaw_Open"), t = smr.sharedMesh.GetBlendShapeIndex("Tongue_Out");
                if (j >= 0) jawShapes.Add((smr, j));
                if (t >= 0) tongueShapes.Add((smr, t));
            }
            followTarget = new GameObject("ExamFollowTarget").transform;
            handAxes[0] = HandAxes(true);
            handAxes[1] = HandAxes(false);
            CacheFingers();
            Queue.Started += OnStarted;
            Queue.Ended += OnEnded;
        }

        /// <summary>The service's `exam` message: {"actions": [{id, slots, comply}], "relax": bool}.</summary>
        public void Receive(JObject msg)
        {
            var steps = ExamQueue.Parse(msg, out bool relax);
            if (relax) Queue.Relax();
            if (steps.Count > 0) Queue.Enqueue(steps);
        }

        void OnStarted(ExamStep s)
        {
            stepStart = Time.time;
            motionDone = skipPosture = false;
            cues.ExamBusy = true;
            switch (s.id)
            {
                case "hold_out_hands":  // the clip gives level arms and spread fingers; IK turns them to the doctor, one hand or both
                    handsWhich = s.which; palms = s.palms;
                    if (UseHandsClip) cues.PlayExamAction("hold_out_hands");
                    break;
                case "roll_up_sleeves": case "show_forearms":
                    cues.PlayExamAction("roll_up_sleeves");
                    // nothing to roll (a sleeveless top): skip the strokes and turn the forearms up to show them
                    if (sleeves && !sleeves.HasSleeves) anim.CrossFadeInFixedTime("action_roll_up_sleeves", 0.5f, lArms, ForearmsUpAt);
                    break;
                case "look_at_light": cues.PlayExamAction("look_at_light"); break;
                case "follow_finger": gaze.Override = followTarget; break;
                case "stand_up":
                    skipPosture = !cues.Seated;  // already standing
                    if (!skipPosture) { cues.Seated = false; anim.CrossFade("stand_up", 0.25f, 0, 0f); }
                    break;
                case "sit_down":
                    skipPosture = cues.Seated;   // "Please have a seat" while she is seated: nothing to do
                    if (!skipPosture) anim.CrossFade("sit_down", 0.25f, 0, 0f);
                    break;
                case "walk_few_steps": walk = StartCoroutine(Walk()); break;
            }
            ExamStarted?.Invoke(s.id);
        }

        void OnEnded(ExamStep s)
        {
            if (s.id == "hold_out_hands") Lower(lArms, "action_hold_out_hands", HandsLower);
            if (s.id is "roll_up_sleeves" or "show_forearms") Lower(lArms, "action_roll_up_sleeves", RollLower);
            if (s.id == "look_at_light") Lower(lHead, "action_look_at_light", LightLower);
            if (s.id == "follow_finger") gaze.Override = null;
            if (s.id == "sit_down") cues.Seated = true;
            cues.ExamBusy = false;
            ExamEnded?.Invoke(s.id);
        }

        void Lower(int layer, string state, float lowerAt)
        {
            if (layer >= 0 && anim.GetCurrentAnimatorStateInfo(layer).IsName(state) && Norm(layer, state) < lowerAt) anim.Play(state, layer, lowerAt);
        }

        bool MotionDone(ExamStep c)
        {
            float t = Time.time - stepStart;
            if (t > 20f) return true;  // a clip that never started (missing, or cleared by another layer change) must not stall the queue
            var base0 = anim.GetCurrentAnimatorStateInfo(0);
            return c.id switch
            {
                "hold_out_hands" => t > 0.8f && (!UseHandsClip || Norm(lArms, "action_hold_out_hands") >= HandsHold),
                "open_mouth" or "stick_out_tongue" => t > 0.5f,
                "roll_up_sleeves" or "show_forearms" => t > 0.3f && Norm(lArms, "action_roll_up_sleeves") >= RollHold,
                "look_at_light" => t > 0.3f && Norm(lHead, "action_look_at_light") >= LightHold,
                "follow_finger" => t > 6f,
                "stand_up" => skipPosture || base0.IsName("stand_idle"),
                "sit_down" => skipPosture || (t > 0.5f && base0.IsName("Seated")),
                "walk_few_steps" => walk == null,
                _ => true,
            };
        }

        bool UseHandsClip => cues.Seated && handsWhich == "both";  // the clip raises both arms

        float Norm(int layer, string state)
        {
            var st = anim.GetCurrentAnimatorStateInfo(layer);
            return layer >= 0 && st.IsName(state) ? st.normalizedTime : 0f;
        }

        void Update()
        {
            if (anim == null) return;
            var c = Queue.Current;
            if (c != null && !Queue.Holding) motionDone = MotionDone(c);
            Queue.Tick(Time.time, motionDone);
            c = Queue.Current;
            string id = c?.id;

            if (Queue.Holding)  // keep the clip at its hold pose; on release it plays on to the lap and CueDriver clears the layer
            {
                if (id == "hold_out_hands" && UseHandsClip) anim.Play("action_hold_out_hands", lArms, HandsHold);
                if (id is "roll_up_sleeves" or "show_forearms") anim.Play("action_roll_up_sleeves", lArms, RollHold);
                if (id == "look_at_light") { anim.Play("action_look_at_light", lHead, LightHold); gaze.LookAtDoctor(0.5f); }
                if (Time.time > nextRefresh)
                {
                    nextRefresh = Time.time + 4f;
                    if (id == "hold_out_hands") cues.Boost("tremor_fine", 0.35f, 5f);
                    if (id == "look_at_light") face?.Hold("face_squint", 4.5f);
                }
            }
            if (id == "follow_finger") MoveFollowTarget(Time.time - stepStart);
            if (sleeves && Norm(lArms, "action_roll_up_sleeves") is var n and > 0f)  // follow the hand's strokes; they stay rolled up
            {
                sleeves.Left = Mathf.Max(sleeves.Left, Mathf.InverseLerp(RollLeft.x, RollLeft.y, n));
                sleeves.Right = Mathf.Max(sleeves.Right, Mathf.InverseLerp(RollRight.x, RollRight.y, n));
            }

            float k = Time.deltaTime / 0.5f;  // about 0.5 s in and out
            handW = Mathf.MoveTowards(handW, id == "hold_out_hands" ? 1f : 0f, k);
            forearmW = Mathf.MoveTowards(forearmW, Queue.Holding && id is "roll_up_sleeves" or "show_forearms" ? 1f : 0f, k);
            mouthW = Mathf.MoveTowards(mouthW, id is "open_mouth" or "stick_out_tongue" ? 1f : 0f, k * 1.5f);
            tongueW = Mathf.MoveTowards(tongueW, id == "stick_out_tongue" && mouthW > 0.6f ? 1f : 0f, k * 1.5f);
        }

        void MoveFollowTarget(float t)
        {
            // an H in front of her eyes, at about where the doctor's finger would be: across, then up and down
            var head = anim.GetBoneTransform(HumanBodyBones.Head).position;
            var toDoc = (doctor.position - head).normalized;
            var right = Vector3.Cross(Vector3.up, toDoc).normalized;
            float x = 0.25f * Mathf.Sin(2f * Mathf.PI * t / 3f), y = t > 3f ? 0.12f * Mathf.Sin(2f * Mathf.PI * (t - 3f) / 1.5f) : 0f;
            followTarget.position = head + toDoc * 0.45f + right * x + Vector3.up * y;
        }

        void OnAnimatorIK(int layer)
        {
            // both hands seated: on top of the hold_out_hands clip (ArmsOneShot); one hand, or standing (that layer is off): the base layer
            if (handW > 0.001f && (UseHandsClip ? layer == lArms : layer == 0)) HandsIK();
            if (layer == lArms) WipeTearsIK();
        }

        void HandsIK()
        {
            var chest = anim.GetBoneTransform(HumanBodyBones.UpperChest) ?? anim.GetBoneTransform(HumanBodyBones.Chest);
            Transform lS = anim.GetBoneTransform(HumanBodyBones.LeftUpperArm), rS = anim.GetBoneTransform(HumanBodyBones.RightUpperArm);
            var dir = PresentDir(chest.position);
            var right = Vector3.Cross(Vector3.up, dir);
            var centre = chest.position + dir * 0.42f;
            centre.y = (lS.position.y + rS.position.y) * 0.5f - 0.08f;
            foreach (bool left in new[] { true, false })
            {
                float w = handsWhich == "both" || handsWhich == (left ? "left" : "right") ? handW : 0f;
                var goal = left ? AvatarIKGoal.LeftHand : AvatarIKGoal.RightHand;
                float side = left ? -1f : 1f;
                anim.SetIKPositionWeight(goal, w);
                anim.SetIKPosition(goal, centre + right * (0.17f * side));
                var hint = left ? AvatarIKHint.LeftElbow : AvatarIKHint.RightElbow;
                anim.SetIKHintPositionWeight(hint, w * 0.6f);
                anim.SetIKHintPosition(hint, (left ? lS : rS).position + Vector3.down * 0.25f + right * (0.25f * side) - dir * 0.05f);
            }
        }

        /// <summary>Horizontal direction the hands point: 40% of the way from her own forward to the doctor. Aimed straight at the
        /// doctor's camera they foreshorten into a droop; this reads as "hands out, toward you".</summary>
        Vector3 PresentDir(Vector3 from)
        {
            var toDoc = doctor.position - from;
            toDoc.y = 0f;
            return Vector3.Slerp(transform.forward, toDoc.normalized, 0.4f).normalized;
        }

        void WipeTearsIK()
        {
            var st = anim.GetCurrentAnimatorStateInfo(lArms);
            if (!st.IsName("cue_wipe_tears")) return;
            float t = st.normalizedTime * 2.5f;  // seconds into the 2.5 s clip
            float w = Mathf.Clamp01((t - 0.6f) / 0.2f) * (1f - Mathf.Clamp01((t - 1.5f) / 0.2f));
            if (w <= 0f) return;
            Transform eye = anim.GetBoneTransform(HumanBodyBones.RightEye), hand = anim.GetBoneTransform(HumanBodyBones.RightHand),
                tip = anim.GetBoneTransform(HumanBodyBones.RightIndexDistal);
            if (!eye || !hand || !tip) return;
            // fingertip 1.5 cm under and 1 cm in front of the eye, sweeping inner -> outer corner; the hand offset is last frame's
            float sweep = Mathf.Lerp(-0.012f, 0.012f, Mathf.InverseLerp(0.8f, 1.5f, t));
            var wantTip = eye.position - Vector3.up * 0.015f + transform.forward * 0.01f + transform.right * sweep;
            anim.SetIKPositionWeight(AvatarIKGoal.RightHand, w);
            anim.SetIKPosition(AvatarIKGoal.RightHand, wantTip - (tip.position - hand.position));
        }

        void LateUpdate()
        {
            if (anim == null) return;
            if (handW > 0.001f)
                foreach (bool left in new[] { true, false })
                    if (handsWhich == "both" || handsWhich == (left ? "left" : "right"))
                    {
                        OrientHand(left, handW);
                        foreach (var (bone, straight, isLeft) in fingers)  // the lap clip's curl read as limp, dangling hands
                            if (isLeft == left) bone.localRotation = Quaternion.Slerp(bone.localRotation, straight, 0.75f * handW);
                    }
            if (forearmW > 0.001f) { Supinate(true, forearmW); Supinate(false, forearmW); }
            if (mouthW > 0.001f && jaw) jaw.rotation = Quaternion.AngleAxis(12f * mouthW, transform.right) * jaw.rotation;
            foreach (var (smr, i) in jawShapes) if (mouthW > 0.001f) smr.SetBlendShapeWeight(i, Mathf.Max(smr.GetBlendShapeWeight(i), 60f * mouthW));
            foreach (var (smr, i) in tongueShapes) smr.SetBlendShapeWeight(i, 100f * tongueW);
        }

        /// <summary>Rolls the hand about the forearm until the palm faces up, so the inner forearm shows (scars, needle marks);
        /// ForearmTwist carries the roll up the forearm.</summary>
        void Supinate(bool left, float w)
        {
            Transform hand = anim.GetBoneTransform(left ? HumanBodyBones.LeftHand : HumanBodyBones.RightHand),
                fore = anim.GetBoneTransform(left ? HumanBodyBones.LeftLowerArm : HumanBodyBones.RightLowerArm);
            var palm = handAxes[left ? 0 : 1].palm;
            if (!hand || !fore || palm == Vector3.zero) return;
            var axis = (hand.position - fore.position).normalized;
            float deg = Vector3.SignedAngle(Vector3.ProjectOnPlane(hand.rotation * palm, axis), Vector3.ProjectOnPlane(Vector3.up, axis), axis);
            hand.rotation = Quaternion.AngleAxis(deg * w, axis) * hand.rotation;
        }

        readonly List<(Transform bone, Quaternion straight, bool left)> fingers = new();

        /// <summary>Each finger joint's bind-pose (straight) local rotation, from the body mesh's bind poses.</summary>
        void CacheFingers()
        {
            SkinnedMeshRenderer skin = null;
            foreach (var r in GetComponentsInChildren<SkinnedMeshRenderer>()) if (r.sharedMesh && (!skin || r.sharedMesh.vertexCount > skin.sharedMesh.vertexCount)) skin = r;
            if (!skin) return;
            var bp = skin.sharedMesh.bindposes;
            for (var b = HumanBodyBones.LeftThumbProximal; b <= HumanBodyBones.RightLittleDistal; b++)
            {
                var t = anim.GetBoneTransform(b);
                int i = t ? System.Array.IndexOf(skin.bones, t) : -1, p = t ? System.Array.IndexOf(skin.bones, t.parent) : -1;
                if (i >= 0 && p >= 0) fingers.Add((t, Quaternion.Inverse(bp[p].inverse.rotation) * bp[i].inverse.rotation, b <= HumanBodyBones.LeftLittleDistal));
            }
        }

        /// <summary>Turns the hand so the fingers point at the doctor (5° up, wrist level as in a tremor check) and the palm faces up or down; the IK only places the
        /// wrist, and the lap pose's bent-up wrist otherwise shows a "stop" gesture.</summary>
        void OrientHand(bool left, float w)
        {
            var hand = anim.GetBoneTransform(left ? HumanBodyBones.LeftHand : HumanBodyBones.RightHand);
            var (fingers, palm) = handAxes[left ? 0 : 1];
            if (!hand || fingers == Vector3.zero) return;
            var dir = PresentDir(hand.position);
            dir = Quaternion.AngleAxis(-5f, Vector3.Cross(Vector3.up, dir)) * dir;
            var want = Quaternion.LookRotation(dir, palms == "up" ? Vector3.down : Vector3.up) * Quaternion.Inverse(Quaternion.LookRotation(fingers, -palm));
            hand.rotation = Quaternion.Slerp(hand.rotation, want, w);
        }

        /// <summary>The hand bone's local finger direction and palm normal (skeleton geometry, the same in any pose).</summary>
        (Vector3, Vector3) HandAxes(bool left)
        {
            Transform hand = anim.GetBoneTransform(left ? HumanBodyBones.LeftHand : HumanBodyBones.RightHand),
                mid = anim.GetBoneTransform(left ? HumanBodyBones.LeftMiddleProximal : HumanBodyBones.RightMiddleProximal),
                index = anim.GetBoneTransform(left ? HumanBodyBones.LeftIndexProximal : HumanBodyBones.RightIndexProximal),
                little = anim.GetBoneTransform(left ? HumanBodyBones.LeftLittleProximal : HumanBodyBones.RightLittleProximal);
            if (!hand || !mid || !index || !little) return (Vector3.zero, Vector3.zero);
            var fingers = (mid.position - hand.position).normalized;
            // out of the palm: palms-down hands held out (fingers forward, index toward the midline) give -up. The old sign pointed out of
            // the back of the hand, so "palms down" turned the palms up with a 180° wrist twist (2026-10-25 live test, checked on both bodies)
            var palm = Vector3.Cross(fingers, index.position - little.position).normalized * (left ? -1f : 1f);
            var inv = Quaternion.Inverse(hand.rotation);
            return (inv * fingers, inv * palm);
        }

        IEnumerator Walk()
        {
            Vector3 startPos = transform.position;
            Quaternion startRot = transform.rotation;
            yield return Turn(startRot * Quaternion.Euler(0f, WalkTurnDeg, 0f), 1.0f);
            for (int leg = 0; leg < 2; leg++)
            {
                anim.applyRootMotion = true;
                anim.CrossFade("walk_in", 0.25f, 0, 0.12f);  // skip the step-off from feet together
                yield return new WaitForSeconds(WalkSeconds);
                anim.CrossFade("stand_idle", 0.3f, 0);
                yield return new WaitForSeconds(0.3f);
                anim.applyRootMotion = false;
                if (leg == 0) yield return Turn(transform.rotation * Quaternion.Euler(0f, 180f, 0f), 1.2f);
            }
            // back on the spot she started from, facing the doctor (absorbs root-motion drift)
            Vector3 p0 = transform.position;
            Quaternion r0 = transform.rotation;
            for (float t = 0f; t < 1f; t += Time.deltaTime / 1.0f)
            {
                float s = Mathf.SmoothStep(0f, 1f, t);
                transform.SetPositionAndRotation(Vector3.Lerp(p0, startPos, s), Quaternion.Slerp(r0, startRot, s));
                yield return null;
            }
            transform.SetPositionAndRotation(startPos, startRot);
            walk = null;
        }

        IEnumerator Turn(Quaternion to, float seconds)
        {
            var from = transform.rotation;
            for (float t = 0f; t < 1f; t += Time.deltaTime / seconds)
            {
                transform.rotation = Quaternion.Slerp(from, to, Mathf.SmoothStep(0f, 1f, t));
                yield return null;
            }
            transform.rotation = to;
        }

        void OnDestroy() { if (followTarget) Destroy(followTarget.gameObject); }
    }
}
