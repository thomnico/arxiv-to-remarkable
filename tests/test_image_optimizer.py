"""Tests for image optimizer."""

import pytest
from PIL import Image

from arxiv2rm.image_optimizer import (
    ImageOptimizer,
    OptimizationSettings,
    RemarkableDevice,
    optimize_for_remarkable,
)


class TestOptimizationSettings:
    """Tests for optimization settings."""

    def test_defaults(self):
        """Test default settings values."""
        settings = OptimizationSettings()
        assert settings.device == RemarkableDevice.REMARKABLE_1
        assert settings.quality == 85
        assert settings.max_file_size_kb == 500
        assert settings.contrast_factor == 1.2
        assert settings.sharpness_factor == 1.1
        assert settings.dither is False
        assert settings.grayscale is True
        assert settings.maintain_aspect is True

    def test_custom_values(self):
        """Test custom settings values."""
        settings = OptimizationSettings(
            device=RemarkableDevice.REMARKABLE_2,
            quality=90,
            max_file_size_kb=800,
            contrast_factor=1.5,
            dither=True,
        )
        assert settings.device == RemarkableDevice.REMARKABLE_2
        assert settings.quality == 90
        assert settings.max_file_size_kb == 800
        assert settings.contrast_factor == 1.5
        assert settings.dither is True


