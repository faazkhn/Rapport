using System.IO;
using UnityEditor;
using UnityEngine;

namespace Rapport.Editor
{
    /// <summary>
    /// Rapport/Render Hero Flight: the showcase site's scroll-scrubbed camera move. Opens the Encounter scene, seats Ananya
    /// and flies a camera from the back corner of the room, over the doctor's shoulder, to a medium close-up of her
    /// face. Writes demo/showcase/flight/f_0001.jpg.. (3840x2160, 8x MSAA, JPEG 95) for tools in the rapport-site repo.
    /// </summary>
    public static class HeroFlight
    {
        const string Body = "female_20s_a", SitClip = "Assets/Art/Animations/Base/base_sit_neutral.fbx";
        const int W = 3840, H = 2160, Frames = 180;

        [MenuItem("Rapport/Render Hero Flight")]
        static void RenderMenu() => Render(Frames, "flight");

        /// <summary>The same move at twice the frames: 6 s at 60 fps for the launch film.</summary>
        [MenuItem("Rapport/Render Hero Flight (film, 360 frames)")]
        static void RenderFilm() => Render(2 * Frames, "flight_film");

        [MenuItem("Rapport/Render Hero Flight (5 preview frames)")]
        static void RenderPreview() => Render(5, "flight_preview");

        static void Render(int frames, string folder)
        {
            var dir = Path.GetFullPath(Path.Combine(Application.dataPath, "../../../demo/showcase/" + folder));
            Directory.CreateDirectory(dir);
            UnityEditor.SceneManagement.EditorSceneManager.OpenScene("Assets/Scenes/Encounter.unity");
            var anchor = GameObject.Find("PatientAnchor").transform;
            var cam = GameObject.Find("DoctorCamera").GetComponent<Camera>();

            var clip = FirstClip(SitClip);
            var go = (GameObject)Object.Instantiate(AssetDatabase.LoadAssetAtPath<GameObject>($"Assets/Art/Patients/{Body}/{Body}.prefab"), anchor.position, anchor.rotation);
            var head = go.GetComponent<Animator>().GetBoneTransform(HumanBodyBones.Head);
            AnimationMode.StartAnimationMode();
            var rt = new RenderTexture(W, H, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB) { antiAliasing = 8 };
            var tex = new Texture2D(W, H, TextureFormat.RGB24, false);
            var (pos0, rot0, fov0) = (cam.transform.position, cam.transform.rotation, cam.fieldOfView);
            cam.clearFlags = CameraClearFlags.SolidColor;  // no sky through the window gaps
            cam.backgroundColor = Color.black;
            try
            {
                Pose(go, anchor, clip, 3f);
                var face = head.position + head.up * 0.06f;
                var toDoc = cam.transform.position - face; toDoc.y = 0; toDoc.Normalize();
                // the Office pack room (no corridor): the back corner at seated eye height (from higher up her seated pose foreshortens into standing) -> over the doctor's shoulder -> a medium close-up
                var side = Vector3.Cross(Vector3.up, toDoc).normalized;
                Vector3[] path =
                {
                    new(-1.5f, 1.4f, 1.45f), new(-1.05f, 1.33f, 1.05f), cam.transform.position + Vector3.up * 0.08f + side * 0.15f,
                    face + toDoc * 1.05f + side * 0.06f - Vector3.up * 0.04f,
                };
                var room = anchor.position + Vector3.up * 1.0f + toDoc * 0.4f;  // first look target: the room, then her face
                float[] preview = { 0f, 0.15f, 0.3f, 0.6f, 1f };
                for (int i = 0; i < frames; i++)
                {
                    float u = frames == preview.Length ? preview[i] : (float)i / (frames - 1), e = Smoother(u);
                    Pose(go, anchor, clip, 3f + u * 1.0f);  // rendered frames show her standing before ~2 s into the clip
                    face = head.position + head.up * 0.06f;
                    var p = CatmullRom(path, e);
                    var look = Vector3.Lerp(room, face, Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(0f, 0.6f, e)));
                    cam.transform.SetPositionAndRotation(p, Quaternion.LookRotation(look - p, Vector3.up));
                    cam.fieldOfView = Mathf.Lerp(54f, 34f, Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(0.5f, 1f, e)));
                    cam.targetTexture = rt;
                    cam.Render();
                    if (i == 0) cam.Render();  // first render after opening the scene can sample not-yet-uploaded textures
                    cam.targetTexture = null;
                    RenderTexture.active = rt;
                    tex.ReadPixels(new Rect(0, 0, W, H), 0, 0);
                    RenderTexture.active = null;
                    File.WriteAllBytes(Path.Combine(dir, $"f_{i + 1:0000}.jpg"), tex.EncodeToJPG(95));
                    EditorUtility.DisplayProgressBar("Hero flight", $"frame {i + 1}/{frames}", (float)(i + 1) / frames);
                }
                Debug.Log($"Rapport: hero flight, {frames} frames to {dir}");
            }
            finally
            {
                EditorUtility.ClearProgressBar();
                cam.transform.SetPositionAndRotation(pos0, rot0); cam.fieldOfView = fov0;
                AnimationMode.StopAnimationMode();
                Object.DestroyImmediate(go);
                Object.DestroyImmediate(tex);
                rt.Release();
                UnityEditor.SceneManagement.EditorSceneManager.OpenScene("Assets/Scenes/Encounter.unity");  // drop the camera changes
            }
        }

        static void Pose(GameObject go, Transform anchor, AnimationClip clip, float t)
        {
            AnimationMode.BeginSampling();
            AnimationMode.SampleAnimationClip(go, clip, clip ? t % clip.length : 0f);
            AnimationMode.EndSampling();
            go.transform.SetPositionAndRotation(anchor.position, anchor.rotation);
        }

        /// <summary>Slow start, slow arrival (smootherstep).</summary>
        static float Smoother(float x) => x * x * x * (x * (x * 6f - 15f) + 10f);

        /// <summary>Centripetal-free uniform Catmull-Rom through the points, u in [0,1] over the whole path.</summary>
        static Vector3 CatmullRom(Vector3[] p, float u)
        {
            int n = p.Length - 1;
            float f = Mathf.Clamp01(u) * n;
            int i = Mathf.Min((int)f, n - 1);
            float t = f - i;
            Vector3 a = p[Mathf.Max(i - 1, 0)], b = p[i], c = p[i + 1], d = p[Mathf.Min(i + 2, n)];
            return 0.5f * (2f * b + (c - a) * t + (2f * a - 5f * b + 4f * c - d) * t * t + (3f * b - a - 3f * c + d) * t * t * t);
        }

        static AnimationClip FirstClip(string path)
        {
            foreach (var a in AssetDatabase.LoadAllAssetsAtPath(path))
                if (a is AnimationClip c && !c.name.StartsWith("__preview__")) return c;
            return null;
        }
    }
}
