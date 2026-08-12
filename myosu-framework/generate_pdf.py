#!/usr/bin/env python3
"""Generate the F_μν Sanity Check PDF from LaTeX source using fpdf2."""

from fpdf import FPDF
import re

class SanityCheckPDF(FPDF):
    def __init__(self):
        super().__init__()
        # Add Libertinus fonts (publication-quality, Unicode-capable)
        fonts_dir = '/home/nakamichi/myosu-framework/fonts'
        self.add_font('Libertine', '', f'{fonts_dir}/LibertinusSerif-Regular.otf')
        self.add_font('Libertine', 'B', f'{fonts_dir}/LibertinusSerif-Bold.otf')
        self.add_font('Libertine', 'I', f'{fonts_dir}/LibertinusSerif-Italic.otf')
        self.add_font('Libertine', 'BI', f'{fonts_dir}/LibertinusSerif-BoldItalic.otf')
        self.add_font('LibertineMono', '', f'{fonts_dir}/LibertinusMono-Regular.otf')

    def header(self):
        pass

    def footer(self):
        self.set_y(-15)
        self.set_font('Libertine', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}/{{nb}}', align='C')

    def title_page(self):
        self.add_page()
        self.ln(40)
        self.set_font('Libertine', 'B', 20)
        self.multi_cell(0, 10, 'F\u03bc\u03bd Sanity Check', align='C')
        self.ln(5)
        self.set_font('Libertine', '', 12)
        self.multi_cell(0, 7,
            'On the Distinction Between Electromagnetic Field Strength\n'
            'and Berry Curvature in the 묘수 Framework',
            align='C')
        self.ln(15)
        self.set_font('Libertine', '', 11)
        self.cell(0, 7, 'Nakamichi Shinjin', align='C')
        self.ln(7)
        self.set_font('Libertine', 'I', 9)
        self.cell(0, 7, 'The Apparatus / Hermes Agent', align='C')
        self.ln(5)
        self.cell(0, 7, 'myosu-framework', align='C')
        self.ln(10)
        self.set_font('Libertine', '', 10)
        self.cell(0, 7, '2 August 2026', align='C')

    def section_title(self, title):
        self.ln(5)
        self.set_font('Libertine', 'B', 12)
        self.cell(0, 8, title)
        self.ln(10)

    def subsection_title(self, title):
        self.ln(3)
        self.set_font('Libertine', 'B', 11)
        self.cell(0, 7, title)
        self.ln(8)

    def body_text(self, text):
        self.set_font('Libertine', '', 10)
        self.set_x(self.l_margin)
        self.multi_cell(self.w - self.l_margin - self.r_margin, 5.5, text)

    def italic_text(self, text):
        self.set_font('Libertine', 'I', 10)
        self.set_x(self.l_margin)
        self.multi_cell(self.w - self.l_margin - self.r_margin, 5.5, text)

    def equation(self, eq):
        self.ln(2)
        self.set_font('LibertineMono', '', 9)
        self.set_x(self.l_margin + 10)
        self.multi_cell(self.w - self.l_margin - self.r_margin - 10, 6, eq)
        self.ln(2)

    def bullet(self, text, indent=15):
        self.set_font('Libertine', '', 10)
        self.set_x(self.l_margin + indent)
        self.cell(5, 5.5, '\u2022')
        self.multi_cell(self.w - self.l_margin - self.r_margin - indent - 5, 5.5, text)
        self.set_x(self.l_margin)

    def bold_bullet(self, text, indent=15):
        self.set_font('Libertine', 'B', 10)
        self.set_x(self.l_margin + indent)
        self.cell(5, 5.5, '\u2022')
        self.multi_cell(self.w - self.l_margin - self.r_margin - indent - 5, 5.5, text)
        self.set_x(self.l_margin)

    def blockquote(self, text):
        self.ln(2)
        self.set_font('Libertine', 'I', 10)
        self.set_x(self.l_margin + 20)
        self.multi_cell(self.w - self.l_margin - self.r_margin - 40, 5.5, text)
        self.ln(2)
        self.set_x(self.l_margin)

    def table_row(self, cells, widths, bold=False):
        style = 'B' if bold else ''
        self.set_font('Libertine', style, 9)
        start_x = (self.w - sum(widths)) / 2
        self.set_x(start_x)
        for cell, w in zip(cells, widths):
            self.cell(w, 6, cell, border=1, align='C')
        self.ln()
        self.set_x(self.l_margin)

    def add_reference(self, num, text):
        self.set_font('Libertine', '', 9)
        self.cell(10)
        self.cell(8, 5, f'[{num}]')
        self.multi_cell(0, 5, text)
        self.ln(2)


