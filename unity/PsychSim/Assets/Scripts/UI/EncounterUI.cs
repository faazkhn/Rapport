using System;
using System.Globalization;
using System.Linq;
using Rapport.Core;
using Rapport.Scoring;
using Rapport.Speech;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.UIElements;

namespace Rapport.UI
{
    /// <summary>
    /// Desktop view (UI Toolkit, built in code): brief card, side-panel tablet (chat, MSE, diagnosis, prescription, disposition, finish),
    /// subtitles for both speakers, score screen. No clinical logic here: everything goes through EncounterManager and the Tools controllers.
    /// </summary>
    [RequireComponent(typeof(UIDocument))]
    public class EncounterUI : MonoBehaviour
    {
        public static readonly string[] Tabs = { "Chat", "MSE", "Diagnosis", "Prescription", "Disposition", "Finish" };
        [SerializeField] EncounterManager encounter;

        VisualElement root, panel, tabBody, overlay;
        Label timer, docSub, patSub, status, voiceLabel, latency;
        VisualElement voiceDot, micFill;
        Button modeButton;
        ScrollView transcript;
        TextField input;
        string currentTab = "Chat";
        bool uiEdit;
        float docSubUntil, patSubUntil;

        static readonly Color Bg = new(0.09f, 0.11f, 0.14f, 0.94f), Card = new(0.15f, 0.17f, 0.21f, 1f), Accent = new(0.35f, 0.6f, 0.9f), Warn = new(0.95f, 0.65f, 0.25f), Bad = new(0.92f, 0.33f, 0.3f), Good = new(0.4f, 0.8f, 0.5f);

        void Start()  // after EncounterManager.Awake has loaded the case
        {
            root = GetComponent<UIDocument>().rootVisualElement;
            root.Clear();
            root.style.flexGrow = 1;
            root.pickingMode = PickingMode.Ignore;
            // Space is push-to-talk: it must not also click the focused button or tick the focused checkbox (Enter still does)
            root.RegisterCallback<NavigationSubmitEvent>(e =>
            {
                if (encounter.Voice is { HandsFree: false } && Keyboard.current?.spaceKey.isPressed == true) e.StopImmediatePropagation();
            }, TrickleDown.TrickleDown);
            BuildPanel();
            BuildSubtitles();
            encounter.PhaseChanged += OnPhase;
            encounter.Subtitle += OnSubtitle;
            encounter.Scored += ShowScore;
            encounter.PatientReplied += t => { if (!string.IsNullOrEmpty(t.reply.utterance)) AddTranscript(encounter.Case.patient.name.Split(' ')[0], t.reply.utterance, Color.white); };
            Action<string, string> refresh = (_, __) => { if (!uiEdit) OpenTab(currentTab); };
            encounter.Mse.Changed += refresh; encounter.Dx.Changed += refresh; encounter.Rx.Changed += refresh; encounter.Disposition.Changed += refresh;
            OnPhase(encounter.Phase);
        }

        void Update()
        {
            if (timer != null && encounter.Case != null)
            {
                var s = encounter.SessionSeconds;
                bool over = s > encounter.TimeLimitSeconds;
                timer.text = $"{encounter.Mode} · {(int)s / 60:00}:{(int)s % 60:00} / {encounter.TimeLimitSeconds / 60:0} min" + (over ? " (over time)" : "");
                timer.style.color = over ? Bad : s > encounter.TimeLimitSeconds - 120 ? Warn : new Color(0.8f, 0.85f, 0.9f);
            }
            UpdateVoiceBar();
            if (status != null) status.text = encounter.ServiceError;
            if (Time.time > docSubUntil) docSub.style.display = DisplayStyle.None;
            if (Time.time > patSubUntil) patSub.style.display = DisplayStyle.None;
        }

        // ---------------------------------------------------------------- layout

