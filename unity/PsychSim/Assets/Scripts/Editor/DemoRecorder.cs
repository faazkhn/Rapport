using System.IO;
using Rapport.UI;
using UnityEditor;
using UnityEditor.Recorder;
using UnityEditor.Recorder.Encoder;
using UnityEditor.Recorder.Input;
using UnityEngine;

namespace Rapport.Editor
{
    /// <summary>
    /// Rapport/Record Demo: enters play mode, adds the DemoDirector and records the game view (1920x1080, 60 fps, audio)
    /// to demo/raw/Rapport_take.mp4 until the take finishes. The patient service must run in demo mode (see demo/README.md).
    /// </summary>
    [InitializeOnLoad]
    public static class DemoRecorder
    {
        const string RecordFlag = "PsychSim.Demo.Record", PlayFlag = "PsychSim.Demo.Play";
        static RecorderController controller;

        static DemoRecorder() { EditorApplication.playModeStateChanged += OnPlayMode; }

        [MenuItem("Rapport/Record Demo")]
        static void Record() { SessionState.SetString(VariantFlag, "female"); SessionState.SetBool(RecordFlag, true); Enter(); }

        [MenuItem("Rapport/Record Demo (Arjun cut)")]
        static void RecordArjun() { SessionState.SetString(VariantFlag, "male"); SessionState.SetBool(RecordFlag, true); Enter(); }

        const string VariantFlag = "PsychSim.Demo.Variant", StagedFlag = "PsychSim.Demo.Staged", ScriptFlag = "PsychSim.Demo.Script", SeedFlag = "PsychSim.Demo.Seed";

        /// <summary>Staged concept preview: needs the service started with RAPPORT_STAGED=demo/staged/script.json.</summary>
        [MenuItem("Rapport/Record Staged Demo")]
        static void RecordStaged() { SessionState.SetBool(StagedFlag, true); Record(); }

        [MenuItem("Rapport/Record Staged Demo (Arjun cut)")]
        static void RecordStagedArjun() { SessionState.SetBool(StagedFlag, true); RecordArjun(); }

        /// <summary>Demo v3: a different interview (demo/v3/script.json), full session with Arjun.</summary>
        [MenuItem("Rapport/Record Demo v3 (Arjun, new script)")]
        static void RecordV3() { SessionState.SetString(ScriptFlag, "demo/v3/script.json"); RecordArjun(); }

        [MenuItem("Rapport/Play Demo v3 (no recording)")]
        static void PlayV3() { SessionState.SetString(ScriptFlag, "demo/v3/script.json"); SessionState.SetString(VariantFlag, "male"); SessionState.SetBool(PlayFlag, true); Enter(); }

        /// <summary>Demo v3 script with a seeded Arjun whose conversation style is upset (seed 2; see brain/styles.json).</summary>
        [MenuItem("Rapport/Record Demo v3 (Arjun, upset, seed 2)")]
        static void RecordV3Upset() { SessionState.SetInt(SeedFlag, 2); RecordV3(); }

        /// <summary>Ward station demo (demo/ward/script.json, case ward_01) with Ananya.</summary>
        [MenuItem("Rapport/Record Ward Demo (Ananya)")]
        static void RecordWard() { SessionState.SetString(ScriptFlag, "demo/ward/script.json"); SessionState.SetString(VariantFlag, "female"); SessionState.SetBool(RecordFlag, true); Enter(); }

        [MenuItem("Rapport/Play Demo (no recording)")]
        static void Play() { SessionState.SetString(VariantFlag, "female"); SessionState.SetBool(PlayFlag, true); Enter(); }

        static void Enter()
        {
            PlayerSettings.runInBackground = true;
            EditorApplication.EnterPlaymode();
        }

        static void OnPlayMode(PlayModeStateChange s)
        {
            if (s != PlayModeStateChange.EnteredPlayMode) return;
            bool record = SessionState.GetBool(RecordFlag, false), play = SessionState.GetBool(PlayFlag, false);
            if (!record && !play) return;
            SessionState.SetBool(RecordFlag, false);
            SessionState.SetBool(PlayFlag, false);
            Application.runInBackground = true;
            DemoDirector.Variant = SessionState.GetString(VariantFlag, "female");
            bool staged = SessionState.GetBool(StagedFlag, false);
            SessionState.SetBool(StagedFlag, false);
            int seed = SessionState.GetInt(SeedFlag, -1);
            SessionState.EraseInt(SeedFlag);
            DemoDirector.Seed = seed >= 0 ? seed : null;
            var script = SessionState.GetString(ScriptFlag, "");
            SessionState.EraseString(ScriptFlag);
            DemoDirector.ScriptPath = staged ? "demo/staged/script.json" : script != "" ? script : "demo/script.json";
            new GameObject("DemoDirector").AddComponent<DemoDirector>();
            if (record) StartRecording(staged ? "Rapport_staged" : script.Contains("ward") ? "Rapport_take_ward" : script != "" ? "Rapport_take_v3" + (seed >= 0 ? "_seed" + seed : "") : "Rapport_take");
            DemoDirector.Finished -= OnFinished;
            DemoDirector.Finished += OnFinished;
        }

        static void OnFinished()
        {
            if (controller != null && controller.IsRecording()) controller.StopRecording();
            controller = null;
            EditorApplication.ExitPlaymode();
        }

        static void StartRecording(string name)
        {
            var outDir = Path.GetFullPath(Path.Combine(Application.dataPath, "../../../demo/raw"));
            Directory.CreateDirectory(outDir);
            var movie = ScriptableObject.CreateInstance<MovieRecorderSettings>();
            movie.name = "PsychSimDemo";
            movie.Enabled = true;
            movie.EncoderSettings = new CoreEncoderSettings
            {
                Codec = CoreEncoderSettings.OutputCodec.MP4,
                EncodingQuality = CoreEncoderSettings.VideoEncodingQuality.High,
            };
            movie.ImageInputSettings = new GameViewInputSettings { OutputWidth = 1920, OutputHeight = 1080 };
            movie.AudioInputSettings.PreserveAudio = true;
            movie.OutputFile = Path.Combine(outDir, DemoDirector.Variant == "male" ? name + "_arjun" : name);
            var settings = ScriptableObject.CreateInstance<RecorderControllerSettings>();
            settings.AddRecorderSettings(movie);
            settings.SetRecordModeToManual();
            settings.FrameRatePlayback = FrameRatePlayback.Constant;
            settings.FrameRate = 60f;
            settings.CapFrameRate = true;
            controller = new RecorderController(settings);
            controller.PrepareRecording();
            controller.StartRecording();
            Debug.Log("Rapport: recording demo to " + movie.OutputFile + ".mp4");
        }
    }
}
