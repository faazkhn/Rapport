using UnityEngine;

namespace Rapport.Cues
{
    /// <summary>
    /// Quiet breathing on top of any clip: the chest lifts and the shoulders rise a little with each breath (about 14 a minute at rest,
    /// faster with Rate). Applied after the Animator in LateUpdate, so it works on every clip and body.
    /// </summary>
    [DefaultExecutionOrder(800)]
    public class Breathing : MonoBehaviour
    {
        public float Rate = 14f;          // breaths per minute; a cue can raise it (anxiety)
        public float Depth = 1f;
        Transform body, chest, upperChest, lClav, rClav;
        float phase;

        public void Setup(Animator anim)
        {
            body = anim.transform;
            chest = anim.GetBoneTransform(HumanBodyBones.Chest);
            upperChest = anim.GetBoneTransform(HumanBodyBones.UpperChest);
            lClav = anim.GetBoneTransform(HumanBodyBones.LeftShoulder);
            rClav = anim.GetBoneTransform(HumanBodyBones.RightShoulder);
            phase = Random.value;
        }

        /// <summary>Inhale 0-1 at a breath phase 0-1: a quicker in-breath (40%) and a slower out-breath.</summary>
        public static float Inhale(float phase)
        {
            phase -= Mathf.Floor(phase);
            return phase < 0.4f ? Mathf.SmoothStep(0f, 1f, phase / 0.4f) : Mathf.SmoothStep(1f, 0f, (phase - 0.4f) / 0.6f);
        }

        void LateUpdate() => Step(Time.deltaTime);

        public void Step(float dt)
        {
            if (!body) return;
            phase += dt * Rate / 60f;
            float a = Inhale(phase) * Depth;
            var back = Quaternion.AngleAxis(-0.8f * a, body.right);  // the chest tips back a touch as it fills
            if (chest) chest.rotation = back * chest.rotation;
            if (upperChest) upperChest.rotation = back * upperChest.rotation;
            // shoulders rise: each clavicle turns about the body's forward axis, outward ends up
            if (lClav) lClav.rotation = Quaternion.AngleAxis(-1.2f * a, body.forward) * lClav.rotation;
            if (rClav) rClav.rotation = Quaternion.AngleAxis(1.2f * a, body.forward) * rClav.rotation;
        }
    }
}
