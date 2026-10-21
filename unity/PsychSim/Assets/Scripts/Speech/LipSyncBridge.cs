using System.Collections;
using System.Linq;
using UnityEngine;

namespace Rapport.Speech
{
    /// <summary>
    /// Puts the patient's voice AudioSource on the head with uLipSync, maps uLipSync phonemes (A I U E O N) to the CC3 visemes
    /// on CC_Base_Body, and opens the jaw bone with the voice (the visemes move the lips; teeth follow the jaw bone).
    /// </summary>
    [DefaultExecutionOrder(1100)]
    public class LipSyncBridge : MonoBehaviour
    {
        public AudioSource Source { get; private set; }
        public uLipSync.uLipSync LipSync { get; private set; }
        public float MaxJawDeg = 14f;

        static readonly (string phoneme, string viseme, float max)[] Map =
        {
            ("A", "V_Open", 1f), ("I", "V_Wide", 0.8f), ("U", "V_Tight_O", 1f), ("E", "V_Lip_Open", 0.9f), ("O", "V_Tight_O", 0.7f), ("N", "V_Explosive", 0.4f),
        };

        Transform jaw;
        float jawOpen, jawVel;
        uLipSync.uLipSyncBlendShape shapes;

        public void Setup(Animator anim, uLipSync.Profile profile)
        {
            var head = anim.GetBoneTransform(HumanBodyBones.Head);
            var go = new GameObject("Voice");
            go.transform.SetParent(head, false);
            go.transform.localPosition = new Vector3(0f, 0.08f, 0.08f);
            Source = go.AddComponent<AudioSource>();
            Source.playOnAwake = false;
            Source.spatialBlend = 0.8f;
            Source.minDistance = 1.5f;
            LipSync = go.AddComponent<uLipSync.uLipSync>();
            LipSync.profile = profile;

            var body = anim.GetComponentsInChildren<SkinnedMeshRenderer>().First(r => r.name == "CC_Base_Body");
            shapes = anim.gameObject.AddComponent<uLipSync.uLipSyncBlendShape>();
            shapes.skinnedMeshRenderer = body;
            shapes.usePhonemeBlend = true;
            shapes.smoothness = 0.06f;
            foreach (var (ph, vis, max) in Map)
            {
                var idx = body.sharedMesh.GetBlendShapeIndex(vis);
                if (idx >= 0) shapes.blendShapes.Add(new uLipSync.uLipSyncBlendShape.BlendShapeInfo { phoneme = ph, index = idx, maxWeight = max });
            }
            LipSync.onLipSyncUpdate.AddListener(shapes.OnLipSyncUpdate);

            jaw = anim.GetBoneTransform(HumanBodyBones.Jaw);
            if (jaw)
            {
                // open = rotate about the jaw's local axis closest to the character's right, so the chin goes down
                var right = anim.transform.right;
                var axes = new[] { Vector3.right, Vector3.up, Vector3.forward, Vector3.left, Vector3.down, Vector3.back };
                var best = axes.OrderByDescending(a => Vector3.Dot(jaw.TransformDirection(a), right)).First();
                jawAxis = best;
            }
        }

        Vector3 jawAxis;
        public float JawSign = 1f;  // flipped once at calibration if the jaw closed instead of opened

        void LateUpdate()
        {
            if (!jaw || LipSync == null) return;
            var info = LipSync.result;
            float vol = 0f;
            if (Source.isPlaying && info.rawVolume > 0f) vol = Mathf.Clamp01((Mathf.Log10(info.rawVolume) - shapes.minVolume) / (shapes.maxVolume - shapes.minVolume));
            float shape = 0.35f;
            if (info.phonemeRatios != null)
            {
                info.phonemeRatios.TryGetValue("A", out var a); info.phonemeRatios.TryGetValue("O", out var o); info.phonemeRatios.TryGetValue("E", out var e);
                info.phonemeRatios.TryGetValue("I", out var i); info.phonemeRatios.TryGetValue("U", out var u);
                shape = a + 0.7f * o + 0.6f * e + 0.35f * (i + u);
            }
            jawOpen = Mathf.SmoothDamp(jawOpen, Mathf.Clamp01(vol * Mathf.Max(shape, 0.3f)), ref jawVel, 0.05f);
            jaw.localRotation *= Quaternion.AngleAxis(JawSign * jawOpen * MaxJawDeg, jawAxis);
        }

        /// <summary>
        /// Calibrates the uLipSync profile from sustained vowels spoken by the case voice (call in play mode; the service must be running).
        /// Each clip plays on the patient source and every loud frame is added to that phoneme's MFCC average.
        /// </summary>
        public IEnumerator CalibrateFromTts(IVoice voice, string voiceId, float speed)
        {
            var prompts = new[] { ("A", "Aaaah. Ahh. Father."), ("I", "Eeeee. See. Me."), ("U", "Ooooo. Food. You."), ("E", "Ehhh. Bed. Red."), ("O", "Ohhhh. Go. Home."), ("N", "Mmmm. Nnnn. Hmm.") };
            for (int p = 0; p < prompts.Length; p++)
            {
                int index = LipSync.profile.mfccs.FindIndex(m => m.name == prompts[p].Item1);
                if (index < 0) continue;
                var task = voice.Speak(prompts[p].Item2, voiceId, speed);
                while (!task.IsCompleted) yield return null;
                if (task.IsFaulted) { Debug.LogWarning($"PsychSim: calibration TTS failed: {task.Exception?.GetBaseException().Message}"); yield break; }
                Source.clip = task.Result;
                Source.Play();
                while (Source.isPlaying)
                {
                    if (LipSync.result.rawVolume > 0.01f) LipSync.RequestCalibration(index);
                    yield return null;
                }
            }
#if UNITY_EDITOR
            LipSync.profile.Save();
#endif
        }
    }
}
