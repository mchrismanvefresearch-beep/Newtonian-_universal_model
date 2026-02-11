# Efficiency Comparison Matrix: VEF vs. ΛCDM N-body

This document summarizes the qualitative and semi-quantitative differences between the VEF 30 GFLOP solver and a representative \(\Lambda\)CDM N-body + radiative transfer pipeline.

| Aspect                        | VEF (This Work)                                                | Conventional \(\Lambda\)CDM N-body                        |
|-------------------------------|----------------------------------------------------------------|-----------------------------------------------------------|
| Representation                | Geometric simplex, exchange field (\(\rho, \Phi, \mathbf{V}, K, \theta\)) | Billions of particles with long-range gravity            |
| Typical DOFs (conceptual)     | \(\sim 10^{5} - 10^{7}\) field cells                           | \(\sim 10^{9} - 10^{12}\) particles                       |
| Gravity solver                | Local exchange rules, no global Poisson solve                 | TreePM / FFT Poisson, non-local updates                  |
| Time stepping                 | Fixed, simple local updates                                   | Adaptive, multi-step with complex criteria               |
| Observables                   | Directly from fields (potential, curvature)                   | Derived via ray tracing, mock catalogs, postprocessing   |
| Computational cost (per run) | \(\sim 10^{1} - 10^{2}\) GFLOPs (depending on mesh)           | \(\sim 10^{10} - 10^{12}\) FLOPs                         |
| Efficiency gain              | Baseline \(\approx 10^{9}\) vs. naive high-res N-body         | Baseline                                                  |
| Memory footprint             | Small, cell state only                                        | Large particle arrays + force structures                 |
| Scaling behavior             | Linear in number of cells                                     | Superlinear due to long-range forces and communication   |
| Parallelization              | Trivially local / domain decomposition                        | Complex, requires careful load balancing                 |

## Notes

1. The **efficiency gain** on the order of \(10^{9}\) is an order-of-magnitude comparison, not a strict benchmark on a particular machine. It reflects:
   - The difference in degrees of freedom needed to reach similar qualitative observables.
   - The absence of global Poisson solves and heavy postprocessing.

2. The VEF solver is best viewed as a **compressed physics engine** for exploration and intuition-building. It is not a direct 1:1 replacement for precision cosmological inference pipelines.

3. Further optimization (e.g., vectorization, GPU support) can close the gap between the reference 30 GFLOP conceptual budget and real hardware performance.

4. The \(\theta\)-phase and \(h_r\) constructs effectively encode part of what is usually attributed to dark matter distributions and metric perturbations, allowing strong compression of the physical state.

5. Future work should add:
   - More detailed baryonic physics proxies.
   - Calibration to full observational likelihoods.
   - Automated comparison notebooks.
