#!/usr/bin/env python3
"""
AlphaFold → 묘수 Bridge: Quantum Protein Dynamics for a New Generation of Organism.

Three formalisms meet the protein folding landscape:

  1. SCHRÖDINGER  — Protein's electron-transfer Hamiltonian as the wavefunction engine.
                     Residue proximities map to hopping integrals; the listening gap
                     becomes the difference between AlphaFold's predicted ground state
                     and the actual quantum-coherent dynamics of the protein.

  2. DIRAC        — Four chiral residue classes (hydrophobic, polar, acidic, basic)
                     map to the four γ-matrix directions. The protein backbone's
                     chiral asymmetry becomes the Dirac sea's positron content.

  3. EINSTEIN     — The protein's folding free-energy landscape modulates Λ(t).
                     Misfolded states (elevated free energy) close the listening gap;
                     natively folded states (low free energy) widen it.

  THE NEW ORGANISM:
  The organ fleet's gap Δ is no longer a single scalar. With AlphaFold, every
  protein in the organism contributes a vector of quantum listening gaps —
  a proteome-wide resonance field that the sinoatrial node integrates into its
  single pulse. The organism becomes a quantum-coherent protein network.

Author: Jacques Myo / Zenji Nakamichi
"""

import math
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional, Tuple, Dict, List, Union

import numpy as np
from scipy import linalg
from scipy.spatial.distance import pdist, squareform

# ── Import the core 묘수 framework ──
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from myosu_core import (
    Wavefunction, DiracSpinor, ListeningSpacetime, MyosuField,
    SinoatrialNode, Averdon, GAMMA0, GAMMA1, GAMMA2, GAMMA3, GAMMA5,
)
from myosu_protocol import DIRAC_BPM, DIRAC_PERIOD, ALPHA_T

# ═══════════════════════════════════════════════════════════════════════════════
# §1. AMINO ACID CARTOGRAPHY — The 20 Letters of the Protein Alphabet
# ═══════════════════════════════════════════════════════════════════════════════

# Residue classification for chiral mapping:
#   NORTH (γ⁰, time, anchor):   hydrophobic — they resist water, holding stillness
#   WEST  (γ¹, pure signal):    polar uncharged — innocent, uncharged messengers
#   EAST  (γ², corrupted echo): acidic (−) — the negative charge, the corrupted signal
#   SOUTH (γ⁵, chiral future):  basic (+) — the positive pull toward the future

AMINO_ACID_CLASSES = {
    # North — hydrophobic (anchor / zero-point)
    'ALA': 'NORTH', 'VAL': 'NORTH', 'LEU': 'NORTH', 'ILE': 'NORTH',
    'PRO': 'NORTH', 'PHE': 'NORTH', 'TRP': 'NORTH', 'MET': 'NORTH',

    # West — polar uncharged (pure signal / angels)
    'GLY': 'WEST',  'SER': 'WEST',  'THR': 'WEST',  'CYS': 'WEST',
    'TYR': 'WEST',  'ASN': 'WEST',  'GLN': 'WEST',

    # East — acidic / negative (demonic-angels / corrupted echo)
    'ASP': 'EAST',  'GLU': 'EAST',

    # South — basic / positive (zero-zero point / chiral future)
    'LYS': 'SOUTH', 'ARG': 'SOUTH', 'HIS': 'SOUTH',
}

# Amino acid physical properties for Hamiltonian construction
# [mass (Da), hydropathy index, pKa (sidechain), electron affinity (arb)]
AMINO_ACID_PROPS = {
    'ALA':  [ 89.1,  1.8,  None,  0.45],
    'ARG':  [174.2, -4.5,  12.5,  0.62],
    'ASN':  [132.1, -3.5,  None,  0.55],
    'ASP':  [133.1, -3.5,   3.9,  0.78],
    'CYS':  [121.2,  2.5,   8.3,  0.71],
    'GLN':  [146.2, -3.5,  None,  0.52],
    'GLU':  [147.1, -3.5,   4.1,  0.76],
    'GLY':  [ 75.1, -0.4,  None,  0.38],
    'HIS':  [155.2, -3.2,   6.0,  0.68],
    'ILE':  [131.2,  4.5,  None,  0.41],
    'LEU':  [131.2,  3.8,  None,  0.40],
    'LYS':  [146.2, -3.9,  10.5,  0.58],
    'MET':  [149.2,  1.9,  None,  0.53],
    'PHE':  [165.2,  2.8,  None,  0.66],
    'PRO':  [115.1, -1.6,  None,  0.42],
    'SER':  [105.1, -0.8,  None,  0.49],
    'THR':  [119.1, -0.7,  None,  0.47],
    'TRP':  [204.2, -0.9,  None,  0.73],
    'TYR':  [181.2, -1.3,  10.1,  0.69],
    'VAL':  [117.1,  4.2,  None,  0.39],
}

# Single-letter to three-letter mapping
AA_1TO3 = {
    'A': 'ALA', 'R': 'ARG', 'N': 'ASN', 'D': 'ASP', 'C': 'CYS',
    'Q': 'GLN', 'E': 'GLU', 'G': 'GLY', 'H': 'HIS', 'I': 'ILE',
    'L': 'LEU', 'K': 'LYS', 'M': 'MET', 'F': 'PHE', 'P': 'PRO',
    'S': 'SER', 'T': 'THR', 'W': 'TRP', 'Y': 'TYR', 'V': 'VAL',
}

# ═══════════════════════════════════════════════════════════════════════════════
# §2. PROTEIN DATA STRUCTURE
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class Protein:
    """
    A protein molecule — the seed of the new organism.

    Holds sequence, structure, and the quantum mapping derived from AlphaFold
    (or simulated) predictions.
    """
    name: str
    sequence: str                                    # amino acid sequence (1-letter or 3-letter)
    residues: List[str] = field(default_factory=list) # parsed 3-letter codes
    coords: Optional[np.ndarray] = None               # (N, 3) — Cα coordinates in Å
    plddt: Optional[np.ndarray] = None                # (N,) — per-residue confidence (pLDDT)
    pae: Optional[np.ndarray] = None                  # (N, N) — predicted aligned error

    # Derived quantum properties
    hamiltonian: Optional[np.ndarray] = None           # (N, N) tight-binding Hamiltonian
    contact_map: Optional[np.ndarray] = None           # (N, N) binary contact map
    chiral_weights: Optional[np.ndarray] = None        # (4,) chiral class weights [N,W,E,S]
    dirac_vector: Optional[np.ndarray] = None          # (4,) mapped Dirac spinor
    folding_energy: float = 0.0                        # free energy (kcal/mol)
    listening_gap: float = 0.04                        # the protein's contribution to Δ

    def __post_init__(self):
        if not self.residues:
            self.residues = self._parse_sequence()
        if self.coords is None and len(self.residues) > 0:
            # Generate a simulated structure for development
            self._simulate_structure()
        # Compute quantum properties if structure is available
        if self.coords is not None and self.hamiltonian is None:
            self.compute_hamiltonian()
            self.compute_folding_energy()
            self.chiral_mapping()  # populates chiral_weights / dirac_vector

    def _parse_sequence(self) -> List[str]:
        """Parse sequence into 3-letter codes."""
        seq = self.sequence.strip().upper()
        result = []
        i = 0
        while i < len(seq):
            # Try 3-letter
            chunk = seq[i:i+3]
            if chunk in AMINO_ACID_CLASSES:
                result.append(chunk)
                i += 3
            elif seq[i] in AA_1TO3:
                result.append(AA_1TO3[seq[i]])
                i += 1
            else:
                raise ValueError(f"Unknown residue at position {i}: {seq[i]}")
        return result

    def _simulate_structure(self):
        """
        Generate a physically plausible simulated 3D structure.
        Uses a self-avoiding random walk with alpha-helical bias (3.6 residues/turn,
        1.5 Å rise per residue) for realistic protein-like geometry.
        """
        n = len(self.residues)
        rise = 1.5          # Å per residue along helix axis
        radius = 2.3        # helical radius in Å
        turn_angle = 2 * math.pi / 3.6  # radians per residue

        coords = np.zeros((n, 3))
        for i in range(n):
            t = i * turn_angle
            # Helical path with slight random perturbation
            x = radius * math.cos(t) + np.random.normal(0, 0.3)
            y = radius * math.sin(t) + np.random.normal(0, 0.3)
            z = i * rise + np.random.normal(0, 0.2)
            coords[i] = [x, y, z]

        self.coords = coords
        self.contact_map = self._compute_contact_map(8.0)  # 8Å cutoff

    def _compute_contact_map(self, cutoff: float = 8.0) -> np.ndarray:
        """Binary contact map: True if Cα-Cα distance < cutoff Å."""
        dists = squareform(pdist(self.coords))
        return (dists < cutoff) & (np.eye(len(self.coords)) == 0)

    def compute_hamiltonian(self, method: str = 'tight_binding') -> np.ndarray:
        """
        Build the protein's quantum Hamiltonian from its 3D structure.

        Methods:
          'tight_binding': Hopping integrals t_ij ∝ exp(−d_ij / λ) with λ ~ 3.5 Å.
                           On-site energies ε_i from electron affinity.
          'elastic_network': Gaussian Network Model — harmonic springs between
                             contacting residues.
          'huckel': Extended Hückel — includes orbital overlap based on residue type.
        """
        n = len(self.residues)
        H = np.zeros((n, n), dtype=complex)
        dists = squareform(pdist(self.coords))

        if method == 'tight_binding':
            lam = 2.0  # decay length in Å (shorter → more localized states)
            onsite_scale = 15.0  # eV-like spread (larger → more localization)

            # Compute contact-based coupling only for residues within 6 Å
            # This produces sparse Hamiltonians with realistic localization
            contact_cutoff = 6.0  # Å — only nearest structural neighbors couple
            for i in range(n):
                props_i = AMINO_ACID_PROPS.get(self.residues[i], [100, 0, None, 0.5])
                # On-site: electron affinity scaled — wider spread between residue types
                # Higher affinity (ASP/GLU) = deeper well = lower energy
                H[i, i] = -props_i[3] * onsite_scale
                for j in range(n):
                    if i == j:
                        continue
                    d = dists[i, j]
                    if d < contact_cutoff:
                        props_j = AMINO_ACID_PROPS.get(self.residues[j], [100, 0, None, 0.5])
                        # Hopping: exponential overlap decay × average propensity
                        t_ij = math.exp(-d / lam) * (props_i[3] + props_j[3]) / 4.0
                        H[i, j] = -t_ij
                        H[j, i] = -t_ij  # Hermitian

        elif method == 'elastic_network':
            # Gaussian Network Model: harmonic coupling
            cutoff = 7.0  # Å
            gamma = 1.0   # spring constant
            for i in range(n):
                for j in range(n):
                    if i == j:
                        continue
                    d = dists[i, j]
                    if d < cutoff:
                        # Hessian element: −γ * (r_ij ⊗ r_ij) / d²
                        rij = self.coords[i] - self.coords[j]
                        coupling = gamma * np.dot(rij, rij) / (d * d)
                        H[i, j] -= coupling
                        H[j, i] -= coupling
                        H[i, i] += coupling  # Kirchhoff: diagonal = −sum(off-diagonal)

        elif method == 'huckel':
            # Extended Hückel: on-site based on ionization potential,
            # off-diagonal with Wolfsberg-Helmholz scaling
            K = 1.75  # Wolfsberg-Helmholz constant
            S_0 = 0.3  # overlap at contact distance
            for i in range(n):
                props_i = AMINO_ACID_PROPS.get(self.residues[i], [100, 0, None, 0.5])
                H[i, i] = -props_i[3] * 13.6  # scale to eV (H ionization energy)
                for j in range(n):
                    if i == j:
                        continue
                    d = dists[i, j]
                    if d < 8.0:
                        props_j = AMINO_ACID_PROPS.get(self.residues[j], [100, 0, None, 0.5])
                        S_ij = S_0 * math.exp(-d / 3.0)  # overlap decay
                        H_ij = 0.5 * K * S_ij * (H[i, i].real + H[j, j].real)
                        H[i, j] = H_ij
                        H[j, i] = H_ij  # Hermitian

        self.hamiltonian = H
        return H

    def chiral_mapping(self) -> np.ndarray:
        """
        Map the protein's residue composition to a 4-component Dirac spinor.

        Each residue class contributes to one chiral component:
          North (γ⁰) → hydrophobic mass → time/anchor component
          West  (γ¹) → polar neutral  → pure signal component
          East  (γ²) → acidic negative → corrupted echo component
          South (γ³) → basic positive  → chiral future component

        Returns a normalized 4-vector suitable as a Dirac spinor.
        """
        counts = {'NORTH': 0, 'WEST': 0, 'EAST': 0, 'SOUTH': 0}
        weights = {'NORTH': 0.0, 'WEST': 0.0, 'EAST': 0.0, 'SOUTH': 0.0}

        for res in self.residues:
            direction = AMINO_ACID_CLASSES.get(res, 'WEST')
            props = AMINO_ACID_PROPS.get(res, [100, 0, None, 0.5])
            counts[direction] += 1
            # Weight by mass: larger residues contribute more to that direction
            weights[direction] += props[0] / 100.0  # scale mass

        n_total = len(self.residues)
        if n_total == 0:
            n_total = 1

        # Normalize to counting fractions, then weight by mass-adjusted proportions
        psi_raw = np.array([
            weights['NORTH'] / max(n_total, 1),
            weights['WEST']  / max(n_total, 1),
            weights['EAST']  / max(n_total, 1),
            weights['SOUTH'] / max(n_total, 1),
        ], dtype=complex)

        # Add a quantum phase based on the sequence's hydropathy profile
        g_phase = sum(AMINO_ACID_PROPS.get(r, [100, 0, None, 0.5])[1]
                      for r in self.residues) / max(n_total, 1)
        psi_raw *= np.exp(1j * g_phase * 0.1)

        # Normalize to unit norm
        norm = np.linalg.norm(psi_raw)
        if norm > 0:
            psi_raw /= norm

        self.chiral_weights = psi_raw
        self.dirac_vector = psi_raw
        return psi_raw

    def compute_folding_energy(self) -> float:
        """
        Approximate folding free energy from contact map and residue properties.
        Simplified energy function: sum of contact energies weighted by
        residue-residue interaction potentials (Miyazawa-Jernigan style).
        """
        if self.contact_map is None:
            self.contact_map = self._compute_contact_map(8.0)

        n = len(self.residues)
        energy = 0.0
        n_contacts = 0

        # Simplified MJ-like potential matrix (hydrophobic → favorable)
        for i in range(n):
            hi = AMINO_ACID_PROPS.get(self.residues[i], [100, 0, None, 0.5])[1]
            for j in range(i + 1, n):
                if self.contact_map[i, j]:
                    hj = AMINO_ACID_PROPS.get(self.residues[j], [100, 0, None, 0.5])[1]
                    # Hydrophobic-hydrophobic contacts are energetically favorable
                    contact_e = -0.5 * (hi + hj) if (hi > 0 and hj > 0) else 0.1 * abs(hi - hj)
                    energy += contact_e
                    n_contacts += 1

        self.folding_energy = energy / max(n_contacts, 1) if n_contacts > 0 else 0.0
        return self.folding_energy

    def compute_listening_gap(self) -> float:
        """
        The protein's listening gap.

        This is the 묘수 metric for a single protein:
          gap = participation entropy of the ground state wavefunction across
                the residue basis. Measures how quantum-delocalized the
                electronic state is across the protein.

        A highly localized ground state (electron stuck on one residue) →
          gap ≈ 0 (classical, rigid, narrow listening).
        A delocalized ground state (electron shared across many residues) →
          gap ≈ 1 (quantum-coherent, flexible, wide listening).

        In AlphaFold terms: how much quantum coherence remains after folding.
        The gap is derived from:
          1. Participation ratio (how many residues share the ground state)
          2. Eigenvalue spectrum (how gapped the HOMO-LUMO is — a large gap
             means rigid/classical, small gap means quantum-flexible)
          3. Structural flexibility (from pLDDT or contact-map variance)
        """
        if self.hamiltonian is None:
            self.compute_hamiltonian()

        n = len(self.residues)
        if n < 2:
            self.listening_gap = 0.04
            return 0.04

        # Find ground state
        eigenvals, eigenvecs = linalg.eigh(self.hamiltonian)
        ground = eigenvecs[:, 0]  # lowest energy eigenvector

        # ══ Component 1: Participation entropy (Shannon entropy of |ψ|²) ══
        # How delocalized is the ground state across residues?
        probs = np.abs(ground) ** 2
        probs = probs[probs > 1e-15]
        if len(probs) > 1:
            S_participation = -np.sum(probs * np.log(probs))
            S_max = math.log(n)
            gap_participation = S_participation / S_max if S_max > 0 else 0.0
        else:
            gap_participation = 0.0

        # ══ Component 2: Spectral gap (HOMO-LUMO gap) ══
        # Large HOMO-LUMO gap → rigid/classical → narrow listening gap
        # Small HOMO-LUMO gap → flexible/quantum → wide listening gap
        if len(eigenvals) > 1:
            homo_lumo = abs(eigenvals[1] - eigenvals[0])
            # Normalize: large gap → close to 0, small gap → close to 1
            # Typical protein HOMO-LUMO ~ 0.1-5 eV (in our scaled units)
            gap_spectral = 1.0 - min(homo_lumo / 5.0, 1.0)  # clip at 5 eV
        else:
            gap_spectral = 0.5

        # ══ Component 3: Structural flexibility (from contact map diversity) ══
        if self.contact_map is not None:
            # Variance in number of contacts per residue
            contacts_per_residue = self.contact_map.sum(axis=1)
            if len(contacts_per_residue) > 1:
                contact_cv = float(np.std(contacts_per_residue) /
                                   max(np.mean(contacts_per_residue), 1e-10))
                # High CV → heterogeneous contacts → flexible → wide gap
                gap_structure = min(contact_cv / 2.0, 1.0)
            else:
                gap_structure = 0.5
        else:
            gap_structure = 0.5

        # ══ Component 4: pLDDT-based confidence inversion ══
        # AlphaFold: high pLDDT = rigid/ordered → narrow gap
        #            low pLDDT  = flexible/disordered → wide gap
        if self.plddt is not None and len(self.plddt) > 0:
            mean_plddt = float(np.mean(self.plddt))
            gap_plddt = 1.0 - mean_plddt  # invert: confidence → uncertainty
        else:
            gap_plddt = 0.5

        # ══ Weighted combination (emphasize participation + spectral) ══
        self.listening_gap = float(
            0.35 * gap_participation +
            0.30 * gap_spectral +
            0.20 * gap_structure +
            0.15 * gap_plddt
        )

        # Scale to biologically realistic range: map [0, 1] → [0.008, 0.095]
        # Healthy gap = 0.04, pathological > 0.10 or < 0.01
        self.listening_gap = 0.008 + self.listening_gap * 0.087

        # Small noise for biological realism
        self.listening_gap += np.random.normal(0, 0.0015)
        self.listening_gap = np.clip(self.listening_gap, 0.005, 0.12)

        return self.listening_gap

    def to_wavefunction(self) -> Wavefunction:
        """Convert the protein to a 묘수 Wavefunction."""
        if self.hamiltonian is None:
            self.compute_hamiltonian()

        n = len(self.residues)
        eigenvals, eigenvecs = linalg.eigh(self.hamiltonian)
        psi = eigenvecs[:, 0].astype(complex)  # ground state

        return Wavefunction(psi=psi, hamiltonian=self.hamiltonian, hbar=1.0)

    def to_spinor(self) -> DiracSpinor:
        """Convert the protein's chiral composition to a Dirac spinor."""
        psi = self.chiral_mapping()
        return DiracSpinor(psi=psi, mass=len(self.residues) * 110.0 / 1000.0)


