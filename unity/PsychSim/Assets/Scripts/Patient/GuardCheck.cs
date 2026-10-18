using System.Collections.Generic;
using System.Linq;
using Newtonsoft.Json.Linq;
using PsychSim.Data;

namespace PsychSim.Patient
{
    public class EventCue { public string id; public float intensity, duration_s; }

    /// <summary>The DESIGN 7.2 reply contract (meta is whatever the service adds).</summary>
    public class PatientReply
    {
        public string utterance, emotion;
        public Dictionary<string, int> state_delta = new();
        public List<EventCue> event_cues = new();
        public List<string> revealed_fact_ids = new(), doctor_intents = new();
        public JObject meta;
    }

    /// <summary>The game has the final say over the LLM (DESIGN 7.2): unknown/locked facts, unknown cues and intents are dropped, deltas clamped.</summary>
    public static class GuardCheck
    {
        public const int DeltaClamp = 10;
        public static readonly string[] Emotions = { "neutral", "sad", "anxious", "angry", "ashamed", "happy", "flat", "suspicious", "confused" };

        /// <summary>Returns the cleaned reply and the list of what was dropped, or null if the reply is unusable (empty utterance).</summary>
        public static PatientReply Clean(PatientReply r, CaseFile c, IntentList intents, float trust, List<string> dropped)
        {
            if (r == null || string.IsNullOrWhiteSpace(r.utterance)) { dropped.Add("utterance: empty"); return null; }
            var known = new HashSet<string>(intents.intents.Select(i => i.id));
            var tagged = new List<string>();
            foreach (var i in r.doctor_intents ?? new List<string>())
                if (known.Contains(i)) { if (!tagged.Contains(i)) tagged.Add(i); }
                else dropped.Add($"intent {i}: unknown");

            var facts = new List<string>();
            foreach (var id in r.revealed_fact_ids ?? new List<string>())
            {
                var f = c.facts.FirstOrDefault(x => x.id == id);
                string reason = f == null ? "unknown" : f.trust_min > trust ? "locked" : f.must_be_asked && !f.unlock_intents.Intersect(tagged).Any() ? "not_asked" : null;
                if (reason != null) dropped.Add($"fact {id}: {reason}");
                else if (!facts.Contains(id)) facts.Add(id);
            }

            var cues = new List<EventCue>();
            foreach (var e in r.event_cues ?? new List<EventCue>())
                if (c.cues.Any(x => x.id == e.id)) cues.Add(new EventCue { id = e.id, intensity = Clamp(e.intensity, 0, 1), duration_s = Clamp(e.duration_s, 0, 10) });
                else dropped.Add($"cue {e.id}: unknown");

            var delta = new Dictionary<string, int>();
            foreach (var k in PatientState.Keys)
            {
                int v = r.state_delta != null && r.state_delta.TryGetValue(k, out var x) ? x : 0;
                delta[k] = v < -DeltaClamp ? -DeltaClamp : v > DeltaClamp ? DeltaClamp : v;
                if (delta[k] != v) dropped.Add($"state_delta {k}: clamped {v} -> {delta[k]}");
            }

            return new PatientReply
            {
                utterance = r.utterance.Trim(),
                emotion = Emotions.Contains(r.emotion) ? r.emotion : "neutral",
                state_delta = delta, event_cues = cues, revealed_fact_ids = facts, doctor_intents = tagged, meta = r.meta,
            };
        }

        static float Clamp(float x, float lo, float hi) => x < lo ? lo : x > hi ? hi : x;
    }

    /// <summary>Scripted lines from the case, used when the LLM fails twice. Rotates so the same line does not repeat back to back.</summary>
    public class FallbackLines
    {
        readonly List<string> lines;
        int next;
        public FallbackLines(List<string> lines) { this.lines = lines; }
        public string Next() => lines[next++ % lines.Count];
    }
}
