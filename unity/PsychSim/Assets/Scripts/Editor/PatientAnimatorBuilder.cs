using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.Animations;
using UnityEngine;

namespace PsychSim.Editor
{
    /// <summary>
    /// PsychSim/Rebuild Patient Animator: applies the import settings from art/Animations/ANIMATIONS.md to every FBX under
    /// Assets/Art/Animations, writes the avatar masks and rebuilds PatientController.controller, wiring clips by name.
    /// Missing clips leave an empty state; runtime code checks which clips exist. Re-run after the artist adds or changes clips.
    /// </summary>
    public static class PatientAnimatorBuilder
    {
        public const string AnimDir = "Assets/Art/Animations";
        public const string ControllerPath = AnimDir + "/PatientController.controller";
        public const string MaskDir = "Assets/Art/Masks";

        static readonly string[] Loops = { "base_sit_neutral", "base_sit_slumped", "cue_fidget_nails_Hands", "gesture_talk_small_01", "gesture_talk_small_02", "stand_idle" };

        [MenuItem("PsychSim/Rebuild Patient Animator")]
        public static void Rebuild()
        {
            var masks = BuildMasks();
            ConfigureClipImports();
            var clips = FindClips();

            AssetDatabase.DeleteAsset(ControllerPath);
            var ac = AnimatorController.CreateAnimatorControllerAtPath(ControllerPath);
            ac.AddParameter("Slumped", AnimatorControllerParameterType.Float);

            // Layer 0: base. Seated = blend tree neutral <-> slumped by the slumped cue intensity.
            var sm = ac.layers[0].stateMachine;
            var tree = new BlendTree { name = "SeatedBlend", blendParameter = "Slumped", blendType = BlendTreeType.Simple1D, useAutomaticThresholds = false };
            AssetDatabase.AddObjectToAsset(tree, ac);
            tree.AddChild(Clip(clips, "base_sit_neutral"), 0f);
            tree.AddChild(Clip(clips, "base_sit_slumped"), 1f);
            var seated = sm.AddState("Seated");
            seated.motion = tree;
            seated.iKOnFeet = true;   // Matt's legs are longer than Mégane's; Foot IK keeps his feet on the floor
            sm.defaultState = seated;
            AddState(sm, "walk_in", clips);
            var sit = AddState(sm, "sit_down", clips);
            sit.iKOnFeet = true;
            var t = sit.AddTransition(seated);
            t.hasExitTime = true; t.exitTime = 1f; t.duration = 0.1f;
            // exam: stand_up -> stand_idle (held while standing); sit_down above returns to Seated
            var standUp = AddState(sm, "stand_up", clips);
            var standIdle = AddState(sm, "stand_idle", clips);
            standUp.iKOnFeet = standIdle.iKOnFeet = true;
            t = standUp.AddTransition(standIdle);
            t.hasExitTime = true; t.exitTime = 1f; t.duration = 0.15f;

            // Talk gestures and the fidget are additive (exact over neutral, stay on the lap over slumped); wipe tears and head gestures override.
            AddLayer(ac, "Fidget", masks["Hands"], AnimatorLayerBlendingMode.Additive, clips, "cue_fidget_nails_Hands");
            AddLayer(ac, "Talk", masks["Arms"], AnimatorLayerBlendingMode.Additive, clips, "Empty", "gesture_talk_small_01", "gesture_talk_small_02");
            AddLayer(ac, "ArmsOneShot", masks["Arms"], AnimatorLayerBlendingMode.Override, clips, "Empty", "cue_wipe_tears", "action_hold_out_hands", "action_roll_up_sleeves");
            AddLayer(ac, "Head", masks["Head"], AnimatorLayerBlendingMode.Override, clips, "Empty", "gesture_nod", "gesture_head_shake", "action_look_at_light");

            // IK pass: base (exam hand presentation while standing) and ArmsOneShot (hands, wipe tears); ExamController.OnAnimatorIK
            var ls = ac.layers;
            foreach (var i in new[] { 0, System.Array.FindIndex(ls, l => l.name == "ArmsOneShot") }) ls[i].iKPass = true;
            ac.layers = ls;

            EditorUtility.SetDirty(ac);
            AssetDatabase.SaveAssets();
            var missing = new[] { "walk_in", "sit_down", "stand_up", "stand_idle", "base_sit_neutral", "base_sit_slumped", "cue_fidget_nails_Hands", "cue_wipe_tears",
                "gesture_talk_small_01", "gesture_talk_small_02", "gesture_nod", "gesture_head_shake",
                "action_hold_out_hands", "action_roll_up_sleeves", "action_look_at_light" }.Where(n => !clips.ContainsKey(n)).ToList();
            Debug.Log($"PsychSim: rebuilt {ControllerPath} with {clips.Count} clips" + (missing.Count > 0 ? $"; missing (empty states): {string.Join(", ", missing)}" : ""));
        }

        static AnimatorState AddState(AnimatorStateMachine sm, string name, Dictionary<string, AnimationClip> clips)
        {
            var s = sm.AddState(name);
            s.motion = Clip(clips, name);
            return s;
        }