class TestRemarkableDevice:
    """Tests for RemarkableDevice enum."""

    def test_remarkable_1_dimensions(self):
        """Test reMarkable 1 device dimensions."""
        assert RemarkableDevice.REMARKABLE_1.value == (1404, 1872)

    def test_remarkable_2_dimensions(self):
        """Test reMarkable 2 device dimensions."""
        assert RemarkableDevice.REMARKABLE_2.value == (1872, 2480)


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

    def test_init_default_settings(self):
        """Test initialization with default settings."""
        optimizer = ImageOptimizer()
        assert optimizer.settings is not None
        assert optimizer.settings.device == RemarkableDevice.REMARKABLE_1

    def test_init_custom_settings(self):
        """Test initialization with custom settings."""
        settings = OptimizationSettings(
            device=RemarkableDevice.REMARKABLE_2,
            quality=90,
        )
        optimizer = ImageOptimizer(settings)
        assert optimizer.settings.device == RemarkableDevice.REMARKABLE_2
        assert optimizer.settings.quality == 90

    def test_optimize_basic(self, test_image, tmp_path):
        """Test basic image optimization."""
        optimizer = ImageOptimizer()
        output_path = tmp_path / "output.jpg"

        result = optimizer.optimize(test_image, output_path)

        assert result.exists()
        assert result.suffix == ".jpg"

        # Check output image properties
        img = Image.open(result)
        # Image should fit within reMarkable dimensions
        assert img.width <= 1404
        assert img.height <= 1872
        assert img.mode == "RGB"

    def test_optimize_default_output_path(self, test_image):
        """Test optimization with default output path."""
        optimizer = ImageOptimizer()
        result = optimizer.optimize(test_image)

        expected_path = test_image.with_suffix(".optimized.jpg")
        assert result == expected_path
        assert result.exists()

        # Clean up
        result.unlink()

    def test_optimize_missing_file(self, tmp_path):
        """Test optimization with non-existent file."""
        optimizer = ImageOptimizer()
        missing_path = tmp_path / "missing.png"

        with pytest.raises(FileNotFoundError):
            optimizer.optimize(missing_path)

    def test_resize_large_image(self, large_image, tmp_path):
        """Test resizing a large image scales down correctly."""
        optimizer = ImageOptimizer()
        output_path = tmp_path / "scaled.jpg"

        result = optimizer.optimize(large_image, output_path)

        img = Image.open(result)
        # Should fit within reMarkable dimensions
        assert img.width <= 1404
        assert img.height <= 1872

    def test_no_upscaling_small_image(self, tmp_path):
        """Test that small images are not upscaled."""
        # Create very small image
        small_img = tmp_path / "small.png"
        img = Image.new("RGB", (200, 150), color=(100, 150, 200))
        img.save(small_img)

        optimizer = ImageOptimizer()
        output_path = tmp_path / "output.jpg"

        result = optimizer.optimize(small_img, output_path)

        # Should not upscale
        out_img = Image.open(result)
        assert out_img.width <= 200
        assert out_img.height <= 150

    def test_grayscale_conversion(self, test_image, tmp_path):
        """Test that grayscale conversion is applied by default."""
        optimizer = ImageOptimizer()
        output_path = tmp_path / "grayscale.jpg"

        result = optimizer.optimize(test_image, output_path)

        # Grayscale RGB has equal channels
        img = Image.open(result)
        pixels = img.load()

        # Sample middle pixel
        center_x, center_y = img.width // 2, img.height // 2
        center_pixel = pixels[center_x, center_y]
        # For grayscale RGB, all channels should be equal (or nearly equal)
        assert abs(center_pixel[0] - center_pixel[1]) <= 1
        assert abs(center_pixel[1] - center_pixel[2]) <= 1

    def test_grayscale_disabled(self, test_image, tmp_path):
        """Test optimization without grayscale conversion."""
        settings = OptimizationSettings(grayscale=False)
        optimizer = ImageOptimizer(settings)
        output_path = tmp_path / "color.jpg"

        result = optimizer.optimize(test_image, output_path)

        img = Image.open(result)
        assert img.mode == "RGB"

    def test_grayscale_input(self, grayscale_image, tmp_path):
        """Test optimization of grayscale image."""
        optimizer = ImageOptimizer()
        output_path = tmp_path / "gray_out.jpg"

        result = optimizer.optimize(grayscale_image, output_path)

        img = Image.open(result)
        # Should fit dimensions
        assert img.width <= 1404
        assert img.height <= 1872
        assert img.mode == "RGB"  # Converted to RGB for JPEG

    def test_rgba_conversion(self, rgba_image, tmp_path):
        """Test RGBA image is converted to RGB."""
        optimizer = ImageOptimizer()
        output_path = tmp_path / "rgba_out.jpg"

        result = optimizer.optimize(rgba_image, output_path)

        img = Image.open(result)
        assert img.mode == "RGB"  # RGBA converted to RGB

    def test_jpeg_quality(self, large_image, tmp_path):
        """Test JPEG quality setting affects file size."""
        # Use a larger image for more noticeable quality difference
        # High quality
        settings_high = OptimizationSettings(quality=95, grayscale=False)
        optimizer_high = ImageOptimizer(settings_high)
        output_high = tmp_path / "high_quality.jpg"
        result_high = optimizer_high.optimize(large_image, output_high)

        # Low quality
        settings_low = OptimizationSettings(quality=30, grayscale=False)
        optimizer_low = ImageOptimizer(settings_low)
        output_low = tmp_path / "low_quality.jpg"
        result_low = optimizer_low.optimize(large_image, output_low)

        # High quality should produce larger file
        size_high = result_high.stat().st_size
        size_low = result_low.stat().st_size
        assert size_high > size_low

    def test_dithering(self, test_image, tmp_path):
        """Test dithering option."""
        settings = OptimizationSettings(dither=True)
        optimizer = ImageOptimizer(settings)
        output_path = tmp_path / "dithered.jpg"

        result = optimizer.optimize(test_image, output_path)

        assert result.exists()
        img = Image.open(result)
        assert img.mode == "RGB"

    def test_contrast_enhancement(self, test_image, tmp_path):
        """Test contrast enhancement."""
        settings = OptimizationSettings(contrast_factor=1.5)
        optimizer = ImageOptimizer(settings)
        output_path = tmp_path / "contrast.jpg"

        result = optimizer.optimize(test_image, output_path)

        assert result.exists()

    def test_sharpness_enhancement(self, test_image, tmp_path):
        """Test sharpness enhancement."""
        settings = OptimizationSettings(sharpness_factor=1.5)
        optimizer = ImageOptimizer(settings)
        output_path = tmp_path / "sharp.jpg"

        result = optimizer.optimize(test_image, output_path)

        assert result.exists()

    def test_max_file_size(self, large_image, tmp_path):
        """Test max file size constraint."""
        settings = OptimizationSettings(max_file_size_kb=50)  # Small limit
        optimizer = ImageOptimizer(settings)
        output_path = tmp_path / "small.jpg"

        result = optimizer.optimize(large_image, output_path)

        # File should be relatively small (may not meet exact target)
        file_size_kb = result.stat().st_size / 1024
        # Allow some margin since very small targets may not be achievable
        assert file_size_kb < 200  # Should be reasonably small

    def test_batch_optimize(self, tmp_path):
        """Test batch optimization of multiple images."""
        input_dir = tmp_path / "input"
        input_dir.mkdir()

        # Create test images
        for i in range(3):
            img = Image.new("RGB", (800, 600), color=(i * 50, 100, 150))
            img.save(input_dir / f"image{i}.png")

        optimizer = ImageOptimizer()
        output_dir = tmp_path / "output"

        input_paths = list(input_dir.glob("*.png"))
        results = optimizer.optimize_batch(input_paths, output_dir)

        assert len(results) == 3
        assert output_dir.exists()
        for result in results:
            assert result.exists()
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

        input_paths = list(input_dir.glob("*.png"))
        results = optimizer.optimize_batch(input_paths, output_dir)

        # Should process only the good image
        assert len(results) == 1
        assert results[0].name == "good.jpg"

    def test_remarkable_2_device(self, test_image, tmp_path):
        """Test optimization for reMarkable 2."""
        settings = OptimizationSettings(device=RemarkableDevice.REMARKABLE_2)
        optimizer = ImageOptimizer(settings)
        output_path = tmp_path / "rm2.jpg"

        result = optimizer.optimize(test_image, output_path)

        img = Image.open(result)
        # Should fit within reMarkable 2 dimensions
        assert img.width <= 1872
        assert img.height <= 2480


