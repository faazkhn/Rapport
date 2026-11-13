using System.IO;
using UnityEditor;
using UnityEngine;

namespace Rapport.Editor
{
    /// <summary>
    /// Rapport/Capture Lighting Stills: seats each patient at the PatientAnchor (base_sit_neutral, frame 0), renders the
    /// DoctorCamera at 1920x1080 and writes &lt;name&gt;.png plus &lt;name&gt;.face.json, the face box projected from the eye and head bones.
    /// tools/lighting/face_luminance.py measures the result.
    /// </summary>
    public static class LightingStills
    {
        const string ClipPath = "Assets/Art/Animations/Base/base_sit_neutral.fbx";

        [MenuItem("Rapport/Capture Lighting Stills")]
        static void CaptureAll()
        {
            var dir = Path.GetFullPath(Path.Combine(Application.dataPath, "../../../docs/media"));
            Capture("female_20s_a", Path.Combine(dir, "lighting_after_female.png"));
            Capture("male_20s_a", Path.Combine(dir, "lighting_after_male.png"));
        }

        /// <summary>Batch mode (-executeMethod Rapport.Editor.LightingStills.CaptureAllBodiesBatch -stillsDir DIR): opens the Encounter
        /// scene and writes &lt;modelId&gt;.png and .face.json for every patient body, from the same camera; exits 0 or 1.</summary>
        public static void CaptureAllBodiesBatch()
        {
            var args = System.Environment.GetCommandLineArgs();
            var i = System.Array.IndexOf(args, "-stillsDir");
            var dir = i >= 0 && i + 1 < args.Length ? args[i + 1] : Path.GetFullPath(Path.Combine(Application.dataPath, "../../../docs/media/stills"));
            try
            {
                UnityEditor.SceneManagement.EditorSceneManager.OpenScene("Assets/Scenes/Encounter.unity");
                foreach (var id in new[] { "female_20s_a", "male_20s_a", "female_20s_b", "male_30s_a" })
                    Capture(id, Path.Combine(dir, id + ".png"));
                EditorApplication.Exit(0);
            }
            catch (System.Exception e)
            {
                Debug.LogException(e);
                EditorApplication.Exit(1);
            }
        }

        public static string Capture(string modelId, string pngPath, int w = 1920, int h = 1080)
        {
            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>($"Assets/Art/Patients/{modelId}/{modelId}.prefab");
            var anchor = GameObject.Find("PatientAnchor").transform;
            var cam = GameObject.Find("DoctorCamera").GetComponent<Camera>();
            var clip = FirstClip(ClipPath);
            var go = (GameObject)Object.Instantiate(prefab, anchor.position, anchor.rotation);
            var anim = go.GetComponent<Animator>();
            AnimationMode.StartAnimationMode();
            try
            {
                AnimationMode.BeginSampling();
                AnimationMode.SampleAnimationClip(go, clip, 0f);
                AnimationMode.EndSampling();
                go.transform.SetPositionAndRotation(anchor.position, anchor.rotation);  // clips may carry root offset; the seat is the anchor

                var rt = new RenderTexture(w, h, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB) { antiAliasing = 4 };
                var prev = cam.targetTexture;
                cam.targetTexture = rt;
                cam.Render();
                cam.targetTexture = prev;
                RenderTexture.active = rt;
                var tex = new Texture2D(w, h, TextureFormat.RGB24, false);
                tex.ReadPixels(new Rect(0, 0, w, h), 0, 0);
                RenderTexture.active = null;
                Directory.CreateDirectory(Path.GetDirectoryName(pngPath));
                File.WriteAllBytes(pngPath, tex.EncodeToPNG());
                Object.DestroyImmediate(tex);
                rt.Release();

                // face box: skin between brow and chin, cheek to cheek, from the eye bones (head bone as fallback)
                var l = anim.GetBoneTransform(HumanBodyBones.LeftEye);
                var r = anim.GetBoneTransform(HumanBodyBones.RightEye);
                var head = anim.GetBoneTransform(HumanBodyBones.Head);
                var eyes = l && r ? (l.position + r.position) / 2 : head.position + head.up * 0.09f + go.transform.forward * 0.08f;
                var right = cam.transform.right; var up = head.up;
                float x0 = float.MaxValue, y0 = float.MaxValue, x1 = float.MinValue, y1 = float.MinValue;
                foreach (var p in new[] { eyes + right * 0.04f + up * 0.03f, eyes - right * 0.04f + up * 0.03f,
                                          eyes + right * 0.035f - up * 0.075f, eyes - right * 0.035f - up * 0.075f })
                {
                    var s = cam.WorldToViewportPoint(p);
                    x0 = Mathf.Min(x0, s.x * w); x1 = Mathf.Max(x1, s.x * w);
                    y0 = Mathf.Min(y0, (1 - s.y) * h); y1 = Mathf.Max(y1, (1 - s.y) * h);
                }
                var json = $"{{\"model\": \"{modelId}\", \"box\": [{x0:F0}, {y0:F0}, {x1:F0}, {y1:F0}]}}";
                File.WriteAllText(Path.ChangeExtension(pngPath, ".face.json"), json);
                return json;
            }
            finally
            {
                AnimationMode.StopAnimationMode();
                Object.DestroyImmediate(go);
            }
        }

        static AnimationClip FirstClip(string path)
        {
            foreach (var a in AssetDatabase.LoadAllAssetsAtPath(path))
                if (a is AnimationClip c && !c.name.StartsWith("__preview__")) return c;
            return null;
        }
    }
}
