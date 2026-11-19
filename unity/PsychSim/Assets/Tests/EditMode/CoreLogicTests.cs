using System.Collections.Generic;
using System.IO;
using System.Linq;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using NUnit.Framework;
using Rapport.Data;
using Rapport.Patient;
using Rapport.Scoring;
using Rapport.Tools;
using UnityEngine;

namespace Rapport.Tests
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
            i.ledger.Add(mdd.answer_key.required_intents.Concat(ScoringEngine.CommunicationIntents).Append("empathy_statement"), 60);  // empathy twice
            foreach (var c in mdd.answer_key.required_cues_noted.Append("fidget")) i.mseCues.Add(c);  // mse_expected also lists fidgeting
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
        public void MseIsMarkedAgainstWhatThePatientShowed()
        {
            var i = Perfect();
            i.mseCues.Clear();
            i.mseCues.UnionWith(new[] { "slumped", "gaze_avoid", "pupils_dilated" });
            i.cueSeconds = new Dictionary<string, float> { ["slumped"] = 120, ["gaze_avoid"] = 90, ["tearful"] = 2 };  // tears for 2 s: not observable
            var r = ScoringEngine.Score(i);
            CollectionAssert.AreEquivalent(new[] { "slumped", "gaze_avoid" }, r.cues_present);
            CollectionAssert.AreEquivalent(new[] { "pupils_dilated" }, r.cues_false);
            CollectionAssert.Contains(r.cues_not_shown, "tearful");
            Assert.AreEqual(16f + 4f * 2f / 3f, r.domains.Single(d => d.id == "observation").score, 0.05f);  // all shown signs found; 1 of 3 ticks wrong
            Assert.IsTrue(r.next_steps.Any(n => n.StartsWith("Record only what you see")));
            Assert.IsFalse(r.side_by_side.Single(x => x.area == "MSE").match);
        }

        [Test]
        public void HandsOutMakesTheTremorObservable()
        {
            var i = Perfect();
            var c = JsonConvert.DeserializeObject<CaseFile>(JsonConvert.SerializeObject(mdd));
            c.answer_key.required_cues_noted.Add("tremor_fine");
            i.caseFile = c;
            i.cueSeconds = new Dictionary<string, float>();
            Assert.IsFalse(ScoringEngine.Score(i).cues_present.Contains("tremor_fine"));
            i.examsDone.Add("hold_out_hands");
            Assert.IsTrue(ScoringEngine.Score(i).cues_present.Contains("tremor_fine"));
        }

        [Test]
        public void RiskAskedButNotAnsweredIsPartialNotCritical()
        {
            var i = Perfect();
            i.revealed = new HashSet<string>();  // asked, but the patient never disclosed (asked too early)
            var r = ScoringEngine.Score(i);
            Assert.AreEqual(30f * ScoringEngine.AskedNotDisclosed, r.domains.Single(d => d.id == "risk").score, 0.05f);
            Assert.IsEmpty(r.critical_errors);
            Assert.IsTrue(r.next_steps.Any(n => n.Contains("before the patient trusted you")));
            i.revealed = new HashSet<string> { "f_passive_si", "f_no_plan_no_attempt", "f_no_means" };
            Assert.AreEqual(30f, ScoringEngine.Score(i).domains.Single(d => d.id == "risk").score, 0.05f);
        }

        [Test]
        public void CaseCriticalIntentCountsAsRisk()
        {
            var alc = CaseVariants.Resolve(data.cases["alc_01"], "male");
            var i = new ScoreInput { caseFile = alc, data = data, finalTrust = 60, primaryDx = "alcohol_use_disorder" };
            i.ledger.Add(alc.answer_key.required_intents.Where(x => x != "ask_withdrawal_history"), 60);
            i.rx.Add(new RxItem { drug = "thiamine", route = "PO" });
            i.dispositions.Add("supervised_detox");
            var r = ScoringEngine.Score(i);
            Assert.IsTrue(r.critical_errors.Any(e => e.StartsWith("Risk item not asked") && e.Contains("fits")));
            Assert.AreEqual("Borderline fail", r.global_rating);
            StringAssert.Contains("Try:", r.next_steps[0]);
        }

        [Test]
        public void JargonAndStackedQuestionsCostAndAreQuoted()
        {
            var i = Perfect();
            i.turns.Add(new TurnRecord { t = 100, doctor = "Any suicidal ideation? Any plans?", intents = { "ask_suicidal_ideation" }, trustBefore = 50, trustAfter = 50 });
            var r = ScoringEngine.Score(i);
            Assert.IsTrue(r.feedback.Any(f => f.note.Contains("'ideation' is jargon")));
            Assert.IsTrue(r.feedback.Any(f => f.note.StartsWith("Several questions at once")));
            Assert.Less(r.domains.Single(d => d.id == "communication").score, ScoringEngine.Score(Perfect()).domains.Single(d => d.id == "communication").score);
            Assert.AreEqual("ideation", ScoringEngine.JargonIn("Any suicidal ideation?"));
            Assert.IsNull(ScoringEngine.JargonIn("How have you been sleeping?"));
        }

        [Test]
        public void FeedbackOnlySaysDisclosedForTheRightFactAndQuotesARealClosedQuestion()
        {
            var i = Perfect();
            i.turns.Add(new TurnRecord { t = 0, doctor = "Hello, I'm Dr. Faaz. What brings you in today?", intents = { "greet_introduce" } });
            i.turns.Add(new TurnRecord { t = 20, doctor = "Do you sleep well?", intents = { "ask_sleep" } });
            i.turns.Add(new TurnRecord { t = 40, doctor = "Are you eating?", intents = { "ask_appetite" } });
            i.turns.Add(new TurnRecord { t = 50, doctor = "Is your energy low?", intents = { "ask_energy" } });  // 1 open question in 5 turns
            i.turns.Add(new TurnRecord { t = 60, doctor = "Have you had thoughts of not wanting to live?", intents = { "ask_suicidal_ideation" }, revealed = { "f_sleep" } });
            var r = ScoringEngine.Score(i);
            StringAssert.Contains("did not answer it yet", r.feedback.Single(f => f.quote != null && f.quote.StartsWith("Have you had")).note);
            Assert.AreEqual("Do you sleep well?", r.feedback.Single(f => f.note.StartsWith("Mostly closed")).quote);
        }

        [Test]
        public void GlobalRatingFollowsTotalAndIsCappedByCriticalErrors()
        {
            Assert.AreEqual("Excellent", ScoringEngine.Global(85, 0));
            Assert.AreEqual("Clear pass", ScoringEngine.Global(70, 0));
            Assert.AreEqual("Borderline pass", ScoringEngine.Global(55, 0));
            Assert.AreEqual("Borderline fail", ScoringEngine.Global(95, 1));
            Assert.AreEqual("Clear fail", ScoringEngine.Global(95, 2));
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
        public void SlotsFillWithTheAuthoredOptionOrTheServicePicks()
        {
            var authored = CaseVariants.Resolve(mdd, "female");
            StringAssert.Contains("Rohan", authored.patient.background);
            Assert.IsFalse(authored.facts.Any(f => f.text.Contains("{")));
            var seeded = CaseVariants.Resolve(mdd, "male", new Dictionary<string, string>
                { ["hobby"] = "guitar", ["hobby_short"] = "guitar", ["sibling"] = "Varun", ["hometown"] = "Hubballi" });
            StringAssert.Contains("Varun", seeded.patient.background); StringAssert.Contains("Hubballi", seeded.patient.background);
            Assert.IsTrue(seeded.facts.Any(f => f.text.Contains("guitar practice")));
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
            yield return new TestCaseData("disulfiram_in_withdrawal", "alcohol_withdrawal", false, new[] { "disulfiram" }, new Drug[0], true).SetName("disulfiram while drinking hit");
            yield return new TestCaseData("disulfiram_in_withdrawal", "mdd_single_episode", false, new[] { "disulfiram" }, new Drug[0], false).SetName("disulfiram no alcohol miss");
            yield return new TestCaseData("antipsychotic_lowers_seizure_threshold", "alcohol_withdrawal", false, new[] { "olanzapine" }, new Drug[0], true).SetName("antipsychotic in withdrawal hit");
            yield return new TestCaseData("antipsychotic_lowers_seizure_threshold", "schizophrenia", false, new[] { "olanzapine" }, new Drug[0], false).SetName("antipsychotic in psychosis miss");
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
            Assert.AreEqual(0f, Rapport.Cues.SpeechTiming.PreReplyDelay(0.05f));
            Assert.AreEqual(1.2f, Rapport.Cues.SpeechTiming.PreReplyDelay(1f), 1e-4f);
            Assert.AreEqual(0.8f, Rapport.Cues.SpeechTiming.PreReplyDelay(0.5f), 1e-4f);
            Assert.AreEqual(0.9f, Rapport.Cues.SpeechTiming.TtsSpeed(1f, 1f), 1e-4f);
        }
        // ---------- ExamQueue (Phase H) ----------

        static Rapport.Cues.ExamQueue Queue(out List<string> log)
        {
            var q = new Rapport.Cues.ExamQueue();
            var l = new List<string>();
            q.Started += s => l.Add("+" + s.id);
            q.Ended += s => l.Add("-" + s.id);
            log = l;
            return q;
        }

        static Rapport.Cues.ExamStep Step(string id) => new Rapport.Cues.ExamStep { id = id };

        [Test]
        public void ExamQueue_HoldsUntilRelax()
        {
            var q = Queue(out var log);
            q.Enqueue(new[] { Step("hold_out_hands") });
            q.Tick(0f, false);
            q.Tick(1f, true);
            q.Tick(20f, true);
            Assert.IsTrue(q.Holding);
            q.Relax();
            Assert.IsNull(q.Current);
            CollectionAssert.AreEqual(new[] { "+hold_out_hands", "-hold_out_hands" }, log);
        }

        [Test]
        public void ExamQueue_HoldCapsAt30s()
        {
            var q = Queue(out _);
            q.Enqueue(new[] { Step("hold_out_hands") });
            q.Tick(0f, false);
            q.Tick(1f, true);
            q.Tick(30.9f, true);
            Assert.IsTrue(q.Holding);
            q.Tick(31.1f, true);
            Assert.IsFalse(q.Holding);
            Assert.IsNull(q.Current);
        }

        [Test]
        public void ExamQueue_NewCommandReleasesHold()
        {
            var q = Queue(out var log);
            q.Enqueue(new[] { Step("hold_out_hands") });
            q.Tick(0f, false);
            q.Tick(1f, true);
            q.Enqueue(new[] { Step("open_mouth") });
            Assert.Contains("-hold_out_hands", log);
            q.Tick(2f, false);
            Assert.AreEqual("open_mouth", q.Current.id);
        }

        [Test]
        public void ExamQueue_CommandMidMotionRunsAfterShortHold()
        {
            var q = Queue(out _);
            q.Enqueue(new[] { Step("hold_out_hands") });
            q.Tick(0f, false);
            q.Enqueue(new[] { Step("open_mouth") });  // arrives while the hands are still rising
            q.Tick(1f, true);
            Assert.IsTrue(q.Holding);
            q.Tick(1f + Rapport.Cues.ExamQueue.MinHoldS + 0.01f, true);
            Assert.AreEqual("open_mouth", q.Current.id);
        }

        [Test]
        public void ExamQueue_ChainedInOneMessageDoesNotWaitForTheCap()
        {
            var q = Queue(out _);
            q.Enqueue(new[] { Step("hold_out_hands"), Step("open_mouth") });
            q.Tick(0f, false);
            q.Tick(1f, true);
            q.Tick(3f, true);
            Assert.AreEqual("open_mouth", q.Current.id);
        }

        [Test]
        public void ExamQueue_RunsInOrder()
        {
            var q = Queue(out var log);
            q.Enqueue(new[] { Step("stand_up"), Step("walk_few_steps"), Step("sit_down") });
            q.Tick(0f, false);
            q.Tick(1f, true);
            q.Tick(2f, true);
            q.Tick(3f, true);
            CollectionAssert.AreEqual(new[] { "+stand_up", "-stand_up", "+walk_few_steps", "-walk_few_steps", "+sit_down", "-sit_down" }, log);
            Assert.IsFalse(q.Standing);
        }

        [Test]
        public void ExamQueue_SeatedOnlyInsertsSitDown()
        {
            var q = Queue(out var log);
            q.Enqueue(new[] { Step("stand_up") });
            q.Tick(0f, false);
            q.Tick(1f, true);
            Assert.IsTrue(q.Standing);
            q.Enqueue(new[] { Step("roll_up_sleeves") });
            q.Tick(2f, false);
            Assert.AreEqual("sit_down", q.Current.id);
            q.Tick(3f, true);
            Assert.AreEqual("roll_up_sleeves", q.Current.id);
        }

        [Test]
        public void ExamQueue_WalkWhileSeatedStandsFirst()
        {
            var q = Queue(out _);
            q.Enqueue(new[] { Step("walk_few_steps") });
            q.Tick(0f, false);
            Assert.AreEqual("stand_up", q.Current.id);
        }

        [Test]
        public void ExamQueue_ParsesMessageAndDropsRefused()
        {
            var msg = JObject.Parse(@"{""type"":""exam"",""relax"":true,""actions"":[
                {""id"":""hold_out_hands"",""slots"":{""which"":""left"",""palms"":""up""},""comply"":true},
                {""id"":""roll_up_sleeves"",""slots"":{""which"":""both""},""comply"":false}]}");
            var steps = Rapport.Cues.ExamQueue.Parse(msg, out bool relax);
            Assert.IsTrue(relax);
            Assert.AreEqual(1, steps.Count);
            Assert.AreEqual(("hold_out_hands", "left", "up"), (steps[0].id, steps[0].which, steps[0].palms));
        }
        // ---------- CameraDirector (Phase H) ----------

        [Test]
        public void CameraDirector_MapsActionsToCloseUps()
        {
            System.Func<string, Rapport.Platform.CameraDirector.Shot> d = Rapport.Platform.CameraDirector.ShotFor;
            Assert.AreEqual(32f, d("hold_out_hands").fov);
            Assert.AreSame(d("roll_up_sleeves"), d("show_forearms"));
            Assert.AreSame(d("look_at_light"), d("follow_finger"));
            Assert.AreSame(d("open_mouth"), d("stick_out_tongue"));
            Assert.AreSame(d("stand_up"), d("walk_few_steps"));
            Assert.AreEqual(0f, d("walk_few_steps").distance);  // full body from the doctor's seat: the room is too small to back off
            Assert.IsNull(d("juggle"));
            Assert.IsNull(d(null));
        }

        [Test]
        public void DoctorView_PutsTheHeadLeftOfCentreInTheUpperThird()
        {
            var from = new Vector3(0.3f, 1.2f, -0.4f); var head = new Vector3(-1.1f, 1.25f, 0.2f);
            foreach (var fov in new[] { Rapport.Platform.CameraDirector.DoctorFov, 42f })
            {
                var local = Quaternion.Inverse(Rapport.Platform.DesktopRig.FollowRotation(from, head, fov, 16f / 9f)) * (head - from);
                float t = Mathf.Tan(fov * 0.5f * Mathf.Deg2Rad);
                Assert.AreEqual(0.30f, 0.5f + 0.5f * local.x / local.z / (t * 16f / 9f), 0.01f);  // 30% from the left, clear of the side panel
                Assert.AreEqual(2f / 3f, 0.5f + 0.5f * local.y / local.z / t, 0.01f);           // eyes on the upper third
            }
        }

        [Test]
        public void AngleSeats_TurnsThePatientAboutHerHipsTo110DegreesFromTheDoctor()
        {
            var room = new GameObject("Room").transform;
            Transform Child(string n, Vector3 p, float yaw) { var t = new GameObject(n).transform; t.SetParent(room); t.SetPositionAndRotation(p, Quaternion.Euler(0f, yaw, 0f)); return t; }
            try
            {
                // the exported office: patient faces -X (156° to the doctor), doctor faces her
                var pat = Child("PatientAnchor", new Vector3(0.576f, 0f, -0.18f), 270f);
                Child("ChairApproach", pat.position, 270f);
                var eye = Child("KeyLightTarget", new Vector3(0.858f, 1.193f, -0.185f), 0f);
                var doc = Child("DoctorAnchor", new Vector3(-0.496f, 1.2f, 0.42f), 114.1f);
                var hips = pat.position - pat.forward * 0.40f;
                float eyeToHips = Vector3.Distance(eye.position, hips);
                Rapport.Editor.EncounterSceneBuilder.AngleSeats(room);
                Assert.AreEqual(Rapport.Editor.EncounterSceneBuilder.SeatAngle, Vector3.Angle(pat.forward, doc.forward), 0.1f);
                Assert.Less((pat.position - pat.forward * 0.40f - hips).magnitude, 1e-4f);   // still on the cushion
                Assert.AreEqual(eyeToHips, Vector3.Distance(eye.position, hips), 1e-4f);          // the key light's target turns with her
                var toDoc = doc.position - eye.position; toDoc.y = 0f;
                Assert.Less(Vector3.Angle(pat.forward, toDoc), 15f);                             // she faces the doctor, a little past him
                Assert.AreEqual(pat.position, room.Find("ChairApproach").position);
                var (p0, r0) = (pat.position, doc.rotation);
                Rapport.Editor.EncounterSceneBuilder.AngleSeats(room);                            // idempotent
                Assert.Less((pat.position - p0).magnitude, 1e-4f);
                Assert.Less(Quaternion.Angle(doc.rotation, r0), 0.01f);
            }
            finally { Object.DestroyImmediate(room.gameObject); }
        }

        [Test]
        public void IdleLife_BlinkBreathAndSaccadeTimingsAreNatural()
        {
            Assert.AreEqual(0f, Rapport.Cues.FacePresets.BlinkShape(-0.01f));
            Assert.AreEqual(1f, Rapport.Cues.FacePresets.BlinkShape(0.08f));                  // shut
            Assert.Greater(Rapport.Cues.FacePresets.BlinkShape(0.17f), 0.3f);                 // opens slower than it closes (70 ms)
            Assert.Less(Rapport.Cues.FacePresets.BlinkShape(0.26f), 0.05f);                   // open again within 0.27 s
            Assert.AreEqual(0f, Rapport.Cues.FacePresets.BlinkShape(0.3f));
            var gaps = Enumerable.Range(1, 400).Select(i => Rapport.Cues.FacePresets.BlinkGap((i * 0.6180339f) % 1f, (i * 0.7548776f) % 1f)).ToList();
            Assert.That(gaps.All(g => g >= 0.8f && g <= 9f));
            Assert.AreEqual(3.4f, gaps.Average(), 0.6f);                                       // about 17 blinks a minute
            Assert.AreEqual(0f, Rapport.Cues.Breathing.Inhale(0f), 1e-4f);
            Assert.AreEqual(1f, Rapport.Cues.Breathing.Inhale(0.4f), 1e-4f);
            Assert.AreEqual(Rapport.Cues.Breathing.Inhale(0.2f), Rapport.Cues.Breathing.Inhale(1.2f), 1e-4f);
            Assert.AreEqual(0.3f, Rapport.Cues.GazeController.SaccadeGap(0f), 1e-4f);
            Assert.AreEqual(2.5f, Rapport.Cues.GazeController.SaccadeGap(1f), 1e-4f);
        }

        [Test]
        public void BodyLanguage_FollowsEmotionIntensityAndTrust()
        {
            System.Func<string, float, string, float, Rapport.Cues.BodyLanguage.Targets> f = Rapport.Cues.BodyLanguage.For;
            var calm = f("neutral", 0f, "", 50f);
            Assert.AreEqual(0f, calm.lean); Assert.AreEqual(0f, calm.avoid, 1e-4f); Assert.AreEqual(1f, calm.motion);
            Assert.Greater(f("angry", 1f, "", 50f).lean, 4f);                                  // leans in
            Assert.Greater(f("neutral", 0.8f, "hostile", 50f).lean, 3f);                       // hostile behaviour reads as anger
            Assert.AreEqual(f("angry", 1f, "", 50f).lean / 2f, f("angry", 0.5f, "", 50f).lean, 1e-4f);  // scales with intensity
            var sad = f("sad", 1f, "", 50f);
            Assert.Greater(sad.headPitch, 8f); Assert.Greater(sad.slump, 0.5f); Assert.Greater(sad.avoid, 0.3f);
            Assert.Greater(f("ashamed", 1f, "", 50f).avoid, sad.avoid);                      // shame looks away most
            var anx = f("anxious", 1f, "", 50f);
            Assert.Greater(anx.fidget, 0.5f); Assert.Greater(anx.knee, 0.5f); Assert.Less(anx.pace, 1f);
            Assert.Less(f("flat", 1f, "", 50f).motion, 0.5f);
            Assert.Greater(f("confused", 1f, "", 50f).tilt, 5f);
            Assert.Less(f("neutral", 0f, "", 100f).avoid, f("neutral", 0f, "", 0f).avoid);   // trust raises eye contact
            Assert.AreEqual(0f, Rapport.Cues.BodyLanguage.Envelope(-0.1f, 0.3f, 1f, 0.5f));
            Assert.AreEqual(1f, Rapport.Cues.BodyLanguage.Envelope(0.8f, 0.3f, 1f, 0.5f));
            Assert.AreEqual(0f, Rapport.Cues.BodyLanguage.Envelope(1.9f, 0.3f, 1f, 0.5f));
        }
    }
}
