---
title: 'Rapport: an on-device, embodied simulated psychiatric patient for interview practice'
tags:
  - Python
  - C#
  - Unity
  - medical education
  - simulated patients
  - large language models
authors:
  - name: Faaz Khan Mohammad
    affiliation: 1
affiliations:
  - name: Rapport project
    index: 1
date: 14 November 2026
bibliography: paper.bib
---

# Summary

Rapport is a spoken, three-dimensional simulated psychiatric patient that a medical student interviews out loud, as in a
psychiatry examination station (OSCE) [@harden1975osce]. Everything runs on one laptop: a Unity client shows the consulting room
and the patient's body; a Python patient service listens, recognises speech, runs the patient model and speaks; and a local language
model served by llama.cpp [@llamacpp] puts the patient's decided reply into words. The patient model, called the Digital Twin, decides
in code how the patient reacts to each doctor turn (trust, guardedness, which behaviours are allowed, which memories may be shared)
and checks every sentence before it is spoken. Patients are data: each case is a JSON file with the patient's history, memories
locked behind trust levels, a mental-status profile, visible signs, examination findings and a hidden answer key. A seed changes the
everyday details and the conversation style while the answer key stays fixed. The student can request physical examination actions,
record findings on an in-app tablet and receive a debrief scored from what the patient actually showed and said. An examiner can
watch the patient's state live in a browser.

# Statement of need

Standardised-patient actors are the usual way to practise psychiatric interviewing, but they are costly, not always available and
hard to keep consistent [@piot2021simulation]. Simulated patients built on language models now model trust-gated disclosure,
resistance and conversation styles [@wang2024patient; @lee2025psyche; @sabour2026patientact], but most are text chats that run in the
cloud, call the model several times per turn, and leave the patient's decisions inside the model where an examiner cannot inspect
them. Rapport is for medical educators and researchers who need a spoken, embodied psychiatric patient that runs privately on
hardware they own, whose behaviour can be inspected and tested, and whose cases faculty can author and review without writing code.

# Features

- One structured language-model call per spoken turn, with the reply's allowed behaviours fixed by code through a JSON schema.
- Trust-locked memories recalled by keywords and by meaning (a 33M-parameter sentence model on the CPU); locked memories never
  reach the prompt.
- Sentence checks before speech for wrong numbers or names, leaks of locked memories, unasked mentions of suicidal thoughts, and flat
  denials of an unlocked risk memory.
- Voice with emotion (Qwen3-TTS VoiceDesign, KittenTTS fallback), turn-end detection, barge-in, and body language driven by the
  patient's decided emotion.
- Rule-based recognition of examination requests (hands, forearms, eyes, tongue, gait) with inverse-kinematics animation.
- Versioned patient models with one-command rollback, an offline learning loop gated on safety checks, and a held-out evaluation
  suite.
- A debrief scored on risk assessment, observation, history, diagnosis, management and communication.

# Acknowledgements

No funding was received for this work.

# AI usage disclosure

The software, documentation and this paper were written with an AI assistant (Claude, Anthropic, used through Claude Code) under
the author's direction; the AI tools used inside the system are listed above. [Author to complete: the model versions, the parts
of the code, documentation and paper produced with AI assistance, and confirmation that the author reviewed, edited and validated
the AI-assisted outputs and made the core design decisions.]

# References
