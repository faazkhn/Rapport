using System.Collections.Generic;
using System.Linq;
using Newtonsoft.Json.Linq;
using UnityEngine;

namespace PsychSim.Cues
{
    /// <summary>
    /// Blends face_&lt;emotion&gt; blendshape presets (art/Animations/Face/*.json, weights 0-100 on CC_Base_Body).
    /// Scale &lt; 1 is flat affect (30% at full intensity). Eye_Blink_* also drives the eye occlusion and tear line so the lid shadow follows.
    /// Adds natural blinks. Emotions without a preset fall back to face_neutral.
    /// </summary>
    [DefaultExecutionOrder(900)]
    public class FacePresets : MonoBehaviour
    {
        public float Scale = 1f;
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
            SetEmotion("neutral");
            current = new Dictionary<string, float>(target);
            nextBlink = Time.time + 2f;
        }

        public void SetEmotion(string emotion)
        {
            if (!presets.TryGetValue("face_" + emotion, out var p) && !presets.TryGetValue("face_neutral", out p)) return;
            target = new Dictionary<string, float>(p);
            foreach (var k in current.Keys.ToList()) if (!target.ContainsKey(k)) target[k] = 0f;
        }

        void LateUpdate()
        {
            if (meshes.Count == 0) return;
            float k = 1f - Mathf.Exp(-Time.deltaTime * 4f);  // ~0.5 s ease between presets
            foreach (var key in target.Keys) current[key] = Mathf.Lerp(current.TryGetValue(key, out var c) ? c : 0f, target[key], k);

            if (Time.time > nextBlink) { blinkStart = Time.time; nextBlink = Time.time + Random.Range(2.5f, 6f); }
            float blink = blinkStart < 0 ? 0f : Mathf.Max(0f, 1f - Mathf.Abs(Time.time - blinkStart - 0.08f) / 0.08f) * 100f;

            foreach (var (smr, idx) in meshes)
                foreach (var kv in current)
                {
                    bool lid = kv.Key.StartsWith("Eye_Blink");
                    if (!idx.TryGetValue(kv.Key, out var i) || (smr.name != "CC_Base_Body" && !lid)) continue;
                    float w = kv.Value * Scale;
                    if (lid) w = Mathf.Max(w, blink);
                    smr.SetBlendShapeWeight(i, w);
                }
        }
    }
}
