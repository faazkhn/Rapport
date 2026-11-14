using System.Globalization;
using System.IO;
using System.Linq;
using Rapport.Cues;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering.Universal;

namespace Rapport.Editor
{
    /// <summary>
    /// Batch check of "life between words" and body language, in play mode (Animator, gaze rig and skinning all run):
    /// Unity -batchmode -projectPath ... -executeMethod Rapport.Editor.LifeFrames.RenderBatch -body male_20s_a -framesDir DIR
    ///       [-seq "neutral:0:4,listen:0:4,think:0:4,angry:8:4,..."]   (no -quit: it exits itself when done)
    /// Opens the Encounter scene, enters play mode (the EncounterManager waits on its start screen), seats the body at the
    /// PatientAnchor with the live components (gaze, face, breathing, body language), then steps through the sequence
    /// (emotion:intensity 0-10:seconds; "listen" = the doctor is talking, "think" = between his line and the reply) at a fixed
    /// 30 fps game clock and writes every third frame (10 fps) from the doctor's view, framed once on the resting head.
    /// CueDriver is not running, so the slump blend and the fidget layer are driven here from BodyLanguage.For.
    /// -wav FILE with a "speak:0:SECONDS" step plays a 16-bit WAV through the live lip sync (LipSyncBridge); frames.txt then logs the
    /// uLipSync volume and the V_Open weight. -fov 9 gives a face close-up.
    /// </summary>
    [InitializeOnLoad]
    public static class LifeFrames
    {
        const string Key = "Rapport.LifeFrames";
        const int Fps = 30, Every = 3;
        static float Fov => float.TryParse(SessionState.GetString(Key + ".fov", ""), NumberStyles.Float, CultureInfo.InvariantCulture, out var f) ? f : Rapport.Platform.CameraDirector.DoctorFov;  // -fov 9: a face close-up

        static LifeFrames() { EditorApplication.playModeStateChanged += OnPlayMode; }

        public static void RenderBatch()
        {
            var args = System.Environment.GetCommandLineArgs();
            string Arg(string name, string def) { var k = System.Array.IndexOf(args, name); return k >= 0 && k + 1 < args.Length ? args[k + 1] : def; }
            SessionState.SetString(Key + ".fov", Arg("-fov", ""));
            var wav = Arg("-wav", "");
            SessionState.SetString(Key, string.Join("|", Arg("-body", "male_20s_a"), Path.GetFullPath(Arg("-framesDir", "Temp/LifeFrames")),
                Arg("-seq", "neutral:0:4,listen:0:4,think:0:3,angry:8:4,anxious:8:4,sad:8:4,ashamed:7:4,happy:8:4,confused:6:3,suspicious:7:3,flat:7:3"),
                wav != "" ? Path.GetFullPath(wav) : ""));
            UnityEditor.SceneManagement.EditorSceneManager.OpenScene("Assets/Scenes/Encounter.unity");
            EditorApplication.EnterPlaymode();
        }

        /// <summary>The whole live path through the DoctorCamera (Cinemachine, close-ups): -executeMethod Rapport.Editor.LifeFrames.EncounterBatch
        /// -body male_20s_a -framesDir DIR. Starts mdd_01 with that body (no patient service needed: the voice just fails to connect),
        /// records the entrance, then injects a brain_snapshot (angry 8), exam actions (hands, penlight, stand/walk/sit) and a sad
        /// snapshot, so body language and the exam actions can be checked together. 10 fps; frames.txt says what happened when.</summary>
        public static void EncounterBatch()
        {
            var args = System.Environment.GetCommandLineArgs();
            string Arg(string name, string def) { var k = System.Array.IndexOf(args, name); return k >= 0 && k + 1 < args.Length ? args[k + 1] : def; }
            SessionState.SetString(Key, string.Join("|", "encounter", Arg("-body", "male_20s_a"), Path.GetFullPath(Arg("-framesDir", "Temp/EncounterFrames"))));
            UnityEditor.SceneManagement.EditorSceneManager.OpenScene("Assets/Scenes/Encounter.unity");
            EditorApplication.EnterPlaymode();
        }

        static void OnPlayMode(PlayModeStateChange s)
        {
            if (s != PlayModeStateChange.EnteredPlayMode) return;
            var spec = SessionState.GetString(Key, "");
            if (spec == "") return;
            SessionState.EraseString(Key);
            var p = spec.Split('|');
            try { if (p[0] == "encounter") RunEncounter(p[1], p[2]); else Run(p[0], p[1], p[2], p[3]); }
            catch (System.Exception e) { Debug.LogException(e); EditorApplication.Exit(1); }
        }

