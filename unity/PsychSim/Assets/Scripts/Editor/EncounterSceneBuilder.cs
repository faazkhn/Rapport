using System.IO;
using System.Linq;
using Rapport.Core;
using Rapport.Platform;
using Rapport.Speech;
using Rapport.UI;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.InputSystem;
using UnityEngine.InputSystem.UI;
using UnityEngine.UIElements;

namespace Rapport.Editor
{
    /// <summary>
    /// Rapport/Build Placeholder Encounter Scene: patient prefabs, settings assets and Assets/Scenes/Encounter.unity with a box room
    /// that follows the room contract (see Core/Room.cs). The artist's Room_OutpatientConsult replaces the "PlaceholderRoom" object.
    /// </summary>
    public static class EncounterSceneBuilder
    {
        const string ScenePath = "Assets/Scenes/Encounter.unity";

        // Layout (metres). Doctor faces +Z across the desk; patient chair on the doctor's left, angled about 110 deg to the doctor's chair,
        // patient head about 1.5 m from the doctor's head; door in the far wall, about 4 m from the chair.
        static readonly Vector3 DoctorEye = new(0f, 1.2f, 0f);
        const float PatientYaw = 110f;
        static readonly Vector3 PatientHips = new(-1.1f, 0f, 1.05f);
        const float WallZ = 3.8f;

        [MenuItem("Rapport/Build Placeholder Encounter Scene")]
        public static void Build()
        {
            // NewScene unloads unused assets, so load/create the assets after it
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var prefabs = new[] { "female_20s_a", "male_20s_a" }.Select(BuildPatientPrefab).Where(p => p).ToArray();
            var settings = Asset("Assets/Settings/PsychSim/ServiceSettings.asset", () => ScriptableObject.CreateInstance<ServiceSettings>());
            var profile = LipSyncProfile();
            var panel = PanelSettingsAsset();
            var officeFbx = AssetDatabase.LoadAssetAtPath<GameObject>(OfficePath);
            var room = officeFbx != null ? OfficeRoom(officeFbx) : BuildRoom();

            var anchor = GameObject.Find("DoctorAnchor").transform;
            var camGo = new GameObject("DoctorCamera", typeof(Camera), typeof(AudioListener), typeof(AudioSource));
            camGo.tag = "MainCamera";
            camGo.transform.SetParent(anchor, false);
            camGo.transform.localRotation = Quaternion.Euler(4f, 15f, 0f);
            var cam = camGo.GetComponent<Camera>();
            cam.fieldOfView = 60f; cam.nearClipPlane = 0.05f;
            var rig = camGo.AddComponent<DesktopRig>();
            var actions = AssetDatabase.LoadAssetAtPath<InputActionAsset>("Assets/InputSystem_Actions.inputactions");
            Set(rig, "actions", actions);
            var keyTarget = GameObject.Find("KeyLightTarget");
            EncounterLighting.Apply(cam, keyTarget ? keyTarget.transform.position : PatientHips + Vector3.up * 1.15f);

            var em = new GameObject("EncounterManager").AddComponent<EncounterManager>();
            Set(em, "settings", settings);
            SetArray(em, "patientPrefabs", prefabs);
            SetArray(em, "facePresets", Directory.GetFiles("Assets/Art/Animations/Face", "*.json").Select(AssetDatabase.LoadAssetAtPath<TextAsset>).ToArray());
            Set(em, "lipSyncProfile", profile);
            Set(em, "doctorVoice", camGo.GetComponent<AudioSource>());
            Set(em, "desktopRig", rig);

            var uiGo = new GameObject("EncounterUI");
            var doc = uiGo.AddComponent<UIDocument>();
            doc.panelSettings = panel;
            var ui = uiGo.AddComponent<EncounterUI>();
            Set(ui, "encounter", em);
            new GameObject("EventSystem", typeof(EventSystem), typeof(InputSystemUIInputModule));

            EditorSceneManager.SaveScene(scene, ScenePath);
            Lightmapping.bakeCompleted -= SaveAfterBake; Lightmapping.bakeCompleted += SaveAfterBake;
            Lightmapping.BakeAsync();
            var list = EditorBuildSettings.scenes.Where(s => s.path != ScenePath).ToList();
            list.Insert(0, new EditorBuildSettingsScene(ScenePath, true));
            EditorBuildSettings.scenes = list.ToArray();
            PlayerSettings.insecureHttpOption = InsecureHttpOption.DevelopmentOnly;  // http://127.0.0.1 patient service in dev builds only
            Debug.Log($"PsychSim: built {ScenePath}");
        }

