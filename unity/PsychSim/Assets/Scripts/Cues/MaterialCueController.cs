using System.Collections.Generic;
using UnityEngine;

namespace Rapport.Cues
{
    /// <summary>
    /// _Tearfulness through a MaterialPropertyBlock (no material copies): wetter tear line and eyes, slight red rim on the eye occlusion.
    /// shortcut: drives URP Lit _BaseColor/_Smoothness directly; switch to a _Tearfulness shader property when the artist's eye shader lands.
    /// </summary>
    public class MaterialCueController : MonoBehaviour
    {
        public float Tearfulness;
        readonly List<(Renderer r, int index, string kind)> slots = new();
        MaterialPropertyBlock mpb;
        float applied = -1f;
        static readonly int BaseColor = Shader.PropertyToID("_BaseColor"), Smoothness = Shader.PropertyToID("_Smoothness");

        public void Setup(Transform patient)
        {
            mpb = new MaterialPropertyBlock();
            foreach (var r in patient.GetComponentsInChildren<SkinnedMeshRenderer>())
                for (int i = 0; i < r.sharedMaterials.Length; i++)
                {
                    var n = r.sharedMaterials[i] ? r.sharedMaterials[i].name : "";
                    if (n.StartsWith("Std_Tearline")) slots.Add((r, i, "tear"));
                    else if (n.StartsWith("Std_Eye_Occlusion")) slots.Add((r, i, "rim"));
                    else if (n.StartsWith("Std_Cornea")) slots.Add((r, i, "cornea"));
                }
        }

        void LateUpdate()
        {
            if (Mathf.Abs(Tearfulness - applied) < 0.01f) return;
            applied = Tearfulness;
            float t = Tearfulness;
            foreach (var (r, i, kind) in slots)
            {
                r.GetPropertyBlock(mpb, i);
                switch (kind)
                {
                    case "tear": mpb.SetColor(BaseColor, new Color(1f, 0.92f, 0.92f, 0.55f * t)); mpb.SetFloat(Smoothness, 0.98f); break;
                    case "rim": mpb.SetColor(BaseColor, new Color(0.75f, 0.15f, 0.15f, 0.22f * t)); mpb.SetFloat(Smoothness, 0.5f); break;
                    case "cornea": mpb.SetColor(BaseColor, new Color(1f, 1f, 1f, 0.06f * t)); mpb.SetFloat(Smoothness, Mathf.Lerp(0.9f, 1f, t)); break;
                }
                r.SetPropertyBlock(mpb, i);
            }
        }
    }
}
