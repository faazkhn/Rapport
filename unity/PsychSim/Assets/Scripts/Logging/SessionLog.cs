using System;
using System.IO;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace Rapport.Logging
{
    /// <summary>Append-only JSON lines per session in &lt;persistentDataPath&gt;/sessions/. Turns, state, cues, tool actions, score, latency. Never audio.</summary>
    public class SessionLog
    {
        public readonly string Path;
        readonly Func<float> clock;

        public SessionLog(string persistentDir, string caseId, Func<float> sessionSeconds)
        {
            var dir = System.IO.Path.Combine(persistentDir, "sessions");
            Directory.CreateDirectory(dir);
            Path = System.IO.Path.Combine(dir, $"{DateTime.Now:yyyyMMdd_HHmmss}_{caseId}.jsonl");
            clock = sessionSeconds;
        }

        public void Write(string type, object data = null)
        {
            var line = new JObject { ["t"] = Math.Round(clock(), 2), ["type"] = type };
            if (data != null) line["data"] = JToken.FromObject(data);
            File.AppendAllText(Path, line.ToString(Formatting.None) + "\n");
        }
    }
}
