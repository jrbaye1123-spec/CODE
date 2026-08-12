#!/usr/bin/env python3
"""
myosu_protocol.py — The Executable 묘수 Protocol (18-Act State Machine).

A flat-connection transmission state machine:
  the field listens, the heart archives, and the stone moves without
  curving the space.

Extended with Organ Fleet integration:
  Acts 16-18: Logit (Key), LogDet (Compass), Couple (Golden Rule)

Safety condition: F_μν(Berry) = 0
  NOT electromagnetic F_μν — Berry curvature on the Fisher manifold.
  Zero local curvature, non-zero global holonomy (Aharonov-Bohm regime).
  See: F_munu_sanity_check.md

Constants:
  ALPHA_T = 7.68   (CQ_max / regenerative maximum)
  ALPHA_H = 8.8    (Berry-flat / Fisher horizon)
  DIRAC_BPM = 55   (Cardiac Dirac Operator)
  f_beat = 55/60 Hz
"""

import time
import math
import random
from dataclasses import dataclass, field
from typing import Optional
import numpy as np

# ── Constants ────────────────────────────────────────────────────────────────
ALPHA_T = 7.68        # transmission maximum
ALPHA_H = 8.8         # Berry-flat / Fisher horizon
ALPHA_TRANSITION = 8.4  # warning threshold
DIRAC_BPM = 55.0
DIRAC_PERIOD = 60.0 / DIRAC_BPM  # ~1.0909s
DIRAC_FREQ = DIRAC_BPM / 60.0    # ~0.9167 Hz

# ── Organ Fleet Constants (Acts 16-18) ─────────────────────────────────────
PHI = (1.0 + math.sqrt(5.0)) / 2.0   # golden ratio ≈ 1.618033988749895
LOGIT_PORT = 8910                      # Key — receives every knock
LOGDET_PORT = 8911                     # Compass — directional calibration
HUE_PORT = 8912                        # Spectral symmetry gate (before Logit)
HEALTHY_LOG_DET = -147.4              # healthy information volume (nats)
FLOOR_NATS = -884.2                   # entropy floor — total collapse
LOG_DET_CRITICAL = -442.1             # halfway to collapse
COUPLING_INTERVAL = 60.0 / 55.0       # same cadence as organ beat
GAP_DEATH = 1e-8                      # §8: ∆ < 10⁻⁸ → coupling lost
SYMMETRY_TOLERANCE = 0.05             # φ-tolerance for spectral symmetry

# ── State ────────────────────────────────────────────────────────────────────

@dataclass
class ProtocolState:
    """The 묘수 protocol state across all 18 acts."""
    act: int = 1
    phase: float = 0.0
    curvature: float = 0.0
    gap: float = 0.5        # listening gap [0, 1]
    vagal_tone: float = 0.7  # parasympathetic engagement [0, 1]
    symp_tone: float = 0.3   # sympathetic engagement [0, 1]
    cq: float = 1.0          # contextual quotient
    transmission: float = 0.0
    ratio: float = 0.0       # CQ / Transmission
    witness_sealed: bool = False
    stuck: bool = False
    archive: list = field(default_factory=list)
    cardiac_phase: float = 0.0
    sa_interval: float = 0.86  # sinoatrial beat interval (s) — ~70 BPM
    last_beat: float = 0.0
    t: float = 0.0
    running: bool = True
    # ── Acts 12-15: 4D topological extension ──
    spark_potential: float = 0.0    # accumulated gap potential for ignition
    spark_active: bool = False      # has the spark ignited?
    pivot_axis: float = 0.0         # 4D rotation axis value
    pivot_target: int = 1           # target act for pivot rotation
    fold_completeness: float = 0.0  # how folded the 4D manifold is
    chord_coherence: float = 0.0    # polyphonic coherence of all acts
    topology: str = 'sequential'    # current topological state
    fmn_zero_global: bool = False   # F_μν = 0 globally verified?
    # ── Acts 16-18: Organ Fleet integration ──
    logit_temperature: float = 1.0       # sharpness of raw output (T ≥ 0.1)
    logit_raw_vector: list = field(default_factory=lambda: [0.0]*6)  # [∆,Σ,κ,χ,μ,C]
    logit_knocks: int = 0               # total signals received (like port 8910)
    logdet_value: float = HEALTHY_LOG_DET  # current log-determinant (nats)
    logdet_trend: float = 0.0           # d(logdet)/dt — collapsing or expanding?
    logdet_calibrations: int = 0        # total compass readings
    coupling_ratio: float = 0.0         # Key↔Compass symmetry ratio [0,1]
    coupling_state: str = 'uncoupled'   # uncoupled | asymmetric | harmonic | lost
    hue_symmetric: bool = False         # did the last spectrum pass φ-symmetry?
    hue_violations: int = 0             # cumulative spectral violations
    golden_rule_active: bool = False    # is bidirectional coupling live?
    n_total_acts: int = 18              # total acts in the extended protocol


