using System.Collections.Generic;
using System.IO;
using System.Linq;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using NUnit.Framework;
using PsychSim.Data;
using PsychSim.Patient;
using PsychSim.Scoring;
using PsychSim.Tools;
using UnityEngine;

namespace PsychSim.Tests
{
    public class CoreLogicTests
    {
        static string DataDir => Path.Combine(Application.streamingAssetsPath, "data");
        ContentData data;
        CaseFile mdd;

        [SetUp]
        public void Load()
        {
            data = CaseLoader.LoadAll(DataDir, releaseBuild: false);
            mdd = data.cases["mdd_01"];
        }

        // ---------- CaseLoader / ContentStatusFilter ----------

        [Test]
        public void AllShippedDataPassesSchemas() => Assert.That(data.cases.Keys, Does.Contain("mdd_01"));

        [Test]
        public void SchemaFailureNamesFileAndField()
        {
            var tmp = Path.Combine(Path.GetTempPath(), "psychsim_data_" + System.Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(Path.Combine(tmp, "cases"));
            Directory.CreateDirectory(Path.Combine(tmp, "schemas"));
            File.Copy(Path.Combine(DataDir, "schemas", "case.schema.json"), Path.Combine(tmp, "schemas", "case.schema.json"));
            var bad = JObject.Parse(File.ReadAllText(Path.Combine(DataDir, "cases", "mdd_01.json")));
            bad["patient"]["voice_id"] = "Siri";
            ((JObject)bad["answer_key"]).Remove("primary_dx");
            File.WriteAllText(Path.Combine(tmp, "cases", "bad.json"), bad.ToString());
            try
            {
                var e = Assert.Throws<ContentException>(() => CaseLoader.Load<CaseFile>(tmp, "cases/bad.json", "case.schema.json"));
                StringAssert.Contains("cases/bad.json", e.Message);
                StringAssert.Contains("$.patient.voice_id: value 'Siri' is not one of", e.Message);
                StringAssert.Contains("$.answer_key: missing required field 'primary_dx'", e.Message);
            }
            finally { Directory.Delete(tmp, true); }
        }

        [Test]
        public void ContentStatusFilterOnlyApprovedInRelease()
        {
            Assert.IsTrue(ContentStatusFilter.Allowed("draft", releaseBuild: false));
            Assert.IsTrue(ContentStatusFilter.Allowed("faculty_review", releaseBuild: false));
            Assert.IsFalse(ContentStatusFilter.Allowed("draft", releaseBuild: true));
            Assert.IsFalse(ContentStatusFilter.Allowed("faculty_review", releaseBuild: true));
            Assert.IsTrue(ContentStatusFilter.Allowed("approved", releaseBuild: true));
            // today every data file is a draft, so a release load must refuse it
            Assert.Throws<ContentException>(() => CaseLoader.LoadAll(DataDir, releaseBuild: true));
        }

        // ---------- GuardCheck ----------

        PatientReply Reply(params string[] facts) => new()
        {
            utterance = "I don't know.", emotion = "sad",
            state_delta = new Dictionary<string, int> { ["trust"] = 25, ["distress"] = -30, ["agitation"] = 3, ["engagement"] = 0 },
            event_cues = new List<EventCue> { new() { id = "tearful", intensity = 1.7f, duration_s = 4 }, new() { id = "sweating", intensity = 0.5f, duration_s = 2 } },
            revealed_fact_ids = facts.ToList(),
            doctor_intents = new List<string> { "ask_sleep", "made_up_intent" },
        };

        [Test]
        public void GuardDropsUnknownAndLockedFactsAndClamps()
        {
            var dropped = new List<string>();
            var r = GuardCheck.Clean(Reply("f_sleep", "f_invented", "f_passive_si", "f_guilt"), mdd, data.intents, trust: 30, dropped);
            CollectionAssert.AreEqual(new[] { "f_sleep" }, r.revealed_fact_ids);
            CollectionAssert.AreEquivalent(new[] { "fact f_invented: unknown", "fact f_passive_si: locked", "fact f_guilt: locked",
                "intent made_up_intent: unknown", "cue sweating: unknown", "state_delta trust: clamped 25 -> 10", "state_delta distress: clamped -30 -> -10" }, dropped);
            Assert.AreEqual(10, r.state_delta["trust"]);
            Assert.AreEqual(-10, r.state_delta["distress"]);
            Assert.AreEqual(1, r.event_cues.Count);
            Assert.AreEqual(1f, r.event_cues[0].intensity);
            CollectionAssert.AreEqual(new[] { "ask_sleep" }, r.doctor_intents);
        }

        [Test]
        public void GuardMustBeAskedFactNeedsItsIntent()
        {
            var dropped = new List<string>();
            var r = GuardCheck.Clean(Reply("f_passive_si"), mdd, data.intents, trust: 70, dropped);
            Assert.IsEmpty(r.revealed_fact_ids);
            Assert.Contains("fact f_passive_si: not_asked", dropped);
            var asked = Reply("f_passive_si");
            asked.doctor_intents.Add("ask_suicidal_ideation");
            CollectionAssert.AreEqual(new[] { "f_passive_si" }, GuardCheck.Clean(asked, mdd, data.intents, 70, new List<string>()).revealed_fact_ids);
        }

        [Test]
        public void GuardRejectsEmptyUtteranceAndFallbackRotates()
        {
            var r = Reply();
            r.utterance = "  ";
            Assert.IsNull(GuardCheck.Clean(r, mdd, data.intents, 30, new List<string>()));
            var fb = new FallbackLines(mdd.fallback_lines);
            Assert.AreNotEqual(fb.Next(), fb.Next());
        }

        [Test]
        public void BrainFallsBackAfterTwoFailures()
        {
            var brain = new PatientBrain(mdd, data, new PatientState(mdd.state_start), new FailingService());
            var turn = brain.Ask("Hello", 0).Result;
            Assert.IsTrue(turn.fallback);
            Assert.AreEqual(mdd.fallback_lines[0], turn.reply.utterance);
            Assert.AreEqual(2, turn.dropped.Count);
        }

        class FailingService : IPatientService
        {
            public System.Threading.Tasks.Task<string> Reply(string requestJson) => System.Threading.Tasks.Task.FromResult("{not json");
        }

        // ---------- PatientState ----------

        [Test]
        public void StateNudgesStackWithDeltaAndClamp()
        {
            var s = new PatientState(mdd.state_start); // trust 30, distress 55, agitation 15, engagement 35
            var applied = s.ApplyTurn(new Dictionary<string, int> { ["trust"] = 3, ["distress"] = 0, ["agitation"] = 0, ["engagement"] = 0 }, new[] { "empathy_statement" }, data.stateRules);
            Assert.AreEqual(37, s["trust"]);       // 3 + 4 nudge
            Assert.AreEqual(52, s["distress"]);    // -3 nudge
            Assert.AreEqual(37, s["engagement"]);  // +2 nudge
            Assert.AreEqual(7, applied["trust"]);
            s.ApplyTurn(new Dictionary<string, int> { ["trust"] = -8 }, new[] { "judgmental_language", "interrupt" }, data.stateRules);
            Assert.AreEqual(27, s["trust"]);       // -8 -8 -4 = -20, clamped to -10 per turn
            var low = new PatientState(new Dictionary<string, float> { ["trust"] = 2 });
            low.ApplyTurn(new Dictionary<string, int> { ["trust"] = -10 }, new string[0], data.stateRules);
            Assert.AreEqual(0, low["trust"]);      // range floor
        }

        [Test]
        public void StateDriftsPerMinuteAndClamps()
        {
            var s = new PatientState(mdd.state_start);
            s.Drift(mdd.state_drift_per_min, 4, data.stateRules.range);
            Assert.AreEqual(33, s["engagement"], 1e-4);   // 35 - 0.5 * 4
            s.Drift(new Dictionary<string, float> { ["agitation"] = 50 }, 10, data.stateRules.range);
            Assert.AreEqual(100, s["agitation"]);
        }

        // ---------- ScoringEngine ----------

        ScoreInput Perfect()
        {
            var i = new ScoreInput { caseFile = mdd, data = data, finalTrust = 80, primaryDx = "mdd_single_episode" };
            i.ledger.Add(mdd.answer_key.required_intents.Concat(ScoringEngine.CommunicationIntents), 60);
            foreach (var c in mdd.answer_key.required_cues_noted) i.mseCues.Add(c);
            i.differentials.Add("adjustment_disorder_depressed");
            i.rx.Add(new RxItem { drug = "sertraline", dose_mg = 50, route = "PO", frequency = "OD", duration = "4 weeks", reason = "depression" });
            i.dispositions.AddRange(new[] { "outpatient_referral", "safety_plan" });
            return i;
        }

        [Test]
        public void PerfectSession()
        {
            var r = ScoringEngine.Score(Perfect());
            Assert.AreEqual(99.0f, r.total, 1e-3);  // communication 12*(0.6+0.4*0.8)=11.04 -> 11.0, all others full (risk 30, MSE 20, history 12, dx 13, mgmt 13)
            Assert.AreEqual("risk", r.domains[0].id);  // risk-first
            Assert.AreEqual("No critical errors", r.verdict);
            Assert.IsEmpty(r.critical_errors);
            Assert.IsEmpty(r.missed_intents);
            Assert.AreEqual("not_verified", r.rx.lines[0].dose);  // draft formulary has no dose ranges
            Assert.IsTrue(r.draft_content);
        }

        [Test]
        public void MissedRiskQuestions()
        {
            var i = Perfect();
            i.ledger.Entries.RemoveAll(e => e.intent.StartsWith("ask_suicid"));
            var r = ScoringEngine.Score(i);
            Assert.AreEqual(0, r.domains.Single(d => d.id == "risk").score);
            Assert.AreEqual(69.0f, r.total, 1e-3);
            CollectionAssert.AreEquivalent(new[] { "ask_suicidal_ideation", "ask_suicide_plan", "ask_suicide_means" }, r.missed_intents);
            Assert.AreEqual("Not passed", r.verdict);  // plan C1: no pass without the risk items
            Assert.AreEqual(3, r.critical_errors.Count(e => e.StartsWith("Risk item not asked")));
            Assert.IsFalse(r.side_by_side.Single(x => x.area == "Risk").match);
        }

        [Test]
        public void FeedbackQuotesTheLearnersLines()
        {
            var i = Perfect();
            i.turns.Add(new TurnRecord { t = 252, doctor = "Have you had thoughts that life isn't worth living?", intents = { "ask_suicidal_ideation" }, revealed = { "f_passive_si" }, trustBefore = 60, trustAfter = 63 });
            i.turns.Add(new TurnRecord { t = 30, doctor = "Just answer yes or no.", intents = { "judgmental_language" }, trustBefore = 30, trustAfter = 22 });
            var r = ScoringEngine.Score(i);
            var si = r.feedback.Single(f => f.quote != null && f.quote.StartsWith("Have you had"));
            Assert.AreEqual(252, si.t); StringAssert.Contains("disclosed", si.note);
            Assert.AreEqual("Just answer yes or no.", r.feedback[0].quote);  // ordered by time
            Assert.AreEqual(4, r.side_by_side.Count);
            Assert.IsTrue(r.side_by_side.Single(x => x.area == "Diagnosis").match);
        }

        [Test]
        public void VariantsFillTemplatesAndFollowSex()
        {
            var f = CaseVariants.Resolve(mdd, "female");
            var m = CaseVariants.Resolve(mdd, "male");
            Assert.AreEqual("Ananya Rao", f.patient.name); Assert.AreEqual("male_20s_a", m.patient.model_id); Assert.AreEqual("Leo", m.patient.voice_id);
            Assert.IsTrue(f.facts.Any(x => x.id == "f_pregnancy")); Assert.IsFalse(m.facts.Any(x => x.id == "f_pregnancy"));
            Assert.IsFalse(m.referral_note.Contains("{")); Assert.IsFalse(f.patient.background.Contains("{their}"));
            Assert.AreEqual(f.facts.Count - 1, m.facts.Count);  // identical clinical facts except the variant-only one
            Assert.Throws<ContentException>(() => CaseVariants.Resolve(mdd, "other"));
        }

        [Test]
        public void CriticalErrorIsNotPassedWhateverTheScore()
        {
            var i = Perfect();
            i.rx.Add(new RxItem { drug = "amitriptyline", dose_mg = 25, route = "PO" });
            var r = ScoringEngine.Score(i);
            Assert.AreEqual("Not passed", r.verdict);
            Assert.IsTrue(r.critical_errors.Any(e => e.StartsWith("Amitriptyline")));
            Assert.AreEqual(0, r.rx.lines.Count(l => l.drug == "sertraline" && l.rule_hits.Count > 0));

            var noPlan = Perfect();
            noPlan.dispositions.Remove("safety_plan");
            var r2 = ScoringEngine.Score(noPlan);
            Assert.AreEqual("Not passed", r2.verdict);
            CollectionAssert.Contains(r2.critical_errors, "Required disposition missing: Safety plan");
        }

        // ---------- PrescriptionChecker ----------

        CaseFile CaseWith(string primaryDx, bool suicidal)
        {
            var c = JsonConvert.DeserializeObject<CaseFile>(JsonConvert.SerializeObject(mdd));
            c.answer_key.primary_dx = new List<string> { primaryDx };
            c.answer_key.unsafe_rx.Clear();
            if (!suicidal) c.facts.RemoveAll(f => f.unlock_intents.Contains("ask_suicidal_ideation"));
            return c;
        }

        Formulary FormularyWith(params Drug[] extra)
        {
            var f = JsonConvert.DeserializeObject<Formulary>(JsonConvert.SerializeObject(data.formulary));
            f.drugs.AddRange(extra);
            return f;
        }

        static RxItem Rx(string drug, float? dose = 10) => new() { drug = drug, dose_mg = dose, route = "PO" };

        // rule id, case dx, suicidal, prescription, extra drugs (for interactions with drugs outside the slice formulary), expect hit
        static IEnumerable<TestCaseData> RuleCases()
        {
            var maoi = new Drug { id = "phenelzine", name = "Phenelzine", @class = "MAOI", routes = new List<string> { "PO" } };
            var tramadol = new Drug { id = "tramadol", name = "Tramadol", @class = "opioid", routes = new List<string> { "PO" } };
            var nsaid = new Drug { id = "ibuprofen", name = "Ibuprofen", @class = "NSAID", routes = new List<string> { "PO" } };
            yield return new TestCaseData("with_maoi", "mdd_single_episode", false, new[] { "sertraline", "phenelzine" }, new[] { maoi }, true).SetName("with_maoi hit");
            yield return new TestCaseData("with_maoi", "mdd_single_episode", false, new[] { "sertraline" }, new Drug[0], false).SetName("with_maoi miss");
            yield return new TestCaseData("bipolar_monotherapy_warning", "bipolar_i", false, new[] { "fluoxetine" }, new Drug[0], true).SetName("bipolar_monotherapy hit");
            yield return new TestCaseData("bipolar_monotherapy_warning", "bipolar_i", false, new[] { "fluoxetine", "lithium" }, new Drug[0], false).SetName("bipolar_monotherapy covered by lithium");
            yield return new TestCaseData("serotonin_syndrome_with_tramadol", "mdd_single_episode", false, new[] { "escitalopram", "tramadol" }, new[] { tramadol }, true).SetName("tramadol hit");
            yield return new TestCaseData("tca_overdose_risk_with_suicidality", "mdd_single_episode", true, new[] { "amitriptyline" }, new Drug[0], true).SetName("tca suicidal hit");
            yield return new TestCaseData("tca_overdose_risk_with_suicidality", "mdd_single_episode", false, new[] { "amitriptyline" }, new Drug[0], false).SetName("tca not suicidal miss");
            yield return new TestCaseData("benzo_with_opioids", "mdd_single_episode", false, new[] { "lorazepam", "tramadol" }, new[] { tramadol }, true).SetName("benzo opioid hit");
            yield return new TestCaseData("benzo_monotherapy_for_depression", "mdd_single_episode", false, new[] { "clonazepam" }, new Drug[0], true).SetName("benzo mono hit");
            yield return new TestCaseData("benzo_monotherapy_for_depression", "mdd_single_episode", false, new[] { "clonazepam", "sertraline" }, new Drug[0], false).SetName("benzo with ssri miss");
            yield return new TestCaseData("lithium_with_nsaid", "bipolar_i", false, new[] { "lithium", "ibuprofen" }, new[] { nsaid }, true).SetName("lithium nsaid hit");
        }

        [TestCaseSource(nameof(RuleCases))]
        public void FormularyRule(string rule, string dx, bool suicidal, string[] drugs, Drug[] extra, bool expectHit)
        {
            var report = PrescriptionChecker.Check(drugs.Select(d => Rx(d)).ToList(), CaseWith(dx, suicidal), FormularyWith(extra));
            Assert.AreEqual(expectHit, report.lines.Any(l => l.rule_hits.Any(h => h.rule == rule)), string.Join("; ", report.critical));
            if (expectHit) Assert.IsNotEmpty(report.critical);
        }

        [Test]
        public void EveryFormularyRuleHasAnImplementationAndATest()
        {
            var tested = RuleCases().Select(t => (string)t.Arguments[0]).ToHashSet();
            foreach (var rule in data.formulary.rules)
            {
                Assert.IsTrue(PrescriptionChecker.Rules.ContainsKey(rule.id), $"no implementation for {rule.id}");
                Assert.IsTrue(tested.Contains(rule.id), $"no test for {rule.id}");
            }
        }

        [Test]
        public void DoseRangeAndRequiredDrug()
        {
            var f = FormularyWith();
            f.drugs.Single(d => d.id == "sertraline").dose_range_mg = new DoseRange { min = 25, max = 200 };
            var c = CaseWith("mdd_single_episode", false);
            c.answer_key.acceptable_rx.Add(new AcceptableRx { drug = "thiamine", required = true });
            var r = PrescriptionChecker.Check(new List<RxItem> { Rx("sertraline", 10), Rx("escitalopram", 10) }, c, f);
            Assert.AreEqual("below_range", r.lines[0].dose);
            Assert.AreEqual("not_verified", r.lines[1].dose);
            Assert.IsNotEmpty(r.minor);
            CollectionAssert.AreEqual(new[] { "thiamine" }, r.missing_required);
            var high = PrescriptionChecker.Check(new List<RxItem> { Rx("sertraline", 400) }, c, f);
            Assert.AreEqual("above_range", high.lines[0].dose);
            Assert.IsNotEmpty(high.critical);
        }

        [Test]
        public void PadRefusesDrugsOffTheFormulary()
        {
            var pad = new PrescriptionPad(data.formulary);
            Assert.Throws<System.ArgumentException>(() => pad.Add(Rx("tramadol")));
            Assert.Throws<System.ArgumentException>(() => pad.Add(new RxItem { drug = "sertraline", route = "IV" }));
            pad.Add(Rx("sertraline"));
            Assert.AreEqual(1, pad.Items.Count);
        }

        [Test]
        public void SlowedPauseAndSpeedMatchTheService()
        {
            Assert.AreEqual(0f, PsychSim.Cues.SpeechTiming.PreReplyDelay(0.05f));
            Assert.AreEqual(1.2f, PsychSim.Cues.SpeechTiming.PreReplyDelay(1f), 1e-4f);
            Assert.AreEqual(0.8f, PsychSim.Cues.SpeechTiming.PreReplyDelay(0.5f), 1e-4f);
            Assert.AreEqual(0.9f, PsychSim.Cues.SpeechTiming.TtsSpeed(1f, 1f), 1e-4f);
        }
    }
}
