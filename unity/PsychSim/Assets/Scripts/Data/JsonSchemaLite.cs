using System.Collections.Generic;
using System.Linq;
using System.Text.RegularExpressions;
using Newtonsoft.Json.Linq;

namespace PsychSim.Data
{
    /// <summary>
    /// Validates JSON against the subset of JSON Schema 2020-12 our schemas in data/schemas use
    /// (type, enum, const, required, properties, additionalProperties, items, min/maxItems, uniqueItems,
    /// minLength, pattern, minimum, maximum, exclusiveMinimum, minProperties, local $ref).
    /// shortcut: not a full validator (no anyOf/oneOf/if); add keywords here when a schema starts using them.
    /// </summary>
    public static class JsonSchemaLite
    {
        public static List<string> Validate(JToken data, JObject schema)
        {
            var errors = new List<string>();
            Check(data, schema, schema, "$", errors);
            return errors;
        }

        static void Check(JToken v, JObject s, JObject root, string path, List<string> err)
        {
            if (s["$ref"] is JValue r)
            {
                JToken target = root;
                foreach (var seg in ((string)r).TrimStart('#').Split('/', System.StringSplitOptions.RemoveEmptyEntries)) target = target?[seg];
                if (target is not JObject t0) { err.Add($"{path}: schema $ref '{r}' not found"); return; }
                Check(v, t0, root, path, err);
            }

            if (s["type"] is JToken t)
            {
                var types = t.Type == JTokenType.Array ? t.Values<string>().ToList() : new List<string> { (string)t };
                if (!types.Any(x => IsType(v, x))) { err.Add($"{path}: expected {string.Join(" or ", types)}, got {Describe(v)}"); return; }
            }
            if (s["enum"] is JArray en && !en.Any(e => JToken.DeepEquals(e, v)))
                err.Add($"{path}: value {Describe(v)} is not one of [{string.Join(", ", en.Select(e => e.ToString(Newtonsoft.Json.Formatting.None)))}]");
            if (s["const"] is JToken c && !JToken.DeepEquals(c, v)) err.Add($"{path}: must be {c}");

            if (v is JObject o)
            {
                foreach (var req in s["required"]?.Values<string>() ?? Enumerable.Empty<string>())
                    if (!o.ContainsKey(req)) err.Add($"{path}: missing required field '{req}'");
                if (s["minProperties"] != null && o.Count < (int)s["minProperties"]) err.Add($"{path}: needs at least {s["minProperties"]} fields");
                var props = s["properties"] as JObject;
                foreach (var p in o.Properties())
                {
                    var sub = props?[p.Name] as JObject;
                    if (sub != null) Check(p.Value, sub, root, $"{path}.{p.Name}", err);
                    else if (s["additionalProperties"] is JObject addl) Check(p.Value, addl, root, $"{path}.{p.Name}", err);
                    else if (s["additionalProperties"]?.Type == JTokenType.Boolean && !(bool)s["additionalProperties"]) err.Add($"{path}.{p.Name}: unknown field");
                }
            }
            else if (v is JArray a)
            {
                if (s["minItems"] != null && a.Count < (int)s["minItems"]) err.Add($"{path}: needs at least {s["minItems"]} items");
                if (s["maxItems"] != null && a.Count > (int)s["maxItems"]) err.Add($"{path}: at most {s["maxItems"]} items");
                if (s["uniqueItems"]?.Value<bool>() == true && a.Select(x => x.ToString()).Distinct().Count() != a.Count) err.Add($"{path}: items must be unique");
                if (s["items"] is JObject items) for (int i = 0; i < a.Count; i++) Check(a[i], items, root, $"{path}[{i}]", err);
            }
            else if (v.Type == JTokenType.String)
            {
                var str = (string)v;
                if (s["minLength"] != null && str.Length < (int)s["minLength"]) err.Add($"{path}: must not be empty");
                if (s["pattern"] != null && !Regex.IsMatch(str, (string)s["pattern"])) err.Add($"{path}: '{str}' does not match {s["pattern"]}");
            }
            else if (v.Type == JTokenType.Integer || v.Type == JTokenType.Float)
            {
                var d = (double)v;
                if (s["minimum"] != null && d < (double)s["minimum"]) err.Add($"{path}: {d} is below the minimum {s["minimum"]}");
                if (s["maximum"] != null && d > (double)s["maximum"]) err.Add($"{path}: {d} is above the maximum {s["maximum"]}");
                if (s["exclusiveMinimum"] != null && d <= (double)s["exclusiveMinimum"]) err.Add($"{path}: must be greater than {s["exclusiveMinimum"]}");
            }
        }

        static bool IsType(JToken v, string t) => t switch
        {
            "object" => v.Type == JTokenType.Object,
            "array" => v.Type == JTokenType.Array,
            "string" => v.Type == JTokenType.String,
            "integer" => v.Type == JTokenType.Integer || (v.Type == JTokenType.Float && (double)v % 1 == 0),
            "number" => v.Type == JTokenType.Integer || v.Type == JTokenType.Float,
            "boolean" => v.Type == JTokenType.Boolean,
            "null" => v.Type == JTokenType.Null,
            _ => false,
        };

        static string Describe(JToken v) => v.Type == JTokenType.String ? $"'{v}'" : v.Type == JTokenType.Null ? "null" : v.Type.ToString().ToLowerInvariant();
    }
}