        void BuildPanel()
        {
            panel = Box(Bg);
            panel.style.position = Position.Absolute;
            panel.style.right = 0; panel.style.top = 0; panel.style.bottom = 0; panel.style.width = 600;
            panel.style.paddingLeft = panel.style.paddingRight = 16;
            panel.style.paddingTop = 12;
            root.Add(panel);

            var head = Row();
            head.Add(Text("Rapport", 22, Color.white, true));
            head.Add(Spacer());
            timer = Text("", 18, new Color(0.8f, 0.85f, 0.9f));
            head.Add(timer);
            panel.Add(head);
            panel.Add(Text("For education only. Draft content, not faculty-validated.", 14, Warn));
            panel.Add(BuildVoiceBar());

            var tabs = Row();
            tabs.style.flexWrap = Wrap.Wrap;
            tabs.style.marginTop = 10;
            foreach (var t in Tabs) tabs.Add(Button(t, () => OpenTab(t), 15));
            panel.Add(tabs);

            tabBody = new VisualElement();
            tabBody.style.flexGrow = 1;
            tabBody.style.marginTop = 8;
            panel.Add(tabBody);

            transcript = new ScrollView();
            transcript.style.flexGrow = 1;
            input = new TextField { multiline = false };
            input.style.fontSize = 18;
            input.RegisterCallback<KeyDownEvent>(e =>
            {
                if (e.keyCode == KeyCode.Return || e.keyCode == KeyCode.KeypadEnter || e.character == '\n') { Send(); e.StopPropagation(); }
            }, TrickleDown.TrickleDown);
            status = Text("", 14, new Color(0.7f, 0.75f, 0.8f));
        }

        void BuildSubtitles()
        {
            var subs = new VisualElement { pickingMode = PickingMode.Ignore };
            subs.style.position = Position.Absolute;
            subs.style.left = 40; subs.style.right = 640; subs.style.bottom = 36;
            subs.style.alignItems = Align.Center;
            docSub = Subtitle(new Color(0.75f, 0.85f, 1f));
            patSub = Subtitle(Color.white);
            subs.Add(docSub); subs.Add(patSub);
            root.Add(subs);
        }

        Label Subtitle(Color c)
        {
            var l = Text("", 30, c);
            l.style.backgroundColor = new Color(0, 0, 0, 0.65f);
            l.style.paddingLeft = l.style.paddingRight = 14; l.style.paddingTop = l.style.paddingBottom = 6;
            l.style.marginTop = 6;
            l.style.whiteSpace = WhiteSpace.Normal;
            l.style.unityTextAlign = TextAnchor.MiddleCenter;
            l.style.display = DisplayStyle.None;
            return l;
        }

        void OnSubtitle(string speaker, string text)
        {
            var (label, name) = speaker == "doctor" ? (docSub, "Doctor") : (patSub, encounter.Case.patient.name.Split(' ')[0]);
            label.text = $"{name}: {text}";
            label.style.display = string.IsNullOrEmpty(text) ? DisplayStyle.None : DisplayStyle.Flex;
            float until = Time.time + Mathf.Clamp(text.Length / 12f, 3f, 12f);
            if (speaker == "doctor") { docSubUntil = until; AddTranscript("Dr. Faaz", text, new Color(0.75f, 0.85f, 1f)); }
            else patSubUntil = until;
        }

        void AddTranscript(string name, string text, Color c)
        {
            var line = Text($"{name}: {text}", 16, c);
            line.style.whiteSpace = WhiteSpace.Normal;
            line.style.marginBottom = 6;
            transcript.Add(line);
            transcript.schedule.Execute(() => transcript.scrollOffset = new Vector2(0, float.MaxValue));
        }

        // ---------------------------------------------------------------- voice bar: listening / thinking / speaking, mic meter, mode

