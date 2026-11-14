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
        /// scene and writes &lt;modelId&gt;.png and .face.json for every patient body, from the same camera; exits 0 or 1.
        /// -tune "key=14,face=1.5,..." overrides EncounterLighting's real-time values; -apply angles the seats, updates the real-time
        /// lights and marks the patient prefabs (no re-bake needed); -save then saves the scene.</summary>
        public static void CaptureAllBodiesBatch()
        {
            var args = System.Environment.GetCommandLineArgs();
            string Arg(string name) { var k = System.Array.IndexOf(args, name); return k >= 0 && k + 1 < args.Length ? args[k + 1] : null; }
            var dir = Arg("-stillsDir") ?? Path.GetFullPath(Path.Combine(Application.dataPath, "../../../docs/media/stills"));
            try
            {
                var scene = UnityEditor.SceneManagement.EditorSceneManager.OpenScene("Assets/Scenes/Encounter.unity");
                if (Arg("-tune") is { } tune) Tune(tune);
                if (System.Array.IndexOf(args, "-apply") >= 0)
                {
                    EncounterSceneBuilder.AngleSeats(GameObject.Find("PatientAnchor").transform.parent);
                    EncounterLighting.ApplyRealtime(GameObject.Find("KeyLightTarget").transform.position);
                    foreach (var id in Bodies)
                    {
                        var path = $"Assets/Art/Patients/{id}/{id}.prefab";
                        var root = PrefabUtility.LoadPrefabContents(path);
                        EncounterLighting.MarkPatient(root);
                        PrefabUtility.SaveAsPrefabAsset(root, path);
                        PrefabUtility.UnloadPrefabContents(root);
                    }
                    if (System.Array.IndexOf(args, "-save") >= 0) UnityEditor.SceneManagement.EditorSceneManager.SaveScene(scene);
                    AssetDatabase.SaveAssets();
                }
                foreach (var id in Bodies)
                    Capture(id, Path.Combine(dir, id + ".png"));
                EditorApplication.Exit(0);
            }
            catch (System.Exception e)
            {
                Debug.LogException(e);
                EditorApplication.Exit(1);
            }
        }

        /// <summary>Batch: off-screen frame time of the doctor view at 1920x1080, 4x MSAA, each body seated (200 frames, a 1-pixel
        /// read-back per frame so GPU time counts). Editor numbers, an upper bound for the Development build; logs "FRAMETIME ...".</summary>
        public static void FrameTimeBatch()
        {
            try
            {
                UnityEditor.SceneManagement.EditorSceneManager.OpenScene("Assets/Scenes/Encounter.unity");
                var cam = GameObject.Find("DoctorCamera").GetComponent<Camera>();
                var anchor = GameObject.Find("PatientAnchor").transform;
                foreach (var id in Bodies)
                {
                    var go = (GameObject)Object.Instantiate(AssetDatabase.LoadAssetAtPath<GameObject>($"Assets/Art/Patients/{id}/{id}.prefab"), anchor.position, anchor.rotation);
                    AnimationMode.StartAnimationMode();
                    AnimationMode.BeginSampling(); AnimationMode.SampleAnimationClip(go, FirstClip(ClipPath), 0f); AnimationMode.EndSampling();
                    var head = go.GetComponent<Animator>().GetBoneTransform(HumanBodyBones.Head);
                    cam.transform.rotation = Rapport.Platform.DesktopRig.FollowRotation(cam.transform.position, head.position);
                    cam.fieldOfView = Rapport.Platform.CameraDirector.DoctorFov;
                    var rt = new RenderTexture(1920, 1080, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB) { antiAliasing = 4 };
                    var px = new Texture2D(1, 1, TextureFormat.RGB24, false);
                    cam.targetTexture = rt;
                    var ms = new System.Collections.Generic.List<double>();
                    for (int f = 0; f < 220; f++)
                    {
                        var sw = System.Diagnostics.Stopwatch.StartNew();
                        cam.Render();
                        RenderTexture.active = rt; px.ReadPixels(new Rect(0, 0, 1, 1), 0, 0); RenderTexture.active = null;
                        if (f >= 20) ms.Add(sw.Elapsed.TotalMilliseconds);
                    }
                    ms.Sort();
                    Debug.Log($"FRAMETIME {id} median {ms[ms.Count / 2]:F2} ms p95 {ms[(int)(ms.Count * 0.95)]:F2} ms");
                    cam.targetTexture = null; rt.Release();
                    AnimationMode.StopAnimationMode();
                    Object.DestroyImmediate(go);
                }
                EditorApplication.Exit(0);
            }
            catch (System.Exception e) { Debug.LogException(e); EditorApplication.Exit(1); }
        }

        static readonly string[] Bodies = { "female_20s_a", "male_20s_a", "female_20s_b", "male_30s_a" };

        static void Tune(string spec)
        {
            foreach (var kv in spec.Split(','))
            {
                var p = kv.Split('=');
                float v = float.Parse(p[1], System.Globalization.CultureInfo.InvariantCulture);
                switch (p[0])
                {
                    case "key": EncounterLighting.KeyIntensity = v; break;
                    case "keyAngle": EncounterLighting.KeyAngle = v; break;
                    case "rim": EncounterLighting.RimIntensity = v; break;
                    case "face": EncounterLighting.FaceIntensity = v; break;
                    case "faceAngle": EncounterLighting.FaceAngle = v; break;
                    case "exposure": EncounterLighting.PostExposure = v; break;
                    default: throw new System.ArgumentException($"-tune: unknown key {p[0]}");
                }
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

                // the live doctor view (DesktopRig follow + CameraDirector FOV), so stills and play mode frame the patient the same way
                var head = anim.GetBoneTransform(HumanBodyBones.Head);
                var (prevRot, prevFov) = (cam.transform.rotation, cam.fieldOfView);
                cam.transform.rotation = Rapport.Platform.DesktopRig.FollowRotation(cam.transform.position, head.position, Rapport.Platform.CameraDirector.DoctorFov, (float)w / h);
                cam.fieldOfView = Rapport.Platform.CameraDirector.DoctorFov;

                var rt = new RenderTexture(w, h, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB) { antiAliasing = 4 };
                var prev = cam.targetTexture;
                cam.targetTexture = rt;
                cam.Render();  // warm-up: the first render after opening the scene in batch mode can sample not-yet-uploaded textures (the rainbow tissue box)
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
                cam.transform.rotation = prevRot; cam.fieldOfView = prevFov;
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