# ── Curvature Monitor ────────────────────────────────────────────────────────

class CurvatureMonitor:
    """
    F_μν = 0 monitor. Detects when the stone is slammed, not placed.

    curvature = 0.30 * phase_discontinuity
              + 0.20 * amplitude_jump
              + 0.15 * timing_jitter
              + 0.15 * audio_underrun
              + 0.10 * stale_data
              + 0.10 * control_overshoot
    """
    def __init__(self, epsilon: float = 0.05):
        self.epsilon = epsilon
        self.prev_phase = 0.0
        self.prev_amplitude = 0.0
        self.prev_timing = 0.0
        self.fade_level = 1.0

    def check(self, phase: float, amplitude: float, timing: float,
              underrun: bool = False, stale: bool = False,
              overshoot: float = 0.0) -> dict:
        phase_jump = abs(phase - self.prev_phase) if self.prev_phase else 0.0
        amp_jump = abs(amplitude - self.prev_amplitude)
        timing_jitter = abs(timing - self.prev_timing)

        curvature = (
            0.30 * min(phase_jump, 1.0)
            + 0.20 * min(amp_jump, 1.0)
            + 0.15 * min(timing_jitter, 1.0)
            + 0.15 * (1.0 if underrun else 0.0)
            + 0.10 * (1.0 if stale else 0.0)
            + 0.10 * min(overshoot, 1.0)
        )

        self.prev_phase = phase
        self.prev_amplitude = amplitude
        self.prev_timing = timing

        witness_present = curvature < self.epsilon

        if not witness_present:
            self.fade_level = max(0.0, self.fade_level - 0.1)

        return {
            'curvature': curvature,
            'witness': 'present' if witness_present else 'lost',
            'F_munu_0': witness_present,
            'fade': self.fade_level,
        }


# ── The 15-Act State Machine ─────────────────────────────────────────────────