        static void RunEncounter(string modelId, string dir)
        {
            Random.InitState(7);
            Directory.CreateDirectory(dir);
            Time.captureFramerate = Fps;
            var em = Object.FindFirstObjectByType<Rapport.Core.EncounterManager>();
            em.Configure("mdd_01", modelId.StartsWith("female") ? "female" : "male", Rapport.Core.Mode.Practice, modelId);
            em.BeginEncounter();
            var cam = GameObject.Find("DoctorCamera").GetComponent<Camera>();
            const int w = 960, h = 540;
            var rt = new RenderTexture(w, h, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB) { antiAliasing = 4 };
            var tex = new Texture2D(w, h, TextureFormat.RGB24, false);
            cam.targetTexture = rt;
            // seconds after the patient is seated (Phase.Active) -> what happens
            var script = new (float t, string what, string json)[]
            {
                (3f, "snapshot angry 8", @"{""type"":""brain_snapshot"",""emotion"":""angry"",""intensity"":8,""reaction"":""challenged"",""behaviour"":""hostile"",""state"":{""trust"":25}}"),
                (8f, "exam hold_out_hands", @"{""type"":""exam"",""actions"":[{""id"":""hold_out_hands"",""slots"":{""which"":""both"",""palms"":""down""},""comply"":true}]}"),
                (15f, "relax", @"{""type"":""exam"",""relax"":true,""actions"":[]}"),
                (18f, "exam look_at_light", @"{""type"":""exam"",""actions"":[{""id"":""look_at_light"",""comply"":true}]}"),
                (25f, "relax", @"{""type"":""exam"",""relax"":true,""actions"":[]}"),
                (25.1f, "snapshot sad 7", @"{""type"":""brain_snapshot"",""emotion"":""sad"",""intensity"":7,""reaction"":""sad"",""behaviour"":""guarded_short"",""state"":{""trust"":40}}"),
                (31f, "exam stand_up, walk_few_steps, sit_down", @"{""type"":""exam"",""actions"":[{""id"":""stand_up"",""comply"":true},{""id"":""walk_few_steps"",""comply"":true},{""id"":""sit_down"",""comply"":true}]}"),
                (52f, "end", null),
            };
            int next = 0, frame = 0, saved = 0;
            float activeAt = -1f;
            var log = new System.Text.StringBuilder();
            var body = (BodyLanguage)null;
            void Tick()
            {
                float now = frame / (float)Fps;
                if (activeAt < 0f && em.Phase == Rapport.Core.Phase.Active) { activeAt = now; log.AppendLine($"---- seated at {now:F1}s"); }
                if (activeAt < 0f && now > 60f) { log.AppendLine("never seated"); Finish(1); return; }
                if (activeAt >= 0f && next < script.Length && now - activeAt >= script[next].t)
                {
                    var (_, what, json) = script[next++];
                    log.AppendLine($"---- {now:F1}s {what}");
                    if (json == null) { Finish(0); return; }
                    var o = Newtonsoft.Json.Linq.JObject.Parse(json);
                    if ((string)o["type"] == "exam") em.Exam.Receive(o);
                    else { body ??= em.Patient.GetComponent<BodyLanguage>(); body.OnSnapshot(o); }
                }
                if (frame++ % Every != 0) return;
                cam.Render();
                RenderTexture.active = rt;
                tex.ReadPixels(new Rect(0, 0, w, h), 0, 0);
                RenderTexture.active = null;
                File.WriteAllBytes(Path.Combine(dir, $"{saved:D4}.png"), tex.EncodeToPNG());
                log.AppendLine($"{saved++:D4} {now:F1}s {em.Phase} exam={em.Exam?.Queue.Current?.id ?? "-"}");
            }
            void Finish(int code)
            {
                File.WriteAllText(Path.Combine(dir, "frames.txt"), log.ToString());
                cam.targetTexture = null;
                rt.Release();
                EditorApplication.Exit(code);
            }
            int lastFrame = -1;
            EditorApplication.update += () => { if (Time.frameCount != lastFrame) { lastFrame = Time.frameCount; Tick(); } };
        }

        static AudioClip Wav(string path)
        {
            var b = File.ReadAllBytes(path);
            int ch = System.BitConverter.ToInt16(b, 22), rate = System.BitConverter.ToInt32(b, 24), pos = 12;
            while (System.Text.Encoding.ASCII.GetString(b, pos, 4) != "data") pos += 8 + System.BitConverter.ToInt32(b, pos + 4);
            int n = System.BitConverter.ToInt32(b, pos + 4) / 2;
            var data = new float[n];
            for (int i = 0; i < n; i++) data[i] = System.BitConverter.ToInt16(b, pos + 8 + i * 2) / 32768f;
            var clip = AudioClip.Create(Path.GetFileName(path), n / ch, ch, rate, false);
            clip.SetData(data, 0);
            return clip;
        }

