"""Build p4_system/p4_system_conf.tex: the 8-page IEEE conference cut of paper 4 (the journal source stays the master)."""
import sys; sys.path.insert(0, 'venues/conf')
from cut import drop_float, swap, check, conference_author

s = conference_author(open('p4_system/p4_system.tex').read())
for lab in ['tab:casestats', 'tab:debriefev', 'tab:history', 'tab:next', 'fig:bodies']:
    s = drop_float(s, lab)
s = swap(s, ' (Fig.~\\ref{fig:bodies})', '')
s = swap(s, 'Table~\\ref{tab:casestats} compares the four cases. In', 'In')
s = swap(s, 'Table~\\ref{tab:debriefev} links each part of the debrief to its evidence. ', '')
s = swap(s, 'Table~\\ref{tab:history} shows how the system developed.', '')
s = swap(s, 'is the next question (Table~\\ref{tab:next}), and it needs', 'is the next question, and it needs')
s = swap(s, s[s.index('\\appendices'):s.index('\\section*{Acknowledgment}')],
 '''\\textbf{Seeds and reproducibility.} A seed picks hand-written everyday details (a hobby, a brother's name, a home town) and an allowed
conversation style; the answer key, trust levels, scores and risk items never change. All held-out scripts, case files, brain versions, judge
marks and analysis scripts are kept with the code.

''')
check(s)
open('p4_system/p4_system_conf.tex', 'w').write(s)