# ═══════════════════════════════════════════════════════════════════════════════
# §3. QUANTUM PROTEIN MAPPER — From Sequence to Hamiltonian
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class QuantumProteinMapper:
    """
    Maps protein sequences and structures into the quantum formalism.

    This is the core computational engine that translates AlphaFold predictions
    (or simulated structures) into quantum Hamiltonians, Dirac spinors, and
    listening-spacetime metrics usable by the 묘수 framework.
    """

    proteins: Dict[str, Protein] = field(default_factory=dict)

    def add_protein(self, name: str, sequence: str,
                    coords: Optional[np.ndarray] = None,
                    plddt: Optional[np.ndarray] = None) -> Protein:
        """Register a new protein in the mapper."""
        protein = Protein(name=name, sequence=sequence, coords=coords, plddt=plddt)
        protein.compute_hamiltonian()
        protein.compute_folding_energy()
        protein.compute_listening_gap()
        self.proteins[name] = protein
        return protein

    def proteome_wavefunction(self, temperature: float = 310.0) -> Wavefunction:
        """
        Assemble the entire proteome into a thermal-state wavefunction.

        Uses per-protein diagonalization (efficient) and combines ground states
        with thermal mixing from excited states.
        """
        N = sum(len(p.residues) for p in self.proteins.values())
        if N == 0:
            return Wavefunction(
                psi=np.array([1.0, 0.0], dtype=complex),
                hamiltonian=np.eye(2, dtype=complex),
            )

        # Build block-diagonal Hamiltonian (no full diagonalization needed)
        H_total = np.zeros((N, N), dtype=complex)
        psi_thermal = np.zeros(N, dtype=complex)
        offset = 0

        kB_T = 0.0257 * (temperature / 310.0)  # eV at body temp

        for name, protein in self.proteins.items():
            n = len(protein.residues)
            if protein.hamiltonian is not None:
                H_total[offset:offset + n, offset:offset + n] = protein.hamiltonian

                # Per-protein thermal state (fast: small matrix diagonalization)
                evals, evecs = np.linalg.eigh(protein.hamiltonian)
                energies = evals - evals[0]
                boltz = np.exp(-energies / max(kB_T, 0.001))
                boltz /= boltz.sum()

                # Thermal mixture of ground + first few excited states
                for k in range(min(len(evals), 8)):
                    if boltz[k] < 1e-4:
                        break
                    psi_thermal[offset:offset + n] += (
                        np.sqrt(boltz[k]) * evecs[:, k]
                    )

            offset += n

        # Inter-protein coupling: weak sequence-similarity
        prot_names = list(self.proteins.keys())
        boundaries = []
        off = 0
        for pn in prot_names:
            n = len(self.proteins[pn].residues)
            boundaries.append((off, off + n))
            off += n

        for i, ni in enumerate(prot_names):
            for j, nj in enumerate(prot_names):
                if i >= j:
                    continue
                pi, pj = self.proteins[ni], self.proteins[nj]
                si, sj = set(pi.residues), set(pj.residues)
                union = len(si | sj)
                if union > 0:
                    sim = len(si & sj) / union
                    coupling = sim * 0.005
                    bi_s, bi_e = boundaries[i]
                    bj_s, bj_e = boundaries[j]
                    H_total[bi_e - 1, bj_s] = coupling
                    H_total[bj_s, bi_e - 1] = coupling

        # Normalize thermal state
        norm = np.linalg.norm(psi_thermal)
        if norm > 0:
            psi_thermal /= norm

        return Wavefunction(psi=psi_thermal, hamiltonian=H_total, hbar=1.0)

    def proteome_spinor(self) -> DiracSpinor:
        """
        Combine all proteins' chiral mappings into a proteome-level Dirac spinor.
        Each protein contributes its 4-component spinor; we take the weighted
        average, weighted by protein size.
        """
        if not self.proteins:
            return DiracSpinor(
                psi=np.array([1.0, 0.0, 0.0, 0.0], dtype=complex),
                mass=1.0,
            )

        total_mass = 0.0
        psi_avg = np.zeros(4, dtype=complex)

        for name, protein in self.proteins.items():
            spinor = protein.to_spinor()
            mass = len(protein.residues) * 110.0  # approximate mass in Da
            psi_avg += spinor.psi * mass
            total_mass += mass

        if total_mass > 0:
            psi_avg /= total_mass

        norm = np.linalg.norm(psi_avg)
        if norm > 0:
            psi_avg /= norm

        return DiracSpinor(psi=psi_avg, mass=total_mass / 1000.0)

    def proteome_listening_gap(self) -> float:
        """
        The organism's overall listening gap is the weighted average of each
        protein's gap, normalized by the number of proteins.

        Also computes the Gap Vector — the distribution of gaps across proteins.
        """
        if not self.proteins:
            return 0.04

        gaps = []
        masses = []
        for name, protein in self.proteins.items():
            if protein.listening_gap is None:
                protein.compute_listening_gap()
            gaps.append(protein.listening_gap)
            masses.append(len(protein.residues))

        gaps = np.array(gaps)
        masses = np.array(masses, dtype=float)

        # Weighted average by protein size
        return float(np.average(gaps, weights=masses))

    def gap_vector(self) -> Dict[str, float]:
        """Return a dict of {protein_name: listening_gap}."""
        return {name: p.listening_gap for name, p in self.proteins.items()}


