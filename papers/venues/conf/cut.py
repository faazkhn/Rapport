"""Helpers to cut an IEEE journal paper down to a conference copy: drop floats by label, swap text, check nothing dangles."""
import re, sys

def drop_float(s, label):
    """Remove the figure/table environment holding \\label{label}."""
    i = s.index('\\label{%s}' % label)
    b = max(s.rfind('\\begin{%s}' % e, 0, i) for e in ('figure', 'figure*', 'table', 'table*'))
    env = re.match(r'\\begin\{(\w+\*?)\}', s[b:]).group(1)
    e = s.index('\\end{%s}' % env, i) + len('\\end{%s}' % env)
    return s[:b] + s[e:].lstrip('\n')

def swap(s, old, new):
    assert old in s, 'not found: ' + old[:70]
    return s.replace(old, new)

def check(s):
    labels = set(re.findall(r'\\label\{([^}]+)\}', s))
    refs = set(re.findall(r'\\ref\{([^}]+)\}', s))
    missing = refs - labels
    assert not missing, f'dangling refs: {missing}'

def conference_author(s):
    s = re.sub(r'\\author\{.*?\}\}\n\\markboth\{.*?\}\{.*?\}\n',
               '\\\\author{\\\\IEEEauthorblockN{Faaz Khan Mohammad}\n\\\\IEEEauthorblockA{Rapport project\\\\\\\\ faazkhn1000@gmail.com}}\n', s, flags=re.S)
    return swap(s, '\\documentclass[journal]{IEEEtran}', '\\documentclass[conference]{IEEEtran}')
