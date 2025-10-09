from __future__ import annotations
import numpy as np
from copy import deepcopy
from pathlib import Path
from dataclasses import dataclass
from PIL import Image

from bencher.results.composable_container.composable_container_base import (
    ComposableContainerBase,
    ComposeType,
)
from bencher.utils import gen_image_path


@dataclass()
class ImageRenderCfg:
    """Configuration class for image composition and rendering options.

    This class controls how multiple images are composed and rendered together.
    It provides options for layout, appearance, and labeling of the output.

    Attributes:
        compose_method (ComposeType): Method to compose multiple images (right, down, overlay).
            Defaults to ComposeType.right. Note: sequence is not supported for static images.
        var_name (str, optional): Variable name for labeling. Defaults to None.
        var_value (str, optional): Variable value for labeling. Defaults to None.
        background_col (tuple[int, int, int]): RGB color for background. Defaults to white (255, 255, 255).
        margin (int): Margin size in pixels to add around images. Defaults to 0.
        equal_size (bool): If True, resizes all images to match the largest dimensions. Defaults to True.
    """

    compose_method: ComposeType = ComposeType.right
    var_name: str = None
    var_value: str = None
    background_col: tuple[int, int, int] = (255, 255, 255)
    margin: int = 0
    equal_size: bool = True