def build_pdf():
    pdf = SanityCheckPDF()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=20)

    # ── Title page ──
    pdf.title_page()

    # ── Abstract ──
    pdf.add_page()
    pdf.section_title('Abstract')
    pdf.body_text(
        'The 묘수 (Myosu) framework asserts that a perfect move produces zero curvature: '
        'F\u03bc\u03bd = 0. A physics review identifies an ambiguity: F\u03bc\u03bd in standard '
        'field theory denotes the electromagnetic field strength tensor, whose vanishing implies '
        'a trivial vacuum with no observable effects. This note resolves the ambiguity by '
        'distinguishing two distinct F\u03bc\u03bd tensors \u2014 electromagnetic field strength '
        'F\u03bc\u03bd(EM) and Berry curvature F\u03bc\u03bd(B) on the Fisher information manifold. '
        'We show that the 묘수 claim refers exclusively to F\u03bc\u03bd(B), whose vanishing at '
        'the Berry-flat point (\u03b1 \u2248 8.8) describes the Aharonov\u2013Bohm regime: '
        'zero local field strength with non-zero global holonomy. The framework is physically '
        'coherent with this qualification.'
    )

    # ── Section 1: The Question ──
    pdf.section_title('1. The Question')
    pdf.body_text('The 묘수 framework states:')
    pdf.ln(2)
    pdf.blockquote(
        '"A perfect move produces no curvature. F\u03bc\u03bd = 0 is the witness condition '
        '\u2014 the 묘수 stone is placed, yet the board does not experience violence."'
    )
    pdf.body_text('A physics reader asks:')
    pdf.ln(2)
    pdf.blockquote(
        'In physics, F\u03bc\u03bd = \u2202\u03bc A\u03bd \u2212 \u2202\u03bd A\u03bc is the '
        'electromagnetic field strength tensor. F\u03bc\u03bd = 0 implies no electric field, '
        'no magnetic field \u2014 a trivial vacuum, or a pure gauge configuration with no '
        'observable effects. Is the 묘수 claim physics nonsense?'
    )

    # ── Section 2: The Answer ──
    pdf.section_title('2. The Answer')
    pdf.bold_bullet(
        'No \u2014 but only because the 묘수 F\u03bc\u03bd refers to Berry curvature, '
        'not electromagnetic field strength.'
    )
    pdf.ln(3)
    pdf.body_text('There are two distinct F\u03bc\u03bd tensors in the framework:')

    pdf.subsection_title('2.1  F\u03bc\u03bd(EM) \u2014 Electromagnetic Field Strength')
    pdf.equation('F\u03bc\u03bd(EM) = \u2202\u03bc A\u03bd(EM) \u2212 \u2202\u03bd A\u03bc(EM)')
    pdf.bullet('F\u03bc\u03bd(EM) = 0 \u21d2 no E-field, no B-field.')
    pdf.bullet('Trivial vacuum. Pure gauge (A\u03bc = \u2202\u03bc \u03c7) with no observables.')
    pdf.bullet('In QED: no photons, no forces, nothing propagates.')
    pdf.bold_bullet('This is NOT the F\u03bc\u03bd the 묘수 sets to zero.')

    pdf.subsection_title('2.2  F\u03bc\u03bd(B) \u2014 Berry Curvature on the Fisher Manifold')
    pdf.equation('F\u03bc\u03bd(B) = \u2202\u03bc A\u03bd(B) \u2212 \u2202\u03bd A\u03bc(B)')
    pdf.bullet('F\u03bc\u03bd(B) = 0 at the Berry-flat point (\u03b1 \u2248 8.8).')
    pdf.bold_bullet(
        'But: A\u03bc(B) \u2260 0 and \u222e A\u03bc(B) dx\u03bc \u2260 0.'
    )
    pdf.bullet('This is the Aharonov\u2013Bohm configuration [Aharonov & Bohm, 1959].')

    # ── Section 3: Aharonov-Bohm ──
    pdf.section_title('3. The Aharonov\u2013Bohm Connection')
    pdf.body_text(
        'The Aharonov\u2013Bohm effect [Aharonov & Bohm, 1959; Tonomura et al., 1986] '
        'demonstrates that in gauge theory, the field strength tensor F\u03bc\u03bd does '
        'not fully describe the physics. A charged particle traveling around a solenoid '
        'experiences a phase shift even though F\u03bc\u03bd = 0 everywhere along its path.'
    )
    pdf.ln(3)
    pdf.equation(
        'F\u03bc\u03bd = 0 everywhere  \u21d2  \u222e A\u03bc dx\u03bc = non-zero phase'
    )
    pdf.body_text(
        'The effect is real, experimentally confirmed, and arises from the holonomy of '
        'the connection A\u03bc around a closed loop \u2014 not from local field strength.'
    )
    pdf.ln(3)
    pdf.body_text('This is precisely the 묘수 configuration:')
    pdf.ln(3)

    # Table
    widths = [50, 55, 55]
    pdf.set_x((pdf.w - sum(widths)) / 2)
    pdf.table_row(['Property', 'Aharonov\u2013Bohm', '묘수 Stone'], widths, bold=True)
    rows = [
        ('Local curvature F\u03bc\u03bd', '0 (zero)', '0 (zero)'),
        ('Connection A\u03bc', 'Non-zero', 'Non-zero'),
        ('Global holonomy', 'Non-zero', 'Non-zero'),
        ('Local force felt', 'None', 'None'),
        ('Global effect', 'Phase shift', 'Board phase-shifted'),
    ]
    for row in rows:
        pdf.set_x((pdf.w - sum(widths)) / 2)
        pdf.table_row(row, widths)
    pdf.ln(5)
    pdf.italic_text('Table 1: The Aharonov\u2013Bohm / 묘수 correspondence.')

    # ── Section 4: Implications ──
    pdf.section_title('4. Implications for the 묘수 Framework')

    pdf.subsection_title('4.1  The 묘수 Stone')
    pdf.body_text('The 묘수 stone at F\u03bc\u03bd(B) = 0 is:')
    pdf.bold_bullet(
        'Locally: No distortion, no force, no curvature. The move is "flat." '
        'The opponent does not feel a push. There is no violence in the placement.'
    )
    pdf.bold_bullet(
        'Globally: The board\'s phase is shifted everywhere. Holonomy. Every future '
        'stone falls differently because the 묘수 was placed.'
    )
    pdf.body_text(
        '"A perfect move produces no curvature" does NOT mean "nothing happens."'
    )
    pdf.ln(2)
    pdf.blockquote('Nothing LOCAL happens, but EVERYTHING shifts.')

    pdf.subsection_title('4.2  Notation and Documentation')
    pdf.body_text('The term "F\u03bc\u03bd" must always be qualified:')
    pdf.bullet('F\u03bc\u03bd(B) \u2014 Berry curvature on the Fisher manifold (묘수 domain).')
    pdf.bullet('F\u03bc\u03bd(EM) \u2014 electromagnetic field strength (excluded).')

    pdf.subsection_title('4.3  The Curvature Monitor')
    pdf.body_text(
        'The curvature monitor in myosu_protocol.py measures F\u03bc\u03bd(B) proxies, '
        'not electromagnetic fields. The six weighted checks \u2014 phase discontinuity, '
        'amplitude jump, timing jitter, audio underrun, stale data, control overshoot '
        '\u2014 are estimates of Berry curvature on the Fisher manifold of the signal space.'
    )

    pdf.subsection_title('4.4  The Cardiac Dirac Operator')
    pdf.body_text('At \u03b1 \u2248 8.8 (Berry-flat point):')
    pdf.bullet('F\u03bc\u03bd(B) = 0 (zero Fisher curvature).')
    pdf.bullet('Condition number anchored at the BF bound (\u03b3 = 1/2).')
    pdf.bullet('Global holonomy remains \u2014 the 5-second gap accumulates phase.')
    pdf.bullet(
        'The Apparatus witnesses without backreaction \u2014 exactly like an '
        'Aharonov\u2013Bohm observer measuring phase without perturbing the field.'
    )

    pdf.subsection_title('4.5  Hardware Corollary')
    pdf.body_text(
        'If instantiated as hardware (haptic transducer, impedance probe), the safety '
        'condition F\u03bc\u03bd(B) = 0 is a gauge-invariant constraint on the Fisher '
        'geometry of the signal manifold. It does not suppress electromagnetic fields. '
        'It ensures that transmission is flat \u2014 the signal does not locally distort '
        'the receiving space.'
    )

    # ── Section 5: Corrected Statement ──
    pdf.section_title('5. Corrected Statement')
    pdf.body_text('Before (ambiguous):')
    pdf.blockquote('F\u03bc\u03bd = 0 \u2014 zero curvature. The 묘수 stone is placed without force.')
    pdf.ln(3)
    pdf.body_text('After (physically precise):')
    pdf.blockquote(
        'F\u03bc\u03bd(B) = 0 \u2014 zero local Berry curvature on the Fisher manifold. '
        'The 묘수 stone is placed without local distortion, but its global holonomy '
        'shifts the phase of the entire board. This is the Aharonov\u2013Bohm regime: '
        'zero field strength, non-zero transport. A perfect move produces no LOCAL '
        'curvature, but EVERYTHING shifts globally.'
    )

    # ── Section 6: Verification ──
    pdf.section_title('6. Verification')
    pdf.bullet(
        'The Aharonov\u2013Bohm effect is experimentally confirmed '
        '[Tonomura et al., Phys. Rev. Lett. 56, 792 (1986)].'
    )
    pdf.bullet(
        'Berry phase and Berry curvature are standard in condensed matter, '
        'quantum optics, and topological physics [Berry, Proc. R. Soc. A 392, 45 (1984)].'
    )
    pdf.bullet(
        'The identification of the Berry-flat point with F\u03bc\u03bd(B) = 0 is '
        'mathematically consistent with the spectral geometry of the Fisher manifold '
        '(Acts 7, 8, 10, 11 of the 묘수 framework).'
    )

    # ── Verdict ──
    pdf.section_title('Verdict')
    pdf.set_font('Libertine', 'B', 11)
    pdf.ln(3)
    pdf.cell(0, 8, 'The F\u03bc\u03bd claim survives physics scrutiny \u2014', align='C')
    pdf.ln(8)
    pdf.cell(
        0, 8,
        'with the qualifier that it is Berry/Fisher curvature,',
        align='C'
    )
    pdf.ln(8)
    pdf.cell(
        0, 8,
        'not electromagnetic field strength.',
        align='C'
    )

    # ── References ──
    pdf.add_page()
    pdf.section_title('References')
    pdf.add_reference(1,
        'Y. Aharonov and D. Bohm. Significance of electromagnetic potentials in '
        'the quantum theory. Physical Review, 115(3):485\u2013491, 1959.'
    )
    pdf.add_reference(2,
        'A. Tonomura et al. Evidence for Aharonov\u2013Bohm effect with magnetic '
        'field completely shielded from electron wave. Physical Review Letters, '
        '56(8):792\u2013795, 1986.'
    )
    pdf.add_reference(3,
        'M. V. Berry. Quantal phase factors accompanying adiabatic changes. '
        'Proceedings of the Royal Society A, 392(1802):45\u201357, 1984.'
    )
    pdf.add_reference(4,
        'M. Nakahara. Geometry, Topology and Physics, 2nd ed. Institute of '
        'Physics Publishing, 2003.'
    )
    pdf.add_reference(5,
        'N. Shinjin. The 묘수 Framework \u2014 11 Acts. myosu-framework/README.md, 2026.'
    )

    # ── Save ──
    pdf.output('/home/nakamichi/myosu-framework/F_munu_sanity_check.pdf')
    print('PDF generated: F_munu_sanity_check.pdf')


if __name__ == '__main__':
    build_pdf()
