using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;
using System.Threading.Tasks;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using Rapport.Data;

namespace Rapport.Patient
{
    /// <summary>Transport for /reply. PatientServiceClient implements it over HTTP; tests use an in-process fake.</summary>
    public interface IPatientService
    {
        Task<string> Reply(string requestJson);
    }

    public class PatientTurn
    {
        public string doctorLine;
        public PatientReply reply;
        public bool fallback;
        public List<string> dropped = new();
        public Dictionary<string, float> stateApplied, stateAfter;
        public long replyMs;
    }

    /// <summary>One learner turn: build the request, call /reply, GuardCheck, retry once, fall back, apply state, publish PatientReplied.</summary>
    public class PatientBrain
    {
        public const int HistoryMessages = 20;
        public event Action<PatientTurn> PatientReplied;
        public readonly List<(string role, string text)> History = new();
        public readonly PatientState State;
        public string Model;  // null = service default; the tester can switch to grok-4.7

        readonly CaseFile caseFile;
        readonly ContentData data;
        readonly IPatientService service;
        readonly FallbackLines fallback;

        public PatientBrain(CaseFile c, ContentData d, PatientState state, IPatientService service)
        {
            caseFile = c; data = d; State = state; this.service = service;
            fallback = new FallbackLines(c.fallback_lines);
        }

        public async Task<PatientTurn> Ask(string doctorLine, float elapsedMin)
        {
            History.Add(("doctor", doctorLine));
            var turn = new PatientTurn { doctorLine = doctorLine };
            var req = new JObject
            {
                ["case_id"] = caseFile.id,
                ["messages"] = new JArray(History.Skip(Math.Max(0, History.Count - HistoryMessages)).Select(m => new JObject { ["role"] = m.role, ["text"] = m.text })),
                ["state"] = JObject.FromObject(State.Snapshot()),
                ["elapsed_min"] = Math.Round(elapsedMin, 1),
            };
            if (!string.IsNullOrEmpty(Model)) req["model"] = Model;

            var sw = Stopwatch.StartNew();
            for (int attempt = 0; attempt < 2 && turn.reply == null; attempt++)
            {
                try
                {
                    var raw = JsonConvert.DeserializeObject<PatientReply>(await service.Reply(req.ToString(Formatting.None)));
                    turn.reply = GuardCheck.Clean(raw, caseFile, data.intents, State.Trust, turn.dropped);
                    if (raw?.meta?["fallback"]?.Value<bool>() == true) turn.fallback = true;
                }
                catch (Exception e) when (e is not OperationCanceledException)
                {
                    turn.dropped.Add($"attempt {attempt + 1}: {e.GetType().Name}: {e.Message}");
                }
            }
            turn.replyMs = sw.ElapsedMilliseconds;
            if (turn.reply == null)
            {
                turn.fallback = true;
                turn.reply = new PatientReply { utterance = fallback.Next(), emotion = "confused", state_delta = PatientState.Keys.ToDictionary(k => k, _ => 0) };
            }

            turn.stateApplied = State.ApplyTurn(turn.reply.state_delta, turn.reply.doctor_intents, data.stateRules);
            turn.stateAfter = State.Snapshot();
            History.Add(("patient", turn.reply.utterance));
            PatientReplied?.Invoke(turn);
            return turn;
        }
    }
}
