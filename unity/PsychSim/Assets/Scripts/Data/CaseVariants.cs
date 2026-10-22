using System.Collections.Generic;
using System.Linq;
using System.Text.RegularExpressions;
using Newtonsoft.Json.Linq;

namespace Rapport.Data
{
    /// <summary>
    /// Sex variants (DESIGN 6.1), mirror of the service's brain.load_case: fills {name} {they} {them} {their} (capitalised
    /// placeholder = capitalised word), drops facts tagged for the other variant and copies name, sex, model and voice onto patient.
    /// </summary>
    public static class CaseVariants
    {
        static readonly Regex Tpl = new(@"\{(name|they|them|their|They|Them|Their)\}");

        static readonly Regex Slot = new(@"\{([a-z_]+)\}");

        public static string Fill(string text, CaseVariant v, IDictionary<string, string> slots)
            => Fill(slots == null ? text : Slot.Replace(text, m => slots.TryGetValue(m.Groups[1].Value, out var s) ? s : m.Value), v);

        public static string Fill(string text, CaseVariant v) => Tpl.Replace(text, m =>
        {
            var key = m.Groups[1].Value;
            var word = key == "name" ? v.name : v.pronouns[key.ToLowerInvariant()];
            return char.IsUpper(key[0]) ? char.ToUpperInvariant(word[0]) + word.Substring(1) : word;
        });

        /// <param name="slots">Slot values the service picked for a seeded patient (GET /patient); null = the authored case (option 0).</param>
        public static CaseFile Resolve(CaseFile c, string variant, IDictionary<string, string> slots = null)
        {
            if (!c.variants.TryGetValue(variant, out var v)) throw new ContentException($"{c.id}: unknown variant '{variant}'");
            slots ??= c.slots.Values.Where(o => o.Count > 0).SelectMany(o => o[0]).ToDictionary(kv => kv.Key, kv => kv.Value);
            var j = JObject.FromObject(c);
            j.Remove("variants");
            foreach (var s in j.Descendants().OfType<JValue>().Where(x => x.Type == JTokenType.String).ToList())
                s.Value = Fill((string)s.Value, v, slots);
            var r = j.ToObject<CaseFile>();
            r.variants = new Dictionary<string, CaseVariant> { [variant] = v };
            r.variant = variant;
            r.facts = r.facts.Where(f => f.variant == null || f.variant == variant).ToList();
            r.patient.name = v.name; r.patient.sex = v.sex; r.patient.model_id = v.model_id; r.patient.voice_id = v.voice_id;
            return r;
        }
    }
}
