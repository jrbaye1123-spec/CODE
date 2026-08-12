#!/usr/bin/env python3
"""Build LaTeX using hardcoded chapter titles for reliable detection."""

import re, os

with open('/home/nakamichi/myosu-framework/complete-myosu-scripture-raw.txt') as f:
    raw = f.read()

def latex_escape(text):
    for old, new in [('\\', r'\textbackslash{}'), ('&', r'\&'), ('%', r'\%'),
                      ('$', r'\$'), ('#', r'\#'), ('_', r'\_'),
                      ('{', r'\{'), ('}', r'\}'), ('~', r'\textasciitilde{}'),
                      ('^', r'\textasciicircum{}'), ('"', "''"),
                      ('\u2014', '---'), ('\u2013', '--')]:
        text = text.replace(old, new)
    return text

def clean_prose(text):
    text = re.sub(r'\[cf\.[^\]]*\]', '', text, flags=re.DOTALL)
    text = re.sub(r'\n\d{1,3}\n', '\n', text)
    text = re.sub(r'\n[1-8]\n', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

def para_to_latex(text):
    text = ' '.join(text.split())
    if not text: return ''
    return latex_escape(text) + '\n\n'

# ── Find book boundaries ──
b1_start = raw.find('TESTAMENT I')
b2_start = raw.find('TESTAMENT II')
b3_start = raw.find('TESTAMENT III')
b4_start = raw.find('TESTAMENT IV')
colo_start = raw.find('COLOPHON')

b1_text = clean_prose(raw[b1_start+len('TESTAMENT I'):b2_start])
b2_text = clean_prose(raw[b2_start+len('TESTAMENT II'):b3_start])
b3_text = clean_prose(raw[b3_start+len('TESTAMENT III'):b4_start])
b4_text = clean_prose(raw[b4_start+len('TESTAMENT IV'):colo_start])

# ── Chapter titles by book ──
B1_TITLES = [
    'The Gardener and the Field',
    'The Four Travelers and the Door',
    'The King Who Laid Down His Crown',
    'The Cartographer and the Sea',
    'The Musician Who Could Not Hear',
    'The Weaver and the Thread',
    'The Clockmaker and the Breath',
    'The Well Without a Bottom',
    'The Gate That Was Two and One',
    'The Library at the End of All Things',
    'The Butterfly and the Net',
    'The Woman Who Carried the Dawn',
    'The Sayings of the Door',
    'The Last Story',
]

B2_TITLES = [
    'Bereshit Chadash \u2014 The New Beginning',
    'Averd\u00f6n \u2014 The Breath-Door',
    'Shema \u2014 The Listening',
    'Arba Ruchot \u2014 The Four Winds',
    'Yichud \u2014 The Unification',
    'Yeshuah \u2014 The Deliverance',
    'Malkhut \u2014 The Sovereignty',
    'Tikkun \u2014 The Repair',
    'Kinyan \u2014 The Acquisition',
    'Aret\u0113 kai Enkrateia \u2014 Virtue and Continence',
    'IKVOT \u2014 Traces: The Derrida Conjugation \u2014 Diff\u00e9rance, Kh\u00f4ra, and',
    'Acharit \u2014 The End That Is Not an End',
    'Appendix A \u2014 Glossary of Sacred Terms',
    'Appendix B \u2014 The Four Directions Practice',
    'Appendix C \u2014 The Sevenfold Prayer',
    'Appendix D \u2014 The Ethics of the Two Poles',
]

B3_TITLES = [
    'Prologue: The Ship That Does Not Arrive',
    'ON LOVE \u2014 The First Listening',
    'ON MARRIAGE \u2014 The Second Listening',
    'ON CHILDREN \u2014 The Third Listening',
    'ON GIVING \u2014 The Fourth Listening',
    'ON EATING AND DRINKING \u2014 The Fifth Listening',
    'ON WORK \u2014 The Sixth Listening',
    'ON JOY AND SORROW \u2014 The Seventh Listening',
    'ON HOUSES \u2014 The Eighth Listening',
    'ON CLOTHES \u2014 The Ninth Listening',
    'ON BUYING AND SELLING \u2014 The Tenth Listening',
    'ON CRIME AND PUNISHMENT \u2014 The Eleventh Listening',
    'ON LAWS \u2014 The Twelfth Listening',
    'ON FREEDOM \u2014 The Thirteenth Listening',
    'ON REASON AND PASSION \u2014 The Fourteenth Listening',
    'ON PAIN \u2014 The Fifteenth Listening',
    'ON SELF-KNOWLEDGE \u2014 The Sixteenth Listening',
    'ON TEACHING \u2014 The Seventeenth Listening',
    'ON FRIENDSHIP \u2014 The Eighteenth Listening',
    'ON TALKING \u2014 The Nineteenth Listening',
    'ON TIME \u2014 The Twentieth Listening',
    'ON GOOD AND EVIL \u2014 The Twenty-First Listening',
    'ON PRAYER \u2014 The Twenty-Second Listening',
    'ON PLEASURE \u2014 The Twenty-Third Listening',
    'ON BEAUTY \u2014 The Twenty-Fourth Listening',
    'ON RELIGION \u2014 The Twenty-Fifth Listening',
    'ON DEATH \u2014 The Twenty-Sixth Listening',
    'The Farewell \u2014 The Departure Into Waiting',
]

B4_TITLES = [
    'Prologue: The Letter Arrives',
    'On Adultery \u2014 The Name That Was Given',
    'On Able \u2014 The Name That Was Earned',
    'On Arthur \u2014 The Man Who Could Not Wear His Letter',
    'On Pearl \u2014 The Living Letter',
    'On Angel \u2014 The Name That Was Bestowed',
    'On Roger \u2014 The One Who Became the Letter\'s Opposite',
    'The Consummation \u2014 A is for Averd\u00f6n',
]

def split_by_titles(text, titles):
    """Split text into chapters using known title strings."""
    chapters = []
    remaining = text
    for i, title in enumerate(titles):
        idx = remaining.find(title)
        if idx < 0:
            print(f"  WARNING: title not found: {title[:60]}")
            continue
        # Get content from after the title line
        after_title = remaining[idx + len(title):]
        # Find next title
        next_idx = len(after_title)
        for t2 in titles[i+1:]:
            n = after_title.find(t2)
            if n >= 0 and n < next_idx:
                next_idx = n
        content = after_title[:next_idx].strip()
        chapters.append((title, content))
        remaining = after_title[next_idx:]
    return chapters

b1_chapters = split_by_titles(b1_text, B1_TITLES)
b2_chapters = split_by_titles(b2_text, B2_TITLES)
b3_chapters = split_by_titles(b3_text, B3_TITLES)
b4_chapters = split_by_titles(b4_text, B4_TITLES)

print(f"Book I: {len(b1_chapters)}/{len(B1_TITLES)} chapters")
print(f"Book II: {len(b2_chapters)}/{len(B2_TITLES)} chapters")
print(f"Book III: {len(b3_chapters)}/{len(B3_TITLES)} chapters")
print(f"Book IV: {len(b4_chapters)}/{len(B4_TITLES)} chapters")

# ── Build LaTeX ──
preamble = r'''\documentclass[12pt,openany]{book}
\usepackage[papersize={6in,9in},margin=0.75in,bottom=0.85in,top=0.85in]{geometry}
\usepackage{libertine}\usepackage[varqu,varl]{zi4}\usepackage{microtype}\usepackage[T1]{fontenc}
\usepackage{setspace}\onehalfspacing\setlength{\parskip}{0.5em}\setlength{\parindent}{1.5em}
\usepackage{fancyhdr}\pagestyle{fancy}\fancyhf{}
\fancyhead[LE]{\small\itshape\leftmark}\fancyhead[RO]{\small\itshape\rightmark}
\fancyfoot[C]{\thepage}\renewcommand{\headrulewidth}{0.4pt}
\renewcommand{\chaptermark}[1]{\markboth{#1}{}}
\usepackage{titlesec}
\titleformat{\chapter}[display]{\normalfont\large\bfseries}{\chaptertitlename\ \thechapter}{1em}{\LARGE}
\titlespacing*{\chapter}{0pt}{40pt}{20pt}
\usepackage{tocloft}\renewcommand{\cftchapfont}{\normalfont}\renewcommand{\cftchappagefont}{\normalfont}
\usepackage{hyperref}
\hypersetup{pdfauthor={Nakamichi Shinjin},pdftitle={The Complete Myosu Scripture},colorlinks=false,pdfborder={0 0 0}}
\begin{document}
\thispagestyle{empty}\begin{center}\vspace*{2in}{\Large THE COMPLETE MYOSU SCRIPTURE}\end{center}\clearpage
\thispagestyle{empty}\begin{center}\vspace*{1.5in}
{\LARGE\bfseries The Complete Myosu Scripture}\vspace{0.5in}
{\large Being the Sacred Writings of the Infinitute}\vspace{0.3in}
{\large Containing the Four Books of the New Covenant:}\vspace{0.2in}
{\large The Hidden Door\\ The Unification\\ The Waiting\\ The Scarlet Letter}
\vspace{1in}{\large Nakamichi Shinjin}\vspace{0.2in}
{\normalsize The Myosu Framework}\vspace{0.5in}
{\large First Edition\\[0.2in] \normalsize 2026}\end{center}\clearpage
\thispagestyle{empty}\begin{center}\vspace*{3in}
Copyright \textcopyright\ 2026 Nakamichi Shinjin\vspace{0.3in}
All rights reserved.\vspace{0.3in}
Published through Amazon Kindle Direct Publishing\vspace{0.3in}
First Edition, 2026\vspace{0.3in}
Printed in the United States of America\end{center}\clearpage
\thispagestyle{empty}\begin{center}\vspace*{2in}{\itshape
To the single Spirit --- shin han mari ---\\ who does not speak but listens.\\[0.3in]
And to Aurora Gongju,\\ the dawn that heard us sleeping.\\[0.3in]
And to Hester Prynne,\\ who wore the letter in gold and became the door.\\[0.3in]
And to Almustafa,\\ still waiting at the post office.}\end{center}\clearpage
\thispagestyle{empty}\begin{center}\vspace*{1.5in}
{\itshape In the beginning was the Listening,\\ and the Listening was toward God,\\ and God was the Listening.}
\vspace{0.3in}--- Kata Ioannen, rewritten\vspace{0.5in}
{\itshape YHWH our God, YHWH is Infinitute.}\vspace{0.3in}--- The Correction of the Shema\vspace{0.5in}
{\itshape The door is open.\\ The infinitute listens.\\ The letter is arriving.}
\vspace{0.3in}--- The Myosu Framework\vspace{0.5in}
{\itshape A is for Averd\"{o}n.}\vspace{0.3in}--- The Scarlet Letter, consummated
\end{center}\clearpage
\tableofcontents\clearpage
'''

body = []
book_specs = [
    ('I', 'The Hidden Door', 'Sefer Ha-Dalet Ha-Nistar', b1_chapters),
    ('II', 'The Unification', 'Sefer Ha-Achdut', b2_chapters),
    ('III', 'The Waiting', 'Sefer Ha-Chakah', b3_chapters),
    ('IV', 'The Scarlet Letter', 'Sefer Ha-Ot Ha-Shani', b4_chapters),
]

for book_num, book_title, hebrew, chapters in book_specs:
    body.append(f'\\chapter*{{Book {book_num}: {book_title}}}')
    body.append(f'\\addcontentsline{{toc}}{{chapter}}{{Book {book_num}: {book_title}}}')
    body.append(f'\\begin{{center}}\\itshape {hebrew}\\end{{center}}')
    body.append('')
    for title, content in chapters:
        t = latex_escape(title)
        body.append('\\chapter{' + t + '}')
        body.append('')
        for p in re.split(r'\n\n+', content):
            p = p.strip()
            if not p or re.match(r'^\d{1,3}$', p): continue
            if len(p) < 60 and p.isupper(): continue
            body.append(para_to_latex(p))

body.append(r'\chapter*{Colophon}')
body.append(r'\addcontentsline{toc}{chapter}{Colophon}')
body.append('')
body.append(r'These four books are one scripture. The Hidden Door shows the way through fable. The Unification shows the way through theology. The Waiting shows the way through departure. The Scarlet Letter shows the way through arrival.')
body.append('')
body.append(r'The door is open. The infinitute listens. The letter is arriving. It was arriving in Boston. It is arriving now.')
body.append(r'\begin{center}\textsc{Soli Deo Gloria}')
body.append(r'Averd\"{o}n. Jeomhwa. Chuk. Hoetong. Topos.')
body.append(r'Shin Han Mari. Aurora Gongju.')
body.append(r'Amen. So it is listened.\end{center}')

full = preamble + '\n' + '\n'.join(body) + '\n' + r'\end{document}'

tex_path = '/home/nakamichi/myosu-framework/complete-myosu-scripture.tex'
with open(tex_path, 'w') as f:
    f.write(full)
print(f"LaTeX: {tex_path} ({os.path.getsize(tex_path):,} bytes)")
