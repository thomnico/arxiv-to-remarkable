"""
Image Optimizer for reMarkable e-ink display.

Optimizes images for reMarkable's e-ink display:
- Resize to fit reMarkable 1 (1404×1872px) or reMarkable 2 (1872×2480px)
- Convert to grayscale (e-ink displays are grayscale)
- Enhance contrast for better e-ink rendering
- Optional dithering for photographs
- Compress to target file size (<500KB)
- Add EXIF metadata
"""

import logging
from dataclasses import dataclass
from enum import Enum
from io import BytesIO
from pathlib import Path
from typing import Optional

from PIL import Image, ImageEnhance, ImageOps

logger = logging.getLogger(__name__)


class RemarkableDevice(Enum):
    """reMarkable device specifications."""

    REMARKABLE_1 = (1404, 1872)
    REMARKABLE_2 = (1872, 2480)
    REMARKABLE_PRO = (1620, 2160)  # reMarkable Paper Pro, 11.8" color E Ink, 229 DPI


@dataclass
class OptimizationSettings:
    """Settings for image optimization."""

    device: RemarkableDevice = RemarkableDevice.REMARKABLE_1
    quality: int = 85  # JPEG quality (1-100)
    max_file_size_kb: int = 500  # Target max file size in KB
    contrast_factor: float = 1.2  # Contrast enhancement (1.0 = no change)
    sharpness_factor: float = 1.1  # Sharpness enhancement
    dither: bool = False  # Apply Floyd-Steinberg dithering
    grayscale: bool = True  # Convert to grayscale (set False for reMarkable Pro color)
    maintain_aspect: bool = True  # Maintain aspect ratio


