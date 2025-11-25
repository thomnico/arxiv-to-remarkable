"""Image optimization for reMarkable e-ink display."""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

import cv2
import numpy as np
import piexif
from PIL import Image

logger = logging.getLogger(__name__)


@dataclass
class ImageMetadata:
    """Metadata to embed in optimized images."""

    source_page: Optional[int] = None
    figure_number: Optional[int] = None
    caption: Optional[str] = None
    source_file: Optional[str] = None
    processed_date: Optional[str] = None


class ImageOptimizer:
    """Optimize images for reMarkable e-ink display."""

    # reMarkable 1 display resolution (portrait)
    REMARKABLE_WIDTH = 1404
    REMARKABLE_HEIGHT = 1872

    # reMarkable 2 has same resolution
    # Target dimensions for optimization
    TARGET_WIDTH = REMARKABLE_WIDTH
    TARGET_HEIGHT = REMARKABLE_HEIGHT

    def __init__(
        self,
        target_width: int = TARGET_WIDTH,
        target_height: int = TARGET_HEIGHT,
        quality: int = 85,
        optimize_eink: bool = True,
    ):
        """
        Initialize image optimizer.

        Args:
            target_width: Target width in pixels (default: 1404 for reMarkable)
            target_height: Target height in pixels (default: 1872 for reMarkable)
            quality: JPEG quality 1-100 (default: 85)
            optimize_eink: Apply e-ink optimizations (default: True)
        """
        self.target_width = target_width
        self.target_height = target_height
        self.quality = quality
        self.optimize_eink = optimize_eink
        logger.info(
            f"ImageOptimizer initialized: {target_width}×{target_height}, "
            f"quality={quality}, e-ink={optimize_eink}"
        )

    def optimize(
        self,
        input_path: Path,
        output_path: Optional[Path] = None,
        metadata: Optional[ImageMetadata] = None,
    ) -> Path:
        """
        Optimize image for reMarkable display.

        Args:
            input_path: Path to input image
            output_path: Path to save optimized image (default: input_path with _opt suffix)
            metadata: Optional metadata to embed in EXIF

        Returns:
            Path to optimized image

        Raises:
            ValueError: If image cannot be processed
        """
        if not input_path.exists():
            raise ValueError(f"Input image not found: {input_path}")

        # Default output path
        if output_path is None:
            output_path = input_path.parent / f"{input_path.stem}_opt.jpg"

        logger.info(f"Optimizing {input_path.name} → {output_path.name}")

        try:
            # Load image
            img = Image.open(input_path)
            logger.debug(f"Loaded image: {img.size} ({img.mode})")

            # Convert to RGB if needed
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
                logger.debug("Converted to RGB mode")

            # Resize with aspect ratio preservation
            img = self._resize_image(img)

            # Apply e-ink optimizations
            if self.optimize_eink:
                img = self._optimize_for_eink(img)

            # Save with EXIF metadata
            save_kwargs = {
                "format": "JPEG",
                "quality": self.quality,
                "optimize": True,
            }

            if metadata:
                exif_bytes = self._create_exif(metadata)
                if exif_bytes:  # Only add exif if not empty
                    save_kwargs["exif"] = exif_bytes

            img.save(output_path, **save_kwargs)

            # Log results
            input_size = input_path.stat().st_size
            output_size = output_path.stat().st_size
            compression_ratio = (1 - output_size / input_size) * 100
            logger.info(
                f"Saved: {output_size // 1024}KB "
                f"(was {input_size // 1024}KB, {compression_ratio:.1f}% reduction)"
            )

            return output_path

        except Exception as e:
            logger.error(f"Failed to optimize {input_path}: {e}")
            raise ValueError(f"Image optimization failed: {e}") from e

    def _resize_image(self, img: Image.Image) -> Image.Image:
        """
        Resize image to target dimensions with aspect ratio preservation.

        Uses letterboxing (white borders) if needed.

        Args:
            img: PIL Image

        Returns:
            Resized PIL Image
        """
        orig_width, orig_height = img.size
        logger.debug(f"Original size: {orig_width}×{orig_height}")

        # Check if image is landscape and should be rotated
        if orig_width > orig_height and self.target_height > self.target_width:
            # Landscape image for portrait display - consider rotating
            # Calculate fit both ways
            portrait_scale = min(self.target_width / orig_width, self.target_height / orig_height)
            landscape_scale = min(self.target_height / orig_width, self.target_width / orig_height)

            # Use rotation if it gives better fit
            if landscape_scale > portrait_scale:
                img = img.rotate(90, expand=True)
                orig_width, orig_height = img.size
                logger.debug("Rotated landscape image to portrait")

        # Calculate scaling to fit within target dimensions
        scale = min(self.target_width / orig_width, self.target_height / orig_height)

        # Don't upscale small images
        if scale > 1.0:
            scale = 1.0

        new_width = int(orig_width * scale)
        new_height = int(orig_height * scale)

        logger.debug(f"Scaled size: {new_width}×{new_height} (scale={scale:.2f})")

        # Resize with high-quality resampling
        img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

        # Add letterboxing if needed
        if new_width < self.target_width or new_height < self.target_height:
            # Create white background
            background = Image.new("RGB", (self.target_width, self.target_height), "white")

            # Center the image
            x_offset = (self.target_width - new_width) // 2
            y_offset = (self.target_height - new_height) // 2

            background.paste(img, (x_offset, y_offset))
            logger.debug(f"Added letterboxing: offsets=({x_offset}, {y_offset})")

            return background

        return img

    def _optimize_for_eink(self, img: Image.Image) -> Image.Image:
        """
        Apply e-ink display optimizations.

        - Convert to grayscale
        - Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)
        - Optional dithering (currently disabled)

        Args:
            img: PIL Image (RGB)

        Returns:
            Optimized PIL Image
        """
        logger.debug("Applying e-ink optimizations")

        # Convert PIL to numpy array for OpenCV
        img_array = np.array(img)

        # Convert to grayscale
        if len(img_array.shape) == 3:
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        else:
            gray = img_array

        # Apply CLAHE for contrast enhancement
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)

        logger.debug("Applied CLAHE contrast enhancement")

        # Convert back to RGB for consistency (JPEG needs RGB)
        enhanced_rgb = cv2.cvtColor(enhanced, cv2.COLOR_GRAY2RGB)

        # Convert back to PIL
        return Image.fromarray(enhanced_rgb)

    def _create_exif(self, metadata: ImageMetadata) -> bytes:
        """
        Create EXIF metadata bytes.

        Args:
            metadata: ImageMetadata to embed

        Returns:
            EXIF bytes for piexif
        """
        exif_dict = {"0th": {}, "Exif": {}, "1st": {}}

        # ImageDescription (caption)
        if metadata.caption:
            exif_dict["0th"][piexif.ImageIFD.ImageDescription] = metadata.caption.encode("utf-8")[
                :255
            ]  # Max 255 bytes

        # Software tag for source tracking
        if metadata.source_file:
            exif_dict["0th"][piexif.ImageIFD.Software] = f"arxiv2rm:{metadata.source_file}".encode(
                "utf-8"
            )

        # UserComment for figure number
        if metadata.figure_number:
            comment = f"Figure {metadata.figure_number}"
            if metadata.source_page:
                comment += f" (page {metadata.source_page})"
            exif_dict["Exif"][piexif.ExifIFD.UserComment] = comment.encode("utf-8")

        # DateTime
        if metadata.processed_date:
            exif_dict["0th"][piexif.ImageIFD.DateTime] = metadata.processed_date.encode("ascii")

        try:
            return piexif.dump(exif_dict)
        except Exception as e:
            logger.warning(f"Failed to create EXIF: {e}")
            return b""

    def batch_optimize(
        self,
        input_dir: Path,
        output_dir: Optional[Path] = None,
        recursive: bool = True,
    ) -> list[Path]:
        """
        Optimize all images in a directory.

        Args:
            input_dir: Directory containing images
            output_dir: Output directory (default: input_dir/optimized)
            recursive: Process subdirectories (default: True)

        Returns:
            List of paths to optimized images
        """
        if not input_dir.exists():
            raise ValueError(f"Input directory not found: {input_dir}")

        if output_dir is None:
            output_dir = input_dir / "optimized"

        output_dir.mkdir(parents=True, exist_ok=True)

        # Supported image formats
        patterns = ["*.png", "*.jpg", "*.jpeg", "*.pdf", "*.eps"]

        input_images = []
        for pattern in patterns:
            if recursive:
                input_images.extend(input_dir.rglob(pattern))
            else:
                input_images.extend(input_dir.glob(pattern))

        logger.info(f"Found {len(input_images)} images to optimize")

        optimized = []
        for img_path in input_images:
            try:
                # Preserve relative directory structure
                rel_path = img_path.relative_to(input_dir)
                out_path = output_dir / rel_path.with_suffix(".jpg")
                out_path.parent.mkdir(parents=True, exist_ok=True)

                result = self.optimize(img_path, out_path)
                optimized.append(result)
            except Exception as e:
                logger.warning(f"Skipped {img_path.name}: {e}")

        logger.info(f"Successfully optimized {len(optimized)}/{len(input_images)} images")
        return optimized


def optimize_image(
    input_path: Path,
    output_path: Optional[Path] = None,
    target_size: Tuple[int, int] = (1404, 1872),
    quality: int = 85,
    eink_optimize: bool = True,
) -> Path:
    """
    Convenience function to optimize a single image.

    Args:
        input_path: Path to input image
        output_path: Path to save output (default: input_path_opt.jpg)
        target_size: Target dimensions (width, height)
        quality: JPEG quality 1-100
        eink_optimize: Apply e-ink optimizations

    Returns:
        Path to optimized image
    """
    optimizer = ImageOptimizer(
        target_width=target_size[0],
        target_height=target_size[1],
        quality=quality,
        optimize_eink=eink_optimize,
    )
    return optimizer.optimize(input_path, output_path)