        VisualElement BuildVoiceBar()
        {
            var bar = Row();
            bar.style.marginTop = 8; bar.style.paddingTop = bar.style.paddingBottom = 6; bar.style.paddingLeft = 8;
            bar.style.backgroundColor = Card;
            voiceDot = new VisualElement();
            voiceDot.style.width = voiceDot.style.height = 16;
            voiceDot.style.borderTopLeftRadius = voiceDot.style.borderTopRightRadius = voiceDot.style.borderBottomLeftRadius = voiceDot.style.borderBottomRightRadius = 8;
            voiceDot.style.marginRight = 8;
            bar.Add(voiceDot);
            voiceLabel = Text("Voice off", 17, Color.white, true);
            voiceLabel.style.width = 185;
            bar.Add(voiceLabel);
            var meter = Box(new Color(0, 0, 0, 0.5f));
            meter.style.width = 120; meter.style.height = 10; meter.style.marginRight = 10;
            micFill = Box(Good);
            micFill.style.height = 10; micFill.style.width = 0;
            meter.Add(micFill);
            bar.Add(Text("Mic", 13, new Color(0.7f, 0.75f, 0.8f)));
            bar.Add(meter);
            modeButton = Button("Use hands-free", ToggleMode, 13);
            modeButton.tooltip = "Push-to-talk: hold Space while you speak. Hands-free: the mic is always open (use a headset).";
            bar.Add(modeButton);
            bar.Add(Spacer());
            latency = Text("", 13, new Color(0.7f, 0.75f, 0.8f));
            latency.style.marginRight = 8;
            bar.Add(latency);
            return bar;
        }

        void ToggleMode()
        {
            var v = encounter.Voice;
            if (v == null) return;
            v.SetHandsFree(!v.HandsFree);
            PlayerPrefs.SetInt(VoiceSession.HandsFreePref, v.HandsFree ? 1 : 0);
        }

        bool pttDown;

        void UpdateVoiceBar()
        {
            if (voiceLabel == null) return;
            var v = encounter.Voice;
            var st = v == null || !v.Connected ? VoiceState.Off : v.State;
            (string label, Color c) = st switch
            {
                VoiceState.Listening => (v.HandsFree ? "Listening" : pttDown ? "Listening (PTT)" : "Hold Space to talk", Good),
                VoiceState.Hearing => ("Hearing you", new Color(0.55f, 0.95f, 0.6f)),
                VoiceState.Thinking => ("Thinking...", Warn),
                VoiceState.Speaking => ("Speaking", Accent),
                _ => ("Voice off (typed only)", new Color(0.5f, 0.5f, 0.5f)),
            };
            voiceLabel.text = label;
            voiceDot.style.backgroundColor = c;
            micFill.style.width = 120 * (v?.MicLevel ?? 0);
            if (modeButton != null && v != null) modeButton.text = v.HandsFree ? "Use push-to-talk" : "Use hands-free";
            if (encounter.LastLatencyMs >= 0) latency.text = $"Last reply {encounter.LastLatencyMs / 1000f:0.0} s";

            // push-to-talk on Space, unless the learner is typing in the chat box
            var kb = Keyboard.current;
            if (v != null && !v.HandsFree && kb != null && encounter.Phase == Phase.Active && (input == null || input.focusController?.focusedElement != input))
            {
                if (kb.spaceKey.wasPressedThisFrame) { pttDown = true; v.PushToTalk(true); }
                if (kb.spaceKey.wasReleasedThisFrame && pttDown) { pttDown = false; v.PushToTalk(false); }
            }
        }

        // ---------------------------------------------------------------- phases

        void OnPhase(Phase p)
        {
            overlay?.RemoveFromHierarchy();
            panel.SetEnabled(p == Phase.Active);
            panel.style.display = p == Phase.Debrief ? DisplayStyle.None : DisplayStyle.Flex;   // the debrief card stands alone, no greyed tablet behind it
            if (p == Phase.Start) ShowStart();
            if (p == Phase.Brief) ShowBrief();
            if (p == Phase.Active) OpenTab("Chat");
        }

        // ---------------------------------------------------------------- start screen and prebrief (plan C6)

        const string Surprise = "random";   // start-screen choice for a seeded patient
        string startCase, startVariant = "female", startLook;
        Mode startMode = Mode.Practice;

