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
    /// Plays the staged demo take from demo/script.json: brief card, entrance (tracking shot), doctor lines spoken aloud with
    /// patient replies, close-ups on the turns marked "close", then MSE, diagnosis, prescription, disposition and the score screen.
    /// Added at runtime by the editor's PsychSim/Record Demo menu; raises Finished when the take is over.
    /// </summary>
    public class DemoDirector : MonoBehaviour
    {
        public static event Action Finished;

        [Serializable] class Turn { public string doctor, shot; }
        [Serializable] class Rx { public string drug, route, frequency, duration, reason; }
        [Serializable] class Tools { public string[] mse, dispositions; public string primary_dx; public Rx rx; }
        [Serializable] class Script { public Turn[] turns; public Tools tools; }

        EncounterManager em;
        EncounterUI ui;
        Camera doctorCam, demoCam;
        VisualElement uiRoot;

        IEnumerator Start()
        {
            var script = JsonUtility.FromJson<Script>(File.ReadAllText(Path.Combine(Application.dataPath, "../../../demo/script.json")));
            em = FindFirstObjectByType<EncounterManager>();
            ui = FindFirstObjectByType<EncounterUI>();
            uiRoot = ui.GetComponent<UIDocument>().rootVisualElement;
            doctorCam = Camera.main;
            demoCam = new GameObject("DemoCam").AddComponent<Camera>();
            demoCam.nearClipPlane = 0.05f;
            demoCam.enabled = false;

            yield return new WaitUntil(() => em.Phase == Phase.Brief);
            yield return new WaitForSeconds(3f);                       // brief card with the draft banner
            em.BeginEncounter();
            ShowUi(false);
            var door = GameObject.Find("Door").transform.position;
            Cut(new Vector3(1.2f, 1.6f, 1.25f), door + Vector3.up, 50f);   // sofa corner looking at the door
            while (em.Phase == Phase.Enter)
            {
                var head = em.Patient.GetBoneTransform(HumanBodyBones.Head).position;
                demoCam.transform.rotation = Quaternion.Slerp(demoCam.transform.rotation,
                    Quaternion.LookRotation(head + Vector3.down * 0.25f - demoCam.transform.position), 1f - Mathf.Exp(-Time.deltaTime * 2.5f));
                yield return null;
            }
            yield return new WaitForSeconds(1.5f);
            Pov();

            foreach (var t in script.turns)
            {
                if (t.shot == "close") CloseUp(); else Pov();
                yield return Wait(em.SubmitDoctorLine(t.doctor, speakAloud: true));
                yield return new WaitForSeconds(0.6f);
            }
            Pov();
            yield return new WaitForSeconds(1f);

            var tools = script.tools;
            ui.OpenTab("MSE");
            yield return new WaitForSeconds(1f);
            foreach (var c in tools.mse) { em.Mse.SetTick(c, true); yield return new WaitForSeconds(0.35f); }
            yield return new WaitForSeconds(1.5f);
            ui.OpenTab("Diagnosis");
            yield return new WaitForSeconds(1f);
            em.Dx.SetPrimary(tools.primary_dx);
            yield return new WaitForSeconds(2f);
            ui.OpenTab("Prescription");
            yield return new WaitForSeconds(1f);
            em.Rx.Add(new RxItem { drug = tools.rx.drug, route = tools.rx.route, frequency = tools.rx.frequency, duration = tools.rx.duration, reason = tools.rx.reason });
            yield return new WaitForSeconds(2.5f);
            ui.OpenTab("Disposition");
            yield return new WaitForSeconds(1f);
            foreach (var d in tools.dispositions) { em.Disposition.Set(d, true); yield return new WaitForSeconds(0.6f); }
            yield return new WaitForSeconds(2f);
            em.Submit();
            yield return new WaitForSeconds(8f);                       // score and debrief screen
            Finished?.Invoke();
        }

        static IEnumerator Wait(Task t) { while (!t.IsCompleted) yield return null; }

        void ShowUi(bool on) => uiRoot.style.display = on ? DisplayStyle.Flex : DisplayStyle.None;

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

        /// <summary>Tight shot of the patient's face from the doctor's side, framed left of the tablet panel.</summary>
        void CloseUp()
        {
            var head = em.Patient.GetBoneTransform(HumanBodyBones.Head).position + Vector3.up * 0.05f;
            var toDoc = doctorCam.transform.position - head; toDoc.y = 0f;
            var pos = head + toDoc.normalized * 0.95f + Vector3.down * 0.05f;
            Cut(pos, head, 30f);
            demoCam.transform.Rotate(0f, 9f, 0f, Space.World);   // subject to the left third, clear of the side panel
            ShowUi(true);
        }
    }
}
