using System;
using System.IO;
using System.Linq;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace Rapport.Data
{
    public class ContentException : Exception
    {
        public ContentException(string message) : base(message) { }
    }

    /// <summary>Loads data/*.json and data/cases/*.json, checks each against data/schemas, then applies ContentStatusFilter.</summary>
    public static class CaseLoader
    {
        public static ContentData LoadAll(string dataDir, bool releaseBuild)
        {
            var d = new ContentData
            {
                intents = Load<IntentList>(dataDir, "intents.json", "intents.schema.json"),
                cues = Load<CueCatalog>(dataDir, "cues.json", "cues.schema.json"),
                diagnoses = Load<DiagnosisList>(dataDir, "diagnoses.json", "diagnoses.schema.json"),
                dispositions = Load<DispositionList>(dataDir, "dispositions.json", "dispositions.schema.json"),
                formulary = Load<Formulary>(dataDir, "formulary.json", "formulary.schema.json"),
                stateRules = Load<StateRules>(dataDir, "state_rules.json", "state_rules.schema.json"),
            };
            foreach (var (file, status) in new[] { ("intents.json", d.intents.status), ("cues.json", d.cues.status), ("diagnoses.json", d.diagnoses.status),
                         ("dispositions.json", d.dispositions.status), ("formulary.json", d.formulary.status), ("state_rules.json", d.stateRules.status) })
                if (!ContentStatusFilter.Allowed(status, releaseBuild))
                    throw new ContentException($"{file}: status '{status}' is not allowed in a release build (only 'approved').");

            foreach (var path in Directory.GetFiles(Path.Combine(dataDir, "cases"), "*.json").OrderBy(p => p))
            {
                var c = Load<CaseFile>(dataDir, "cases/" + Path.GetFileName(path), "case.schema.json");
                if (ContentStatusFilter.Allowed(c.status, releaseBuild)) d.cases[c.id] = c;
            }
            return d;
        }

        /// <summary>Reads one file, validates it, and throws a ContentException naming the file and field on failure.</summary>
        public static T Load<T>(string dataDir, string rel, string schemaRel)
        {
            var json = Parse(dataDir, rel);
            var schema = (JObject)Parse(dataDir, "schemas/" + schemaRel);
            var errors = JsonSchemaLite.Validate(json, schema);
            if (errors.Count > 0) throw new ContentException($"{rel}: {string.Join("; ", errors)}");
            return json.ToObject<T>();
        }

        static JToken Parse(string dataDir, string rel)
        {
            var path = Path.Combine(dataDir, rel);
            if (!File.Exists(path)) throw new ContentException($"{rel}: file not found in {dataDir}");
            try { return JToken.Parse(File.ReadAllText(path)); }
            catch (JsonReaderException e) { throw new ContentException($"{rel}: invalid JSON at line {e.LineNumber}, position {e.LinePosition}: {e.Message}"); }
        }
    }

    /// <summary>Development builds load every status; release builds only 'approved' (DESIGN 9.1). The build preprocess step enforces it too.</summary>
    public static class ContentStatusFilter
    {
        public const string Approved = "approved";
        public static bool Allowed(string status, bool releaseBuild) => !releaseBuild || status == Approved;
    }
}
