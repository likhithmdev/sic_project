"""
Very lightweight heuristic waste classifier for Raspberry Pi.

This avoids TensorFlow / TFLite / YOLO entirely and uses only OpenCV + NumPy.
It is NOT as accurate as a trained model but is sufficient for a demo:
- Looks at color / brightness to guess: 'dry', 'wet', or 'electronic'.

Interface is compatible with the existing detectors:
- detect(frame_bgr) -> List[Dict]
- get_detection_summary(detections) -> Dict with 'destination'
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List

import cv2
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class HeuristicPrediction:
    label: str        # 'dry' | 'wet' | 'electronic'
    confidence: float # 0.0 - 1.0


class HeuristicWasteClassifier:
    """
    Simple, fast heuristic classifier:
    - Uses color / brightness / edge density to guess bin type.
    - Intended to ALWAYS run on Raspberry Pi without heavy dependencies.
    """

    def __init__(self, conf_threshold: float = 0.4):
        self.conf_threshold = conf_threshold
        logger.info("Initialized HeuristicWasteClassifier (no ML, lightweight)")

    def _analyze_frame(self, frame_bgr) -> HeuristicPrediction:
        # Resize to small size for speed
        resized = cv2.resize(frame_bgr, (160, 120))

        # Convert to HSV and grayscale
        hsv = cv2.cvtColor(resized, cv2.COLOR_BGR2HSV)
        gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)

        h, s, v = cv2.split(hsv)

        # Basic statistics
        mean_s = float(np.mean(s))         # colorfulness
        mean_v = float(np.mean(v))         # brightness
        std_v = float(np.std(v))           # contrast

        # Edge density (electronics often have more sharp edges / structure)
        edges = cv2.Canny(gray, 80, 160)
        edge_density = float(np.mean(edges > 0))

        logger.debug(
            "Heuristic stats - mean_s=%.2f mean_v=%.2f std_v=%.2f edge_density=%.3f",
            mean_s,
            mean_v,
            std_v,
            edge_density,
        )

        # Simple rules (tuned for reasonable behavior, not perfection):
        # 1) Likely electronic: high edge density and moderate brightness
        if edge_density > 0.12 and 80 < mean_v < 200:
            return HeuristicPrediction(label="electronic", confidence=0.7)

        # 2) Likely wet/organic: high saturation and moderate-to-high brightness
        if mean_s > 80 and mean_v > 90:
            return HeuristicPrediction(label="wet", confidence=0.65)

        # 3) Default: dry
        return HeuristicPrediction(label="dry", confidence=0.6)

    # ------- Public API compatible with existing detectors ------- #

    def detect(self, frame_bgr) -> List[Dict]:
        """
        Return list of "detections" with the same structure as other models.
        We always return a single detection for the whole frame.
        """
        pred = self._analyze_frame(frame_bgr)
        detection = {
            "class": pred.label,
            "confidence": round(pred.confidence, 2),
            "bbox": None,
        }
        logger.info("Heuristic detection: %s", detection)
        return [detection]

    def get_detection_summary(self, detections: List[Dict]) -> Dict:
        """
        Summary payload for MQTT: {count, objects, destination}.
        """
        if not detections:
            return {"count": 0, "objects": [], "destination": "none"}

        best = detections[0]
        label = best.get("class", "dry")
        confidence = float(best.get("confidence", 0.0))

        # Apply threshold: if below, default to dry (safe bin)
        destination = label if confidence >= self.conf_threshold else "dry"

        return {
            "count": 1,
            "objects": [{"class": destination, "confidence": round(confidence, 2)}],
            "destination": destination,
            "confidence": round(confidence, 2),
        }