        void ShowStart()
        {
            if (string.IsNullOrEmpty(startCase) || !encounter.Data.cases.ContainsKey(startCase)) startCase = encounter.Data.cases.Keys.First();
            var card = Overlay(900);
            card.Add(Text("Rapport", 34, Color.white, true));
            card.Add(Text("Embodied psychiatry and addiction OSCE simulator. For education only.", 17, Warn));
            card.Add(Heading("1. Case"));
            var cases = encounter.Data.cases.Values.ToList();
            var caseRow = Row();
            foreach (var c in cases) { var id = c.id; caseRow.Add(Choice(c.title, startCase == id, () => { startCase = id; startLook = null; ShowStart(); })); }
            card.Add(caseRow);
            card.Add(Heading("2. Patient"));
            var vRow = Row();
            foreach (var kv in encounter.Data.cases[startCase].variants)
            {
                var key = kv.Key;
                vRow.Add(Choice($"{char.ToUpper(key[0]) + key.Substring(1)} · {kv.Value.name}", startVariant == key, () => SelectVariant(key)));
            }
            if (encounter.Data.cases[startCase].slots.Count > 0 || encounter.Data.cases[startCase].styles_allowed.Count > 1)
                vRow.Add(Choice("Surprise me", startVariant == Surprise, () => SelectVariant(Surprise)));
            card.Add(vRow);
            if (startVariant != Surprise && encounter.Data.cases[startCase].variants.TryGetValue(startVariant, out var sv) && encounter.Looks(sv.sex) is { Count: > 1 } looks)
            {
                var lRow = Row();
                lRow.Add(Text("Look", 16, new Color(0.8f, 0.85f, 0.9f)));
                for (int i = 0; i < looks.Count; i++)
                {
                    var look = looks[i];
                    lRow.Add(Choice($"{i + 1}" + (look == sv.model_id ? " (case)" : ""), (startLook ?? sv.model_id) == look, () => { startLook = look; ShowStart(); }));
                }
                card.Add(lRow);
            }
            card.Add(Para(startVariant == Surprise
                ? "A random patient: the same clinical story, but family details and the way they talk change each time. The debrief says who you met."
                : "Same clinical story for both; only the name, pronouns, body and voice change."));
            card.Add(Heading("3. Mode"));
            var mRow = Row();
            mRow.Add(Choice("Practice", startMode == Mode.Practice, () => { startMode = Mode.Practice; ShowStart(); }));
            mRow.Add(Choice("Assessment", startMode == Mode.Assessment, () => { startMode = Mode.Assessment; ShowStart(); }));
            card.Add(mRow);
            card.Add(Para(startMode == Mode.Practice ? "Practice: the 15-minute clock is a guide; you can run over." : "Assessment: a strict 15-minute station; it ends and scores itself at 15:00."));
            var go = Button("Continue", () =>
            {
                if (startVariant != Surprise) { encounter.Configure(startCase, startVariant, startMode, startLook); return; }
                var keys = encounter.Data.cases[startCase].variants.Keys.ToList();
                _ = encounter.ConfigureSeeded(startCase, keys[UnityEngine.Random.Range(0, keys.Count)], startMode, UnityEngine.Random.Range(0, int.MaxValue));
            }, 20);
            go.style.marginTop = 16;
            card.Add(go);
        }

        /// <summary>Demo hook: highlights a patient option on the start screen as if clicked.</summary>
        public void SelectVariant(string variant)
        {
            startVariant = variant;
            startLook = null;
            if (encounter.Phase == Phase.Start) ShowStart();
        }

        Button Choice(string text, bool selected, Action onClick)
        {
            var b = Button(text, onClick, 18);
            b.style.marginRight = 10;
            b.style.paddingLeft = b.style.paddingRight = 14; b.style.paddingTop = b.style.paddingBottom = 8;
            b.style.backgroundColor = selected ? Accent : new Color(0.25f, 0.27f, 0.31f);
            b.style.color = Color.white;
            return b;
        }

