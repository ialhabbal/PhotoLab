from .photo_lab import PhotoLab

NODE_CLASS_MAPPINGS = {
    "PhotoLab": PhotoLab,
}

# Tells ComfyUI to serve all files inside the /js/ subfolder as web assets.
WEB_DIRECTORY = "./js"

__all__ = ['NODE_CLASS_MAPPINGS', 'WEB_DIRECTORY']
