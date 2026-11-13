using System.Collections.Generic;
using UnityEngine;

namespace Rapport.Cues
{
    /// <summary>
    /// Rolls the sleeves up to the elbow. At setup, each clothing mesh gets one blendshape per arm that slides the vertices which
    /// follow the forearm (by skin weight) up into a thick cuff just below the elbow; the body underneath already has forearm skin.
    /// Built from the rig at runtime, so any skinned character works without re-exporting its FBX. Left/Right: 0 down, 1 rolled.
    /// </summary>
    public class SleeveRoller : MonoBehaviour
    {
        public float Left, Right;
        const float CuffStart = 0.04f, CuffLength = 0.16f, MaxS = 1.15f;  // along the forearm, elbow 0 to wrist 1
        readonly List<(SkinnedMeshRenderer r, int shape, bool left)> shapes = new();

        public void Setup(Animator anim)
        {
            foreach (var r in GetComponentsInChildren<SkinnedMeshRenderer>())
            {
                if (!r.sharedMesh || System.Array.Exists(r.sharedMaterials, m => m && m.name.Contains("Skin"))) continue;  // the body itself
                Mesh mesh = null;
                var weights = r.sharedMesh.boneWeights;
                foreach (bool left in new[] { true, false })
                {
                    var deltas = Deltas(r, anim, left, weights);
                    if (deltas == null) continue;
                    mesh ??= Instantiate(r.sharedMesh);
                    mesh.AddBlendShapeFrame(left ? "Rapport_SleeveRolled_L" : "Rapport_SleeveRolled_R", 100f, deltas, null, null);
                    shapes.Add((r, mesh.blendShapeCount - 1, left));
                }
                if (!mesh) continue;
                mesh.boneWeights = weights;
                Ease(mesh, r, anim);
                mesh.name = r.sharedMesh.name;
                r.sharedMesh = mesh;
            }
        }

        public bool HasSleeves => shapes.Count > 0;

        /// <summary>Gives the sleeve 8 mm more room around each elbow: bent past ~70° the elbow skin poked through the shirt.</summary>
        static void Ease(Mesh mesh, SkinnedMeshRenderer r, Animator anim)
        {
            const float Radius = 0.1f, Room = 0.008f;
            var verts = mesh.vertices;
            var bp = mesh.bindposes;
            foreach (var (lower, hb) in new[] { (HumanBodyBones.LeftLowerArm, HumanBodyBones.LeftHand), (HumanBodyBones.RightLowerArm, HumanBodyBones.RightHand) })
            {
                int fi = System.Array.IndexOf(r.bones, anim.GetBoneTransform(lower)), hi = System.Array.IndexOf(r.bones, anim.GetBoneTransform(hb));
                if (fi < 0 || hi < 0) continue;
                Vector3 elbow = bp[fi].inverse.MultiplyPoint3x4(Vector3.zero), axis = (bp[hi].inverse.MultiplyPoint3x4(Vector3.zero) - elbow).normalized;
                for (int v = 0; v < verts.Length; v++)
                {
                    float d = Vector3.Distance(verts[v], elbow);
                    if (d > Radius) continue;
                    var radial = verts[v] - (elbow + axis * Vector3.Dot(verts[v] - elbow, axis));
                    verts[v] += radial.normalized * (Room * (1f - d / Radius));
                }
            }
            mesh.vertices = verts;
            mesh.RecalculateBounds();
        }

        /// <summary>Per-vertex offsets that roll this arm's sleeve. Rolled vertices that followed the hand (the cuff) follow the
        /// forearm's wrist-end twist bone instead: rolled up to the elbow, the hand's turn swung them half a metre out.</summary>
        static Vector3[] Deltas(SkinnedMeshRenderer r, Animator anim, bool left, BoneWeight[] weights)
        {
            Transform fore = anim.GetBoneTransform(left ? HumanBodyBones.LeftLowerArm : HumanBodyBones.RightLowerArm),
                hand = anim.GetBoneTransform(left ? HumanBodyBones.LeftHand : HumanBodyBones.RightHand);
            var bones = r.bones;
            var mesh = r.sharedMesh;
            int fi = System.Array.IndexOf(bones, fore), hi = System.Array.IndexOf(bones, hand);
            if (!fore || !hand || fi < 0 || hi < 0) return null;
            var bp = mesh.bindposes;
            Vector3 elbow = bp[fi].inverse.MultiplyPoint3x4(Vector3.zero), wrist = bp[hi].inverse.MultiplyPoint3x4(Vector3.zero);
            float len = Vector3.Distance(elbow, wrist);
            var axis = (wrist - elbow) / len;
            var follows = new bool[bones.Length];  // the forearm and everything under it (twist bones, hand, fingers)
            var inHand = new bool[bones.Length];
            int cuffBone = fi;
            float cuffS = -1f;
            for (int b = 0; b < bones.Length; b++)
            {
                if (!bones[b]) continue;
                follows[b] = bones[b].IsChildOf(fore);
                inHand[b] = bones[b].IsChildOf(hand);
                float sb = Vector3.Dot(bp[b].inverse.MultiplyPoint3x4(Vector3.zero) - elbow, axis) / len;
                if (follows[b] && !inHand[b] && b != fi && sb > cuffS) { cuffS = sb; cuffBone = b; }
            }
            var verts = mesh.vertices;
            var deltas = new Vector3[verts.Length];
            int moved = 0;
            for (int v = 0; v < verts.Length; v++)
            {
                var w = weights[v];
                float wf = (follows[w.boneIndex0] ? w.weight0 : 0) + (follows[w.boneIndex1] ? w.weight1 : 0) + (follows[w.boneIndex2] ? w.weight2 : 0) + (follows[w.boneIndex3] ? w.weight3 : 0);
                if (wf < 0.5f) continue;
                float s = Vector3.Dot(verts[v] - elbow, axis) / len;
                if (s < CuffStart) continue;
                float k = Mathf.Min(s, MaxS) / MaxS;
                var radial = verts[v] - (elbow + axis * (s * len));
                // the further down the sleeve, the more cloth is piled into the cuff, so the outer layers sit thicker
                var target = elbow + axis * ((CuffStart + CuffLength * k) * len) + radial + radial.normalized * (0.004f + 0.01f * k);
                deltas[v] = target - verts[v];
                weights[v] = OffHand(w, inHand, cuffBone);
                moved++;
            }
            return moved > 0 ? deltas : null;
        }

        static BoneWeight OffHand(BoneWeight w, bool[] inHand, int to)
        {
            if (inHand[w.boneIndex0]) w.boneIndex0 = to;
            if (inHand[w.boneIndex1]) w.boneIndex1 = to;
            if (inHand[w.boneIndex2]) w.boneIndex2 = to;
            if (inHand[w.boneIndex3]) w.boneIndex3 = to;
            return w;  // shortcut: a bone can now appear twice in one vertex; Unity sums duplicate influences, which is what we want
        }

        void LateUpdate()
        {
            foreach (var (r, shape, left) in shapes) r.SetBlendShapeWeight(shape, 100f * Mathf.Clamp01(left ? Left : Right));
        }
    }
}