        static void AddLayer(AnimatorController ac, string name, AvatarMask mask, AnimatorLayerBlendingMode mode, Dictionary<string, AnimationClip> clips, params string[] states)
        {
            var layer = new AnimatorControllerLayer
            {
                name = name, avatarMask = mask, blendingMode = mode, defaultWeight = 0f,
                stateMachine = new AnimatorStateMachine { name = name, hideFlags = HideFlags.HideInHierarchy },
            };
            AssetDatabase.AddObjectToAsset(layer.stateMachine, ac);
            foreach (var s in states) { var st = AddState(layer.stateMachine, s, clips); st.writeDefaultValues = false; }
            ac.AddLayer(layer);
        }

        static Motion Clip(Dictionary<string, AnimationClip> clips, string name) => clips.TryGetValue(name, out var c) ? c : null;

        static Dictionary<string, AnimationClip> FindClips()
        {
            var d = new Dictionary<string, AnimationClip>();
            foreach (var guid in AssetDatabase.FindAssets("t:AnimationClip", new[] { AnimDir }))
                foreach (var c in AssetDatabase.LoadAllAssetsAtPath(AssetDatabase.GUIDToAssetPath(guid)).OfType<AnimationClip>())
                    if (!c.name.StartsWith("__preview__")) d[c.name] = c;
            return d;
        }

        static void ConfigureClipImports()
        {
            foreach (var path in Directory.GetFiles(AnimDir, "*.fbx", SearchOption.AllDirectories).Select(p => p.Replace('\\', '/')))
            {
                var mi = (ModelImporter)AssetImporter.GetAtPath(path);
                var name = Path.GetFileNameWithoutExtension(path);
                mi.animationType = ModelImporterAnimationType.Human;
                // Create From This Model (the file's rest pose is the CC3 A-pose). Copy From Other errors because the clips key the
                // in-between CC_Base_NeckTwist02 away from its rest rotation; humanoid retargeting makes the result the same.
                mi.avatarSetup = ModelImporterAvatarSetup.CreateFromThisModel;
                mi.sourceAvatar = null;
                mi.importAnimation = true;
                mi.materialImportMode = ModelImporterMaterialImportMode.None;
                var src = mi.defaultClipAnimations.FirstOrDefault(c => c.takeName == name) ?? mi.defaultClipAnimations.FirstOrDefault();
                if (src == null) { Debug.LogError($"PsychSim: {path} has no animation take"); continue; }
                bool walk = name == "walk_in";
                src.name = name;
                src.loopTime = Loops.Contains(name);
                src.loopPose = false;
                src.lockRootRotation = true;                 // Bake Into Pose
                src.keepOriginalOrientation = !walk;         // Original (seated) / Body Orientation (walk)
                src.lockRootHeightY = true;
                src.keepOriginalPositionY = !walk;           // Original (seated) / Feet (walk)
                src.heightFromFeet = walk;
                src.lockRootPositionXZ = !walk;              // walk_in keeps its XZ root motion
                src.keepOriginalPositionXZ = !walk;
                mi.clipAnimations = new[] { src };
                mi.SaveAndReimport();
            }
        }

        static Dictionary<string, AvatarMask> BuildMasks()
        {
            if (!AssetDatabase.IsValidFolder(MaskDir)) AssetDatabase.CreateFolder("Assets/Art", "Masks");
            var parts = new Dictionary<string, AvatarMaskBodyPart[]>
            {
                ["UpperBody"] = new[] { AvatarMaskBodyPart.Body, AvatarMaskBodyPart.Head, AvatarMaskBodyPart.LeftArm, AvatarMaskBodyPart.RightArm, AvatarMaskBodyPart.LeftFingers, AvatarMaskBodyPart.RightFingers, AvatarMaskBodyPart.LeftHandIK, AvatarMaskBodyPart.RightHandIK },
                ["Arms"] = new[] { AvatarMaskBodyPart.LeftArm, AvatarMaskBodyPart.RightArm, AvatarMaskBodyPart.LeftFingers, AvatarMaskBodyPart.RightFingers, AvatarMaskBodyPart.LeftHandIK, AvatarMaskBodyPart.RightHandIK },
                ["Hands"] = new[] { AvatarMaskBodyPart.LeftFingers, AvatarMaskBodyPart.RightFingers },
                ["Legs"] = new[] { AvatarMaskBodyPart.LeftLeg, AvatarMaskBodyPart.RightLeg, AvatarMaskBodyPart.LeftFootIK, AvatarMaskBodyPart.RightFootIK },
                ["Head"] = new[] { AvatarMaskBodyPart.Head },   // humanoid Head part = neck + head
            };
            var result = new Dictionary<string, AvatarMask>();
            foreach (var kv in parts)
            {
                var path = $"{MaskDir}/{kv.Key}.mask";
                var mask = AssetDatabase.LoadAssetAtPath<AvatarMask>(path);
                if (mask == null) { mask = new AvatarMask(); AssetDatabase.CreateAsset(mask, path); }
                for (var p = AvatarMaskBodyPart.Root; p < AvatarMaskBodyPart.LastBodyPart; p++) mask.SetHumanoidBodyPartActive(p, kv.Value.Contains(p));
                EditorUtility.SetDirty(mask);
                result[kv.Key] = mask;
            }
            AssetDatabase.SaveAssets();
            return result;
        }
    }
}
