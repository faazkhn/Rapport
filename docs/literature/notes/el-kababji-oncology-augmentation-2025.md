# El Kababji et al.: Augmenting Insufficiently Accruing Oncology Clinical Trials Using Generative Models

- **Citation:** El Kababji S, Mitsakakis N, Jonker E, et al., J Med Internet Res 2025;27:e66821. DOI 10.2196/66821 (PMC11923467).
- **Link:** https://www.jmir.org/2025/1/e66821 · **Open access:** yes (PMC)
- **Code:** pysdg package (synthetic data generation) · **Code licence:** unknown
- **Paper licence:** CC BY
- **Informs:** none

## Mechanism
Retrospective study: from 10 datasets of 9 completed breast cancer trials, the last 10-50% of recruits were removed, generative models (sequential decision-tree synthesis, Bayesian network, CTGAN, VAE) simulated replacements, and the published analysis was repeated.

## Evidence
Sequential synthesis up to 40% removed: decision agreement 88-100%, estimate agreement 100%, CI overlap 0.80-0.92. Bootstrap baseline decision agreement 78-89%. At 50% removal unaugmented analysis lost decision agreement in two trials.

## Limitations
- Retrospective, mostly breast cancer; generalisability unknown.
- Safety/rare events not assessed; failed on smallest trial (needs >=50 observations).
- GAN/VAE untuned.

## For Rapport
**Verdict:** skip. Tabular synthetic trial data; unrelated to a patient simulator. Only distant echo: synthetic data must be validated against real before use.
