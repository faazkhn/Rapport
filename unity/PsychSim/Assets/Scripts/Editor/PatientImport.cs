using System.IO;
using System.Linq;
using Rapport.Core;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace Rapport.Editor
{
    /// <summary>
    /// Turns a staged character (tools/blender/stage_patient.py: Art/Patients/&lt;id&gt;/&lt;id&gt;.fbx + Textures/) into a patient:
    /// a humanoid avatar, URP Lit materials copied from the tuned ones on the existing patients (same name, else hair or cloth),
    /// the patient prefab, and an entry in the Encounter scene's patient list.
    /// </summary>
    public static class PatientImport
    {
        public static readonly string[] NewIds = { "female_20s_b", "male_30s_a" };
        static readonly string[] TemplateDirs = { "Assets/Art/Patients/male_20s_a/Materials", "Assets/Art/Patients/female_20s_a/Materials" };

        [MenuItem("Rapport/Import New Patients")]
        public static void ImportAll()
        {
            var prefabs = NewIds.Select(Import).Where(p => p).ToArray();
            var scene = EditorSceneManager.OpenScene("Assets/Scenes/Encounter.unity");
            var em = Object.FindAnyObjectByType<EncounterManager>();
            var so = new SerializedObject(em);
            var list = so.FindProperty("patientPrefabs");
            foreach (var p in prefabs)
            {
                if (Enumerable.Range(0, list.arraySize).Any(i => list.GetArrayElementAtIndex(i).objectReferenceValue == p)) continue;
                list.InsertArrayElementAtIndex(list.arraySize);
                list.GetArrayElementAtIndex(list.arraySize - 1).objectReferenceValue = p;
            }
            so.ApplyModifiedPropertiesWithoutUndo();
            EditorSceneManager.SaveScene(scene);
            Debug.Log($"PatientImport: {prefabs.Length} patients, scene list now {list.arraySize}");
        }

        static GameObject Import(string id)
        {
            string dir = $"Assets/Art/Patients/{id}", fbx = $"{dir}/{id}.fbx";
            if (!File.Exists(fbx)) { Debug.LogError($"PatientImport: no {fbx}"); return null; }
            foreach (var path in Directory.GetFiles($"{dir}/Textures").Where(p => !p.EndsWith(".meta"))) SetupTexture(path.Replace('\\', '/'));
            var mi = (ModelImporter)AssetImporter.GetAtPath(fbx);
            mi.humanDescription = new HumanDescription();  // map from scratch: a mapping kept from an older export of the file points at the wrong bones
            mi.animationType = ModelImporterAnimationType.Human;
            mi.avatarSetup = ModelImporterAvatarSetup.CreateFromThisModel;
            mi.importBlendShapes = true;
            mi.isReadable = true;  // SleeveRoller builds its blendshapes from the mesh at runtime; without this, builds cannot read it
            mi.importAnimation = false;
            mi.materialImportMode = ModelImporterMaterialImportMode.ImportStandard;
            mi.SaveAndReimport();
            var avatar = AssetDatabase.LoadAllAssetsAtPath(fbx).OfType<Avatar>().FirstOrDefault();
            if (avatar == null || !avatar.isValid)  // auto-mapping missed: every CC body has the same bone names, so take Arjun's mapping
            {
                var template = ((ModelImporter)AssetImporter.GetAtPath("Assets/Art/Patients/male_20s_a/male_20s_a.fbx")).humanDescription;
                var model = AssetDatabase.LoadAssetAtPath<GameObject>(fbx);
                template.skeleton = model.GetComponentsInChildren<Transform>(true).Select(t => new SkeletonBone
                    { name = t.name, position = t.localPosition, rotation = t.localRotation, scale = t.localScale }).ToArray();
                mi.humanDescription = template;
                mi.SaveAndReimport();
                avatar = AssetDatabase.LoadAllAssetsAtPath(fbx).OfType<Avatar>().FirstOrDefault();
            }
            if (avatar == null || !avatar.isValid || !avatar.isHuman) { Debug.LogError($"PatientImport: {id} has no valid humanoid avatar"); return null; }

            var prefab = EncounterSceneBuilder.BuildPatientPrefab(id);
            var root = PrefabUtility.LoadPrefabContents($"{dir}/{id}.prefab");
            Directory.CreateDirectory($"{dir}/Materials");
            int made = 0;
            foreach (var r in root.GetComponentsInChildren<Renderer>(true))
                r.sharedMaterials = r.sharedMaterials.Select(m => m ? MakeMaterial(dir, m.name, ref made) : m).ToArray();
            PrefabUtility.SaveAsPrefabAsset(root, $"{dir}/{id}.prefab");
            PrefabUtility.UnloadPrefabContents(root);
            Debug.Log($"PatientImport: {id} avatar ok, {made} materials");
            return AssetDatabase.LoadAssetAtPath<GameObject>($"{dir}/{id}.prefab");
        }

        static Material MakeMaterial(string dir, string name, ref int made)
        {
            name = name.Replace(" (Instance)", "");
            var path = $"{dir}/Materials/{name}.mat";
            if (AssetDatabase.LoadAssetAtPath<Material>(path) is { } existing) return existing;
            var m = new Material(Template(name)) { name = name };
            var tex = $"{dir}/Textures/{name}";
            var baseMap = Load(tex + "_Diffuse_A.png") ?? Load(tex + "_Diffuse.jpg") ?? Load(tex + "_Diffuse.png");
            if (baseMap) m.SetTexture("_BaseMap", baseMap);
            var normal = Load(tex + "_Normal.png") ?? Load(tex + "_Normal.jpg");
            if (normal) { m.SetTexture("_BumpMap", normal); m.EnableKeyword("_NORMALMAP"); }
            else { m.SetTexture("_BumpMap", null); m.DisableKeyword("_NORMALMAP"); }
            AssetDatabase.CreateAsset(m, path);
            made++;
            return m;
        }

        /// <summary>The tuned material with the same name on an existing patient; hair-like ones copy the hair, the rest a shirt.</summary>
        static Material Template(string name)
        {
            Material Find(string n) => TemplateDirs.Select(d => AssetDatabase.LoadAssetAtPath<Material>($"{d}/{n}.mat")).FirstOrDefault(m => m);
            return Find(name) ?? (name.Contains("Hair") || name.Contains("Brow") ? Find("Hair_Transparency") : Find("Fit_shirts"));
        }

        static Texture2D Load(string path) => AssetDatabase.LoadAssetAtPath<Texture2D>(path);

        static void SetupTexture(string path)
        {
            if (AssetImporter.GetAtPath(path) is not TextureImporter ti) return;
            ti.maxTextureSize = 2048;
            if (path.Contains("_Normal.")) ti.textureType = TextureImporterType.NormalMap;
            if (path.EndsWith("_Diffuse_A.png"))  // alpha-clipped cards keep their coverage in the mips (the hair fix)
            {
                ti.alphaIsTransparency = true;
                ti.mipMapsPreserveCoverage = true;
                ti.alphaTestReferenceValue = 0.35f;
            }
            ti.SaveAndReimport();
        }
    }
}
