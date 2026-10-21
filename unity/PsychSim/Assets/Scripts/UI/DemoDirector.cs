using System;
using System.Collections;
using System.IO;
using System.Threading.Tasks;
using PsychSim.Core;
using PsychSim.Scoring;
using UnityEngine;
using UnityEngine.UIElements;

namespace PsychSim.UI
{
    /// <summary>
    /// Plays the demo take from demo/script.json with a live patient: start screen (both patients shown), prebrief, establishing shot,
    /// entrance, then each doctor line is synthesised in Dr. Faaz's voice and fed into the microphone path (VAD -> STT -> local LLM ->
    /// streamed TTS). Patient replies are generated live; nothing is pre-baked. Then MSE, diagnosis, prescription, disposition and the debrief.
    /// Variant "male" plays the short Arjun cut. Added at runtime by Rapport/Record Demo; raises Finished when the take is over.
    /// </summary>
    public class DemoDirector : MonoBehaviour
    {
        public static event Action Finished;
        public static string Variant = "female";
        public static string ScriptPath = "demo/script.json";   // demo/staged/script.json for the staged concept preview

        [Serializable] class Turn { public string doctor, shot; }
        [Serializable] class Rx { public string drug, route, frequency, duration, reason; }
        [Serializable] class Tools { public string[] mse, dispositions; public string primary_dx; public Rx rx; }
        [Serializable] class Script { public string case_id; public Turn[] turns, arjun_turns; public Tools tools; }

        EncounterManager em;
        EncounterUI ui;
        Camera doctorCam, demoCam;
        VisualElement uiRoot;
        Room room;

