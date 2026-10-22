# R2 Voigt et al.: LLM-Powered Virtual Patient Agents for Interactive Clinical Skills Training with Automated Feedback

- **Citation:** Voigt H, Sugamiya Y, Lawonn K, et al., arXiv 2025. arXiv:2508.13943
- **Link:** https://arxiv.org/abs/2508.13943 · **Open access:** yes (arXiv HTML)
- **Code:** none found · **Code licence:** none
- **Paper licence:** arXiv non-exclusive
- **Informs:** expression/embodiment, feedback/pedagogy, evaluation

## Mechanism
OSCE trainer with LLM patient and tutor agents on a ROS-inspired publish-subscribe message feed; each agent prompt has role, perception and action functions, observed variables and the feed. Patient has "action spaces" (movement, reactions) shown on a Unity WebGL avatar; tutor summarises and answers `@tutor` queries. Gemini 1.5 Flash LLM, Whisper-tiny in browser.

## Evidence
Whisper RTF tiny 0.325, base 0.567, small 1.91; LLM latency 2.07 s (Flash), 2.51 s (Pro), 14.82 s (Qwen-0.5B local). Expert study n=18 (8 physicians, 4 assistants, 6 students), ~10 min neuro exam, 1-5 scale: patient 4.38 (chat 4.78, movement 4.25, reactive behaviour 4.11); tutor 4.33.

## Limitations
- Single scenario, preliminary, subjective Likert only; no tutor scoring validation.
- Cloud LLM dependency; local models too slow.
- Struggles with multiple commands per sentence and nuanced conditions.

## For Rapport
**Verdict:** idea-only. Closest to Rapport's exam-command router and embodied patient; confirms multi-command failure and that a separate tutor feedback agent is a feasible add-on (feedback after the encounter, not in the live turn).