@dataclass
class ComposableContainerImage(ComposableContainerBase):
    """Container for composing multiple images into a single image.

    This class provides functionality to combine multiple images using different
    composition methods (horizontal, vertical, or overlay).
    """

    def append(self, obj: Image.Image | str | np.ndarray) -> None:
        """Appends an image to the container

        Args:
            obj (Image.Image | str | np.ndarray): Any representation of an image

        Raises:
            RuntimeWarning: if file format is not recognised or data is invalid
        """
        if obj is not None:
            if isinstance(obj, Image.Image):
                self.container.append(obj)
            elif isinstance(obj, ComposableContainerImage):
                self.container.append(obj.render())
            elif isinstance(obj, np.ndarray):
                # Convert numpy array to PIL Image
                if obj.dtype != np.uint8:
                    # Normalize to 0-255 range if needed
                    if obj.max() <= 1.0:
                        obj = (obj * 255).astype(np.uint8)
                    else:
                        obj = obj.astype(np.uint8)
                self.container.append(Image.fromarray(obj))
            elif isinstance(obj, str):
                path = Path(obj)
                extension = str.lower(path.suffix)
                if extension in [".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"]:
                    self.container.append(Image.open(obj))
                else:
                    raise RuntimeWarning(f"unsupported filetype {extension}")
            else:
                raise RuntimeWarning(f"unsupported type {type(obj)}")
        else:
            raise RuntimeWarning("No data passed to ComposableContainerImage.append()")

    def _make_equal_size(self, images: list[Image.Image]) -> list[Image.Image]:
        """Resize all images to match the largest dimensions.

        Args:
            images: List of PIL Images

        Returns:
            List of resized PIL Images
        """
        if not images:
            return images

        # Find maximum dimensions
        max_width = max(img.width for img in images)
        max_height = max(img.height for img in images)

        # Resize all images to max dimensions
        resized = []
        for img in images:
            if img.width != max_width or img.height != max_height:
                # Create new image with background color
                new_img = Image.new("RGB", (max_width, max_height), (255, 255, 255))
                # Paste original image centered
                x_offset = (max_width - img.width) // 2
                y_offset = (max_height - img.height) // 2
                if img.mode == "RGBA":
                    new_img.paste(img, (x_offset, y_offset), img)
                else:
                    new_img.paste(img, (x_offset, y_offset))
                resized.append(new_img)
            else:
                resized.append(img.convert("RGB"))

        return resized

    def _add_margin(self, img: Image.Image, margin: int, color: tuple) -> Image.Image:
        """Add margin around an image.

        Args:
            img: PIL Image
            margin: Margin size in pixels
            color: RGB color tuple

        Returns:
            PIL Image with margin
        """
        if margin <= 0:
            return img

        new_width = img.width + 2 * margin
        new_height = img.height + 2 * margin
        new_img = Image.new("RGB", (new_width, new_height), color)
        new_img.paste(img, (margin, margin))
        return new_img

    def _create_label(self, text: str, width: int, height: int, color: tuple) -> Image.Image:
        """Create a simple text label image.

        Args:
            text: Label text
            width: Image width
            height: Image height
            color: Background color

        Returns:
            PIL Image with text
        """
        from PIL import ImageDraw, ImageFont

        img = Image.new("RGB", (width, height), color)
        draw = ImageDraw.Draw(img)

        # Try to use a default font, fall back to default if not available
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
        except (OSError, IOError):
            font = ImageFont.load_default()

        # Draw text centered
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        position = ((width - text_width) // 2, (height - text_height) // 2)
        draw.text(position, text, fill=(0, 0, 0), font=font)

        return img

    def render(self, render_cfg: ImageRenderCfg = None, **kwargs) -> Image.Image:
        """Composes the images into a single image based on the compose method

        Args:
            render_cfg (ImageRenderCfg, optional): Configuration for rendering. If None, uses defaults.
            **kwargs: Additional arguments to override render_cfg settings

        Returns:
            Image.Image: A composite PIL Image containing the images added via append()
        """
        if render_cfg is None:
            render_cfg = ImageRenderCfg(**kwargs)

        if not self.container:
            # Return empty white image
            return Image.new("RGB", (100, 100), render_cfg.background_col)

        images = self.container.copy()

        # Make all images equal size if requested
        if render_cfg.equal_size:
            images = self._make_equal_size(images)

        # Add margins
        if render_cfg.margin > 0:
            images = [
                self._add_margin(img, render_cfg.margin, render_cfg.background_col)
                for img in images
            ]

        # Compose images based on method
        if render_cfg.compose_method == ComposeType.right:
            # Horizontal concatenation
            total_width = sum(img.width for img in images)
            max_height = max(img.height for img in images)

            result = Image.new("RGB", (total_width, max_height), render_cfg.background_col)
            x_offset = 0
            for img in images:
                result.paste(img, (x_offset, 0))
                x_offset += img.width

        elif render_cfg.compose_method == ComposeType.down:
            # Vertical concatenation
            max_width = max(img.width for img in images)
            total_height = sum(img.height for img in images)

            result = Image.new("RGB", (max_width, total_height), render_cfg.background_col)
            y_offset = 0
            for img in images:
                result.paste(img, (0, y_offset))
                y_offset += img.height

        elif render_cfg.compose_method == ComposeType.overlay:
            # Overlay with alpha blending
            max_width = max(img.width for img in images)
            max_height = max(img.height for img in images)

            result = Image.new("RGBA", (max_width, max_height), render_cfg.background_col + (255,))

            alpha = 1.0 / len(images)
            for img in images:
                # Convert to RGBA and adjust alpha
                img_rgba = img.convert("RGBA")
                # Multiply alpha channel
                img_array = np.array(img_rgba).astype(float)
                img_array[:, :, 3] *= alpha
                img_alpha = Image.fromarray(img_array.astype(np.uint8), "RGBA")
                result = Image.alpha_composite(result, img_alpha)

            result = result.convert("RGB")

        elif render_cfg.compose_method == ComposeType.sequence:
            # For images, sequence doesn't make sense, so just return the last image
            result = images[-1]
        else:
            raise RuntimeError(f"This compose type is not supported: {render_cfg.compose_method}")

        # Add label if specified
        label_text = self.label_formatter(render_cfg.var_name, render_cfg.var_value)
        if label_text is not None:
            label_img = self._create_label(
                label_text,
                result.width if render_cfg.compose_method == ComposeType.down else 200,
                30 if render_cfg.compose_method == ComposeType.down else result.height,
                render_cfg.background_col,
            )

            # Compose label with result
            if render_cfg.compose_method == ComposeType.down:
                # Add label to the right
                total_width = result.width + label_img.width
                max_height = max(result.height, label_img.height)
                final = Image.new("RGB", (total_width, max_height), render_cfg.background_col)
                final.paste(label_img, (0, 0))
                final.paste(result, (label_img.width, 0))
                result = final
            else:
                # Add label on top
                max_width = max(result.width, label_img.width)
                total_height = result.height + label_img.height
                final = Image.new("RGB", (max_width, total_height), render_cfg.background_col)
                final.paste(label_img, (0, 0))
                final.paste(result, (0, label_img.height))
                result = final

        return result

    def to_image(self, render_cfg: ImageRenderCfg = None) -> str:
        """Returns the composite image as a PNG file path

        Args:
            render_cfg: Configuration for rendering

        Returns:
            str: PNG filepath
        """
        img = self.render(render_cfg)
        filepath = gen_image_path("composable")
        img.save(filepath, "PNG")
        return str(filepath)

    def deep(self):
        """Create a deep copy of this container"""
        return deepcopy(self)