        IEnumerator Start()
        {
            var script = JsonUtility.FromJson<Script>(File.ReadAllText(Path.Combine(Application.dataPath, "../../../" + ScriptPath)));
            bool arjun = Variant == "male";
            PsychSim.Cues.CueDriver.WipeTears = !ScriptPath.Contains("staged");
            QualitySettings.vSyncCount = 0;
            Application.targetFrameRate = 60;   // uncapped editor rendering halves the local LLM's speed on the shared GPU
            em = FindAnyObjectByType<EncounterManager>();
            em.UseMicrophone = false;   // the doctor's voice comes from the synthesised lines, through the same mic path
            ui = FindAnyObjectByType<EncounterUI>();
            room = Room.Find();
            uiRoot = ui.GetComponent<UIDocument>().rootVisualElement;
            em.PatientReplied += t => { if (t.reply.exam_action == "hold_out_hands") StartCoroutine(HandsCloseUp()); };
            doctorCam = Camera.main;
            demoCam = new GameObject("DemoCam").AddComponent<Camera>();
            demoCam.nearClipPlane = 0.05f;
            demoCam.enabled = false;
            var data = doctorCam.GetComponent<UnityEngine.Rendering.Universal.UniversalAdditionalCameraData>();
            if (data) { var d2 = demoCam.gameObject.AddComponent<UnityEngine.Rendering.Universal.UniversalAdditionalCameraData>(); d2.renderPostProcessing = data.renderPostProcessing; d2.antialiasing = data.antialiasing; }

            // shot 2: start screen, both patient options, pick one
            yield return new WaitUntil(() => em.Phase == Phase.Start);
            yield return new WaitForSeconds(arjun ? 1.0f : 2.0f);
            ui.SelectVariant(arjun ? "female" : "male");
            yield return new WaitForSeconds(arjun ? 0.5f : 1.3f);
            ui.SelectVariant(arjun ? "male" : "female");
            yield return new WaitForSeconds(arjun ? 1.0f : 1.5f);
            em.Configure(script.case_id, Variant, Mode.Practice);
            yield return new WaitForSeconds(arjun ? 1.0f : 3.5f);      // prebrief

            // shot 3: establishing; shot 4: door opens, the patient walks in and sits
            em.BeginEncounter();
            ShowUi(false);
            var door = room.Door.position;
            var pa = room.PatientAnchor.position;
            Establishing();
            yield return new WaitForSeconds(arjun ? 1.5f : 3.0f);
            Cut(Vector3.Lerp(pa, room.DoctorAnchor.position, 0.35f) + Vector3.up * 1.55f + (pa - door).normalized * 0.4f, door + Vector3.up, 50f);
            while (em.Phase == Phase.Enter)
            {
                var head = em.Patient.GetBoneTransform(HumanBodyBones.Head).position;
                demoCam.transform.rotation = Quaternion.Slerp(demoCam.transform.rotation,
                    Quaternion.LookRotation(head + Vector3.down * 0.25f - demoCam.transform.position), 1f - Mathf.Exp(-Time.deltaTime * 2.5f));
                yield return null;
            }
            if (!string.IsNullOrEmpty(em.ServiceError)) { Debug.LogError("PsychSim demo: " + em.ServiceError); Finished?.Invoke(); yield break; }
            yield return new WaitForSeconds(1.2f);

            // shots 5-8: the interview, Dr. Faaz speaking through the mic path
            foreach (var t in arjun ? script.arjun_turns : script.turns)
            {
                Shot(t.shot);
                yield return Wait(em.SpeakDoctorIntoMic(t.doctor));
                yield return new WaitForSeconds(0.5f);
            }
            if (arjun) { yield return new WaitForSeconds(1f); Finished?.Invoke(); yield break; }

            // shot 9: the tablet
            Pov();
            yield return new WaitForSeconds(0.8f);
            var tools = script.tools;
            ui.OpenTab("MSE");
            yield return new WaitForSeconds(0.8f);
            foreach (var c in tools.mse) { em.Mse.SetTick(c, true); yield return new WaitForSeconds(0.3f); }
            yield return new WaitForSeconds(1.0f);
            ui.OpenTab("Diagnosis");
            yield return new WaitForSeconds(0.8f);
            em.Dx.SetPrimary(tools.primary_dx);
            yield return new WaitForSeconds(1.5f);
            ui.OpenTab("Prescription");
            yield return new WaitForSeconds(0.8f);
            em.Rx.Add(new RxItem { drug = tools.rx.drug, route = tools.rx.route, frequency = tools.rx.frequency, duration = tools.rx.duration, reason = tools.rx.reason });
            yield return new WaitForSeconds(2.0f);
            ui.OpenTab("Disposition");
            yield return new WaitForSeconds(0.8f);
            foreach (var d in tools.dispositions) { em.Disposition.Set(d, true); yield return new WaitForSeconds(0.5f); }
            yield return new WaitForSeconds(1.2f);

            // shot 10: debrief (side by side, risk-first score, quoted feedback), scrolled slowly
            em.Submit();
            yield return new WaitForSeconds(4f);
            ScrollView sv = null;
            foreach (var s in uiRoot.Query<ScrollView>().ToList()) if (s.contentContainer.childCount > 10) sv = s;
            if (sv != null)
                for (float k = 0; k < 1f; k += Time.deltaTime / 8f)
                {
                    sv.scrollOffset = new Vector2(0, Mathf.SmoothStep(0, 1, k) * Mathf.Max(0, sv.contentContainer.layout.height - sv.layout.height));
                    yield return null;
                }
            yield return new WaitForSeconds(2f);
            Finished?.Invoke();
        }

        static IEnumerator Wait(Task t) { while (!t.IsCompleted) yield return null; if (t.IsFaulted) Debug.LogException(t.Exception); }

        void ShowUi(bool on) => uiRoot.style.display = on ? DisplayStyle.Flex : DisplayStyle.None;

        int shotNo;

        void Shot(string shot)
        {
            shotNo++;
            switch (shot)
            {
                case "close": CloseUp(); break;
                case "hands": Hands(); break;
                case "pov": Pov(); break;
                default: OverShoulder(); break;
            }
        }

