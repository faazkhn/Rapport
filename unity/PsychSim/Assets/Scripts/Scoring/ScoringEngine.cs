using System;
using System.Collections.Generic;
using System.Linq;
using PsychSim.Data;

namespace PsychSim.Scoring
{
    /// <summary>Doctor intents tagged per turn, with session time in seconds.</summary>
    public class IntentLedger
    {
        public readonly List<(string intent, float t)> Entries = new();
        public void Add(IEnumerable<string> intents, float t) { foreach (var i in intents) Entries.Add((i, t)); }
        public bool Has(string intent) => Entries.Any(e => e.intent == intent);
        public int Count(string intent) => Entries.Count(e => e.intent == intent);
    }

    public class ScoreInput
    {
        public CaseFile caseFile;
        public ContentData data;
        public IntentLedger ledger = new();
        public HashSet<string> mseCues = new();
        public string primaryDx;
        public List<string> differentials = new();
        public List<RxItem> rx = new();
        public List<string> dispositions = new();
        public float finalTrust;
    }

    public class DomainScore { public string id, name; public float score, max; public List<string> notes = new(); }

    public class ScoreResult
    {
        public string case_id, verdict;
        public bool draft_content;
        public float total;
        public List<string> critical_errors = new();
        public List<DomainScore> domains = new();
        public List<string> missed_intents = new(), cues_present = new(), cues_recorded = new(), cues_missed = new(), teaching_points = new();
        public RxReport rx;
    }

    /// <summary>Stage 1 version of DESIGN 8. Pure and deterministic; weights are the DESIGN defaults.</summary>
    public static class ScoringEngine
    {
        public static readonly string[] CommunicationIntents = { "greet_introduce", "open_question", "empathy_statement", "summarise", "check_understanding", "explain_confidentiality" };
        public const float NegativeIntentPenalty = 4f;

        public static ScoreResult Score(ScoreInput i)
        {
            var key = i.caseFile.answer_key;
            var intents = i.data.intents.intents;
            bool IsRisk(string id) => intents.Any(x => x.id == id && x.is_risk);
            var r = new ScoreResult { case_id = i.caseFile.id, draft_content = i.caseFile.status != ContentStatusFilter.Approved };

            // Communication and rapport (20)
            float fc = CommunicationIntents.Count(i.ledger.Has) / (float)CommunicationIntents.Length;
            int negatives = intents.Where(x => x.negative).Sum(x => i.ledger.Count(x.id));
            var comm = Domain("communication", "Communication and rapport", 20, 20 * (0.6f * fc + 0.4f * i.finalTrust / 100f) - NegativeIntentPenalty * negatives);
            comm.notes.Add($"Rapport intents used: {CommunicationIntents.Count(i.ledger.Has)}/{CommunicationIntents.Length}; final trust {i.finalTrust:0}");
            if (negatives > 0) comm.notes.Add($"Judgmental language or interruptions: {negatives}");

            // History taking (20) and risk assessment (15) from required_intents
            var hist = key.required_intents.Where(x => !IsRisk(x)).ToList();
            var risk = key.required_intents.Where(IsRisk).ToList();
            r.missed_intents = key.required_intents.Where(x => !i.ledger.Has(x)).ToList();
            var history = Domain("history", "History taking", 20, hist.Count == 0 ? 20 : 20f * hist.Count(i.ledger.Has) / hist.Count);
            var riskD = Domain("risk", "Risk assessment", 15, risk.Count == 0 ? 15 : 15f * risk.Count(i.ledger.Has) / risk.Count);
            riskD.notes.AddRange(risk.Where(x => !i.ledger.Has(x)).Select(x => $"Not asked: {x}"));

            // Observation (15)
            r.cues_present = i.caseFile.cues.Select(c => c.id).ToList();
            r.cues_recorded = i.mseCues.OrderBy(x => x).ToList();
            r.cues_missed = key.required_cues_noted.Where(x => !i.mseCues.Contains(x)).ToList();
            var obs = Domain("observation", "Observation (MSE)", 15,
                key.required_cues_noted.Count == 0 ? 15 : 15f * key.required_cues_noted.Count(i.mseCues.Contains) / key.required_cues_noted.Count);
            obs.notes.AddRange(i.mseCues.Where(x => !r.cues_present.Contains(x)).Select(x => $"Recorded but not present: {x}"));

            // Diagnosis (15): primary 10, differentials 5 (share of chosen differentials that are sensible)
            bool primaryOk = i.primaryDx != null && key.primary_dx.Contains(i.primaryDx);
            var sensible = key.acceptable_differentials.Concat(key.primary_dx).ToList();
            float diffs = i.differentials.Count == 0 ? 0 : 5f * i.differentials.Count(sensible.Contains) / i.differentials.Count;
            var dx = Domain("diagnosis", "Diagnosis", 15, (primaryOk ? 10 : 0) + diffs);
            dx.notes.Add(primaryOk ? "Primary diagnosis correct" : $"Primary diagnosis expected: {string.Join(", ", key.primary_dx)}");

            // Management (15): prescription 10, disposition 5
            r.rx = PrescriptionChecker.Check(i.rx, i.caseFile, i.data.formulary);
            float rxScore = r.rx.critical.Count > 0 || i.rx.Count == 0 ? 0 : 10f * r.rx.lines.Count(l => l.appropriate) / r.rx.lines.Count;
            if (r.rx.missing_required.Count > 0) rxScore = Math.Max(0, rxScore - 5);
            var missingDispo = key.required_disposition.Where(x => !i.dispositions.Contains(x)).ToList();
            float dispo = (i.dispositions.Any(key.acceptable_disposition.Contains) ? 3 : 0) + (missingDispo.Count == 0 ? 2 : 0);
            var mgmt = Domain("management", "Management", 15, rxScore + dispo);
            if (i.rx.Count == 0) mgmt.notes.Add("No prescription written");
            mgmt.notes.AddRange(r.rx.missing_required.Select(x => $"Required drug missing: {x}"));
            mgmt.notes.AddRange(r.rx.minor);

            r.domains = new List<DomainScore> { comm, history, obs, riskD, dx, mgmt };
            r.total = (float)Math.Round(r.domains.Sum(d => d.score), 1);
            r.critical_errors.AddRange(r.rx.critical);
            r.critical_errors.AddRange(missingDispo.Select(x => $"Required disposition missing: {i.data.dispositions.dispositions.FirstOrDefault(d => d.id == x)?.name ?? x}"));
            r.verdict = r.critical_errors.Count > 0 ? "Not passed" : "No critical errors";
            r.teaching_points = key.teaching_points?.items ?? new List<string>();
            return r;
        }

        static DomainScore Domain(string id, string name, float max, float raw) =>
            new() { id = id, name = name, max = max, score = (float)Math.Round(Math.Clamp(raw, 0, max), 1) };
    }
}
