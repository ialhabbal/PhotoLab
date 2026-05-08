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
                "pixelate_strength": ("INT", {
                    "default": 0,
                    "min": 0,
                    "max": 100,
                    "step": 1,
                    "tooltip": "Pixelation strength. Reduces image to a lower resolution grid and scales back up. Set to 0 to disable (0-100)"
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
                "mask_mode": (["Face Only", "Inverted", "Disabled"], {
                    "default": "Face Only",
                    "tooltip": (
                        "Controls the face_mask and ALL skin effects below this widget. "
                        "'Face Only' — skin effects apply only inside the connected mask. "
                        "'Inverted' — skin effects apply only outside the mask (e.g. body skin). "
                        "'Disabled' — ALL skin effect widgets below are completely skipped; "
                        "only global effects above (color grade, blur, grain, vignette, compression) run."
                    )
                }),
                "pores_strength": ("INT", {
                    "default": 0,
                    "min": 0,
                    "max": 100,
                    "step": 1,
                    "tooltip": (
                        "Simulates visible skin pores via a high-frequency Difference-of-Gaussians "
                        "texture layer blended in Overlay mode. "
                        "Subtle: 10-25 | Natural: 30-50 | Heavy/macro: 60-80. Set to 0 to disable."
                    )
                }),
                "blemishes_strength": ("INT", {
                    "default": 0,
                    "min": 0,
                    "max": 100,
                    "step": 1,
                    "tooltip": (
                        "Adds soft reddish/brownish skin blemishes (pigmentation spots) using "
                        "Gaussian-falloff ellipses in melanin-aware colour space. "
                        "Light: 10-25 | Moderate: 30-55 | Heavy: 60-100. Set to 0 to disable."
                    )
                }),
                "acne_strength": ("INT", {
                    "default": 0,
                    "min": 0,
                    "max": 100,
                    "step": 1,
                    "tooltip": (
                        "Renders raised-looking acne spots with a reddish inflamed surround and "
                        "a subtle specular highlight to suggest a 3-D bump. "
                        "Few/mild: 10-25 | Moderate breakout: 30-55 | Severe: 60-100. Set to 0 to disable."
                    )
                }),
                "freckles_strength": ("INT", {
                    "default": 0,
                    "min": 0,
                    "max": 100,
                    "step": 1,
                    "tooltip": (
                        "Scatters small melanin-tinted freckles concentrated on cheeks and nose bridge, "
                        "with randomised size, opacity, and slight colour variation. "
                        "Light dusting: 10-25 | Natural coverage: 30-55 | Dense: 60-100. Set to 0 to disable."
                    )
                }),
                "skin_texture_strength": ("INT", {
                    "default": 0,
                    "min": 0,
                    "max": 100,
                    "step": 1,
                    "tooltip": (
                        "Enhances micro skin texture (fine lines, pore shadows, subtle relief) by "
                        "boosting a high-frequency detail layer extracted via unsharp masking. "
                        "Subtle: 10-20 | Natural film look: 25-45 | Hyper-detailed: 50-70. Set to 0 to disable."
                    )
                }),
                # ---- Improvement 3: subsurface scattering ----
                "sss_strength": ("INT", {
                    "default": 0,
                    "min": 0,
                    "max": 100,
                    "step": 1,
                    "tooltip": (
                        "Subsurface scattering: adds a warm translucent glow beneath skin by Screen-blending "
                        "a low-opacity orange-pink blurred layer, simulating how light travels through the "
                        "dermis. Breaks the flat opaque 'plastic' AI look. "
                        "Subtle: 5-15 | Natural: 16-35 | Strong: 36-60. Set to 0 to disable."
                    )
                }),
                # ---- Improvement 4: peach fuzz ----
                "peach_fuzz_strength": ("INT", {
                    "default": 0,
                    "min": 0,
                    "max": 100,
                    "step": 1,
                    "tooltip": (
                        "Renders procedural vellus (peach fuzz) hair as fine curved micro-strokes oriented "
                        "downward with slight random angles, at very low opacity. Dramatically breaks the "
                        "AI plastic-skin look by adding the fine hair that covers real faces. "
                        "Barely visible: 5-15 | Natural: 16-40 | Dense: 41-70. Set to 0 to disable."
                    )
                }),
                # ---- Improvement 5: uneven skin tone / redness ----
                "skin_redness_strength": ("INT", {
                    "default": 0,
                    "min": 0,
                    "max": 100,
                    "step": 1,
                    "tooltip": (
                        "Adds natural facial redness zones — cheeks, nose tip, chin — from blood vessels "
                        "near the skin surface, using soft Gaussian blobs in warm-red tint. "
                        "Subtle flush: 5-20 | Rosy cheeks: 21-50 | Strong redness: 51-80. Set to 0 to disable."
                    )
                }),
                # ---- Improvement 6: sebum shine ----
                "sebum_shine_strength": ("INT", {
                    "default": 0,
                    "min": 0,
                    "max": 100,
                    "step": 1,
                    "tooltip": (
                        "Simulates T-zone sebum/oil shine (forehead, nose bridge, chin) using small specular "
                        "highlight ellipses in Screen blend. Adds the natural sheen of oily skin without "
                        "overexposing the whole image. "
                        "Matte skin: 0 | Light shine: 5-20 | Oily: 21-55 | Very oily: 56-80. Set to 0 to disable."
                    )
                }),
                # ---- Improvement 7: seed control ----
                "skin_seed": ("INT", {
                    "default": 0,
                    "min": 0,
                    "max": 2147483647,
                    "step": 1,
                    "tooltip": (
                        "Master seed for all procedural skin effects (pores, freckles, blemishes, acne, "
                        "peach fuzz, shine). Same seed always produces the same pattern on the same image. "
                        "Change to get a different arrangement of spots, pores, and hairs."
                    )
                }),
                # ---- Improvement 8: per-effect opacity sliders ----
                "pores_opacity": ("INT", {
                    "default": 100,
                    "min": 0,
                    "max": 100,
                    "step": 1,
                    "tooltip": "Opacity of the pores effect (0 = invisible, 100 = full). Controls visibility independently of density/strength."
                }),
                "blemishes_opacity": ("INT", {
                    "default": 100,
                    "min": 0,
                    "max": 100,
                    "step": 1,
                    "tooltip": "Opacity of blemishes (0 = invisible, 100 = full). Allows many faint marks vs few vivid ones."
                }),
                "acne_opacity": ("INT", {
                    "default": 100,
                    "min": 0,
                    "max": 100,
                    "step": 1,
                    "tooltip": "Opacity of acne spots (0 = invisible, 100 = full)."
                }),
                "freckles_opacity": ("INT", {
                    "default": 100,
                    "min": 0,
                    "max": 100,
                    "step": 1,
                    "tooltip": "Opacity of freckles (0 = invisible, 100 = full). Allows dense faint freckles vs sparse vivid ones."
                }),
                "skin_texture_opacity": ("INT", {
                    "default": 100,
                    "min": 0,
                    "max": 100,
                    "step": 1,
                    "tooltip": "Opacity of the skin texture effect (0 = invisible, 100 = full)."
                }),
            },
            "optional": {
                "reference_image": ("IMAGE", {
                    "tooltip": (
                        "Reference image whose lighting and shadows will be matched onto the input images. "
                        "Only used when lighting_match_mode is not 'Disabled'."
                    )
                }),
                "face_mask": ("MASK", {
                    "tooltip": (
                        "Optional grayscale mask (0 = no effect, 1 = full effect) used to spatially "
                        "restrict skin effects. Behaviour set by mask_mode: 'Face Only' keeps effects "
                        "inside the mask; 'Inverted' keeps them outside; 'Disabled' skips all skin "
                        "effects entirely regardless of this input."
                    )
                }),
            },
        }

    RETURN_TYPES = ("IMAGE", "MASK")
    RETURN_NAMES = ("images", "face_mask")
    FUNCTION = "process"
    CATEGORY = "image/effects"
    DESCRIPTION = (
        "Apply photo lab effects including JPG compression artifacts, film grain, vignette, blur, and color grading. "
        "Optionally matches the lighting and shadows of a reference image. "
        "Skin effects (pores, freckles, blemishes, acne, texture, SSS, peach fuzz, redness, shine) sit below "
        "the mask_mode widget and are fully skipped when mask_mode is 'Disabled', spatially confined to a "
        "connected face mask when 'Face Only', or applied outside the mask when 'Inverted'. "
        "The mask is also passed through as a second output. "
        "A seed input controls all procedural skin effect patterns for reproducibility."
    )

    def process(self, images, quality=70, passes=1, pixelate_strength=0, grain_strength=5,
                vignette_strength=0, color_grade="Faded", color_grade_strength=50,
                saturation=70, blur_type="None", blur_strength=0,
                lighting_match_mode="Disabled", lighting_match_strength=1.0,
                mask_mode="Face Only",
                pores_strength=0, blemishes_strength=0, acne_strength=0,
                freckles_strength=0, skin_texture_strength=0,
                sss_strength=0, peach_fuzz_strength=0,
                skin_redness_strength=0, sebum_shine_strength=0,
                skin_seed=0,
                pores_opacity=100, blemishes_opacity=100, acne_opacity=100,
                freckles_opacity=100, skin_texture_opacity=100,
                reference_image=None, face_mask=None):
        """
        Apply photo lab effects to input images, with optional lighting match from a reference.

        Args:
            images: Tensor of images in ComfyUI format [B, H, W, C]
            quality: JPG compression quality (0-100)
            passes: Number of compression passes
            pixelate_strength: Strength of pixelation effect (0-100, 0 = disabled)
            grain_strength: Strength of grain effect (0-100, 0 = disabled)
            vignette_strength: Strength of vignette effect (0-100, 0 = disabled)
            color_grade: Color grading preset
            color_grade_strength: Strength of color grade (0-100)
            saturation: Color saturation (0-200, 100 = original)
            blur_type: Type of blur effect
            blur_strength: Strength of blur (0-100)
            lighting_match_mode: Algorithm to use for lighting transfer
            lighting_match_strength: Blend strength for lighting match (0.0-1.0)
            pores_strength: Visible skin pore texture (0-100, 0 = disabled)
            blemishes_strength: Soft pigmentation/blemish spots (0-100, 0 = disabled)
            acne_strength: Raised acne spots with specular highlight (0-100, 0 = disabled)
            freckles_strength: Melanin freckle scatter (0-100, 0 = disabled)
            skin_texture_strength: High-frequency micro skin texture (0-100, 0 = disabled)
            sss_strength: Subsurface scattering warm-glow simulation (0-100, 0 = disabled)
            peach_fuzz_strength: Procedural vellus hair micro-strokes (0-100, 0 = disabled)
            skin_redness_strength: Natural cheek/nose redness zones (0-100, 0 = disabled)
            sebum_shine_strength: T-zone sebum specular shine (0-100, 0 = disabled)
            skin_seed: Master seed for all procedural skin effects (0-2147483647)
            pores_opacity: Final opacity multiplier for pores effect (0-100)
            blemishes_opacity: Final opacity multiplier for blemishes (0-100)
            acne_opacity: Final opacity multiplier for acne (0-100)
            freckles_opacity: Final opacity multiplier for freckles (0-100)
            skin_texture_opacity: Final opacity multiplier for skin texture (0-100)
            reference_image: Optional reference tensor [B, H, W, C] for lighting match
            face_mask: Optional mask tensor [B, H, W] or [B, 1, H, W] in [0,1] range.
                       When provided, all skin effects are composited back onto the
                       original using the mask as alpha, so only masked (white) regions
                       receive the skin treatment. The mask is also returned as a second
                       output; a full-white mask is returned when no mask is connected.

        Returns:
            Tuple of (processed_images_tensor, face_mask_tensor)
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

        # Skin effects are entirely skipped when mask_mode is "Disabled".
        # This lets the node act as a pure global-effects node without needing
        # to zero out every individual skin slider.
        any_skin_effect = mask_mode != "Disabled" and any([
            skin_texture_strength > 0, pores_strength > 0, freckles_strength > 0,
            blemishes_strength > 0, acne_strength > 0, sss_strength > 0,
            peach_fuzz_strength > 0, skin_redness_strength > 0, sebum_shine_strength > 0,
        ])

        result_images = []

        for i, image in enumerate(images):
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

            if pixelate_strength > 0:
                img_pil = self._apply_pixelation(img_pil, pixelate_strength)

            # ----------------------------------------------------------------
            # 3. Face skin effects — optionally masked to face region only
            # ----------------------------------------------------------------
            if any_skin_effect:
                # Snapshot the image before any skin effects so we can
                # composite back with the mask afterwards
                img_before_skin = img_pil.copy()

                # Detect Fitzpatrick skin tone once per image (improvement #1)
                fitzpatrick = self._detect_fitzpatrick(img_pil)

                if skin_redness_strength > 0:
                    img_pil = self._apply_skin_redness(img_pil, skin_redness_strength)

                if sss_strength > 0:
                    img_pil = self._apply_subsurface_scatter(img_pil, sss_strength, fitzpatrick)

                if skin_texture_strength > 0:
                    img_pil = self._apply_skin_texture(
                        img_pil, skin_texture_strength,
                        opacity=skin_texture_opacity / 100.0,
                        seed=skin_seed
                    )

                if pores_strength > 0:
                    img_pil = self._apply_pores(
                        img_pil, pores_strength,
                        opacity=pores_opacity / 100.0,
                        seed=skin_seed + 1
                    )

                if freckles_strength > 0:
                    img_pil = self._apply_freckles(
                        img_pil, freckles_strength, fitzpatrick,
                        opacity=freckles_opacity / 100.0,
                        seed=skin_seed + 2
                    )

                if blemishes_strength > 0:
                    img_pil = self._apply_blemishes(
                        img_pil, blemishes_strength, fitzpatrick,
                        opacity=blemishes_opacity / 100.0,
                        seed=skin_seed + 3
                    )

                if acne_strength > 0:
                    img_pil = self._apply_acne(
                        img_pil, acne_strength,
                        opacity=acne_opacity / 100.0,
                        seed=skin_seed + 4
                    )

                if peach_fuzz_strength > 0:
                    img_pil = self._apply_peach_fuzz(
                        img_pil, peach_fuzz_strength, fitzpatrick,
                        seed=skin_seed + 5
                    )

                if sebum_shine_strength > 0:
                    img_pil = self._apply_sebum_shine(
                        img_pil, sebum_shine_strength,
                        seed=skin_seed + 6
                    )

                # Composite skin effects back through the mask.
                # mask_mode "Disabled" never reaches here (any_skin_effect is False).
                # "Face Only": apply inside mask.  "Inverted": apply outside mask.
                if face_mask is not None:
                    img_pil = self._composite_with_mask(
                        img_before_skin, img_pil, face_mask, i,
                        invert=(mask_mode == "Inverted")
                    )

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

        # --- Improvement #6: pass face_mask through as second output --------
        # If a mask was connected, pass it through unchanged so downstream
        # nodes can reuse it without needing a second mask node.
        # If no mask was connected, return a full-white (ones) mask matching
        # the batch shape so the output socket is always valid.
        if face_mask is not None:
            out_mask = face_mask
        else:
            b, h, w = result_batch.shape[0], result_batch.shape[1], result_batch.shape[2]
            out_mask = torch.ones((b, h, w), dtype=torch.float32)

        return (result_batch, out_mask)

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

    def _detect_fitzpatrick(self, img_pil):
        """
        Classify the dominant skin tone into a Fitzpatrick scale bucket (1-6)
        by sampling the centre region of the image in CIE LAB space.

        Fitzpatrick scale (L* ranges in LAB, approximate):
          Type I   (very fair, burns easily):      L* > 78
          Type II  (fair):                    68 < L* <= 78
          Type III (medium, light brown):     58 < L* <= 68
          Type IV  (olive, moderate brown):   48 < L* <= 58
          Type V   (brown):                   38 < L* <= 48
          Type VI  (dark brown / black):           L* <= 38

        Returns int 1-6.
        """
        try:
            from skimage import color as skcolor
            arr = np.array(img_pil, dtype=np.float32) / 255.0
            h, w = arr.shape[:2]
            # Sample the central 40% of the image to avoid background / hair
            y0, y1 = int(h * 0.30), int(h * 0.70)
            x0, x1 = int(w * 0.30), int(w * 0.70)
            patch = arr[y0:y1, x0:x1]
            lab = skcolor.rgb2lab(patch)
            l_mean = float(lab[:, :, 0].mean())
        except ImportError:
            # fallback: use simple luminance if skimage unavailable
            arr = np.array(img_pil, dtype=np.float32) / 255.0
            h, w = arr.shape[:2]
            patch = arr[int(h*0.3):int(h*0.7), int(w*0.3):int(w*0.7)]
            lum = 0.299*patch[:,:,0] + 0.587*patch[:,:,1] + 0.114*patch[:,:,2]
            l_mean = float(lum.mean()) * 100.0

        if   l_mean > 78: return 1
        elif l_mean > 68: return 2
        elif l_mean > 58: return 3
        elif l_mean > 48: return 4
        elif l_mean > 38: return 5
        else:             return 6

    def _composite_with_mask(self, original_pil, processed_pil, face_mask, batch_index, invert=False):
        """
        Alpha-composite the skin-processed image over the original using the
        face mask, so skin effects only appear inside (or outside) the masked region.

        Args:
            original_pil  : PIL.Image — image before any skin effects
            processed_pil : PIL.Image — image after all skin effects
            face_mask     : torch.Tensor — ComfyUI MASK, shape [B, H, W] or [B, 1, H, W],
                            values in [0, 1] where 1 = fully apply skin effect
            batch_index   : int — which batch element to use from face_mask
            invert        : bool — flip the mask before compositing so skin effects
                            apply *outside* the masked region (mask_mode "Inverted")

        Returns:
            PIL.Image composited result
        """
        # --- extract the right mask frame -----------------------------------
        # ComfyUI MASKs are [B, H, W]; some nodes emit [B, 1, H, W]
        mask_tensor = face_mask[batch_index] if face_mask.ndim == 4 else face_mask[min(batch_index, face_mask.shape[0] - 1)]
        if mask_tensor.ndim == 3:          # (1, H, W) → (H, W)
            mask_tensor = mask_tensor.squeeze(0)
        mask_np = mask_tensor.cpu().numpy().astype(np.float32)   # [0, 1]

        # --- resize mask to match image if necessary ------------------------
        h, w = np.array(original_pil).shape[:2]
        if mask_np.shape != (h, w):
            mask_pil = Image.fromarray((mask_np * 255).astype(np.uint8), mode='L')
            mask_pil = mask_pil.resize((w, h), Image.LANCZOS)
            mask_np = np.array(mask_pil, dtype=np.float32) / 255.0

        # --- optional: feather mask edges for a seamless blend --------------
        # A small Gaussian blur (1.5 px) softens hard mask boundaries so the
        # skin effects don't have a sharp cut-off at the face outline.
        from scipy.ndimage import gaussian_filter
        mask_np = gaussian_filter(mask_np, sigma=1.5)
        mask_np = np.clip(mask_np, 0.0, 1.0)

        # Flip for "Inverted" mode: apply skin effects outside the masked region
        if invert:
            mask_np = 1.0 - mask_np

        # --- composite: out = processed * mask + original * (1 - mask) -----
        orig_arr = np.array(original_pil, dtype=np.float32)
        proc_arr = np.array(processed_pil, dtype=np.float32)
        alpha = mask_np[:, :, np.newaxis]          # broadcast over RGB channels
        result = proc_arr * alpha + orig_arr * (1.0 - alpha)
        return Image.fromarray(np.clip(result, 0, 255).astype(np.uint8))

    # =========================================================================
    # Face Skin Effects
    # =========================================================================

    def _apply_skin_redness(self, img, strength):
        """
        Improvement #4: Natural facial redness zones.

        Real faces have elevated blood vessel density at the nose, cheeks, and
        chin, producing a warm reddish flush visible beneath the skin. This is
        rendered as a small set of large, very soft Gaussian blobs placed at
        anatomically correct positions, tinted warm-red and blended in Soft-Light
        mode so they shift the skin tone without blowing out bright areas.

        Anatomical zones (relative to image frame, assuming portrait crop):
          - Left cheek:   (0.28, 0.48), σ = 0.10 × w
          - Right cheek:  (0.72, 0.48), σ = 0.10 × w
          - Nose tip:     (0.50, 0.60), σ = 0.05 × w
          - Chin:         (0.50, 0.80), σ = 0.07 × w
        """
        img_array = np.array(img, dtype=np.float32)
        h, w = img_array.shape[:2]
        t = strength / 100.0

        # Redness zones: (cx_frac, cy_frac, σ_frac, r_boost, g_scale, b_scale)
        zones = [
            (0.28, 0.48, 0.11, 1.18, 0.78, 0.74),  # left cheek
            (0.72, 0.48, 0.11, 1.18, 0.78, 0.74),  # right cheek
            (0.50, 0.60, 0.055, 1.22, 0.72, 0.68), # nose tip
            (0.50, 0.80, 0.075, 1.12, 0.80, 0.77), # chin
        ]

        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        result = img_array.copy() / 255.0
        base = result.copy()

        for cx_f, cy_f, sigma_f, r_b, g_s, b_s in zones:
            cx = w * cx_f
            cy = h * cy_f
            sigma = w * sigma_f
            dist2 = ((xx - cx)**2 + (yy - cy)**2) / (sigma**2)
            blob = np.exp(-0.5 * dist2)[:, :, np.newaxis]   # (H, W, 1)

            # Build tint colour from local skin + red shift
            tint = result.copy()
            tint[:, :, 0] = np.clip(result[:, :, 0] * r_b, 0, 1)
            tint[:, :, 1] = np.clip(result[:, :, 1] * g_s, 0, 1)
            tint[:, :, 2] = np.clip(result[:, :, 2] * b_s, 0, 1)

            # Soft-light blend the tinted zone
            blend_amt = blob * (0.08 + t * 0.30)
            soft_light = np.where(
                base < 0.5,
                base - (1.0 - 2.0 * tint) * base * (1.0 - base),
                base + (2.0 * tint - 1.0) * (np.sqrt(np.clip(base, 0, 1)) - base)
            )
            result = result * (1.0 - blend_amt) + soft_light * blend_amt

        return Image.fromarray(np.clip(result * 255.0, 0, 255).astype(np.uint8))

    def _apply_subsurface_scatter(self, img, strength, fitzpatrick=2):
        """
        Improvement #2: Subsurface scattering (SSS) simulation.

        Real skin is translucent — light enters the epidermis, scatters through
        the dermis, and exits nearby, producing the warm inner glow that makes
        living skin look different from plastic. We approximate this by:

          1. Creating a heavily blurred (radius = 8-18 px) copy of the image
          2. Tinting it with a warm SSS colour tuned to the Fitzpatrick skin tone:
               Types I-II:   light peachy-orange  (255, 210, 175)
               Types III-IV: warm golden-tan      (230, 175, 130)
               Types V-VI:   deep warm brown-red  (195, 130, 95)
          3. Screen-blending it at low opacity (3-18%) over the original.

        Screen blend: result = 1 - (1-base)*(1-blend)
        This only brightens — it can never darken — which is correct for SSS.
        """
        # SSS tint colours per Fitzpatrick group
        sss_tints = {
            1: (255, 215, 185),
            2: (250, 205, 175),
            3: (235, 180, 140),
            4: (220, 165, 120),
            5: (195, 135, 100),
            6: (175, 115, 85),
        }
        tint_rgb = sss_tints.get(fitzpatrick, sss_tints[2])

        img_array = np.array(img, dtype=np.float32) / 255.0
        t = strength / 100.0

        # Blur radius: 8-18 px (larger = more diffuse scatter)
        blur_radius = 8.0 + t * 10.0
        blurred = np.array(
            img.filter(ImageFilter.GaussianBlur(radius=blur_radius)),
            dtype=np.float32
        ) / 255.0

        # Tint the blurred layer with the SSS colour
        tint = np.array(tint_rgb, dtype=np.float32) / 255.0
        sss_layer = blurred * tint[np.newaxis, np.newaxis, :]

        # Screen blend: lifts warm midtones without blowing out highlights
        screened = 1.0 - (1.0 - img_array) * (1.0 - sss_layer)

        # Blend strength: 0.03-0.18
        alpha = 0.03 + t * 0.15
        result = img_array * (1.0 - alpha) + screened * alpha
        return Image.fromarray(np.clip(result * 255.0, 0, 255).astype(np.uint8))

    def _apply_peach_fuzz(self, img, strength, fitzpatrick=2, seed=0):
        """
        Improvement #3: Procedural vellus (peach fuzz) hair.

        Vellus hair covers ~95% of the human face and is one of the most
        consistently missing elements in AI portraits. Each hair is rendered as:
          - A short (4-14 px) curved Bézier-like micro-stroke
          - Oriented primarily downward (270°±40°) following gravity
          - Slightly lighter or darker than local skin (not a fixed colour)
          - Very low opacity per stroke (4-15%) — density creates the effect

        Colour is tuned to Fitzpatrick type:
          Types I-II:  nearly white / blonde, very subtle
          Types III-IV: light brown, slightly warm
          Types V-VI:  dark brown / near-black, more visible

        Hair is drawn by sampling pairs of points and Gaussian-blurring a line
        segment in a local patch (faster than full Bézier).
        """
        from scipy.ndimage import gaussian_filter as sp_gaussian

        img_array = np.array(img, dtype=np.float32)
        h, w = img_array.shape[:2]
        t = strength / 100.0
        rng = np.random.default_rng(seed=seed + 300)

        # Number of hairs: 200 → 3000
        n_hairs = int(200 + t ** 1.1 * 2800)

        # Hair colour offset by Fitzpatrick type
        # Positive = lighter than skin, negative = darker
        fitz_params = {
            1: (+0.35, 0.06),   # very blonde/white, very low contrast
            2: (+0.25, 0.08),
            3: (-0.05, 0.10),   # near-skin colour
            4: (-0.15, 0.12),
            5: (-0.25, 0.14),
            6: (-0.38, 0.16),   # dark, more visible
        }
        brightness_offset, max_opacity_base = fitz_params.get(fitzpatrick, fitz_params[3])

        result = img_array.copy()

        for _ in range(n_hairs):
            # Start point anywhere in the face area
            cx = int(rng.uniform(w * 0.08, w * 0.92))
            cy = int(rng.uniform(h * 0.08, h * 0.88))

            # Hair length: 4-14 px, direction: mostly downward ±40°
            length = rng.uniform(4.0, 4.0 + 10.0 * t ** 0.7)
            angle = rng.normal(np.pi / 2.0, np.radians(38))   # 90° = straight down
            dx = int(np.cos(angle) * length)
            dy = int(np.sin(angle) * length)

            ex = int(np.clip(cx + dx, 0, w - 1))
            ey = int(np.clip(cy + dy, 0, h - 1))

            # Draw a thin line segment by stepping along it
            steps = max(2, int(length))
            px_list = np.round(np.linspace(cx, ex, steps)).astype(int)
            py_list = np.round(np.linspace(cy, ey, steps)).astype(int)
            px_list = np.clip(px_list, 0, w - 1)
            py_list = np.clip(py_list, 0, h - 1)

            # Sample local skin colour at start point
            local = img_array[cy, cx].astype(np.float32)
            hair_colour = np.clip(local + brightness_offset * 255.0, 0, 255)

            # Per-hair opacity
            opacity = rng.uniform(0.04, max_opacity_base) * (0.3 + t * 0.7)

            for px, py in zip(px_list, py_list):
                result[py, px] = result[py, px] * (1.0 - opacity) + hair_colour * opacity

        # Lightly blur the hair layer to soften pixel-level aliasing
        hair_layer = result - img_array
        hair_blurred = sp_gaussian(hair_layer, sigma=0.35, axes=(0, 1))
        result = np.clip(img_array + hair_blurred, 0, 255)

        return Image.fromarray(result.astype(np.uint8))

    def _apply_sebum_shine(self, img, strength, seed=0):
        """
        Improvement #5: T-zone sebum / oil shine.

        The forehead, nose bridge, and chin produce more sebum than other areas,
        giving them a characteristic specular sheen. This is rendered as a field
        of small bright ellipses in the T-zone, Screen-blended at low opacity.

        T-zone anatomy (portrait-relative coordinates):
          - Forehead strip: y ∈ [0.08, 0.30], x ∈ [0.25, 0.75]
          - Nose bridge:    y ∈ [0.30, 0.65], x ∈ [0.42, 0.58]
          - Chin:           y ∈ [0.75, 0.90], x ∈ [0.38, 0.62]
        """
        img_array = np.array(img, dtype=np.float32) / 255.0
        h, w = img_array.shape[:2]
        t = strength / 100.0
        rng = np.random.default_rng(seed=seed + 600)

        # T-zone placement boxes (y0_f, y1_f, x0_f, x1_f, weight)
        zones = [
            (0.08, 0.30, 0.22, 0.78, 0.45),   # forehead
            (0.30, 0.65, 0.41, 0.59, 0.35),   # nose bridge
            (0.75, 0.90, 0.37, 0.63, 0.20),   # chin
        ]

        n_highlights = int(15 + t ** 1.1 * 185)
        result = img_array.copy()
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)

        for _ in range(n_highlights):
            # Pick a zone weighted by area
            zone_weights = [z[4] for z in zones]
            zone_weights = np.array(zone_weights) / sum(zone_weights)
            zi = rng.choice(len(zones), p=zone_weights)
            y0_f, y1_f, x0_f, x1_f, _ = zones[zi]

            cy = rng.uniform(h * y0_f, h * y1_f)
            cx = rng.uniform(w * x0_f, w * x1_f)

            # Highlight size: 1.5-8 px radius
            r = rng.uniform(1.5, 1.5 + 6.5 * t ** 0.6)
            aspect = rng.uniform(0.6, 1.0)
            angle = rng.uniform(0, np.pi)
            cos_a, sin_a = np.cos(angle), np.sin(angle)

            pad = int(r * 3) + 2
            y0i, y1i = max(0, int(cy)-pad), min(h, int(cy)+pad+1)
            x0i, x1i = max(0, int(cx)-pad), min(w, int(cx)+pad+1)
            yy_p = yy[y0i:y1i, x0i:x1i]
            xx_p = xx[y0i:y1i, x0i:x1i]

            dxr =  cos_a * (xx_p - cx) + sin_a * (yy_p - cy)
            dyr = -sin_a * (xx_p - cx) + cos_a * (yy_p - cy)
            d2 = (dxr / r) ** 2 + (dyr / (r * aspect)) ** 2
            spot = np.exp(-2.0 * d2)[:, :, np.newaxis]

            # Screen blend: bright specular highlight
            opacity = rng.uniform(0.06, 0.22) * (0.3 + t * 0.7)
            base_p = result[y0i:y1i, x0i:x1i]
            highlight = np.ones_like(base_p) * rng.uniform(0.92, 1.0)
            screened = 1.0 - (1.0 - base_p) * (1.0 - highlight)
            result[y0i:y1i, x0i:x1i] = base_p * (1.0 - spot * opacity) + screened * spot * opacity

        return Image.fromarray(np.clip(result * 255.0, 0, 255).astype(np.uint8))

    def _apply_skin_texture(self, img, strength, opacity=1.0, seed=0):
        """
        Break the AI 'plastic skin' look. opacity: final blend (0-1). seed: noise pattern.
        """
        img_array = np.array(img, dtype=np.float32)
        h, w = img_array.shape[:2]
        t = strength / 100.0
        hp_alpha  = 0.12 + t * 0.55
        noise_amt = 3.0 + t * 18.0
        hp_radius = 1.8 + t * 2.2
        blurred = np.array(img.filter(ImageFilter.GaussianBlur(radius=hp_radius)), dtype=np.float32)
        high_pass = (img_array - blurred) + 128.0
        linear_light = img_array + 2.0 * (high_pass - 128.0)
        layer_a = img_array * (1.0 - hp_alpha) + linear_light * hp_alpha
        rng = np.random.default_rng(seed=seed + 99)
        noise = rng.normal(0.0, noise_amt, (h, w)).astype(np.float32)
        from scipy.ndimage import gaussian_filter as sp_gaussian
        noise = sp_gaussian(noise, sigma=0.4)
        noise_rgb = np.stack([noise, noise, noise], axis=-1)
        base = np.clip(layer_a, 0, 255) / 255.0
        blend = np.clip((noise_rgb + 128.0), 0, 255) / 255.0
        overlay = np.where(base < 0.5, 2.0*base*blend, 1.0 - 2.0*(1.0-base)*(1.0-blend))
        noise_alpha = 0.08 + t * 0.22
        combined = base * (1.0 - noise_alpha) + overlay * noise_alpha
        original_f = img_array / 255.0
        result = original_f * (1.0 - opacity) + combined * opacity
        return Image.fromarray(np.clip(result * 255.0, 0, 255).astype(np.uint8))

    def _apply_pores(self, img, strength, opacity=1.0, seed=0):
        """
        Simulate visible skin pores as dark, slightly elliptical indentations
        concentrated in the T-zone (forehead, nose, chin) where sebaceous glands
        are densest, as documented by clinical pore research.

        Pore anatomy: each pore is a small dark pit (the follicle opening) with
        a slightly brighter rim (the surrounding epidermis catching light). We
        render this with three components:

          1. A field of tiny dark ellipses placed on a Perlin-like grid
             so spacing is semi-regular (like real follicles) rather than
             purely random.
          2. A high-pass DoG layer (r_fine=0.6, r_coarse=1.8 px) that picks
             up any existing pore-like detail in the source image and deepens it.
          3. A very subtle brightness dip over the whole T-zone to suggest
             the coarser pore density there.

        Recommended range: 10-20 subtle, 25-45 natural, 50-70 enlarged/oily.
        """
        from scipy.ndimage import gaussian_filter as sp_gaussian
        img_array = np.array(img, dtype=np.float32)
        h, w = img_array.shape[:2]
        t = strength / 100.0

        # --- Component 1: procedural pore field -----------------------------
        # Grid spacing: ~8-4 px depending on strength (denser at higher strength)
        spacing = max(3, int(9 - t * 5))
        rng = np.random.default_rng(seed=seed + 17)

        pore_layer = np.zeros((h, w), dtype=np.float32)
        # Iterate grid nodes and jitter positions
        for gy in range(0, h, spacing):
            for gx in range(0, w, spacing):
                # Skip ~30% of grid positions for organic irregularity
                if rng.random() < 0.30:
                    continue
                # Jitter up to half a spacing unit
                jit = spacing // 2
                cy = int(np.clip(gy + rng.integers(-jit, jit + 1), 0, h - 1))
                cx = int(np.clip(gx + rng.integers(-jit, jit + 1), 0, w - 1))

                # Pore radius: 0.8–2.5 px
                pr = rng.uniform(0.8, 0.8 + 1.7 * t)
                # Slight ellipse
                aspect = rng.uniform(0.70, 1.0)
                angle  = rng.uniform(0, np.pi)
                cos_a, sin_a = np.cos(angle), np.sin(angle)

                # Only paint a small local patch for speed
                pad = int(pr * 3) + 2
                y0, y1 = max(0, cy - pad), min(h, cy + pad + 1)
                x0, x1 = max(0, cx - pad), min(w, cx + pad + 1)
                yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
                dx = xx - cx
                dy = yy - cy
                dx_r =  cos_a * dx + sin_a * dy
                dy_r = -sin_a * dx + cos_a * dy
                d2 = (dx_r / pr) ** 2 + (dy_r / (pr * aspect)) ** 2
                # Dark pit
                pore_layer[y0:y1, x0:x1] -= np.exp(-2.0 * d2) * rng.uniform(0.4, 0.9)

        # Normalise pore layer to [-1, 0]
        pore_layer = np.clip(pore_layer, -1.0, 0.0)

        # --- Component 2: DoG depth-of-existing-structure -------------------
        fine   = np.array(img.filter(ImageFilter.GaussianBlur(radius=0.6)), dtype=np.float32)
        coarse = np.array(img.filter(ImageFilter.GaussianBlur(radius=1.8)), dtype=np.float32)
        dog = (fine - coarse)   # positive = bright rim, negative = dark pit
        # Only keep the dark-pit side and desaturate to luminance
        dog_lum = 0.299*dog[:,:,0] + 0.587*dog[:,:,1] + 0.114*dog[:,:,2]
        dog_dark = np.clip(dog_lum, -30, 0) / 30.0   # in [-1, 0]

        # Combine: pore field + deepened existing structure
        combined = pore_layer * (0.6 + t * 0.3) + dog_dark * (0.3 + t * 0.4)

        # --- Darken skin via combined map -----------------------------------
        # Multiply luminance: combined is ≤ 0, so this only darkens
        darkness = 1.0 + combined * (0.25 + t * 0.35)
        darkness = np.clip(darkness, 0.0, 1.0)[:, :, np.newaxis]
        processed = np.clip(img_array * darkness, 0, 255).astype(np.float32)
        # Apply per-effect opacity
        result = img_array * (1.0 - opacity) + processed * opacity
        return Image.fromarray(np.clip(result, 0, 255).astype(np.uint8))

    def _apply_freckles(self, img, strength, fitzpatrick=2, opacity=1.0, seed=0):
        """
        Render ephelides (classic sun freckles) with clinically accurate properties:

          • Flat, not raised — pure pigment change, no emboss/bump.
          • Small: 1–5 mm diameter. At typical portrait resolutions (512–1024 px
            for a face ~150 mm wide) that maps to roughly 3–35 px diameter, so
            radius 1.5–17 px. Size distribution skews small (most freckles < 3 mm).
          • Colour: reddish-tan to warm brown, always darker than surrounding skin.
            The R channel stays proportional; G drops ~10-25%; B drops ~25-45%.
            This matches the warm/golden-brown of pheomelanin in fair skin.
          • Soft irregular edges: Gaussian falloff with slight wobble in the radius
            (±15%) so spots look organic rather than mathematically perfect.
          • Distribution: concentrated on nose bridge and cheeks (sun-exposed), with
            sparse scatter on forehead. Symmetric but not perfectly mirrored.
          • Opacity varies per spot (0.30–0.75) — darker for bigger spots.

        Recommended range: 10-20 very light, 25-50 natural coverage, 55-100 dense.
        """
        img_array = np.array(img, dtype=np.float32)
        h, w = img_array.shape[:2]
        t = strength / 100.0

        # Number: 8 → 350 spots (power curve so low strengths stay subtle)
        n_freckles = int(8 + t ** 1.3 * 342)

        rng = np.random.default_rng(seed=seed + 42)
        result = img_array.copy()

        # We'll weight placement toward cheeks (left/right) and nose bridge (centre)
        # by sampling from a mixture of three Gaussian zones
        face_cx = w * 0.5
        face_cy = h * 0.42   # slightly above centre — nose/cheek area
        # σ values for the placement distributions
        sx = w * 0.22
        sy = h * 0.18

        # Pre-build coordinate grids once
        yy_full, xx_full = np.mgrid[0:h, 0:w].astype(np.float32)

        for _ in range(n_freckles):
            # Sample placement with Gaussian bias toward face centre
            cx = int(np.clip(rng.normal(face_cx, sx), w * 0.10, w * 0.90))
            cy = int(np.clip(rng.normal(face_cy, sy), h * 0.10, h * 0.75))

            # Radius: skew small — most freckles are 1-3 mm
            # Use exponential-ish distribution: most ~2 px, max scales with strength
            r_base = rng.exponential(scale=1.5 + t * 4.5)
            r_base = np.clip(r_base, 1.2, 2.0 + t * 15.0)

            # Irregular edge: wobble radius by ±15%
            aspect = rng.uniform(0.75, 1.0)
            angle  = rng.uniform(0, np.pi)
            cos_a, sin_a = np.cos(angle), np.sin(angle)

            # Paint only over a local patch
            pad = int(r_base * 4) + 3
            y0, y1 = max(0, cy - pad), min(h, cy + pad + 1)
            x0, x1 = max(0, cx - pad), min(w, cx + pad + 1)
            yy = yy_full[y0:y1, x0:x1]
            xx = xx_full[y0:y1, x0:x1]

            dx = xx - cx
            dy = yy - cy
            dx_r =  cos_a * dx + sin_a * dy
            dy_r = -sin_a * dx + cos_a * dy
            # Add mild radius wobble for organic edge
            wobble = 1.0 + 0.15 * np.sin(np.arctan2(dy_r, dx_r) * rng.integers(3, 7))
            d2 = (dx_r / (r_base * wobble)) ** 2 + (dy_r / (r_base * aspect * wobble)) ** 2
            mask = np.exp(-2.5 * d2)   # soft Gaussian falloff

            # Freckle colour: warm pheomelanin shift
            # Sample local average skin tone (3×3 patch to avoid hitting hair/eyes)
            py0, py1 = max(0, cy-1), min(h, cy+2)
            px0, px1 = max(0, cx-1), min(w, cx+2)
            local = img_array[py0:py1, px0:px1].mean(axis=(0, 1))
            lr, lg, lb = float(local[0]), float(local[1]), float(local[2])

            # Darken and warm: R stays close, G drops moderately, B drops most
            dark = rng.uniform(0.48, 0.72)
            fr = np.clip(lr * dark * rng.uniform(0.92, 1.08), 0, 255)
            fg = np.clip(lg * dark * rng.uniform(0.72, 0.88), 0, 255)
            fb = np.clip(lb * dark * rng.uniform(0.45, 0.65), 0, 255)

            # Per-spot opacity; scale with strength
            spot_opacity = rng.uniform(0.30, 0.68) * (0.35 + t * 0.65)
            spot_opacity = min(spot_opacity, 0.82)

            alpha = mask * spot_opacity
            for c, fc in enumerate([fr, fg, fb]):
                result[y0:y1, x0:x1, c] = (
                    result[y0:y1, x0:x1, c] * (1.0 - alpha) + fc * alpha
                )

        # Apply per-effect opacity: blend result back toward original
        final = img_array * (1.0 - opacity) + result * opacity
        return Image.fromarray(np.clip(final, 0, 255).astype(np.uint8))

    def _apply_blemishes(self, img, strength, fitzpatrick=2, opacity=1.0, seed=0):
        """
        Render post-inflammatory hyperpigmentation (PIH) and flat pigmentation
        blemishes — the kind left by healed spots, sun exposure, or hormonal
        changes. These are FLAT marks (no raised geometry), distinguishing them
        from acne.

        Visual properties:
          • Irregular elliptical shapes with diffuse edges (larger Gaussian falloff)
          • Warm brown to reddish-brown, darker than surrounding skin
          • Variable opacity — older marks more faded, fresh ones more vivid
          • Often slightly desaturated toward grey-brown rather than vivid red
          • Distributed across full face; cheeks and forehead most common
          • Sometimes cluster in groups of 2-3 nearby spots

        Recommended range: 10-20 a few marks, 25-50 noticeable, 55-100 heavy PIH.
        """
        img_array = np.array(img, dtype=np.float32)
        h, w = img_array.shape[:2]
        t = strength / 100.0

        # Number: 3 → 55 (includes cluster groups so actual visual density is higher)
        n_primary = max(3, int(3 + t ** 1.1 * 52))
        rng = np.random.default_rng(seed=seed + 7)
        result = img_array.copy()
        yy_full, xx_full = np.mgrid[0:h, 0:w].astype(np.float32)

        for _ in range(n_primary):
            # Placement: full face but weighted toward central zones
            cx = int(rng.uniform(w * 0.12, w * 0.88))
            cy = int(rng.uniform(h * 0.08, h * 0.88))

            # Blemish radius: 5–28 px (larger than freckles, smaller than large patches)
            r = rng.uniform(5.0, 5.0 + 23.0 * t ** 0.7)
            aspect = rng.uniform(0.55, 1.0)
            angle = rng.uniform(0, np.pi)
            cos_a, sin_a = np.cos(angle), np.sin(angle)

            pad = int(r * 3.5) + 4
            y0, y1 = max(0, cy - pad), min(h, cy + pad + 1)
            x0, x1 = max(0, cx - pad), min(w, cx + pad + 1)
            yy = yy_full[y0:y1, x0:x1]
            xx = xx_full[y0:y1, x0:x1]

            dx = xx - cx
            dy = yy - cy
            dx_r =  cos_a * dx + sin_a * dy
            dy_r = -sin_a * dx + cos_a * dy
            d2 = (dx_r / r) ** 2 + (dy_r / (r * aspect)) ** 2
            # Use a wider falloff than freckles — blemishes have more diffuse edges
            mask = np.exp(-1.2 * d2)

            # Colour: haemoglobin/melanin tint — brownish-red, not vivid red
            py0, py1 = max(0, cy-2), min(h, cy+3)
            px0, px1 = max(0, cx-2), min(w, cx+3)
            local = img_array[py0:py1, px0:px1].mean(axis=(0, 1))
            lr, lg, lb = float(local[0]), float(local[1]), float(local[2])

            # Type A: brown melanin spot
            if rng.random() < 0.65:
                dark = rng.uniform(0.52, 0.80)
                br = np.clip(lr * dark * rng.uniform(0.88, 1.05), 0, 255)
                bg = np.clip(lg * dark * rng.uniform(0.62, 0.78), 0, 255)
                bb = np.clip(lb * dark * rng.uniform(0.48, 0.62), 0, 255)
            # Type B: reddish haemoglobin post-inflammation mark
            else:
                dark = rng.uniform(0.60, 0.85)
                br = np.clip(lr * dark * rng.uniform(0.98, 1.18), 0, 255)
                bg = np.clip(lg * dark * rng.uniform(0.55, 0.72), 0, 255)
                bb = np.clip(lb * dark * rng.uniform(0.50, 0.68), 0, 255)

            spot_opacity = rng.uniform(0.18, 0.52) * (0.4 + t * 0.6)
            alpha = mask * spot_opacity
            for c, bc in enumerate([br, bg, bb]):
                result[y0:y1, x0:x1, c] = (
                    result[y0:y1, x0:x1, c] * (1.0 - alpha) + bc * alpha
                )

            # Optional satellite: 1-2 smaller nearby marks (clusters)
            if rng.random() < 0.40:
                for _ in range(rng.integers(1, 3)):
                    ox = int(np.clip(cx + rng.integers(-int(r*2), int(r*2)+1), 0, w-1))
                    oy = int(np.clip(cy + rng.integers(-int(r*2), int(r*2)+1), 0, h-1))
                    sr = r * rng.uniform(0.25, 0.6)
                    pad2 = int(sr * 3) + 2
                    sy0, sy1 = max(0, oy-pad2), min(h, oy+pad2+1)
                    sx0, sx1 = max(0, ox-pad2), min(w, ox+pad2+1)
                    yys = yy_full[sy0:sy1, sx0:sx1]
                    xxs = xx_full[sy0:sy1, sx0:sx1]
                    sd2 = ((xxs-ox)**2 + (yys-oy)**2) / (sr**2 + 1e-6)
                    smask = np.exp(-1.5 * sd2) * rng.uniform(0.5, 0.9) * spot_opacity
                    for c, bc in enumerate([br, bg, bb]):
                        result[sy0:sy1, sx0:sx1, c] = (
                            result[sy0:sy1, sx0:sx1, c] * (1.0 - smask) + bc * smask
                        )

        # Apply per-effect opacity
        final = img_array * (1.0 - opacity) + result * opacity
        return Image.fromarray(np.clip(final, 0, 255).astype(np.uint8))

    def _apply_acne(self, img, strength, opacity=1.0, seed=0):
        """
        Render inflammatory acne lesions (papules and pustules) with clinically
        accurate layered anatomy:

        PAPULE (closed comedone, ~70% of spots):
          • No pus — the centre is a darker reddish-brown solid bump
          • 4 layers: wide diffuse redness halo → narrower bright-red ring →
            dark brownish papule core → very faint edge shadow

        PUSTULE (~30% of spots):
          • Has a central white/yellow pus dome
          • Same inflamed surround as papule but core is lighter
          • Small specular catch-light offset toward upper-left

        Both types show the haemoglobin erythema (redness) that is the
        hallmark of inflammatory acne — R channel boosted, G/B suppressed.

        Distribution: T-zone (forehead, nose, chin) and cheeks — avoiding
        the eye area and the very edges of the face.

        Recommended range: 10-20 a few spots, 25-50 moderate, 55-100 severe.
        """
        img_array = np.array(img, dtype=np.float32)
        h, w = img_array.shape[:2]
        t = strength / 100.0

        # Number of lesions: 1 → 45
        n_spots = max(1, int(1 + t ** 1.2 * 44))

        # T-zone + cheeks — exclude extreme edges and top of frame (hair)
        zone_y0 = int(h * 0.18)
        zone_y1 = int(h * 0.82)
        zone_x0 = int(w * 0.14)
        zone_x1 = int(w * 0.86)

        rng = np.random.default_rng(seed=seed + 13)
        result = img_array.copy()
        yy_full, xx_full = np.mgrid[0:h, 0:w].astype(np.float32)

        for _ in range(n_spots):
            cy = int(rng.integers(zone_y0, zone_y1))
            cx = int(rng.integers(zone_x0, zone_x1))

            # Core radius: 3–14 px
            r_core = rng.uniform(3.0, 3.0 + 11.0 * t ** 0.65)
            is_pustule = rng.random() < 0.30   # 30% are pustules

            # Sample local skin tone from a patch away from any previous spots
            py0, py1 = max(0, cy-2), min(h, cy+3)
            px0, px1 = max(0, cx-2), min(w, cx+3)
            local = img_array[py0:py1, px0:px1].mean(axis=(0, 1))
            lr, lg, lb = float(local[0]), float(local[1]), float(local[2])

            pad = int(r_core * 4) + 4
            y0, y1 = max(0, cy - pad), min(h, cy + pad + 1)
            x0, x1 = max(0, cx - pad), min(w, cx + pad + 1)
            yy = yy_full[y0:y1, x0:x1]
            xx = xx_full[y0:y1, x0:x1]
            dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)

            # ------ Layer 1: wide diffuse erythema halo (largest, palest red) ------
            r_halo = r_core * rng.uniform(2.8, 3.5)
            halo_mask = np.exp(-0.5 * (dist / r_halo) ** 2)
            h_opacity = rng.uniform(0.18, 0.38) * (0.5 + t * 0.5)
            h_r = np.clip(lr * rng.uniform(1.08, 1.22), 0, 255)
            h_g = np.clip(lg * rng.uniform(0.72, 0.85), 0, 255)
            h_b = np.clip(lb * rng.uniform(0.68, 0.80), 0, 255)
            for c, hc in enumerate([h_r, h_g, h_b]):
                result[y0:y1, x0:x1, c] = (
                    result[y0:y1, x0:x1, c] * (1.0 - halo_mask * h_opacity)
                    + hc * halo_mask * h_opacity
                )

            # ------ Layer 2: tighter bright-red inflammatory ring ----------------
            r_ring = r_core * rng.uniform(1.6, 2.0)
            ring_mask = np.exp(-0.5 * (dist / r_ring) ** 2)
            ri_opacity = rng.uniform(0.28, 0.50) * (0.5 + t * 0.5)
            ri_r = np.clip(lr * rng.uniform(1.12, 1.30), 0, 255)
            ri_g = np.clip(lg * rng.uniform(0.55, 0.70), 0, 255)
            ri_b = np.clip(lb * rng.uniform(0.50, 0.65), 0, 255)
            for c, rc in enumerate([ri_r, ri_g, ri_b]):
                result[y0:y1, x0:x1, c] = (
                    result[y0:y1, x0:x1, c] * (1.0 - ring_mask * ri_opacity)
                    + rc * ring_mask * ri_opacity
                )

            # ------ Layer 3: central lesion core --------------------------------
            core_mask = np.exp(-0.5 * (dist / r_core) ** 2)
            c_opacity = rng.uniform(0.55, 0.82) * (0.5 + t * 0.5)
            if is_pustule:
                # Pustule centre: creamy white/yellow
                c_r = np.clip(lr * rng.uniform(1.05, 1.18), 0, 255)
                c_g = np.clip(lg * rng.uniform(0.95, 1.08), 0, 255)
                c_b = np.clip(lb * rng.uniform(0.72, 0.85), 0, 255)
            else:
                # Papule centre: dark brownish-red
                dark = rng.uniform(0.42, 0.65)
                c_r = np.clip(lr * dark * rng.uniform(0.88, 1.05), 0, 255)
                c_g = np.clip(lg * dark * rng.uniform(0.50, 0.65), 0, 255)
                c_b = np.clip(lb * dark * rng.uniform(0.45, 0.60), 0, 255)
            for c, cc in enumerate([c_r, c_g, c_b]):
                result[y0:y1, x0:x1, c] = (
                    result[y0:y1, x0:x1, c] * (1.0 - core_mask * c_opacity)
                    + cc * core_mask * c_opacity
                )

            # ------ Layer 4: specular catch-light (pustules and some papules) ----
            if is_pustule or (rng.random() < 0.45):
                offset = max(1, int(r_core * 0.4))
                hy = max(0, cy - offset)
                hx = max(0, cx - offset)
                r_spec = max(0.7, r_core * 0.25)
                spec_dist = np.sqrt((xx - hx) ** 2 + (yy - hy) ** 2)
                spec_mask = np.exp(-0.5 * (spec_dist / r_spec) ** 2)
                spec_opacity = rng.uniform(0.50, 0.85) * (0.4 + t * 0.3)
                # Additive white highlight
                for c in range(3):
                    result[y0:y1, x0:x1, c] = np.clip(
                        result[y0:y1, x0:x1, c] + spec_mask * spec_opacity * (
                            255.0 - result[y0:y1, x0:x1, c]
                        ) * 0.55,
                        0, 255
                    )

        # Apply per-effect opacity
        final = img_array * (1.0 - opacity) + result * opacity
        return Image.fromarray(np.clip(final, 0, 255).astype(np.uint8))

    def _apply_pixelation(self, img, strength):
        """
        Apply real pixelation by downscaling to a reduced resolution grid
        and scaling back up with nearest-neighbour interpolation, producing
        hard-edged pixel blocks.

        strength 1  → very subtle (large blocks only at high resolution)
        strength 100 → extreme pixelation (very coarse grid)
        """
        w, h = img.size
        # Map strength 1-100 to a scale factor range 0.5 → 0.02
        # (i.e. keep between 50% and 2% of original pixels)
        scale = max(0.02, 0.5 - (strength - 1) * (0.48 / 99))
        small_w = max(1, int(round(w * scale)))
        small_h = max(1, int(round(h * scale)))
        # Downscale (nearest) then upscale (nearest) to get hard pixel blocks
        img_small = img.resize((small_w, small_h), Image.NEAREST)
        return img_small.resize((w, h), Image.NEAREST)

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
