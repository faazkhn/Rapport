using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Threading.Tasks;
using Newtonsoft.Json.Linq;
using Rapport.Cues;
using Rapport.Data;
using Rapport.Logging;
using Rapport.Patient;
using Rapport.Scoring;
using Rapport.Speech;
using Rapport.Tools;
using UnityEngine;

namespace Rapport.Core
{
    public enum Phase { Start, Brief, Enter, Active, Debrief }
    public enum Mode { Practice, Assessment }

    /// <summary>
    /// Start (case, patient sex, mode) -> Brief (prebrief) -> Enter -> Active -> Debrief. Owns the session clock, the patient state, the
    /// voice session (server/patient-service/PROTOCOL.md), the tool controllers and the SessionLog. Interview/examine/assess/plan are not
    /// locked steps inside Active. Public methods double as the demo-video hooks.
    /// </summary>
    public class EncounterManager : MonoBehaviour
    {
        [SerializeField] string caseId = "mdd_01";
        [SerializeField] ServiceSettings settings;
        [SerializeField] GameObject[] patientPrefabs;     // matched to the variant's model_id by name
        [SerializeField] TextAsset[] facePresets;
        [SerializeField] uLipSync.Profile lipSyncProfile;
        [SerializeField] AudioSource doctorVoice;
        [SerializeField] Rapport.Platform.DesktopRig desktopRig;

        public Phase Phase { get; private set; }
        public Mode Mode { get; private set; }
        public event Action<Phase> PhaseChanged;
        public event Action<string, string> Subtitle;      // (speaker "doctor" | "patient", text); empty text clears
        public event Action<PatientTurn> PatientReplied;
        public event Action<string, float> CueFired;
        public event Action<string> FactRevealed;
        public event Action<ScoreResult> Scored;

        public ContentData Data { get; private set; }
        public CaseFile Case { get; private set; }
        public PatientState State { get; private set; }
        public IntentLedger Ledger { get; private set; }
        public SessionLog Log { get; private set; }
        public MsePanel Mse { get; private set; }
        public DiagnosisPicker Dx { get; private set; }
        public PrescriptionPad Rx { get; private set; }
        public DispositionSelector Disposition { get; private set; }
        public ScoreResult Score { get; private set; }
        public VoiceSession Voice { get; private set; }
        public readonly List<string> RevealedFacts = new();
        public readonly List<TurnRecord> Turns = new();
        public float SessionSeconds { get; private set; }
        public float TimeLimitSeconds => (Case.time_limit_min ?? 15f) * 60f;
        public bool Busy => Voice != null && (Voice.State == VoiceState.Thinking || Voice.State == VoiceState.Speaking);
        public Animator Patient { get; private set; }
        public ExamController Exam { get; private set; }
        Platform.CameraDirector cameraDirector;
        public CueDriver Cues { get; private set; }
        public long LastLatencyMs { get; private set; } = -1;
        [field: NonSerialized] public string ServiceError { get; private set; }
        /// <summary>false: the real microphone is not opened; only InjectMicAudio feeds the mic path (demo take, play-mode tests).</summary>
        [NonSerialized] public bool UseMicrophone = true;

        PatientServiceClient http;
        GazeController gaze;
        LipSyncBridge lips;
        Room room;
        float driftAccum, stateSyncAccum, turnStart;
        string pendingDoctor;
        int repliesSeen;
        bool lastReplyBarged;

        void Awake()
        {
            Data = CaseLoader.LoadAll(Path.Combine(Application.streamingAssetsPath, "data"), releaseBuild: !Debug.isDebugBuild);
            if (!Data.cases.ContainsKey(caseId)) caseId = Data.cases.Keys.FirstOrDefault() ?? throw new ContentException("no cases (or none approved in a release build)");
            Case = CaseVariants.Resolve(Data.cases[caseId], "female");
            Mse = new MsePanel(Data.cues);
            Dx = new DiagnosisPicker(Data.diagnoses);
            Rx = new PrescriptionPad(Data.formulary);
            Disposition = new DispositionSelector(Data.dispositions);
            http = new PatientServiceClient(settings);
            room = Room.Find();
            if (desktopRig)
            {
                cameraDirector = desktopRig.gameObject.AddComponent<Platform.CameraDirector>();
                cameraDirector.Setup(desktopRig.GetComponent<Camera>(), desktopRig);
            }
        }

        void Start() => SetPhase(Phase.Start);