        const string OfficePath = "Assets/Art/Environments/Office/Room_Office.fbx";

        static void SaveAfterBake()
        {
            Lightmapping.bakeCompleted -= SaveAfterBake;
            EditorSceneManager.SaveScene(EditorSceneManager.GetActiveScene());
            Debug.Log("PsychSim: lighting baked");
        }

        /// <summary>The office room from tools/blender/make_office.py; it already carries the room-contract empties.</summary>
        static GameObject OfficeRoom(GameObject fbx)
        {
            var go = (GameObject)PrefabUtility.InstantiatePrefab(fbx);
            foreach (var r in go.GetComponentsInChildren<Renderer>()) r.gameObject.isStatic = r.transform.parent == go.transform;
            // brief §2 items the pack lacks: a window with blinds (motivates the key light) and a box of tissues on the side table
            var frame = Mat("Office/Materials", "M_WindowFrame", new Color(0.93f, 0.91f, 0.87f));
            var sky = Mat("Office/Materials", "M_WindowDaylight", new Color(0.95f, 0.93f, 0.9f));
            sky.EnableKeyword("_EMISSION"); sky.SetColor("_EmissionColor", Mathf.CorrelatedColorTemperatureToRGB(5000f).gamma * 2.5f);
            sky.globalIlluminationFlags = MaterialGlobalIlluminationFlags.BakedEmissive;
            EditorUtility.SetDirty(sky);
            var win = new GameObject("Window").transform;
            win.SetParent(go.transform, false);
            win.position = new Vector3(0.4f, 1.475f, 1.495f);   // south wall, right of the desk; 1.0 x 1.05 m, sill at 0.95 m
            Box(win.gameObject, "Pane", new Vector3(0f, 0f, 0f), new Vector3(0.96f, 1.01f, 0.01f), sky, true);
            Box(win.gameObject, "Frame_T", new Vector3(0f, 0.525f, -0.02f), new Vector3(1.04f, 0.05f, 0.05f), frame, true);
            Box(win.gameObject, "Frame_B", new Vector3(0f, -0.525f, -0.04f), new Vector3(1.1f, 0.04f, 0.12f), frame, true);
            Box(win.gameObject, "Frame_L", new Vector3(-0.5f, 0f, -0.02f), new Vector3(0.05f, 1.1f, 0.05f), frame, true);
            Box(win.gameObject, "Frame_R", new Vector3(0.5f, 0f, -0.02f), new Vector3(0.05f, 1.1f, 0.05f), frame, true);
            for (int i = 0; i < 7; i++)                          // blinds lowered over the top half, slats tilted open
            {
                Box(win.gameObject, "Slat", new Vector3(0f, 0.47f - i * 0.07f, -0.05f), new Vector3(0.94f, 0.004f, 0.05f), frame, true);
                win.GetChild(win.childCount - 1).localRotation = Quaternion.Euler(-35f, 0f, 0f);
            }
            var tissues = new GameObject("Tissues").transform;
            tissues.SetParent(go.transform, false);
            tissues.SetPositionAndRotation(new Vector3(0.98f, 0.83f, -0.72f), Quaternion.Euler(0f, 20f, 0f));
            Box(tissues.gameObject, "Box", new Vector3(0f, 0.045f, 0f), new Vector3(0.12f, 0.09f, 0.24f), Mat("Office/Materials", "M_TissueBox", new Color(0.45f, 0.66f, 0.7f)), true);
            Box(tissues.gameObject, "Tissue", new Vector3(0f, 0.11f, 0f), new Vector3(0.06f, 0.05f, 0.1f), frame, true);
            foreach (var t in win.GetComponentsInChildren<Transform>().Concat(tissues.GetComponentsInChildren<Transform>())) t.gameObject.isStatic = true;
            // bare upper corner above the door-side shelves for internal_stimuli looks (the old target sat on the shelves)
            go.transform.Find("CornerLookTarget").position = new Vector3(-1.47f, 2.2f, -1.4f);
            AngleSeats(go.transform);
            return go;
        }

