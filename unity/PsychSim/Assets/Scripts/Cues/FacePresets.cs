using System.Collections.Generic;
using System.Linq;
using Newtonsoft.Json.Linq;
using UnityEngine;

namespace Rapport.Cues
{
    /// <summary>
    /// Blends face_&lt;emotion&gt; blendshape presets (art/Animations/Face/*.json, weights 0-100 on CC_Base_Body).
    /// Scale &lt; 1 is flat affect (30% at full intensity). Eye_Blink_* also drives the eye occlusion and tear line so the lid shadow follows.
    /// Adds natural blinks (log-normal gaps around 3 s, some doubles, fast close and slower open). Emotions without a preset fall back to face_neutral.
    /// </summary>
    [DefaultExecutionOrder(900)]
    public class FacePresets : MonoBehaviour
    {
        public float Scale = 1f;
        public float EmotionGain = 1f;   // the brain's intensity (BodyLanguage): about 0.5 at 0/10, 1.2 at 10/10
        readonly Dictionary<string, Dictionary<string, float>> presets = new();
        readonly List<(SkinnedMeshRenderer smr, Dictionary<string, int> idx)> meshes = new();
        Dictionary<string, float> current = new(), target = new();
        float nextBlink, blinkStart = -1f;

        public void Setup(Transform patient, IEnumerable<TextAsset> presetFiles)
        {
            foreach (var f in presetFiles)
            {
                var w = JObject.Parse(f.text)["weights"].ToObject<Dictionary<string, float>>();
                presets[f.name] = w;
            }
            foreach (var name in new[] { "CC_Base_Body", "CC_Base_EyeOcclusion", "CC_Base_TearLine" })
            {
                var smr = patient.GetComponentsInChildren<SkinnedMeshRenderer>().FirstOrDefault(r => r.name == name);
                if (smr == null) continue;
                var idx = new Dictionary<string, int>();
                for (int i = 0; i < smr.sharedMesh.blendShapeCount; i++) idx[smr.sharedMesh.GetBlendShapeName(i)] = i;
                meshes.Add((smr, idx));
            }
            foreach (var kv in Builtin) presets.TryAdd(kv.Key, kv.Value);  // a JSON preset of the same name wins
            SetEmotion("neutral");
            current = new Dictionary<string, float>(target);
            nextBlink = clock + 2f;
        }

        float holdUntil;

        /// <summary>Shows one preset for a few seconds (e.g. face_squint during the penlight) over the current emotion.</summary>
        public void Hold(string preset, float seconds)
        {
            if (!presets.TryGetValue(preset, out var p)) return;
            held ??= target;
            target = new Dictionary<string, float>(p);
            foreach (var k in current.Keys.ToList()) if (!target.ContainsKey(k)) target[k] = 0f;
            holdUntil = clock + seconds;
        }

        Dictionary<string, float> held;

        public void SetEmotion(string emotion)
        {
            if (clock < holdUntil) { held = Merge(presets.TryGetValue("face_" + emotion, out var h) ? h : presets.GetValueOrDefault("face_neutral")) ?? held; return; }
            if (!presets.TryGetValue("face_" + emotion, out var p) && !presets.TryGetValue("face_neutral", out p)) return;
            target = Merge(p);
        }

        Dictionary<string, float> Merge(Dictionary<string, float> p)
        {
            if (p == null) return null;
            var t = new Dictionary<string, float>(p);
            foreach (var k in current.Keys.ToList()) if (!t.ContainsKey(k)) t[k] = 0f;
            return t;
        }

