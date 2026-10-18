using System.IO;
using System.Linq;
using PsychSim.Core;
using PsychSim.Platform;
using PsychSim.Speech;
using PsychSim.UI;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.InputSystem;
using UnityEngine.InputSystem.UI;
using UnityEngine.UIElements;

namespace PsychSim.Editor
{
    /// <summary>
    /// PsychSim/Build Placeholder Encounter Scene: patient prefabs, settings assets and Assets/Scenes/Encounter.unity with a box room
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

        [MenuItem("PsychSim/Build Placeholder Encounter Scene")]
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

            var lightGo = new GameObject("Sun");
            var sun = lightGo.AddComponent<Light>();
            sun.type = LightType.Directional; sun.intensity = 0.6f; sun.color = new Color(1f, 0.96f, 0.9f);
            lightGo.transform.rotation = Quaternion.Euler(55f, -30f, 0f);
            var key = new GameObject("KeyLight_PatientFace").AddComponent<Light>();  // the one real-time light on the patient's face
            key.type = LightType.Spot; key.intensity = 6f; key.range = 5f; key.spotAngle = 45f; key.color = new Color(1f, 0.95f, 0.88f);
            key.transform.position = new Vector3(-0.2f, 2.4f, 0.2f);
            var keyTarget = GameObject.Find("KeyLightTarget");
            key.transform.LookAt(keyTarget ? keyTarget.transform.position : PatientHips + Vector3.up * 1.15f);
            if (keyTarget) key.transform.position = keyTarget.transform.position + new Vector3(-1.0f, 1.0f, 0.6f);
            if (keyTarget) key.transform.LookAt(keyTarget.transform.position);
            var ceiling = new GameObject("CeilingLight").AddComponent<Light>();
            ceiling.type = LightType.Point; ceiling.intensity = 2.5f; ceiling.range = 6f; ceiling.shadows = LightShadows.Soft;
            ceiling.color = new Color(1f, 0.96f, 0.9f);
            ceiling.transform.position = new Vector3(0f, 2.2f, 0f);
            RenderSettings.ambientMode = UnityEngine.Rendering.AmbientMode.Flat;
            RenderSettings.ambientLight = new Color(0.55f, 0.55f, 0.57f);
            RenderSettings.reflectionIntensity = 0f;  // the default sky reflects cyan off the CC3 alpha-0 eye/hair layers indoors

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
            var list = EditorBuildSettings.scenes.Where(s => s.path != ScenePath).ToList();
            list.Insert(0, new EditorBuildSettingsScene(ScenePath, true));
            EditorBuildSettings.scenes = list.ToArray();
            PlayerSettings.insecureHttpOption = InsecureHttpOption.DevelopmentOnly;  // http://127.0.0.1 patient service in dev builds only
            Debug.Log($"PsychSim: built {ScenePath}");
        }

        const string OfficePath = "Assets/Art/Environments/Office/Room_Office.fbx";

        /// <summary>The office room from tools/blender/make_office.py; it already carries the room-contract empties.</summary>
        static GameObject OfficeRoom(GameObject fbx)
        {
            var go = (GameObject)PrefabUtility.InstantiatePrefab(fbx);
            foreach (var r in go.GetComponentsInChildren<Renderer>()) r.gameObject.isStatic = r.transform.parent == go.transform;
            return go;
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

        static Material Mat(string name, Color c)
        {
            var path = $"Assets/Art/Environments/Placeholder/{name}.mat";
            return Asset(path, () => new Material(Shader.Find("Universal Render Pipeline/Lit")) { color = c });
        }

        static GameObject BuildPatientPrefab(string id)
        {
            var model = AssetDatabase.LoadAssetAtPath<GameObject>($"Assets/Art/Patients/{id}/{id}.fbx");
            if (model == null) return null;
            var path = $"Assets/Art/Patients/{id}/{id}.prefab";
            var inst = (GameObject)PrefabUtility.InstantiatePrefab(model);
            var anim = inst.GetComponent<Animator>();
            anim.runtimeAnimatorController = AssetDatabase.LoadAssetAtPath<RuntimeAnimatorController>(PatientAnimatorBuilder.ControllerPath);
            anim.applyRootMotion = false;
            anim.cullingMode = AnimatorCullingMode.AlwaysAnimate;
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