        /// <summary>Angle between the patient's and the doctor's facing (brief: 90-120°; the room as exported had about 156°).</summary>
        public const float SeatAngle = 110f;
        /// <summary>The patient sits turned this far past the doctor, toward the desk side, so her face reads as a gentle three-quarter
        /// view; the doctor's chair takes the rest of (180 - SeatAngle), turned toward the desk, so the two chairs converge in front.</summary>
        public const float PatientOffAxis = 10f;

        /// <summary>Turns the patient's seat (PatientAnchor, ChairApproach, KeyLightTarget) about her hips, which stay on the cushion,
        /// and the DoctorAnchor in place. Absolute yaws from the hips-to-doctor line, so running it twice changes nothing.</summary>
        public static void AngleSeats(Transform room)
        {
            Transform doc = room.Find("DoctorAnchor"), pat = room.Find("PatientAnchor"), app = room.Find("ChairApproach"), eye = room.Find("KeyLightTarget");
            var hips = pat.position - pat.forward * 0.40f;     // seated clips put the hips 0.40 m behind the anchor
            var line = doc.position - hips; line.y = 0f;
            float lineYaw = Quaternion.LookRotation(line).eulerAngles.y;
            var turn = Quaternion.Euler(0f, lineYaw + PatientOffAxis, 0f) * Quaternion.Inverse(pat.rotation);
            if (eye) eye.position = hips + turn * (eye.position - hips);
            pat.SetPositionAndRotation(hips + turn * (pat.position - hips), turn * pat.rotation);
            if (app) app.SetPositionAndRotation(pat.position, pat.rotation);
            doc.rotation = Quaternion.Euler(0f, lineYaw + 180f - (180f - SeatAngle - PatientOffAxis), 0f);
        }

