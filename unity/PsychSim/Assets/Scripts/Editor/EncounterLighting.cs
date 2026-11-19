using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;

namespace Rapport.Editor
{
    /// <summary>
    /// Office lighting (brief §2, DESIGN v0.3): bright, warm, clinical but humane. Called by EncounterSceneBuilder.
    /// Key = soft 5,000 K "window" spot, three-quarters from the doctor's side (real-time, the only shadowed light on the face).
    /// Fill = 3,200 K ceiling lamp (baked). Rim = small real-time spot behind the patient. The window (emissive pane + baked area light) bakes the daylight bounce.
    /// Baked GI, light probes around the sofa and the walk-in path, one box-projected reflection probe, one global post volume.
    /// </summary>
    public static class EncounterLighting
    {
        const string ProfilePath = "Assets/Settings/PsychSim/EncounterVolume.asset";
        const string LightingPath = "Assets/Settings/PsychSim/EncounterLighting.lighting";

        /// <summary>Rendering layer only the patients carry (bit 1, "Light Layer 1"): the face light lights them and nothing else.</summary>
        public const uint PatientLayer = 1u << 1;

        // Real-time settings, tuned on all four bodies (docs/lighting.md). Public so LightingStills -tune can try values without a rebuild.
        public static float KeyIntensity = 14f, KeyAngle = 70f, RimIntensity = 4f, FaceIntensity = 6f, FaceAngle = 30f, PostExposure = 0.35f;

        public static void Apply(Camera cam, Vector3 face)
        {
            ApplyRealtime(face);
            var fill = Kelvin(new GameObject("FillLight_Ceiling").AddComponent<Light>(), 3200f);
            fill.type = LightType.Point; fill.lightmapBakeType = LightmapBakeType.Baked;
            fill.intensity = 0.7f; fill.range = 5f; fill.shadows = LightShadows.Soft;
            fill.transform.position = new Vector3(0f, 2.2f, 0f);
            var day = Kelvin(new GameObject("WindowDaylight_Area").AddComponent<Light>(), 5000f);  // baked bounce from the window
            day.type = LightType.Rectangle; day.lightmapBakeType = LightmapBakeType.Baked; day.areaSize = new Vector2(0.95f, 1f);
            day.intensity = 4f; day.range = 6f;
            day.transform.SetPositionAndRotation(new Vector3(0.4f, 1.475f, 1.47f), Quaternion.Euler(0f, 180f, 0f));

            RenderSettings.ambientMode = AmbientMode.Flat;
            RenderSettings.ambientLight = new Color(0.46f, 0.46f, 0.47f);
            RenderSettings.reflectionIntensity = 0f;  // the default sky reflects cyan off the CC3 alpha-0 eye/hair layers indoors

            var probe = new GameObject("ReflectionProbe_Room").AddComponent<ReflectionProbe>();
            probe.transform.position = new Vector3(0f, 1.2f, 0f);
            probe.size = new Vector3(3.0f, 2.35f, 3.0f); probe.center = Vector3.zero;  // room interior, so box projection lines up
            probe.boxProjection = true; probe.mode = ReflectionProbeMode.Baked; probe.resolution = 128;
            probe.clearFlags = ReflectionProbeClearFlags.SolidColor; probe.backgroundColor = new Color(0.9f, 0.86f, 0.8f);
            probe.gameObject.isStatic = true;

            var lp = new GameObject("LightProbes").AddComponent<LightProbeGroup>();
            var pts = new System.Collections.Generic.List<Vector3>();
            for (float x = -1.3f; x <= 1.31f; x += 0.65f)            // coarse room grid (walk-in path, doctor side)
                for (float z = -1.25f; z <= 1.31f; z += 0.64f)
                    foreach (var y in new[] { 0.3f, 1.2f, 2.0f }) pts.Add(new Vector3(x, y, z));
            for (float x = -0.1f; x <= 1.31f; x += 0.35f)            // dense cage around the sofa seat and the patient's head
                for (float z = -0.8f; z <= 0.41f; z += 0.3f)
                    foreach (var y in new[] { 0.6f, 1.0f, 1.3f, 1.6f }) pts.Add(new Vector3(x, y, z));
            lp.probePositions = pts.ToArray();

            var volume = new GameObject("PostProcess").AddComponent<Volume>();
            volume.isGlobal = true; volume.sharedProfile = Profile();
            cam.GetUniversalAdditionalCameraData().renderPostProcessing = true;

            Lightmapping.lightingSettings = Settings();
        }