        void SetPhase(Phase p)
        {
            Phase = p;
            Log?.Write("phase", new { phase = p.ToString() });
            PhaseChanged?.Invoke(p);
        }

        /// <summary>Start screen: case, then the patient's sex (DESIGN 6.1 variants), then Practice or Assessment. Shows the prebrief.</summary>
        public void Configure(string caseId, string variant, Mode mode)
        {
            if (Phase != Phase.Start) return;
            Case = CaseVariants.Resolve(Data.cases[caseId], variant);
            Mode = mode;
            SetPhase(Phase.Brief);
        }

        /// <summary>Brief -> Enter: starts the session, spawns the patient, connects the voice loop and plays the entrance; Active follows.</summary>
        public void BeginEncounter()
        {
            if (Phase != Phase.Brief) return;
            State = new PatientState(Case.state_start);
            Ledger = new IntentLedger();
            Log = new SessionLog(Application.persistentDataPath, Case.id, () => SessionSeconds);
            Log.Write("session_start", new { case_id = Case.id, case_version = Case.version, case_status = Case.status, variant = Case.variant, mode = Mode.ToString(), state = State.Snapshot() });
            Action<string, string> logTool = (kind, id) => Log.Write("tool", new { action = kind, id });
            Mse.Changed += logTool; Dx.Changed += logTool; Rx.Changed += logTool; Disposition.Changed += logTool;
            SetPhase(Phase.Enter);
            StartCoroutine(Enter());
        }

        IEnumerator Enter()
        {
            SpawnPatient();
            var connect = ConnectVoice();   // the service warms the model's cache for this case while the patient walks in
            if (!room.SoundSourceDoor.TryGetComponent(out AudioSource doorAudio)) doorAudio = room.SoundSourceDoor.gameObject.AddComponent<AudioSource>();  // not ??: Unity fake-null
            yield return EntranceSequence.Run(Patient, Cues, gaze, room, doorAudio);
            while (!connect.IsCompleted) yield return null;
            if (Voice.Connected) Voice.SetHandsFree(true);   // off during the entrance so door and footsteps are not heard as speech
            SetPhase(Phase.Active);
        }

        async Task ConnectVoice()
        {
            Voice = gameObject.AddComponent<VoiceSession>();
            Voice.UseMicrophone = UseMicrophone;
            Voice.Setup(lips.Source);
            Voice.Event += OnVoiceEvent;
            Voice.SentenceStarted += OnSentence;
            Voice.Stopped += () => Log.Write("barge_in");
            try
            {
                await Voice.Connect(settings.baseUrl, new JObject
                {
                    ["case_id"] = Case.id, ["variant"] = Case.variant, ["state"] = JObject.FromObject(State.Snapshot()), ["hands_free"] = false, ["vad_silence_ms"] = settings.vadSilenceMs,
                });
            }
            catch (Exception e)
            {
                ServiceError = $"Cannot reach the patient service at {settings.baseUrl} ({e.GetBaseException().Message}). Start it with server/patient-service/run.sh.";
                Log.Write("service_error", new { error = e.GetBaseException().Message });
                Debug.LogError("PsychSim: " + ServiceError);
            }
        }

        void SpawnPatient()
        {
            var prefab = patientPrefabs.FirstOrDefault(p => p.name == Case.patient.model_id)
                         ?? throw new MissingReferenceException($"no patient prefab named '{Case.patient.model_id}' on EncounterManager");
            var go = Instantiate(prefab, room.PatientSpawn.position, room.PatientSpawn.rotation);
            go.name = "Patient_" + Case.patient.model_id;
            Patient = go.GetComponent<Animator>();
            Patient.applyRootMotion = false;
            if (desktopRig) desktopRig.Follow = Patient.GetBoneTransform(HumanBodyBones.Head);
            gaze = go.AddComponent<GazeController>();
            gaze.Setup(Patient, room.DoctorAnchor, room.CornerLookTarget);
            var tremor = go.AddComponent<TremorController>();
            tremor.Setup(Patient);
            var mats = go.AddComponent<MaterialCueController>();
            mats.Setup(go.transform);
            var face = go.AddComponent<FacePresets>();
            face.Setup(go.transform, facePresets);
            lips = go.AddComponent<LipSyncBridge>();
            lips.Setup(Patient, lipSyncProfile);
            Cues = go.AddComponent<CueDriver>();
            Cues.Init(Case, State, () => SessionSeconds / 60f, Patient, gaze, tremor, mats, face);
            Cues.CueFired += (id, v) => { Log.Write("cue_fired", new { id, intensity = Math.Round(v, 2) }); CueFired?.Invoke(id, v); };
            Cues.CueChanged += (id, v) => Log.Write("cue", new { id, intensity = Math.Round(v, 2) });
            Exam = go.AddComponent<ExamController>();
            Exam.Setup(Patient, Cues, gaze, face, room.DoctorAnchor);
            Exam.ExamStarted += id => { Log.Write("exam_started", new { id }); if (cameraDirector) cameraDirector.OnExamStarted(id, Patient); };
            Exam.ExamEnded += id => { Log.Write("exam_ended", new { id }); if (cameraDirector) cameraDirector.OnExamEnded(id); };
        }

