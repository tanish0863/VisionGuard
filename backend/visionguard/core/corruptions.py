"""VisionGuard – corruptions.py

Corruption engine that simulates degraded capture conditions.

Three corruption types
----------------------
blur          – Gaussian blur simulating loss of sharpness / focus.
low_light     – Gamma darkening simulating poor illumination.
gaussian_noise – Additive white Gaussian noise simulating sensor noise.

Public API
----------
>>> corrupted = apply(image, kind="blur", severity=2, seed=0)

Design rules (enforced by this module)
---------------------------------------
- Severity levels: 1, 2, 3.
- The original image is NEVER mutated (always deep-copied first).
- Output shape equals input shape.
- Output dtype is uint8; pixel values clipped to [0, 255].
- Randomness (noise only) uses ``np.random.default_rng(seed)``.
- All corruption parameters are documented below and fixed at import time.

Parameters are inspired by ImageNet-C severity levels
(Hendrycks & Dietterich, 2019 – https://github.com/hendrycks/robustness).
This implementation does NOT claim to reproduce ImageNet-C exactly.
The actual parameters used are listed in ``CORRUPTION_PARAMS``.
"""
from __future__ import annotations

import math
from typing import Literal

import cv2
import numpy as np

CorruptionKind = Literal["blur", "low_light", "gaussian_noise"]
Severity = Literal[1, 2, 3]

# --------------------------------------------------------------------------- #
# Documented corruption parameters                                              #
# --------------------------------------------------------------------------- #

#: All parameters used by this module, keyed by (kind, severity).
#: Record these verbatim in the evaluation report so results are reproducible.
CORRUPTION_PARAMS: dict[tuple[str, int], dict] = {
    # Gaussian blur: sigma controls the spread of the kernel.
    # kernel size is always (0, 0) so OpenCV derives it from sigma.
    ("blur", 1): {"sigma": 1.0},
    ("blur", 2): {"sigma": 2.0},
    ("blur", 3): {"sigma": 3.5},

    # Low light: gamma > 1 darkens the image via the standard power law
    #   out = (in / 255) ** gamma * 255
    # Inspired by ImageNet-C brightness (inverted direction).
    ("low_light", 1): {"gamma": 1.5},
    ("low_light", 2): {"gamma": 2.5},
    ("low_light", 3): {"gamma": 4.0},

    # Gaussian noise: standard deviation of additive noise in [0, 255] scale.
    # Inspired by ImageNet-C gaussian_noise severities (approx σ / 255 ~
    # 0.06, 0.12, 0.18 of the [0, 1] scale → 15, 30, 45 on [0, 255] scale).
    ("gaussian_noise", 1): {"std": 15},
    ("gaussian_noise", 2): {"std": 30},
    ("gaussian_noise", 3): {"std": 45},
}


# --------------------------------------------------------------------------- #
# Public entry point                                                            #
# --------------------------------------------------------------------------- #

def apply(
    image: np.ndarray,
    kind: CorruptionKind,
    severity: Severity,
    seed: int = 0,
) -> np.ndarray:
    """Apply a corruption to *image* and return the corrupted copy.

    Parameters
    ----------
    image:
        H×W×3 uint8 NumPy array in RGB colour order.
    kind:
        One of ``"blur"``, ``"low_light"``, ``"gaussian_noise"``.
    severity:
        Corruption intensity: 1 (mild), 2 (moderate), 3 (severe).
    seed:
        RNG seed used for stochastic corruptions (gaussian_noise).
        Deterministic corruptions (blur, low_light) ignore this value.

    Returns
    -------
    np.ndarray
        Corrupted image – same shape and dtype as *image*.

    Raises
    ------
    ValueError
        For unknown kind or severity outside {1, 2, 3}.
    """
    _validate(image, kind, severity)
    img = image.copy()  # never mutate the original

    if kind == "blur":
        return _gaussian_blur(img, severity)
    if kind == "low_light":
        return _low_light(img, severity)
    if kind == "gaussian_noise":
        return _gaussian_noise(img, severity, seed)
    raise ValueError(f"Unknown corruption kind: {kind!r}")  # unreachable


# --------------------------------------------------------------------------- #
# Implementations                                                               #
# --------------------------------------------------------------------------- #

def _gaussian_blur(image: np.ndarray, severity: Severity) -> np.ndarray:
    """Gaussian blur.

    Uses OpenCV's GaussianBlur with a sigma derived from ``CORRUPTION_PARAMS``.
    Kernel size is (0, 0) so OpenCV computes the tightest odd kernel that
    contains the given sigma (6σ + 1 rule).

    Note: OpenCV's GaussianBlur expects BGR by default, but because Gaussian
    blur is isotropic and channel-independent, channel order does not matter.
    """
    params = CORRUPTION_PARAMS[("blur", severity)]
    sigma: float = params["sigma"]
    return cv2.GaussianBlur(image, (0, 0), sigmaX=sigma, sigmaY=sigma)


def _low_light(image: np.ndarray, severity: Severity) -> np.ndarray:
    """Gamma darkening to simulate poor illumination.

    Applies the standard display gamma power-law correction:
        out = (in / 255) ** gamma * 255

    gamma > 1 darkens the image.  A precomputed look-up table (LUT) is used
    for efficiency; it also guarantees exact integer rounding behaviour.
    """
    params = CORRUPTION_PARAMS[("low_light", severity)]
    gamma: float = params["gamma"]

    # Build LUT: maps each pixel value in [0, 255] to its corrected value.
    lut = np.array(
        [math.floor(((i / 255.0) ** gamma) * 255.0 + 0.5) for i in range(256)],
        dtype=np.uint8,
    )
    return cv2.LUT(image, lut)


def _gaussian_noise(
    image: np.ndarray, severity: Severity, seed: int
) -> np.ndarray:
    """Additive white Gaussian noise to simulate sensor noise.

    Uses ``np.random.default_rng(seed)`` for reproducibility.  Noise is
    drawn from N(0, std²) in float32, added to the image, then clipped and
    cast back to uint8.
    """
    params = CORRUPTION_PARAMS[("gaussian_noise", severity)]
    std: int = params["std"]

    rng = np.random.default_rng(seed)
    noise = rng.normal(loc=0.0, scale=float(std), size=image.shape).astype(np.float32)

    corrupted = image.astype(np.float32) + noise
    return np.clip(corrupted, 0, 255).astype(np.uint8)


# --------------------------------------------------------------------------- #
# Validation helpers                                                            #
# --------------------------------------------------------------------------- #

_VALID_KINDS: frozenset[str] = frozenset({"blur", "low_light", "gaussian_noise"})
_VALID_SEVERITIES: frozenset[int] = frozenset({1, 2, 3})


def _validate(image: np.ndarray, kind: str, severity: int) -> None:
    if kind not in _VALID_KINDS:
        raise ValueError(
            f"Unknown corruption kind {kind!r}. "
            f"Valid options: {sorted(_VALID_KINDS)}"
        )
    if severity not in _VALID_SEVERITIES:
        raise ValueError(
            f"Invalid severity {severity!r}. Must be one of {sorted(_VALID_SEVERITIES)}."
        )
    if image.ndim != 3 or image.shape[2] != 3:
        raise ValueError(
            f"Expected H×W×3 image, got shape {image.shape}"
        )
    if image.dtype != np.uint8:
        raise ValueError(
            f"Expected uint8 image, got dtype {image.dtype}"
        )
