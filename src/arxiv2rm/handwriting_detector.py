"""
Handwriting Detection Module

Detects whether an image/page contains handwritten text to route to appropriate OCR engine.
Uses multiple heuristics and optional confidence scores from DeepSeek OCR.
"""

import logging
from pathlib import Path
from typing import Dict, Optional

import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


class HandwritingDetector:
    """
    Detect handwritten vs printed text using multiple strategies.

    Strategies:
    1. DeepSeek OCR confidence scores (if available)
    2. Edge density analysis (handwriting has irregular edges)
    3. Stroke width variance (handwriting varies more)
    4. Text line straightness (printed text is straighter)
    5. Optional: lightweight CNN classifier
    """

    def __init__(self, confidence_threshold: float = 0.85):
        """
        Initialize detector.

        Args:
            confidence_threshold: If DeepSeek confidence < this, likely handwritten
        """
        self.confidence_threshold = confidence_threshold

    def detect(
        self,
        image_path: Path,
        deepseek_confidence: Optional[float] = None,
        deepseek_text: Optional[str] = None,
    ) -> Dict:
        """
        Detect if image contains handwritten text.

        Args:
            image_path: Path to image file
            deepseek_confidence: Optional confidence score from DeepSeek OCR
            deepseek_text: Optional extracted text from DeepSeek OCR

        Returns:
            Dict with:
            - is_handwritten: bool
            - confidence: float (0-1)
            - reasons: list of detection reasons
            - recommendation: str (local/groq)
        """
        reasons = []
        scores = []

        # Strategy 1: DeepSeek confidence score (HIGHEST WEIGHT)
        # If DeepSeek was run, trust its confidence score heavily
        if deepseek_confidence is not None:
            if deepseek_confidence < self.confidence_threshold:
                reasons.append(f"DeepSeek confidence low ({deepseek_confidence:.2f})")
                # Low confidence = likely handwritten
                deepseek_score = 1.0 - deepseek_confidence
            else:
                reasons.append(f"DeepSeek confidence high ({deepseek_confidence:.2f})")
                # High confidence = likely printed
                deepseek_score = 0.0

            # Give DeepSeek score 3x weight (most reliable indicator)
            scores.extend([deepseek_score] * 3)

        # Strategy 2: Text quality analysis
        if deepseek_text is not None:
            text_score = self._analyze_text_quality(deepseek_text)
            if text_score > 0.5:
                reasons.append(f"Low text quality (score: {text_score:.2f})")
            scores.append(text_score)

        # Strategy 3: Image analysis
        img = Image.open(image_path)
        img_array = np.array(img.convert("L"))  # Grayscale

        # Edge density
        edge_score = self._calculate_edge_density(img_array)
        if edge_score > 0.6:
            reasons.append(f"High edge irregularity ({edge_score:.2f})")
        scores.append(edge_score)

        # Stroke width variance
        stroke_score = self._calculate_stroke_variance(img_array)
        if stroke_score > 0.6:
            reasons.append(f"High stroke variance ({stroke_score:.2f})")
        scores.append(stroke_score)

        # Line straightness (if text detected)
        if len(img_array) > 0:
            line_score = self._calculate_line_straightness(img_array)
            if line_score > 0.5:
                reasons.append(f"Irregular text lines ({line_score:.2f})")
            scores.append(line_score)

        # Aggregate scores
        final_score = np.mean(scores) if scores else 0.5
        is_handwritten = final_score > 0.5

        result = {
            "is_handwritten": is_handwritten,
            "confidence": final_score,
            "reasons": reasons,
            "recommendation": "groq" if is_handwritten else "local",
            "scores": {
                "deepseek_confidence": deepseek_confidence,
                "text_quality": text_score if deepseek_text else None,
                "edge_density": edge_score,
                "stroke_variance": stroke_score,
                "line_straightness": line_score if len(img_array) > 0 else None,
            },
        }

        logger.info(
            f"Handwriting detection: {is_handwritten} "
            f"(confidence: {final_score:.2f}, reasons: {len(reasons)})"
        )

        return result

    def _analyze_text_quality(self, text: str) -> float:
        """
        Analyze extracted text quality to infer handwriting.

        Poor OCR results suggest handwritten text:
        - Many short words (fragmented)
        - High ratio of non-alphanumeric chars
        - Unusual character patterns

        Returns:
            Score 0-1 (higher = more likely handwritten)
        """
        if not text or len(text) < 10:
            return 0.5  # Insufficient data

        # Count indicators
        words = text.split()
        if not words:
            return 0.5

        # Short words (< 3 chars) suggest fragmentation
        short_words = sum(1 for w in words if len(w) < 3)
        short_ratio = short_words / len(words)

        # Non-alphanumeric ratio
        alnum_chars = sum(1 for c in text if c.isalnum())
        non_alnum_ratio = 1.0 - (alnum_chars / len(text))

        # Gibberish detection: uncommon character sequences
        gibberish_score = self._detect_gibberish(text)

        # Aggregate
        quality_score = (short_ratio + non_alnum_ratio + gibberish_score) / 3
        return quality_score

    def _detect_gibberish(self, text: str) -> float:
        """
        Detect gibberish text (indicates poor OCR on handwriting).

        Returns:
            Score 0-1 (higher = more gibberish)
        """
        # Simple heuristic: count unusual character combinations
        unusual_patterns = [
            "xxx",
            "yyy",
            "zzz",  # Repeated uncommon letters
            "qq",
            "kk",
            "jj",  # Double uncommon consonants
        ]

        text_lower = text.lower()
        unusual_count = sum(text_lower.count(pattern) for pattern in unusual_patterns)

        return min(unusual_count / 10.0, 1.0)

    def _calculate_edge_density(self, img_array: np.ndarray) -> float:
        """
        Calculate edge density and irregularity.

        Handwriting has more irregular edges than printed text.

        Returns:
            Score 0-1 (higher = more handwritten-like)
        """
        try:
            # Detect edges using Canny
            edges = cv2.Canny(img_array, 50, 150)

            # Calculate edge pixel ratio
            edge_ratio = np.sum(edges > 0) / edges.size

            # Calculate edge irregularity (standard deviation of edge runs)
            edge_runs = []
            for row in edges:
                run_length = 0
                for pixel in row:
                    if pixel > 0:
                        run_length += 1
                    elif run_length > 0:
                        edge_runs.append(run_length)
                        run_length = 0

            if edge_runs:
                irregularity = np.std(edge_runs) / (np.mean(edge_runs) + 1e-6)
            else:
                irregularity = 0

            # Combine metrics (normalize to 0-1)
            score = min((edge_ratio * 10 + irregularity) / 2, 1.0)
            return score

        except Exception as e:
            logger.warning(f"Edge density calculation failed: {e}")
            return 0.5

    def _calculate_stroke_variance(self, img_array: np.ndarray) -> float:
        """
        Calculate stroke width variance.

        Handwriting has more variable stroke widths.

        Returns:
            Score 0-1 (higher = more variance = more handwritten-like)
        """
        try:
            # Simple approach: calculate variance in local pixel intensity
            # Apply Gaussian blur to get stroke regions
            blurred = cv2.GaussianBlur(img_array, (5, 5), 0)

            # Calculate local variance using sliding window
            kernel_size = 10
            variances = []

            for i in range(0, img_array.shape[0] - kernel_size, kernel_size):
                for j in range(0, img_array.shape[1] - kernel_size, kernel_size):
                    window = blurred[i : i + kernel_size, j : j + kernel_size]
                    if np.mean(window) < 200:  # Text region (darker)
                        variances.append(np.var(window))

            if variances:
                overall_variance = np.var(variances)
                # Normalize (handwriting typically has variance > 500)
                score = min(overall_variance / 1000, 1.0)
                return score

            return 0.5

        except Exception as e:
            logger.warning(f"Stroke variance calculation failed: {e}")
            return 0.5

    def _calculate_line_straightness(self, img_array: np.ndarray) -> float:
        """
        Calculate text line straightness.

        Printed text has straighter baselines than handwriting.

        Returns:
            Score 0-1 (higher = more curved/irregular = more handwritten-like)
        """
        try:
            # Find horizontal projection profile
            projection = np.sum(img_array < 128, axis=1)  # Dark pixels per row

            # Find peaks (text lines)
            from scipy import signal

            peaks, _ = signal.find_peaks(projection, distance=20, prominence=50)

            if len(peaks) < 2:
                return 0.5  # Insufficient data

            # Calculate standard deviation of peak positions
            # Handwriting has more variation
            peak_variance = np.std(np.diff(peaks))

            # Normalize (typical variation: printed ~2-5, handwritten ~10-30)
            score = min(peak_variance / 30, 1.0)
            return score

        except Exception as e:
            logger.warning(f"Line straightness calculation failed: {e}")
            return 0.5