        static void Run(string modelId, string dir, string seq, string wav)
        {
            Random.InitState(7);
            Directory.CreateDirectory(dir);
            Time.captureFramerate = Fps;
            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>($"Assets/Art/Patients/{modelId}/{modelId}.prefab");
            var anchor = GameObject.Find("PatientAnchor").transform;
            var doctor = GameObject.Find("DoctorAnchor").transform;
            var docCam = GameObject.Find("DoctorCamera").GetComponent<Camera>();
            var go = Object.Instantiate(prefab, anchor.position, anchor.rotation);
            var anim = go.GetComponent<Animator>();
            var gaze = go.AddComponent<GazeController>(); gaze.Setup(anim, doctor, GameObject.Find("CornerLookTarget").transform);
            gaze.RigWeight = 1f;
            var face = go.AddComponent<FacePresets>();
            face.Setup(go.transform, Directory.GetFiles("Assets/Art/Animations/Face", "*.json").Select(AssetDatabase.LoadAssetAtPath<TextAsset>));
            var body = go.AddComponent<BodyLanguage>(); body.Setup(anim, null, gaze, face);
            // "speak:<emotion intensity>:<s>" plays -wav (16-bit PCM) through the live lip sync, as the patient's voice does
            Rapport.Speech.LipSyncBridge lips = null;
            if (wav != "")
            {
                lips = go.AddComponent<Rapport.Speech.LipSyncBridge>();
                lips.Setup(anim, AssetDatabase.LoadAssetAtPath<uLipSync.Profile>("Assets/Art/LipSync/uLipSync-Profile-female_20s_a.asset"));
                lips.Source.clip = Wav(wav);
            }
            int lFidget = anim.GetLayerIndex("Fidget");

            // its own camera at the doctor's eye (Cinemachine owns the DoctorCamera in play mode)
            var cam = new GameObject("LifeFramesCam").AddComponent<Camera>();
            cam.CopyFrom(docCam);
            cam.GetUniversalAdditionalCameraData().renderPostProcessing = true;
            cam.transform.position = docCam.transform.position;
            cam.fieldOfView = Fov;
            cam.enabled = false;
            docCam.enabled = false;
            const int w = 960, h = 540;
            var rt = new RenderTexture(w, h, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB) { antiAliasing = 4 };
            var tex = new Texture2D(w, h, TextureFormat.RGB24, false);
            cam.targetTexture = rt;

            var vOpen = go.GetComponentsInChildren<SkinnedMeshRenderer>().FirstOrDefault(r => r.name == "CC_Base_Body");
            var steps = seq.Split(',').Select(x => x.Split(':')).ToArray();
            int stepIdx = -1, stepFrames = 0, frame = 0, saved = 0, settle = 15;
            var log = new System.Text.StringBuilder();
            void Tick()
            {
                if (settle-- > 0) return;  // let the Animator and rig settle on the seat
                if (stepIdx < 0 && stepFrames <= 0)  // frame once on the seated head, as the doctor's view rests
                    cam.transform.rotation = Rapport.Platform.DesktopRig.FollowRotation(cam.transform.position, anim.GetBoneTransform(HumanBodyBones.Head).position,
                                                                                       Fov, 16f / 9f);
                if (stepFrames <= 0)
                {
                    if (++stepIdx >= steps.Length)
                    {
                        File.WriteAllText(Path.Combine(dir, "frames.txt"), log.ToString());
                        rt.Release();
                        EditorApplication.Exit(0);
                        return;
                    }
                    var st = steps[stepIdx];
                    body.Listening = st[0] == "listen";
                    if (st[0] == "speak" && lips) lips.Source.Play();
                    gaze.Thinking = st[0] == "think";
                    string emo = st[0] is "listen" or "think" or "speak" ? "neutral" : st[0];
                    body.Mood(emo, float.Parse(st[1], CultureInfo.InvariantCulture), "", emo == "angry" ? "hostile" : "", 50f);
                    stepFrames = Mathf.RoundToInt(float.Parse(st[2], CultureInfo.InvariantCulture) * Fps);
                }
                var t = BodyLanguage.For(body.Emotion, body.Intensity, body.Behaviour, body.Trust);
                anim.SetFloat("Slumped", t.slump, 0.5f, 1f / Fps);
                if (lFidget >= 0) anim.SetLayerWeight(lFidget, Mathf.MoveTowards(anim.GetLayerWeight(lFidget), t.fidget, 3f / Fps));
                stepFrames--;
                if (frame++ % Every != 0) return;
                cam.Render();
                RenderTexture.active = rt;
                tex.ReadPixels(new Rect(0, 0, w, h), 0, 0);
                RenderTexture.active = null;
                File.WriteAllBytes(Path.Combine(dir, $"{saved:D4}.png"), tex.EncodeToPNG());
                log.AppendLine($"{saved++:D4} {frame / (float)Fps:F1}s {steps[stepIdx][0]} {steps[stepIdx][1]}" + (lips ? $" vol={lips.LipSync.result.rawVolume:F4} V_Open={vOpen?.GetBlendShapeWeight(vOpen.sharedMesh.GetBlendShapeIndex("V_Open")):F0} playing={lips.Source.isPlaying}" : ""));
            }
            int lastFrame = -1;
            EditorApplication.update += () => { if (Time.frameCount != lastFrame) { lastFrame = Time.frameCount; Tick(); } };
        }
    }
}
