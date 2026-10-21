# 3. Rename PsychSim to Rapport

Date: 2026-10-21 · Status: accepted

## Context

`usc-psychsim/psychsim` is an established USC research framework with the same name. The owner chose **Rapport** for the product and **Digital Twin** for the patient's brain.

## Decision

- GitHub repo `faazkhn/PsychSim` → `faazkhn/Rapport` (GitHub redirects the old URL).
- User-facing names change: Unity product name `Rapport`, bundle id `com.faazkhn.rapport`, build `Builds/Rapport.app`, launcher `Rapport.command`, editor menus `Rapport/…`, service title, logs `~/Library/Logs/Rapport`.
- Environment variables are `RAPPORT_*`. The old `PSYCHSIM_*` names still work as deprecated aliases until v0.3 (`brain.env`, `run.sh`).
- Not renamed: the Unity project folder `unity/PsychSim`, the `PsychSim.*` C# namespaces and asmdefs. Renaming them touches every script, scene reference and test assembly for no user-visible gain; tracked as a follow-up issue.

## Consequences

- The new product name moves Unity's `persistentDataPath`, so session logs now go to `~/Library/Application Support/<company>/Rapport/sessions`. Older logs stay in the `PsychSim` folder.
- The new bundle id asks for microphone permission again on first launch.
- Old demo files keep their names (`demo/PsychSim_demo_v*.mp4`).