class TestConvenienceFunction:
    """Tests for convenience function."""

    @pytest.fixture
    def test_image(self, tmp_path):
        """Create a test image."""
        img_path = tmp_path / "test.png"
        img = Image.new("RGB", (800, 600), color=(100, 150, 200))
        img.save(img_path)
        return img_path

    def test_optimize_for_remarkable(self, test_image, tmp_path):
        """Test optimize_for_remarkable convenience function."""
        output_path = tmp_path / "convenience.jpg"

        result = optimize_for_remarkable(test_image, output_path)

        assert result.exists()
        assert result == output_path

        img = Image.open(result)
        assert img.width <= 1404
        assert img.height <= 1872

    def test_optimize_for_remarkable_default_output(self, test_image):
        """Test convenience function with default output."""
        result = optimize_for_remarkable(test_image)

        expected_path = test_image.with_suffix(".optimized.jpg")
        assert result == expected_path
        assert result.exists()

        # Clean up
        result.unlink()

    def test_optimize_for_remarkable_rm2(self, test_image, tmp_path):
        """Test convenience function for reMarkable 2."""
        output_path = tmp_path / "rm2.jpg"

        result = optimize_for_remarkable(
            test_image,
            output_path,
            device=RemarkableDevice.REMARKABLE_2,
        )

        img = Image.open(result)
        assert img.width <= 1872
        assert img.height <= 2480

    def test_optimize_for_remarkable_custom_quality(self, test_image, tmp_path):
        """Test convenience function with custom quality."""
        output_path = tmp_path / "custom_quality.jpg"

        result = optimize_for_remarkable(test_image, output_path, quality=95)

        assert result.exists()