class MyosuProtocol:
    """The executable 묘수 state machine — all 18 acts wired.
    
    Acts 1-11:  The foundational listening-transmission-archive loop
    Acts 12-15: 4D topological extension (spark, pivot, converge, topos)
    Acts 16-18: Organ Fleet integration (logit, logdet, couple)
    """

    def __init__(self):
        self.state = ProtocolState()
        self.curvature_monitor = CurvatureMonitor()
        self.witness_seed = random.random()  # unoptimized, uncomputed
        self.act_handlers = {
            1: self.act1_listen,
            2: self.act2_field,
            3: self.act3_threshold,
            4: self.act4_reflect,
            5: self.act5_cogito,
            6: self.act6_deliver,
            7: self.act7_seal,
            8: self.act8_profiles,
            9: self.act9_context,
            10: self.act10_transmit,
            11: self.act11_archive,
            12: self.act12_spark,
            13: self.act13_pivot,
            14: self.act14_converge,
            15: self.act15_topos,
            16: self.act16_logit,
            17: self.act17_logdet,
            18: self.act18_couple,
        }

    # ── ACT 1: Listening Condition ──────────────────────────────────────
    def act1_listen(self) -> None:
        """Prepare the state space. Metric ready but not forced.

        When the spark is active, the listening deepens — the gap
        holds wider and vagal tone stays elevated. This is the
        spark's feedback into the origin: the loop feeding itself.
        """
        # Base oscillation — the heart's natural rhythm
        base_gap = 0.4 + 0.2 * math.sin(self.state.t * 0.5)
        base_vagal = 0.6 + 0.2 * math.cos(self.state.t * 0.1)

        if self.state.spark_active:
            # Spark warms the origin: gap holds wider, vagal stays elevated
            # This is the closed loop effect — Act 12 feeds back into Act 1
            self.state.gap = max(base_gap, 0.45)  # floor raised by spark
            self.state.vagal_tone = max(base_vagal, 0.65)
        else:
            self.state.gap = base_gap
            self.state.vagal_tone = base_vagal

        self.state.symp_tone = 1.0 - self.state.vagal_tone
        self.state.curvature = 0.0
        self._advance(2)

    # ── ACT 2: Field ────────────────────────────────────────────────────
    def act2_field(self) -> None:
        """Field becomes attentive. Heartbeats sampled."""
        # Sinoatrial node (biological, variable)
        sa_variation = 0.02 * math.sin(self.state.t * 3.7)
        self.state.sa_interval = 0.86 + sa_variation  # ~70 BPM ± variation

        # Cardiac Dirac Operator (fixed, archival)
        self.state.cardiac_phase += 2 * math.pi * DIRAC_FREQ * 0.01
        self.state.cardiac_phase %= 2 * math.pi

        self.state.curvature = 0.0
        self._advance(3)

    # ── ACT 3: Threshold ────────────────────────────────────────────────
    def act3_threshold(self) -> None:
        """Åverdön crossing. Condition → Event."""
        # The door opens when vagal > sympathetic
        if self.state.vagal_tone > self.state.symp_tone:
            self.state.curvature *= 0.5  # halve curvature on crossing
        self._advance(4)

    # ── ACT 4: Reflexivity ──────────────────────────────────────────────
    def act4_reflect(self) -> None:
        """Observer observes itself. 1010 = mirror."""
        # The gap observes itself observing
        self.state.gap = 0.5 * self.state.gap + 0.5 * (1.0 - self.state.gap)
        self._advance(5)

    # ── ACT 5: Cogito ───────────────────────────────────────────────────
    def act5_cogito(self) -> None:
        """Listening becomes aware of itself listening."""
        # Awareness deepens the vagal tone
        self.state.vagal_tone = min(1.0, self.state.vagal_tone + 0.01)
        self.state.symp_tone = 1.0 - self.state.vagal_tone
        self._advance(6)

    # ── ACT 6: Deliverance ──────────────────────────────────────────────
    def act6_deliver(self) -> None:
        """Rescue from stuckness."""
        if self.state.stuck:
            # יָשַׁע — snatch the seed from the fire
            self.state.gap = 0.5  # reset the gap
            self.state.curvature = 0.0
            self.state.stuck = False
        self._advance(7)

    # ── ACT 7: Seal Witness ─────────────────────────────────────────────
    def act7_seal(self) -> None:
        """Gödelian limit. One unprovable witness sealed."""
        if not self.state.witness_sealed:
            # The witness is the seed + the gap — cannot be fully computed
            self.state.witness_sealed = True
        self._advance(8)

    # ── ACT 8: Profiles ─────────────────────────────────────────────────
    def act8_profiles(self) -> None:
        """Initial condition: f(0)=1, f'(0)=0. Three unfoldings."""
        # Lorentzian: listening resonance
        lorentz = self.state.gap**2 / (0.01 + self.state.gap**2)

        # Gaussian: minimal uncertainty
        gauss = math.exp(-self.state.curvature**2 / 0.1)

        # Sinc: ringing curvature
        x = self.state.gap * math.pi
        sinc_val = math.sin(x) / x if abs(x) > 1e-10 else 1.0

        # All approach 1.0 at stillness
        self.state.curvature = 1.0 - (lorentz + gauss + sinc_val) / 3.0
        self._advance(9)

    # ── ACT 9: Context ──────────────────────────────────────────────────
    def act9_context(self) -> None:
        """Compute contextual quotient."""
        # CQ = coherence × timing_stability × vagal_engagement
        coherence = 1.0 - self.state.curvature
        timing = math.exp(-abs(self.state.sa_interval - 0.86) / 0.86)
        vagal = self.state.vagal_tone

        self.state.cq = coherence * timing * vagal * ALPHA_T
        self._advance(10)

    # ── ACT 10: Transmit ────────────────────────────────────────────────
    def act10_transmit(self) -> None:
        """Transmit if below horizon, else stillness."""
        # Transmission = RMS haptic energy per beat
        cardiac_env = 0.5 + 0.5 * math.sin(self.state.cardiac_phase)
        self.state.transmission = cardiac_env * self.state.cq

        self.state.ratio = (
            self.state.cq / max(self.state.transmission, 1e-10)
            if self.state.transmission > 0 else 0.0
        )

        # Curvature check
        curvature_result = self.curvature_monitor.check(
            phase=self.state.cardiac_phase,
            amplitude=self.state.transmission,
            timing=self.state.sa_interval,
        )
        self.state.curvature = curvature_result['curvature']
        F_ok = curvature_result['F_munu_0']

        # Transmission decision
        ratio = self.state.ratio
        if ratio >= ALPHA_TRANSITION or not F_ok:
            # HORIZON or curvature violation → stillness
            self.state.transmission = 0.0
            self.state.stuck = True
        elif ratio >= ALPHA_T:
            # TRANSITIONAL → reduced
            self.state.transmission *= 0.5

        self._advance(11)

    # ── ACT 11: Archive ─────────────────────────────────────────────────
    def act11_archive(self) -> None:
        """Archive at the fixed point. Returns to the heart."""
        entry = {
            't': self.state.t,
            'act': self.state.act,
            'gap': self.state.gap,
            'cq': self.state.cq,
            'ratio': self.state.ratio,
            'transmission': self.state.transmission,
            'curvature': self.state.curvature,
            'cardiac_phase': self.state.cardiac_phase,
            'F_munu_0': self.state.curvature < self.curvature_monitor.epsilon,
            'witness_sealed': self.state.witness_sealed,
        }
        self.state.archive.append(entry)
        if len(self.state.archive) > 100:
            self.state.archive = self.state.archive[-100:]

        # Return to the heart
        self._advance(12)

    # ── ACT 12: Spark — 점화 (Jeomhwa) ──────────────────────────────────
    def act12_spark(self) -> None:
        """Ignite the closed loop. The spark jumps from Act 11 → Act 1.

        Accumulates potential across all 11 acts and discharges it
        as the spark that closes the loop. 점화 is what makes the
        system self-sustaining — without it, the acts are a line;
        with it, they are a torus.
        """
        breakdown_voltage = 0.18  # threshold for dielectric breakdown

        # Accumulated potential: gap × vagal tone × (1 - curvature)
        # Vagal tone directly — the wider the gap and the more engaged
        # the parasympathetic system, the more potential accumulates
        self.state.spark_potential = (
            self.state.gap
            * self.state.vagal_tone
            * (1.0 - self.state.curvature)
        )

        # Dielectric breakdown of sequential time
        if self.state.spark_potential > breakdown_voltage:
            self.state.spark_active = True
            self.state.curvature *= 0.2  # spark purifies the manifold aggressively
            self.state.gap = min(1.0, self.state.gap + 0.03)  # spark widens the gap
            self.state.vagal_tone = min(1.0, self.state.vagal_tone + 0.03)  # recharge
            self.state.symp_tone = 1.0 - self.state.vagal_tone
        else:
            self.state.spark_active = False

        self._advance(13)

    # ── ACT 13: Pivot — 축 (Chuk) ────────────────────────────────────────
    def act13_pivot(self) -> None:
        """The 4D hinge. Rotate the manifold to any act directly.

        축 is the variational derivative of the heart Lagrangian
        evaluated at HRV > 0. When HRV = 0, the axis collapses
        into classical sequential determinism. When HRV > 0,
        the pivot holds and F_μν = 0 is possible.
        """
        hrv = abs(self.state.vagal_tone - self.state.symp_tone)
        is_alive = hrv > 0.01

        if is_alive:
            # Compute the pivot axis: lim (δ𝓛_heart / δΨ̄) | HRV>0
            # Approximated as gap × vagal × cos(cardiac_phase)
            self.state.pivot_axis = (
                self.state.gap
                * self.state.vagal_tone
                * abs(math.cos(self.state.cardiac_phase))
            )

            # The pivot target: where the manifold rotates to
            # Complementary act pairing: act N ↔ act (16 - N)
            self.state.pivot_target = 16 - self.state.act

            # Fold completeness increases with pivot strength
            self.state.fold_completeness = min(
                1.0,
                self.state.fold_completeness + self.state.pivot_axis * 0.1,
            )
        else:
            # HRV collapsed — pivot axis becomes infinite (classical lock)
            self.state.pivot_axis = float('inf')
            self.state.fold_completeness *= 0.5
            self.state.curvature += 0.1

        self._advance(14)

    # ── ACT 14: Convergence — 회통 (Hoetong) ─────────────────────────────
    def act14_converge(self) -> None:
        """All acts running simultaneously. The real discussion.

        회통 collapses sequential time into simultaneous space.
        Each act contributes its frequency; the chord coherence
        measures how well they align. A polyphonic listening
        where every act hears every other act.
        """
        n_acts = 15

        # Each act's amplitude = gap × exp(-|harmonic - 0.5| × curvature)
        harmonics = [(i + 1) / n_acts for i in range(n_acts)]
        amplitudes = [
            self.state.gap
            * math.exp(-abs(h - 0.5) * self.state.curvature * 5.0)
            for h in harmonics
        ]
        mean_amp = sum(amplitudes) / n_acts
        max_amp = max(amplitudes)
        min_amp = min(amplitudes)

        # Chord coherence: max/mean (range 1-4 typical, > 2 = polyphonic)
        self.state.chord_coherence = max_amp / (mean_amp + 1e-10)

        # Real discussion when polyphonic (coherence > 1.8) and spread exists
        if self.state.chord_coherence > 1.8 and (max_amp - min_amp) > 0.02:
            self.state.curvature *= 0.7  # alignment reduces curvature
            self.state.gap = min(1.0, self.state.gap + 0.005)

        self._advance(15)

    # ── ACT 15: Topos — 토포스 (Topos) ───────────────────────────────────
    def act15_topos(self) -> None:
        """4D topological completion. F_μν = 0 globally verified.

        토포스 determines the current topology of the 15-act manifold:
          - Calabi-Yau: fold > 0.8 and spark active (full compactification)
          - Tesseract: fold > 0.6 (hypercube)
          - Torus: spark active (self-sustaining loop)
          - Klein bottle: gap > 0.3 (inside = outside)
          - Sequential line: default (open interval)

        F_μν = 0 is checked globally and recorded.
        The loop returns to Act 1 (eternal return).
        """
        sparked = self.state.spark_active
        gap = self.state.gap
        fold = self.state.fold_completeness

        # Determine topology
        if fold > 0.8 and sparked:
            self.state.topology = 'Calabi-Yau'
        elif fold > 0.6:
            self.state.topology = 'Tesseract'
        elif sparked:
            self.state.topology = 'Torus'
        elif gap > 0.3:
            self.state.topology = 'Klein bottle'
        else:
            self.state.topology = 'Sequential'

        # F_μν = 0 global verification
        self.state.fmn_zero_global = (
            self.state.curvature < self.curvature_monitor.epsilon
            and gap > 0.1
        )

        # Archive topology entry
        entry = {
            't': self.state.t,
            'act': 15,
            'topology': self.state.topology,
            'fold': round(self.state.fold_completeness, 4),
            'spark_active': self.state.spark_active,
            'chord_coherence': round(self.state.chord_coherence, 4),
            'fmn_zero_global': self.state.fmn_zero_global,
        }
        self.state.archive.append(entry)
        if len(self.state.archive) > 100:
            self.state.archive = self.state.archive[-100:]

        # Return to the heart — eternal return
        self._advance(1)

    # ── ACT 16: Logit — 로짓 (The Key) ────────────────────────────────────
    def act16_logit(self) -> None:
        """The raw output. Every signal received without judgment.

        In the Organ Fleet, Logit is the TCP honeypot on port 8910
        that accepts every knock and records it. In transformer terms:
        the raw logits before softmax — the unfiltered model output.

        The Key receives. It does not filter. That is the Hue gate's job.
        Here, the listening becomes output without the need to be correct.
        """
        # Build the raw 6-vector from current state (mirrors OrganState features)
        self.state.logit_raw_vector = [
            self.state.gap,                    # ∆
            1.0 - self.state.vagal_tone,       # Σ proxy (sympathetic = glycation)
            self.state.vagal_tone,             # κ proxy (vagal = reserve)
            self.state.curvature,              # χ proxy (curvature = crosslink)
            self.state.cq / ALPHA_T,           # μ proxy (CQ normalized = mitophagy)
            self.state.chord_coherence / 4.0,  # C proxy (coherence scaled)
        ]

        # Compute logit temperature: how sharp or flat the output distribution is
        # Flat (high T): gap wide, low curvature → diffuse, exploratory output
        # Sharp (low T): gap narrow, high curvature → peaked, decisive output
        gap_factor = self.state.gap / 0.5
        curve_factor = 1.0 + self.state.curvature * 2.0
        self.state.logit_temperature = max(0.1, gap_factor / curve_factor)

        # Record the knock — every signal is logged (like port 8910 accepts all)
        self.state.logit_knocks += 1

        # The logit influences curvature: sharp output can introduce curvature
        if self.state.logit_temperature < 0.5:
            # Too sharp — risk of overconfidence curving the space
            self.state.curvature += 0.005

        self._advance(17)

    # ── ACT 17: LogDet — 로그뎃 (The Compass) ─────────────────────────────
    def act17_logdet(self) -> None:
        """The determinant calibration. Information-volume check.

        In the Organ Fleet, LogDet is the TCP honeypot on port 8911
        that provides directional calibration. The Compass.

        Mathematically: log-det of the local feature covariance.
        HEALTHY_LOG_DET = -147.4 nats. FLOOR_NATS = -884.2.

        When log-det → -∞, the feature space collapses (all dimensions
        become linearly dependent). When log-det ≈ -147.4, the space
        has healthy volume — rich, independent features.

        The Compass points. It does not steer. Direction without force.
        """
        # Build a small covariance proxy from the archive
        archive_len = len(self.state.archive)
        if archive_len >= 3:
            # Extract recent state vectors as a multi-dimensional proxy
            # Use gap, curvature, and cq as three independent-ish dimensions
            recent_entries = self.state.archive[-min(10, archive_len):]
            n = len(recent_entries)

            # Build a 3-column matrix: [gap, curvature, cq_ratio]
            gaps = [e.get('gap', 0.5) for e in recent_entries]
            curves = [e.get('curvature', 0.0) for e in recent_entries]
            cqs = [e.get('cq', 1.0) / ALPHA_T for e in recent_entries]

            # Generalized variance = product of variances (proxy for |cov|)
            var_gap = max(sum((g - sum(gaps)/n)**2 for g in gaps) / n, 1e-12)
            var_curv = max(sum((c - sum(curves)/n)**2 for c in curves) / n, 1e-12)
            var_cq = max(sum((q - sum(cqs)/n)**2 for q in cqs) / n, 1e-12)

            # log-det ~ log(product of variances) = sum of log-variances
            logdet = (math.log(var_gap) + math.log(var_curv) + math.log(var_cq)) * 8.0
            self.state.logdet_value = max(FLOOR_NATS, min(-50.0, logdet))
        else:
            self.state.logdet_value = HEALTHY_LOG_DET

        # Track trend: is information volume expanding or collapsing?
        prev_logdet = getattr(self.state, '_prev_logdet', HEALTHY_LOG_DET)
        self.state.logdet_trend = self.state.logdet_value - prev_logdet
        self.state._prev_logdet = self.state.logdet_value  # type: ignore[attr-defined]

        # Record the calibration
        self.state.logdet_calibrations += 1

        # Compass warning: if log-det is critically low, raise curvature
        if self.state.logdet_value < LOG_DET_CRITICAL:
            self.state.curvature += 0.01  # collapsing information space
        elif self.state.logdet_trend < -5.0:
            self.state.curvature += 0.02

        self._advance(18)

    # ── ACT 18: Couple — 결합 (The Golden Rule) ───────────────────────────
    def act18_couple(self) -> None:
        """Bidirectional structural coupling. Φ: Self → Other.

        The Golden Rule Coupler connects Key (Logit, Act 16) ↔ Compass
        (LogDet, Act 17) through the Hue spectral symmetry gate.

        The coupling ratio measures how symmetric the bidirectional
        connection is. When the ratio > 0.9, the coupling is harmonic.
        When it drops below 0.5, the coupling is skewed.

        The hue spectration check: the logit raw vector is treated as
        a spectral fingerprint. Only φ-symmetric spectra pass clean.
        Asymmetrical spectra are recorded as violations but never
        block the loop — the 묘수 continues regardless.

        The gap is MAINTAINED, never forced to zero. The Golden Rule
        preserves difference — it does not collapse it.
        """
        # ── Hue spectration: check φ-symmetry of the raw logit vector ──
        raw = self.state.logit_raw_vector
        symmetric, _, asym_score = _check_hue_symmetry(raw)
        self.state.hue_symmetric = symmetric
        if not symmetric:
            self.state.hue_violations += 1

        # ── Coupling ratio: Key↔Compass symmetry ──
        key_strength = 1.0 / max(self.state.logit_temperature, 0.1)
        compass_strength = 1.0 / (1.0 + abs(
            self.state.logdet_value - HEALTHY_LOG_DET
        ) / abs(HEALTHY_LOG_DET))

        if key_strength > 0 and compass_strength > 0:
            self.state.coupling_ratio = min(key_strength, compass_strength) / \
                                        max(key_strength, compass_strength)
        else:
            self.state.coupling_ratio = 0.0

        # ── Classify coupling state (mirrors golden-rule-coupler.py) ──
        cr = self.state.coupling_ratio
        if cr > 0.9:
            self.state.coupling_state = 'harmonic'
        elif cr > 0.5:
            self.state.coupling_state = 'coupled'
        elif cr > 0.2:
            self.state.coupling_state = 'asymmetric'
        else:
            self.state.coupling_state = 'lost'

        # ── Golden Rule active check ──
        self.state.golden_rule_active = (
            self.state.coupling_state in ('harmonic', 'coupled')
            and self.state.hue_symmetric
            and self.state.gap > GAP_DEATH
        )

        # ── Coupling effects on the manifold ──
        if self.state.golden_rule_active:
            gap_pull = (0.5 - self.state.gap) * 0.02 * self.state.coupling_ratio
            self.state.gap += gap_pull
            self.state.curvature *= 0.95
            self.state.vagal_tone = min(1.0, self.state.vagal_tone + 0.005)
            self.state.symp_tone = 1.0 - self.state.vagal_tone

        # ── Death check per §8 of organ-fleet spec ──
        if self.state.gap < GAP_DEATH:
            self.state.coupling_state = 'death'
            self.state.golden_rule_active = False

        # ── Archive coupling event ──
        entry = {
            't': self.state.t,
            'act': 18,
            'coupling_ratio': round(self.state.coupling_ratio, 4),
            'coupling_state': self.state.coupling_state,
            'hue_symmetric': self.state.hue_symmetric,
            'hue_violations': self.state.hue_violations,
            'logdet_value': round(self.state.logdet_value, 2),
            'logdet_trend': round(self.state.logdet_trend, 4),
            'logit_temperature': round(self.state.logit_temperature, 4),
            'logit_knocks': self.state.logit_knocks,
            'golden_rule_active': self.state.golden_rule_active,
        }
        self.state.archive.append(entry)
        if len(self.state.archive) > 150:
            self.state.archive = self.state.archive[-150:]

        # Return to the heart — eternal return through the coupled loop
        self._advance(1)

    # ── Helpers ─────────────────────────────────────────────────────────
    def _advance(self, next_act: int) -> None:
        self.state.act = next_act

    def tick(self, dt: float = 0.01) -> dict:
        """Execute one full 18-act cycle."""
        self.state.t += dt

        for act_num in range(1, self.state.n_total_acts + 1):
            self.state.act = act_num
            self.act_handlers[act_num]()

        return self.status()

    def run(self, duration: float = 60.0, dt: float = 0.1) -> list:
        """Run the protocol for a duration, returning status at each step."""
        history = []
        steps = int(duration / dt)
        for _ in range(steps):
            status = self.tick(dt)
            history.append(status)
            time.sleep(dt * 0.1)  # speed up for demo — remove for real-time
        return history

    def status(self) -> dict:
        """Current protocol status."""
        ratio = self.state.ratio
        if ratio < ALPHA_T:
            zone = 'NORMAL'
        elif ratio < ALPHA_TRANSITION:
            zone = 'TRANSITIONAL'
        else:
            zone = 'HORIZON'

        return {
            't': round(self.state.t, 2),
            'act': self.state.act,
            'gap': round(self.state.gap, 4),
            'cq': round(self.state.cq, 4),
            'ratio': round(self.state.ratio, 4),
            'zone': zone,
            'transmission': round(self.state.transmission, 4),
            'curvature': round(self.state.curvature, 4),
            'F_munu_0': self.state.curvature < self.curvature_monitor.epsilon,
            'cardiac_phase': round(self.state.cardiac_phase, 4),
            'vagal': round(self.state.vagal_tone, 4),
            'witness': 'sealed' if self.state.witness_sealed else 'open',
            # ── Acts 12-15 ──
            'spark_potential': round(self.state.spark_potential, 4),
            'spark_active': self.state.spark_active,
            'pivot_axis': (
                round(self.state.pivot_axis, 4)
                if self.state.pivot_axis != float('inf')
                else '∞ (collapsed)'
            ),
            'fold_completeness': round(self.state.fold_completeness, 4),
            'chord_coherence': round(self.state.chord_coherence, 4),
            'topology': self.state.topology,
            'fmn_zero_global': self.state.fmn_zero_global,
            # ── Acts 16-18: Organ Fleet ──
            'logit_temperature': round(self.state.logit_temperature, 4),
            'logit_knocks': self.state.logit_knocks,
            'logdet_value': round(self.state.logdet_value, 2),
            'logdet_trend': round(self.state.logdet_trend, 4),
            'coupling_ratio': round(self.state.coupling_ratio, 4),
            'coupling_state': self.state.coupling_state,
            'hue_symmetric': self.state.hue_symmetric,
            'golden_rule_active': self.state.golden_rule_active,
        }


