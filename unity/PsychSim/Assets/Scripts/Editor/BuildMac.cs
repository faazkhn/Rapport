using System.Linq;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEngine;

namespace PsychSim.Editor
{
    /// <summary>Development macOS build to Builds/Rapport.app (draft content ships only in Development builds).
    /// Batch: Unity -batchmode -quit -projectPath unity/PsychSim -executeMethod PsychSim.Editor.BuildMac.Build</summary>
    public static class BuildMac
    {
        [MenuItem("Rapport/Build macOS (Development)")]
        public static void Build()
        {
            var scenes = EditorBuildSettings.scenes.Where(s => s.enabled).Select(s => s.path).ToArray();
            var r = BuildPipeline.BuildPlayer(scenes, "Builds/Rapport.app", BuildTarget.StandaloneOSX, BuildOptions.Development);
            Debug.Log($"BuildMac: {r.summary.result}, {r.summary.totalSize / 1e6:F0} MB, {r.summary.totalTime}");
            if (Application.isBatchMode && r.summary.result != BuildResult.Succeeded) EditorApplication.Exit(1);
        }
    }
}
