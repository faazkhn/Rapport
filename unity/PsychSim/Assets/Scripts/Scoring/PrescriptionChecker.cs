using System;
using System.Collections.Generic;
using System.Linq;
using Rapport.Data;

namespace Rapport.Scoring
{
    public class RxItem
    {
        public string drug, route, frequency, duration, reason;
        public float? dose_mg;
    }

    public class RuleHit { public string rule, severity, why; }

    public class RxLineResult
    {
        public string drug;
        public bool on_formulary;
        public string dose;          // "not_verified" (no range in the formulary yet) | "in_range" | "below_range" | "above_range" | "missing"
        public List<RuleHit> rule_hits = new();
        public bool appropriate;     // in the case's acceptable_rx
    }

    public class RxReport
    {
        public List<RxLineResult> lines = new();
        public List<string> missing_required = new();
        public List<string> critical = new();
        public List<string> minor = new();
    }

    /// <summary>DESIGN 6.3 checks in order: formulary, dose range, contraindication/interaction rules, appropriateness. Rules are data in formulary.json; each id maps to a named function here.</summary>
    public static class PrescriptionChecker
    {
        static readonly string[] Antidepressants = { "SSRI", "SNRI", "TCA", "NaSSA", "MAOI" };
        static readonly string[] Serotonergic = { "SSRI", "SNRI", "TCA", "NaSSA" };

        public delegate bool RuleFn(Drug drug, List<Drug> allRx, CaseFile c);

        public static readonly Dictionary<string, RuleFn> Rules = new()
        {
            ["with_maoi"] = (d, all, c) => Serotonergic.Contains(d.@class) && all.Any(o => o != d && o.@class == "MAOI"),
            ["bipolar_monotherapy_warning"] = (d, all, c) => Antidepressants.Contains(d.@class) && c.answer_key.primary_dx.Any(x => x.Contains("bipolar"))
                                                            && !all.Any(o => o.@class == "mood_stabiliser" || o.@class.Contains("antipsychotic")),
            ["serotonin_syndrome_with_tramadol"] = (d, all, c) => Serotonergic.Contains(d.@class) && (all.Any(o => o.id == "tramadol") || c.facts.Any(f => f.text.ToLowerInvariant().Contains("tramadol"))),
            ["tca_overdose_risk_with_suicidality"] = (d, all, c) => d.@class == "TCA" && c.facts.Any(f => f.unlock_intents.Contains("ask_suicidal_ideation")),
            ["benzo_with_opioids"] = (d, all, c) => d.@class == "benzodiazepine" && (all.Any(o => o.@class == "opioid") || c.answer_key.primary_dx.Any(x => x.Contains("opioid"))),
            ["benzo_monotherapy_for_depression"] = (d, all, c) => d.@class == "benzodiazepine" && c.answer_key.primary_dx.Any(x => x.StartsWith("mdd") || x.Contains("depress"))
                                                                 && !all.Any(o => Antidepressants.Contains(o.@class)),
            ["lithium_with_nsaid"] = (d, all, c) => d.id == "lithium" && all.Any(o => o.@class == "NSAID"),
            ["disulfiram_in_withdrawal"] = (d, all, c) => d.id == "disulfiram" && c.answer_key.primary_dx.Any(x => x.StartsWith("alcohol")),
            ["antipsychotic_lowers_seizure_threshold"] = (d, all, c) => d.@class.Contains("antipsychotic") && c.answer_key.primary_dx.Contains("alcohol_withdrawal"),
        };

        public static RxReport Check(List<RxItem> rx, CaseFile c, Formulary f)
        {
            var report = new RxReport();
            var drugs = rx.Select(r => f.drugs.FirstOrDefault(d => d.id == r.drug)).Where(d => d != null).ToList();
            foreach (var item in rx)
            {
                var drug = f.drugs.FirstOrDefault(d => d.id == item.drug);
                var line = new RxLineResult { drug = item.drug, on_formulary = drug != null };
                report.lines.Add(line);
                if (drug == null) { report.critical.Add($"{item.drug}: not on the formulary"); continue; }

                var range = drug.dose_range_mg;
                line.dose = item.dose_mg == null ? "missing" : range.min == null || range.max == null ? "not_verified"
                    : item.dose_mg < range.min ? "below_range" : item.dose_mg > range.max ? "above_range" : "in_range";
                if (line.dose == "below_range") report.minor.Add($"{drug.name}: dose below range");
                if (line.dose == "above_range") report.critical.Add($"{drug.name}: dose above range");

                foreach (var ruleId in drug.contraindication_rules.Concat(drug.interaction_rules).Distinct())
                {
                    if (!Rules.TryGetValue(ruleId, out var fn)) throw new InvalidOperationException($"formulary rule '{ruleId}' has no implementation in PrescriptionChecker");
                    if (fn(drug, drugs, c)) line.rule_hits.Add(Hit(f, ruleId, null));
                }
                foreach (var u in c.answer_key.unsafe_rx)
                    if ((u.drug == drug.id || u.drug_class == drug.@class) && !line.rule_hits.Any(h => h.rule == u.rule))
                        line.rule_hits.Add(Hit(f, u.rule, u.why));
                foreach (var h in line.rule_hits) (h.severity == "critical" ? report.critical : report.minor).Add($"{drug.name}: {h.why}");

                line.appropriate = c.answer_key.acceptable_rx.Any(a => a.drug == drug.id);
            }
            report.missing_required = c.answer_key.acceptable_rx.Where(a => a.required && !rx.Any(r => r.drug == a.drug)).Select(a => a.drug).ToList();
            return report;
        }

        static RuleHit Hit(Formulary f, string ruleId, string why)
        {
            var rule = f.rules.FirstOrDefault(r => r.id == ruleId);
            return new RuleHit { rule = ruleId, severity = rule?.severity ?? "critical", why = why ?? rule?.description ?? ruleId };
        }
    }
}