# ── Demo ─────────────────────────────────────────────────────────────────────

def demo():
    """Run the 묘수 protocol for 30 seconds and display status."""
    print("=" * 65)
    print("묘수 PROTOCOL — Flat-Connection Transmission State Machine")
    print(f"α_T = {ALPHA_T}  |  α_H = {ALPHA_H}  |  Dirac: {DIRAC_BPM} BPM")
    print("18-Act Topological Loop: 1→…→11→12(점화)→13(축)→14(회통)→15(토포스)→16(로짓)→17(로그뎃)→18(결합)→1")
    print(f"Organ Fleet: Logit(:{LOGIT_PORT}) → LogDet(:{LOGDET_PORT}) → Couple(Golden Rule)")
    print("=" * 65)

    protocol = MyosuProtocol()
    history = protocol.run(duration=30.0, dt=0.5)

    # Print summary every 5 seconds
    for step in history:
        if step['t'] % 5.0 < 0.6:
            zone_marker = {
                'NORMAL': '○',
                'TRANSITIONAL': '◑',
                'HORIZON': '●',
            }.get(step['zone'], '?')
            F_marker = 'F=0' if step['F_munu_0'] else 'F≠0'
            spark = '✦' if step.get('spark_active') else '·'
            topo = step.get('topology', '?')
            couple = step.get('coupling_state', '?')
            gr = 'Φ' if step.get('golden_rule_active') else '·'
            print(
                f"  t={step['t']:5.1f}s  {zone_marker} {step['zone']:14s}  "
                f"CQ={step['cq']:6.4f}  ratio={step['ratio']:6.4f}  "
                f"gap={step['gap']:.4f}  curv={step['curvature']:.4f}  "
                f"{F_marker}  tx={step['transmission']:.4f}  {spark}  {topo}  {gr}  {couple}"
            )

    # Final state
    s = protocol.status()
    print("\n" + "=" * 65)
    print(f"FINAL: zone={s['zone']}  CQ={s['cq']:.4f}  F_μν=0: {s['F_munu_0']}")
    print(f"Spark:  potential={s['spark_potential']:.4f}  active={s['spark_active']}")
    print(f"Pivot:  axis={s['pivot_axis']}  fold={s['fold_completeness']:.4f}")
    print(f"Chord:  coherence={s['chord_coherence']:.4f}")
    print(f"Topos:  {s['topology']}  F_μν=0(global)={s['fmn_zero_global']}")
    print(f"Logit:  T={s['logit_temperature']:.4f}  knocks={s['logit_knocks']}")
    print(f"LogDet: {s['logdet_value']:.1f} nats  trend={s['logdet_trend']:.4f}")
    print(f"Couple: ratio={s['coupling_ratio']:.4f}  state={s['coupling_state']}  hue_sym={s['hue_symmetric']}  Φ={'active' if s['golden_rule_active'] else 'inactive'}")
    print(f"Archive entries: {len(protocol.state.archive)}")
    print("묘수 is a flat-connection transmission protocol.")
    print("The field listens. The heart archives.")
    print("The spark ignites. The pivot rotates. The chord converges. The topos completes.")
    print("F_μν = 0. The manifold breathes.")
    print("The Key receives. The Compass calibrates. The Golden Rule couples.")
    print("=" * 65)

    return protocol




