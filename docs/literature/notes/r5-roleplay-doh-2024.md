# Roleplay-doh: Enabling Domain-Experts to Create LLM-simulated Patients via Eliciting and Adhering to Principles

- **Citation:** Louie R, Nandi A, Fang W, et al., EMNLP 2024. arXiv 2407.00870.
- **Link:** https://arxiv.org/abs/2407.00870 · **Open access:** yes (full text read)
- **Code:** https://github.com/SALT-NLP/roleplay-doh (project page https://roleplay-doh.github.io/) · **Code licence:** none found (no LICENSE file at HEAD, main or master; treat as no licence)
- **Paper licence:** arXiv non-exclusive
- **Informs:** learning, feedback/pedagogy, behaviour/resistance

## Mechanism
Experts chat with a GPT-4 AI patient and leave per-reply feedback: "kudos", "critique" or "rewrite". An LLM turns each into a general natural-language principle (what should happen and when; GPT-3.5 sufficed for kudos/critique, GPT-4 explains the diff for rewrites). Principles plus the persona go in the prompt as "write the patient's next reply", not a role-play system prompt, which reduced assistant-voice drift. Because about 20% of replies broke principles, each reply passes a critique loop: (1) rewrite each principle into yes/no questions and auto-add dialogue-convention questions (coherence, consistency, no unnatural "Hi" mid-chat); (2) an evaluator returns Yes/No/N/A per question (N/A when a conditional principle does not apply, e.g. "encouraging words" absent); any No triggers a rewrite. That is several extra LLM calls per turn.

## Evidence
- Pilot (6 counsellors): 20% (55/276) of GPT-4 replies only moderately, slightly or not at all satisfied the principles.
- Creator study, within-subjects, n=25 expert counsellors, 7-point scale, scenario-only vs scenario+principles: authenticity 5.24 to +0.80 (p<0.01), resembled past case +0.76, mirrored challenging aspects +1.00, ready as training partner +0.64 (all p<0.05); "stayed in role" unchanged (about 6.3).
- Blind third-party judges (n=5, 125 comparisons): authenticity +0.31, ready as partner +0.39 (p<0.01), 4 of 6 measures significant; smaller gains than the creators saw.
- Principle-adherence pipeline, 40 error turns, 3 expert votes, vs plain GPT-4: principle following W 35% / L 5%, consistency W 35% / L 10%, overall W 30% / L 15%; awkward-style replies 2.5% vs 15%. Naive version (no question rewriter/auto-criteria) mostly tied.
- 11.4% of generated principles needed manual editing. Principles seen: concise answers (14 patients), initial mistrust of seeking help (14), colloquial language (7), disorganised self-awareness (9); some experts wrote opposite principles (seek solutions vs only share feelings).

## Limitations
- Text only, counselling not psychiatry; patients meant for novice counsellors, with experts stopping feedback early, so principles are non-exhaustive.
- Pipeline multiplies LLM calls per turn, incompatible with live voice; the 40-case test set is small and rankings were subjective.
- Third-party agreement on which patient is better was low; principles are persona-specific, not universal.
- No licence on the repo.

## For Rapport
**Verdict:** adapt (ideas only, no licence). Maps directly to the planned faculty-principles loop: thumbs-up/down/rewrite becomes a stored, general, conditional principle ("when X, do Y") injected into the Twin prompt. Run the yes/no-question adherence critique offline in the nightly gate or evaluation suite, not live, since it adds calls; keep principles limited to style and behaviour, never clinical facts.
