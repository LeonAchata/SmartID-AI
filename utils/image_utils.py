import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Imports opcionales
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Pillow no disponible: {e}")
    PIL_AVAILABLE = False

# Constantes
SUPPORTED_IMAGE_FORMATS = {'.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp'}


def is_image_file(file_path: Path) -> bool:
    """Verifica si el archivo es una imagen soportada."""
    return file_path.suffix.lower() in SUPPORTED_IMAGE_FORMATS


def validate_image_dependencies():
    """Valida que Pillow esté disponible."""
    if not PIL_AVAILABLE:
        raise ImportError("Pillow no está instalado. Instalar con: pip install Pillow")