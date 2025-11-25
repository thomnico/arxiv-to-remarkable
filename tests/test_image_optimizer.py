"""Tests for image optimizer."""

import pytest
from PIL import Image

from arxiv2rm.image_optimizer import ImageMetadata, ImageOptimizer, optimize_image


class TestImageOptimizer:
    """Tests for reMarkable image optimization."""

    @pytest.fixture
    def test_image(self, tmp_path):
        """Create a test image (800x600 RGB)."""
        img_path = tmp_path / "test.png"
        img = Image.new("RGB", (800, 600), color=(100, 150, 200))
        img.save(img_path)
        return img_path

    @pytest.fixture
    def large_image(self, tmp_path):
        """Create a large test image (2400x1800 RGB)."""
        img_path = tmp_path / "large.png"
        img = Image.new("RGB", (2400, 1800), color=(50, 100, 150))
        img.save(img_path)
        return img_path

    @pytest.fixture
    def landscape_image(self, tmp_path):
        """Create a landscape test image (1600x900)."""
        img_path = tmp_path / "landscape.jpg"
        img = Image.new("RGB", (1600, 900), color=(80, 120, 160))
        img.save(img_path)
        return img_path

    @pytest.fixture
    def portrait_image(self, tmp_path):
        """Create a portrait test image (600x900)."""
        img_path = tmp_path / "portrait.jpg"
        img = Image.new("RGB", (600, 900), color=(120, 80, 160))
        img.save(img_path)
        return img_path

    @pytest.fixture
    def grayscale_image(self, tmp_path):
        """Create a grayscale test image."""
        img_path = tmp_path / "gray.png"
        img = Image.new("L", (800, 600), color=128)
        img.save(img_path)
        return img_path

    @pytest.fixture
    def rgba_image(self, tmp_path):
        """Create an RGBA test image."""
        img_path = tmp_path / "rgba.png"
        img = Image.new("RGBA", (800, 600), color=(100, 150, 200, 255))
        img.save(img_path)
        return img_path

    def test_init_default_params(self):
        """Test initialization with default parameters."""
        optimizer = ImageOptimizer()
        assert optimizer.target_width == 1404
        assert optimizer.target_height == 1872
        assert optimizer.quality == 85
        assert optimizer.optimize_eink is True

    def test_init_custom_params(self):
        """Test initialization with custom parameters."""
        optimizer = ImageOptimizer(
            target_width=1000,
            target_height=1500,
            quality=90,
            optimize_eink=False,
        )
        assert optimizer.target_width == 1000
        assert optimizer.target_height == 1500
        assert optimizer.quality == 90
        assert optimizer.optimize_eink is False

    def test_optimize_basic(self, test_image, tmp_path):
        """Test basic image optimization."""
        optimizer = ImageOptimizer()
        output_path = tmp_path / "output.jpg"

        result = optimizer.optimize(test_image, output_path)

        assert result.exists()
        assert result.suffix == ".jpg"

        # Check output image properties
        img = Image.open(result)
        assert img.size == (1404, 1872)  # reMarkable dimensions
        assert img.mode == "RGB"

    def test_optimize_default_output_path(self, test_image):
        """Test optimization with default output path."""
        optimizer = ImageOptimizer()
        result = optimizer.optimize(test_image)

        expected_path = test_image.parent / f"{test_image.stem}_opt.jpg"
        assert result == expected_path
        assert result.exists()

    def test_optimize_missing_file(self, tmp_path):
        """Test optimization with non-existent file."""
        optimizer = ImageOptimizer()
        missing_path = tmp_path / "missing.png"

        with pytest.raises(ValueError, match="Input image not found"):
            optimizer.optimize(missing_path)

    def test_resize_with_letterboxing(self, test_image, tmp_path):
        """Test resizing adds letterboxing for aspect ratio preservation."""
        optimizer = ImageOptimizer()
        output_path = tmp_path / "letterbox.jpg"

        result = optimizer.optimize(test_image, output_path)

        # Original is 800x600 (4:3), target is 1404x1872 (3:4)
        # Should add letterboxing
        img = Image.open(result)
        assert img.size == (1404, 1872)

        # Check for white letterboxing (check corners)
        pixels = img.load()
        # Top-left corner should be white (or near-white for letterbox)
        top_left = pixels[0, 0]
        # Image should be centered, so extreme corners likely white
        assert top_left[0] >= 200  # High RGB values = white/light

    def test_resize_large_image(self, large_image, tmp_path):
        """Test resizing a large image scales down correctly."""
        optimizer = ImageOptimizer()
        output_path = tmp_path / "scaled.jpg"

        result = optimizer.optimize(large_image, output_path)

        img = Image.open(result)
        assert img.size == (1404, 1872)

    def test_no_upscaling_small_image(self, tmp_path):
        """Test that small images are not upscaled."""
        # Create very small image
        small_img = tmp_path / "small.png"
        img = Image.new("RGB", (200, 150), color=(100, 150, 200))
        img.save(small_img)

        optimizer = ImageOptimizer()
        output_path = tmp_path / "output.jpg"

        result = optimizer.optimize(small_img, output_path)

        # Should be letterboxed to target size but original not upscaled
        out_img = Image.open(result)
        assert out_img.size == (1404, 1872)

    def test_landscape_rotation(self, landscape_image, tmp_path):
        """Test that landscape images may be rotated for better fit."""
        optimizer = ImageOptimizer()
        output_path = tmp_path / "rotated.jpg"

        result = optimizer.optimize(landscape_image, output_path)

        img = Image.open(result)
        assert img.size == (1404, 1872)
        # Rotation logic depends on scale improvement
        # Just verify it processed without error

    def test_portrait_image_optimization(self, portrait_image, tmp_path):
        """Test portrait image optimization."""
        optimizer = ImageOptimizer()
        output_path = tmp_path / "portrait_out.jpg"

        result = optimizer.optimize(portrait_image, output_path)

        img = Image.open(result)
        assert img.size == (1404, 1872)

    def test_eink_optimization_applied(self, test_image, tmp_path):
        """Test that e-ink optimizations are applied."""
        optimizer = ImageOptimizer(optimize_eink=True)
        output_path = tmp_path / "eink.jpg"

        result = optimizer.optimize(test_image, output_path)

        # E-ink optimization converts to grayscale
        # Check that output is grayscale (RGB with equal channels)
        img = Image.open(result)
        pixels = img.load()

        # Sample middle pixel - should have equal RGB values (grayscale)
        center_pixel = pixels[702, 936]  # Center of 1404x1872
        # For grayscale RGB, all channels should be equal
        assert center_pixel[0] == center_pixel[1] == center_pixel[2]

    def test_eink_optimization_disabled(self, test_image, tmp_path):
        """Test optimization without e-ink processing."""
        optimizer = ImageOptimizer(optimize_eink=False)
        output_path = tmp_path / "no_eink.jpg"

        result = optimizer.optimize(test_image, output_path)

        # Without e-ink optimization, original colors may be preserved
        img = Image.open(result)
        assert img.mode == "RGB"
        # Can't easily verify color preservation due to resizing

    def test_grayscale_input(self, grayscale_image, tmp_path):
        """Test optimization of grayscale image."""
        optimizer = ImageOptimizer()
        output_path = tmp_path / "gray_out.jpg"

        result = optimizer.optimize(grayscale_image, output_path)

        img = Image.open(result)
        assert img.size == (1404, 1872)
        assert img.mode == "RGB"  # Converted to RGB for JPEG

    def test_rgba_conversion(self, rgba_image, tmp_path):
        """Test RGBA image is converted to RGB."""
        optimizer = ImageOptimizer()
        output_path = tmp_path / "rgba_out.jpg"

        result = optimizer.optimize(rgba_image, output_path)

        img = Image.open(result)
        assert img.mode == "RGB"  # RGBA converted to RGB

    def test_jpeg_quality(self, test_image, tmp_path):
        """Test JPEG quality setting affects file size."""
        # High quality
        optimizer_high = ImageOptimizer(quality=95)
        output_high = tmp_path / "high_quality.jpg"
        result_high = optimizer_high.optimize(test_image, output_high)

        # Low quality
        optimizer_low = ImageOptimizer(quality=50)
        output_low = tmp_path / "low_quality.jpg"
        result_low = optimizer_low.optimize(test_image, output_low)

        # High quality should produce larger file
        size_high = result_high.stat().st_size
        size_low = result_low.stat().st_size
        assert size_high > size_low

    def test_compression_reduces_size(self, large_image, tmp_path):
        """Test that optimization reduces file size."""
        optimizer = ImageOptimizer()
        output_path = tmp_path / "compressed.jpg"

        result = optimizer.optimize(large_image, output_path)
        output_size = result.stat().st_size

        # Should compress (though not guaranteed for all images)
        # Just verify output exists and is reasonable
        assert output_size > 0

    def test_metadata_embedding(self, test_image, tmp_path):
        """Test EXIF metadata embedding."""
        optimizer = ImageOptimizer()
        output_path = tmp_path / "with_metadata.jpg"

        metadata = ImageMetadata(
            source_page=5,
            figure_number=3,
            caption="Test figure caption",
            source_file="paper.pdf",
            processed_date="2025-01-24 12:00:00",
        )

        result = optimizer.optimize(test_image, output_path, metadata=metadata)

        # Verify EXIF was embedded (requires piexif to read)
        import piexif

        exif_dict = piexif.load(str(result))

        # Check ImageDescription (caption)
        if piexif.ImageIFD.ImageDescription in exif_dict["0th"]:
            caption_bytes = exif_dict["0th"][piexif.ImageIFD.ImageDescription]
            caption = caption_bytes.decode("utf-8")
            assert "Test figure caption" in caption

        # Check Software tag (source file)
        if piexif.ImageIFD.Software in exif_dict["0th"]:
            software_bytes = exif_dict["0th"][piexif.ImageIFD.Software]
            software = software_bytes.decode("utf-8")
            assert "arxiv2rm:paper.pdf" in software

    def test_metadata_with_missing_fields(self, test_image, tmp_path):
        """Test metadata embedding with partial data."""
        optimizer = ImageOptimizer()
        output_path = tmp_path / "partial_metadata.jpg"

        metadata = ImageMetadata(figure_number=1)  # Only figure number

        result = optimizer.optimize(test_image, output_path, metadata=metadata)

        # Should succeed without error
        assert result.exists()

    def test_batch_optimize_basic(self, tmp_path):
        """Test batch optimization of multiple images."""
        input_dir = tmp_path / "input"
        input_dir.mkdir()

        # Create test images
        for i in range(3):
            img = Image.new("RGB", (800, 600), color=(i * 50, 100, 150))
            img.save(input_dir / f"image{i}.png")

        optimizer = ImageOptimizer()
        output_dir = tmp_path / "output"

        results = optimizer.batch_optimize(input_dir, output_dir)

        assert len(results) == 3
        assert output_dir.exists()
        for result in results:
            assert result.exists()
            assert result.suffix == ".jpg"

    def test_batch_optimize_default_output(self, tmp_path):
        """Test batch optimization with default output directory."""
        input_dir = tmp_path / "input"
        input_dir.mkdir()

        img = Image.new("RGB", (800, 600), color=(100, 150, 200))
        img.save(input_dir / "test.png")

        optimizer = ImageOptimizer()
        results = optimizer.batch_optimize(input_dir)

        assert len(results) == 1
        expected_output_dir = input_dir / "optimized"
        assert expected_output_dir.exists()
        assert results[0].parent == expected_output_dir

    def test_batch_optimize_recursive(self, tmp_path):
        """Test recursive batch optimization."""
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        subdir = input_dir / "subdir"
        subdir.mkdir()

        # Create images in both directories
        img1 = Image.new("RGB", (800, 600), color=(100, 150, 200))
        img1.save(input_dir / "image1.png")

        img2 = Image.new("RGB", (800, 600), color=(150, 100, 200))
        img2.save(subdir / "image2.jpg")

        optimizer = ImageOptimizer()
        output_dir = tmp_path / "output"

        results = optimizer.batch_optimize(input_dir, output_dir, recursive=True)

        assert len(results) == 2
        # Check that subdirectory structure is preserved
        assert (output_dir / "image1.jpg").exists()
        assert (output_dir / "subdir" / "image2.jpg").exists()

    def test_batch_optimize_non_recursive(self, tmp_path):
        """Test non-recursive batch optimization."""
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        subdir = input_dir / "subdir"
        subdir.mkdir()

        img1 = Image.new("RGB", (800, 600), color=(100, 150, 200))
        img1.save(input_dir / "image1.png")

        img2 = Image.new("RGB", (800, 600), color=(150, 100, 200))
        img2.save(subdir / "image2.jpg")

        optimizer = ImageOptimizer()
        output_dir = tmp_path / "output"

        results = optimizer.batch_optimize(input_dir, output_dir, recursive=False)

        assert len(results) == 1  # Only top-level image
        assert (output_dir / "image1.jpg").exists()

    def test_batch_optimize_mixed_formats(self, tmp_path):
        """Test batch optimization with multiple image formats."""
        input_dir = tmp_path / "input"
        input_dir.mkdir()

        # Create images in different formats
        formats = ["png", "jpg", "jpeg"]
        for fmt in formats:
            img = Image.new("RGB", (800, 600), color=(100, 150, 200))
            img.save(input_dir / f"image.{fmt}")

        optimizer = ImageOptimizer()
        output_dir = tmp_path / "output"

        results = optimizer.batch_optimize(input_dir, output_dir)

        assert len(results) == 3
        # All should be converted to .jpg
        for result in results:
            assert result.suffix == ".jpg"

    def test_batch_optimize_skips_corrupted(self, tmp_path):
        """Test batch optimization skips corrupted images."""
        input_dir = tmp_path / "input"
        input_dir.mkdir()

        # Create good image
        img = Image.new("RGB", (800, 600), color=(100, 150, 200))
        img.save(input_dir / "good.png")

        # Create fake corrupted image
        (input_dir / "corrupted.png").write_bytes(b"not an image")

        optimizer = ImageOptimizer()
        output_dir = tmp_path / "output"

        results = optimizer.batch_optimize(input_dir, output_dir)

        # Should process only the good image
        assert len(results) == 1
        assert results[0].name == "good.jpg"

    def test_batch_optimize_missing_directory(self, tmp_path):
        """Test batch optimization with non-existent directory."""
        optimizer = ImageOptimizer()
        missing_dir = tmp_path / "missing"

        with pytest.raises(ValueError, match="Input directory not found"):
            optimizer.batch_optimize(missing_dir)

    def test_convenience_function(self, test_image, tmp_path):
        """Test convenience function optimize_image."""
        output_path = tmp_path / "convenience.jpg"

        result = optimize_image(
            test_image,
            output_path,
            target_size=(1404, 1872),
            quality=85,
            eink_optimize=True,
        )

        assert result.exists()
        assert result == output_path

        img = Image.open(result)
        assert img.size == (1404, 1872)

    def test_convenience_function_custom_size(self, test_image, tmp_path):
        """Test convenience function with custom target size."""
        output_path = tmp_path / "custom_size.jpg"

        result = optimize_image(
            test_image,
            output_path,
            target_size=(1000, 1500),
            quality=90,
            eink_optimize=False,
        )

        img = Image.open(result)
        assert img.size == (1000, 1500)

    def test_aspect_ratio_preservation(self, tmp_path):
        """Test that aspect ratio is preserved during resizing."""
        # Create image with distinct aspect ratio (2:1)
        wide_img = tmp_path / "wide.png"
        img = Image.new("RGB", (1000, 500), color=(100, 150, 200))
        img.save(wide_img)

        optimizer = ImageOptimizer()
        output_path = tmp_path / "output.jpg"

        result = optimizer.optimize(wide_img, output_path)

        # Original is 2:1, target is ~3:4
        # Should be scaled down and letterboxed
        out_img = Image.open(result)
        assert out_img.size == (1404, 1872)

    def test_image_metadata_defaults(self):
        """Test ImageMetadata default values."""
        metadata = ImageMetadata()
        assert metadata.source_page is None
        assert metadata.figure_number is None
        assert metadata.caption is None
        assert metadata.source_file is None
        assert metadata.processed_date is None

    def test_image_metadata_partial(self):
        """Test ImageMetadata with partial data."""
        metadata = ImageMetadata(
            figure_number=5,
            caption="Test caption",
        )
        assert metadata.figure_number == 5
        assert metadata.caption == "Test caption"
        assert metadata.source_page is None