        void Cut(Vector3 pos, Vector3 lookAt, float fov)
        {
            demoCam.transform.SetPositionAndRotation(pos, Quaternion.LookRotation(lookAt - pos));
            demoCam.fieldOfView = fov;
            doctorCam.enabled = false;
            demoCam.enabled = true;
        }

        void Pov()
        {
            demoCam.enabled = false;
            doctorCam.enabled = true;
            ShowUi(true);
        }

        Vector3 Head => em.Patient.GetBoneTransform(HumanBodyBones.Head).position;
        Vector3 ToDoctor { get { var d = doctorCam.transform.position - Head; d.y = 0; return d.normalized; } }

        /// <summary>Wide shot from the room's far corner: doctor's desk, the patient's chair and the door in one frame.</summary>
        void Establishing()
        {
            var pa = room.PatientAnchor.position; var da = room.DoctorAnchor.position; var door = room.Door.position;
            var centre = (pa + da + door) / 3f;
            var away = (centre - door); away.y = 0;
            var side = Vector3.Cross(Vector3.up, away.normalized);
            var pos = centre + away.normalized * 2.4f + side * 0.6f + Vector3.up * 2.0f;
            Cut(pos, centre + Vector3.up * 0.7f, 62f);
        }

        /// <summary>Behind the doctor's shoulder toward the patient; the tablet panel and subtitles stay visible.</summary>
        void OverShoulder()
        {
            var right = Vector3.Cross(Vector3.up, -ToDoctor);
            var pos = doctorCam.transform.position + ToDoctor * 0.35f - right * 0.3f + Vector3.up * 0.05f;
            Cut(pos, Head + Vector3.down * 0.15f, 34f);
            demoCam.transform.Rotate(0f, 6f, 0f, Space.World);   // patient left of centre, clear of the side panel
            ShowUi(true);
        }

        /// <summary>Tight shot of the patient's face from the doctor's side, framed left of the tablet panel.</summary>
        void CloseUp()
        {
            var head = Head + Vector3.down * 0.02f;
            var pos = head + ToDoctor * 1.0f + Vector3.down * 0.16f;   // below eye level: her head is bowed (slumped, gaze avoidance)
            Cut(pos, head, 30f);
            demoCam.transform.Rotate(0f, 8f, 0f, Space.World);
            ShowUi(true);
        }

        /// <summary>When the patient holds out her hands: wait for the arms to rise, ease to a close-up of both hands, track them until the next shot.</summary>
        IEnumerator HandsCloseUp()
        {
            int mine = shotNo;
            yield return new WaitForSeconds(0.9f);
            Transform l = em.Patient.GetBoneTransform(HumanBodyBones.LeftHand), r = em.Patient.GetBoneTransform(HumanBodyBones.RightHand);
            Vector3 p0 = demoCam.transform.position; Quaternion q0 = demoCam.transform.rotation; float f0 = demoCam.fieldOfView;
            for (float k = 0; mine == shotNo; k += Time.deltaTime / 1.4f)
            {
                var hands = (l.position + r.position) / 2f;
                var pos = hands + ToDoctor * 0.75f + Vector3.up * 0.18f;
                float e = Mathf.SmoothStep(0, 1, Mathf.Clamp01(k));
                demoCam.transform.SetPositionAndRotation(Vector3.Lerp(p0, pos, e), Quaternion.Slerp(q0, Quaternion.LookRotation(hands - pos), e));
                demoCam.fieldOfView = Mathf.Lerp(f0, 34f, e);
                yield return null;
            }
        }

        /// <summary>Medium shot for the hands exam: head to knees.</summary>
        void Hands()
        {
            var chest = em.Patient.GetBoneTransform(HumanBodyBones.Chest).position;
            var pos = chest + ToDoctor * 1.6f + Vector3.up * 0.1f;
            Cut(pos, chest + Vector3.down * 0.12f, 40f);
            demoCam.transform.Rotate(0f, 9f, 0f, Space.World);
            ShowUi(true);
        }
    }
}
