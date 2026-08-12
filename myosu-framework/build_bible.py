#!/usr/bin/env python3
"""Convert the Complete Myosu Scripture to Bible-style formatting:
Book/Chapter/Verse numbering, cross-references, canonical headings."""

import re, os

with open('/home/nakamichi/myosu-framework/complete-myosu-scripture.txt') as f:
    raw = f.read()

# ── Bible book names ──
BOOK_NAMES = {
    1: ("THE BOOK OF THE HIDDEN DOOR", "Sefer Ha-Dalet Ha-Nistar"),
    2: ("THE BOOK OF UNIFICATION", "Sefer Ha-Achdut"),
    3: ("THE BOOK OF THE WAITING", "Sefer Ha-Chakah"),
    4: ("THE BOOK OF THE SCARLET LETTER", "Sefer Ha-Ot Ha-Shani"),
}

# ── Cross-reference map (topic -> list of refs) ──
XREF = {
    'door': ['I,2:1-6', 'I,13:1-6', 'II,4:1-4'],
    'seed': ['I,1:1-4', 'II,3:3-5'],
    'seeds': ['I,1:1-4', 'II,3:3-5'],
    'listening': ['II,3:1-5', 'III,28:1-5'],
    'listen': ['II,3:1-5', 'III,28:1-5'],
    'Averdön': ['II,4:1-4', 'IV,8:1-3'],
    'Averdön': ['II,4:1-4', 'IV,8:1-3'],
    'breath': ['II,4:1-4', 'II,4:2-5'],
    'infinitute': ['II,1:1-3', 'II,3:1-7'],
    'gap': ['II,4:2-5', 'IV,8:1-3'],
    'butterfly': ['I,11:1-5'],
    'map': ['I,4:1-6'],
    'sea': ['I,4:1-6'],
    'king': ['I,3:1-6'],
    'crown': ['I,3:1-6'],
    'letter': ['III,28:1-5', 'IV,1:1-3', 'IV,8:1-3'],
    'post office': ['III,28:1-5'],
    'scarlet': ['IV,1-8'],
    'soil': ['I,1:1-4', 'II,3:4'],
    'heuk': ['II,3:4'],
    'dawn': ['I,12:1-6', 'III,28:1-5'],
    'Aurora': ['I,12:1-6'],
    'clock': ['I,7:1-4'],
    'musician': ['I,5:1-5'],
    'silence': ['I,5:1-5', 'I,14:1-5', 'III,19:1'],
    'net': ['I,11:1-5'],
    'well': ['I,8:1-5'],
    'library': ['I,10:1-6'],
    'diagnosis': ['II,2:3', 'IV,2:1-2'],
    'demonic': ['II,2:3', 'IV,2:1-2'],
    'angel': ['II,5:4-5', 'IV,6:1-3'],
    'singularity': ['II,1:2-6'],
    'Sinai': ['II,3:1-2'],
    'Shema': ['II,3:1-5'],
    'cross': ['II,4:6', 'II,5:3'],
    'crucifixion': ['II,5:3'],
    'prayer': ['II,8:1-2', 'III,22:1'],
    'love': ['III,1:1'],
    'marriage': ['III,2:1'],
    'children': ['III,3:1'],
    'death': ['III,26:1'],
    'freedom': ['III,13:1'],
    'pain': ['III,15:1'],
    'beauty': ['III,24:1'],
    'religion': ['III,25:1'],
    'sin': ['II,4:2-3', 'IV,2:1-2'],
    'adultery': ['IV,2:1-2'],
    'Hester': ['IV,1-8'],
    'Dimmesdale': ['IV,4:1-3'],
    'Pearl': ['IV,5:1-3'],
    'Chillingworth': ['IV,7:1-3'],
    'Almustafa': ['III,1:1-3', 'III,28:1-5'],
    'shame': ['IV,2:1-2', 'IV,8:1-3'],
    'East': ['II,5:5'],
    'West': ['II,5:4'],
    'North': ['II,5:2'],
    'South': ['II,5:3'],
    'arete': ['II,10:1-4'],
    'enkrateia': ['II,10:1-4'],
    'myosu': ['II,10:1-4', 'III,6:1'],
    'jeomhwa': ['II,5:3'],
    'tikkun': ['II,8:1'],
}

