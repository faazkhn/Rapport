using UnityEngine;
using UnityEngine.Animations.Rigging;

namespace Rapport.Cues
{
    /// <summary>
    /// Head + eye gaze with Animation Rigging Multi-Aim (built at runtime so any CC3 patient works).
    /// gaze_avoid intensity = share of time spent looking away (floor, or down to the side). Looks back when the doctor speaks.
    /// The eyes have their own target: they lead the head on a gaze shift and make small saccades (eyes, mouth) while fixating.
    /// Also adds Breathing to the patient.
    /// </summary>
    public class GazeController : MonoBehaviour
    {
        public float AvoidShare;
        public float CornerShare;        // internal_stimuli (Stage 2): looks at the bare corner
        public float MoodAvoid;          // BodyLanguage: more looking away with shame, sadness or low trust, less with trust (-0.3..0.7)
        public float Pace = 1f;          // BodyLanguage: < 1 = quicker glances (anxious), > 1 = slower (sad)
        public bool Thinking;
        public float RigWeight;          // 0 during the entrance, 1 when seated
        public Transform Override;       // an exam gaze target (follow_finger) wins over everything else
        public Transform LookTarget { get; private set; }

        Transform doctor, corner, body;
        Rig rig;
        Vector3 target, vel;
        float nextSwitch, forceDoctorUntil;
        bool away;

        public void Setup(Animator anim, Transform doctorFace, Transform cornerTarget)
        {
            doctor = doctorFace; corner = cornerTarget; body = anim.transform;
            LookTarget = new GameObject("PatientLookTarget").transform;
            LookTarget.position = target = doctor.position;
            eyeTarget = new GameObject("PatientEyeTarget").transform;
            eyeTarget.position = eyePos = doctor.position;

            var rigGo = new GameObject("GazeRig");
            rigGo.transform.SetParent(anim.transform, false);
            rig = rigGo.AddComponent<Rig>();
            var head = anim.GetBoneTransform(HumanBodyBones.Head);
            AddAim(rigGo, "NeckAim", anim.GetBoneTransform(HumanBodyBones.Neck), 0.25f, 30f, LookTarget);
            AddAim(rigGo, "HeadAim", head, 0.55f, 45f, LookTarget);
            AddAim(rigGo, "EyeAimL", anim.GetBoneTransform(HumanBodyBones.LeftEye), 1f, 25f, eyeTarget);
            AddAim(rigGo, "EyeAimR", anim.GetBoneTransform(HumanBodyBones.RightEye), 1f, 25f, eyeTarget);
            if (!anim.TryGetComponent(out RigBuilder builder)) builder = anim.gameObject.AddComponent<RigBuilder>();  // not ??: Unity fake-null
            builder.layers.Clear();
            builder.layers.Add(new RigLayer(rig, true));
            builder.Build();
            rig.weight = 0;
            if (!anim.TryGetComponent<Breathing>(out _)) anim.gameObject.AddComponent<Breathing>().Setup(anim);
        }

        void AddAim(GameObject parent, string name, Transform bone, float weight, float limit, Transform source)
        {
            if (bone == null) return;
            var go = new GameObject(name);
            go.transform.SetParent(parent.transform, false);
            var c = go.AddComponent<MultiAimConstraint>();
            c.weight = weight;
            var d = c.data;
            d.constrainedObject = bone;
            d.aimAxis = AxisClosestTo(bone, body.forward);  // CC3 bone axes differ per bone; pick from the rest pose
            d.upAxis = AxisClosestTo(bone, Vector3.up);
            d.worldUpType = MultiAimConstraintData.WorldUpType.None;
            d.limits = new Vector2(-limit, limit);
            var src = new WeightedTransformArray { new WeightedTransform(source, 1f) };
            d.sourceObjects = src;
            d.maintainOffset = false;
            c.data = d;
        }

        static MultiAimConstraintData.Axis AxisClosestTo(Transform bone, Vector3 world)
        {
            var axes = new[] { (bone.right, MultiAimConstraintData.Axis.X), (-bone.right, MultiAimConstraintData.Axis.X_NEG), (bone.up, MultiAimConstraintData.Axis.Y),
                (-bone.up, MultiAimConstraintData.Axis.Y_NEG), (bone.forward, MultiAimConstraintData.Axis.Z), (-bone.forward, MultiAimConstraintData.Axis.Z_NEG) };
            var best = axes[0];
            foreach (var a in axes) if (Vector3.Dot(a.Item1, world) > Vector3.Dot(best.Item1, world)) best = a;
            return best.Item2;
        }

        /// <summary>Called when the doctor starts a line: look at them briefly, however avoidant.</summary>
        public void LookAtDoctor(float seconds) { forceDoctorUntil = Time.time + seconds; away = false; }

        void Update()
        {
            if (rig == null) return;
            rig.weight = Mathf.MoveTowards(rig.weight, RigWeight, Time.deltaTime * 1.5f);
            if (Thinking && !wasThinking) nextSwitch = 0f;  // between the doctor's line and the reply: look off at once
            wasThinking = Thinking;
            if (Time.time > nextSwitch)
            {
                float avoid = Mathf.Clamp01(AvoidShare + MoodAvoid);
                away = Random.value < avoid + CornerShare;
                cornerNow = away && Random.value * (avoid + CornerShare) < CornerShare;
                nextSwitch = Time.time + Pace * (away ? Random.Range(1.5f, 4f) : Random.Range(1.5f, 4.5f) * (1.2f - avoid));
                floorPoint = body.position + body.forward * Random.Range(0.9f, 1.4f) + body.right * Random.Range(-0.5f, 0.5f);
                // thinking: the eyes wander up and to the side, a new spot each switch
                thinkPoint = body.position + body.forward * 1.5f + body.right * Random.Range(-0.9f, 0.9f) + Vector3.up * Random.Range(0.9f, 1.7f);
                if (Thinking) nextSwitch = Time.time + Random.Range(0.7f, 1.6f);
            }
            Vector3 goal = Override ? Override.position
                : Time.time < forceDoctorUntil ? doctor.position
                : away && cornerNow ? corner.position
                : Thinking ? thinkPoint
                : away ? floorPoint : doctor.position;
            target = Vector3.SmoothDamp(target, goal, ref vel, 0.18f);
            LookTarget.position = target;

            if (Time.time > nextSaccade || (goal - lastGoal).sqrMagnitude > 0.04f)  // a new fixation, or a gaze shift (the eyes jump first)
            {
                var d = goal - body.position; d.y = 0f;
                var side = Vector3.Cross(Vector3.up, d.normalized);
                saccade = Override ? Vector3.zero : side * Random.Range(-0.03f, 0.03f) + Vector3.up * Random.Range(-0.04f, 0.015f);  // eyes to mouth, ~1-2°
                nextSaccade = Time.time + SaccadeGap(Random.value);
            }
            lastGoal = goal;
            eyePos = Vector3.SmoothDamp(eyePos, goal + saccade, ref eyeVel, 0.03f);
            eyeTarget.position = eyePos;
        }

        /// <summary>Seconds a fixation lasts: mostly 0.3-1 s, now and then up to 2.5 s.</summary>
        public static float SaccadeGap(float u) => 0.3f + 2.2f * u * u * u;

        Transform eyeTarget;
        Vector3 eyePos, eyeVel, saccade, lastGoal;
        float nextSaccade;
        Vector3 floorPoint, thinkPoint;
        bool cornerNow, wasThinking;

        void OnDestroy() { if (LookTarget) Destroy(LookTarget.gameObject); if (eyeTarget) Destroy(eyeTarget.gameObject); }
    }
}