        void Update()
        {
            if (Phase != Phase.Active) return;
            SessionSeconds += Time.deltaTime;
            driftAccum += Time.deltaTime;
            stateSyncAccum += Time.deltaTime;
            if (driftAccum >= 1f)  // drift once a second; SessionLog snapshots every 30 s
            {
                State.Drift(Case.state_drift_per_min, driftAccum / 60f, Data.stateRules.range);
                driftAccum = 0f;
                if ((int)SessionSeconds % 30 == 0) Log.Write("state", State.Snapshot());
            }
            if (stateSyncAccum >= 5f && !Busy && Voice != null) { stateSyncAccum = 0f; _ = Voice.SendState(State.Snapshot()); }  // drift reaches the fact gate
            gaze.Thinking = Voice != null && Voice.State == VoiceState.Thinking;
            if (Mode == Mode.Assessment && SessionSeconds >= TimeLimitSeconds && !Busy) { Log.Write("timeout"); Submit(); }  // D4: hard stop
        }

        // ---------------------------------------------------------------- voice events

        void OnVoiceEvent(JObject o)
        {
            switch ((string)o["type"])
            {
                case "transcript":
                    var text = (string)o["text"];
                    if (string.IsNullOrWhiteSpace(text)) break;
                    pendingDoctor = text;
                    turnStart = SessionSeconds;
                    Subtitle?.Invoke("doctor", text);
                    gaze.LookAtDoctor(1.5f);
                    break;
                case "reply": OnReply(o); break;
                case "exam": Exam.Receive(o); Log.Write("exam", o); break;
                case "brain_snapshot": Log.Write("brain_snapshot", o); break;
                case "timing":
                    if (o["audio_start_ms"]?.Type == JTokenType.Integer) LastLatencyMs = (long)o["audio_start_ms"];
                    Log.Write("timing", o);
                    break;
                case "error": Log.Write("service_error", new { error = (string)o["error"] }); break;
            }
        }

        string patientSoFar = "";

        /// <summary>Live subtitle: the patient's words so far, sentence by sentence as each one starts playing.</summary>
        void OnSentence(int index, string text)
        {
            patientSoFar = index == 0 ? text : patientSoFar + " " + text;
            Subtitle?.Invoke("patient", patientSoFar);
            Cues.OnSpeechStarted(text, Mathf.Clamp(text.Length / 14f, 1f, 8f));
        }

        void OnReply(JObject o)
        {
            var raw = o["reply"].ToObject<PatientReply>();
            var dropped = new List<string>();
            var reply = GuardCheck.Clean(raw, Case, Data.intents, State.Trust, dropped) ?? new PatientReply { utterance = "", emotion = "neutral" };
            var before = State.Snapshot();
            State.Set(o["state"].ToObject<Dictionary<string, float>>());
            var turn = new PatientTurn { doctorLine = pendingDoctor, reply = reply, dropped = dropped, fallback = o["meta"]?["fallback"]?.Value<bool>() == true,
                                         stateAfter = State.Snapshot() };
            turn.stateApplied = PatientState.Keys.ToDictionary(k => k, k => turn.stateAfter[k] - before[k]);
            Turns.Add(new TurnRecord { t = turnStart, doctor = pendingDoctor, patient = reply.utterance, intents = reply.doctor_intents.ToList(),
                                       revealed = reply.revealed_fact_ids.ToList(), trustBefore = before["trust"], trustAfter = State.Trust });
            lastReplyBarged = o["meta"]?["barge_in"]?.Value<bool>() == true;
            repliesSeen++;
            Ledger.Add(reply.doctor_intents, SessionSeconds);
            foreach (var f in reply.revealed_fact_ids.Where(f => !RevealedFacts.Contains(f)))
            {
                RevealedFacts.Add(f);
                Log.Write("fact_revealed", new { id = f });
                FactRevealed?.Invoke(f);
            }
            Cues.OnPatientReplied(turn);
            Log.Write("turn", new
            {
                doctor = pendingDoctor, patient = reply.utterance, reply.emotion, reply.doctor_intents, reply.revealed_fact_ids, reply.event_cues, reply.exam_action,
                turn.fallback, dropped, state = turn.stateAfter, meta = o["meta"],
            });
            PatientReplied?.Invoke(turn);
        }

