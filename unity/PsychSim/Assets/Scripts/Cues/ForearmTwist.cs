using System.Collections.Generic;
using System.Linq;
using UnityEngine;

namespace Rapport.Cues
{
    /// <summary>
    /// Spreads the hand's roll (pronation / supination) along the forearm's twist bones, as the radius does. Humanoid clips and the
    /// exam's palm turns rotate only the hand bone, and the CC twist bones (ForearmTwist01 at the elbow, 02 mid-forearm) are not
    /// humanoid bones, so nothing moved them: the wrist skin corkscrewed ("hands in a weird, non-human rotation").
    /// Runs after everything that turns the hand (exam 200, tremor 1000, lip sync 1100).
    /// </summary>
    [DefaultExecutionOrder(1200)]
    public class ForearmTwist : MonoBehaviour
    {
        class Arm
        {
            public Transform fore, hand;
            public Quaternion handBind;   // hand rotation relative to the forearm in the bind pose
            public Vector3 axis;          // forearm -> hand, forearm local
            public readonly List<(Transform bone, Quaternion rest, float share)> twists = new();
        }

        readonly List<Arm> arms = new();

        public void Setup(Animator anim)
        {
            var skin = GetComponentsInChildren<SkinnedMeshRenderer>().OrderByDescending(r => r.sharedMesh ? r.sharedMesh.vertexCount : 0).FirstOrDefault();
            if (!skin) return;
            foreach (var (lower, hb) in new[] { (HumanBodyBones.LeftLowerArm, HumanBodyBones.LeftHand), (HumanBodyBones.RightLowerArm, HumanBodyBones.RightHand) })
            {
                Transform fore = anim.GetBoneTransform(lower), hand = anim.GetBoneTransform(hb);
                int fi = System.Array.IndexOf(skin.bones, fore), hi = System.Array.IndexOf(skin.bones, hand);
                if (!fore || !hand || fi < 0 || hi < 0) continue;
                var bp = skin.sharedMesh.bindposes;
                var a = new Arm
                {
                    fore = fore, hand = hand,
                    handBind = Quaternion.Inverse(bp[fi].inverse.rotation) * bp[hi].inverse.rotation,
                    axis = fore.InverseTransformDirection(hand.position - fore.position).normalized,
                };
                float len = Vector3.Distance(fore.position, hand.position);
                // twist bones in parent-first order; the share grows toward the wrist (0.3 at the elbow, 0.65 mid-forearm)
                foreach (var t in fore.GetComponentsInChildren<Transform>())
                    if (t != fore && !t.IsChildOf(hand) && t.name.ToLowerInvariant().Contains("twist"))
                    {
                        float s = Mathf.Clamp01(Vector3.Dot(t.position - fore.position, hand.position - fore.position) / (len * len));
                        a.twists.Add((t, Quaternion.Inverse(fore.rotation) * t.rotation, 0.3f + 0.7f * s));
                    }
                if (a.twists.Count > 0) arms.Add(a);
            }
        }

        void LateUpdate()
        {
            foreach (var a in arms)
            {
                float deg = TwistDeg(Quaternion.Inverse(a.fore.rotation) * a.hand.rotation * Quaternion.Inverse(a.handBind), a.axis);
                var axisW = a.fore.TransformDirection(a.axis);
                foreach (var (bone, rest, share) in a.twists)
                    bone.rotation = Quaternion.AngleAxis(deg * share, axisW) * a.fore.rotation * rest;
            }
        }

        /// <summary>Signed angle (degrees, -180..180) of the twist part of `q` about the unit `axis` (swing-twist split).</summary>
        public static float TwistDeg(Quaternion q, Vector3 axis)
        {
            var p = Vector3.Dot(new Vector3(q.x, q.y, q.z), axis) * axis;
            var t = new Quaternion(p.x, p.y, p.z, q.w);
            float n = Mathf.Sqrt(t.x * t.x + t.y * t.y + t.z * t.z + t.w * t.w);
            if (n < 1e-6f) return 0f;
            float deg = 2f * Mathf.Atan2(Vector3.Dot(new Vector3(t.x, t.y, t.z), axis) / n, t.w / n) * Mathf.Rad2Deg;
            return Mathf.DeltaAngle(0f, deg);
        }
    }
}
