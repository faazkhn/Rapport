# Glossary

- **Rapport (formerly PsychSim)**: the product, an embodied psychiatry and addiction OSCE simulator. The doctor talks out loud to a 3D patient, all on one Mac. Renamed because `usc-psychsim/psychsim` is an established research framework (ADR 0003). C# namespaces and asmdefs are `Rapport.*`; only the Unity project folder `unity/PsychSim` keeps the old name for now.
- **Digital Twin**: the patient's brain in the service (`server/patient-service`): memory with trust locks, feelings, behaviour choice, expression map. Spec: `docs/TWIN.md`.
- **Twin view**: the live web picture of the Digital Twin's state (`/twin/?live=1`).
- **Case**: one patient scenario (`StreamingAssets/data/cases/*.json`), e.g. `mdd_01`. Clinical content is draft until faculty approve it.
- **Variant**: the body and voice that play a case (`female` = Ananya, `male` = Arjun).
- **Exam action**: a physical request the doctor makes ("hold out your hands"), routed by rules in the service, played by `ExamController` in Unity.
- **Staged mode**: the service answers from a fixed script (`RAPPORT_STAGED`) for concept previews; replies are pre-scripted, not live.