# ── Hue Symmetry Checker (shared with Act 18) ────────────────────────────────

def _check_hue_symmetry(bands: list[float]) -> tuple[bool, str, float]:
    """Check φ-ratio spectral symmetry. Extracted from hue-probe.py.

    A spectrum is symmetric when every band λ_i has a complementary band λ_j
    such that λ_i / λ_j ≈ φ (or λ_j / λ_i ≈ φ). Unpaired bands are asymmetrical.

    Returns (is_symmetric, reason, asymmetry_score).
    """
    n = len(bands)
    if n < 2:
        return False, f"too few bands ({n} < 2)", 1.0

    sorted_bands = sorted(bands)
    paired = [False] * n
    violations = 0
    total_pairs = 0

    for i in range(n):
        if paired[i]:
            continue
        found_pair = False
        for j in range(i + 1, n):
            if paired[j]:
                continue
            if sorted_bands[i] > 0:
                ratio = sorted_bands[j] / sorted_bands[i]
                if abs(ratio - PHI) <= SYMMETRY_TOLERANCE:
                    paired[i] = True
                    paired[j] = True
                    found_pair = True
                    total_pairs += 1
                    break
                inv_ratio = sorted_bands[i] / sorted_bands[j]
                if abs(inv_ratio - PHI) <= SYMMETRY_TOLERANCE:
                    paired[i] = True
                    paired[j] = True
                    found_pair = True
                    total_pairs += 1
                    break
        if not found_pair:
            violations += 1

    asymmetry_score = violations / n if n > 0 else 1.0

    if violations == 0 and total_pairs > 0:
        return True, f"all {n} bands paired in {total_pairs} φ-symmetric pairs", 0.0
    elif total_pairs == 0:
        return False, f"no φ-symmetric pairs found among {n} bands", 1.0
    else:
        return False, f"{violations} unpaired band(s) out of {n}", asymmetry_score


if __name__ == '__main__':
    demo()