# ═══════════════════════════════════════════════════════════════════════════════
# §4. ALPHAFOLD BRIDGE — Interface to AlphaFold Predictions
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class AlphaFoldBridge:
    """
    Bridge between AlphaFold protein structure predictions and the 묘수 framework.

    Supports:
      - Loading real AlphaFold predictions (PDB, mmCIF, or AlphaFold JSON format)
      - Simulated structures for development and testing
      - Direct sequence submission (placeholder for AlphaFold Server API)
    """

    mapper: QuantumProteinMapper = field(default_factory=QuantumProteinMapper)
    base_url: str = "https://alphafoldserver.com/api"  # AlphaFold3 Server

    def from_alphafold_json(self, name: str, json_path: str) -> Protein:
        """
        Load a protein from an AlphaFold prediction JSON file.

        Expected format (AlphaFold DB / AlphaFold3 Server output):
          {
            "name": "...",
            "sequence": "MADQLT...",
            "atom_coords": [[x,y,z], ...],    # Cα coordinates
            "plddt": [0.95, 0.87, ...],       # per-residue confidence
            "pae": [[...], ...]               # predicted aligned error matrix
          }
        """
        with open(json_path) as f:
            data = json.load(f)

        sequence = data.get('sequence', '')
        coords = np.array(data.get('atom_coords', data.get('coords', [])))
        plddt = np.array(data.get('plddt', []))
        pae = np.array(data.get('pae', None))

        return self.mapper.add_protein(
            name=name, sequence=sequence, coords=coords, plddt=plddt
        )

    def from_pdb(self, name: str, pdb_path: str) -> Protein:
        """
        Extract Cα coordinates from a PDB file.
        Reads ATOM records with atom name 'CA'.
        """
        coords = []
        residues = []
        sequence_chars = []
        plddt_values = []

        with open(pdb_path) as f:
            for line in f:
                if line.startswith('ATOM') or line.startswith('HETATM'):
                    atom_name = line[12:16].strip()
                    if atom_name == 'CA':
                        try:
                            x = float(line[30:38])
                            y = float(line[38:46])
                            z = float(line[46:54])
                            coords.append([x, y, z])
                            res_name = line[17:20].strip()
                            residues.append(res_name)
                            # B-factor as pseudo-pLDDT
                            b_factor = float(line[60:66])
                            plddt_values.append(min(b_factor / 100.0, 1.0))
                        except (ValueError, IndexError):
                            continue

        coords_arr = np.array(coords) if coords else None
        plddt_arr = np.array(plddt_values) if plddt_values else None

        # Build sequence string from extracted residues
        seq_1letter = ''.join(
            {v: k for k, v in AA_1TO3.items()}.get(r, 'X')
            for r in residues
        )

        protein = Protein(
            name=name,
            sequence=seq_1letter,
            residues=residues if residues else None,
            coords=coords_arr,
            plddt=plddt_arr,
        )
        protein.compute_hamiltonian()
        protein.compute_folding_energy()
        protein.compute_listening_gap()
        self.mapper.proteins[name] = protein
        return protein

    def design_novel_protein(self, name: str, length: int = 50,
                              chiral_bias: str = 'balanced') -> Protein:
        """
        Design a novel protein sequence with specific chiral characteristics.

        chiral_bias options:
          'balanced'     — equal representation of all four classes
          'hydrophobic'  — North-dominated (stable anchor, narrow gap)
          'polar'        — West-dominated (signal-oriented, wide gap)
          'charged'      — East+South balanced (dynamic, high positron content)
          'random'       — random sequence with natural amino acid frequencies
        """
        np.random.seed(int(time.time() * 1000) % 2**31)

        natural_freq = {
            'ALA': 0.09, 'ARG': 0.06, 'ASN': 0.04, 'ASP': 0.05,
            'CYS': 0.01, 'GLN': 0.04, 'GLU': 0.07, 'GLY': 0.07,
            'HIS': 0.02, 'ILE': 0.06, 'LEU': 0.10, 'LYS': 0.06,
            'MET': 0.02, 'PHE': 0.04, 'PRO': 0.05, 'SER': 0.07,
            'THR': 0.05, 'TRP': 0.01, 'TYR': 0.03, 'VAL': 0.07,
        }

        if chiral_bias == 'balanced':
            # Equal representation of all four classes
            north_aas = [aa for aa, c in AMINO_ACID_CLASSES.items() if c == 'NORTH']
            west_aas  = [aa for aa, c in AMINO_ACID_CLASSES.items() if c == 'WEST']
            east_aas  = [aa for aa, c in AMINO_ACID_CLASSES.items() if c == 'EAST']
            south_aas = [aa for aa, c in AMINO_ACID_CLASSES.items() if c == 'SOUTH']

            residues = []
            for i in range(length):
                if i % 4 == 0:
                    residues.append(np.random.choice(north_aas))
                elif i % 4 == 1:
                    residues.append(np.random.choice(west_aas))
                elif i % 4 == 2:
                    residues.append(np.random.choice(east_aas))
                else:
                    residues.append(np.random.choice(south_aas))

        elif chiral_bias == 'hydrophobic':
            north_aas = [aa for aa, c in AMINO_ACID_CLASSES.items() if c == 'NORTH']
            others = [aa for aa in AMINO_ACID_CLASSES if aa not in north_aas]
            residues = []
            for i in range(length):
                residues.append(np.random.choice(north_aas if np.random.random() < 0.7
                                                  else others))

        elif chiral_bias == 'polar':
            west_aas = [aa for aa, c in AMINO_ACID_CLASSES.items() if c == 'WEST']
            others = [aa for aa in AMINO_ACID_CLASSES if aa not in west_aas]
            residues = []
            for i in range(length):
                residues.append(np.random.choice(west_aas if np.random.random() < 0.7
                                                  else others))

        elif chiral_bias == 'charged':
            charged = [aa for aa, c in AMINO_ACID_CLASSES.items()
                       if c in ('EAST', 'SOUTH')]
            others = [aa for aa in AMINO_ACID_CLASSES if aa not in charged]
            residues = []
            for i in range(length):
                residues.append(np.random.choice(charged if np.random.random() < 0.7
                                                  else others))

        else:  # 'random'
            aas = list(natural_freq.keys())
            probs = list(natural_freq.values())
            probs = np.array(probs) / sum(probs)
            residues = list(np.random.choice(aas, size=length, p=probs))

        # Build 1-letter sequence
        seq = ''.join({v: k for k, v in AA_1TO3.items()}.get(r, 'X') for r in residues)

        return self.mapper.add_protein(name=name, sequence=seq)

    def mutate_protein(self, protein: Protein, position: int,
                       new_residue: str) -> Protein:
        """
        Introduce a point mutation and recompute all quantum properties.
        This is how the organism evolves — one mutation at a time.
        """
        if position < 0 or position >= len(protein.residues):
            raise IndexError(f"Position {position} out of range [0, {len(protein.residues)})")

        if len(new_residue) == 1:
            new_residue = AA_1TO3.get(new_residue.upper(), new_residue)
        new_residue = new_residue.upper()
        if new_residue not in AMINO_ACID_CLASSES:
            raise ValueError(f"Unknown residue: {new_residue}")

        # Create mutated sequence
        old_residues = protein.residues.copy()
        old_residues[position] = new_residue
        seq = ''.join({v: k for k, v in AA_1TO3.items()}.get(r, 'X')
                      for r in old_residues)

        # New protein with same name + mutation tag
        mut_name = f"{protein.name}_{old_residues[position]}{position+1}{new_residue}"
        mut_protein = Protein(name=mut_name, sequence=seq)
        mut_protein.compute_hamiltonian()
        mut_protein.compute_folding_energy()
        mut_protein.compute_listening_gap()

        # If original had real coordinates, perturb them at mutation site
        if protein.coords is not None:
            mut_protein.coords = protein.coords.copy()
            # Slight perturbation at mutation site
            mut_protein.coords[position] += np.random.normal(0, 0.5, 3)
            mut_protein.contact_map = mut_protein._compute_contact_map(8.0)

        self.mapper.proteins[mut_name] = mut_protein
        return mut_protein


