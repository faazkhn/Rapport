using System;
using System.Collections.Generic;
using System.Linq;
using Newtonsoft.Json.Linq;

namespace PsychSim.Cues
{
    public class ExamStep
    {
        public string id;
        public string which = "both";
        public string palms = "down";
    }

    /// <summary>
    /// Order and timing of exam actions the service routed (Phase H), with no Unity calls so it is testable. Actions run one at a time in
    /// order. Held actions (hands out, sleeves, light, mouth) stay until relax, a new command, or 30 s. Posture comes first when needed:
    /// sleeves or forearms while standing sit down first, a walk while seated stands up first. ExamController plays what Started reports
    /// and tells Tick when the current motion has finished.
    /// </summary>
    public class ExamQueue
    {
        public const float HoldCapS = 30f;
        public static readonly HashSet<string> SeatedOnly = new() { "roll_up_sleeves", "show_forearms" };
        public static readonly HashSet<string> Held = new() { "hold_out_hands", "roll_up_sleeves", "show_forearms", "look_at_light", "open_mouth", "stick_out_tongue" };

        public event Action<ExamStep> Started, Ended;
        public ExamStep Current { get; private set; }
        public bool Holding { get; private set; }
        public bool Standing { get; private set; }

        readonly LinkedList<ExamStep> pending = new();
        float holdStart;

        /// <summary>Steps the patient agreed to (comply true), in order; relax is set when the doctor said to stop.</summary>
        public static List<ExamStep> Parse(JObject msg, out bool relax)
        {
            relax = msg["relax"]?.Value<bool>() == true;
            return (msg["actions"] as JArray ?? new JArray()).OfType<JObject>().Where(a => a["comply"]?.Value<bool>() == true)
                .Select(a => new ExamStep { id = (string)a["id"], which = (string)a["slots"]?["which"] ?? "both", palms = (string)a["slots"]?["palms"] ?? "down" })
                .ToList();
        }

        public void Enqueue(IEnumerable<ExamStep> steps)
        {
            if (Current != null && Holding) Finish();  // a new command releases the hold
            foreach (var s in steps) pending.AddLast(s);
        }

        /// <summary>Ends the current held action, whether it is still moving or already holding. Posture changes are not interrupted.</summary>
        public void Relax()
        {
            if (Current != null && Held.Contains(Current.id)) Finish();
        }

        /// <summary>motionDone: the current action's movement (clip, IK reach, posture change) has finished.</summary>
        public void Tick(float now, bool motionDone)
        {
            if (Current != null)
            {
                if (Holding && now - holdStart >= HoldCapS) Finish();
                else if (motionDone && !Holding)
                {
                    if (Held.Contains(Current.id)) { Holding = true; holdStart = now; }
                    else
                    {
                        if (Current.id == "stand_up") Standing = true;
                        else if (Current.id == "sit_down") Standing = false;
                        Finish();
                    }
                }
            }
            if (Current == null && pending.Count > 0) Start();
        }

        void Start()
        {
            var next = pending.First.Value;
            if (SeatedOnly.Contains(next.id) && Standing) next = new ExamStep { id = "sit_down" };
            else if (next.id == "walk_few_steps" && !Standing) next = new ExamStep { id = "stand_up" };
            else pending.RemoveFirst();
            Current = next;
            Holding = false;
            Started?.Invoke(next);
        }

        void Finish()
        {
            var done = Current;
            Current = null;
            Holding = false;
            Ended?.Invoke(done);
        }
    }
}