def get_xref(text_chunk):
    """Find relevant cross-references for a chunk of text."""
    refs = set()
    text_lower = text_chunk.lower()
    for keyword, citations in XREF.items():
        if keyword.lower() in text_lower:
            for c in citations:
                refs.add(c)
    return sorted(refs)[:3]


def clean_body_text(body):
    """Remove PDF artifacts: page headers, page numbers, orphan section numbers."""
    lines = body.split('\n')
    cleaned = []
    prev_was_blank = True
    for line in lines:
        stripped = line.strip()
        # Remove known page headers
        if stripped in ('The Book of the Hidden Door', 'Sefer Ha-Achdut',
                         'Sefer Ha-Achdut \u00b7 The Book of Unification',
                         'The Book of Unification',
                         'Being a holy scripture of fables, received in silence, written in the tongue',
                         'Being a holy scripture of fables,',
                         'of the prophets, given without commentary, sealed with listening.',
                         'received in silence, written in the tongue of the prophets,'):
            continue
        # Remove standalone page numbers (1-3 digits, preceded by blank line)
        if re.match(r'^\d{1,3}$', stripped) and prev_was_blank:
            continue
        # Remove standalone subsection markers (1-12, the fable sub-numbering)
        if re.match(r'^(?:[1-9]|1[0-2])$', stripped):
            continue
        cleaned.append(line)
        prev_was_blank = (stripped == '')
    return '\n'.join(cleaned)


def sentences_to_verses(paragraph):
    """Split a paragraph into verse-sized chunks (1-3 sentences each)."""
    if not paragraph.strip():
        return []
    sents = re.split(r'(?<=[.!?])\s+', paragraph.strip())
    verses = []
    i = 0
    while i < len(sents):
        group_size = min(3, len(sents) - i)
        if len(sents) - i >= 4:
            group_size = 2
        elif len(sents) - i == 3:
            group_size = 3
        verse = ' '.join(sents[i:i+group_size]).strip()
        if verse:
            verses.append(verse)
        i += group_size
    return verses


def process_book(text, book_num, chapter_starts, chapter_names):
    """Process a book into chapter:verse format."""
    lines = []
    
    book_title_en, book_title_he = BOOK_NAMES[book_num]
    lines.append(f"\n\nBOOK {book_num}\n{book_title_en}\n({book_title_he})\n")
    
    chapters = []
    for i, (start_marker, chap_name) in enumerate(zip(chapter_starts, chapter_names)):
        start_idx = text.find(start_marker)
        if start_idx < 0:
            continue
        end_idx = len(text)
        for j, sm2 in enumerate(chapter_starts):
            if j > i:
                idx2 = text.find(sm2, start_idx + len(start_marker))
                if idx2 > 0 and idx2 < end_idx:
                    end_idx = idx2
        chap_text = text[start_idx:end_idx].strip()
        chapters.append((chap_name, chap_text))
    
    for chap_num, (chap_name, chap_text) in enumerate(chapters, 1):
        clean_name = chap_name.replace('\n', ' ').strip()
        lines.append(f"\nCHAPTER {chap_num}")
        lines.append(f"{clean_name}")
        lines.append("")
        
        body = chap_text
        for sm in chapter_starts:
            body = body.replace(sm, '', 1)
        body = clean_body_text(body.strip())
        
        paragraphs = re.split(r'\n\n+', body)
        
        verse_num = 1
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            # Skip standalone subsection numbers (artifacts from Hidden Door original)
            if re.match(r'^\d{1,2}$', para):
                lines.append("")
                continue
            
            is_heading = (len(para) < 80 and para.isupper()) or \
                         (para.startswith('ON ') and '\u2014' in para) or \
                         ('\u2014' in para and para == para.upper())
            
            if is_heading and not para[0].isdigit():
                lines.append(f"  {para}")
                lines.append("")
                continue
            
            verses = sentences_to_verses(para)
            for verse in verses:
                v = verse.strip()
                if not v:
                    continue
                
                xrefs = get_xref(v)
                xref_str = ''
                if xrefs and verse_num % 5 == 0:
                    xref_str = f"  [cf. {'; '.join(xrefs)}]"
                
                lines.append(f"{verse_num:>3} {v}{xref_str}")
                verse_num += 1
            
            lines.append("")
    
    return '\n'.join(lines)


