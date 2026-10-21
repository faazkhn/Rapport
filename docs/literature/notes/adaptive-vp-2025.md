# Adaptive-VP: A Framework for LLM-Based Virtual Patients that Adapts to Trainees' Dialogue to Facilitate Nurse Communication Training

- **Citation:** Lee K, Lee S, Kim E H, et al., Findings of ACL 2025, pp. 2319-2352. DOI 10.18653/v1/2025.findings-acl.118
- **Link:** https://aclanthology.org/2025.findings-acl.118/ · **Open access:** yes (full text read)
- **Code:** https://github.com/keyeun/adaptive-vp (repo exists; code and data) · **Code licence:** none found (no LICENSE file at HEAD, main or master); ideas only
- **Paper licence:** CC BY 4.0 (ACL Anthology default, believed)
- **Informs:** behaviour/resistance, affect, evaluation, feedback/pedagogy

## Mechanism
Claude 3.5 Sonnet throughout; four modules per turn. (1) Evaluation: three LLM judges (nursing professor, communication-skills trainer, clinical psychologist; unanimity required for a positive) score each trainee utterance for Tone (calm and clear +1), Empathy (ECCS level >=3 +1), Prohibited behaviours (premature empathy, invalidating beliefs, dismissive commands, -1), and the conversation for de-escalation (autonomy, limit-setting, problem-solving/reframing, +1 each if used once), giving a 0-5 score. (2) Dynamic Adjustment: a lookup (Table 8) maps the score to three directions: communication style (0 = maximal intensification of the profile's negative traits ... 5 = slight), complaint intensity, responsiveness to the nurse; shifts are clamped to stay within the persona. (3) Dialogue generation returns three tags: inner monologue (hidden), spoken reply, non-verbal cue. (4) Safety monitor checks the draft against four criteria (not excessively hostile, aligned with training goal, consistent with profile, follows the direction) and sends it back for revision with feedback if it fails. Cases come from a five-step pipeline with expert review and 7 communication-trait styles. This is 5+ LLM calls per turn.

## Evidence
- Case validation, 10 nurses (avg 7 yrs): realism 3.81/5, accuracy 4.00/5 for 8 draft scenarios (4 challenging-patient types x 2), revised after interviews.
- Evaluator validity: 15 experienced vs 15 novice nurses, 8 VP chats each, first 5 utterances: experts scored higher (Mann-Whitney U=160960, p=0.001); three judges agreed at Fleiss kappa >0.75; judge roles differed systematically (psychologist scored tone higher, p<0.001).
- Human evaluation, 28 experienced nurses, between-subjects (14 static, 14 dynamic), 8 VPs each: Dynamic beat Static on Role Fidelity F(1,25.4)=4.52, p=.043, eta2p=0.151 and Conversational Realism F(1,24.7)=8.421, p=.008, eta2p=0.254. No effect of patient type. Static patients "should calm down" when the nurse does well.
- No learning-outcome data.

## Limitations
- Korean nursing, Claude 3.5 only, 28 raters; measures realism, not whether trainees improve.
- Many LLM calls per turn (3 judges, generator, safety) is incompatible with live voice.
- Text only; the score-to-direction table is hand-written, with no test of its calibration beyond realism ratings.
- No licence on the repo.

## For Rapport
**Verdict:** adapt (ideas only). Their score-to-direction table is the same idea as Rapport's trust and resistance state: a rule (code) turns the doctor's last move into a clamped step on patient hostility, which the single LLM call then voices; the paper's human result (dynamic > static on realism) supports it. Take the utterance/conversation rubric (calm and clear, empathy level, premature empathy, invalidation, autonomy, limit-setting) as the trigger set for trust updates and for the evaluation suite, and the hidden inner-monologue field as an extra slot in the structured reply. Run the multi-judge and safety checks offline or as a cheap rule, not live.
