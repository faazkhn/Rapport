using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.RegularExpressions;
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
        public Dictionary<string, float> cueSeconds;   // seconds each cue was visibly on (intensity >= 0.35); null = unknown, all count as shown
        public HashSet<string> examsDone = new();      // exam actions the patient performed (hands out shows the tremor)
        public HashSet<string> revealed;               // facts the patient disclosed; null = unknown, risk answers count as disclosed
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
        public List<string> cues_false = new(), cues_not_shown = new();   // ticked but not part of this patient; expected but never visible this session
        public string global_rating;                                       // examiner-style overall judgement next to the checklist total
        public List<string> next_steps = new();                            // the 2-3 changes that would matter most next time

        public RxReport rx;
        public List<Feedback> feedback = new();
        public List<SideBySide> side_by_side = new();
    }

    /// <summary>Stage 1 version of DESIGN 8, revised from docs/literature/evaluation-and-assessment.md. Pure and deterministic.
    /// Risk-first weights (plan C1, R3's risk 5 : MSE 2 : history 1): risk 30, observation 20, history 12, communication 12,
    /// diagnosis 13, management 13. Missing a required risk item is a critical error. Observation is scored against what the
    /// patient visibly showed this session (recall 16, precision 4); risk credits disclosure, not only asking; communication uses
    /// MIRS / Calgary-Cambridge items; a global rating sits next to the total, as OSCE examiners give one.</summary>
    public static class ScoringEngine
    {
        public static readonly string[] CommunicationIntents = { "greet_introduce", "open_question", "empathy_statement", "summarise", "check_understanding", "explain_confidentiality" };
        public const float NegativeIntentPenalty = 4f;
        public const float ShownSeconds = 5f;          // a cue on screen this long counts as observable
        public const float AskedNotDisclosed = 0.6f;   // risk item asked but the patient did not answer it (asked too early, little trust)
        // words a patient should not have to decode (MIRS "minimises jargon"); matched as word starts, case-insensitive
        public static readonly string[] Jargon = { "ideation", "anhedoni", "psychomotor", "dysphori", "euthymi", "suicidality", "comorbid", "aetiolog", "etiolog",
            "prognos", "pharmacotherap", "titrat", "contraindicat", "benzodiazepine", "ssri", "ciwa", "delirium", "psychosis", "psychotic", "somati", "affective" };
        static readonly Regex Words = new(@"[A-Za-z]+", RegexOptions.Compiled);
        // a yes/no question by its form ("Do you...?", "Any plans?"); an open one by its opener ("What...", "How...", "Tell me...")
        static readonly Regex ClosedForm = new(@"(^|[.!?]\s+)(do|does|did|are|is|was|were|have|has|had|can|could|will|would|any|anything)\b[^.!?]*\?", RegexOptions.IgnoreCase | RegexOptions.Compiled);
        static readonly Regex OpenForm = new(@"(^|[.!?]\s+)(what|how|why|tell me|describe|could you tell|can you tell)\b", RegexOptions.IgnoreCase | RegexOptions.Compiled);

        public static ScoreResult Score(ScoreInput i)
        {
            var key = i.caseFile.answer_key;
            var intents = i.data.intents.intents;
            bool IsRisk(string id) => intents.Any(x => x.id == id && x.is_risk) || key.critical_intents.Contains(id);
            var r = new ScoreResult { case_id = i.caseFile.id, draft_content = i.caseFile.status != ContentStatusFilter.Approved };
            var risk = key.required_intents.Where(IsRisk).ToList();
            var hist = key.required_intents.Where(x => !IsRisk(x)).ToList();
            r.missed_intents = key.required_intents.Where(x => !i.ledger.Has(x)).ToList();

            // Risk (30): asked and answered 1, asked but not answered 0.6, not asked 0 and a critical error (NICE NG225: assess, do not stratify)
            float RiskItem(string id) => !i.ledger.Has(id) ? 0f : Disclosed(i, id) ? 1f : AskedNotDisclosed;
            var riskD = Domain("risk", "Risk assessment", 30, risk.Count == 0 ? 30 : 30f * risk.Sum(RiskItem) / risk.Count);
            riskD.notes.AddRange(risk.Where(x => !i.ledger.Has(x)).Select(x => $"Not asked: {Describe(intents, x)}"));
            riskD.notes.AddRange(risk.Where(x => i.ledger.Has(x) && !Disclosed(i, x)).Select(x => $"Asked, but the patient did not answer yet: {Describe(intents, x)}"));

            // Observation (20): against the cues the patient visibly showed (16 for finding them, 4 for not recording what was not there)
            var caseCues = i.caseFile.cues.Select(c => c.id).ToHashSet();
            var expectedAll = key.required_cues_noted.Concat(key.mse_expected.Values.SelectMany(m => m.cues)).Where(caseCues.Contains).Distinct().ToList();
            var expected = expectedAll.Where(c => Shown(i, c)).ToList();
            r.cues_not_shown = expectedAll.Except(expected).ToList();
            r.cues_present = expected;
            r.cues_recorded = i.mseCues.OrderBy(x => x).ToList();
            r.cues_missed = expected.Where(c => !i.mseCues.Contains(c)).ToList();
            r.cues_false = i.mseCues.Where(c => !caseCues.Contains(c)).OrderBy(x => x).ToList();
            float recall = expected.Count == 0 ? 1f : (float)expected.Count(i.mseCues.Contains) / expected.Count;
            float precision = i.mseCues.Count == 0 ? (expected.Count == 0 ? 1f : 0f) : 1f - (float)r.cues_false.Count / i.mseCues.Count;
            var obs = Domain("observation", "Observation (MSE)", 20, 16f * recall + 4f * precision);
            obs.notes.Add($"Seen and recorded {expected.Count(i.mseCues.Contains)}/{expected.Count}" + (r.cues_false.Count > 0 ? $"; recorded but not present: {r.cues_false.Count}" : ""));
            if (r.cues_not_shown.Count > 0) obs.notes.Add($"Not shown this session (not marked): {string.Join(", ", r.cues_not_shown.Select(c => CueName(i, c)))}");

            // History (12)
            var history = Domain("history", "History taking", 12, hist.Count == 0 ? 12 : 12f * hist.Count(i.ledger.Has) / hist.Count);

            // Communication (12): MIRS / Calgary-Cambridge items, then trust as the patient's verdict; judgmental lines, jargon and stacked questions cost
            int negatives = intents.Where(x => x.negative).Sum(x => i.ledger.Count(x.id));
            var jargonTurns = i.turns.Where(t => JargonIn(t.doctor) != null).ToList();
            var stacked = i.turns.Where(t => (t.doctor ?? "").Count(ch => ch == '?') >= 2).ToList();
            float items = CommItems(i).Average();
            var comm = Domain("communication", "Communication and rapport", 12,
                12 * (0.6f * items + 0.4f * i.finalTrust / 100f) - NegativeIntentPenalty * negatives - Math.Min(2, jargonTurns.Count) - Math.Min(1.5f, 0.5f * stacked.Count));
            comm.notes.Add($"Interview skills {items * 100:0}%; final trust {i.finalTrust:0}");
            if (negatives > 0) comm.notes.Add($"Judgmental language or interruptions: {negatives}");
            if (jargonTurns.Count > 0) comm.notes.Add($"Jargon in {jargonTurns.Count} line(s)");
            if (stacked.Count > 0) comm.notes.Add($"Several questions in one turn: {stacked.Count} time(s)");

            // Diagnosis (13): primary 9, differentials 5 x 0.8 (share of chosen differentials that are sensible)
            bool primaryOk = i.primaryDx != null && key.primary_dx.Contains(i.primaryDx);
            var sensible = key.acceptable_differentials.Concat(key.primary_dx).ToList();
            float diffs = i.differentials.Count == 0 ? 0 : 5f * i.differentials.Count(sensible.Contains) / i.differentials.Count;
            var dx = Domain("diagnosis", "Diagnosis", 13, (primaryOk ? 9 : 0) + diffs * 0.8f);
            dx.notes.Add(primaryOk ? "Primary diagnosis correct" : $"Primary diagnosis expected: {string.Join(", ", key.primary_dx)}");

            // Management (13): prescription 10, disposition 5, scaled
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
            r.critical_errors.AddRange(missingDispo.Select(x => $"Required disposition missing: {Dispo(i, x)}"));
            r.verdict = r.critical_errors.Count > 0 ? "Not passed" : "No critical errors";
            r.global_rating = Global(r.total, r.critical_errors.Count);
            r.teaching_points = key.teaching_points?.items ?? new List<string>();
            r.feedback = Quotes(i, intents, risk);
            r.feedback.AddRange(jargonTurns.Take(2).Select(t => new Feedback { kind = "improve", t = t.t, quote = t.doctor, note = $"'{JargonIn(t.doctor)}' is jargon to a patient; say it in everyday words." }));
            if (stacked.Count > 0) r.feedback.Add(new Feedback { kind = "improve", t = stacked[0].t, quote = stacked[0].doctor, note = "Several questions at once: the patient answers only one. Ask one, wait, then the next." });
            r.feedback = r.feedback.OrderBy(x => x.quote == null ? float.MaxValue : x.t).ToList();
            r.next_steps = NextSteps(i, r, intents, risk, missingDispo, jargonTurns.Count, stacked.Count);
            r.side_by_side = Compare(i, r, risk, primaryOk);
            return r;
        }

        /// <summary>Provisional cut-offs until faculty set them with a borderline-group or regression method on real cohorts.
        /// Critical errors cap the rating, as a missed safety item would for an examiner.</summary>
        public static string Global(float total, int critical) =>
            critical >= 2 ? "Clear fail" : critical == 1 ? "Borderline fail"
            : total >= 80 ? "Excellent" : total >= 65 ? "Clear pass" : total >= 50 ? "Borderline pass" : "Borderline fail";

        /// <summary>Opening, confidentiality, open questions, repeated empathy, summarising, checking understanding: each 0..1.</summary>
        static float[] CommItems(ScoreInput i)
        {
            int n = i.turns.Count;
            float Count(string id) => n > 0 ? i.turns.Count(t => t.intents.Contains(id)) : i.ledger.Count(id);
            float open = n >= 4 ? Math.Min(1f, Count("open_question") / (0.25f * n)) : (Count("open_question") > 0 ? 1f : 0f);
            return new[] { Count("greet_introduce") > 0 ? 1f : 0f, Count("explain_confidentiality") > 0 ? 1f : 0f, open,
                           Math.Min(1f, Count("empathy_statement") / 2f), Count("summarise") > 0 ? 1f : 0f, Count("check_understanding") > 0 ? 1f : 0f };
        }

        static bool Shown(ScoreInput i, string cue) =>
            i.cueSeconds == null || (i.cueSeconds.TryGetValue(cue, out var s) && s >= ShownSeconds)
            || (cue is "tremor_fine" or "tremor_coarse" && i.examsDone.Contains("hold_out_hands"));   // holding the hands out shows the tremor

        static IEnumerable<string> Unlocks(ScoreInput i, string intent) => i.caseFile.facts.Where(f => f.unlock_intents.Contains(intent)).Select(f => f.id);

        /// <summary>The patient answered this risk item: a must-ask fact it unlocks was disclosed (or none needs disclosing).</summary>
        static bool Disclosed(ScoreInput i, string intent)
        {
            if (i.revealed == null) return true;
            var facts = i.caseFile.facts.Where(f => f.must_be_asked && f.unlock_intents.Contains(intent)).Select(f => f.id).ToList();
            return facts.Count == 0 || facts.Any(i.revealed.Contains);
        }

        public static string JargonIn(string line)
        {
            if (string.IsNullOrEmpty(line)) return null;
            foreach (Match m in Words.Matches(line))
            {
                var w = m.Value.ToLowerInvariant();
                var j = Jargon.FirstOrDefault(w.StartsWith);
                if (j != null) return m.Value;
            }
            return null;
        }

        /// <summary>The two or three changes that would matter most next time, highest stakes first, each with words to try.</summary>
        static List<string> NextSteps(ScoreInput i, ScoreResult r, List<Intent> intents, List<string> risk, List<string> missingDispo, int jargon, int stacked)
        {
            string Try(string id) => intents.FirstOrDefault(x => x.id == id)?.example is { Length: > 0 } ex ? $" Try: \"{ex}\"" : "";
            var steps = new List<string>();
            steps.AddRange(risk.Where(x => !i.ledger.Has(x)).Select(x => $"Ask about this every time: {Describe(intents, x).ToLowerInvariant()}.{Try(x)}"));
            steps.AddRange(r.rx.critical.Select(c => $"Prescribing safety: {c}"));
            steps.AddRange(missingDispo.Select(x => $"Plan: include {Dispo(i, x).ToLowerInvariant()}."));
            steps.AddRange(r.rx.missing_required.Select(x => $"Plan: {x} is needed in this case."));
            steps.AddRange(risk.Where(x => i.ledger.Has(x) && !Disclosed(i, x)).Select(x =>
                $"You asked about {Describe(intents, x).ToLowerInvariant().Replace("asks about ", "")} before the patient trusted you enough to answer. Build rapport, then come back to it gently."));
            if (r.cues_missed.Count > 0)
                steps.Add($"Watch the patient: {string.Join(", ", r.cues_missed.Select(c => CueName(i, c).ToLowerInvariant()))} {(r.cues_missed.Count == 1 ? "was" : "were")} visible but not recorded.");
            if (r.cues_false.Count > 0)
                steps.Add($"Record only what you see: {string.Join(", ", r.cues_false.Select(c => CueName(i, c).ToLowerInvariant()))} {(r.cues_false.Count == 1 ? "was" : "were")} not part of this patient.");
            if (i.turns.Count > 0 && !i.turns.Any(t => t.intents.Contains("empathy_statement")))
                steps.Add($"Name what the patient feels at least twice.{Try("empathy_statement")}");
            if (stacked > 0) steps.Add("Ask one question at a time and wait for the answer.");
            if (jargon > 0) steps.Add("Use everyday words instead of clinical terms.");
            steps.AddRange(r.missed_intents.Where(x => !risk.Contains(x)).Take(2).Select(x => $"History: {Describe(intents, x).ToLowerInvariant()}.{Try(x)}"));
            return steps.Distinct().Take(3).ToList();
        }

        static string CueName(ScoreInput i, string id) => i.data.cues.cues.FirstOrDefault(c => c.id == id)?.name ?? id;
        static string Dispo(ScoreInput i, string id) => i.data.dispositions.dispositions.FirstOrDefault(d => d.id == id)?.name ?? id;

        static string Describe(List<Intent> intents, string id) => intents.FirstOrDefault(x => x.id == id)?.description.TrimEnd('.') ?? id;

        /// <summary>Plan C2: every item quotes the learner's line and its time.</summary>
        static List<Feedback> Quotes(ScoreInput i, List<Intent> intents, List<string> risk)
        {
            var f = new List<Feedback>();
            TurnRecord First(string intent) => i.turns.FirstOrDefault(t => t.intents.Contains(intent));
            foreach (var id in risk)
            {
                var t = First(id);
                bool told = i.revealed != null ? Disclosed(i, id) : t != null && Unlocks(i, id).Any(t.revealed.Contains);  // the fact this question unlocks, not any fact
                f.Add(t != null ? new Feedback { kind = "good", t = t.t, quote = t.doctor, note = $"Risk: {Describe(intents, id).ToLowerInvariant()}." + (told ? " The patient disclosed it." : " The patient did not answer it yet: come back to it once there is more trust.") }
                                : new Feedback { kind = "improve", note = $"Risk not covered: {Describe(intents, id).ToLowerInvariant()}. Ask directly and kindly." });
            }
            var empathy = First("empathy_statement");
            if (empathy != null) f.Add(new Feedback { kind = "good", t = empathy.t, quote = empathy.doctor, note = "Empathy statement; trust rose after it." });
            else f.Add(new Feedback { kind = "improve", note = "No empathy statement was recognised. Try naming what the patient feels." });
            foreach (var t in i.turns.Where(t => t.intents.Contains("judgmental_language") || t.intents.Contains("interrupt")))
                f.Add(new Feedback { kind = "improve", t = t.t, quote = t.doctor, note = "Judgmental or interrupting; trust fell. Try an open, non-blaming question." });
            foreach (var t in i.turns.Where(t => t.trustAfter - t.trustBefore <= -5 && !t.intents.Contains("judgmental_language")))
                f.Add(new Feedback { kind = "improve", t = t.t, quote = t.doctor, note = $"Trust dropped {t.trustBefore - t.trustAfter:0} points after this line." });
            var open = i.turns.Count(t => t.intents.Contains("open_question") || OpenForm.IsMatch(t.doctor ?? ""));
            if (i.turns.Count >= 4 && open * 4 < i.turns.Count)
            {
                var closed = i.turns.FirstOrDefault(t => ClosedForm.IsMatch(t.doctor ?? ""));
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
                        truth = (r.cues_present.Count == 0 ? "(no signs shown)" : string.Join(", ", r.cues_present.Select(Cue)))
                                + (r.cues_not_shown.Count > 0 ? $" [not shown this time: {string.Join(", ", r.cues_not_shown.Select(Cue))}]" : ""),
                        match = r.cues_missed.Count == 0 && r.cues_false.Count == 0 },
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
