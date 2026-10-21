using System;
using System.Collections.Generic;
using Rapport.Data;

namespace Rapport.Patient
{
    /// <summary>Trust, distress, agitation, engagement (0..100). Mirrors server brain.apply_turn: LLM delta + state_rules nudges, clamped per turn, then to range.</summary>
    public class PatientState
    {
        public static readonly string[] Keys = { "trust", "distress", "agitation", "engagement" };
        readonly float[] v = new float[4];

        public PatientState(Dictionary<string, float> start)
        {
            for (int i = 0; i < 4; i++) v[i] = start.TryGetValue(Keys[i], out var x) ? x : 50f;
        }

        public float this[string key]
        {
            get => v[Index(key)];
            set => v[Index(key)] = value;
        }

        public float Trust => v[0];

        static int Index(string key)
        {
            int i = Array.IndexOf(Keys, key);
            if (i < 0) throw new ArgumentException($"unknown state key '{key}'");
            return i;
        }

        /// <summary>Per-minute drift from the case file, applied over 'minutes' of session time.</summary>
        public void Drift(Dictionary<string, float> perMinute, float minutes, ValueRange range)
        {
            foreach (var kv in perMinute) this[kv.Key] = Clamp(this[kv.Key] + kv.Value * minutes, range.min, range.max);
        }

        /// <summary>Applies one patient turn and returns the change actually applied per value.</summary>
        public Dictionary<string, float> ApplyTurn(IDictionary<string, int> llmDelta, IEnumerable<string> intents, StateRules rules)
        {
            var applied = new Dictionary<string, float>();
            for (int i = 0; i < 4; i++)
            {
                var k = Keys[i];
                float d = llmDelta != null && llmDelta.TryGetValue(k, out var ld) ? ld : 0;
                foreach (var intent in intents)
                    if (rules.intent_nudges.TryGetValue(intent, out var n) && n.TryGetValue(k, out var nv)) d += nv;
                d = Clamp(d, -rules.clamp_per_turn, rules.clamp_per_turn);
                var before = v[i];
                v[i] = Clamp(v[i] + d, rules.range.min, rules.range.max);
                applied[k] = v[i] - before;
            }
            return applied;
        }

        /// <summary>Takes the service's state after a voice turn (the service applies the same rules, brain.apply_turn).</summary>
        public void Set(IDictionary<string, float> s) { foreach (var kv in s) if (Array.IndexOf(Keys, kv.Key) >= 0) this[kv.Key] = kv.Value; }

        public Dictionary<string, float> Snapshot() => new() { ["trust"] = v[0], ["distress"] = v[1], ["agitation"] = v[2], ["engagement"] = v[3] };

        static float Clamp(float x, float lo, float hi) => x < lo ? lo : x > hi ? hi : x;
    }
}
