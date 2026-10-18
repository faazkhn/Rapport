using UnityEngine;
using UnityEngine.Animations.Rigging;

namespace PsychSim.Cues
{
    /// <summary>
    /// Head + eye gaze with Animation Rigging Multi-Aim (built at runtime so any CC3 patient works).
    /// gaze_avoid intensity = share of time spent looking away (floor, or down to the side). Looks back when the doctor speaks.
    /// </summary>
    public class GazeController : MonoBehaviour
    {
        public float AvoidShare;
        public float CornerShare;        // internal_stimuli (Stage 2): looks at the bare corner
        public bool Thinking;
        public float RigWeight;          // 0 during the entrance, 1 when seated
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

            var rigGo = new GameObject("GazeRig");
            rigGo.transform.SetParent(anim.transform, false);
            rig = rigGo.AddComponent<Rig>();
            var head = anim.GetBoneTransform(HumanBodyBones.Head);
            AddAim(rigGo, "NeckAim", anim.GetBoneTransform(HumanBodyBones.Neck), 0.25f, 30f);
            AddAim(rigGo, "HeadAim", head, 0.55f, 45f);
            AddAim(rigGo, "EyeAimL", anim.GetBoneTransform(HumanBodyBones.LeftEye), 1f, 25f);
            AddAim(rigGo, "EyeAimR", anim.GetBoneTransform(HumanBodyBones.RightEye), 1f, 25f);
            if (!anim.TryGetComponent(out RigBuilder builder)) builder = anim.gameObject.AddComponent<RigBuilder>();  // not ??: Unity fake-null
            builder.layers.Clear();
            builder.layers.Add(new RigLayer(rig, true));
            builder.Build();
            rig.weight = 0;
        }

        void AddAim(GameObject parent, string name, Transform bone, float weight, float limit)
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
            var src = new WeightedTransformArray { new WeightedTransform(LookTarget, 1f) };
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
            if (Time.time > nextSwitch)
            {
                away = Random.value < AvoidShare + CornerShare;
                cornerNow = away && Random.value * (AvoidShare + CornerShare) < CornerShare;
                nextSwitch = Time.time + (away ? Random.Range(1.5f, 4f) : Random.Range(1.5f, 4.5f) * (1.2f - AvoidShare));
                floorPoint = body.position + body.forward * Random.Range(0.9f, 1.4f) + body.right * Random.Range(-0.5f, 0.5f);
            }
            Vector3 goal = Time.time < forceDoctorUntil ? doctor.position
                : away && cornerNow ? corner.position
                : Thinking ? body.position + body.forward * 1.5f + body.right * 0.6f + Vector3.up * 0.4f
                : away ? floorPoint : doctor.position;
            target = Vector3.SmoothDamp(target, goal, ref vel, 0.18f);
            LookTarget.position = target;
        }

        Vector3 floorPoint;
        bool cornerNow;

        void OnDestroy() { if (LookTarget) Destroy(LookTarget.gameObject); }
    }
}