        void ShowBrief()
        {
            var c = encounter.Case;
            var card = Overlay(860);
            card.Add(Text("Before you start", 30, Color.white, true));
            card.Add(Text($"{c.title} · {c.patient.name} · {encounter.Mode}", 18, new Color(0.8f, 0.85f, 0.9f)));
            if (c.status != "approved") card.Add(Banner("Draft content, not faculty-validated"));
            card.Add(Heading("Objectives"));
            card.Add(Para("• Build rapport and take a focused psychiatric history.\n• Observe the patient: posture, gaze, speech, affect. Record what you see in the MSE tab.\n"
                          + "• Assess risk directly and kindly.\n• Make a working diagnosis and a safe management plan."));
            card.Add(Heading("How it works"));
            card.Add(Para($"Talk to the patient out loud. The patient answers in their own voice. {c.time_limit_min ?? 15:0} minutes. Hold Space while you speak "
                          + "(push-to-talk), or type. With a headset you can switch to hands-free; with speakers, stay on push-to-talk."));
            card.Add(Para("Scoring is formative and risk-first: risk assessment counts most, and missing a risk question means 'Not passed'. "
                          + "The debrief quotes your own words and shows your conclusions next to the case."));
            if (!string.IsNullOrEmpty(c.content_note))
            {
                var note = Text("Content note: " + c.content_note, 17, Warn);
                note.style.whiteSpace = WhiteSpace.Normal; note.style.marginTop = 10;
                card.Add(note);
            }
            card.Add(Para("This is a safe place to practise and make mistakes. You can pause or leave at any time.", Good));
            card.Add(Heading("Referral note"));
            card.Add(Para(c.referral_note));
            card.Add(Para("Privacy: your voice is processed on this computer only (local speech recognition and a local language model). Nothing is recorded or sent to the cloud."));
            var go = Button("Enter the room", () => encounter.BeginEncounter(), 20);
            go.style.marginTop = 16;
            card.Add(go);
        }

        void ShowScore(ScoreResult s)
        {
            var card = Overlay(1100);
            var sv = new ScrollView();
            sv.style.maxHeight = 900;
            card.Add(sv);
            sv.Add(Banner("Draft content, not faculty-validated. For education only."));
            sv.Add(Text(s.verdict, 34, s.critical_errors.Count > 0 ? Bad : Good, true));
            foreach (var e in s.critical_errors) sv.Add(Para("Critical error: " + e, Bad));
            sv.Add(Text($"Score {s.total:0.#} / 100 (formative) · Global rating: {s.global_rating}", 26, Color.white, true));
            if (s.next_steps.Count > 0)
            {
                sv.Add(Heading("Next time, focus on"));
                for (int k = 0; k < s.next_steps.Count; k++) sv.Add(Para($"{k + 1}. {s.next_steps[k]}", Color.white));
            }
            if (encounter.Case.seed is int seed)
                sv.Add(Para($"You met {encounter.Case.patient.name}, conversation style: {encounter.StyleLabel ?? encounter.Case.style} (patient seed {seed}; same seed, same patient)."));
            sv.Add(Heading("Your conclusions vs the case"));
            var grid = new VisualElement();
            var hdr = Row();
            foreach (var h in new[] { ("", 120), ("You", 440), ("Case truth", 440) }) { var l = Text(h.Item1, 15, Accent, true); l.style.width = h.Item2; hdr.Add(l); }
            grid.Add(hdr);
            foreach (var row in s.side_by_side)
            {
                var r = Row();
                r.style.alignItems = Align.FlexStart;
                r.style.backgroundColor = row.match ? new Color(0.2f, 0.35f, 0.25f, 0.5f) : new Color(0.45f, 0.2f, 0.18f, 0.5f);
                r.style.paddingTop = r.style.paddingBottom = 4;
                foreach (var (txt, w, bold) in new[] { (row.area, 120, true), (row.yours, 440, false), (row.truth, 440, false) })
                {
                    var l = Text(txt, 14, Color.white, bold);
                    l.style.width = w; l.style.whiteSpace = WhiteSpace.Normal; l.style.paddingRight = 8;
                    r.Add(l);
                }
                grid.Add(r);
            }
            sv.Add(grid);
            sv.Add(Heading("Feedback on your own words"));
            foreach (var f in s.feedback)
            {
                var when = f.quote == null ? "" : $"At {(int)f.t / 60:00}:{(int)f.t % 60:00} you said \"{f.quote}\". ";
                sv.Add(Para((f.kind == "good" ? "✓ " : "△ ") + when + f.note, f.kind == "good" ? Good : Warn));
            }
            foreach (var d in s.domains)
            {
                var r = Row();
                r.Add(Text(d.name, 18, Color.white)); r.Add(Spacer()); r.Add(Text($"{d.score:0.#} / {d.max:0}", 18, Color.white));
                sv.Add(r);
                foreach (var n in d.notes) sv.Add(Para("   " + n));
            }
            sv.Add(Heading("What the patient showed vs what you recorded"));
            string Cue(string id) => encounter.Data.cues.cues.FirstOrDefault(x => x.id == id)?.name ?? id;
            foreach (var cue in s.cues_present) sv.Add(Para($"{(s.cues_recorded.Contains(cue) ? "✓ Seen and recorded" : "✗ Shown, not recorded")}   {Cue(cue)}", s.cues_recorded.Contains(cue) ? Good : Warn));
            foreach (var cue in s.cues_false) sv.Add(Para($"✗ Recorded, not present   {Cue(cue)}", Bad));
            foreach (var cue in s.cues_not_shown) sv.Add(Para($"·  Not shown this session (no mark lost)   {Cue(cue)}"));
            if (s.missed_intents.Count > 0) { sv.Add(Heading("Questions not asked")); sv.Add(Para(string.Join(", ", s.missed_intents))); }
            sv.Add(Heading("Prescription checks"));
            foreach (var l in s.rx.lines)
                sv.Add(Para($"{l.drug}: dose {(l.dose == "not_verified" ? "not verified (no faculty-approved range yet)" : l.dose.Replace('_', ' '))}; {(l.appropriate ? "appropriate for this case" : "not in the case's acceptable options")}"
                            + string.Concat(l.rule_hits.Select(h => $"; RULE {h.rule}: {h.why}"))));
            if (s.rx.lines.Count == 0) sv.Add(Para("No prescription written."));
            sv.Add(Heading("Teaching points"));
            foreach (var t in s.teaching_points) sv.Add(Para("• " + t));
            AddExaminerNotes(sv);
        }

