using System.IO;
using PsychSim.UI;
using UnityEditor;
using UnityEditor.Recorder;
using UnityEditor.Recorder.Encoder;
using UnityEditor.Recorder.Input;
using UnityEngine;

namespace PsychSim.Editor
{
    /// <summary>
    /// PsychSim/Record Demo: enters play mode, adds the DemoDirector and records the game view (1920x1080, 60 fps, audio)
    /// to demo/raw/PsychSim_take.mp4 until the take finishes. The patient service must run in demo mode (see demo/README.md).
    /// </summary>
    [InitializeOnLoad]
    public static class DemoRecorder
    {
        const string RecordFlag = "PsychSim.Demo.Record", PlayFlag = "PsychSim.Demo.Play";
        static RecorderController controller;

        static DemoRecorder() { EditorApplication.playModeStateChanged += OnPlayMode; }

        [MenuItem("PsychSim/Record Demo")]
        static void Record() { SessionState.SetString(VariantFlag, "female"); SessionState.SetBool(RecordFlag, true); Enter(); }

        [MenuItem("PsychSim/Record Demo (Arjun cut)")]
        static void RecordArjun() { SessionState.SetString(VariantFlag, "male"); SessionState.SetBool(RecordFlag, true); Enter(); }

        const string VariantFlag = "PsychSim.Demo.Variant", StagedFlag = "PsychSim.Demo.Staged";

        /// <summary>Staged concept preview: needs the service started with SANVAAD_STAGED=demo/staged/script.json.</summary>
        [MenuItem("PsychSim/Record Staged Demo")]
        static void RecordStaged() { SessionState.SetBool(StagedFlag, true); Record(); }

        [MenuItem("PsychSim/Record Staged Demo (Arjun cut)")]
        static void RecordStagedArjun() { SessionState.SetBool(StagedFlag, true); RecordArjun(); }

        [MenuItem("PsychSim/Play Demo (no recording)")]
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
            DemoDirector.ScriptPath = staged ? "demo/staged/script.json" : "demo/script.json";
            new GameObject("DemoDirector").AddComponent<DemoDirector>();
            if (record) StartRecording(staged ? "Sanvaad_staged" : "PsychSim_take");
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
            Debug.Log("PsychSim: recording demo to " + movie.OutputFile + ".mp4");
        }
    }
}
