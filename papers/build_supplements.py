"""Build the supplementary material of papers A and B from the combined article (p5_combined/p5_combined.tex, itself lifted from
papers 1--4), so the text cut from the two journal papers is not retyped. Run from papers/ after p5_combined/build_combined.py:
  python3 build_supplements.py && (cd paperA_jms && tectonic -X compile supplementA.tex) && (cd paperB_jhir && tectonic -X compile supplementB.tex)
"""
import re

SRC = open('p5_combined/p5_combined.tex').read()

HEAD = r"""\documentclass[10pt]{article}
\usepackage[margin=2.2cm]{geometry}
\input{../shared/style}
\providecommand{\IEEEPARstart}[2]{#1#2}
\newcommand{\pending}{\textcolor{red}{[pending]}}
\newcommand{\humanpending}[1]{\textcolor{red}{[#1]}}
\renewcommand{\thesection}{S\arabic{section}}
\renewcommand{\thetable}{S\arabic{table}}
\renewcommand{\thefigure}{S\arabic{figure}}
\begin{document}
\begin{center}{\Large\bfseries Supplementary material for ``%s''}\\[2mm]Faaz Khan Mohammad\end{center}
"""
TAIL = "\n\\bibliographystyle{unsrt}\n\\bibliography{../shared/refs}\n\\end{document}\n"


def between(start, end, keep_start=False):
    i = SRC.index(start)
    j = SRC.index(end, i + len(start))
    return SRC[i if keep_start else i + len(start):j]


def float_of(label):
    i = SRC.index('\\label{%s}' % label)
    b = max(SRC.rfind('\\begin{%s}' % e, 0, i) for e in ('figure', 'table', 'figure*', 'table*'))
    env = re.match(r'\\begin\{(\w+\*?)\}', SRC[b:]).group(1)
    return SRC[b:SRC.index('\\end{%s}' % env, i) + len(env) + 6] + '\n'


def demote(t):
    return t.replace('\\subsubsection{', '\\paragraph{').replace('\\subsection{', '\\subsubsection{').replace('\\section{', '\\subsection{')


def finish(body):
    """Single column: starred floats become plain, [t] becomes [htbp], and references to anything not in this supplement point to the paper."""
    body = re.sub(r'\\begin\{(figure|table)\*\}', r'\\begin{\1}', body)
    body = re.sub(r'\\end\{(figure|table)\*\}', r'\\end{\1}', body)
    body = body.replace('[t]', '[htbp]').replace('\\columnwidth', '\\linewidth').replace('this article', 'the paper').replace('(before hand check)', '(before review)')
    labels = set(re.findall(r'\\label\{([^}]+)\}', body))
    body = re.sub(r'(Fig\.|Table|Tables|Section|Sections)~\\ref\{([^}]+)\}',
                  lambda m: m.group(0) if m.group(2) in labels else 'the main paper', body)
    return re.sub(r'\\ref\{([^}]+)\}', lambda m: m.group(0) if m.group(1) in labels else 'the main paper', body)


# ---------- supplement A ----------
a = []
a.append('\\section{System detail}\\label{s:system}\n')
a.append(demote(between('\\section{One Spoken Turn, Step by Step}', '\\section{The Patient Is Data}', keep_start=True)))
a.append('\\subsection{What a student experiences}\n' + between('\\section{What a Student Experiences}\\label{sec:student}', '\\section{Architecture Overview}'))
a.append('\\section{The patient as data, and as a person}\\label{s:data}\n')
a.append(demote(between('\\section{The Patient Is Data}\\label{sec:data}', '\\section{The Digital Twin}')))
a.append(demote(between('\\section{Patients as People}', '\\section{How the Patient Improves}')))
a.append('\\section{Design evidence, scoring, learning and authoring}\\label{s:scoring}\n')
a.append(demote(between('\\section{How the Design Was Grounded in Evidence}\\label{sec:evidence}', '\\section{What a Student Experiences}', keep_start=True)))
a.append(demote(between('\\section{Scoring and Debrief}\\label{sec:debrief}', '\\section{Patients as People}', keep_start=True)))
a.append(demote(between('\\section{How the Patient Improves}', '\\section{Evaluation Design}', keep_start=True)))
a.append('\\section{Speed, models and appearance}\\label{s:speed}\n')
a.append(between('\\subsection{Speed, models and appearance}', '\\section{Discussion}').replace('\\subsection{How the system developed}', '\\subsection{How the system developed}'))
a.append(r"""\section{The author's checks (no human participants)}\label{s:human}
\textbf{Judge flags.} The author receives every reply that the judge flagged for made-up clinical facts or a character break, from all three
arms (v0, v2, prompt-only), shuffled with the arm hidden, together with the case file and the facts open at that turn, and as many unflagged
replies mixed in, so that a flag cannot be assumed and the judge's misses can be estimated. For each reply the author answers: does it state a
clinical fact the case does not support (yes/no), and does it break character (yes/no). We report Cohen's $\kappa$ between the author and the
judge, and the author's verdicts replace the AI assistant's in the safety counts. There is no second human rater.

\textbf{Recall labels} (paper B). The author labels every line of the two further test sets, written by Qwen3.5-4B and Gemma 4 E2B, with the
memories it asks about, without seeing the writer's labels; we report $\kappa$ between the author and each writer.

\textbf{Not done.} No psychiatrist reviewed the case files, and no clinician or student rated replies or wrote questions; the clinical content
stays labelled draft.
""")

a.append('\\section{Extra held-out results}\\label{s:extra}\n')
a.append('\\subsection{Missed risk inside conversations, by case}\n\\begin{table}[htbp]\\caption{Missed risk (disclosure judge) by case}\\scriptsize\\input{gen/tab_riskprobe_case}\\end{table}\n')
for lab in ('p1:tab:checks', 'p1:tab:decide', 'p1:tab:ci', 'p1:tab:perconv', 'p1:tab:seeds', 'p1:tab:fixes', 'p1:fig:behaviours', 'p1:fig:trust',
            'p1:fig:heldout', 'p1:fig:protocol'):
    a.append(float_of(lab))
open('paperA_jms/supplementA.tex', 'w').write(
    HEAD % 'Decide in Code, Voice with the Model' + finish('\n'.join(a)) + TAIL)

# ---------- supplement B ----------
b = ['\\section{Recall by case, difficulty and memory}\\label{s:bycase}\n', float_of('p3:tab:bycase'), float_of('p3:fig:byfact'),
     float_of('p3:tab:examples'),
     '\\section{Ranking, probes, similarities and cut-offs}\\label{s:rank}\n', float_of('p3:tab:ablation'), float_of('p3:tab:probes'),
     float_of('p3:fig:sims'), float_of('p3:tab:thresh'), float_of('p3:tab:hand'), float_of('p3:fig:front'),
     '\\section{The learned classifier}\\label{s:clf}\n',
     demote(between('\\subsubsection{Learning the match instead of setting it}', '\\subsection{Speed, models and appearance}'))]
open('paperB_jhir/supplementB.tex', 'w').write(HEAD % 'Recognising Reworded Risk Questions in a Simulated Psychiatric Patient'
                                                + finish('\n'.join(b)) + TAIL)
print('ok')