        async void AddExaminerNotes(ScrollView sv)
        {
            sv.Add(Heading("Examiner notes (AI, formative)"));
            var wait = Para("Reading your interview...");
            sv.Add(wait);
            var notes = await encounter.ExaminerNotes();
            wait.RemoveFromHierarchy();
            if (notes == null) { sv.Add(Para("Not available (the patient service did not answer).")); return; }
            sv.Add(Para("From the local language model, on your spoken skills only. It does not change your score; treat it as a second opinion.",
                        new Color(0.7f, 0.75f, 0.8f)));
            foreach (var (key, mark, colour) in new[] { ("strengths", "✓ ", Good), ("improvements", "△ ", Warn) })
                foreach (var n in notes[key] ?? new Newtonsoft.Json.Linq.JArray())
                {
                    var q = (string)n["quote"] ?? "";
                    // the model praises lines the rules flag (jargon, stacked questions): it is weakest exactly there (Geathers 2025)
                    if (key == "strengths" && (ScoringEngine.JargonIn(q) != null || q.Count(ch => ch == '?') >= 2)) continue;
                    sv.Add(Para($"{mark}\"{q}\": {n["comment"]}", colour));
                }
        }

        // ---------------------------------------------------------------- tabs (also a demo hook: open any tab from code)

        public void OpenTab(string tab)
        {
            currentTab = tab;
            tabBody.Clear();
            switch (tab)
            {
                case "Chat": ChatTab(); break;
                case "MSE": MseTab(); break;
                case "Diagnosis": DxTab(""); break;
                case "Prescription": RxTab(); break;
                case "Disposition": DispoTab(); break;
                case "Finish": FinishTab(); break;
            }
        }

        void ChatTab()
        {
            tabBody.Add(transcript);
            tabBody.Add(status);
            var r = Row();
            input.style.flexGrow = 1;
            r.Add(input);
            r.Add(Button("Send", Send, 16));
            tabBody.Add(r);
            tabBody.Add(Text("Speak to the patient, or type a question and press Enter.", 13, new Color(0.65f, 0.7f, 0.75f)));
            input.schedule.Execute(() => input.Focus());
        }