        /// <summary>Faces the brain names that have no JSON preset (CC Standard keys; ARKit-only bodies also carry these names).</summary>
        static readonly Dictionary<string, Dictionary<string, float>> Builtin = new()
        {
            ["face_angry"] = new() { ["Brow_Drop_L"] = 45, ["Brow_Drop_R"] = 45, ["Brow_Compress_L"] = 40, ["Brow_Compress_R"] = 40, ["Eye_Squint_L"] = 20,
                ["Eye_Squint_R"] = 20, ["Nose_Sneer_L"] = 18, ["Nose_Sneer_R"] = 15, ["Mouth_Press_L"] = 30, ["Mouth_Press_R"] = 30,
                ["Mouth_Tighten_L"] = 30, ["Mouth_Tighten_R"] = 30, ["Jaw_Forward"] = 12, ["Mouth_Chin_Up"] = 15 },   // brows down, jaw set
            ["face_happy"] = new() { ["Mouth_Smile_L"] = 45, ["Mouth_Smile_R"] = 42, ["Cheek_Raise_L"] = 30, ["Cheek_Raise_R"] = 28, ["Eye_Squint_L"] = 12,
                ["Eye_Squint_R"] = 12, ["Mouth_Dimple_L"] = 10, ["Mouth_Dimple_R"] = 10 },
            ["face_laugh"] = new() { ["Mouth_Smile_L"] = 80, ["Mouth_Smile_R"] = 78, ["Cheek_Raise_L"] = 60, ["Cheek_Raise_R"] = 58, ["Eye_Squint_L"] = 35,
                ["Eye_Squint_R"] = 35, ["Jaw_Open"] = 18, ["Mouth_Dimple_L"] = 20, ["Mouth_Dimple_R"] = 20 },
            ["face_suspicious"] = new() { ["Eye_Squint_L"] = 32, ["Eye_Squint_R"] = 26, ["Brow_Drop_L"] = 26, ["Brow_Drop_R"] = 10, ["Brow_Raise_Outer_R"] = 14,
                ["Mouth_Press_L"] = 22, ["Mouth_Press_R"] = 18, ["Mouth_L"] = 8 },
            ["face_confused"] = new() { ["Brow_Raise_Inner_L"] = 32, ["Brow_Raise_Outer_L"] = 26, ["Brow_Compress_R"] = 26, ["Brow_Drop_R"] = 16,
                ["Mouth_Press_L"] = 10, ["Mouth_R"] = 6 },
        };

        float clock;

        /// <summary>Lid closure 0-1, t seconds into a blink: closes in 70 ms, stays shut 30 ms, opens over 170 ms (eased).</summary>
        public static float BlinkShape(float t)
        {
            if (t < 0f || t >= 0.27f) return 0f;
            if (t < 0.07f) { float a = t / 0.07f; return a * a; }
            if (t < 0.10f) return 1f;
            float b = 1f - (t - 0.10f) / 0.17f;
            return b * b * (3f - 2f * b);
        }

        /// <summary>Seconds to the next blink from two uniforms: log-normal, median 3 s (about 17 a minute at rest), kept to 0.8-9 s.</summary>
        public static float BlinkGap(float u1, float u2)
        {
            float n = Mathf.Sqrt(-2f * Mathf.Log(Mathf.Max(u1, 1e-6f))) * Mathf.Cos(2f * Mathf.PI * u2);  // Box-Muller standard normal
            return Mathf.Clamp(3f * Mathf.Exp(0.5f * n), 0.8f, 9f);
        }

        void LateUpdate() => Step(Time.deltaTime);

        /// <summary>One frame of the face (LateUpdate, or an editor render loop that drives the clock itself).</summary>
        public void Step(float dt)
        {
            clock += dt;
            if (meshes.Count == 0) return;
            if (held != null && clock >= holdUntil) { target = held; held = null; }
            float k = 1f - Mathf.Exp(-dt * 4f);  // ~0.5 s ease between presets
            foreach (var key in target.Keys) current[key] = Mathf.Lerp(current.TryGetValue(key, out var c) ? c : 0f, target[key], k);

            if (clock > nextBlink)
            {
                blinkStart = clock;
                nextBlink = clock + (Random.value < 0.12f ? Random.Range(0.3f, 0.45f) : BlinkGap(Random.value, Random.value));  // ~1 in 8 is a double blink
            }
            float blink = blinkStart < 0 ? 0f : BlinkShape(clock - blinkStart) * 100f;

            foreach (var (smr, idx) in meshes)
                foreach (var kv in current)
                {
                    bool lid = kv.Key.StartsWith("Eye_Blink");
                    if (!idx.TryGetValue(kv.Key, out var i) || (smr.name != "CC_Base_Body" && !lid)) continue;
                    float w = Mathf.Min(100f, kv.Value * Scale * EmotionGain);
                    if (lid) w = Mathf.Max(w, blink);
                    smr.SetBlendShapeWeight(i, w);
                }
        }
    }
}
