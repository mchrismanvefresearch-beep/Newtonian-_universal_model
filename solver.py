"""
solver.py

Reference implementation of the Variable Exchange Field (VEF) 30 GFLOP solver.

This is a compact, didactic implementation consistent with the Whitepaper.
It is not hardware-optimized but is structured such that operation counts
scale to an ~O(30 GFLOP) budget for moderate mesh sizes.

Author: Mark Chrisman 
Date: 2026-02-09
"""

from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Tuple, Dict, Any, List

@dataclass
class VEFParams:
    """
    Parameters controlling the VEF dynamics.
    """
    exchange_strength: float = 0.05
    hr_base: float = 1.0          # baseline radial Planck gradient
    theta_coupling: float = 0.1   # coupling between theta-phase and exchange
    curvature_relax: float = 0.02
    dt: float = 0.01

@dataclass
class VEFState:
    """
    State of the VEF field on a regular 3D mesh.

    All fields are stored as 3D lists [nx][ny][nz].
    For simplicity we keep pure Python lists; a production version would use
    NumPy / JAX / etc., but this keeps dependencies minimal.
    """
    rho: List[List[List[float]]]      # effective density
    phi: List[List[List[float]]]      # scalar potential
    vx: List[List[List[float]]]       # exchange velocity x
    vy: List[List[List[float]]]       # exchange velocity y
    vz: List[List[List[float]]]       # exchange velocity z
    K:  List[List[List[float]]]       # curvature proxy
    theta: List[List[List[float]]]    # theta-phase pendulum

def create_mesh(nx: int, ny: int, nz: int, init_profile: str = "gaussian") -> VEFState:
    """
    Initialize a VEF mesh with a simple density profile and zeroed fields.
    """
    rho = [[[0.0 for _ in range(nz)] for _ in range(ny)] for _ in range(nx)]
    phi = [[[0.0 for _ in range(nz)] for _ in range(ny)] for _ in range(nx)]
    vx  = [[[0.0 for _ in range(nz)] for _ in range(ny)] for _ in range(nx)]
    vy  = [[[0.0 for _ in range(nz)] for _ in range(ny)] for _ in range(nx)]
    vz  = [[[0.0 for _ in range(nz)] for _ in range(ny)] for _ in range(nx)]
    K   = [[[0.0 for _ in range(nz)] for _ in range(ny)] for _ in range(nx)]
    th  = [[[0.0 for _ in range(nz)] for _ in range(ny)] for _ in range(nx)]

    cx, cy, cz = (nx - 1) / 2.0, (ny - 1) / 2.0, (nz - 1) / 2.0

    for i in range(nx):
        for j in range(ny):
            for k in range(nz):
                if init_profile == "gaussian":
                    dx = (i - cx) / max(1.0, 0.3 * nx)
                    dy = (j - cy) / max(1.0, 0.3 * ny)
                    dz = (k - cz) / max(1.0, 0.3 * nz)
                    r2 = dx * dx + dy * dy + dz * dz
                    rho[i][j][k] = math.exp(-r2)
                else:
                    # uniform with small noise
                    rho[i][j][k] = 1.0

    return VEFState(rho=rho, phi=phi, vx=vx, vy=vy, vz=vz, K=K, theta=th)

def _neighbors(i: int, j: int, k: int, nx: int, ny: int, nz: int) -> List[Tuple[int, int, int]]:
    """
    Return 6-connected neighbors inside the mesh.
    """
    neigh = []
    if i > 0:       neigh.append((i - 1, j, k))
    if i < nx - 1:  neigh.append((i + 1, j, k))
    if j > 0:       neigh.append((i, j - 1, k))
    if j < ny - 1:  neigh.append((i, j + 1, k))
    if k > 0:       neigh.append((i, j, k - 1))
    if k < nz - 1:  neigh.append((i, j, k + 1))
    return neigh

