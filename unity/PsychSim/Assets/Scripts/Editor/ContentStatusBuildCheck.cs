using System.IO;
using System.Linq;
using Newtonsoft.Json.Linq;
using PsychSim.Data;
using UnityEditor;
using UnityEditor.Build;
using UnityEditor.Build.Reporting;
using UnityEngine;

namespace PsychSim.Editor
{
    /// <summary>
    /// Release builds may ship only 'approved' content (DESIGN 9.1). Development builds ship everything.
    /// Runs on every player build so it can't be forgotten; a release build with any non-approved file fails here.
    /// </summary>
    public class ContentStatusBuildCheck : IPreprocessBuildWithReport
    {
        public int callbackOrder => 0;

        public void OnPreprocessBuild(BuildReport report)
        {
            bool release = (report.summary.options & BuildOptions.Development) == 0;
            var dir = Path.Combine(Application.streamingAssetsPath, "data");
            CaseLoader.LoadAll(dir, releaseBuild: false);  // schema-check everything either way
            if (!release) return;
            var bad = Directory.GetFiles(dir, "*.json", SearchOption.AllDirectories)
                .Where(p => !p.Contains("schemas"))
                .Select(p => (p, status: (string)JObject.Parse(File.ReadAllText(p))["status"]))
                .Where(x => !ContentStatusFilter.Allowed(x.status, true))
                .Select(x => $"{Path.GetRelativePath(dir, x.p)} ({x.status})").ToList();
            if (bad.Count > 0)
                throw new BuildFailedException($"Release build blocked: only 'approved' content may ship. Not approved: {string.Join(", ", bad)}. Use a Development Build for draft content.");
        }
    }
}