        static GameObject BuildRoom()
        {
            var root = new GameObject("PlaceholderRoom");
            var wall = Mat("Wall", new Color(0.82f, 0.8f, 0.74f));
            var floor = Mat("Floor", new Color(0.45f, 0.38f, 0.3f));
            var wood = Mat("Wood", new Color(0.5f, 0.36f, 0.24f));
            var fabric = Mat("ChairFabric", new Color(0.25f, 0.33f, 0.42f));
            var doorMat = Mat("Door", new Color(0.62f, 0.5f, 0.36f));

            Box(root, "Floor", new Vector3(0f, -0.05f, 1.2f), new Vector3(5.2f, 0.1f, 5.2f), floor);
            Box(root, "CorridorFloor", new Vector3(1.5f, -0.05f, 5.0f), new Vector3(2.4f, 0.1f, 2.4f), floor);
            Box(root, "Ceiling", new Vector3(0f, 2.85f, 1.2f), new Vector3(5.4f, 0.1f, 5.4f), wall);
            Box(root, "Wall_South", new Vector3(0f, 1.4f, -1.45f), new Vector3(5.2f, 2.8f, 0.1f), wall);
            Box(root, "Wall_West", new Vector3(-2.65f, 1.4f, 1.2f), new Vector3(0.1f, 2.8f, 5.3f), wall);
            Box(root, "Wall_East", new Vector3(2.65f, 1.4f, 1.2f), new Vector3(0.1f, 2.8f, 5.3f), wall);
            // north wall with a 0.9 x 2.1 m door opening from x 1.05 to 1.95
            Box(root, "Wall_North_L", new Vector3(-0.8f, 1.4f, WallZ), new Vector3(3.7f, 2.8f, 0.1f), wall);
            Box(root, "Wall_North_R", new Vector3(2.3f, 1.4f, WallZ), new Vector3(0.7f, 2.8f, 0.1f), wall);
            Box(root, "Wall_North_Top", new Vector3(1.5f, 2.45f, WallZ), new Vector3(0.9f, 0.7f, 0.1f), wall);

            // desk in front of the doctor
            Box(root, "Desk_Top", new Vector3(0.3f, 0.74f, 0.8f), new Vector3(1.2f, 0.04f, 0.7f), wood);
            foreach (var (x, z) in new[] { (-0.27f, 0.48f), (0.87f, 0.48f), (-0.27f, 1.12f), (0.87f, 1.12f) })
                Box(root, "Desk_Leg", new Vector3(x, 0.36f, z), new Vector3(0.05f, 0.72f, 0.05f), wood);
            Chair(root, "DoctorChair", new Vector3(0f, 0f, -0.12f), 180f, fabric);   // the doctor sits here (eye point above it)

            // patient chair: seat front edge 0.10 m behind PatientAnchor, seat 0.46 deep, top at 0.45 m (matches the artist's clips)
            var f = Quaternion.Euler(0f, PatientYaw, 0f) * Vector3.forward;
            var patientRoot = PatientHips + f * 0.40f;
            Chair(root, "PatientChair", patientRoot - f * 0.33f, PatientYaw + 180f, fabric);

            // contract children
            Empty(root, "DoctorAnchor", DoctorEye, 0f);
            Empty(root, "PatientAnchor", patientRoot, PatientYaw);
            Empty(root, "ChairApproach", patientRoot, PatientYaw);
            Empty(root, "PatientSpawn", new Vector3(1.5f, 0f, WallZ + 0.5f), 180f);
            Empty(root, "CornerLookTarget", new Vector3(-2.5f, 1.5f, WallZ - 0.1f), 0f);
            Empty(root, "SoundSource_Door", new Vector3(1.5f, 1.0f, WallZ), 0f);
            Empty(root, "SoundSource_Corridor", new Vector3(1.5f, 1.5f, WallZ + 1.6f), 0f);
            // door: hinge on the east side of the opening; frame turned 180 so a negative local Y angle swings the door into the room
            var frame = Empty(root, "DoorFrame", new Vector3(1.95f, 0f, WallZ), 180f);
            var door = new GameObject("Door").transform;
            door.SetParent(frame, false);
            Box(door.gameObject, "DoorPanel", new Vector3(0.45f, 1.05f, 0f), new Vector3(0.88f, 2.08f, 0.04f), doorMat, local: true);
            return root;
        }

        static void Chair(GameObject root, string name, Vector3 seatCentre, float yaw, Material m)
        {
            // seat centred on seatCentre, backrest at local -Z (yaw turns it); seat top 0.45 m
            var c = new GameObject(name).transform;
            c.SetParent(root.transform, false);
            c.SetPositionAndRotation(seatCentre, Quaternion.Euler(0f, yaw, 0f));
            Box(c.gameObject, "Seat", new Vector3(0f, 0.42f, 0f), new Vector3(0.46f, 0.06f, 0.46f), m, true);
            Box(c.gameObject, "Back", new Vector3(0f, 0.72f, 0.25f), new Vector3(0.46f, 0.55f, 0.05f), m, true);
            foreach (var (x, z) in new[] { (-0.2f, -0.2f), (0.2f, -0.2f), (-0.2f, 0.2f), (0.2f, 0.2f) })
                Box(c.gameObject, "Leg", new Vector3(x, 0.2f, z), new Vector3(0.04f, 0.4f, 0.04f), m, true);
        }

        static Transform Empty(GameObject root, string name, Vector3 pos, float yaw)
        {
            var t = new GameObject(name).transform;
            t.SetParent(root.transform, false);
            t.SetPositionAndRotation(pos, Quaternion.Euler(0f, yaw, 0f));
            return t;
        }

