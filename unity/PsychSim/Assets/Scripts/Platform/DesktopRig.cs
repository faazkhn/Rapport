using UnityEngine;
using UnityEngine.InputSystem;

namespace PsychSim.Platform
{
    /// <summary>
    /// Desktop doctor camera at DoctorAnchor. Hold the right mouse button to look around (limited), via InputSystem_Actions only.
    /// Follow (set by EncounterManager to the patient's head) keeps the patient in the free area left of the tablet panel, eyes in the
    /// upper third, until the user looks around. With Cinemachine (CameraDirector) it steers Target, the doctor's virtual camera.
    /// </summary>
    public class DesktopRig : MonoBehaviour
    {
        [SerializeField] InputActionAsset actions;
        [SerializeField] float sensitivity = 0.08f;
        [SerializeField] Vector2 yawLimit = new(-70f, 70f), pitchLimit = new(-35f, 30f);
        [SerializeField] float followYawOffset = 17f;   // puts the followed target about a third from the left, clear of the side panel
        [SerializeField] float followPitchOffset = 7f;  // one sixth of the 42° FOV: the patient's eyes sit in the upper third
        public Transform Follow;
        public Transform Target;                        // what it rotates; defaults to its own transform
        InputAction look, hold;
        Quaternion baseRot;
        float yaw, pitch;

        void Awake()
        {
            look = actions.FindAction("Player/Look", true);
            hold = actions.FindAction("UI/RightClick", true);
            if (!Target) Target = transform;
            baseRot = Target.localRotation;
        }

        void OnEnable() { look.Enable(); hold.Enable(); }
        void OnDisable() { look.Disable(); hold.Disable(); }

        void Update()
        {
            if (hold.ReadValue<float>() < 0.5f)
            {
                if (Follow)
                {
                    var want = Quaternion.LookRotation(Follow.position - Target.position) * Quaternion.Euler(followPitchOffset, followYawOffset, 0f);
                    Target.rotation = Quaternion.Slerp(Target.rotation, want, 1f - Mathf.Exp(-Time.deltaTime * 3f));
                }
                return;
            }
            if (Follow) { Follow = null; baseRot = Target.localRotation; yaw = pitch = 0f; }  // the user takes over
            var d = look.ReadValue<Vector2>() * sensitivity;
            yaw = Mathf.Clamp(yaw + d.x, yawLimit.x, yawLimit.y);
            pitch = Mathf.Clamp(pitch - d.y, pitchLimit.x, pitchLimit.y);
            Target.localRotation = baseRot * Quaternion.Euler(pitch, yaw, 0f);
        }
    }
}
