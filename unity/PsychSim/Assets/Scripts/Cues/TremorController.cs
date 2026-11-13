using System.Collections.Generic;
using System.Linq;
using UnityEngine;

namespace Rapport.Cues
{
    /// <summary>
    /// Procedural bone noise applied after the Animator and the gaze rig (LateUpdate):
    /// fine tremor = Perlin noise around 10 Hz on wrists and fingers; coarse tremor (alcohol withdrawal) = about 5-6 Hz, larger, and
    /// the forearms shake too; restless = small seat shifts on hips and spine
    /// (no restless clip in Stage 1).
    /// </summary>
    [DefaultExecutionOrder(1000)]
    public class TremorController : MonoBehaviour
    {
        public float FineTremor;   // 0..1
        public float CoarseTremor; // 0..1
        public float MaxCoarseDeg = 5f;
        public float Restless;     // 0..1
        public float MaxTremorDeg = 2.0f;
        public float TremorHz = 10f;

        readonly List<(Transform bone, float seed, float scale)> tremorBones = new(), forearms = new();
        Transform hips, spine, chest;
        float shiftStart = -10f, shiftDir, nextShift;

        public void Setup(Animator anim)
        {
            void Add(HumanBodyBones b, float scale) { var t = anim.GetBoneTransform(b); if (t) tremorBones.Add((t, Random.value * 100f, scale)); }
            Add(HumanBodyBones.LeftHand, 1f); Add(HumanBodyBones.RightHand, 1f);
            for (var b = HumanBodyBones.LeftThumbProximal; b <= HumanBodyBones.RightLittleDistal; b++) Add(b, 0.6f);
            foreach (var b in new[] { HumanBodyBones.LeftLowerArm, HumanBodyBones.RightLowerArm }) if (anim.GetBoneTransform(b) is { } t) forearms.Add((t, Random.value * 100f, 0.35f));
            hips = anim.GetBoneTransform(HumanBodyBones.Hips);
            spine = anim.GetBoneTransform(HumanBodyBones.Spine);
            chest = anim.GetBoneTransform(HumanBodyBones.Chest);
            nextShift = Time.time + 8f;
        }

        void LateUpdate()
        {
            float t = Time.time;
            if (FineTremor > 0.01f)
                foreach (var (bone, seed, scale) in tremorBones)
                {
                    float a = FineTremor * MaxTremorDeg * scale;
                    float hz = TremorHz + (seed % 4f) - 2f;  // 8-12 Hz per bone
                    bone.localRotation *= Quaternion.Euler((Mathf.PerlinNoise(seed, t * hz) - 0.5f) * 2f * a, 0f, (Mathf.PerlinNoise(t * hz, seed) - 0.5f) * 2f * a);
                }
            if (CoarseTremor > 0.01f)
                foreach (var (bone, seed, scale) in tremorBones.Concat(forearms))
                {
                    float a = CoarseTremor * MaxCoarseDeg * scale, hz = 5.5f + (seed % 1f);
                    bone.localRotation *= Quaternion.Euler(Mathf.Sin(2f * Mathf.PI * hz * t + seed) * a, 0f, (Mathf.PerlinNoise(seed, t * hz) - 0.5f) * a);
                }

            if (hips == null) return;
            if (Restless > 0.05f && t > nextShift)
            {
                shiftStart = t;
                shiftDir = Random.value < 0.5f ? -1f : 1f;
                nextShift = t + Mathf.Lerp(25f, 5f, Restless) * Random.Range(0.7f, 1.3f);
            }
            float s = Mathf.Clamp01((t - shiftStart) / 1.6f);
            float bump = Mathf.Sin(s * Mathf.PI);                 // 1.6 s weight shift, out and back
            if (bump > 0f)
            {
                float deg = bump * Mathf.Lerp(2f, 6f, Restless) * shiftDir;
                hips.localRotation *= Quaternion.Euler(0f, deg * 0.5f, deg * 0.4f);
                if (spine) spine.localRotation *= Quaternion.Euler(0f, -deg * 0.3f, -deg * 0.5f);
                if (chest) chest.localRotation *= Quaternion.Euler(0f, 0f, -deg * 0.3f);
            }
        }
    }
}
