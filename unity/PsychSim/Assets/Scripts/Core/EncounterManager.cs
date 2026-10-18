using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Threading.Tasks;
using PsychSim.Cues;
using PsychSim.Data;
using PsychSim.Logging;
using PsychSim.Patient;
using PsychSim.Scoring;
using PsychSim.Speech;
using PsychSim.Tools;
using UnityEngine;

namespace PsychSim.Core
{
    public enum Phase { Brief, Enter, Active, Debrief }

    /// <summary>
    /// Brief -> Enter -> Active -> Debrief. Owns the session clock, the patient brain and state, the tool controllers and the SessionLog.
    /// Interview/examine/assess/plan are not locked steps inside Active. Public methods double as the demo-video hooks.
    /// </summary>
    public class EncounterManager : MonoBehaviour
    {
        [SerializeField] string caseId = "mdd_01";
        [SerializeField] ServiceSettings settings;
        [SerializeField] GameObject[] patientPrefabs;     // matched to the case's model_id by name
        [SerializeField] TextAsset[] facePresets;
        [SerializeField] uLipSync.Profile lipSyncProfile;
        [SerializeField] AudioSource doctorVoice;
        [SerializeField] PsychSim.Platform.DesktopRig desktopRig;

        public Phase Phase { get; private set; }
        public event Action<Phase> PhaseChanged;
        public event Action<string, string> Subtitle;      // (speaker "doctor" | "patient", text); empty text clears
        public event Action<PatientTurn> PatientReplied;
        public event Action<string, float> CueFired;
        public event Action<string> FactRevealed;
        public event Action<ScoreResult> Scored;

        public ContentData Data { get; private set; }
        public CaseFile Case { get; private set; }
        public PatientState State { get; private set; }
        public PatientBrain Brain { get; private set; }
        public IntentLedger Ledger { get; private set; }
        public SessionLog Log { get; private set; }
        public MsePanel Mse { get; private set; }
        public DiagnosisPicker Dx { get; private set; }
        public PrescriptionPad Rx { get; private set; }
        public DispositionSelector Disposition { get; private set; }
        public ScoreResult Score { get; private set; }
        public readonly List<string> RevealedFacts = new();
        public float SessionSeconds { get; private set; }
        public float TimeLimitSeconds => (Case.time_limit_min ?? 15f) * 60f;
        public bool Busy { get; private set; }
        public Animator Patient { get; private set; }
        public CueDriver Cues { get; private set; }

        /// <summary>Transports; default to the HTTP client. Tests swap in fakes before BeginEncounter.</summary>
        public IPatientService Service;
        public IVoice Voice;

        GazeController gaze;
        LipSyncBridge lips;
        Room room;
        float driftAccum;

        void Awake()
        {
            Data = CaseLoader.LoadAll(Path.Combine(Application.streamingAssetsPath, "data"), releaseBuild: !Debug.isDebugBuild);
            if (!Data.cases.TryGetValue(caseId, out var c)) throw new ContentException($"case '{caseId}' not found (or not approved in a release build)");
            Case = c;
            Mse = new MsePanel(Data.cues);
            Dx = new DiagnosisPicker(Data.diagnoses);
            Rx = new PrescriptionPad(Data.formulary);
            Disposition = new DispositionSelector(Data.dispositions);
            var client = new PatientServiceClient(settings);
            Service ??= client;
            Voice ??= client;
            room = Room.Find();
        }

        void Start() => SetPhase(Phase.Brief);

        void SetPhase(Phase p)
        {
            Phase = p;
            Log?.Write("phase", new { phase = p.ToString() });
            PhaseChanged?.Invoke(p);
        }

        /// <summary>Brief -> Enter: starts the session, spawns the patient and plays the entrance; Active follows automatically.</summary>
        public void BeginEncounter()
        {
            if (Phase != Phase.Brief) return;
            State = new PatientState(Case.state_start);
            Brain = new PatientBrain(Case, Data, State, Service) { Model = string.IsNullOrEmpty(settings.model) ? null : settings.model };
            Ledger = new IntentLedger();
            Log = new SessionLog(Application.persistentDataPath, Case.id, () => SessionSeconds);
            Log.Write("session_start", new { case_id = Case.id, case_version = Case.version, case_status = Case.status, state = State.Snapshot() });
            Brain.PatientReplied += OnReplied;
            Action<string, string> logTool = (kind, id) => Log.Write("tool", new { action = kind, id });
            Mse.Changed += logTool; Dx.Changed += logTool; Rx.Changed += logTool; Disposition.Changed += logTool;
            SetPhase(Phase.Enter);
            StartCoroutine(Enter());
        }

        IEnumerator Enter()
        {
            SpawnPatient();
            if (!room.SoundSourceDoor.TryGetComponent(out AudioSource doorAudio)) doorAudio = room.SoundSourceDoor.gameObject.AddComponent<AudioSource>();  // not ??: Unity fake-null
            yield return EntranceSequence.Run(Patient, Cues, gaze, room, doorAudio);
            SetPhase(Phase.Active);
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
        }

