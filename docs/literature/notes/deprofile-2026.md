# DEPROFILE: Synthetic or Authentic? Building Mental Patient Simulators from Longitudinal Evidence

- **Citation:** Li B, Jin B, Lan K, et al. arXiv:2603.22704, 2026
- **Link:** https://arxiv.org/abs/2603.22704 · **Open access:** yes (arXiv HTML, first 100k chars read)
- **Code:** https://github.com/Baihan-12/Deprofile · **Code licence:** none (GitHub shows no licence)
- **Paper licence:** CC BY-NC-SA 4.0
- **Informs:** identity/formulation, cross-session memory, memory and disclosure

## Mechanism
Builds multi-source patient profiles (demographics, depression and suicide risk, Big Five, symptoms, life-event timeline) from assessment dialogues, counseling dialogues and social-media histories. A Chain-of-Change agent turns posts into symptom and life-event nodes in a temporal graph, grouped into 7-day "Memory Cards" with relative timestamps for prompting.

## Evidence
3,258 skeleton profiles; datasets D4 (1,340 sessions), 300 counseling clients, Twitter-STMHD (6,803 users). Realism (MentalBERT) 0.932 vs Eeyore 0.910, Patient-Psi 0.908; G-Eval event richness 4.58 vs 3.92/4.05; human overall 3.73 vs 2.58/2.73 (8 experts, 30 profiles). Paper text and table conflict on one symptom-consistency number.

## Limitations
- Twitter-only longitudinal source, demographic skew.
- Text only; GPT-5 as judge.
- Small human study; not for clinical use.

## For Rapport
**Verdict:** idea-only. Time-grounded memory cards with citation of time point are a good model for cross-session memory in the Digital Twin; no licence and NC paper, so reimplement the idea.
