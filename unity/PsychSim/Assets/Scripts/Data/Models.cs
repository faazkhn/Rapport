// Schema-backed models for StreamingAssets/data. Field names match the JSON (snake_case) so no mapping layer is needed.
using System.Collections.Generic;
using Newtonsoft.Json.Linq;

namespace Rapport.Data
{
    public class CaseFile
    {
        public string id, title, version, status, setting, content_note, referral_note, verified_by;
        public List<string> authors = new(), reviewed_by = new();
        public float? time_limit_min;
        public PatientInfo patient;
        public Dictionary<string, float> state_start = new(), state_drift_per_min = new();
        public List<Fact> facts = new();
        public List<CaseCue> cues = new();
        public JObject exam, scales;
        public List<string> fallback_lines = new();
        public AnswerKey answer_key;
        // v0.3 (DESIGN 6.1)
        public string style, variant;  // variant: set by CaseVariants.Resolve
        public List<string> banned_words = new(), principles = new();
        public JObject behavior;
        public JToken rubric;
        public Dictionary<string, CaseVariant> variants = new();
        public Dictionary<string, ExamActionRule> exam_actions = new();
    }

    public class CaseVariant
    {
        public string name, sex, model_id, voice_id;
        public Dictionary<string, string> pronouns = new();
    }

    public class ExamActionRule { public float trust_min; public string refusal_line; }

    public class PatientInfo
    {
        public string name, sex, model_id, variant, voice_id, background, personality, speech_style;
        public int age;
        public float voice_speed = 1f;
    }

    public class Fact
    {
        public string id, text, variant;
        public float trust_min;
        public bool volunteered, must_be_asked;
        public List<string> unlock_intents = new();
    }

    public class CaseCue
    {
        public string id;
        public float @base, trust_gain, distress_gain, agitation_gain, engagement_gain, time_gain_per_min;
        public List<string> on_facts = new();
        public float? event_boost, event_duration_s;
    }

    public class AnswerKey
    {
        public List<string> primary_dx = new(), acceptable_differentials = new(), required_intents = new(), required_cues_noted = new(),
            acceptable_disposition = new(), required_disposition = new();
        public List<AcceptableRx> acceptable_rx = new();
        public List<UnsafeRx> unsafe_rx = new();
        public TeachingPoints teaching_points;
        public Dictionary<string, MseExpected> mse_expected = new();
    }

    public class AcceptableRx { public string drug, note; public bool required; }
    public class UnsafeRx { public string drug, drug_class, rule, why; }
    public class TeachingPoints { public string status, verified_by; public List<string> items = new(); }
    public class MseExpected { public List<string> cues = new(); public string note; }

    public class Intent { public string id, description; public bool is_risk, negative; }
    public class IntentList { public string status; public List<Intent> intents = new(); }

    public class Cue { public string id, name, meaning, mse_section; public List<string> method = new(); public bool in_slice; }
    public class CueCatalog { public string status; public List<string> mse_sections = new(); public List<Cue> cues = new(); }

    public class Diagnosis { public string id, dsm5tr_name, icd11, icd10; }
    public class DiagnosisList { public string status; public List<Diagnosis> diagnoses = new(); }

    public class Disposition { public string id, name, description, mhca_basis; }
    public class DispositionList { public string status; public List<Disposition> dispositions = new(); }

    public class DoseRange { public float? min, max; }
    public class Drug
    {
        public string id, name, @class, source, verified_by;
        public List<string> routes = new(), contraindication_rules = new(), interaction_rules = new();
        public DoseRange dose_range_mg = new();
    }
    public class FormularyRule { public string id, kind, severity, description; }
    public class Formulary { public string status; public List<FormularyRule> rules = new(); public List<Drug> drugs = new(); }

    public class ValueRange { public float min, max; }
    public class StateRules
    {
        public string status;
        public float clamp_per_turn = 10;
        public ValueRange range = new() { min = 0, max = 100 };
        public Dictionary<string, Dictionary<string, float>> intent_nudges = new();
    }

    /// <summary>Everything CaseLoader loads, already schema-checked and status-filtered.</summary>
    public class ContentData
    {
        public IntentList intents;
        public CueCatalog cues;
        public DiagnosisList diagnoses;
        public DispositionList dispositions;
        public Formulary formulary;
        public StateRules stateRules;
        public Dictionary<string, CaseFile> cases = new();
    }
}
