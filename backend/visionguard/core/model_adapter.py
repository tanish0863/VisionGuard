"""VisionGuard – model_adapter.py

Provides a uniform DetectorAdapter interface so the pipeline can switch
detectors without touching any other module.

Conventions (mirror visionguard_contracts/visionguard/core/types.py):
- Input:  H×W×3 numpy array, dtype uint8, RGB colour order.
- Output: list of dicts, each with keys:
      class_id   (int)
      class_name (str)
      confidence (float, [0, 1])
      bbox_xyxy  (list[float], absolute pixels of the ORIGINAL image)
- Boxes are kept in original-image pixel coordinates.
- The SAME confidence threshold and NMS settings are applied to BOTH clean
  and corrupted images.  The caller must not tweak these between runs.
- NMS settings are reported via `nms_settings` so they appear in the report.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

import numpy as np

log = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Public types                                                                  #
# --------------------------------------------------------------------------- #

PredictionDict = dict[str, Any]   # class_id, class_name, confidence, bbox_xyxy


class DetectorAdapter(ABC):
    """Common interface for all detectors used by VisionGuard.

    Subclasses MUST NOT change the meaning of ``score_threshold`` or apply
    their own thresholding on top of it: the threshold is the single source
    of truth and is recorded in every report.
    """

    #: Confidence threshold applied AFTER model inference.
    score_threshold: float
    #: NMS settings (iou_threshold, …) – recorded in the report verbatim.
    nms_settings: dict[str, Any]

    @abstractmethod
    def predict(self, image_rgb: np.ndarray) -> list[PredictionDict]:
        """Run inference on one RGB image.

        Parameters
        ----------
        image_rgb:
            H×W×3 uint8 NumPy array in RGB order.  The adapter MUST NOT
            mutate this array.

        Returns
        -------
        list[PredictionDict]
            Detections above ``score_threshold``, sorted descending by
            confidence.  Empty list when nothing is detected.
        """

    def info(self) -> dict[str, Any]:
        """Return adapter settings for inclusion in the evaluation report."""
        return {
            "adapter": type(self).__name__,
            "score_threshold": self.score_threshold,
            "nms_settings": self.nms_settings,
        }


# --------------------------------------------------------------------------- #
# COCO class names                                                              #
# --------------------------------------------------------------------------- #

# COCO 2017 class names indexed by the torchvision label integer.
# Index 0 = "__background__" (never returned by the model).
_COCO_NAMES: list[str] = [
    "__background__", "person", "bicycle", "car", "motorcycle", "airplane",
    "bus", "train", "truck", "boat", "traffic light", "fire hydrant", "N/A",
    "stop sign", "parking meter", "bench", "bird", "cat", "dog", "horse",
    "sheep", "cow", "elephant", "bear", "zebra", "giraffe", "N/A", "backpack",
    "umbrella", "N/A", "N/A", "handbag", "tie", "suitcase", "frisbee", "skis",
    "snowboard", "sports ball", "kite", "baseball bat", "baseball glove",
    "skateboard", "surfboard", "tennis racket", "bottle", "N/A", "wine glass",
    "cup", "fork", "knife", "spoon", "bowl", "banana", "apple", "sandwich",
    "orange", "broccoli", "carrot", "hot dog", "pizza", "donut", "cake",
    "chair", "couch", "potted plant", "bed", "N/A", "dining table", "N/A",
    "N/A", "toilet", "N/A", "tv", "laptop", "mouse", "remote", "keyboard",
    "cell phone", "microwave", "oven", "toaster", "sink", "refrigerator",
    "N/A", "book", "clock", "vase", "scissors", "teddy bear", "hair drier",
    "toothbrush",
]


# --------------------------------------------------------------------------- #
# TorchvisionDetector                                                           #
# --------------------------------------------------------------------------- #

class TorchvisionDetector(DetectorAdapter):
    """Pretrained Faster R-CNN (ResNet-50 FPN) from torchvision.

    Supported model IDs
    -------------------
    ``fasterrcnn_resnet50_fpn``     – default, COCO-pretrained.
    ``fasterrcnn_resnet50_fpn_v2``  – improved version (torchvision >= 0.14).

    NMS is handled internally by torchvision's GeneralizedRCNN.  The NMS
    IoU threshold is set **explicitly** via ``roi_heads.nms_thresh`` so the
    value is deterministic and recorded in the report regardless of which
    torchvision version is installed.  Do not assume the model default is 0.5.

    Parameters
    ----------
    model_id:
        One of the supported model IDs above.
    score_threshold:
        Discard detections whose confidence is below this value.
        Applied after model inference.  Default 0.5.
    nms_iou_threshold:
        IoU threshold passed to the model's built-in NMS.  Default 0.5.
    device:
        ``"cpu"`` or ``"cuda"``.  Defaults to CUDA when available.
    """

    _SUPPORTED: dict[str, str] = {
        "fasterrcnn_resnet50_fpn": "fasterrcnn_resnet50_fpn",
        "fasterrcnn_resnet50_fpn_v2": "fasterrcnn_resnet50_fpn_v2",
    }

    def __init__(
        self,
        model_id: str = "fasterrcnn_resnet50_fpn",
        *,
        score_threshold: float = 0.5,
        nms_iou_threshold: float = 0.5,
        device: str | None = None,
    ) -> None:
        if model_id not in self._SUPPORTED:
            raise ValueError(
                f"Unsupported model_id '{model_id}'. "
                f"Choose from: {list(self._SUPPORTED)}"
            )

        # Lazy import so the module is importable without torch installed.
        try:
            import torch
            import torchvision
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "TorchvisionDetector requires torch and torchvision. "
                "Install them with:  pip install torch torchvision"
            ) from exc

        self.model_id = model_id
        self.score_threshold = float(score_threshold)
        self.nms_iou_threshold = float(nms_iou_threshold)

        # Device resolution
        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device = device

        # Load model ----------------------------------------------------------
        log.info("Loading %s  weights=DEFAULT  device=%s", model_id, device)
        loader_fn = getattr(torchvision.models.detection, self._SUPPORTED[model_id])

        # New weights API (torchvision >= 0.13) with graceful fallback.
        try:
            from torchvision.models.detection import (
                FasterRCNN_ResNet50_FPN_Weights,
                FasterRCNN_ResNet50_FPN_V2_Weights,
            )
            _weights_map = {
                "fasterrcnn_resnet50_fpn": FasterRCNN_ResNet50_FPN_Weights.DEFAULT,
                "fasterrcnn_resnet50_fpn_v2": FasterRCNN_ResNet50_FPN_V2_Weights.DEFAULT,
            }
            self._model = loader_fn(weights=_weights_map[model_id])
            self._weights_name = str(_weights_map[model_id])
        except (ImportError, AttributeError):
            self._model = loader_fn(pretrained=True)  # type: ignore[call-arg]
            self._weights_name = "DEFAULT (legacy pretrained=True)"

        # Explicitly override NMS threshold – do NOT rely on the torchvision
        # default, which differs between model versions.
        if hasattr(self._model, "roi_heads") and hasattr(
            self._model.roi_heads, "nms_thresh"
        ):
            self._model.roi_heads.nms_thresh = nms_iou_threshold
            _nms_source = "roi_heads.nms_thresh (set explicitly)"
        else:  # pragma: no cover
            log.warning(
                "Could not set nms_thresh on %s; the model's built-in default "
                "is used.  Record the actual value from torchvision source.",
                model_id,
            )
            _nms_source = "model default (could not override – see warning)"

        self._model.eval()
        self._model.to(device)

        # Preprocessing: torchvision.transforms.functional.to_tensor converts
        # a uint8 HxWxC numpy array to a float32 CxHxW tensor in [0, 1].
        try:
            from torchvision.transforms.functional import to_tensor as _to_tensor
        except ImportError:
            import torchvision.transforms.functional as _TF
            _to_tensor = _TF.to_tensor  # type: ignore[assignment]
        self._to_tensor = _to_tensor

        # Record NMS settings for the report.
        self.nms_settings = {
            "nms_iou_threshold": self.nms_iou_threshold,
            "source": _nms_source,
        }

        log.info(
            "%s ready:  score_threshold=%.2f  nms_iou=%.2f  device=%s",
            model_id, score_threshold, nms_iou_threshold, device,
        )

    # ---------------------------------------------------------------------- #

    def predict(self, image_rgb: np.ndarray) -> list[PredictionDict]:
        """Run Faster R-CNN on one RGB uint8 image."""
        import torch

        if image_rgb.ndim != 3 or image_rgb.shape[2] != 3:
            raise ValueError(
                f"Expected H×W×3 RGB image, got shape {image_rgb.shape}"
            )

        # to_tensor: uint8 HxWxC -> float32 CxHxW in [0,1]
        tensor = self._to_tensor(image_rgb).to(self.device)

        with torch.no_grad():
            outputs = self._model([tensor])

        out = outputs[0]
        boxes: list[list[float]] = out["boxes"].cpu().tolist()
        labels: list[int] = out["labels"].cpu().tolist()
        scores: list[float] = out["scores"].cpu().tolist()

        # torchvision already returns detections sorted by score (descending).
        results: list[PredictionDict] = []
        for box, label, score in zip(boxes, labels, scores):
            if score < self.score_threshold:
                break  # sorted descending – safe to break early
            class_name = (
                _COCO_NAMES[label]
                if 0 <= label < len(_COCO_NAMES)
                else str(label)
            )
            results.append(
                {
                    "class_id": int(label),
                    "class_name": class_name,
                    "confidence": round(float(score), 6),
                    "bbox_xyxy": [round(v, 2) for v in box],
                }
            )

        return results

    # ---------------------------------------------------------------------- #

    def info(self) -> dict[str, Any]:
        base = super().info()
        base.update(
            {
                "model_id": self.model_id,
                "weights": self._weights_name,
                "device": self.device,
            }
        )
        return base


# --------------------------------------------------------------------------- #
# FakeDetector                                                                  #
# --------------------------------------------------------------------------- #

class FakeDetector(DetectorAdapter):
    """Deterministic stub detector for unit tests.

    Returns a caller-supplied list of predictions for *every* image,
    regardless of image content.  Completely isolated from torch/torchvision.

    Parameters
    ----------
    predictions:
        The list returned by every ``predict()`` call.
    score_threshold:
        Stored and reported; the caller is responsible for only passing
        predictions that should survive the threshold.
    """

    def __init__(
        self,
        predictions: list[PredictionDict] | None = None,
        *,
        score_threshold: float = 0.5,
    ) -> None:
        self.score_threshold = float(score_threshold)
        self.nms_settings = {
            "nms_iou_threshold": "n/a",
            "source": "FakeDetector – no real NMS",
        }
        self._predictions: list[PredictionDict] = list(predictions or [])

    def predict(self, image_rgb: np.ndarray) -> list[PredictionDict]:  # noqa: ARG002
        """Return the fixed prediction list; image content is ignored."""
        return list(self._predictions)

    def set_predictions(self, predictions: list[PredictionDict]) -> None:
        """Replace the fixed predictions between test cases."""
        self._predictions = list(predictions)