def _hr_factor(i: int, j: int, k: int, nx: int, ny: int, nz: int, hr_base: float) -> float:
    """
    Simple radial Planck gradient factor: increases with distance from center.
    """
    cx, cy, cz = (nx - 1) / 2.0, (ny - 1) / 2.0, (nz - 1) / 2.0
    dx = (i - cx) / max(1.0, 0.5 * nx)
    dy = (j - cy) / max(1.0, 0.5 * ny)
    dz = (k - cz) / max(1.0, 0.5 * nz)
    r = math.sqrt(dx * dx + dy * dy + dz * dz)
    return hr_base * (1.0 + 0.3 * r)

def step(state: VEFState, params: VEFParams) -> None:
    """
    Advance the VEF state by one time step using local exchange rules.

    This function performs:
      - Gradient-like updates of phi from rho and K
      - Exchange flux computation via vx, vy, vz
      - Theta-phase pendulum update
      - Curvature relaxation

    All updates are done on temporaries then committed, to avoid directional bias.
    """
    rho, phi, vx, vy, vz, K, th = state.rho, state.phi, state.vx, state.vy, state.vz, state.K, state.theta
    nx, ny, nz = len(rho), len(rho[0]), len(rho[0][0])

    new_phi = [[[phi[i][j][k] for k in range(nz)] for j in range(ny)] for i in range(nx)]
    new_vx  = [[[vx[i][j][k]  for k in range(nz)] for j in range(ny)] for i in range(nx)]
    new_vy  = [[[vy[i][j][k]  for k in range(nz)] for j in range(ny)] for i in range(nx)]
    new_vz  = [[[vz[i][j][k]  for k in range(nz)] for j in range(ny)] for i in range(nx)]
    new_K   = [[[K[i][j][k]   for k in range(nz)] for j in range(ny)] for i in range(nx)]
    new_th  = [[[th[i][j][k]  for k in range(nz)] for j in range(ny)] for i in range(nx)]

    ex = params.exchange_strength
    dt = params.dt
    hr0 = params.hr_base
    theta_c = params.theta_coupling
    Krelax = params.curvature_relax

    for i in range(nx):
        for j in range(ny):
            for k in range(nz):
                nbs = _neighbors(i, j, k, nx, ny, nz)
                # local averages
                rho_c = rho[i][j][k]
                phi_c = phi[i][j][k]
                K_c   = K[i][j][k]
                th_c  = th[i][j][k]

                # compute neighbor averages and simple Laplacian-like terms
                sum_phi = 0.0
                sum_K   = 0.0
                for (ii, jj, kk) in nbs:
                    sum_phi += phi[ii][jj][kk]
                    sum_K   += K[ii][jj][kk]
                if nbs:
                    avg_phi = sum_phi / len(nbs)
                    avg_K   = sum_K / len(nbs)
                else:
                    avg_phi = phi_c
                    avg_K   = K_c

                # effective radial Planck gradient
                hr = _hr_factor(i, j, k, nx, ny, nz, hr0)

                # update phi: respond to density and curvature differences
                dphi = (rho_c - 0.5 * (phi_c - avg_phi) - 0.2 * (K_c - avg_K)) * ex * hr * dt
                new_phi[i][j][k] = phi_c + dphi

                # approximate gradient -> velocity update (exchange flow)
                gx = 0.0
                gy = 0.0
                gz = 0.0
                for (ii, jj, kk) in nbs:
                    d = phi[ii][jj][kk] - phi_c
                    if ii != i:
                        gx += math.copysign(d, ii - i)
                    if jj != j:
                        gy += math.copysign(d, jj - j)
                    if kk != k:
                        gz += math.copysign(d, kk - k)
                if nbs:
                    scale = ex * dt / len(nbs)
                    gx *= scale
                    gy *= scale
                    gz *= scale

                # theta-phase pendulum: driven oscillator around 0
                omega2 = 1.0 + 0.5 * abs(K_c)
                dtheta = -omega2 * th_c * dt + theta_c * (rho_c - 1.0) * dt
                new_th[i][j][k] = th_c + dtheta

                # theta feeds back into velocity magnitude
                cos_th = math.cos(new_th[i][j][k])
                new_vx[i][j][k] = vx[i][j][k] + gx * (1.0 + 0.3 * cos_th)
                new_vy[i][j][k] = vy[i][j][k] + gy * (1.0 + 0.3 * cos_th)
                new_vz[i][j][k] = vz[i][j][k] + gz * (1.0 + 0.3 * cos_th)

                # curvature relaxes toward local energy density
                target_K = rho_c + 0.1 * abs(phi_c)
                new_K[i][j][k] = K_c + Krelax * (target_K - K_c) * dt

    # commit
    state.phi = new_phi
    state.vx = new_vx
    state.vy = new_vy
    state.vz = new_vz
    state.K = new_K
    state.theta = new_th

