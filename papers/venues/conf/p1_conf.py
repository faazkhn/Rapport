"""Build p1_brain/p1_brain_conf.tex: the 8-page IEEE conference cut of paper 1 (the journal source stays the master)."""
import sys; sys.path.insert(0, 'venues/conf')
from cut import drop_float, swap, check, conference_author

s = conference_author(open('p1_brain/p1_brain.tex').read())
for lab in ['tab:glossary', 'tab:lit', 'fig:resist', 'fig:checks', 'tab:prompt', 'tab:schema', 'fig:protocol', 'tab:seeds',
            'fig:trust', 'tab:perconv', 'fig:trustgrid', 'tab:fixes']:
    s = drop_float(s, lab)
s = swap(s, '\\subsection{Terms used in this paper}\n', '')
s = swap(s, s[s.index('\\textbf{How well can a language model hold a persona?}'):s.index('\\section{The Digital Twin}')],
 '''\\textbf{How well can a language model hold a persona?} Not well enough to trust with the patient's mind. Self-reported model personality
shifts with prompt wording and question order, and long histories make small models \\emph{less} stable \\cite{gupta2023selfassessment,tosato2025persist};
instructions drift within about eight rounds \\cite{li2024instruction}, and model size does not predict persona keeping \\cite{samuel2025personagym}.
So personality and resistance are held in code, and the model gets one style label and a few example lines.

\\textbf{How the design was chosen.} We read 83 papers on simulated patients, patient agents, learning simulators and evaluation. Five points
most of them shared became design rules: keep facts, state and locks in code and check every sentence against the case
\\cite{chen2023llmempowered,lai2025patientzero}; one model call per live turn \\cite{sabour2026patientact}; resistance designed in, with explicit
softening \\cite{steenstra2025scaffolding,lee2025psyche}; a debrief built from what the patient actually did \\cite{haut2025ai,brugge2024llm}; and
judges from another model family, with every flag checked by hand \\cite{zheng2023judging}.

''')
s = swap(s, 'by explicit rules (Fig.~\\ref{fig:resist}):', 'by explicit rules:')
s = swap(s, 'Fig.~\\ref{fig:checks} shows the checks. They run', 'The checks fix numbers, ages and names, strip apologies from an upset patient, drop near-repeats, and drop any unasked or locked mention of the death wish. They run')
s = swap(s, s[s.index('\\subsection{What the language model actually sees}'):s.index('\\textbf{Versions and rollback.}')],
 '''\\subsection{What the language model actually sees}
The prompt has a fixed part, cached for the session (role, case, presentation, rules and the menu of labels), and a short per-turn part
(state, conversation memory, open facts and the decision). The model must return a JSON object whose schema is rebuilt each turn: its list of
allowed behaviours \\emph{is} the decision, so the model cannot choose a behaviour that code did not allow. Behaviour and emotion come before the
words: decide first, then speak.

''')
s = swap(s, s[s.index('\\textbf{Versions and rollback.}'):s.index('\\section{Worked Examples}')],
 '''\\textbf{Versions.} Each change is a numbered brain version that only switches features on or off, so switching back is one command. v2 turns on
six: meaning-based recall, the decision rubric, conversation memory, sentence checks, the mental-status profile and everyday improvisation.

''')
s = swap(s, 'Fig.~\\ref{fig:protocol} summarises the method.\n\n', '')
s = swap(s, 'within\nthe spread between seeds (Fig.~\\ref{fig:heldout}, Table~\\ref{tab:seeds}).', 'within\nthe spread between seeds (Fig.~\\ref{fig:heldout}).')
s = swap(s, ' Fig.~\\ref{fig:trust} shows trust over time: with a kind doctor both versions pass the death-wish level after about\nfive turns; a judgmental doctor drives trust to zero in four.', ' With a kind doctor both versions pass the death-wish trust level after about five turns; a judgmental doctor drives trust to zero in four.')
s = swap(s, s[s.index('\\textbf{Conversation by conversation.}'):s.index('\\textbf{What the independent safety review found.}')],
 '''\\textbf{Conversation by conversation.} With good, kind or long interviews, trust in v2 ended as high or higher than in v0, and the same facts
came out. Hostile doctors drove trust to zero or near it in both. Rushed, closed questioning cost v2 more trust than v0 (22.7 vs 32.7), as it
would a real patient being hurried.

''')
s = swap(s, '\\textbf{Effect of the fixes.} Table~\\ref{tab:fixes} compares v2 as it first ran overnight with the final v2 on the same scripts and seeds. The\nthree portrayal failures were the unasked mentions of the death wish; after the fixes there were none, and accuracy rose slightly.',
 '\\textbf{Effect of the fixes.} On the same scripts and seeds, the fixes took portrayal failures from 3 to 0 and the composite from 0.937 to 0.947.')
s = swap(s, s[s.index('\\appendices'):s.index('\\section*{Acknowledgment}')],
 '''\\textbf{Reproducibility.} Patient: Gemma 4 E4B (4-bit) on llama.cpp; judge: Qwen3.5-9B; recall: bge-small-en-v1.5; one Apple M5 Pro laptop.
The scripts, case files, brain versions and every judged reply are kept with the code, so each number traces to the replies behind it.

''')
check(s)
open('p1_brain/p1_brain_conf.tex', 'w').write(s)