        void Update()
        {
            if (Phase != Phase.Active) return;
            SessionSeconds += Time.deltaTime;
            driftAccum += Time.deltaTime;
            if (driftAccum >= 1f)  // drift once a second; SessionLog snapshots every 30 s
            {
                State.Drift(Case.state_drift_per_min, driftAccum / 60f, Data.stateRules.range);
                driftAccum = 0f;
                if ((int)SessionSeconds % 30 == 0) Log.Write("state", State.Snapshot());
            }
            if (SessionSeconds >= TimeLimitSeconds && !Busy) { Log.Write("timeout"); Submit(); }
        }

        /// <summary>
        /// Demo hook and the chat box's entry point: one doctor line -> /reply -> GuardCheck -> state -> /tts -> lip-synced audio.
        /// Completes when the patient's audio has finished. speakAloud plays the line in the doctor voice first.
        /// </summary>
        public async Task<PatientTurn> SubmitDoctorLine(string text, bool speakAloud = false)
        {
            text = text?.Trim();
            if (Phase != Phase.Active || Busy || string.IsNullOrEmpty(text)) return null;
            Busy = true;
            try
            {
                if (speakAloud) await SpeakDoctor(text);
                else Subtitle?.Invoke("doctor", text);
                var start = Time.realtimeSinceStartup;
                gaze.LookAtDoctor(1.5f);
                gaze.Thinking = true;
                float slowed = Cues.Get("slowed");
                var turn = await Brain.Ask(text, SessionSeconds / 60f);
                float replyDone = Time.realtimeSinceStartup;
                AudioClip clip = null;
                try { clip = await Voice.Speak(turn.reply.utterance, Case.patient.voice_id, SpeechTiming.TtsSpeed(Case.patient.voice_speed, slowed)); }
                catch (Exception e) { Log.Write("tts_error", new { error = e.Message }); }
                float ttsMs = (Time.realtimeSinceStartup - replyDone) * 1000f;
                float wait = SpeechTiming.PreReplyDelay(slowed) - (Time.realtimeSinceStartup - start);
                if (wait > 0) await Awaitable.WaitForSecondsAsync(wait);
                gaze.Thinking = false;
                float totalMs = (Time.realtimeSinceStartup - start) * 1000f;

                Subtitle?.Invoke("patient", turn.reply.utterance);
                float seconds = clip ? clip.length : Mathf.Clamp(turn.reply.utterance.Length / 15f, 1.5f, 6f);  // reading time without audio
                Cues.OnSpeechStarted(turn.reply.utterance, seconds);
                Log.Write("turn", new
                {
                    doctor = text, patient = turn.reply.utterance, turn.reply.emotion, turn.reply.doctor_intents, turn.reply.revealed_fact_ids, turn.reply.event_cues,
                    turn.fallback, turn.dropped, state = turn.stateAfter, reply_ms = turn.replyMs, tts_ms = Math.Round(ttsMs), total_ms = Math.Round(totalMs),
                });
                if (clip)
                {
                    lips.Source.clip = clip;
                    lips.Source.Play();
                    while (lips.Source && lips.Source.isPlaying) await Awaitable.NextFrameAsync();
                }
                else await Awaitable.WaitForSecondsAsync(seconds);
                return turn;
            }
            finally { Busy = false; }
        }

        void OnReplied(PatientTurn turn)
        {
            Ledger.Add(turn.reply.doctor_intents, SessionSeconds);
            foreach (var f in turn.reply.revealed_fact_ids.Where(f => !RevealedFacts.Contains(f)))
            {
                RevealedFacts.Add(f);
                Log.Write("fact_revealed", new { id = f });
                FactRevealed?.Invoke(f);
            }
            Cues.OnPatientReplied(turn);
            PatientReplied?.Invoke(turn);
        }

        /// <summary>Demo hook: says a line in the doctor's voice (male KittenTTS voice from ServiceSettings) with its own subtitle.</summary>
        public async Task SpeakDoctor(string text)
        {
            Subtitle?.Invoke("doctor", text);
            AudioClip clip = null;
            try { clip = await Voice.Speak(text, settings.doctorVoice, 1.0f); }
            catch (Exception e) { Log?.Write("tts_error", new { error = e.Message }); }
            if (!clip || !doctorVoice) return;
            doctorVoice.clip = clip;
            doctorVoice.Play();
            while (doctorVoice.isPlaying) await Awaitable.NextFrameAsync();
        }

        /// <summary>Ends the station (learner submits, or time runs out) and scores it.</summary>
        public ScoreResult Submit()
        {
            if (Phase != Phase.Active) return Score;
            Score = ScoringEngine.Score(new ScoreInput
            {
                caseFile = Case, data = Data, ledger = Ledger, mseCues = new HashSet<string>(Mse.Ticked), primaryDx = Dx.Primary,
                differentials = Dx.Differentials.ToList(), rx = Rx.Items.ToList(), dispositions = Disposition.Selected.ToList(), finalTrust = State.Trust,
            });
            Log.Write("mse", new { ticked = Mse.Ticked.OrderBy(x => x), notes = Mse.Notes });
            Log.Write("score", Score);
            SetPhase(Phase.Debrief);
            Scored?.Invoke(Score);
            return Score;
        }
    }
}