def total_energy_like(state: VEFState) -> float:
    """
    Compute a simple energy-like quantity for diagnostics.
    """
    rho, phi, vx, vy, vz, K = state.rho, state.phi, state.vx, state.vy, state.vz, state.K
    nx, ny, nz = len(rho), len(rho[0]), len(rho[0][0])
    total = 0.0
    for i in range(nx):
        for j in range(ny):
            for k in range(nz):
                v2 = vx[i][j][k] ** 2 + vy[i][j][k] ** 2 + vz[i][j][k] ** 2
                total += rho[i][j][k] * (0.5 * v2 + 0.5 * phi[i][j][k] ** 2) + 0.1 * K[i][j][k] ** 2
    return total

def simple_observables(state: VEFState) -> Dict[str, Any]:
    """
    Compute a few coarse observables from the field:
      - radial potential profile
      - rough rotation curve proxy
    """
    rho, phi = state.rho, state.phi
    nx, ny, nz = len(rho), len(rho[0]), len(rho[0][0])
    cx, cy, cz = (nx - 1) / 2.0, (ny - 1) / 2.0, (nz - 1) / 2.0

    max_r = int(min(nx, ny, nz) / 2)
    radial_phi = [0.0 for _ in range(max_r)]
    radial_count = [0 for _ in range(max_r)]

    for i in range(nx):
        for j in range(ny):
            for k in range(nz):
                r = int(round(math.sqrt((i - cx) ** 2 + (j - cy) ** 2 + (k - cz) ** 2)))
                if 0 <= r < max_r:
                    radial_phi[r] += phi[i][j][k]
                    radial_count[r] += 1

    for r in range(max_r):
        if radial_count[r] > 0:
            radial_phi[r] /= radial_count[r]

    # rotation curve proxy: v_rot ~ sqrt(r * dPhi/dr)
    vrot = [0.0 for _ in range(max_r)]
    for r in range(1, max_r - 1):
        dphi_dr = 0.5 * (radial_phi[r + 1] - radial_phi[r - 1])
        vrot[r] = math.sqrt(max(0.0, r * abs(dphi_dr)))

    return {
        "radial_phi": radial_phi,
        "vrot_proxy": vrot,
    }

def run_simulation(nx: int = 32, ny: int = 32, nz: int = 32,
                   steps: int = 100,
                   params: VEFParams | None = None) -> Dict[str, Any]:
    """
    Run a basic VEF simulation and return diagnostics and observables.
    """
    if params is None:
        params = VEFParams()

    state = create_mesh(nx, ny, nz, init_profile="gaussian")
    energies = []

    for _ in range(steps):
        step(state, params)
        energies.append(total_energy_like(state))

    obs = simple_observables(state)
    result = {
        "energies": energies,
        "observables": obs,
        "final_state": state,
    }
    return result

if __name__ == "__main__":
    # Minimal example run
    sim = run_simulation(nx=16, ny=16, nz=16, steps=50)
    print("Final energy-like quantity:", sim["energies"][-1])
    print("Sample vrot_proxy:", sim["observables"]["vrot_proxy"][:10])
