using System.Collections;
using System.Linq;
using Rapport.Cues;
using UnityEngine;

namespace Rapport.Core
{
    /// <summary>
    /// Enter phase: door opens, patient walks in from PatientSpawn to ChairApproach (walk_in root motion, steered), turns,
    /// sits (sit_down, which lands on the seat when started at PatientAnchor), looks at the doctor, door closes.
    /// Without the clips it falls back to a lerp so the flow still works; real clips are picked up automatically.
    /// </summary>
    public static class EntranceSequence
    {
        public const float DoorOpenDeg = -100f;

        public static IEnumerator Run(Animator anim, CueDriver cues, GazeController gaze, Room room, AudioSource doorAudio)
        {
            var t = anim.transform;
            if (!anim.TryGetComponent(out RootMotionMover mover)) mover = anim.gameObject.AddComponent<RootMotionMover>();  // not ??: Unity fake-null
            t.SetPositionAndRotation(room.PatientSpawn.position, room.PatientSpawn.rotation);
            bool hasWalk = cues.HasClip("walk_in"), hasSit = cues.HasClip("sit_down");
            anim.speed = 0f;  // stand still on walk_in frame 0 while the door opens
            if (hasWalk) { anim.Play("walk_in", 0, 0f); anim.Update(0f); }

            doorAudio.clip = DoorClip();
            doorAudio.Play();
            yield return Door(room.Door, 0f, DoorOpenDeg, 1.2f);

            var goal = room.ChairApproach.position;
            goal.y = t.position.y;
            if (hasWalk)
            {
                var clip = anim.runtimeAnimatorController.animationClips.First(c => c.name == "walk_in");
                float clipDist = clip.averageSpeed.magnitude * clip.length;
                float pathDist = Vector3.Distance(t.position, goal);
                // stride scaling within +-25% keeps the feet believable; any leftover is closed with a short step below
                mover.Scale = clipDist > 0.01f ? Mathf.Clamp(pathDist / clipDist, 0.75f, 1.25f) : 1f;
                mover.Target = goal;
                anim.applyRootMotion = true;
                anim.speed = 1f;
                while (anim.GetCurrentAnimatorStateInfo(0).IsName("walk_in") && anim.GetCurrentAnimatorStateInfo(0).normalizedTime < 1f
                       && Flat(goal - t.position).magnitude > 0.03f)
                    yield return null;
                anim.applyRootMotion = false;
                mover.Target = null;
            }
            yield return Slide(t, goal, hasWalk ? 0.5f : 1.0f);   // idle-step for any leftover (or the whole path without a walk clip)

            // turn in place to face away from the seat
            var from = t.rotation;
            for (float s = 0; s < 1f; s += Time.deltaTime / 0.9f) { t.rotation = Quaternion.Slerp(from, room.PatientAnchor.rotation, Smooth(s)); yield return null; }
            t.SetPositionAndRotation(room.PatientAnchor.position, room.PatientAnchor.rotation);

            anim.speed = 1f;
            if (hasSit)
            {
                anim.CrossFade("sit_down", 0.25f, 0, 0f);
                yield return null;
                yield return new WaitUntil(() => anim.GetCurrentAnimatorStateInfo(0).IsName("Seated"));
            }
            else
            {
                anim.CrossFade("Seated", 1f, 0);
                yield return new WaitForSeconds(1f);
            }

            cues.Seated = true;
            gaze.RigWeight = 1f;
            gaze.LookAtDoctor(2.5f);
            doorAudio.Play();
            yield return Door(room.Door, DoorOpenDeg, 0f, 1.4f);
        }

        static IEnumerator Door(Transform door, float from, float to, float seconds)
        {
            for (float s = 0; s < 1f; s += Time.deltaTime / seconds)
            {
                door.localRotation = Quaternion.Euler(0f, Mathf.Lerp(from, to, Smooth(s)), 0f);
                yield return null;
            }
            door.localRotation = Quaternion.Euler(0f, to, 0f);
        }

        static IEnumerator Slide(Transform t, Vector3 goal, float speed)
        {
            while (Flat(goal - t.position).magnitude > 0.005f)
            {
                var d = Flat(goal - t.position);
                if (d.magnitude > 0.2f) t.rotation = Quaternion.RotateTowards(t.rotation, Quaternion.LookRotation(d), 180f * Time.deltaTime);
                t.position = Vector3.MoveTowards(t.position, goal, speed * Time.deltaTime);
                yield return null;
            }
        }

        static Vector3 Flat(Vector3 v) { v.y = 0; return v; }
        static float Smooth(float s) { s = Mathf.Clamp01(s); return s * s * (3f - 2f * s); }

        /// <summary>Placeholder door sound (latch click + short creak) until real audio arrives.</summary>
        static AudioClip DoorClip()
        {
            const int rate = 24000;
            var data = new float[rate * 7 / 10];
            var rng = new System.Random(7);
            for (int i = 0; i < data.Length; i++)
            {
                float t = i / (float)rate;
                float click = t < 0.03f ? (float)(rng.NextDouble() * 2 - 1) * (1 - t / 0.03f) : 0f;
                float creak = t > 0.08f ? Mathf.Sin(2 * Mathf.PI * (180f + 60f * Mathf.Sin(t * 23f)) * t) * 0.18f * Mathf.Exp(-(t - 0.08f) * 4f) : 0f;
                data[i] = (click * 0.6f + creak) * 0.5f;
            }
            var clip = AudioClip.Create("door_placeholder", data.Length, 1, rate, false);
            clip.SetData(data, 0);
            return clip;
        }
    }

    /// <summary>Applies walk_in root motion (scaled) while steering toward a target. Does nothing when root motion is off.</summary>
    [RequireComponent(typeof(Animator))]
    public class RootMotionMover : MonoBehaviour
    {
        [System.NonSerialized] public Vector3? Target;
        public float Scale = 1f;
        public float TurnDegPerSec = 90f;
        Animator anim;

        void Awake() { anim = GetComponent<Animator>(); }

        void OnAnimatorMove()
        {
            if (!anim.applyRootMotion) return;
            var d = anim.deltaPosition * Scale;
            d.y = 0f;
            if (Target is Vector3 goal)
            {
                var to = goal - transform.position; to.y = 0f;
                if (to.magnitude > 0.3f)
                    transform.rotation = Quaternion.RotateTowards(transform.rotation, Quaternion.LookRotation(to), TurnDegPerSec * Time.deltaTime);
                if (d.magnitude > to.magnitude) d = d.normalized * to.magnitude;  // don't overshoot
            }
            transform.position += d;
        }
    }
}
