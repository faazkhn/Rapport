using System.Collections.Generic;
using Unity.Cinemachine;
using UnityEngine;
using UnityEngine.InputSystem;

namespace PsychSim.Platform
{
    /// <summary>
    /// The doctor's view through Cinemachine (Phase H), built at runtime so the scene needs no rebuild:
    /// - the doctor camera: seated eye height, 42° vertical FOV, steered by DesktopRig;
    /// - lean in with the scroll wheel over the room (Space is push-to-talk);
    /// - one close-up camera, placed each frame on the body part of the running exam action, eased in and out by the Brain.
    /// DemoDirector keeps its own separate cinematic camera.
    /// </summary>
    public class CameraDirector : MonoBehaviour
    {
        public class Shot
        {
            public HumanBodyBones[] bones;  // the close-up looks at their midpoint
            public float distance;          // from the target toward the doctor; 0 = from the doctor's seat (full body)
            public float fov;
        }

        public const float DoctorFov = 42f, LeanFov = 38f, LeanDistance = 0.25f;
        static readonly Shot Hands = new() { bones = new[] { HumanBodyBones.LeftHand, HumanBodyBones.RightHand }, distance = 0.85f, fov = 32f };
        static readonly Shot Forearms = new() { bones = new[] { HumanBodyBones.LeftLowerArm, HumanBodyBones.RightLowerArm }, distance = 0.9f, fov = 34f };
        static readonly Shot Eyes = new() { bones = new[] { HumanBodyBones.LeftEye, HumanBodyBones.RightEye }, distance = 0.45f, fov = 22f };
        static readonly Shot Face = new() { bones = new[] { HumanBodyBones.Jaw, HumanBodyBones.Head }, distance = 0.5f, fov = 24f };
        static readonly Shot FullBody = new() { bones = new[] { HumanBodyBones.Hips, HumanBodyBones.Head }, distance = 0f, fov = 70f };  // the room is ~1.1 m deep: wide, from the doctor
        static readonly Dictionary<string, Shot> Shots = new()
        {
            ["hold_out_hands"] = Hands, ["roll_up_sleeves"] = Forearms, ["show_forearms"] = Forearms,
            ["look_at_light"] = Eyes, ["follow_finger"] = Eyes, ["open_mouth"] = Face, ["stick_out_tongue"] = Face,
            ["stand_up"] = FullBody, ["sit_down"] = FullBody, ["walk_few_steps"] = FullBody,
        };

        public static Shot ShotFor(string examId) => examId != null && Shots.TryGetValue(examId, out var s) ? s : null;

        CinemachineCamera doctorCam, closeCam;
        Transform doctorView;
        Animator patient;
        Shot active, pending;
        float pendingAt, dropAt = -1f, lean, leanTarget;
        Vector3 viewHome;
        float aspect = 16f / 9f;

        public void Setup(Camera cam, DesktopRig rig)
        {
            if (!cam.TryGetComponent(out CinemachineBrain brain)) brain = cam.gameObject.AddComponent<CinemachineBrain>();
            brain.DefaultBlend = new CinemachineBlendDefinition(CinemachineBlendDefinition.Styles.EaseInOut, 0.6f);
            doctorView = new GameObject("DoctorView").transform;
            doctorView.SetParent(cam.transform.parent, false);
            doctorView.SetLocalPositionAndRotation(cam.transform.localPosition, cam.transform.localRotation);
            viewHome = doctorView.localPosition;
            aspect = cam.aspect;
            rig.Target = doctorView;
            doctorCam = doctorView.gameObject.AddComponent<CinemachineCamera>();
            doctorCam.Priority = 10;
            doctorCam.Lens = Lens(cam, DoctorFov);
            closeCam = new GameObject("ExamCloseUp").AddComponent<CinemachineCamera>();
            closeCam.Priority = 0;
            closeCam.Lens = Lens(cam, 30f);
        }

        static LensSettings Lens(Camera cam, float fov)
        {
            var l = LensSettings.FromCamera(cam);
            l.FieldOfView = fov;
            return l;
        }

        /// <summary>Cuts to the action's close-up if it is still running 0.3 s later (a no-op "have a seat" while seated never cuts).</summary>
        public void OnExamStarted(string id, Animator who)
        {
            var s = ShotFor(id);
            if (s == null) return;
            patient = who;
            pending = s;
            pendingAt = Time.time + 0.3f;
        }

        public void OnExamEnded(string id)
        {
            if (ShotFor(id) == null) return;
            if (pending != null) pending = null;
            else if (active != null) dropAt = Time.time + 0.5f;
        }

        void LateUpdate()
        {
            if (doctorView == null) return;
            var mouse = Mouse.current;
            if (mouse != null && mouse.position.ReadValue().x < Screen.width * 0.62f)  // not over the side panel, which scrolls
            {
                float sc = mouse.scroll.ReadValue().y;
                if (sc > 0f) leanTarget = 1f;
                else if (sc < 0f) leanTarget = 0f;
            }
            lean = Mathf.MoveTowards(lean, leanTarget, Time.deltaTime / 0.4f);
            float e = Mathf.SmoothStep(0f, 1f, lean);
            var fwd = doctorView.forward;
            fwd.y = 0f;
            doctorView.localPosition = viewHome + (doctorView.parent ? doctorView.parent.InverseTransformDirection(fwd.normalized) : fwd.normalized) * (LeanDistance * e);
            doctorCam.Lens.FieldOfView = Mathf.Lerp(DoctorFov, LeanFov, e);

            if (pending != null && Time.time >= pendingAt)
            {
                active = pending;
                pending = null;
                dropAt = -1f;
                closeCam.Lens.FieldOfView = active.fov;
                closeCam.Priority = 20;
            }
            if (dropAt > 0f && Time.time >= dropAt)
            {
                closeCam.Priority = 0;
                active = null;
                dropAt = -1f;
            }
            if (active != null && patient) PlaceCloseUp();
        }

        void PlaceCloseUp()
        {
            Vector3 target = Vector3.zero;
            int n = 0;
            foreach (var b in active.bones)
            {
                var t = patient.GetBoneTransform(b);
                if (t) { target += t.position; n++; }
            }
            if (n == 0) return;
            target /= n;
            Vector3 pos;
            if (active.distance <= 0f) pos = doctorView.position;
            else
            {
                var toDoc = doctorView.position - target;
                toDoc.y = 0f;
                pos = target + toDoc.normalized * active.distance + Vector3.up * 0.08f;
            }
            // turn so the target sits left of centre, clear of the side panel (as DesktopRig does for the doctor view)
            float yaw = Mathf.Atan(0.35f * Mathf.Tan(active.fov * 0.5f * Mathf.Deg2Rad) * aspect) * Mathf.Rad2Deg;
            closeCam.transform.SetPositionAndRotation(pos, Quaternion.LookRotation(target - pos) * Quaternion.Euler(0f, yaw, 0f));
        }
    }
}