        static void Box(GameObject parent, string name, Vector3 pos, Vector3 size, Material m, bool local = false)
        {
            var b = GameObject.CreatePrimitive(PrimitiveType.Cube);
            b.name = name;
            b.transform.SetParent(parent.transform, false);
            if (local) b.transform.localPosition = pos; else b.transform.position = pos;
            b.transform.localScale = size;
            b.GetComponent<Renderer>().sharedMaterial = m;
            b.isStatic = !local;
        }

        static Material Mat(string name, Color c) => Mat("Placeholder", name, c);

        static Material Mat(string room, string name, Color c)
        {
            var path = $"Assets/Art/Environments/{room}/{name}.mat";
            return Asset(path, () => new Material(Shader.Find("Universal Render Pipeline/Lit")) { color = c });
        }

        internal static GameObject BuildPatientPrefab(string id)
        {
            var model = AssetDatabase.LoadAssetAtPath<GameObject>($"Assets/Art/Patients/{id}/{id}.fbx");
            if (model == null) return null;
            var path = $"Assets/Art/Patients/{id}/{id}.prefab";
            var inst = (GameObject)PrefabUtility.InstantiatePrefab(model);
            var anim = inst.GetComponent<Animator>();
            anim.runtimeAnimatorController = AssetDatabase.LoadAssetAtPath<RuntimeAnimatorController>(PatientAnimatorBuilder.ControllerPath);
            anim.applyRootMotion = false;
            anim.cullingMode = AnimatorCullingMode.AlwaysAnimate;
            EncounterLighting.MarkPatient(inst);
            var prefab = PrefabUtility.SaveAsPrefabAsset(inst, path);
            Object.DestroyImmediate(inst);
            return prefab;
        }

        static uLipSync.Profile LipSyncProfile()
        {
            const string path = "Assets/Art/LipSync/uLipSync-Profile-female_20s_a.asset";
            if (AssetDatabase.LoadAssetAtPath<uLipSync.Profile>(path) is { } p) return p;
            var sample = AssetDatabase.FindAssets("uLipSync-Profile-Sample-Female t:uLipSync.Profile").Select(AssetDatabase.GUIDToAssetPath).First();
            Directory.CreateDirectory("Assets/Art/LipSync");
            AssetDatabase.CopyAsset(sample, path);
            return AssetDatabase.LoadAssetAtPath<uLipSync.Profile>(path);
        }

        static PanelSettings PanelSettingsAsset()
        {
            const string themePath = "Assets/UI/PsychSimTheme.tss";
            if (!File.Exists(themePath))
            {
                Directory.CreateDirectory("Assets/UI");
                File.WriteAllText(themePath, "@import url(\"unity-theme://default\");\n");
                AssetDatabase.ImportAsset(themePath);
            }
            var ps = Asset("Assets/UI/PanelSettings.asset", () => ScriptableObject.CreateInstance<PanelSettings>());
            ps.themeStyleSheet = AssetDatabase.LoadAssetAtPath<ThemeStyleSheet>(themePath);
            ps.scaleMode = PanelScaleMode.ScaleWithScreenSize;
            ps.referenceResolution = new Vector2Int(1920, 1080);
            ps.match = 0.5f;
            EditorUtility.SetDirty(ps);
            return ps;
        }

        static T Asset<T>(string path, System.Func<T> create) where T : Object
        {
            var a = AssetDatabase.LoadAssetAtPath<T>(path);
            if (a) return a;
            Directory.CreateDirectory(Path.GetDirectoryName(path));
            a = create();
            AssetDatabase.CreateAsset(a, path);
            return a;
        }

        static void Set(Object target, string field, Object value)
        {
            var so = new SerializedObject(target);
            so.FindProperty(field).objectReferenceValue = value;
            so.ApplyModifiedPropertiesWithoutUndo();
        }

        static void SetArray(Object target, string field, Object[] values)
        {
            var so = new SerializedObject(target);
            var p = so.FindProperty(field);
            p.arraySize = values.Length;
            for (int i = 0; i < values.Length; i++) p.GetArrayElementAtIndex(i).objectReferenceValue = values[i];
            so.ApplyModifiedPropertiesWithoutUndo();
        }
    }
}
