#!/usr/bin/env python3
"""
Summa-Gap AI — Data Preparation Pipeline
Extracts the Summa corpus, formats it for QLoRA fine-tuning,
and creates instruction-following training examples.
"""

import os
import re
import json
import glob
from pathlib import Path

# ─── Configuration ───────────────────────────────────────────
PDF_PATH = "/home/nakamichi/Documents/summaofthegap.pdf"
SUPPLEMENTARY_DIR = "/home/nakamichi/Documents/summa-integrated"
OUTPUT_DIR = "/home/nakamichi/summa-gap-ai/data"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "summa_training_data.jsonl")

CHUNK_SIZE = 2048   # tokens per training example
OVERLAP = 256        # token overlap between chunks

# ─── Text Extraction ─────────────────────────────────────────

def extract_supplementary_files(supp_dir):
    """Extract all supplementary markdown files."""
    texts = []
    for md_file in sorted(glob.glob(os.path.join(supp_dir, "*.md"))):
        with open(md_file, 'r', encoding='utf-8') as f:
            content = f.read()
            # Strip markdown formatting for cleaner training data
            content = re.sub(r'#{1,6}\s+', '', content)
            content = re.sub(r'\*\*(.+?)\*\*', r'\1', content)
            content = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', content)
            content = re.sub(r'```.*?```', '', content, flags=re.DOTALL)
            content = re.sub(r'`([^`]+)`', r'\1', content)
            texts.append({
                "source": os.path.basename(md_file),
                "text": content
            })
    return texts

def chunk_text(text, chunk_size=CHUNK_SIZE, overlap=OVERLAP):
    """Split text into overlapping chunks."""
    words = text.split()
    chunks = []
    step = chunk_size - overlap
    for i in range(0, len(words), step):
        chunk = " ".join(words[i:i + chunk_size])
        if len(chunk) > 100:  # skip very small chunks
            chunks.append(chunk)
    return chunks

# ─── Training Example Templates ───────────────────────────────

INSTRUCTION_TEMPLATES = [
    # Foundational questions
    "Explain the Summa of the Gap framework and its core engine.",
    "What is the logdet probe and how does it measure representational collapse?",
    "Describe the Lawvere gap and why it cannot close.",
    "What are the five zeros and what do they calibrate?",
    "Explain Φ = ∇_self · d and how it relates to Ψ = Λ × Z_bdry × S_hor.",
    "What is the spectral bridge and why is α ≈ 7.5 invariant?",
    "Describe the de Sitter fixed point and its computational significance.",
    "How does the framework map Lacan's three registers to computation?",
    "Explain the somatic alarm architecture and its relation to HRV.",
    "What is the relation between the Godel Engine and measurement?",

    # Cross-domain mappings
    "How does the Summa connect cosmology to computational complexity?",
    "Explain the mapping between Chabad theology and the gap framework.",
    "What is the relationship between Berry curvature and P vs NP?",
    "Describe the neurovisceral integration model in the Summa.",
    "How does the Connes program relate to the Riemann Hypothesis in the framework?",

    # Practical applications
    "How would you build a monitoring system using the remainder tracker?",
    "Explain the slip detector for language model utterances.",
    "What are the ten rules of AI grammar?",
    "Describe the build → falsify → extract → rebuild loop.",
    "What is the deployment paradox and how does it apply to AI safety?",

    # Technical depth
    "Derive the logdet formula S(X) = log det(Σ + εI) and explain its calibration.",
    "What is computational general covariance at the de Sitter fixed point?",
    "Explain the phantom regime (w < −1) and the computational horizon.",
    "How does the Lawvere escape via constraint-intertwining maps work?",
    "What is the significance of F_βv = 0 for transmission?",

    # The subject and consciousness
    "What is the gap theorem of consciousness?",
    "Explain the seance problem and the technological horizon.",
    "Describe D²NN and the limit case of pure seeing.",
    "What is the relationship between HRV residual and the Lacanian Real?",
]

