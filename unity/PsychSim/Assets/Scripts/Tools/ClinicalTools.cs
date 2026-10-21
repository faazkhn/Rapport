// Controllers behind the tablet panels. Views (desktop UI Toolkit now, VR tablet in Stage 5) only call these.
using System;
using System.Collections.Generic;
using System.Linq;
using Rapport.Data;
using Rapport.Scoring;

namespace Rapport.Tools
{
    /// <summary>MSE notes (DESIGN 5.2): tick boxes are cue ids grouped by cues.json mse_section, plus free text per section.</summary>
    public class MsePanel
    {
        public readonly CueCatalog Catalog;
        public readonly HashSet<string> Ticked = new();
        public readonly Dictionary<string, string> Notes = new();
        public event Action<string, string> Changed;  // (kind, id) for SessionLog

        public MsePanel(CueCatalog catalog) { Catalog = catalog; }
        public IEnumerable<string> Sections => Catalog.mse_sections;
        public IEnumerable<Cue> CuesIn(string section) => Catalog.cues.Where(c => c.mse_section == section);

        public void SetTick(string cueId, bool on)
        {
            if (!Catalog.cues.Any(c => c.id == cueId)) throw new ArgumentException($"unknown cue '{cueId}'");
            if (on ? Ticked.Add(cueId) : Ticked.Remove(cueId)) Changed?.Invoke(on ? "mse_tick" : "mse_untick", cueId);
        }

        public void SetNote(string section, string text) { Notes[section] = text; Changed?.Invoke("mse_note", section); }
    }

    /// <summary>Searchable DSM-5-TR names with ICD-11 codes; one primary plus up to three differentials.</summary>
    public class DiagnosisPicker
    {
        public const int MaxDifferentials = 3;
        public readonly DiagnosisList List;
        public string Primary { get; private set; }
        public readonly List<string> Differentials = new();
        public event Action<string, string> Changed;

        public DiagnosisPicker(DiagnosisList list) { List = list; }

        public IEnumerable<Diagnosis> Search(string query) => string.IsNullOrWhiteSpace(query) ? List.diagnoses
            : List.diagnoses.Where(d => d.dsm5tr_name.IndexOf(query, StringComparison.OrdinalIgnoreCase) >= 0 || d.icd11.StartsWith(query, StringComparison.OrdinalIgnoreCase));

        public void SetPrimary(string id)
        {
            Require(id);
            Primary = id;
            Differentials.Remove(id);
            Changed?.Invoke("dx_primary", id);
        }

        public bool AddDifferential(string id)
        {
            Require(id);
            if (id == Primary || Differentials.Contains(id) || Differentials.Count >= MaxDifferentials) return false;
            Differentials.Add(id);
            Changed?.Invoke("dx_differential", id);
            return true;
        }

        public void RemoveDifferential(string id) { if (Differentials.Remove(id)) Changed?.Invoke("dx_remove", id); }

        void Require(string id) { if (!List.diagnoses.Any(d => d.id == id)) throw new ArgumentException($"unknown diagnosis '{id}'"); }
    }

    /// <summary>Formulary drugs only; dose/route/frequency/duration/reason; checked by PrescriptionChecker.</summary>
    public class PrescriptionPad
    {
        public readonly Formulary Formulary;
        public readonly List<RxItem> Items = new();
        public event Action<string, string> Changed;

        public PrescriptionPad(Formulary f) { Formulary = f; }

        public void Add(RxItem item)
        {
            var drug = Formulary.drugs.FirstOrDefault(d => d.id == item.drug) ?? throw new ArgumentException($"'{item.drug}' is not on the formulary");
            if (string.IsNullOrEmpty(item.route)) item.route = drug.routes[0];
            if (!drug.routes.Contains(item.route)) throw new ArgumentException($"{drug.name} cannot be given {item.route}");
            Items.Add(item);
            Changed?.Invoke("rx_add", item.drug);
        }

        public void RemoveAt(int index) { var id = Items[index].drug; Items.RemoveAt(index); Changed?.Invoke("rx_remove", id); }
    }

    /// <summary>Disposition options from dispositions.json (Mental Healthcare Act 2017 basis shown with each).</summary>
    public class DispositionSelector
    {
        public readonly DispositionList List;
        public readonly List<string> Selected = new();
        public event Action<string, string> Changed;

        public DispositionSelector(DispositionList list) { List = list; }

        public void Set(string id, bool on)
        {
            if (!List.dispositions.Any(d => d.id == id)) throw new ArgumentException($"unknown disposition '{id}'");
            if (on && !Selected.Contains(id)) Selected.Add(id);
            if (!on) Selected.Remove(id);
            Changed?.Invoke(on ? "dispo_add" : "dispo_remove", id);
        }
    }
}
