import torch
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter
import io


class PhotoLab:
    """
    ComfyUI node that applies photo lab effects through JPG compression,
    color grading, film grain, vignette, and blur to emulate darkroom aesthetics.
    Optionally matches the lighting and shadows of a reference image.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE", {"tooltip": "The images to apply photo lab effects to."}),
                "quality": ("INT", {
                    "default": 70,
                    "min": 0,
                    "max": 100,
                    "step": 1,
                    "tooltip": "JPG compression quality. Lower = more artifacts (0-100)"
                }),
                "passes": ("INT", {
                    "default": 1,
                    "min": 1,
                    "max": 10,
                    "step": 1,
                    "tooltip": "Number of compression passes. More passes = more degradation"
                }),
                "grain_strength": ("INT", {
                    "default": 5,
                    "min": 0,
                    "max": 100,
                    "step": 1,
                    "tooltip": "Amount of film grain. Set to 0 to disable (0-100)"
                }),
                "vignette_strength": ("INT", {
                    "default": 0,
                    "min": 0,
                    "max": 100,
                    "step": 1,
                    "tooltip": "Vignette darkness around edges. Set to 0 to disable (0-100)"
                }),
                "color_grade": (["None", "Warm", "Cool", "Faded", "Sepia"], {
                    "default": "Faded",
                    "tooltip": "Color grading preset"
                }),
                "color_grade_strength": ("INT", {
                    "default": 50,
                    "min": 0,
                    "max": 100,
                    "step": 1,
                    "tooltip": "Strength of color grade effect. 0 = disabled, 100 = full effect (0-100)"
                }),
                "saturation": ("INT", {
                    "default": 70,
                    "min": 0,
                    "max": 200,
                    "step": 1,
                    "tooltip": "Color saturation (0 = grayscale, 100 = original, 200 = max boost)"
                }),
                "blur_type": (["None", "Gaussian", "Box", "Motion Horizontal", "Motion Vertical", "Radial", "Lens", "Soft Focus"], {
                    "default": "None",
                    "tooltip": "Type of blur to apply"
                }),
                "blur_strength": ("INT", {
                    "default": 0,
                    "min": 0,
                    "max": 100,
                    "step": 1,
                    "tooltip": "Strength of blur effect. Set to 0 to disable (0-100)"
                }),
                "lighting_match_mode": (["Disabled", "Histogram (L-channel)", "Reinhard Transfer", "Full LAB Histogram"], {
                    "default": "Disabled",
                    "tooltip": (
                        "Algorithm used to match lighting from reference image. "
                        "'Histogram (L-channel)' - best all-rounder, matches luminance distribution only. "
                        "'Reinhard Transfer' - fast mean/std transfer, good for subtle corrections. "
                        "'Full LAB Histogram' - matches all LAB channels including color tone."
                    )
                }),
                "lighting_match_strength": ("FLOAT", {
                    "default": 1.0,
                    "min": 0.0,
                    "max": 1.0,
                    "step": 0.05,
                    "tooltip": "Blend between original (0.0) and fully matched lighting (1.0)"
                }),
            },
            "optional": {
                "reference_image": ("IMAGE", {
                    "tooltip": (
                        "Reference image whose lighting and shadows will be matched onto the input images. "
                        "Only used when lighting_match_mode is not 'Disabled'."
                    )
                }),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "process"
    CATEGORY = "image/effects"
    DESCRIPTION = (
        "Apply photo lab effects including JPG compression artifacts, film grain, vignette, blur, and color grading. "
        "Optionally matches the lighting and shadows of a reference image before applying effects."
    )

    def process(self, images, quality=70, passes=1, grain_strength=5,
                vignette_strength=0, color_grade="Faded", color_grade_strength=50,
                saturation=70, blur_type="None", blur_strength=0,
                lighting_match_mode="Disabled", lighting_match_strength=1.0,
                reference_image=None):
        """
        Apply photo lab effects to input images, with optional lighting match from a reference.

        Args:
            images: Tensor of images in ComfyUI format [B, H, W, C]
            quality: JPG compression quality (0-100)
            passes: Number of compression passes
            grain_strength: Strength of grain effect (0-100, 0 = disabled)
            vignette_strength: Strength of vignette effect (0-100, 0 = disabled)
            color_grade: Color grading preset
            color_grade_strength: Strength of color grade (0-100)
            saturation: Color saturation (0-200, 100 = original)
            blur_type: Type of blur effect
            blur_strength: Strength of blur (0-100)
            lighting_match_mode: Algorithm to use for lighting transfer
            lighting_match_strength: Blend strength for lighting match (0.0-1.0)
            reference_image: Optional reference tensor [B, H, W, C] for lighting match

        Returns:
            Processed images tensor
        """
        # Convert 0-100 scale inputs to their actual ranges
        quality_actual = max(1, quality)
        saturation_actual = saturation / 100.0
        vignette_actual = vignette_strength / 100.0
        grain_actual = grain_strength / 2.0
        color_grade_actual = color_grade_strength / 100.0

        # Pre-extract the reference numpy array once (reused for every image in the batch)
        ref_np = None
        if lighting_match_mode != "Disabled" and reference_image is not None:
            ref_np = reference_image[0].cpu().numpy().astype(np.float32)

        result_images = []

        for image in images:
            img_np = 255.0 * image.cpu().numpy()
            img_np = np.clip(img_np, 0, 255).astype(np.uint8)
            img_pil = Image.fromarray(img_np)

            # Convert to RGB if necessary
            if img_pil.mode in ('RGBA', 'LA', 'P'):
                img_pil = img_pil.convert('RGB')

            # ----------------------------------------------------------------
            # 1. Lighting match (applied first, before any artistic effects)
            # ----------------------------------------------------------------
            if lighting_match_mode != "Disabled" and ref_np is not None:
                img_pil = self._match_lighting(img_pil, ref_np, lighting_match_mode, lighting_match_strength)

            # ----------------------------------------------------------------
            # 2. Effects pipeline
            # ----------------------------------------------------------------
            # When color_grade is "None", skip ALL colour changes including
            # saturation — the image must pass through completely unaltered
            # in terms of colour. Saturation only runs when a grade is active.
            if color_grade != "None":
                if saturation != 100:
                    enhancer = ImageEnhance.Color(img_pil)
                    img_pil = enhancer.enhance(saturation_actual)
                img_pil = self._apply_color_effects(img_pil, color_grade, color_grade_actual)

            if grain_strength > 0:
                img_pil = self._add_film_grain(img_pil, grain_actual)

            if blur_type != "None" and blur_strength > 0:
                img_pil = self._apply_blur(img_pil, blur_type, blur_strength)

            if vignette_strength > 0:
                img_pil = self._apply_vignette(img_pil, vignette_actual)

            for _ in range(passes):
                buffer = io.BytesIO()
                img_pil.save(buffer, format='JPEG', quality=quality_actual)
                buffer.seek(0)
                img_pil = Image.open(buffer)

            img_np = np.array(img_pil).astype(np.float32) / 255.0
            img_tensor = torch.from_numpy(img_np)
            result_images.append(img_tensor)

        result_batch = torch.stack(result_images)
        return (result_batch,)

    # =========================================================================
    # Lighting Match
    # =========================================================================

    def _match_lighting(self, target_pil, ref_np, mode, strength):
        """
        Transfer the lighting/shadow characteristics of a reference image onto
        the target PIL image.

        Works entirely in CIE LAB colour space so that hue and saturation are
        preserved; only the lightness (and optionally the chrominance) channels
        are adjusted.

        Args:
            target_pil  : PIL.Image  - the image whose lighting will be adjusted
            ref_np      : np.ndarray - reference image in [0,1] float32 RGB
            mode        : str        - one of the lighting_match_mode options
            strength    : float      - 0.0 = no change, 1.0 = full match

        Returns:
            PIL.Image with adjusted lighting
        """
        try:
            from skimage import color, exposure
        except ImportError:
            print("[PhotoLab] WARNING: scikit-image not found; lighting match skipped. "
                  "Install it with: pip install scikit-image")
            return target_pil

        # ---- prepare arrays ------------------------------------------------
        tgt_np = np.array(target_pil, dtype=np.float32) / 255.0

        # Resize reference to target dimensions if they differ
        if ref_np.shape[:2] != tgt_np.shape[:2]:
            ref_pil_resized = Image.fromarray((ref_np * 255).astype(np.uint8)).resize(
                (tgt_np.shape[1], tgt_np.shape[0]), Image.LANCZOS
            )
            ref_np_sized = np.array(ref_pil_resized, dtype=np.float32) / 255.0
        else:
            ref_np_sized = ref_np

        # ---- convert to LAB ------------------------------------------------
        tgt_lab = color.rgb2lab(tgt_np)
        ref_lab = color.rgb2lab(ref_np_sized)
        original_lab = tgt_lab.copy()

        # ---- apply chosen algorithm ----------------------------------------
        if mode == "Histogram (L-channel)":
            tgt_lab[..., 0] = exposure.match_histograms(
                tgt_lab[..., 0], ref_lab[..., 0]
            )

        elif mode == "Reinhard Transfer":
            tgt_L = tgt_lab[..., 0]
            ref_L = ref_lab[..., 0]
            tgt_lab[..., 0] = (
                (tgt_L - tgt_L.mean()) / (tgt_L.std() + 1e-6)
            ) * ref_L.std() + ref_L.mean()

        elif mode == "Full LAB Histogram":
            tgt_lab = exposure.match_histograms(tgt_lab, ref_lab, channel_axis=-1)

        # ---- blend with original based on strength -------------------------
        if strength < 1.0:
            tgt_lab = original_lab + strength * (tgt_lab - original_lab)

        # ---- convert back to RGB -------------------------------------------
        result_rgb = np.clip(color.lab2rgb(tgt_lab), 0.0, 1.0)
        result_uint8 = (result_rgb * 255).astype(np.uint8)
        return Image.fromarray(result_uint8)

    # =========================================================================
    # Effects helpers
    # =========================================================================

    def _apply_blur(self, img, blur_type, strength):
        """Apply various types of blur effects."""
        if strength == 0 or blur_type == "None":
            return img

        if blur_type == "Gaussian":
            radius = strength / 5.0
            return img.filter(ImageFilter.GaussianBlur(radius=radius))

        elif blur_type == "Box":
            radius = max(1, int(strength / 5.0))
            return img.filter(ImageFilter.BoxBlur(radius=radius))

        elif blur_type == "Motion Horizontal":
            img_array = np.array(img, dtype=np.float32)
            kernel_size = max(3, int(strength / 3.0))
            kernel = np.zeros((kernel_size, kernel_size))
            kernel[kernel_size // 2, :] = 1.0 / kernel_size
            from scipy.ndimage import convolve
            for i in range(img_array.shape[2]):
                img_array[:, :, i] = convolve(img_array[:, :, i], kernel, mode='reflect')
            return Image.fromarray(np.clip(img_array, 0, 255).astype(np.uint8))

        elif blur_type == "Motion Vertical":
            img_array = np.array(img, dtype=np.float32)
            kernel_size = max(3, int(strength / 3.0))
            kernel = np.zeros((kernel_size, kernel_size))
            kernel[:, kernel_size // 2] = 1.0 / kernel_size
            from scipy.ndimage import convolve
            for i in range(img_array.shape[2]):
                img_array[:, :, i] = convolve(img_array[:, :, i], kernel, mode='reflect')
            return Image.fromarray(np.clip(img_array, 0, 255).astype(np.uint8))

        elif blur_type == "Radial":
            img_array = np.array(img, dtype=np.float32)
            height, width = img_array.shape[:2]
            center_y, center_x = height / 2, width / 2
            samples = max(3, int(strength / 10.0))
            blur_amount = strength / 500.0
            result = np.zeros_like(img_array)
            for i in range(samples):
                scale = 1.0 - (i * blur_amount / samples)
                y_indices = np.arange(height)
                x_indices = np.arange(width)
                new_y = ((y_indices - center_y) * scale + center_y).astype(np.float32)
                new_x = ((x_indices - center_x) * scale + center_x).astype(np.float32)
                new_y = np.clip(new_y, 0, height - 1)
                new_x = np.clip(new_x, 0, width - 1)
                new_y_int = new_y.astype(np.int32)
                new_x_int = new_x.astype(np.int32)
                result += img_array[new_y_int[:, np.newaxis], new_x_int[np.newaxis, :]]
            result /= samples
            return Image.fromarray(np.clip(result, 0, 255).astype(np.uint8))

        elif blur_type == "Lens":
            img_array = np.array(img, dtype=np.float32)
            height, width = img_array.shape[:2]
            center_y, center_x = height / 2, width / 2
            Y, X = np.ogrid[:height, :width]
            dist_from_center = np.sqrt((X - center_x)**2 + (Y - center_y)**2)
            max_dist = np.sqrt(center_x**2 + center_y**2)
            dist_normalized = dist_from_center / max_dist
            blur_amount = (dist_normalized ** 1.5) * (strength / 5.0)
            blurred = np.array(img.filter(ImageFilter.GaussianBlur(radius=strength / 5.0)))
            blend_mask = np.clip(blur_amount, 0, 1)
            if len(img_array.shape) == 3:
                blend_mask = blend_mask[:, :, np.newaxis]
            result = img_array * (1 - blend_mask) + blurred * blend_mask
            return Image.fromarray(np.clip(result, 0, 255).astype(np.uint8))

        elif blur_type == "Soft Focus":
            radius = strength / 4.0
            blurred = img.filter(ImageFilter.GaussianBlur(radius=radius))
            img_array = np.array(img, dtype=np.float32)
            blurred_array = np.array(blurred, dtype=np.float32)
            blend_strength = min(0.6, strength / 150.0)
            result = img_array * (1 - blend_strength) + (
                255 - (255 - img_array) * (255 - blurred_array) / 255
            ) * blend_strength
            return Image.fromarray(np.clip(result, 0, 255).astype(np.uint8))

        return img

    def _apply_color_effects(self, img, color_grade, strength=1.0):
        """Apply color grading with controllable strength. Saturation is handled separately."""
        original_img = img.copy()

        if color_grade == "Warm":
            img_array = np.array(img, dtype=np.float32)
            img_array[:, :, 0] = np.clip(img_array[:, :, 0] * 1.15, 0, 255)
            img_array[:, :, 1] = np.clip(img_array[:, :, 1] * 1.05, 0, 255)
            img_array[:, :, 2] = np.clip(img_array[:, :, 2] * 0.85, 0, 255)
            img = Image.fromarray(img_array.astype(np.uint8))

        elif color_grade == "Cool":
            img_array = np.array(img, dtype=np.float32)
            img_array[:, :, 0] = np.clip(img_array[:, :, 0] * 0.85, 0, 255)
            img_array[:, :, 1] = np.clip(img_array[:, :, 1] * 1.0, 0, 255)
            img_array[:, :, 2] = np.clip(img_array[:, :, 2] * 1.2, 0, 255)
            img = Image.fromarray(img_array.astype(np.uint8))

        elif color_grade == "Faded":
            contrast = ImageEnhance.Contrast(img)
            img = contrast.enhance(0.75)
            brightness = ImageEnhance.Brightness(img)
            img = brightness.enhance(1.15)

        elif color_grade == "Sepia":
            img_array = np.array(img, dtype=np.float32)
            sepia_r = img_array[:, :, 0] * 0.393 + img_array[:, :, 1] * 0.769 + img_array[:, :, 2] * 0.189
            sepia_g = img_array[:, :, 0] * 0.349 + img_array[:, :, 1] * 0.686 + img_array[:, :, 2] * 0.168
            sepia_b = img_array[:, :, 0] * 0.272 + img_array[:, :, 1] * 0.534 + img_array[:, :, 2] * 0.131
            img_array[:, :, 0] = np.clip(sepia_r, 0, 255)
            img_array[:, :, 1] = np.clip(sepia_g, 0, 255)
            img_array[:, :, 2] = np.clip(sepia_b, 0, 255)
            img = Image.fromarray(img_array.astype(np.uint8))

        if strength < 1.0:
            img_array = np.array(img, dtype=np.float32)
            original_array = np.array(original_img, dtype=np.float32)
            blended = original_array * (1.0 - strength) + img_array * strength
            img = Image.fromarray(blended.astype(np.uint8))

        return img

    def _add_film_grain(self, img, strength):
        """Add film grain/noise to the image."""
        img_array = np.array(img, dtype=np.float32)
        noise = np.random.normal(0, strength, img_array.shape)
        img_array = np.clip(img_array + noise, 0, 255)
        return Image.fromarray(img_array.astype(np.uint8))

    def _apply_vignette(self, img, strength):
        """Apply vignette effect (darkening around edges)."""
        img_array = np.array(img, dtype=np.float32)
        height, width = img_array.shape[:2]
        center_y, center_x = height / 2, width / 2
        Y, X = np.ogrid[:height, :width]
        dist_from_center = np.sqrt((X - center_x)**2 + (Y - center_y)**2)
        max_dist = np.sqrt(center_x**2 + center_y**2)
        dist_from_center = dist_from_center / max_dist
        vignette_mask = 1.0 - (dist_from_center ** 2) * strength
        vignette_mask = np.clip(vignette_mask, 0, 1)
        if len(img_array.shape) == 3:
            vignette_mask = vignette_mask[:, :, np.newaxis]
        img_array = img_array * vignette_mask
        img_array = np.clip(img_array, 0, 255)
        return Image.fromarray(img_array.astype(np.uint8))
