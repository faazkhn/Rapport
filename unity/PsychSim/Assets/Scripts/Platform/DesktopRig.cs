using UnityEngine;
using UnityEngine.InputSystem;

namespace PsychSim.Platform
{
    /// <summary>
    /// Desktop doctor camera at DoctorAnchor. Hold the right mouse button to look around (limited), via InputSystem_Actions only.
    /// Follow (set by EncounterManager to the patient's head) keeps the patient in the free area left of the tablet panel until the user looks around.
    /// </summary>
    public class DesktopRig : MonoBehaviour
    {
        [SerializeField] InputActionAsset actions;
        [SerializeField] float sensitivity = 0.08f;
        [SerializeField] Vector2 yawLimit = new(-70f, 70f), pitchLimit = new(-35f, 30f);
        [SerializeField] float followYawOffset = 17f;   // puts the followed target about a third from the left, clear of the side panel
        public Transform Follow;
        InputAction look, hold;
        Quaternion baseRot;
        float yaw, pitch;

        void Awake()
        {
            look = actions.FindAction("Player/Look", true);
            hold = actions.FindAction("UI/RightClick", true);
            baseRot = transform.localRotation;
        }

        void OnEnable() { look.Enable(); hold.Enable(); }
        void OnDisable() { look.Disable(); hold.Disable(); }

        void Update()
        {
            if (hold.ReadValue<float>() < 0.5f)
            {
                if (Follow)
                {
                    var want = Quaternion.LookRotation(Follow.position - transform.position) * Quaternion.Euler(0f, followYawOffset, 0f);
                    transform.rotation = Quaternion.Slerp(transform.rotation, want, 1f - Mathf.Exp(-Time.deltaTime * 3f));
                }
                return;
            }
            if (Follow) { Follow = null; baseRot = transform.localRotation; yaw = pitch = 0f; }  // the user takes over
            var d = look.ReadValue<Vector2>() * sensitivity;
            yaw = Mathf.Clamp(yaw + d.x, yawLimit.x, yawLimit.y);
            pitch = Mathf.Clamp(pitch - d.y, pitchLimit.x, pitchLimit.y);
            transform.localRotation = baseRot * Quaternion.Euler(pitch, yaw, 0f);
        }
    }
}