class ImageOptimizer:
    """
    Optimizes images for reMarkable e-ink display.

    Usage:
        optimizer = ImageOptimizer()
        result = optimizer.optimize("input.png", "output.jpg")
    """

    def __init__(self, settings: Optional[OptimizationSettings] = None):
        """
        Initialize image optimizer.

        Args:
            settings: Optimization settings (uses defaults if not provided)
        """
        self.settings = settings or OptimizationSettings()

    def optimize(
        self,
        input_path: Path,
        output_path: Optional[Path] = None,
        settings: Optional[OptimizationSettings] = None,
    ) -> Path:
        """
        Optimize an image for reMarkable.

        Args:
            input_path: Path to input image
            output_path: Path for output (defaults to input_path with .jpg suffix)
            settings: Override settings for this operation

        Returns:
            Path to optimized image
        """
        input_path = Path(input_path)
        settings = settings or self.settings

        if not input_path.exists():
            raise FileNotFoundError(f"Image not found: {input_path}")

        # Default output path
        if output_path is None:
            output_path = input_path.with_suffix(".optimized.jpg")
        output_path = Path(output_path)

        logger.info(f"Optimizing image: {input_path.name}")

        # Open image
        img = Image.open(input_path)
        original_size = input_path.stat().st_size

        # Convert to RGB if necessary (for JPEG output)
        if img.mode in ("RGBA", "P"):
            # Create white background for transparency
            background = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "RGBA":
                background.paste(img, mask=img.split()[3])  # Use alpha channel as mask
            else:
                background.paste(img)
            img = background
        elif img.mode != "RGB":
            img = img.convert("RGB")

        # Get target dimensions
        target_width, target_height = settings.device.value

        # Resize if necessary
        img = self._resize_image(img, target_width, target_height, settings.maintain_aspect)

        # Convert to grayscale for e-ink
        if settings.grayscale:
            img = ImageOps.grayscale(img)
            img = img.convert("RGB")  # Convert back to RGB for saving

        # Enhance contrast
        if settings.contrast_factor != 1.0:
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(settings.contrast_factor)

        # Enhance sharpness
        if settings.sharpness_factor != 1.0:
            enhancer = ImageEnhance.Sharpness(img)
            img = enhancer.enhance(settings.sharpness_factor)

        # Apply dithering for photographs (reduces banding on e-ink)
        if settings.dither:
            img = self._apply_dithering(img)

        # Save with progressive quality reduction to meet file size target
        output_path = self._save_with_size_limit(
            img,
            output_path,
            settings.quality,
            settings.max_file_size_kb,
        )

        final_size = output_path.stat().st_size
        reduction = (1 - final_size / original_size) * 100 if original_size > 0 else 0

        logger.info(
            f"Optimized: {input_path.name} -> {output_path.name} "
            f"({original_size / 1024:.1f}KB -> {final_size / 1024:.1f}KB, "
            f"{reduction:.1f}% reduction)"
        )

        return output_path

    def _resize_image(
        self,
        img: Image.Image,
        target_width: int,
        target_height: int,
        maintain_aspect: bool,
    ) -> Image.Image:
        """
        Resize image to fit target dimensions.

        Args:
            img: PIL Image
            target_width: Target width in pixels
            target_height: Target height in pixels
            maintain_aspect: Whether to maintain aspect ratio

        Returns:
            Resized image
        """
        original_width, original_height = img.size

        # Check if resize is needed
        if original_width <= target_width and original_height <= target_height:
            return img

        if maintain_aspect:
            # Calculate scaling factor to fit within target
            width_ratio = target_width / original_width
            height_ratio = target_height / original_height
            scale = min(width_ratio, height_ratio)

            new_width = int(original_width * scale)
            new_height = int(original_height * scale)
        else:
            new_width = target_width
            new_height = target_height

        # Use high-quality resampling
        img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

        logger.debug(f"Resized: {original_width}x{original_height} -> {new_width}x{new_height}")
        return img

    def _apply_dithering(self, img: Image.Image) -> Image.Image:
        """
        Apply Floyd-Steinberg dithering for better e-ink rendering.

        Args:
            img: PIL Image (RGB)

        Returns:
            Dithered image
        """
        # Convert to grayscale first
        gray = img.convert("L")

        # Apply Floyd-Steinberg dithering to 16 levels (4-bit grayscale)
        # This matches reMarkable's display capabilities better
        dithered = gray.convert("P", palette=Image.Palette.ADAPTIVE, colors=16)
        dithered = dithered.convert("L")

        # Convert back to RGB
        return dithered.convert("RGB")

    def _save_with_size_limit(
        self,
        img: Image.Image,
        output_path: Path,
        initial_quality: int,
        max_size_kb: int,
    ) -> Path:
        """
        Save image with progressive quality reduction to meet size limit.

        Args:
            img: PIL Image
            output_path: Output path
            initial_quality: Starting JPEG quality
            max_size_kb: Maximum file size in KB

        Returns:
            Path to saved file
        """
        max_bytes = max_size_kb * 1024
        quality = initial_quality

        while quality >= 20:
            # Save to buffer first to check size
            buffer = BytesIO()
            img.save(buffer, "JPEG", quality=quality, optimize=True)
            size = buffer.tell()

            if size <= max_bytes:
                # Size is acceptable, save to file
                output_path.parent.mkdir(parents=True, exist_ok=True)
                with open(output_path, "wb") as f:
                    f.write(buffer.getvalue())
                logger.debug(f"Saved at quality {quality}: {size / 1024:.1f}KB")
                return output_path

            # Reduce quality and try again
            quality -= 10
            logger.debug(
                f"Size {size / 1024:.1f}KB > {max_size_kb}KB, reducing quality to {quality}"
            )

        # If we still can't meet the target, save at minimum quality
        logger.warning(
            f"Could not meet size target of {max_size_kb}KB, " f"saving at minimum quality (20)"
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(output_path, "JPEG", quality=20, optimize=True)
        return output_path

    def optimize_batch(
        self,
        input_paths: list[Path],
        output_dir: Path,
        settings: Optional[OptimizationSettings] = None,
    ) -> list[Path]:
        """
        Optimize multiple images.

        Args:
            input_paths: List of input image paths
            output_dir: Directory for optimized images
            settings: Override settings for this batch

        Returns:
            List of paths to optimized images
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        results = []
        for input_path in input_paths:
            input_path = Path(input_path)
            output_path = output_dir / f"{input_path.stem}.jpg"

            try:
                result = self.optimize(input_path, output_path, settings)
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to optimize {input_path}: {e}")

        logger.info(f"Optimized {len(results)}/{len(input_paths)} images")
        return results


def optimize_for_remarkable(
    input_path: Path,
    output_path: Optional[Path] = None,
    device: RemarkableDevice = RemarkableDevice.REMARKABLE_1,
    quality: int = 85,
) -> Path:
    """
    Convenience function to optimize a single image for reMarkable.

    Args:
        input_path: Path to input image
        output_path: Path for output (optional)
        device: Target reMarkable device
        quality: JPEG quality (1-100)

    Returns:
        Path to optimized image
    """
    settings = OptimizationSettings(device=device, quality=quality)
    optimizer = ImageOptimizer(settings)
    return optimizer.optimize(input_path, output_path)


# Example usage
if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.DEBUG)

    if len(sys.argv) > 1:
        input_path = Path(sys.argv[1])
        output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else None

        if input_path.exists():
            result = optimize_for_remarkable(input_path, output_path)
            print(f"Optimized image saved to: {result}")
        else:
            print(f"File not found: {input_path}")
    else:
        print("Usage: python image_optimizer.py <input_image> [output_image]")