        async void Send()
        {
            var text = input.value;
            if (string.IsNullOrWhiteSpace(text) || encounter.Busy) return;
            input.value = "";
            await encounter.SubmitDoctorLine(text);
            input.Focus();
        }

        void MseTab()
        {
            var sv = Scroll();
            foreach (var section in encounter.Mse.Sections)
            {
                sv.Add(Heading(char.ToUpper(section[0]) + section.Substring(1).Replace('_', ' ')));
                foreach (var cue in encounter.Mse.CuesIn(section))
                {
                    var t = new Toggle(cue.name) { value = encounter.Mse.Ticked.Contains(cue.id) };
                    t.style.fontSize = 15; t.labelElement.style.color = Color.white;
                    var id = cue.id;
                    t.RegisterValueChangedCallback(e => Ui(() => encounter.Mse.SetTick(id, e.newValue)));
                    sv.Add(t);
                }
                var note = new TextField { multiline = true, value = encounter.Mse.Notes.TryGetValue(section, out var n) ? n : "" };
                note.style.minHeight = 40;
                var s = section;
                note.RegisterValueChangedCallback(e => Ui(() => encounter.Mse.SetNote(s, e.newValue)));
                sv.Add(note);
            }
        }

        void DxTab(string query)
        {
            var dx = encounter.Dx;
            var search = new TextField("Search") { value = query };
            search.RegisterValueChangedCallback(e => { tabBody.Clear(); DxTab(e.newValue); tabBody.Q<TextField>().Focus(); });
            tabBody.Add(search);
            string Name(string id) => dx.List.diagnoses.First(d => d.id == id).dsm5tr_name;
            tabBody.Add(Para("Primary: " + (dx.Primary == null ? "(none)" : Name(dx.Primary))));
            tabBody.Add(Para("Differentials (up to 3): " + (dx.Differentials.Count == 0 ? "(none)" : string.Join("; ", dx.Differentials.Select(Name)))));
            var sv = Scroll();
            foreach (var d in dx.Search(query))
            {
                var r = Row();
                var l = Text($"{d.dsm5tr_name}  [ICD-11 {d.icd11}]", 15, Color.white);
                l.style.flexShrink = 1; l.style.whiteSpace = WhiteSpace.Normal;
                r.Add(l); r.Add(Spacer());
                var id = d.id;
                r.Add(Button("Primary", () => { dx.SetPrimary(id); OpenTab("Diagnosis"); }, 13));
                r.Add(dx.Differentials.Contains(id) ? Button("Remove", () => dx.RemoveDifferential(id), 13) : Button("Differential", () => dx.AddDifferential(id), 13));
                sv.Add(r);
            }
        }

        void RxTab()
        {
            var pad = encounter.Rx;
            tabBody.Add(Para("Formulary drugs only. Doses in this draft formulary are not yet verified by faculty.", Warn));
            var drugs = pad.Formulary.drugs;
            var drug = new DropdownField("Drug", drugs.Select(d => d.name).ToList(), 0);
            var route = new DropdownField("Route", drugs[0].routes, 0);
            drug.RegisterValueChangedCallback(e => { route.choices = drugs[drug.index].routes; route.index = 0; });
            var dose = new TextField("Dose (mg)");
            var freq = new TextField("Frequency") { value = "once daily" };
            var dur = new TextField("Duration") { value = "4 weeks" };
            var reason = new TextField("Reason");
            foreach (var f in new VisualElement[] { drug, route, dose, freq, dur, reason }) tabBody.Add(f);
            var error = Para("", Bad);
            tabBody.Add(Button("Add to prescription", () =>
            {
                try
                {
                    float? mg = float.TryParse(dose.value, NumberStyles.Float, CultureInfo.InvariantCulture, out var v) ? v : null;
                    Ui(() => pad.Add(new RxItem { drug = drugs[drug.index].id, route = route.value, dose_mg = mg, frequency = freq.value, duration = dur.value, reason = reason.value }));
                    OpenTab("Prescription");
                }
                catch (ArgumentException ex) { error.text = ex.Message; }
            }, 16));
            tabBody.Add(error);
            tabBody.Add(Heading("Prescription"));
            for (int i = 0; i < pad.Items.Count; i++)
            {
                var it = pad.Items[i];
                var r = Row();
                var l = Text($"{drugs.First(d => d.id == it.drug).name} {it.dose_mg?.ToString(CultureInfo.InvariantCulture) ?? "?"} mg {it.route}, {it.frequency}, {it.duration}" + (string.IsNullOrEmpty(it.reason) ? "" : $" ({it.reason})"), 15, Color.white);
                l.style.flexShrink = 1; l.style.whiteSpace = WhiteSpace.Normal;
                r.Add(l); r.Add(Spacer());
                int idx = i;
                r.Add(Button("Remove", () => pad.RemoveAt(idx), 13));
                tabBody.Add(r);
            }
        }

