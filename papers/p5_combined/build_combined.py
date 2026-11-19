"""Assemble p5_combined.tex, the single long journal article, from the four paper sources.

Body text is lifted verbatim from each paper; labels get a per-paper prefix (p1: ... p4:) so they cannot collide. The new
introduction, discussion and conclusion live in front.tex and back.tex. Run from papers/: python3 p5_combined/build_combined.py
"""
import re, sys
sys.path.insert(0, 'venues/conf')
from cut import check, swap

src = {k: open(f'{d}/{d}.tex').read() for k, d in
       [('p1', 'p1_brain'), ('p2', 'p2_architecture'), ('p3', 'p3_recall'), ('p4', 'p4_system')]}

def between(k, start, end, keep_start=True):
    """Text of paper k from the line `start` (kept or not) up to, not including, `end`."""
    t = src[k]; i = t.index(start); j = t.index(end, i + len(start))
    chunk = t[i if keep_start else i + len(start):j]
    chunk = re.sub(r'\\(label|ref)\{([^}]+)\}', lambda m: '\\%s{%s:%s}' % (m.group(1), k, m.group(2)), chunk)
    return chunk.replace('this paper', 'this article').replace('This paper', 'This article')

def float_of(k, label):
    t = between(k, '\\begin{document}', '\\end{document}')
    i = t.index('\\label{%s:%s}' % (k, label))
    b = max(t.rfind('\\begin{%s}' % e, 0, i) for e in ('figure', 'table', 'figure*', 'table*'))
    env = re.match(r'\\begin\{(\w+\*?)\}', t[b:]).group(1)
    return t[b:t.index('\\end{%s}' % env, i) + len(env) + 6] + '\n'

def demote(t):
    return t.replace('\\subsection{', '\\subsubsection{').replace('\\section{', '\\subsection{')

body = []
add = body.append
add('\\section{Related Work}\n\\subsection{Psychiatric AI patients, and whether they help}\n')
add(between('p4', '\\section{Related Work}', '\\section{How the Design Was Grounded', keep_start=False))
add('\\subsection{How well a language model holds a persona}\n')
add(between('p1', '\\textbf{How well can a language model hold a persona?}', '\\textbf{How the design was chosen.}')
    .replace('\\textbf{How well can a language model hold a persona?} ', ''))
add('\\subsection{Matching questions to memories}\n')
add(between('p3', '\\section{Related Work}', '\\section{How Meaning-Based Matching Works}', keep_start=False))
add(between('p4', '\\section{How the Design Was Grounded', '\\section{System}'))   # evidence base, student journey, stations

arch = between('p2', '\\section{Architecture Overview}', '\\section{Results}')
arch = swap(arch, '\\subsection{One brain for typed and spoken turns}',
            'Fig.~\\ref{p4:fig:examiner} shows the examiner view.\n\n' + float_of('p4', 'fig:examiner')
            + '\\subsection{One brain for typed and spoken turns}')
arch = swap(arch, '\\subsection{The examiner view}',
            'Fig.~\\ref{p4:fig:hands} shows an examination request from the student\'s side.\n\n' + float_of('p4', 'fig:hands')
            + '\\subsection{The examiner view}')
add(arch)

add(between('p1', '\\section{The Digital Twin}', '\\section{Validation Method}'))

add('\\section{Recalling Memories When Questions Are Reworded}\\label{sec:recall}\n')
add(between('p3', 'In the Rapport simulator, keyword matching', '\\textbf{Contributions.}'))
add(demote(between('p3', '\\section{How Meaning-Based Matching Works}', '\\section{Results}')))

add(between('p4', '\\subsection{Scoring and debrief}', '\\section{Patients as People}').replace('\\subsection{Scoring and debrief}', '\\section{Scoring and Debrief}'))
add(between('p4', '\\section{Patients as People}', '\\section{Evaluation Design}'))

add(between('p4', '\\section{Evaluation Design}', '\\section{Results}').replace('\\section{Evaluation Design}', '\\section{Evaluation Design}\\label{sec:eval}'))
add('\\subsection{Held-out validation of the Digital Twin}\n')
add(demote(between('p1', '\\section{Validation Method}', '\\section{Results}', keep_start=False)))

add('\\section{Results}\\label{sec:results}\n\\subsection{The Digital Twin}\n')
add(between('p1', '\\section{Results}', '\\section{Discussion}', keep_start=False)
    .replace('(see the companion recall paper)', '(Section~\\ref{sec:recall})'))
add('\\subsection{Recall under paraphrase}\n')
add(demote(between('p3', '\\section{Results}', '\\section{Discussion}', keep_start=False)))
add('\\subsection{Speed, models and appearance}\n')
add(demote(between('p2', '\\section{Results}', '\\section{Discussion and Limitations}', keep_start=False)))
add('\\subsection{How the system developed}\n')
add(float_of('p4', 'tab:history') + 'Table~\\ref{p4:tab:history} shows how the system developed, from the first live Digital Twin to the version evaluated here.\n\n')

front, back = open('p5_combined/front.tex').read(), open('p5_combined/back.tex').read()
out = front + '\n'.join(body) + back
for head, lab in [('How the Design Was Grounded in Evidence', 'evidence'), ('What a Student Experiences', 'student'),
                  ('Architecture Overview', 'arch'), ('The Patient Is Data', 'data'), ('Scoring and Debrief', 'debrief'),
                  ('Authoring and Content Safety', 'authoring')]:
    out = swap(out, '\\section{%s}' % head, '\\section{%s}\\label{sec:%s}' % (head, lab))
# sections that now exist once for the whole article
for a, b in [('p1:sec:model', 'sec:model'), ('p1:sec:results', 'sec:results'), ('p3:sec:results', 'sec:results'),
             ('p1:sec:method', 'sec:eval'), ('p1:sec:disc', 'sec:disc')]:
    out = out.replace('\\ref{%s}' % a, '\\ref{%s}' % b).replace('\\label{%s}' % a, '\\label{%s}' % b if b == 'sec:model' else '')
check(out)
open('p5_combined/p5_combined.tex', 'w').write(out)
print('ok', len(out.split()), 'words')
