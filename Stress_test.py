"""
stress_test.py

Stress tests and validation routines for the VEF solver.

Author: Mark Chrisman 
Date: 2026-02-09
"""

from __future__ import annotations
import math
from typing import Dict, Any, List

from solver import VEFParams, create_mesh, step, total_energy_like, simple_observables

def conservation_test(steps: int = 100) -> Dict[str, Any]:
    """
    Track an energy-like quantity over several steps to detect drift.
    """
    params = VEFParams()
    state = create_mesh(16, 16, 16, init_profile="gaussian")
    energies: List[float] = []

    for _ in range(steps):
        step(state, params)
        energies.append(total_energy_like(state))

    drift = energies[-1] - energies[0]
    rel_drift = drift / max(1e-9, abs(energies[0]))

    return {
        "energies": energies,
        "drift": drift,
        "relative_drift": rel_drift,
    }

def perturbation_growth_test(steps: int = 100, amplitude: float = 0.01) -> Dict[str, Any]:
    """
    Apply a small perturbation to the density field and assess growth of structure.
    """
    params = VEFParams()
    state = create_mesh(16, 16, 16, init_profile="gaussian")

    # apply localized perturbation
    nx, ny, nz = len(state.rho), len(state.rho[0]), len(state.rho[0][0])
    cx, cy, cz = nx // 2, ny // 2, nz // 2
    state.rho[cx][cy][cz] *= (1.0 + amplitude)

    contrast: List[float] = []

    for _ in range(steps):
        step(state, params)
        # compute variance as simple structure measure
        mean_rho = 0.0
        count = nx * ny * nz
        for i in range(nx):
            for j in range(ny):
                for k in range(nz):
                    mean_rho += state.rho[i][j][k]
        mean_rho /= count

        var_rho = 0.0
        for i in range(nx):
            for j in range(ny):
                for k in range(nz):
                    dr = state.rho[i][j][k] - mean_rho
                    var_rho += dr * dr
        var_rho /= count
        contrast.append(var_rho)

    return {
        "contrast_history": contrast,
        "final_contrast": contrast[-1],
    }

def parameter_sensitivity_test(steps: int = 50) -> Dict[str, Any]:
    """
    Sweep a few key parameters and record simple stability diagnostics.
    """
    strengths = [0.02, 0.05, 0.1]
    theta_couplings = [0.05, 0.1, 0.2]

    results = {}
    for ex in strengths:
        for tc in theta_couplings:
            label = f"ex_{ex}_tc_{tc}"
            params = VEFParams(exchange_strength=ex, theta_coupling=tc)
            state = create_mesh(16, 16, 16, init_profile="gaussian")
            energies = []
            for _ in range(steps):
                step(state, params)
                energies.append(total_energy_like(state))
            # simple stability metric: max energy excursion
            e0 = energies[0]
            max_dev = max(abs(e - e0) for e in energies)
            results[label] = {
                "energies": energies,
                "max_energy_deviation": max_dev,
            }
    return results

def scaling_estimate() -> Dict[str, Any]:
    """
    Very rough FLOP-scaling estimate based on mesh size.
    This is an analytical estimate, not a runtime measurement.
    """
    # Each cell: O(100) operations per step (rough, from inspection).
    ops_per_cell_per_step = 100.0

    sizes = [(16, 16, 16), (32, 32, 32), (48, 48, 48)]
    steps = 100
    estimates = {}

    for (nx, ny, nz) in sizes:
        cells = nx * ny * nz
        total_ops = cells * ops_per_cell_per_step * steps
        gflops = total_ops / 1e9
        estimates[f"{nx}x{ny}x{nz}"] = {
            "cells": cells,
            "steps": steps,
            "ops_per_cell_per_step": ops_per_cell_per_step,
            "total_ops": total_ops,
            "approx_GFLOPs": gflops,
        }

    return estimates

def run_all_tests() -> Dict[str, Any]:
    """
    Run all stress tests and return a combined report.
    """
    report: Dict[str, Any] = {}
    report["conservation"] = conservation_test()
    report["perturbation_growth"] = perturbation_growth_test()
    report["parameter_sensitivity"] = parameter_sensitivity_test()
    report["scaling_estimate"] = scaling_estimate()
    return report

if __name__ == "__main__":
    report = run_all_tests()
    print("Conservation relative drift:", report["conservation"]["relative_drift"])
    print("Final contrast:", report["perturbation_growth"]["final_contrast"])
    print("Scaling estimates:")
    for k, v in report["scaling_estimate"].items():
        print(k, "-> approx_GFLOPs:", v["approx_GFLOPs"])
