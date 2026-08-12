#!/usr/bin/env python3
"""
The Somatic Alarm (Summa Volume IV): GPU analog of the autonomic nervous system.

Maps the body's registers to compute telemetry:
    HRV  (heart rate variability)  ->  response-time jitter
    respiration                     ->  throughput variance
    vagal tone                      ->  remainder (unallocated capacity)

The remainder tracker detects unknown unknowns: when the residual of the
predicted resource curve vs the observed curve exceeds a threshold sigma,
an alarm fires.

Reference values from the Summa: RHR ~ 55 BPM, 5% free memory as a critical
threshold, non-linear resource cliff. Jitter -> 0 = dead / deterministic loop.
"""
import numpy as np


def hrv_of(jitter):
    """HRV analog: coefficient of variation of response time."""
    j = np.asarray(jitter, dtype=float)
    return float(j.std() / (j.mean() + 1e-9))


def remainder_tracker(observed, predicted, window=20, threshold=3.0):
    """Detect unknown unknowns: |obs - pred| residual beyond threshold sigma."""
    obs = np.asarray(observed, dtype=float)
    pred = np.asarray(predicted, dtype=float)
    residuals = obs - pred
    alarms = []
    for i in range(window, len(obs)):
        w = residuals[i - window:i]
        mu, sigma = w.mean(), w.std() + 1e-9
        z = (residuals[i] - mu) / sigma
        if abs(z) > threshold:
            alarms.append((i, float(z)))
    return alarms


def main():
    rng = np.random.default_rng(7)
    n = 600

    # healthy GPU: flexible jitter around a "resting heart rate" of ~55 ms
    latency = 55.0 + rng.normal(0.0, 8.0, n)
    throughput = 1000 + rng.normal(0.0, 60.0, n)
    load = np.linspace(0.5, 0.9, n) + rng.normal(0, 0.02, n)
    predicted = 40.0 + 40.0 * load

    # resource cliff at t=400: deterministic slow loop -> jitter collapses
    latency[400:] = 350.0 + rng.normal(0.0, 0.5, n - 400)   # near-constant slow
    throughput[400:] = 250.0 + rng.normal(0.0, 2.0, n - 400)

    hrv_healthy = hrv_of(latency[:400])
    hrv_after = hrv_of(latency[400:])
    alarms = remainder_tracker(latency, predicted)

    print("=" * 56)
    print("SOMATIC ALARM — GPU HRV / remainder tracker")
    print("=" * 56)
    print(f"HRV (jitter CV) healthy  = {hrv_healthy:.4f}")
    print(f"HRV (jitter CV) after    = {hrv_after:.4f}   <- jitter collapse")
    print(f"throughput mean healthy  = {throughput[:400].mean():.1f}")
    print(f"throughput mean after    = {throughput[400:].mean():.1f}   <- cliff")
    print()
    print(f"remainder-tracker alarms (|z| > 3): {len(alarms)}")
    if alarms:
        first = alarms[0]
        print(f"  first alarm at t={first[0]}  z={first[1]:.2f}  (resource cliff)")
    print()
    print("Jitter -> 0 = dead or deterministic failure loop.")
    print("5% free memory = critical threshold. The resource cliff is non-linear.")


if __name__ == "__main__":
    main()