        /// <summary>The real-time lights (key, rim, patient-only face light) and post exposure, created or updated in the open scene,
        /// aimed at the patient's seated eye. Needs no re-bake: none of them is baked.</summary>
        public static void ApplyRealtime(Vector3 face)
        {
            var key = Spot("KeyLight_Window", new Vector3(0.2f, 1.95f, 1.3f), face, 5000f, KeyIntensity, KeyAngle, LightmapBakeType.Realtime);
            key.shadows = LightShadows.Soft; key.shadowStrength = 0.75f; key.innerSpotAngle = 25f; key.range = 5f;
            var rim = Spot("RimLight", new Vector3(1.3f, 1.95f, -1.0f), face + Vector3.up * 0.1f, 4500f, RimIntensity, 30f, LightmapBakeType.Realtime);
            rim.shadows = LightShadows.None;
            // a soft lamp-like fill from above the doctor's shoulder that lights only the patient (rendering layer), so the face can sit
            // in the 0.45-0.60 band without brightening the room behind it
            var doctor = GameObject.Find("DoctorAnchor");
            var from = doctor ? doctor.transform.position + new Vector3(0f, 0.45f, 0f) : face + new Vector3(-1.3f, 0.45f, 0.6f);
            var fill = Spot("FaceLight", from, face + Vector3.down * 0.05f, 4500f, FaceIntensity, FaceAngle, LightmapBakeType.Realtime);
            fill.shadows = LightShadows.None; fill.innerSpotAngle = FaceAngle * 0.4f; fill.range = 4f;
            fill.renderingLayerMask = (int)PatientLayer;
            var p = AssetDatabase.LoadAssetAtPath<VolumeProfile>(ProfilePath);
            if (p && p.TryGet<ColorAdjustments>(out var ca)) { ca.postExposure.Override(PostExposure); EditorUtility.SetDirty(p); }
        }

        /// <summary>Puts every renderer of a patient on PatientLayer as well as Default, so the face light reaches it. Also makes skinned
        /// meshes compute their bounds from the bones: Amber's and the Realistic Man's imported bounds sit off the posed head, so at
        /// the 30° doctor FOV their hair and eyes were frustum-culled.</summary>
        public static void MarkPatient(GameObject root)
        {
            foreach (var r in root.GetComponentsInChildren<Renderer>(true)) r.renderingLayerMask |= 1u | PatientLayer;
            foreach (var s in root.GetComponentsInChildren<SkinnedMeshRenderer>(true)) s.updateWhenOffscreen = true;
        }

        static Light Spot(string name, Vector3 pos, Vector3 target, float kelvin, float intensity, float angle, LightmapBakeType mode)
        {
            var found = GameObject.Find(name);
            var l = Kelvin(found && found.TryGetComponent(out Light existing) ? existing : new GameObject(name).AddComponent<Light>(), kelvin);
            l.type = LightType.Spot; l.lightmapBakeType = mode;
            l.intensity = intensity; l.spotAngle = angle; l.range = 4f;
            l.transform.position = pos; l.transform.LookAt(target);
            return l;
        }

        // colour temperature mode, not light.color = CorrelatedColorTemperatureToRGB: that returns linear RGB, and light.color is
        // sRGB, so it came out far too orange (3,200 K looked like 2,000 K)
        static Light Kelvin(Light l, float kelvin)
        {
            l.color = Color.white; l.useColorTemperature = true; l.colorTemperature = kelvin;
            return l;
        }

        static VolumeProfile Profile()
        {
            var p = AssetDatabase.LoadAssetAtPath<VolumeProfile>(ProfilePath);
            if (!p) { p = ScriptableObject.CreateInstance<VolumeProfile>(); AssetDatabase.CreateAsset(p, ProfilePath); }
            T Get<T>() where T : VolumeComponent
            {
                if (p.TryGet<T>(out var c)) return c;
                c = p.Add<T>(true); c.name = typeof(T).Name; AssetDatabase.AddObjectToAsset(c, p);
                return c;
            }
            Get<Tonemapping>().mode.Override(TonemappingMode.Neutral);
            var ca = Get<ColorAdjustments>();
            ca.postExposure.Override(PostExposure); ca.contrast.Override(10f); ca.saturation.Override(5f);
            var bloom = Get<Bloom>();
            bloom.intensity.Override(0.25f); bloom.threshold.Override(1.1f); bloom.scatter.Override(0.6f);
            var v = Get<Vignette>();
            v.intensity.Override(0.12f); v.smoothness.Override(0.5f);
            EditorUtility.SetDirty(p);
            AssetDatabase.SaveAssets();
            return p;
        }

        static LightingSettings Settings()
        {
            var s = AssetDatabase.LoadAssetAtPath<LightingSettings>(LightingPath);
            if (!s) { s = new LightingSettings(); AssetDatabase.CreateAsset(s, LightingPath); }
            s.bakedGI = true; s.realtimeGI = false; s.mixedBakeMode = MixedLightingMode.IndirectOnly;
            s.lightmapper = LightingSettings.Lightmapper.ProgressiveGPU;
            s.lightmapResolution = 12f; s.lightmapMaxSize = 1024; s.lightmapPadding = 2;  // modest: one small lightmap for a 3 x 3 m room
            s.directionalityMode = LightmapsMode.NonDirectional; s.lightmapCompression = LightmapCompression.NormalQuality;
            s.maxBounces = 2; s.directSampleCount = 32; s.indirectSampleCount = 256; s.environmentSampleCount = 128;
            EditorUtility.SetDirty(s);
            return s;
        }
    }
}
