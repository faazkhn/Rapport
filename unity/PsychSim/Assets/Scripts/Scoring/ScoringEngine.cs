using System;
using System.Collections.Generic;
using System.Linq;
using Rapport.Data;

namespace Rapport.Scoring
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
        public List<TurnRecord> turns = new();   // for quote-grounded feedback (plan C2); may be empty
    }

    /// <summary>One doctor line and the patient's answer, with session time and what the turn did.</summary>
    public class TurnRecord
    {
        public float t, trustBefore, trustAfter;
        public string doctor, patient;
        public List<string> intents = new(), revealed = new();
    }

    /// <summary>A debrief item tied to the learner's own words ("At 04:12 you asked '...'").</summary>
    public class Feedback { public string kind, quote, note; public float t; }

    /// <summary>One row of the side-by-side debrief (plan C5): what the learner concluded next to the case truth.</summary>
    public class SideBySide { public string area, yours, truth; public bool match; }

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
        public List<Feedback> feedback = new();
        public List<SideBySide> side_by_side = new();
    }

    /// <summary>Stage 1 version of DESIGN 8. Pure and deterministic. Risk-first weights (plan C1, R3's risk 5 : MSE 2 : history 1):
    /// risk 30, observation 20, history 12, communication 12, diagnosis 13, management 13. Missing a required risk item is a critical error.</summary>
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
            var comm = Domain("communication", "Communication and rapport", 12, 12 * (0.6f * fc + 0.4f * i.finalTrust / 100f) - NegativeIntentPenalty * negatives);
            comm.notes.Add($"Rapport intents used: {CommunicationIntents.Count(i.ledger.Has)}/{CommunicationIntents.Length}; final trust {i.finalTrust:0}");
            if (negatives > 0) comm.notes.Add($"Judgmental language or interruptions: {negatives}");

            // History taking (20) and risk assessment (15) from required_intents
            var hist = key.required_intents.Where(x => !IsRisk(x)).ToList();
            var risk = key.required_intents.Where(IsRisk).ToList();
            r.missed_intents = key.required_intents.Where(x => !i.ledger.Has(x)).ToList();
            var history = Domain("history", "History taking", 12, hist.Count == 0 ? 12 : 12f * hist.Count(i.ledger.Has) / hist.Count);
            var riskD = Domain("risk", "Risk assessment", 30, risk.Count == 0 ? 30 : 30f * risk.Count(i.ledger.Has) / risk.Count);
            riskD.notes.AddRange(risk.Where(x => !i.ledger.Has(x)).Select(x => $"Not asked: {x}"));

            // Observation (15)
            r.cues_present = i.caseFile.cues.Select(c => c.id).ToList();
            r.cues_recorded = i.mseCues.OrderBy(x => x).ToList();
            r.cues_missed = key.required_cues_noted.Where(x => !i.mseCues.Contains(x)).ToList();
            var obs = Domain("observation", "Observation (MSE)", 20,
                key.required_cues_noted.Count == 0 ? 20 : 20f * key.required_cues_noted.Count(i.mseCues.Contains) / key.required_cues_noted.Count);
            obs.notes.AddRange(i.mseCues.Where(x => !r.cues_present.Contains(x)).Select(x => $"Recorded but not present: {x}"));

            // Diagnosis (15): primary 10, differentials 5 (share of chosen differentials that are sensible)
            bool primaryOk = i.primaryDx != null && key.primary_dx.Contains(i.primaryDx);
            var sensible = key.acceptable_differentials.Concat(key.primary_dx).ToList();
            float diffs = i.differentials.Count == 0 ? 0 : 5f * i.differentials.Count(sensible.Contains) / i.differentials.Count;
            var dx = Domain("diagnosis", "Diagnosis", 13, (primaryOk ? 9 : 0) + diffs * 0.8f);
            dx.notes.Add(primaryOk ? "Primary diagnosis correct" : $"Primary diagnosis expected: {string.Join(", ", key.primary_dx)}");

            // Management (15): prescription 10, disposition 5
            r.rx = PrescriptionChecker.Check(i.rx, i.caseFile, i.data.formulary);
            float rxScore = r.rx.critical.Count > 0 || i.rx.Count == 0 ? 0 : 10f * r.rx.lines.Count(l => l.appropriate) / r.rx.lines.Count;
            if (r.rx.missing_required.Count > 0) rxScore = Math.Max(0, rxScore - 5);
            var missingDispo = key.required_disposition.Where(x => !i.dispositions.Contains(x)).ToList();
            float dispo = (i.dispositions.Any(key.acceptable_disposition.Contains) ? 3 : 0) + (missingDispo.Count == 0 ? 2 : 0);
            var mgmt = Domain("management", "Management", 13, (rxScore + dispo) * 13f / 15f);
            if (i.rx.Count == 0) mgmt.notes.Add("No prescription written");
            mgmt.notes.AddRange(r.rx.missing_required.Select(x => $"Required drug missing: {x}"));
            mgmt.notes.AddRange(r.rx.minor);

            r.domains = new List<DomainScore> { riskD, obs, history, comm, dx, mgmt };
            r.total = (float)Math.Round(r.domains.Sum(d => d.score), 1);
            r.critical_errors.AddRange(risk.Where(x => !i.ledger.Has(x)).Select(x => $"Risk item not asked: {Describe(intents, x)}"));
            r.critical_errors.AddRange(r.rx.critical);
            r.critical_errors.AddRange(missingDispo.Select(x => $"Required disposition missing: {i.data.dispositions.dispositions.FirstOrDefault(d => d.id == x)?.name ?? x}"));
            r.verdict = r.critical_errors.Count > 0 ? "Not passed" : "No critical errors";
            r.teaching_points = key.teaching_points?.items ?? new List<string>();
            r.feedback = Quotes(i, intents, risk);
            r.side_by_side = Compare(i, r, risk, primaryOk);
            return r;
        }

        static string Describe(List<Intent> intents, string id) => intents.FirstOrDefault(x => x.id == id)?.description.TrimEnd('.') ?? id;

        /// <summary>Plan C2: every item quotes the learner's line and its time.</summary>
        static List<Feedback> Quotes(ScoreInput i, List<Intent> intents, List<string> risk)
        {
            var f = new List<Feedback>();
            TurnRecord First(string intent) => i.turns.FirstOrDefault(t => t.intents.Contains(intent));
            foreach (var id in risk)
            {
                var t = First(id);
                f.Add(t != null ? new Feedback { kind = "good", t = t.t, quote = t.doctor, note = $"Risk: {Describe(intents, id).ToLowerInvariant()}." + (t.revealed.Count > 0 ? " The patient disclosed it." : "") }
                                : new Feedback { kind = "improve", note = $"Risk not covered: {Describe(intents, id).ToLowerInvariant()}. Ask directly and kindly." });
            }
            var empathy = First("empathy_statement");
            if (empathy != null) f.Add(new Feedback { kind = "good", t = empathy.t, quote = empathy.doctor, note = "Empathy statement; trust rose after it." });
            else f.Add(new Feedback { kind = "improve", note = "No empathy statement was recognised. Try naming what the patient feels." });
            foreach (var t in i.turns.Where(t => t.intents.Contains("judgmental_language") || t.intents.Contains("interrupt")))
                f.Add(new Feedback { kind = "improve", t = t.t, quote = t.doctor, note = "Judgmental or interrupting; trust fell. Try an open, non-blaming question." });
            foreach (var t in i.turns.Where(t => t.trustAfter - t.trustBefore <= -5 && !t.intents.Contains("judgmental_language")))
                f.Add(new Feedback { kind = "improve", t = t.t, quote = t.doctor, note = $"Trust dropped {t.trustBefore - t.trustAfter:0} points after this line." });
            var open = i.turns.Count(t => t.intents.Contains("open_question"));
            if (i.turns.Count >= 4 && open * 4 < i.turns.Count)
            {
                var closed = i.turns.FirstOrDefault(t => !t.intents.Contains("open_question") && t.doctor.TrimEnd().EndsWith("?"));
                if (closed != null) f.Add(new Feedback { kind = "improve", t = closed.t, quote = closed.doctor, note = "Mostly closed questions. Open questions let a guarded patient say more." });
            }
            return f.OrderBy(x => x.quote == null ? float.MaxValue : x.t).ToList();
        }

        /// <summary>Plan C5: the learner's conclusions next to the case truth.</summary>
        static List<SideBySide> Compare(ScoreInput i, ScoreResult r, List<string> risk, bool primaryOk)
        {
            var key = i.caseFile.answer_key;
            string Dx(string id) => id == null ? "(none)" : i.data.diagnoses.diagnoses.FirstOrDefault(d => d.id == id)?.dsm5tr_name ?? id;
            string Cue(string id) => i.data.cues.cues.FirstOrDefault(c => c.id == id)?.name ?? id;
            string Dispo(string id) => i.data.dispositions.dispositions.FirstOrDefault(d => d.id == id)?.name ?? id;
            var siFacts = i.caseFile.facts.Where(f => f.unlock_intents.Contains("ask_suicidal_ideation") || f.unlock_intents.Contains("ask_suicide_plan")).ToList();
            var disclosed = i.turns.SelectMany(t => t.revealed).Distinct().ToList();
            return new List<SideBySide>
            {
                new() { area = "Risk", yours = risk.Count(i.ledger.Has) + "/" + risk.Count + " risk questions asked" + (siFacts.Any(f => disclosed.Contains(f.id)) ? "; suicidal thoughts disclosed" : ""),
                        truth = string.Join(" ", siFacts.Select(f => f.text)), match = risk.All(i.ledger.Has) },
                new() { area = "MSE", yours = r.cues_recorded.Count == 0 ? "(nothing recorded)" : string.Join(", ", r.cues_recorded.Select(Cue)),
                        truth = string.Join(", ", key.required_cues_noted.Select(Cue)), match = r.cues_missed.Count == 0 },
                new() { area = "Diagnosis", yours = Dx(i.primaryDx), truth = string.Join(" / ", key.primary_dx.Select(Dx)), match = primaryOk },
                new() { area = "Plan", yours = (i.rx.Count == 0 ? "no prescription" : string.Join(", ", i.rx.Select(x => x.drug))) + "; " +
                                                (i.dispositions.Count == 0 ? "no disposition" : string.Join(", ", i.dispositions.Select(Dispo))),
                        truth = string.Join(" or ", key.acceptable_rx.Select(x => x.drug)) + "; " + string.Join(", ", key.required_disposition.Concat(key.acceptable_disposition).Distinct().Select(Dispo)),
                        match = r.rx.critical.Count == 0 && i.rx.Count > 0 && !key.required_disposition.Except(i.dispositions).Any() },
            };
        }

        static DomainScore Domain(string id, string name, float max, float raw) =>
            new() { id = id, name = name, max = max, score = (float)Math.Round(Math.Clamp(raw, 0, max), 1) };
    }
}