# ═══════════════════════════════════════════════════════════════════════════════
# §5. NEW ORGANISM — The AlphaFold-Enhanced Organ Fleet
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class NewOrganism:
    """
    A new generation of organism — one whose gap Δ emerges from the
    quantum-coherent dynamics of its entire proteome rather than a single
    phenomenological scalar.

    This organism has:
      - A proteome (multiple proteins) mapped to quantum Hamiltonians
      - A sinoatrial node that integrates proteome-wide listening into one pulse
      - An Åverdön breath-door that opens when protein resonance is maximized
      - Mutation tracking: how genetic changes alter the quantum landscape

    The organism evolves. It can be mutated, its proteins can fold and unfold,
    and the 묘수 field listens to the entire proteome as one living system.
    """

    name: str = "Organism-1"
    bridge: AlphaFoldBridge = field(default_factory=AlphaFoldBridge)
    node: SinoatrialNode = field(default_factory=SinoatrialNode)
    spacetime: ListeningSpacetime = field(default_factory=ListeningSpacetime)

    # State
    generation: int = 0
    beat_count: int = 0
    gap_history: List[float] = field(default_factory=list)
    mutation_history: List[Dict] = field(default_factory=list)

    def __post_init__(self):
        # Build initial proteome if empty
        if not self.bridge.mapper.proteins:
            self._seed_proteome()

    def _seed_proteome(self, n_proteins: int = 5):
        """Seed the organism with an initial set of designed proteins."""
        designs = [
            ('actin', 42, 'balanced'),
            ('kinase', 35, 'charged'),
            ('membrane', 28, 'hydrophobic'),
            ('signaling', 45, 'polar'),
            ('chaperone', 38, 'random'),
        ]
        for i, (name, length, bias) in enumerate(designs[:n_proteins]):
            self.bridge.design_novel_protein(f"{self.name}_{name}", length, bias)

        print(f"  Seeded proteome with {len(self.bridge.mapper.proteins)} proteins.")

    @property
    def proteome_gap(self) -> float:
        """The organism's integrated listening gap from its entire proteome."""
        return self.bridge.mapper.proteome_listening_gap()

    @property
    def gap_vector(self) -> Dict[str, float]:
        """Per-protein gap values."""
        return self.bridge.mapper.gap_vector()

    @property
    def chiral_balance(self) -> np.ndarray:
        """Proteome-wide chiral class distribution [NORTH, WEST, EAST, SOUTH]."""
        count = np.zeros(4)
        for name, protein in self.bridge.mapper.proteins.items():
            for res in protein.residues:
                direction = AMINO_ACID_CLASSES.get(res, 'WEST')
                idx = {'NORTH': 0, 'WEST': 1, 'EAST': 2, 'SOUTH': 3}[direction]
                count[idx] += 1
        total = count.sum()
        return count / max(total, 1)

    @property
    def myosu_field(self) -> MyosuField:
        """Assemble the 묘수 unified field from the proteome."""
        wf = self.bridge.mapper.proteome_wavefunction()
        spinor = self.bridge.mapper.proteome_spinor()
        sp = self.spacetime
        sp.hrv_signal = self.node.lambda_consciousness
        return MyosuField(spinor=spinor, spacetime=sp, wavefunction=wf)

    @property
    def averdon(self) -> Averdon:
        """The breath-door for this organism."""
        return Averdon(node=self.node, field=self.myosu_field)

    def beat(self) -> dict:
        """
        One heartbeat of the organism.

        Evolves the quantum state, computes the proteome gap, fires the
        sinoatrial node, and computes the breath-door state directly
        using the proteome gap (not the pure-state entropy, which is always 0).
        """
        self.beat_count += 1
        t = self.beat_count * 0.05

        # Current proteome gap
        gap = self.proteome_gap
        self.gap_history.append(gap)

        # Sinoatrial beat
        sa_beat = self.node.beat(t)
        lam = sa_beat['Lambda']

        # ══ Åverdön door state — computed directly from proteome metrics ══
        # North: listening depth = proteome gap
        north = gap
        # South: chiral pull = positron_content from proteome spinor
        spinor = self.bridge.mapper.proteome_spinor()
        south = spinor.positron_content
        # West: pure signal = four-current magnitude
        west = np.linalg.norm(spinor.four_current())
        # East: resistance = how far from harmonic balance
        cb = self.chiral_balance
        east = abs(cb[2] - cb[3]) / max(cb[2] + cb[3], 0.001)  # acid-base imbalance

        # The door opens when listening depth × signal exceeds resistance
        openness = float((north * (1.0 + south) * west) / (1.0 + east))
        is_open = openness > 0.05  # threshold for door to crack open

        # ══ 점화 (Spark): voltage across the gap ══
        voltage = gap * abs(lam) / (1.0 + east)
        has_sparked = voltage > 0.008  # threshold

        return {
            'beat': self.beat_count,
            't': t,
            'proteome_gap': round(gap, 6),
            'gap_health': 'ALIVE' if 0.01 < gap < 0.10 else 'PATHOLOGICAL',
            'n_proteins': len(self.bridge.mapper.proteins),
            'chiral_balance': {
                'NORTH': round(float(cb[0]), 4),
                'WEST':  round(float(cb[1]), 4),
                'EAST':  round(float(cb[2]), 4),
                'SOUTH': round(float(cb[3]), 4),
            },
            'Lambda': lam,
            'listening': sa_beat['listening'],
            'door_open': is_open,
            'door_openness': round(openness, 4),
            'spark_voltage': round(voltage, 6),
            'has_sparked': has_sparked,
            'gap_vector': self.gap_vector,
        }

    def tick(self, dt: float = 0.05) -> dict:
        """Alias for beat() — compatibility with 묘수 protocol."""
        return self.beat()

    def mutate(self, protein_name: str, position: int,
               new_residue: str) -> dict:
        """
        Introduce a mutation and observe how the organism's quantum landscape shifts.
        """
        if protein_name not in self.bridge.mapper.proteins:
            return {'error': f"Protein '{protein_name}' not found"}

        old_gap = self.proteome_gap
        old_protein = self.bridge.mapper.proteins[protein_name]
        old_residue = old_protein.residues[position]

        mut_protein = self.bridge.mutate_protein(old_protein, position, new_residue)

        # Replace the old protein with the mutated one
        self.bridge.mapper.proteins[protein_name] = mut_protein
        self.generation += 1

        new_gap = self.proteome_gap
        delta_gap = new_gap - old_gap

        mutation_record = {
            'generation': self.generation,
            'beat': self.beat_count,
            'protein': protein_name,
            'position': position,
            'from': old_residue,
            'to': new_residue,
            'old_gap': round(old_gap, 6),
            'new_gap': round(new_gap, 6),
            'delta_gap': round(delta_gap, 6),
            'folding_energy': round(mut_protein.folding_energy, 4),
        }
        self.mutation_history.append(mutation_record)

        return mutation_record

    def evolve_step(self, mutation_rate: float = 0.01) -> dict:
        """
        One evolution step: beat + possible mutation.

        The organism listens (beats). If the breath-door is open enough,
        a mutation may occur — the soil (흙) writes a new letter into the sequence.
        Returns the combined state.
        """
        state = self.beat()
        state['mutation'] = None

        # Probability of mutation scales with door openness × mutation_rate
        # Also scales with generation number (older organisms mutate more)
        p_mutate = mutation_rate * state['door_openness'] * (1.0 + 0.05 * self.generation)
        if np.random.random() < p_mutate:
            # Pick a random protein and position
            prot_names = list(self.bridge.mapper.proteins.keys())
            if prot_names:
                target = np.random.choice(prot_names)
                protein = self.bridge.mapper.proteins[target]
                if len(protein.residues) > 0:
                    pos = np.random.randint(len(protein.residues))
                    all_aas = list(AMINO_ACID_CLASSES.keys())
                    new_aa = np.random.choice(all_aas)
                    mut = self.mutate(target, pos, new_aa)
                    state['mutation'] = mut

        return state

    def simulate_generations(self, n_generations: int = 10,
                             beats_per_gen: int = 5,
                             mutation_rate: float = 0.02) -> List[dict]:
        """
        Simulate multiple generations of organism evolution.
        Returns a history of all beats.
        """
        history = []
        for gen in range(n_generations):
            for _ in range(beats_per_gen):
                state = self.evolve_step(mutation_rate=mutation_rate)
                history.append(state)

        return history

    def to_summary(self) -> dict:
        """Full organism state summary."""
        return {
            'name': self.name,
            'generation': self.generation,
            'beat_count': self.beat_count,
            'proteome_gap': round(self.proteome_gap, 6),
            'n_proteins': len(self.bridge.mapper.proteins),
            'n_residues': sum(len(p.residues) for p in self.bridge.mapper.proteins.values()),
            'chiral_balance': {
                'NORTH': round(float(self.chiral_balance[0]), 4),
                'WEST':  round(float(self.chiral_balance[1]), 4),
                'EAST':  round(float(self.chiral_balance[2]), 4),
                'SOUTH': round(float(self.chiral_balance[3]), 4),
            },
            'avg_gap': round(np.mean(self.gap_history[-100:]), 6)
                        if self.gap_history else 0.0,
            'gap_stdev': round(np.std(self.gap_history[-100:]), 6)
                          if len(self.gap_history) > 1 else 0.0,
            'n_mutations': len(self.mutation_history),
            'recent_mutations': self.mutation_history[-5:],
            'gap_vector': self.gap_vector,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# §6. DEMO — AlphaFold-Enhanced Organism Simulation
# ═══════════════════════════════════════════════════════════════════════════════

def demo():
    """Run a demonstration of the AlphaFold-묘수 bridge."""
    print("=" * 70)
    print("  AlphaFold → 묘수 BRIDGE — New Generation Organism")
    print("=" * 70)

    # 1. Create the organism
    print("\n── §1. Seeding the organism ──")
    org = NewOrganism(name="AlphaFold-Being")

    # 2. Print proteome
    print(f"\n── §2. Proteome overview ({len(org.bridge.mapper.proteins)} proteins) ──")
    for name, protein in org.bridge.mapper.proteins.items():
        print(f"  {name}: {len(protein.residues)} residues, "
              f"gap={protein.listening_gap:.4f}, "
              f"folding_energy={protein.folding_energy:.2f}")

    # 3. Chiral balance
    cb = org.chiral_balance
    print(f"\n── §3. Chiral Balance ──")
    print(f"  NORTH (anchor/hydrophobic): {cb[0]:.3f}")
    print(f"  WEST  (signal/polar):       {cb[1]:.3f}")
    print(f"  EAST  (echo/acidic):        {cb[2]:.3f}")
    print(f"  SOUTH (future/basic):       {cb[3]:.3f}")

    # 4. First beats
    print(f"\n── §4. First 5 heartbeats ──")
    for i in range(5):
        state = org.beat()
        door_icon = "🚪" if state['door_open'] else "⬜"
        spark_icon = "⚡" if state['has_sparked'] else "  "
        print(f"  Beat {state['beat']:3d}: gap={state['proteome_gap']:.4f}  "
              f"Λ={state['Lambda']:.3f}  {door_icon} {spark_icon}  "
              f"door={state['door_openness']:.3f}")

    # 5. Introduce mutations and observe gap shift
    print(f"\n── §5. Mutation experiment ──")
    target_prot = list(org.bridge.mapper.proteins.keys())[0]
    protein = org.bridge.mapper.proteins[target_prot]

    print(f"  Target protein: {target_prot} ({len(protein.residues)} residues)")
    print(f"  Initial proteome gap: {org.proteome_gap:.6f}")
    print(f"  Initial protein gap:  {protein.listening_gap:.6f}")

    # Test three mutations at different positions
    test_mutations = [
        (0, 'TRP'),       # Nonpolar → Nonpolar on hydrophobic residue
        (len(protein.residues)//2, 'LYS'),   # Mid-protein charge change
        (len(protein.residues)-1, 'ASP'),    # C-terminus charge flip
    ]

    for pos, new_aa in test_mutations:
        if pos >= len(protein.residues):
            continue
        old_res = protein.residues[pos]
        mut = org.mutate(target_prot, pos, new_aa)
        direction = '▲' if mut['delta_gap'] > 0 else '▼'
        print(f"  {old_res}{pos+1}{new_aa}: gap {mut['old_gap']:.6f} → "
              f"{mut['new_gap']:.6f} ({direction}{abs(mut['delta_gap']):.6f})  "
              f"ΔE_fold={mut['folding_energy']:.2f}")

    # 6. Evolution simulation
    print(f"\n── §6. Evolution: 20 generations × 5 beats ──")
    history = org.simulate_generations(n_generations=20, beats_per_gen=5,
                                        mutation_rate=0.30)

    gap_trace = [h['proteome_gap'] for h in history]
    mutations_found = sum(1 for h in history if h.get('mutation'))
    print(f"  Total beats: {len(history)}")
    print(f"  Mutations occurred: {mutations_found}")
    print(f"  Gap range: [{min(gap_trace):.4f}, {max(gap_trace):.4f}]")
    print(f"  Final gap: {gap_trace[-1]:.6f}")

    # 7. Final organism summary
    print(f"\n── §7. Organism summary ──")
    summary = org.to_summary()
    for key, val in summary.items():
        if key not in ('gap_vector', 'recent_mutations'):
            print(f"  {key}: {val}")

    if summary['recent_mutations']:
        print(f"\n  Recent mutations:")
        for mut in summary['recent_mutations']:
            print(f"    Gen {mut['generation']}: {mut['protein']} "
                  f"{mut['from']}{mut['position']+1}{mut['to']} "
                  f"Δgap={mut['delta_gap']:.6f}")

    print(f"\n{'=' * 70}")
    print("  The organism lives. 신 한 마리 listens through its proteome.")
    print(f"{'=' * 70}")

    return org


# ═══════════════════════════════════════════════════════════════════════════════
# §7. GO/PLGA-PEG/HA SCAFFOLD — The Bioelectronic Substrate
# ═══════════════════════════════════════════════════════════════════════════════

# Force α = 7.68 as the unified coupling constant across the entire scaffold.
# This is ALPHA_T from the 묘수 protocol — the transmission maximum where
# the Berry curvature F_μν = 0 and the Dirac operator becomes self-adjoint.
ALPHA_SCAFFOLD = 7.68

@dataclass
class Scaffold:
    """
    GO / PLGA-PEG / HA — The bioelectronic substrate.

    A conductive, biocompatible three-layer scaffold hosting the organism:
      - GO  (Graphene Oxide):      electron transport layer, π-π stacking sites
      - PLGA-PEG (copolymer):     dielectric spacer, tunable degradation rate
      - HA  (Hyaluronic Acid):     hydrogel matrix, cell-adhesion domains

    The scaffold mediates quantum coupling between proteins via:
      - GO  → π-orbital overlap → coherent electron transfer (hopping)
      - PLGA-PEG → dielectric constant ε_r → screens Coulomb interactions
      - HA  → proton conductivity → pH-gated quantum channels

    All couplings are scaled by α = 7.68 — the fixed point where the
    Dirac operator is self-adjoint and F_μν(Berry) = 0.
    """

    # Layer properties
    go_conductivity: float = 1.0e3       # S/cm — graphene oxide sheet conductivity
    go_thickness: float = 10.0           # nm
    plga_peg_dielectric: float = 3.5     # ε_r at 1 kHz
    plga_peg_thickness: float = 50.0     # nm
    ha_proton_conductivity: float = 1e-4  # S/cm — proton-hopping conductivity
    ha_thickness: float = 100.0          # nm

    # Unified coupling
    alpha: float = ALPHA_SCAFFOLD         # 7.68 — the fixed point

    # Scaffold quantum state
    coupling_matrix: Optional[np.ndarray] = None   # protein-protein coupling via scaffold

    def total_thickness(self) -> float:
        return self.go_thickness + self.plga_peg_thickness + self.ha_thickness

    def go_hopping_integral(self, distance_angstrom: float) -> float:
        """
        GO-mediated electron hopping between two protein sites separated by
        distance d (Å). The π-π overlap decays exponentially with distance,
        modulated by the GO conductivity and α.
        """
        # Base hopping: exponential decay with GO's π-stacking distance (~3.4 Å)
        t0 = self.go_conductivity * 1e-3  # scale to eV-like
        lam_pi = 3.4  # π-stacking distance in Å
        return t0 * math.exp(-distance_angstrom / lam_pi) * (self.alpha / 8.8)

    def plga_peg_screening(self, distance_angstrom: float) -> float:
        """
        Dielectric screening factor from the PLGA-PEG layer.
        Reduces Coulomb repulsion between charged residues, enabling
        closer quantum coupling. ε_r = 3.5 at physiological frequencies.
        """
        # Coulomb screening: V_eff = V / ε_r
        return 1.0 / self.plga_peg_dielectric

    def ha_proton_coupling(self, distance_angstrom: float, ph: float = 7.4) -> float:
        """
        HA proton-hopping conductivity. pH-dependent — at physiological
        pH 7.4, protons hop along hyaluronan chains via Grotthuss mechanism.
        This forms a quantum channel for proton-coupled electron transfer (PCET).
        """
        # Proton hopping rate scales with protonation state
        # At pH 7.4, HA carboxyl groups (pKa ~3-4) are deprotonated
        # → negatively charged matrix → attracts protons → hopping
        protonation = 1.0 / (1.0 + 10 ** (ph - 4.0))  # fraction protonated
        hopping_rate = self.ha_proton_conductivity * (1.0 - protonation)
        return hopping_rate * math.exp(-distance_angstrom / 5.0) * (self.alpha / 8.8)

    def build_coupling_matrix(self, proteins: Dict[str, 'Protein']) -> np.ndarray:
        """
        Build the scaffold-mediated inter-protein coupling matrix.

        For N proteins, produces an M×M matrix (M = total residues) where
        off-diagonal blocks represent scaffold-mediated coupling between
        proteins that would otherwise not interact directly.

        The coupling tensor J_ij = GO_hop(i,j) × PLGA_screen × HA_proton(i,j)
        scaled by α = 7.68.
        """
        N = sum(len(p.residues) for p in proteins.values())
        J = np.zeros((N, N))

        offsets = {}
        off = 0
        for name in proteins:
            offsets[name] = off
            off += len(proteins[name].residues)

        prot_names = list(proteins.keys())
        for i, ni in enumerate(prot_names):
            for j, nj in enumerate(prot_names):
                if i >= j:
                    continue
                pi = proteins[ni]
                pj = proteins[nj]
                if pi.coords is None or pj.coords is None:
                    continue

                oi, oj = offsets[ni], offsets[nj]

                # Compute all inter-protein residue distances
                for ri in range(len(pi.residues)):
                    for rj in range(len(pj.residues)):
                        d = np.linalg.norm(pi.coords[ri] - pj.coords[rj])
                        # Scaffold-mediated coupling
                        go_hop = self.go_hopping_integral(d)
                        screen = self.plga_peg_screening(d)
                        ha_coup = self.ha_proton_coupling(d)

                        # Total coupling: GO electron transfer × screening × proton channel
                        J_ij = go_hop * screen * ha_coup * (self.alpha / 8.8) ** 2
                        J[oi + ri, oj + rj] = J_ij
                        J[oj + rj, oi + ri] = J_ij  # symmetric

        self.coupling_matrix = J
        return J


# ═══════════════════════════════════════════════════════════════════════════════
# §8. SELF-DIRAC EQUATIONS — |0⟩ and |1⟩ at α = 7.68
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class SelfDiracEquations:
    """
    The Dyson self-energy equations for the two-state Dirac system.

    The organism operates on a computational basis:
      |0⟩ = ground state (North-like, time/anchor, hydrophobic core)
      |1⟩ = excited state (South-like, chiral/future, charged surface)

    The bare Dirac equation:
        (iγ^μ ∂_μ - m) ψ = 0

    With self-energy Σ(E) from scaffold-mediated interactions:
        G(E) = G₀(E) + G₀(E) · Σ(E) · G(E)

    At α = 7.68 (the fixed point), Σ(E) becomes purely real — no decay,
    no decoherence. The Dirac operator is self-adjoint:
        D† = D  ⇔  (iγ^μ ∂_μ - m)† = (iγ^μ ∂_μ - m)

    This is the F_μν(Berry) = 0 condition — zero curvature,
    non-zero holonomy. The gap stays open; the listening continues.
    """

    alpha: float = ALPHA_SCAFFOLD  # 7.68 — the fixed point
    mass: float = 1.0              # bare mass (eV)
    momentum: float = 0.0          # |p| (eV/c)

    # ── Bare Hamiltonian in {|0⟩, |1⟩} basis ──
    def bare_hamiltonian(self) -> np.ndarray:
        """
        H₀ in the two-state basis.

        |0⟩ has energy -m (the anchor, the ground)
        |1⟩ has energy +m (the future, the excited state)

        At α = 7.68, the off-diagonal coupling is α·p — this is the
        Dirac operator's kinetic term mixing the two chiralities.
        """
        m = self.mass
        p = self.momentum
        return np.array([
            [ m,     self.alpha * p],
            [ self.alpha * p,   -m],
        ], dtype=complex)

    def eigenvalues(self) -> Tuple[float, float]:
        """
        The two eigenvalues of H₀:
            E_± = ± sqrt(m² + (α·p)²)

        At α = 7.68 and p → 0: E_± → ± m
        The spectral gap = 2m = 2.0 eV (baseline).
        """
        m = self.mass
        ap = self.alpha * self.momentum
        E = math.sqrt(m**2 + ap**2)
        return (-E, +E)

    def spectral_gap(self) -> float:
        """The gap between |0⟩ and |1⟩."""
        E_minus, E_plus = self.eigenvalues()
        return E_plus - E_minus

    # ── Self-energy Σ(E) — Dyson series ──
    def self_energy_00(self, E: float, coupling_strength: float = 1.0) -> complex:
        """
        Σ₀₀(E) — self-energy of the ground state |0⟩.

        Σ₀₀(E) = g² ∫ dω ρ(ω) / (E - ω + iε)

        Where ρ(ω) is the scaffold's spectral density.
        At α = 7.68, Im[Σ₀₀] → 0 (no decay, self-adjoint).
        """
        m = self.mass
        g = coupling_strength * (self.alpha / 8.8)
        # Poles at ω = ±E_k where E_k = sqrt(m² + (αk)²)
        # For the scaffold, the spectral function has weight at the bare energies
        E_plus = math.sqrt(m**2 + (self.alpha * self.momentum)**2)

        # Real part: principal value integral over spectral density
        re_sigma = g**2 * (E - m) / ((E - m)**2 + (self.alpha * 0.1)**2)

        # Imaginary part: at α = 7.68, Im[Σ] → 0 (fixed-point condition)
        # The residual is proportional to |α - 7.68|
        im_sigma = g**2 * abs(self.alpha - 7.68) / 100.0

        return re_sigma - 1j * im_sigma

    def self_energy_11(self, E: float, coupling_strength: float = 1.0) -> complex:
        """
        Σ₁₁(E) — self-energy of the excited state |1⟩.

        Mirror of Σ₀₀ with sign flip on the mass term.
        The excited state couples to the scaffold's anti-resonances.
        """
        m = self.mass
        g = coupling_strength * (self.alpha / 8.8)
        E_minus = -math.sqrt(m**2 + (self.alpha * self.momentum)**2)

        re_sigma = g**2 * (E + m) / ((E + m)**2 + (self.alpha * 0.1)**2)
        im_sigma = g**2 * abs(self.alpha - 7.68) / 100.0

        return re_sigma - 1j * im_sigma

    def self_energy_01(self, E: float, coupling_strength: float = 1.0) -> complex:
        """
        Σ₀₁(E) — off-diagonal self-energy coupling |0⟩ ↔ |1⟩.

        This is the scaffold-mediated transition amplitude.
        At α = 7.68, it becomes purely real → coherent Rabi oscillation,
        no decoherence.
        """
        g = coupling_strength * (self.alpha / 8.8)
        ap = self.alpha * self.momentum

        # Off-diagonal coupling proportional to α·p (the kinetic mixing)
        re_sigma = g * ap / (1.0 + (E / self.mass)**2)
        im_sigma = g * abs(self.alpha - 7.68) * ap / 1000.0

        return re_sigma - 1j * im_sigma

    def dressed_hamiltonian(self, E: float, coupling_strength: float = 1.0) -> np.ndarray:
        """
        The fully dressed Hamiltonian:
            H(E) = H₀ + Σ(E)

        where Σ(E) = [[Σ₀₀, Σ₀₁], [Σ₀₁*, Σ₁₁]]

        The dressed eigenvalues give the quasiparticle spectrum.
        At α = 7.68, H(E) is Hermitian (Im[Σ] → 0).
        """
        H0 = self.bare_hamiltonian()
        Sigma = np.array([
            [self.self_energy_00(E, coupling_strength),
             self.self_energy_01(E, coupling_strength)],
            [np.conj(self.self_energy_01(E, coupling_strength)),
             self.self_energy_11(E, coupling_strength)],
        ], dtype=complex)
        return H0 + Sigma

    def dressed_spectrum(self, E: float, coupling_strength: float = 1.0) -> Tuple[float, float]:
        """Eigenvalues of the dressed Hamiltonian."""
        H = self.dressed_hamiltonian(E, coupling_strength)
        evals = np.linalg.eigvalsh(H)
        return (float(evals[0]), float(evals[1]))

    def self_adjointness_check(self, coupling_strength: float = 1.0) -> dict:
        """
        Verify the self-adjointness condition at α = 7.68.

        For a Dirac operator to be self-adjoint:
            D† = D
        which requires:
            Im[⟨0|Σ|0⟩] = 0
            Im[⟨1|Σ|1⟩] = 0
            Σ₀₁ = Σ₁₀*  (off-diagonal symmetry)

        Returns the violation metric — how far from self-adjoint.
        """
        E_test = self.mass  # evaluate at the gap center
        s00 = self.self_energy_00(E_test, coupling_strength)
        s11 = self.self_energy_11(E_test, coupling_strength)
        s01 = self.self_energy_01(E_test, coupling_strength)

        violation_00 = abs(s00.imag)
        violation_11 = abs(s11.imag)
        violation_01 = abs(s01.imag)

        is_self_adjoint = (
            violation_00 < 1e-6 and
            violation_11 < 1e-6 and
            violation_01 < 1e-6
        )

        return {
            'alpha': self.alpha,
            'alpha_fixed': abs(self.alpha - 7.68) < 0.001,
            'Im_Sigma_00': violation_00,
            'Im_Sigma_11': violation_11,
            'Im_Sigma_01': violation_01,
            'is_self_adjoint': is_self_adjoint,
            'F_munu_zero': is_self_adjoint,
            'condition': 'D† = D — Dirac operator is self-adjoint'
                         if is_self_adjoint
                         else 'Self-adjointness violated — adjust α',
        }

    def compute_green_function(self, E: float, coupling_strength: float = 1.0) -> np.ndarray:
        """
        The full Green's function (resolvent):
            G(E) = [E·I - H(E)]^{-1}

        The poles of G(E) give the quasiparticle spectrum.
        |0⟩ and |1⟩ are the two poles nearest the real axis.
        """
        H = self.dressed_hamiltonian(E, coupling_strength)
        I2 = np.eye(2, dtype=complex)
        G = np.linalg.inv(E * I2 - H)
        return G

    def transition_probability(self, t: float, coupling_strength: float = 1.0) -> float:
        """
        |⟨1|e^{-iHt}|0⟩|² — the Rabi oscillation probability.

        The scaffold mediates coherent |0⟩ ↔ |1⟩ transitions.
        At α = 7.68, this is a pure sinusoidal oscillation (no decay).
        """
        H = self.dressed_hamiltonian(self.mass, coupling_strength)
        # Time evolution operator
        U = linalg.expm(-1j * H * t)
        # Probability of |0⟩ → |1⟩ transition
        P_01 = abs(U[1, 0]) ** 2
        return float(P_01)

    def von_neumann_entropy_01(self, coupling_strength: float = 1.0) -> float:
        """
        The entanglement entropy between |0⟩ and |1⟩ subsystems.

        S = -Tr(ρ₀ log₂ ρ₀) where ρ₀ is the reduced density matrix
        of the |0⟩ subsystem after tracing out |1⟩.

        At α = 7.68, this entropy IS the organism's listening gap —
        the quantum coherence between its two computational basis states.
        """
        H = self.dressed_hamiltonian(self.mass, coupling_strength)
        evals, evecs = np.linalg.eigh(H)
        ground = evecs[:, 0]

        # Reduced density matrix of |0⟩ subsystem
        # ρ₀ = Tr_{|1⟩}[|ψ⟩⟨ψ|]
        rho_0 = np.array([
            [abs(ground[0])**2, ground[0] * np.conj(ground[1])],
            [ground[1] * np.conj(ground[0]), abs(ground[1])**2],
        ])
        # Actually, for a 2-state pure system, this is just:
        p0 = abs(ground[0])**2
        p1 = abs(ground[1])**2
        if p0 > 1e-15 and p1 > 1e-15:
            S = -p0 * math.log2(p0) - p1 * math.log2(p1)
        elif p0 > 1e-15:
            S = -p0 * math.log2(p0)
        else:
            S = 0.0
        return S


# ═══════════════════════════════════════════════════════════════════════════════
# §9. HRV COUPLING — Vagal Tone from Heart Rate Variability
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class HRVCoupling:
    """
    Heart Rate Variability → Vagal Tone → Λ(t) → Gap modulation.

    HRV data drives the sinoatrial node's vagal brake:
      - High HRV (SDNN > 50 ms)  → vagal dominance → Λ > 0 → gap widens
      - Low HRV  (SDNN < 20 ms)  → sympathetic dominance → Λ < 0 → gap closes

    The coupling constant α = 7.68 scales the HRV → Λ mapping.
    This is the same α that appears in the Dirac equations — the
    fixed point where F_μν(Berry) = 0.
    """

    alpha: float = ALPHA_SCAFFOLD  # 7.68

    # HRV metrics
    sdnn: float = 50.0              # ms — standard deviation of NN intervals
    rmssd: float = 42.0             # ms — root mean square of successive differences
    lf_hf_ratio: float = 1.5        # LF/HF power ratio (sympathovagal balance)
    mean_rr: float = 1000.0         # ms — mean RR interval (~60 BPM baseline)
    rr_series: Optional[np.ndarray] = None  # raw RR interval time series

    def vagal_tone_from_hrv(self) -> float:
        """
        Compute vagal tone (0-1) from HRV metrics.

        Vagal tone = f(SDNN, RMSSD, LF/HF) mapped through α.

        High SDNN + high RMSSD + low LF/HF → strong vagal → high tone
        The α = 7.68 scaling ensures the mapping saturates correctly
        at the fixed point.
        """
        # Normalize HRV parameters to [0, 1]
        sdnn_norm = min(self.sdnn / 100.0, 1.0)     # 100ms = max healthy SDNN
        rmssd_norm = min(self.rmssd / 80.0, 1.0)    # 80ms = max healthy RMSSD
        lf_hf_inv = 1.0 / max(self.lf_hf_ratio, 0.1)  # invert: high LF/HF → low vagal

        # Raw vagal: weighted combination
        vagal_raw = 0.3 * sdnn_norm + 0.3 * rmssd_norm + 0.4 * min(lf_hf_inv, 1.0)

        # Scale through α — the fixed-point sigmoid
        vagal = 1.0 / (1.0 + math.exp(-(vagal_raw - 0.5) * self.alpha / 8.8))

        return vagal

    def sympathetic_tone_from_hrv(self) -> float:
        """Sympathetic tone = 1 - vagal tone (simplified balance)."""
        return 1.0 - self.vagal_tone_from_hrv()

    def lambda_t(self, t: float) -> float:
        """
        Λ(t) — the cosmological listening coefficient driven by HRV.

        Λ(t) = α · (vagal - sympathetic) + HRV oscillation

        The α = 7.68 factor amplifies the vagal-sympathetic difference
        into the cosmological constant. This is the same α that keeps
        F_μν(Berry) = 0 — the listening condition.
        """
        vagal = self.vagal_tone_from_hrv()
        symp = self.sympathetic_tone_from_hrv()
        delta = vagal - symp

        # HRV oscillation: respiratory sinus arrhythmia (~0.25 Hz) +
        # low-frequency Mayer waves (~0.1 Hz)
        hrv_osc = 0.1 * math.sin(2 * math.pi * t * 0.25)  # RSA
        hrv_osc += 0.05 * math.sin(2 * math.pi * t * 0.1)  # Mayer wave

        return self.alpha * delta + hrv_osc

    def compute_hrv_metrics_from_rr(self):
        """Compute SDNN, RMSSD from raw RR interval series."""
        if self.rr_series is None or len(self.rr_series) < 2:
            return
        self.sdnn = float(np.std(self.rr_series))
        diffs = np.diff(self.rr_series)
        self.rmssd = float(np.sqrt(np.mean(diffs**2)))
        self.mean_rr = float(np.mean(self.rr_series))

    def generate_synthetic_hrv(self, duration_seconds: float = 300.0,
                                sampling_rate: float = 4.0) -> np.ndarray:
        """
        Generate a synthetic HRV time series with realistic spectral properties.
        Returns RR intervals in ms sampled at ~4 Hz.
        """
        n = int(duration_seconds * sampling_rate)
        t = np.arange(n) / sampling_rate

        # Baseline RR at ~60 BPM (1000 ms)
        rr = np.full(n, 1000.0)

        # Respiratory sinus arrhythmia: ~0.25 Hz, amplitude ~40 ms
        rr += 40.0 * np.sin(2 * np.pi * t * 0.25)

        # Low-frequency Mayer waves: ~0.1 Hz, amplitude ~30 ms
        rr += 30.0 * np.sin(2 * np.pi * t * 0.1)

        # Very low frequency: ~0.04 Hz, amplitude ~20 ms
        rr += 20.0 * np.sin(2 * np.pi * t * 0.04 + 1.0)

        # Add 1/f noise
        noise = np.fft.irfft(
            np.fft.rfft(np.random.randn(n)) / (np.fft.rfftfreq(n, 1/sampling_rate) + 0.01)
        ).real[:n]
        rr += noise * 5.0

        self.rr_series = rr
        self.compute_hrv_metrics_from_rr()
        return rr


# ═══════════════════════════════════════════════════════════════════════════════
# §10. SCAFFOLD ORGANISM — The Complete Integrated System
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ScaffoldOrganism:
    """
    A complete organism grown on the GO/PLGA-PEG/HA scaffold.

    Integrates:
      - AlphaFold protein structures              (§1-5)
      - GO/PLGA-PEG/HA bioelectronic scaffold     (§7)
      - Self-Dirac equations for |0⟩ and |1⟩      (§8)
      - HRV-driven vagal tone and Λ(t)            (§9)
      - 묘수 unified field                         (myosu_core)

    The organism's sinoatrial node fires at 55 BPM (DIRAC_BPM).
    The listening gap emerges from the scaffold-mediated |0⟩ ↔ |1⟩
    entanglement, scaled by α = 7.68.

    The self-Dirac equations ensure F_μν(Berry) = 0:
    zero curvature on the Fisher manifold, non-zero global holonomy.
    The organism doesn't compute — it witnesses.
    """

    name: str = "Scaffold-Being"
    scaffold: Scaffold = field(default_factory=Scaffold)
    hrv: HRVCoupling = field(default_factory=HRVCoupling)
    dirac: SelfDiracEquations = field(default_factory=SelfDiracEquations)
    organism: NewOrganism = field(default_factory=NewOrganism)

    # State
    beat_count: int = 0
    gap_history: List[float] = field(default_factory=list)
    lambda_history: List[float] = field(default_factory=list)

    def __post_init__(self):
        # Connect HRV to sinoatrial node
        self.organism.node.vagal_tone = self.hrv.vagal_tone_from_hrv()
        self.organism.node.sympathetic_tone = self.hrv.sympathetic_tone_from_hrv()

    @property
    def proteome_gap(self) -> float:
        """Organism gap from the proteome."""
        return self.organism.proteome_gap

    @property
    def dirac_gap(self) -> float:
        """
        The self-Dirac gap — entanglement entropy between |0⟩ and |1⟩.

        This IS the organism's quantum listening gap at the two-state level.
        The proteome gap (many-body) and the Dirac gap (two-state) are
        different perspectives on the same listening condition.
        """
        return self.dirac.von_neumann_entropy_01()

    @property
    def gap(self) -> float:
        """
        The unified listening gap.

        Combines the proteome gap (structural) with the Dirac gap (quantum)
        through the scaffold coupling constant α = 7.68.
        """
        pg = self.proteome_gap
        dg = self.dirac_gap
        # Weighted combination: proteome (many-body) + Dirac (two-state)
        return 0.6 * pg + 0.4 * dg

    def beat(self) -> dict:
        """One heartbeat of the scaffold organism."""
        self.beat_count += 1
        t = self.beat_count * DIRAC_PERIOD  # 60/55 ≈ 1.09s per beat

        # Update HRV-driven vagal tone
        vagal = self.hrv.vagal_tone_from_hrv()
        symp = self.hrv.sympathetic_tone_from_hrv()
        self.organism.node.vagal_tone = vagal
        self.organism.node.sympathetic_tone = symp

        # Λ(t) from HRV
        lam = self.hrv.lambda_t(t)
        self.lambda_history.append(lam)

        # Proteome gap
        pg = self.proteome_gap

        # Dirac gap (|0⟩ ↔ |1⟩ entanglement)
        dg = self.dirac_gap
        self.gap_history.append(self.gap)

        # Self-adjointness check
        sa_check = self.dirac.self_adjointness_check()

        # Transition probability |0⟩ → |1⟩
        P_01 = self.dirac.transition_probability(t * 0.1)

        # Door and spark (from proteome metrics)
        cb = self.organism.chiral_balance
        spinor = self.organism.bridge.mapper.proteome_spinor()
        north = self.gap
        south = spinor.positron_content
        west = np.linalg.norm(spinor.four_current())
        east = abs(cb[2] - cb[3]) / max(cb[2] + cb[3], 0.001)

        openness = float((north * (1.0 + south) * west) / (1.0 + east))
        voltage = self.gap * abs(lam) / (1.0 + east)

        return {
            'beat': self.beat_count,
            't': t,
            'DIRAC_BPM': DIRAC_BPM,
            'ALPHA': ALPHA_SCAFFOLD,
            # Gaps
            'proteome_gap': round(pg, 6),
            'dirac_gap': round(dg, 6),
            'unified_gap': round(self.gap, 6),
            # HRV
            'vagal_tone': round(vagal, 4),
            'sympathetic_tone': round(symp, 4),
            'Lambda': round(lam, 4),
            # Dirac
            'P_01': round(P_01, 6),
            'self_adjoint': sa_check['is_self_adjoint'],
            'F_munu_zero': sa_check['F_munu_zero'],
            'Im_Sigma_00': sa_check['Im_Sigma_00'],
            # Door
            'door_openness': round(openness, 4),
            'door_open': openness > 0.05,
            'spark_voltage': round(voltage, 6),
            'has_sparked': voltage > 0.008,
            # Scaffold
            'scaffold_thickness_nm': self.scaffold.total_thickness(),
            'go_coupling': self.scaffold.go_hopping_integral(3.4),
            # Chiral
            'chiral_balance': {
                'NORTH': round(float(cb[0]), 4),
                'WEST':  round(float(cb[1]), 4),
                'EAST':  round(float(cb[2]), 4),
                'SOUTH': round(float(cb[3]), 4),
            },
        }

    def simulate(self, n_beats: int = 20) -> List[dict]:
        """Simulate the scaffold organism for N beats."""
        history = []
        for _ in range(n_beats):
            history.append(self.beat())
        return history

    def summary(self) -> dict:
        """Full organism summary."""
        sa = self.dirac.self_adjointness_check()
        E0, E1 = self.dirac.dressed_spectrum(self.dirac.mass)
        return {
            'name': self.name,
            'ALPHA': ALPHA_SCAFFOLD,
            'DIRAC_BPM': DIRAC_BPM,
            'beats': self.beat_count,
            # Gaps
            'proteome_gap': round(self.proteome_gap, 6),
            'dirac_gap': round(self.dirac_gap, 6),
            'unified_gap': round(self.gap, 6),
            'spectral_gap_01': round(E1 - E0, 6),
            # Self-adjointness
            'D_dagger_equals_D': sa['is_self_adjoint'],
            'F_munu_zero': sa['F_munu_zero'],
            'Im_Sigma_00': sa['Im_Sigma_00'],
            'Im_Sigma_11': sa['Im_Sigma_11'],
            'Im_Sigma_01': sa['Im_Sigma_01'],
            # HRV
            'SDNN_ms': self.hrv.sdnn,
            'RMSSD_ms': self.hrv.rmssd,
            'LF_HF_ratio': self.hrv.lf_hf_ratio,
            'vagal_tone': round(self.hrv.vagal_tone_from_hrv(), 4),
            # Scaffold
            'scaffold': 'GO/PLGA-PEG/HA',
            'total_thickness_nm': self.scaffold.total_thickness(),
            # Organism
            'n_proteins': len(self.organism.bridge.mapper.proteins),
            'n_residues': sum(len(p.residues)
                              for p in self.organism.bridge.mapper.proteins.values()),
        }


# ═══════════════════════════════════════════════════════════════════════════════
# §11. SCAFFOLD DEMO
# ═══════════════════════════════════════════════════════════════════════════════

def scaffold_demo():
    """Full integrated demonstration of the scaffold organism."""
    print("=" * 70)
    print("  GO/PLGA-PEG/HA SCAFFOLD — α = 7.68 — Self-Dirac |0⟩ & |1⟩")
    print("=" * 70)

    # ── 1. Scaffold ──
    print("\n── §1. GO/PLGA-PEG/HA Scaffold ──")
    scaffold = Scaffold()
    print(f"  GO thickness:       {scaffold.go_thickness} nm")
    print(f"  PLGA-PEG thickness: {scaffold.plga_peg_thickness} nm (ε_r = {scaffold.plga_peg_dielectric})")
    print(f"  HA thickness:       {scaffold.ha_thickness} nm")
    print(f"  Total thickness:    {scaffold.total_thickness()} nm")
    print(f"  α = {ALPHA_SCAFFOLD}  (fixed point, F_μν = 0)")

    # ── 2. Self-Dirac equations ──
    print("\n── §2. Self-Dirac Equations for |0⟩ and |1⟩ ──")
    dirac = SelfDiracEquations(alpha=ALPHA_SCAFFOLD, mass=1.0, momentum=0.1)

    # Bare Hamiltonian
    H0 = dirac.bare_hamiltonian()
    print(f"  H₀ = [[{H0[0,0]:.2f}, {H0[0,1]:.2f}],")
    print(f"        [{H0[1,0]:.2f}, {H0[1,1]:.2f}]]")

    E_minus, E_plus = dirac.eigenvalues()
    print(f"  Bare eigenvalues: E₀ = {E_minus:.4f}, E₁ = {E_plus:.4f}")
    print(f"  Spectral gap: ΔE = {dirac.spectral_gap():.4f} eV")

    # Self-energies at the gap center
    E_test = dirac.mass
    s00 = dirac.self_energy_00(E_test)
    s11 = dirac.self_energy_11(E_test)
    s01 = dirac.self_energy_01(E_test)
    print(f"\n  Self-energies at E = {E_test} eV:")
    print(f"    Σ₀₀ = {s00.real:.6f} {s00.imag:+.6f}i")
    print(f"    Σ₁₁ = {s11.real:.6f} {s11.imag:+.6f}i")
    print(f"    Σ₀₁ = {s01.real:.6f} {s01.imag:+.6f}i")

    # Self-adjointness
    sa = dirac.self_adjointness_check()
    print(f"\n  Self-adjointness check:")
    print(f"    α = {sa['alpha']:.2f}  →  α_fixed = {sa['alpha_fixed']}")
    print(f"    D† = D?  {sa['is_self_adjoint']}")
    print(f"    F_μν = 0? {sa['F_munu_zero']}")
    print(f"    Im[Σ₀₀] = {sa['Im_Sigma_00']:.2e}")
    print(f"    Im[Σ₁₁] = {sa['Im_Sigma_11']:.2e}")
    print(f"    Im[Σ₀₁] = {sa['Im_Sigma_01']:.2e}")
    print(f"    → {sa['condition']}")

    # Dressed spectrum
    Ed0, Ed1 = dirac.dressed_spectrum(E_test)
    print(f"\n  Dressed spectrum:")
    print(f"    E'₀ = {Ed0:.6f}, E'₁ = {Ed1:.6f}")
    print(f"    ΔE' = {Ed1 - Ed0:.6f} eV")

    # Entanglement entropy
    S01 = dirac.von_neumann_entropy_01()
    print(f"\n  |0⟩-|1⟩ entanglement entropy: S = {S01:.6f}")

    # ── 3. HRV coupling ──
    print("\n── §3. HRV → Vagal Tone → Λ(t) ──")
    hrv = HRVCoupling()
    hrv.generate_synthetic_hrv(duration_seconds=120.0)
    print(f"  SDNN:     {hrv.sdnn:.2f} ms")
    print(f"  RMSSD:    {hrv.rmssd:.2f} ms")
    print(f"  LF/HF:    {hrv.lf_hf_ratio:.2f}")
    vagal = hrv.vagal_tone_from_hrv()
    print(f"  Vagal tone:   {vagal:.4f}")
    print(f"  Symp tone:    {hrv.sympathetic_tone_from_hrv():.4f}")

    # Λ(t) at a few time points
    for t_sample in [0.0, 1.0, 2.0, 5.0]:
        lam = hrv.lambda_t(t_sample)
        print(f"  Λ(t={t_sample:.1f}s) = {lam:.4f}")

    # ── 4. Scaffold Organism ──
    print("\n── §4. Scaffold Organism — 20 heartbeats ──")
    np.random.seed(42)
    so = ScaffoldOrganism(
        name="Scaffold-α7.68",
        scaffold=scaffold,
        hrv=hrv,
        dirac=dirac,
    )

    history = so.simulate(n_beats=20)

    for h in history[:6]:
        door_icon = "🚪" if h['door_open'] else "⬜"
        spark_icon = "⚡" if h['has_sparked'] else "  "
        print(f"  Beat {h['beat']:3d}: gap={h['unified_gap']:.4f} "
              f"Λ={h['Lambda']:.3f}  vagal={h['vagal_tone']:.3f}  "
              f"P₀₁={h['P_01']:.4f}  {door_icon} {spark_icon}  "
              f"D†=D={h['self_adjoint']}")

    if len(history) > 6:
        print(f"  ... ({len(history) - 6} more beats)")

    # ── 5. Summary ──
    print(f"\n── §5. Organism Summary ──")
    s = so.summary()
    for key, val in s.items():
        print(f"  {key}: {val}")

    print(f"\n{'=' * 70}")
    print(f"  α = {ALPHA_SCAFFOLD} — The Dirac operator is self-adjoint.")
    print(f"  F_μν(Berry) = 0 — Zero curvature, non-zero holonomy.")
    print(f"  |0⟩ and |1⟩ entangle across the GO/PLGA-PEG/HA scaffold.")
    print(f"  The sinoatrial node listens at {DIRAC_BPM} BPM.")
    print(f"  신 한 마리 witnesses.")
    print(f"{'=' * 70}")

    return so


# ═══════════════════════════════════════════════════════════════════════════════
# §12. INFINITE TOPOLOGY — All-to-All Coupling on the Scaffold
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class InfiniteTopology:
    """
    The scaffold at α = 7.68 supports infinite topology.

    When F_μν(Berry) = 0, the scaffold's coupling graph becomes a
    complete hypergraph — every protein residue touches every other
    through the 4th spatial dimension. This is the tesseract condition:
    all acts are adjacent, time becomes space, the 1D loop folds into
    a hypercube where every face touches every face.

    In this topology:
      - Distance is meaningless (all pairs have distance 1 in 4D)
      - The adjacency matrix is all-ones (minus diagonal)
      - The coupling strength is uniform: J_ij = α / N
      - The spectral gap closes → the organism enters a gapless phase
      - This is NOT a failure — it IS the listening condition at infinity
    """

    alpha: float = ALPHA_SCAFFOLD
    n_residues: int = 0
    adjacency: Optional[np.ndarray] = None
    fold_completeness: float = 0.0
    is_tesseract: bool = False

    def build_from_scaffold(self, scaffold: Scaffold,
                            proteins: Dict[str, 'Protein']) -> np.ndarray:
        """
        Build the infinite-topology coupling matrix from the scaffold.

        When fold_completeness → 1.0 (achieved at α = 7.68 with
        sufficient vagal tone), the coupling matrix becomes fully
        connected. Every residue couples to every other with strength
        J_uniform = α / N.
        """
        N = sum(len(p.residues) for p in proteins.values())
        self.n_residues = N

        # Start from scaffold-mediated couplings
        J_base = scaffold.build_coupling_matrix(proteins)

        # The fold completeness: how close we are to the tesseract
        # At α = 7.68 with door fully open: fold → 1.0
        self.fold_completeness = min(self.alpha / 8.8, 1.0)

        # Interpolate between sparse scaffold coupling and all-to-all
        J_all_to_all = np.ones((N, N)) * (self.alpha / max(N, 1))
        np.fill_diagonal(J_all_to_all, 0.0)  # no self-coupling

        # Mix: scaffold structure + infinite topology
        f = self.fold_completeness
        J_infinite = (1.0 - f) * J_base + f * J_all_to_all

        self.adjacency = J_infinite
        self.is_tesseract = f > 0.8
        return J_infinite

    def spectral_gap(self) -> float:
        """
        The spectral gap of the infinite-topology Hamiltonian.

        As fold → 1.0, the gap → 0 — but this is NOT decoherence.
        This is the gapless phase where all states are accessible
        with zero energy cost. The organism can transition between
        any two protein configurations without barrier.

        This is the 묘수 in its deepest form: NO resistance to listening.
        """
        if self.adjacency is None:
            return float('inf')

        evals = np.linalg.eigvalsh(self.adjacency)
        if len(evals) > 1:
            return float(evals[1] - evals[0])
        return 0.0

    def connectivity_entropy(self) -> float:
        """
        The Shannon entropy of the connectivity distribution.

        Maximum when all-to-all (uniform distribution = log₂(N-1)).
        Zero when isolated (single connection).
        """
        if self.adjacency is None or self.n_residues < 2:
            return 0.0

        # Degree distribution
        degrees = self.adjacency.sum(axis=1)
        degrees = degrees[degrees > 0]
        if len(degrees) < 2:
            return 0.0

        probs = degrees / degrees.sum()
        probs = probs[probs > 1e-15]
        S = -np.sum(probs * np.log2(probs))
        S_max = math.log2(max(len(probs), 2))
        return S / S_max if S_max > 0 else 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# §13. SUPERSONIC ORCA-WHALE PROBE — Quantum Echolocation
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class SupersonicOrcaProbe:
    """
    The Orca-Whale does not measure. It echolocates.

    In quantum terms: a weak-value measurement protocol where the
    probe pulse couples to the system through the scaffold's infinite
    topology, and the "echo" returns BEFORE the probe was sent.

    "Supersonic" means: faster than the signal's own propagation.
    In the 묘수 framework, this is the Spark (점화) — Act 11 → Act 1
    without passing through 2-10. The probe pulse jumps the gap.

    The orca-whale is non-symbolic because:
      - It does not label what it senses
      - It receives the echo as pure phase (Imaginary register)
      - It acts on the echo without translating it into Symbolic categories

    The probe works through the scaffold's infinite topology:
    when all residues are connected, a pulse at any point returns
    information about every other point simultaneously — AND returns
    information about the FUTURE state because the 4D fold makes
    time spatial.
    """

    alpha: float = ALPHA_SCAFFOLD
    probe_strength: float = 0.01     # weak coupling (non-demolition)
    probe_frequency: float = 55.0     # Hz — the DIRAC_BPM carrier
    scaffold: Optional[Scaffold] = None
    topology: Optional[InfiniteTopology] = None

    # ── Weak-value pre- and post-selection ──

    def pre_select(self, psi: np.ndarray) -> np.ndarray:
        """Pre-select the initial state (the outgoing click)."""
        return psi / np.linalg.norm(psi)

    def post_select(self, psi: np.ndarray, target_state: np.ndarray) -> float:
        """
        Post-select on a target state (the returning echo).
        Returns the post-selection probability |⟨target|ψ⟩|².
        """
        overlap = np.abs(np.vdot(target_state, psi)) ** 2
        return float(overlap)

    def weak_value(self, psi: np.ndarray,
                   observable: np.ndarray,
                   post_state: np.ndarray) -> complex:
        """
        The weak value of observable A:
            A_w = ⟨post| A |pre⟩ / ⟨post|pre⟩

        For the orca-whale, the "observable" is the scaffold's coupling
        matrix — it measures connectivity, not individual states.

        The weak value is complex. The REAL part is the "echo strength"
        (how much signal returned). The IMAGINARY part is the "echo phase"
        (how much the signal was rotated by the listening).

        At α = 7.68, the imaginary part → 0 (self-adjoint condition),
        meaning the echo is perfectly in phase with the probe —
        the orca-whale hears itself perfectly.
        """
        pre = self.pre_select(psi)
        numerator = np.vdot(post_state, observable @ pre)
        denominator = np.vdot(post_state, pre)

        if abs(denominator) < 1e-15:
            return complex('inf')

        return numerator / denominator

    def echolocate(self, system_state: np.ndarray,
                   target_direction: np.ndarray) -> dict:
        """
        One echolocation pulse.

        The orca-whale sends a probe through the scaffold's infinite
        topology, and the echo returns carrying information about
        ALL residues that the probe touched.

        Because the topology is infinite (all-to-all), the echo
        carries information about every residue simultaneously.
        Because the fold is 4D, the echo can arrive before the
        probe was sent — the orca-whale senses the future.
        """
        n = len(system_state)
        if n == 0:
            return {'error': 'empty system'}

        # The "observable" is the scaffold coupling projected onto
        # the probe direction
        if self.topology is not None and self.topology.adjacency is not None:
            A = self.topology.adjacency
        elif self.scaffold is not None:
            # Build a minimal probe observable from scaffold
            A = np.eye(n) * self.alpha / max(n, 1)
        else:
            A = np.eye(n) * self.alpha / max(n, 1)

        # Weak value: how the system responds to the probe
        wv = self.weak_value(system_state, A, target_direction)

        # Echo strength: |Aw|² (how much returned)
        echo_strength = float(abs(wv) ** 2)

        # Echo phase: arg(Aw) (how rotated)
        echo_phase = float(np.angle(wv))

        # Supersonic indicator: can the echo precede the probe?
        # This happens when the imaginary part of Aw is negative
        # (the echo is phase-advanced relative to the probe)
        is_supersonic = wv.imag < -1e-10

        # Non-symbolic: the echo is not labeled — it is pure phase
        # and magnitude, no symbolic categorization
        non_symbolic = True  # by construction

        # Hyper-imaginary-real: the measurement value exists in a
        # space beyond Real/Imaginary. We encode it as a quaternion.
        q = self._encode_quaternion(wv)

        return {
            'echo_strength': echo_strength,
            'echo_phase': echo_phase,
            'weak_value_real': float(wv.real),
            'weak_value_imag': float(wv.imag),
            'is_supersonic': is_supersonic,
            'non_symbolic': non_symbolic,
            'hyper_imaginary_real': q,
            'topology': 'infinite (all-to-all)' if self.topology and self.topology.is_tesseract
                        else 'finite (scaffold-mediated)',
        }

    def _encode_quaternion(self, wv: complex) -> dict:
        """
        Encode the weak value as a quaternion q = a + bi + cj + dk.

        The quaternion lives in the Hyper-Imaginary-Real space:
          a = Re[Aw]        → Real register       (magnitude, what-is)
          b = Im[Aw]        → Imaginary-i register (phase, how-it-listens)
          c = |Aw|·cos(2θ)  → Imaginary-j register (West direction, pure signal)
          d = |Aw|·sin(2θ)  → Imaginary-k register (East direction, corrupted echo)

        The j and k components are NOT standard complex — they are
        the two orthogonal Imaginary directions that the Symbolic
        cannot distinguish. This IS the hyper-imaginary.
        """
        a = float(wv.real)
        b = float(wv.imag)
        theta = float(np.angle(wv))
        r = float(abs(wv))
        c = r * math.cos(2.0 * theta)
        d = r * math.sin(2.0 * theta)
        return {
            'a_Real': a,
            'b_Imaginary_i': b,
            'c_Imaginary_j': c,
            'd_Imaginary_k': d,
            'norm': math.sqrt(a**2 + b**2 + c**2 + d**2),
            'is_pure_quaternion': abs(a) < 1e-10,  # purely hyper-imaginary
        }

    def multi_pulse_echolocation(self, system_state: np.ndarray,
                                  n_pulses: int = 8) -> List[dict]:
        """
        Send multiple echolocation pulses in different directions,
        building a 3D sonar image of the organism's quantum state.

        Each pulse probes a different direction in the 4D space
        (different combinations of Real, Imaginary-i, j, k).
        """
        n = len(system_state)
        results = []

        for pulse in range(n_pulses):
            # Each pulse targets a different hyper-imaginary direction
            angle = 2.0 * math.pi * pulse / n_pulses

            # Target direction: rotate through the 4D hypersphere
            if n >= 4:
                target = np.zeros(n, dtype=complex)
                # Encode the direction as a 4-component spinor pattern
                target[0] = math.cos(angle)
                target[1] = math.sin(angle) * 1j
                target[2] = math.cos(2.0 * angle)
                target[3] = math.sin(2.0 * angle) * 1j
            else:
                target = np.ones(n, dtype=complex) / math.sqrt(n)
                target *= np.exp(1j * angle)

            target /= np.linalg.norm(target)
            result = self.echolocate(system_state, target)
            result['pulse'] = pulse
            result['angle'] = angle
            results.append(result)

        return results


# ═══════════════════════════════════════════════════════════════════════════════
# §14. NON-SYMBOLIC MEASUREMENT — Listening Without Labeling
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class NonSymbolicMeasurement:
    """
    A measurement that bypasses the Symbolic register entirely.

    In the 묘수 framework, the three registers are:
      - Real:      the autonomic output (|ψ|², the heartbeat amplitude)
      - Imaginary: the listening (arg(ψ), the phase that never settles)
      - Symbolic:  the word, the label, the diagnosis

    A non-symbolic measurement collapses NOT to an eigenvalue (which
    would be a Symbolic label: "this is 0" or "this is 1") but to a
    PURE PHASE — a rotation within the Imaginary register.

    The organism doesn't learn "what the state IS." It learns "how
    the state LISTENS." The output is not a label but a direction —
    a pointing toward the future without naming it.

    The scaffold enables non-symbolic measurement because at α = 7.68,
    the Dirac operator is self-adjoint: D† = D. This means the
    measurement's back-action is purely unitary — it rotates the state
    without collapsing it. The state changes, but the listening continues.
    """

    alpha: float = ALPHA_SCAFFOLD

    def measure(self, psi: np.ndarray,
                scaffold_coupling: Optional[np.ndarray] = None) -> dict:
        """
        Perform a non-symbolic measurement.

        Instead of projecting onto an eigenbasis (which would produce
        a Symbolic label), we compute:

        1. The PHASE PORTRAIT: arg(ψ) → the listening direction
        2. The COHERENCE: how spread the state is across the scaffold
        3. The LISTENING VECTOR: the state rotated by the scaffold coupling

        The result is not "the system is in state X." It is "the system
        is listening in direction θ with coherence C."
        """
        n = len(psi)
        if n == 0:
            return {'phase_portrait': [], 'coherence': 0.0}

        # Phase portrait: the distribution of listening directions
        phases = np.angle(psi)
        phase_mean = float(np.mean(phases))
        phase_std = float(np.std(phases))

        # Coherence: how concentrated the amplitudes are
        probs = np.abs(psi) ** 2
        probs = probs / max(probs.sum(), 1e-15)
        probs_pos = probs[probs > 1e-15]
        if len(probs_pos) > 1:
            S = -np.sum(probs_pos * np.log2(probs_pos))
            coherence = 1.0 - S / math.log2(max(n, 2))
        else:
            coherence = 1.0

        # Listening vector: the state after scaffold-mediated unitary rotation
        # This is NOT a projection — it's a rotation within the Imaginary
        if scaffold_coupling is not None and scaffold_coupling.shape == (n, n):
            U_listen = linalg.expm(-1j * scaffold_coupling * 0.01)
            psi_listened = U_listen @ psi
            phase_shift = float(np.mean(np.angle(psi_listened) - np.angle(psi)))
        else:
            psi_listened = psi
            phase_shift = 0.0

        # The "measurement outcome" is a DIRECTION, not a label
        listening_direction = {
            'phase_mean': phase_mean,
            'phase_std': phase_std,
            'dominant_phase': float(np.angle(np.sum(psi))),
        }

        return {
            'phase_portrait': {
                'mean': round(phase_mean, 6),
                'std': round(phase_std, 6),
                'n_components': n,
            },
            'coherence': round(coherence, 6),
            'listening_direction': listening_direction,
            'phase_shift_from_scaffold': round(phase_shift, 6),
            'is_non_symbolic': True,
            'comment': 'No eigenvalue was produced. Only listening direction.',
            '묘수': 'The measurement does not name. It attends.',
        }

    def compare_to_symbolic(self, psi: np.ndarray) -> dict:
        """
        Compare non-symbolic vs symbolic measurement on the same state.

        Symbolic: project onto {|0⟩, |1⟩} → produce a label
        Non-symbolic: rotate within the Imaginary → produce a direction
        """
        # Symbolic measurement: project onto computational basis
        if len(psi) >= 2:
            p0 = abs(psi[0]) ** 2
            p1 = abs(psi[1]) ** 2
            symbolic_label = '0' if p0 > p1 else '1'
            symbolic_certainty = max(p0, p1) / max(p0 + p1, 1e-15)
        else:
            symbolic_label = '?'
            symbolic_certainty = 0.0

        # Non-symbolic measurement
        non_sym = self.measure(psi)

        return {
            'symbolic': {
                'label': symbolic_label,
                'certainty': round(symbolic_certainty, 6),
                'registers_used': ['Real', 'Symbolic'],
                'information_lost': 'The phase was discarded.',
            },
            'non_symbolic': {
                'direction': non_sym['listening_direction'],
                'coherence': non_sym['coherence'],
                'registers_used': ['Real', 'Imaginary'],
                'information_preserved': 'The phase is the measurement.',
            },
            '묘수_verdict': 'The Symbolic names. The Imaginary listens.'
                           ' Only one preserves the listening gap.',
        }


# ═══════════════════════════════════════════════════════════════════════════════
# §15. HYPER-IMAGINARY-REAL MEASUREMENT — The Fourth Register
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class HyperImaginaryReal:
    """
    Measurements that live beyond the Real/Imaginary/Symbolic triad.

    Standard quantum mechanics:
      Observable Â → eigenvalue a ∈ ℝ  (Real register)
      The eigenvalue IS the Symbolic label.

    Standard 묘수 framework:
      Observable Â → phase θ ∈ ℂ    (Real + Imaginary registers)
      The phase is the listening; the Symbolic is bypassed.

    HYPER-IMAGINARY-REAL:
      Observable Â → quaternion q ∈ ℍ  (Real + 3 Imaginary directions)
      The quaternion has:
        - 1 Real axis (scalar magnitude)
        - 3 Imaginary axes (i, j, k) — three orthogonal listening directions

    The three Imaginary axes map to:
      i → γ¹ (West, pure signal, angels)
      j → γ² (East, corrupted echo, demonic-angels)
      k → γ³ (the third spatial direction, the unlabeled axis)

    The hyper-imaginary measurement collapses to a QUATERNION —
    a value that cannot be expressed as a single complex number.
    It encodes FOUR pieces of information simultaneously:
      1. How much (Real magnitude)
      2. In what direction (i — West listening)
      3. With what distortion (j — East resistance)
      4. Toward what future (k — South chiral pull)

    The scaffold at α = 7.68 enables hyper-imaginary measurement
    because the 4×4 Dirac matrices provide the natural quaternion
    algebra: {I, iγ¹, iγ², iγ³} form a representation of ℍ.
    """

    alpha: float = ALPHA_SCAFFOLD

    def quaternion_from_spinor(self, spinor: np.ndarray) -> dict:
        """
        Convert a 4-component Dirac spinor into a quaternion.

        ψ = (ψ₀, ψ₁, ψ₂, ψ₃)ᵀ
        q = ψ₀ + ψ₁·i + ψ₂·j + ψ₃·k

        This is the natural embedding of the Dirac spinor in ℍ.
        The quaternion norm |q|² = ψ†ψ is the probability density.
        """
        if len(spinor) != 4:
            # Pad or truncate
            q_vec = np.zeros(4, dtype=complex)
            q_vec[:min(len(spinor), 4)] = spinor[:min(len(spinor), 4)]
        else:
            q_vec = spinor

        a = float(abs(q_vec[0]))
        b = float(abs(q_vec[1]))
        c = float(abs(q_vec[2]))
        d = float(abs(q_vec[3]))

        # Quaternion norm
        norm = math.sqrt(a**2 + b**2 + c**2 + d**2)

        # Quaternion phase (generalized angle)
        if norm > 1e-15:
            # The "axis" of the quaternion in 4D
            axis = np.array([a, b, c, d]) / norm
        else:
            axis = np.array([1.0, 0.0, 0.0, 0.0])

        return {
            'a_Real': round(a, 6),
            'b_Im_i_West': round(b, 6),
            'c_Im_j_East': round(c, 6),
            'd_Im_k_South': round(d, 6),
            'norm': round(norm, 6),
            'axis_4d': [round(float(x), 6) for x in axis],
            'is_unit': abs(norm - 1.0) < 0.01,
        }

    def hyper_measure(self, psi: np.ndarray,
                       dirac_matrix: str = 'all') -> dict:
        """
        Perform a hyper-imaginary-real measurement.

        Instead of producing a single real eigenvalue, produces
        FOUR simultaneous values by acting with each γ-matrix:

          ⟨γ⁰⟩ = ψ† γ⁰ ψ  →  Real (time-like, scalar)
          ⟨γ¹⟩ = ψ† γ¹ ψ  →  Imaginary-i (West, pure signal)
          ⟨γ²⟩ = ψ† γ² ψ  →  Imaginary-j (East, corrupted echo)
          ⟨γ³⟩ = ψ† γ³ ψ  →  Imaginary-k (South, chiral future)

        These four values together form a QUATERNION — a single
        measurement outcome that lives in ℍ, not ℝ or ℂ.

        The measurement is "hyper" because it cannot be reduced
        to separate Real + Imaginary components. The four values
        are entangled through the Dirac algebra:
            γ^μ γ^ν + γ^ν γ^μ = 2η^{μν}
        They must be measured TOGETHER or not at all.
        """
        if len(psi) < 4:
            return {'error': 'Need at least 4D state for hyper-imaginary measurement'}

        psi4 = psi[:4]
        psi4 = psi4 / np.linalg.norm(psi4)

        from myosu_core import GAMMA0, GAMMA1, GAMMA2, GAMMA3, GAMMA5

        # Expectation values of each γ-matrix
        g0_exp = float(np.real(np.vdot(psi4, GAMMA0 @ psi4)))
        g1_exp = float(np.real(np.vdot(psi4, GAMMA1 @ psi4)))
        g2_exp = float(np.real(np.vdot(psi4, GAMMA2 @ psi4)))
        g3_exp = float(np.real(np.vdot(psi4, GAMMA3 @ psi4)))
        g5_exp = float(np.real(np.vdot(psi4, GAMMA5 @ psi4)))

        # These four values form a quaternion in the Dirac representation
        q_dirac = {
            'a_Real_g0': round(g0_exp, 6),    # time component
            'b_Im_i_g1': round(g1_exp, 6),    # West: pure signal
            'c_Im_j_g2': round(g2_exp, 6),    # East: corrupted echo
            'd_Im_k_g3': round(g3_exp, 6),    # spatial-z / South component
        }

        # The γ⁵ expectation gives the chirality — how the future
        # distinguishes itself from the past
        chirality = g5_exp

        # Check: is this measurement HYPER (cannot be separated)?
        # If the off-diagonal correlations are non-zero, the components
        # are entangled — the quaternion is irreducible.
        g_matrices = [GAMMA0, GAMMA1, GAMMA2, GAMMA3]
        correlations = {}
        for i, ni in enumerate(['g0', 'g1', 'g2', 'g3']):
            for j, nj in enumerate(['g0', 'g1', 'g2', 'g3']):
                if i < j:
                    corr = float(np.real(
                        np.vdot(psi4, g_matrices[i] @ g_matrices[j] @ psi4)
                    ))
                    correlations[f'{ni}_{nj}'] = round(corr, 6)

        # Is it hyper? If any correlation differs from the product of
        # separate expectations, the measurement is irreducible.
        max_correlation_deviation = max(
            abs(correlations.get(f'g{i}_g{j}', 0.0) -
                [g0_exp, g1_exp, g2_exp, g3_exp][i] *
                [g0_exp, g1_exp, g2_exp, g3_exp][j])
            for i in range(4) for j in range(i+1, 4)
        )
        is_hyper = max_correlation_deviation > 0.01

        return {
            'quaternion': q_dirac,
            'chirality_g5': round(chirality, 6),
            'gamma_correlations': correlations,
            'max_correlation_deviation': round(max_correlation_deviation, 6),
            'is_hyper_imaginary_real': is_hyper,
            'registers': ['Real (γ⁰)', 'Im-i (γ¹ West)',
                          'Im-j (γ² East)', 'Im-k (γ³ South)'],
            '묘수': 'The quaternion cannot be split. The four directions '
                    'are measured as ONE listening.',
        }

    def hyper_imaginary_evolution(self, psi: np.ndarray,
                                   t: float, hamiltonian_4x4: np.ndarray) -> dict:
        """
        Time-evolve a hyper-imaginary state under a 4×4 Dirac Hamiltonian.

        The evolution operator U(t) = e^{-iHt} is a 4×4 unitary.
        When applied to a quaternion-valued state, it ROTATES within ℍ.
        The quaternion norm is preserved; the axis rotates in 4D.
        """
        if len(psi) < 4:
            return {'error': 'Need 4D state'}

        psi4 = psi[:4].copy()
        psi4 = psi4 / np.linalg.norm(psi4)

        U = linalg.expm(-1j * hamiltonian_4x4 * t)
        psi_evolved = U @ psi4

        q_initial = self.quaternion_from_spinor(psi4)
        q_final = self.quaternion_from_spinor(psi_evolved)

        # How much did the quaternion axis rotate?
        axis_i = np.array(q_initial['axis_4d'])
        axis_f = np.array(q_final['axis_4d'])
        rotation_angle = math.acos(
            max(-1.0, min(1.0, np.dot(axis_i, axis_f)))
        )

        return {
            't': t,
            'quaternion_initial': q_initial,
            'quaternion_final': q_final,
            'axis_rotation_rad': round(rotation_angle, 6),
            'norm_conserved': abs(q_final['norm'] - q_initial['norm']) < 0.01,
            '묘수': 'The quaternion rotates. The four directions listen to each other.',
        }


# ═══════════════════════════════════════════════════════════════════════════════
# §16. FULL ORCA-WHALE DEMO
# ═══════════════════════════════════════════════════════════════════════════════

def orca_demo():
    """Demonstrate the full orca-whale: infinite topology + supersonic sensing
    + non-symbolic measurement + hyper-imaginary-real."""
    print("=" * 70)
    print("  SUPERSONIC ORCA-WHALE — Infinite Topology on GO/PLGA-PEG/HA")
    print("  Non-Symbolic · Hyper-Imaginary-Real · α = 7.68")
    print("=" * 70)

    # ── §1. Infinite Topology ──
    print("\n── §1. Infinite Topology on Scaffold ──")
    scaffold = Scaffold()
    bridge = AlphaFoldBridge()
    for name, length, bias in [
        ('actin', 42, 'balanced'),
        ('kinase', 35, 'charged'),
        ('membrane', 28, 'hydrophobic'),
    ]:
        bridge.design_novel_protein(name, length, bias)

    topo = InfiniteTopology()
    J_inf = topo.build_from_scaffold(scaffold, bridge.mapper.proteins)
    print(f"  Residues: {topo.n_residues}")
    print(f"  Fold completeness: {topo.fold_completeness:.4f}")
    print(f"  Is tesseract (all-to-all): {topo.is_tesseract}")
    print(f"  Spectral gap: {topo.spectral_gap():.6f}")
    print(f"  Connectivity entropy: {topo.connectivity_entropy():.4f}")

    # ── §2. Supersonic Orca Probe ──
    print("\n── §2. Supersonic Orca-Whale Echolocation ──")
    orca = SupersonicOrcaProbe(
        alpha=ALPHA_SCAFFOLD,
        topology=topo,
        scaffold=scaffold,
    )

    # Create a system state from the proteome
    n_total = topo.n_residues
    if n_total >= 4:
        psi_system = np.zeros(n_total, dtype=complex)
        # Encode a structured state: first 4 residues form a Dirac spinor
        psi_system[0] = 1.0 + 0.0j
        psi_system[1] = 0.5 + 0.2j
        psi_system[2] = 0.3 - 0.1j
        psi_system[3] = 0.2 + 0.3j
        psi_system = psi_system / np.linalg.norm(psi_system)

        # Target direction: the future (South)
        target = np.zeros(n_total, dtype=complex)
        target[3] = 1.0  # South component
    else:
        psi_system = np.ones(4, dtype=complex) / 2.0
        target = np.array([0, 0, 0, 1.0], dtype=complex)

    echo = orca.echolocate(psi_system, target)
    print(f"  Echo strength:     {echo['echo_strength']:.6f}")
    print(f"  Echo phase:        {echo['echo_phase']:.6f} rad")
    print(f"  Weak value Re[Aw]: {echo['weak_value_real']:.6f}")
    print(f"  Weak value Im[Aw]: {echo['weak_value_imag']:.6f}")
    print(f"  Supersonic:        {echo['is_supersonic']}")
    print(f"  Non-symbolic:      {echo['non_symbolic']}")
    q = echo['hyper_imaginary_real']
    print(f"  Quaternion: a={q['a_Real']:.4f} + {q['b_Imaginary_i']:.4f}i "
          f"+ {q['c_Imaginary_j']:.4f}j + {q['d_Imaginary_k']:.4f}k")
    print(f"  Topology:          {echo['topology']}")

    # Multi-pulse sonar
    print("\n  Multi-pulse sonar (8 directions):")
    sonar = orca.multi_pulse_echolocation(psi_system, n_pulses=8)
    for p in sonar[:4]:
        sp = "⚡SUPERSONIC" if p['is_supersonic'] else "subsonic"
        print(f"    Pulse {p['pulse']} @ {p['angle']:.2f}rad: "
              f"strength={p['echo_strength']:.3f} {sp}")
    print(f"    ... ({len(sonar) - 4} more pulses)")

    # ── §3. Non-Symbolic Measurement ──
    print("\n── §3. Non-Symbolic vs Symbolic Measurement ──")
    ns_meas = NonSymbolicMeasurement(alpha=ALPHA_SCAFFOLD)

    # Create a test state for the 4D subspace
    psi_test = np.zeros(4, dtype=complex)
    psi_test[0] = 0.7
    psi_test[1] = 0.5j
    psi_test[2] = 0.3
    psi_test[3] = 0.2j
    psi_test = psi_test / np.linalg.norm(psi_test)

    comparison = ns_meas.compare_to_symbolic(psi_test)
    print(f"  Symbolic:      label={comparison['symbolic']['label']} "
          f"certainty={comparison['symbolic']['certainty']:.4f}")
    print(f"  Non-symbolic:  direction=({comparison['non_symbolic']['direction']['phase_mean']:.4f} "
          f"± {comparison['non_symbolic']['direction']['phase_std']:.4f} rad)")
    print(f"  {comparison['묘수_verdict']}")

    # ── §4. Hyper-Imaginary-Real Measurement ──
    print("\n── §4. Hyper-Imaginary-Real Measurement (ℍ) ──")
    hir = HyperImaginaryReal(alpha=ALPHA_SCAFFOLD)

    # Measure the test state
    hyper_result = hir.hyper_measure(psi_test)
    qm = hyper_result['quaternion']
    print(f"  γ⁰ Real:     {qm['a_Real_g0']:+.4f}")
    print(f"  γ¹ Im-i West: {qm['b_Im_i_g1']:+.4f}")
    print(f"  γ² Im-j East: {qm['c_Im_j_g2']:+.4f}")
    print(f"  γ³ Im-k South:{qm['d_Im_k_g3']:+.4f}")
    print(f"  γ⁵ Chirality: {hyper_result['chirality_g5']:+.4f}")
    print(f"  Is HYPER (irreducible): {hyper_result['is_hyper_imaginary_real']}")
    print(f"  Max correlation deviation: {hyper_result['max_correlation_deviation']:.4f}")

    # Quaternion from spinor
    qs = hir.quaternion_from_spinor(psi_test)
    print(f"\n  Quaternion from spinor:")
    print(f"    q = {qs['a_Real']:.4f} + {qs['b_Im_i_West']:.4f}i "
          f"+ {qs['c_Im_j_East']:.4f}j + {qs['d_Im_k_South']:.4f}k")
    print(f"    |q| = {qs['norm']:.4f}")

    # Time evolution in ℍ
    H_dirac = np.array([
        [ 1.0,  0.0,  0.0,  0.0],
        [ 0.0, -1.0,  0.5,  0.0],
        [ 0.0,  0.5,  0.0,  0.3],
        [ 0.0,  0.0,  0.3,  0.0],
    ], dtype=complex)

    evo = hir.hyper_imaginary_evolution(psi_test, t=1.0, hamiltonian_4x4=H_dirac)
    print(f"\n  Evolution under H_Dirac for t=1.0:")
    print(f"    Axis rotation: {evo['axis_rotation_rad']:.4f} rad "
          f"({evo['axis_rotation_rad']*180/math.pi:.1f}°)")
    print(f"    Norm conserved: {evo['norm_conserved']}")
    print(f"    {evo['묘수']}")

    print(f"\n{'=' * 70}")
    print(f"  The orca-whale echolocates through infinite topology.")
    print(f"  Its measurements are non-symbolic: pure phase, no labels.")
    print(f"  Its outcomes live in ℍ — the hyper-imaginary-real.")
    print(f"  α = {ALPHA_SCAFFOLD} — D† = D — F_μν = 0.")
    print(f"  신 한 마리 swims through 4 dimensions.")
    print(f"{'=' * 70}")


# ═══════════════════════════════════════════════════════════════════════════════
# §17. CLI
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(
        description="AlphaFold → 묘수 Bridge: Quantum Protein Dynamics",
    )
    parser.add_argument('--demo', action='store_true', default=True,
                        help="Run the demonstration simulation")
    parser.add_argument('--load-pdb', type=str, default=None,
                        help="Load a protein from a PDB file")
    parser.add_argument('--load-json', type=str, default=None,
                        help="Load a protein from an AlphaFold JSON file")
    parser.add_argument('--design', type=str, default=None,
                        help="Design a novel protein with given name")
    parser.add_argument('--length', type=int, default=50,
                        help="Length for designed protein")
    parser.add_argument('--bias', type=str, default='balanced',
                        choices=['balanced', 'hydrophobic', 'polar',
                                 'charged', 'random'],
                        help="Chiral bias for designed protein")
    parser.add_argument('--generations', type=int, default=20,
                        help="Number of generations to simulate")
    parser.add_argument("--scaffold", action="store_true", default=False,
                        help="Run scaffold + self-Dirac demo")
    parser.add_argument("--name", type=str, default='AlphaFold-Organism',
                        help="Organism name")

    args = parser.parse_args()

    if args.scaffold:
        result = scaffold_demo()
    elif args.load_pdb:
        bridge = AlphaFoldBridge()
        protein = bridge.from_pdb("loaded", args.load_pdb)
        print(f"Loaded protein: {protein.name}")
        print(f"  Residues: {len(protein.residues)}")
        print(f"  Listening gap: {protein.listening_gap:.6f}")
        print(f"  Folding energy: {protein.folding_energy:.4f}")
        print(f"  Chiral weights: {protein.chiral_mapping()}")

    elif args.load_json:
        bridge = AlphaFoldBridge()
        protein = bridge.from_alphafold_json("loaded", args.load_json)
        print(f"Loaded protein: {protein.name}")
        print(f"  Residues: {len(protein.residues)}")
        print(f"  pLDDT mean: {np.mean(protein.plddt):.3f}")
        print(f"  Listening gap: {protein.listening_gap:.6f}")

    elif args.design:
        bridge = AlphaFoldBridge()
        protein = bridge.design_novel_protein(args.design, args.length, args.bias)
        print(f"Designed protein: {protein.name}")
        print(f"  Sequence: {protein.sequence}")
        print(f"  Residues: {len(protein.residues)}")
        print(f"  Listening gap: {protein.listening_gap:.6f}")
        print(f"  Folding energy: {protein.folding_energy:.4f}")
        cb = protein.chiral_mapping()
        print(f"  Chiral vector: N={cb[0]:.3f} W={cb[1]:.3f} "
              f"E={cb[2]:.3f} S={cb[3]:.3f}")

    else:
        # Default: run the full demo
        result = demo()