# ── Book I: The Hidden Door ──
hd_start = raw.find('THE BOOK OF THE HIDDEN\nDOOR')
hd_end = raw.find('TESTAMENT II')
hd_text = raw[hd_start:hd_end]

hd_chapters = [
    ('I. THE GARDENER AND THE FIELD', 'The Gardener and the Field'),
    ('II. THE FOUR TRAVELERS AND THE DOOR', 'The Four Travelers and the Door'),
    ('III. THE KING WHO LAID DOWN HIS', 'The King Who Laid Down His Crown'),
    ('IV. THE CARTOGRAPHER AND THE SEA', 'The Cartographer and the Sea'),
    ('V. THE MUSICIAN WHO COULD NOT HEAR', 'The Musician Who Could Not Hear'),
    ('VI. THE WEAVER AND THE THREAD', 'The Weaver and the Thread'),
    ('VII. THE CLOCKMAKER AND THE BREATH', 'The Clockmaker and the Breath'),
    ('VIII. THE WELL WITHOUT A BOTTOM', 'The Well Without a Bottom'),
    ('IX. THE GATE THAT WAS TWO AND ONE', 'The Gate That Was Two and One'),
    ('X. THE LIBRARY AT THE END OF ALL', 'The Library at the End of All Things'),
    ('XI. THE BUTTERFLY AND THE NET', 'The Butterfly and the Net'),
    ('XII. THE WOMAN WHO CARRIED THE', 'The Woman Who Carried the Dawn'),
    ('XIII. THE SAYINGS OF THE DOOR', 'The Sayings of the Door'),
    ('XIV. THE LAST STORY', 'The Last Story'),
]

# ── Book II: Unified Scripture ──
us_start = raw.find('TESTAMENT II')
us_end = raw.find('TESTAMENT III')
us_text = raw[us_start:us_end]

us_chapters = [
    ('BOOK I\nBERESHIT CHADASH', 'Bereshit Chadash \u2014 The New Beginning'),
    ('BOOK II\nAVERDON', 'Averdo\u0308n \u2014 The Breath-Door'),
    ('BOOK III\nSHEMA', 'Shema \u2014 The Listening'),
    ('BOOK IV\nARBA RUCHOT', 'Arba Ruchot \u2014 The Four Winds'),
    ('BOOK V\nYICHUD', 'Yichud \u2014 The Unification'),
    ('BOOK VI\nYESHUAH', 'Yeshuah \u2014 The Deliverance'),
    ('BOOK VII\nMALKHUT', 'Malkhut \u2014 The Sovereignty'),
    ('BOOK VIII\nTIKKUN', 'Tikkun \u2014 The Repair'),
    ('BOOK IX\nKINYAN', 'Kinyan \u2014 The Acquisition'),
    ('BOOK X\nARET\u0112 KAI ENKRATEIA', 'Aret\u0113 kai Enkrateia \u2014 Virtue and Continence'),
    ('BOOK XI\nDERRIDA', 'Derrida \u2014 The Philosopher at the Threshold'),
    ('EPILOGUE\nACHARIT', 'Acharit \u2014 The End That Is Not an End'),
    ('APPENDIX A\nGlossary', 'Appendix A \u2014 Glossary of Sacred Terms'),
    ('APPENDIX B\nThe Four Directions', 'Appendix B \u2014 The Four Directions Practice'),
    ('APPENDIX C\nThe Sevenfold Prayer', 'Appendix C \u2014 The Sevenfold Prayer'),
    ('APPENDIX D\nThe Ethics', 'Appendix D \u2014 The Ethics of the Two Poles'),
]

# ── Book III: The Waiting ──
wt_start = raw.find('TESTAMENT III')
wt_end = raw.find('TESTAMENT IV')
wt_text = raw[wt_start:wt_end]

wt_chapters = [('Prologue: The Ship That Does Not Arrive', 'Prologue: The Ship That Does Not Arrive')]
on_sections = re.findall(r'(ON\s+[A-Z\s]+\u2014[^\n]+)', wt_text)
for s in on_sections:
    wt_chapters.append((s.strip(), s.strip()))
wt_chapters.append(('THE FAREWELL', 'The Farewell \u2014 The Departure Into Waiting'))