def detect_handwriting_smart(
    image_path: Path, deepseek_ocr_result: Optional[Dict] = None, threshold: float = 0.6
) -> bool:
    """
    Convenience function for smart handwriting detection.

    Args:
        image_path: Path to image
        deepseek_ocr_result: Optional DeepSeek OCR result with confidence/text
        threshold: Confidence threshold for classification

    Returns:
        True if handwritten, False if printed
    """
    detector = HandwritingDetector()

    confidence = None
    text = None

    if deepseek_ocr_result:
        confidence = deepseek_ocr_result.get("confidence")
        text = deepseek_ocr_result.get("text")

    result = detector.detect(image_path, confidence, text)

    return result["is_handwritten"]


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Test on handwritten image
    test_image = Path("exemples/handwritten/Newsletter - page 1.png")

    if test_image.exists():
        detector = HandwritingDetector()
        result = detector.detect(test_image)

        print("\nHandwriting Detection Result:")
        print(f"Is Handwritten: {result['is_handwritten']}")
        print(f"Confidence: {result['confidence']:.2f}")
        print(f"Recommendation: Use {result['recommendation']} OCR")
        print("\nReasons:")
        for reason in result["reasons"]:
            print(f"  - {reason}")
        print("\nDetailed Scores:")
        for key, value in result["scores"].items():
            if value is not None:
                print(f"  {key}: {value:.2f}")