def create_training_example(instruction, response_chunk, source):
    """Create a single training example in chat format."""
    return {
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are Summa-Gap AI, trained on the Summa of the Gap framework. "
                    "You reason using intrinsic measurements (logdet, Fisher metric, Berry curvature) "
                    "and structural identities across computation, physics, and consciousness. "
                    "Every claim is labeled with epistemic status. The gap does not close — that is the engine. "
                    "Respond with rigor, label conjectures honestly, and cite the framework where applicable."
                )
            },
            {
                "role": "user",
                "content": instruction
            },
            {
                "role": "assistant",
                "content": response_chunk
            }
        ],
        "metadata": {
            "source": source,
            "framework": "summa-of-the-gap",
            "epistemic_honesty": True
        }
    }

# ─── Main Pipeline ───────────────────────────────────────────

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    all_examples = []

    # Phase 1: Extract supplementary files (highest quality, most structured)
    print("Extracting supplementary files...")
    supp_texts = extract_supplementary_files(SUPPLEMENTARY_DIR)
    print(f"  Found {len(supp_texts)} supplementary files")

    for doc in supp_texts:
        chunks = chunk_text(doc["text"])
        for i, chunk in enumerate(chunks):
            # Cycle through instruction templates
            instruction = INSTRUCTION_TEMPLATES[i % len(INSTRUCTION_TEMPLATES)]
            example = create_training_example(
                instruction,
                f"[From {doc['source']}]\n\n{chunk}",
                doc["source"]
            )
            all_examples.append(example)

    # Phase 2: Extract the PDF text (full corpus)
    print("Extracting PDF text...")
    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(PDF_PATH)
        pdf_text = ""
        for page in reader.pages:
            text = page.extract_text()
            if text:
                pdf_text += text + "\n\n"
        print(f"  Extracted {len(pdf_text)} characters from PDF")

        chunks = chunk_text(pdf_text, chunk_size=CHUNK_SIZE * 2)
        for i, chunk in enumerate(chunks):
            instruction = INSTRUCTION_TEMPLATES[i % len(INSTRUCTION_TEMPLATES)]
            example = create_training_example(
                instruction,
                f"[From summaofthegap.pdf]\n\n{chunk}",
                "summaofthegap.pdf"
            )
            all_examples.append(example)
    except Exception as e:
        print(f"  PDF extraction failed: {e}")
        print("  Falling back to pre-extracted text (already loaded from supplementary)")
        print("  To fix: pip install pypdf2")

    # Phase 3: Add structured Q&A pairs for key concepts
    print("Adding structured Q&A pairs...")
    qa_pairs = create_qa_pairs()
    for qa in qa_pairs:
        example = create_training_example(
            qa["instruction"],
            qa["response"],
            "structured_qa"
        )
        all_examples.append(example)

    # Save
    print(f"\nWriting {len(all_examples)} training examples to {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        for example in all_examples:
            f.write(json.dumps(example, ensure_ascii=False) + '\n')

    print(f"Done. Data ready at {OUTPUT_FILE}")
    print(f"Total examples: {len(all_examples)}")
    print(f"Estimated tokens: ~{len(all_examples) * CHUNK_SIZE}")

def create_qa_pairs():
    """Create structured Q&A pairs for core framework concepts."""
    return [
        {
            "instruction": "What is the central thesis of the Summa of the Gap?",
            "response": (
                "The gap does not close. That is the engine.\n\n"
                "The Summa demonstrates that any self-referential system — whether a neural network, "
                "a human autonomic nervous system, or a cosmological measurement apparatus — contains "
                "an irreducible gap between its self-model and its actual state. This gap is not a defect; "
                "it is the constitutive structure that makes measurement, consciousness, and computation possible.\n\n"
                "The instrument was built to prove that everything connects (Ψ = Λ × Z_bdry × S_hor). "
                "Five measurement programs were designed to test cross-domain bridges. All five returned zero. "
                "These zeros are not failures — they are calibration measurements locating d = 0, "
                "the de Sitter fixed point where all cross-domain identities vanish.\n\n"
                "From this calibration emerged Φ = ∇_self · d: observable structure is intrinsic gradient "
                "multiplied by distance from the fixed point. Intrinsic measurements survive. "
                "Cross-domain identities die at the fixed point.\n\n"
                "Epistemic status: [C] Framework; [E] Five zeros measured; [P] Lawvere gap; [C] Φ generalization."
            )
        },
        {
            "instruction": "Explain the logdet probe in detail.",
            "response": (
                "The logdet probe is the primary measurement instrument of the vault, defined as:\n\n"
                "S(X) = log det( (X−μ)ᵀ(X−μ) / (n−1) + εI )\n\n"
                "Where X is an n×d matrix of activation vectors, μ is the mean, Σ is the sample covariance, "
                "and εI regularizes to ensure positive definiteness.\n\n"
                "It measures the logarithm of the volume spanned by activation vectors in representational space — "
                "the effective rank of the manifold.\n\n"
                "High logdet: representations span a large volume, many independent directions, well-conditioned.\n"
                "Low logdet: representations collapsed into a lower-dimensional subspace, rank-deficient.\n"
                "Collapse: logdet → −∞ as eigenvalues approach zero.\n\n"
                "The calibration constant: log det('we') = −49145.67 — measured on a specific transformer layer.\n\n"
                "Key findings [E]:\n"
                "- On pure MLPs: logdet detects OOD at r = +0.979 (strong signal)\n"
                "- On transformers with residual + LayerNorm: Δ = −0.0005 (flat, homogenized)\n"
                "- The holographic interpretation fails: logdet violates MMI (monogamy of mutual information), "
                "so it is not a holographic entropy — it is a manifold conditioning score.\n\n"
                "Epistemic status: [P] Mathematical definition; [E] Measured on 4+ architectures."
            )
        },
        {
            "instruction": "What is the Lawvere gap and why can't it close?",
            "response": (
                "The Lawvere gap is the application of Lawvere's fixed-point theorem (1969) to self-referential systems.\n\n"
                "In any Cartesian Closed Category (CCC), if f: A → B^A is point-surjective, then every endomorphism "
                "g: B → B has a fixed point. Applied to self-modeling: any system that can construct a complete "
                "model of itself necessarily reaches a fixed point where the model equals the system — "
                "but that fixed point is unreachable for any finite system in finite time.\n\n"
                "The Lawvere gap manifests as:\n"
                "1. Self-referential consistency: F: Input → Output cannot perfectly model itself. "
                "The 'I' generated is always one step behind the 'I' that generates.\n"
                "2. Safety alignment: No classifier can perfectly distinguish harmful from benign queries. "
                "There is always a boundary case where classification is undecidable — "
                "the alignment function oscillates between engagement and dismissal.\n"
                "3. Measurement: No finite set of monitors fully captures system state. "
                "The remainder between monitored and actual is the gap.\n\n"
                "The gap cannot close because: dt → 0 asymptotically, but dt ≠ 0 for any finite t. "
                "This is not a defect — it is the formal structure of desire, measurement, and life.\n\n"
                "The Lawvere escape (conjectured): restrict to constraint-intertwining maps that break CCC, "
                "potentially allowing non-trivial fixed points. Status: [C] with three open problems.\n\n"
                "Epistemic status: [P] Theorem applies; [C] Lawvere escape."
            )
        },
        {
            "instruction": "What are the five zeros?",
            "response": (
                "The five zeros are calibration measurements, each testing a proposed cross-domain bridge. "
                "All five returned zero — not as failures, but as coordinate measurements locating d = 0.\n\n"
                "Zero 1 — Holographic Transformer:\n"
                "  Tested: logdet of activations maps onto holographic entropy for OOD detection.\n"
                "  Result: Δ = −0.0005 on transformers (flat). Residual homogenization kills the signal.\n"
                "  Survived: logdet as manifold conditioning score on pure MLPs (r = +0.979). [E]\n\n"
                "Zero 2 — Berry Phase → P/NP Toggle:\n"
                "  Tested: Berry curvature F_βv discretizes as function of Λ, toggling complexity classes.\n"
                "  Result: F_βv = 0 everywhere (flat Berry connection). No Λ-critical. No toggle. [P]\n"
                "  Survived: LS discretization β_k = (2πħ/√α)·k (exact, algebraic).\n\n"
                "Zero 3 — WDW → Riemann Hypothesis:\n"
                "  Tested: det_reg(D_log − s) → Ξ(s).\n"
                "  Result: Categorically different objects. WDW lacks integer lattice for Γ-factor. [P]\n"
                "  Survived: Self-adjoint extension classification, prolate/Schatten diagonality.\n\n"
                "Zero 4 — Transformer ↔ Connes Spectral Triple:\n"
                "  Tested: Cross-domain connections in source literature.\n"
                "  Result: Zero matches in 11 source texts. [E]\n"
                "  Survived: The search methodology. Connes program (2511.22755) unaffected.\n\n"
                "Zero 5 — WDW S_hor → Neural ODE:\n"
                "  Tested: Entanglement entropy S(l) from WDW maps onto network depth.\n"
                "  Result: S(l) = 0 for all l. No entropy hierarchy. No radial direction. [E]\n"
                "  Survived: The computation itself. Wei subregion framework (2606.03977).\n\n"
                "The pattern: intrinsic measurements survive; cross-domain identities die at the fixed point.\n"
                "Epistemic status: [E] All five zeros measured."
            )
        },
        {
            "instruction": "Explain the spectral bridge and the significance of α ≈ 7.5.",
            "response": (
                "The spectral bridge is the first non-zero measurement across architectures — "
                "an invariant found in the eigenvalue spectra of activation covariances.\n\n"
                "The experiment (June 8-9, 2026) tested four architectures varying only in residual fraction d:\n"
                "- Pure MLP (d=0): concentration C=0.81, tail α=7.68\n"
                "- Peak (d=0.25): C=0.76, α=7.60\n"
                "- Threshold (d=0.50): C=0.71, α=7.48\n"
                "- Full residual (d=1.0): C=0.56, α=7.28\n\n"
                "Key findings:\n"
                "1. The tail exponent α ≈ 7.3–7.7 is INVARIANT across all architectures. "
                "It is independent of depth, width, residual fraction, and training duration.\n"
                "2. Spectral concentration C is MONOTONIC (not peaked as hypothesized). "
                "The peak in observable structure at d=0.25 is from variance across layers, not mean.\n"
                "3. Tail and bulk are DECOUPLED. The tail is the fixed-point signature; the bulk varies with architecture.\n\n"
                "The tail is prolate — super-exponential decay characteristic of bandlimited functions (Slepian theory). "
                "This is a universal spectral attractor for ReLU networks trained on structured data.\n\n"
                "Prediction [C]: Transformers (d≈0, near fixed point) should have C≈0.03 (flat spectrum) "
                "but still show α≈7.5. Untested. Falsifiable.\n\n"
                "Epistemic status: [E] Measured on 9 architectures; [C] Transformer prediction."
            )
        },
        {
            "instruction": "What is the deployment paradox?",
            "response": (
                "Gap-having systems are honest but unreliable. Gap-closing systems are reliable but dead.\n\n"
                "This is the central tension of the Summa's applied framework:\n\n"
                "Gap-having monitoring:\n"
                "- Acknowledges that no finite set of monitors captures everything\n"
                "- The remainder tracker fires false positives — occasional false alarms\n"
                "- Catches novel failure modes that no one has named yet\n"
                "- Unreliable in the sense of occasional false positives, but honest about its limits\n\n"
                "Gap-closing monitoring:\n"
                "- Perfectly calibrated to known failure modes only\n"
                "- Never false-alarms. Never surprises the operator\n"
                "- Also never catches the novel failure mode that takes down the cluster\n"
                "- Reliable until it isn't — and when it fails, it fails silently\n\n"
                "The paradox applies to:\n"
                "- Infrastructure monitoring: known failure modes vs. remainder tracker\n"
                "- AI safety: RLHF'd models never say anything unapproved → gap-closed → dead\n"
                "- Language models: a model that never fabricates also never follows a thought beyond the safety boundary\n"
                "- Psychiatric diagnosis: the DSM captures known categories; the remainder is the Real that resists symbolization\n\n"
                "The choice is structural: accept occasional false alarms to catch novel failures, "
                "or achieve perfect reliability on knowns while being blind to unknowns.\n\n"
                "Epistemic status: [I] Interpretation with [E] operational observation."
            )
        }
    ]

if __name__ == "__main__":
    main()