        // ---------------------------------------------------------------- doctor input

        /// <summary>Typed fallback (and a test hook): sends one line over the voice session. Completes when the patient has finished speaking.</summary>
        public async Task SubmitDoctorLine(string text)
        {
            text = text?.Trim();
            if (Phase != Phase.Active || string.IsNullOrEmpty(text) || Voice == null || !Voice.Connected) return;
            int seen = repliesSeen;
            await Voice.SendText(text);
            await WaitForReply(seen);
        }

        /// <summary>
        /// Demo hook: synthesises the line in the doctor's KittenTTS voice, plays it in the room and feeds the same audio, resampled to
        /// 16 kHz, into the microphone path (VAD -> STT -> LLM -> TTS on the service). Completes when the patient has finished replying.
        /// </summary>
        public async Task SpeakDoctorIntoMic(string text)
        {
            if (Phase != Phase.Active || Voice == null || !Voice.Connected) return;
            var clip = await http.Speak(text, settings.doctorVoice, 1.0f);
            var data = new float[clip.samples * clip.channels];
            clip.GetData(data, 0);
            data = CapPauses(data, clip.frequency, 0.25f);   // TTS leaves long gaps between sentences; a person speaking one turn does not
            clip = AudioClip.Create("doctor_line", data.Length, 1, clip.frequency, false);
            clip.SetData(data, 0);
            int seen = repliesSeen;
            if (doctorVoice) { doctorVoice.clip = clip; doctorVoice.Play(); }
            Voice.InjectMicAudio(VoiceSession.Resample(data, clip.frequency, VoiceSession.InRate));
            await WaitForReply(seen);
        }

        /// <summary>Shortens every silence longer than maxGap seconds (|x| below 1% for that long) to maxGap.</summary>
        public static float[] CapPauses(float[] x, int rate, float maxGap)
        {
            int cap = (int)(maxGap * rate), run = 0;
            var o = new List<float>(x.Length);
            foreach (var v in x)
            {
                run = Mathf.Abs(v) < 0.01f ? run + 1 : 0;
                if (run <= cap) o.Add(v);
            }
            return o.ToArray();
        }

        async Task WaitForReply(int seen)
        {
            float t0 = Time.realtimeSinceStartup;
            while (repliesSeen == seen && Time.realtimeSinceStartup - t0 < 60f) await Awaitable.NextFrameAsync();
            while (lastReplyBarged && Time.realtimeSinceStartup - t0 < 60f) { seen = repliesSeen; while (repliesSeen == seen && Time.realtimeSinceStartup - t0 < 60f) await Awaitable.NextFrameAsync(); }
            while (Voice.State == VoiceState.Speaking || Voice.State == VoiceState.Thinking) await Awaitable.NextFrameAsync();
        }

        /// <summary>Ends the station (learner submits, or the Assessment timer runs out) and scores it.</summary>
        public ScoreResult Submit()
        {
            if (Phase != Phase.Active) return Score;
            if (Voice != null) Voice.SetHandsFree(false);
            Score = ScoringEngine.Score(new ScoreInput
            {
                caseFile = Case, data = Data, ledger = Ledger, mseCues = new HashSet<string>(Mse.Ticked), primaryDx = Dx.Primary,
                differentials = Dx.Differentials.ToList(), rx = Rx.Items.ToList(), dispositions = Disposition.Selected.ToList(), finalTrust = State.Trust,
                turns = Turns.ToList(),
            });
            Log.Write("mse", new { ticked = Mse.Ticked.OrderBy(x => x), notes = Mse.Notes });
            Log.Write("score", Score);
            SetPhase(Phase.Debrief);
            Scored?.Invoke(Score);
            return Score;
        }
    }
}