# ── Book IV: The Scarlet Letter ──
sl_start = raw.find('TESTAMENT IV')
sl_end = raw.find('COLOPHON')
sl_text = raw[sl_start:sl_end]

sl_chapters = [
    ('Prologue: The Letter Arrives', 'Prologue: The Letter Arrives'),
    ('ON ADULTERY \u2014', 'On Adultery \u2014 The Name That Was Given'),
    ('ON ABLE \u2014', 'On Able \u2014 The Name That Was Earned'),
    ('ON ARTHUR \u2014', 'On Arthur \u2014 The Man Who Could Not Wear His Letter'),
    ('ON PEARL \u2014', 'On Pearl \u2014 The Living Letter'),
    ('ON ANGEL \u2014', 'On Angel \u2014 The Name That Was Bestowed'),
    ('ON ROGER \u2014', 'On Roger \u2014 The One Who Became the Letter\'s Opposite'),
    ('THE CONSUMMATION \u2014', 'The Consummation \u2014 A is for Averdo\u0308n'),
]

# ── Build the complete Bible ──

title_page = """THE COMPLETE MYOSU SCRIPTURE

Being the Sacred Writings of the Infinitute
Containing the Four Books of the New Covenant:
The Hidden Door, The Unification, The Waiting,
and The Scarlet Letter

Transmitted through the listening of
Nakamichi Shinjin
In the Year of the Convergence, 2026

CANONICAL EDITION
With Chapter and Verse
And Cross-References Throughout

"""

toc = """
TABLE OF CONTENTS

BOOK I \u2014 THE HIDDEN DOOR (Sefer Ha-Dalet Ha-Nistar)
  Chapters 1\u201314: Fourteen sacred fables of the door, the seed,
  the listening, and the silence

BOOK II \u2014 THE BOOK OF UNIFICATION (Sefer Ha-Achdut)
  Chapters 1\u201316: The theological synthesis of the infinitute,
  the Averd\u00f6n, the four winds, and the unification of all paths

BOOK III \u2014 THE BOOK OF THE WAITING (Sefer Ha-Chakah)
  Chapters 1\u201328: The twenty-six listenings of Almustafa the
  Prophet, who departed not for home but for the post office

BOOK IV \u2014 THE BOOK OF THE SCARLET LETTER (Sefer Ha-Ot Ha-Shani)
  Chapters 1\u20138: The letter delivered \u2014 Hester Prynne and
  the A that became Adultery, Able, Angel, and Averd\u00f6n

ABBREVIATIONS
  I = The Hidden Door
  II = The Unification
  III = The Waiting
  IV = The Scarlet Letter
  cf. = confer (cross-reference)

"""

# Process all books
b1 = process_book(hd_text, 1, [c[0] for c in hd_chapters], [c[1] for c in hd_chapters])
b2 = process_book(us_text, 2, [c[0] for c in us_chapters], [c[1] for c in us_chapters])
b3 = process_book(wt_text, 3, [c[0] for c in wt_chapters], [c[1] for c in wt_chapters])
b4 = process_book(sl_text, 4, [c[0] for c in sl_chapters], [c[1] for c in sl_chapters])

colophon = """

COLOPHON

These four books are one scripture. The Hidden Door shows the way
through fable. The Unification shows the way through theology. The
Waiting shows the way through departure. The Scarlet Letter shows the
way through arrival \u2014 for the letter Almustafa waited for was
always already here, embroidered on the breast of every soul who has
been named and has outlived the name.

The door is open. The infinitute listens. The letter is arriving.
It was arriving in Boston. It is arriving now.

SOLI DEO GLORIA

Averd\u00f6n. Jeomhwa. Chuk. Hoetong. Topos.
Shin Han Mari. Aurora Gongju.

Amen. So it is listened.
"""

full_bible = title_page + toc + "\n" + b1 + "\n" + b2 + "\n" + b3 + "\n" + b4 + "\n" + colophon

outpath = '/home/nakamichi/myosu-framework/complete-myosu-scripture.txt'
with open(outpath, 'w') as f:
    f.write(full_bible)

print(f"Written: {outpath}")
print(f"Size: {os.path.getsize(outpath):,} bytes")
print(f"Lines: {len(full_bible.splitlines()):,}")

verse_count = len(re.findall(r'^\s*\d{1,3}\s', full_bible, re.MULTILINE))
print(f"Verses: ~{verse_count}")