        void DispoTab()
        {
            var sv = Scroll();
            foreach (var d in encounter.Disposition.List.dispositions)
            {
                var t = new Toggle(d.name) { value = encounter.Disposition.Selected.Contains(d.id) };
                t.style.fontSize = 16; t.labelElement.style.color = Color.white;
                var id = d.id;
                t.RegisterValueChangedCallback(e => Ui(() => encounter.Disposition.Set(id, e.newValue)));
                sv.Add(t);
                sv.Add(Para(d.description + "  Basis: " + d.mhca_basis));
            }
        }

        void FinishTab()
        {
            tabBody.Add(Para("Submitting ends the station and shows your score. Check your MSE notes, diagnosis, prescription and disposition first."));
            tabBody.Add(Button("Submit and end station", () => encounter.Submit(), 18));
        }

        void Ui(Action a) { uiEdit = true; try { a(); } finally { uiEdit = false; } }

        // ---------------------------------------------------------------- small element helpers

        VisualElement Overlay(float width)
        {
            overlay?.RemoveFromHierarchy();   // re-rendering a card (start screen choices) replaces it
            overlay = new VisualElement();
            overlay.style.position = Position.Absolute;
            overlay.style.left = overlay.style.right = overlay.style.top = overlay.style.bottom = 0;
            overlay.style.backgroundColor = new Color(0, 0, 0, 0.55f);
            overlay.style.alignItems = Align.Center; overlay.style.justifyContent = Justify.Center;
            var card = Box(Card);
            card.style.width = width;
            card.style.paddingLeft = card.style.paddingRight = card.style.paddingTop = card.style.paddingBottom = 28;
            overlay.Add(card);
            root.Add(overlay);
            return card;
        }

        static VisualElement Box(Color c) { var v = new VisualElement(); v.style.backgroundColor = c; return v; }
        static VisualElement Row() { var v = new VisualElement(); v.style.flexDirection = FlexDirection.Row; v.style.alignItems = Align.Center; v.style.marginBottom = 4; return v; }
        static VisualElement Spacer() { var v = new VisualElement(); v.style.flexGrow = 1; return v; }
        ScrollView Scroll() { var s = new ScrollView(); s.style.flexGrow = 1; tabBody.Add(s); return s; }

        static Label Text(string t, int size, Color c, bool bold = false)
        {
            var l = new Label(t);
            l.style.fontSize = size; l.style.color = c;
            if (bold) l.style.unityFontStyleAndWeight = FontStyle.Bold;
            return l;
        }

        static Label Heading(string t) { var l = Text(t, 19, Accent, true); l.style.marginTop = 12; return l; }
        static Label Para(string t, Color? c = null) { var l = Text(t, 15, c ?? new Color(0.85f, 0.88f, 0.92f)); l.style.whiteSpace = WhiteSpace.Normal; l.style.marginBottom = 4; return l; }

        static Label Banner(string t)
        {
            var l = Text(t, 18, Color.black, true);
            l.style.backgroundColor = Warn;
            l.style.paddingLeft = l.style.paddingRight = 10; l.style.paddingTop = l.style.paddingBottom = 4;
            l.style.marginTop = 8; l.style.marginBottom = 8;
            return l;
        }

        static Button Button(string t, Action onClick, int size)
        {
            var b = new Button(onClick) { text = t };
            b.style.fontSize = size;
            return b;
        }
    }
}
