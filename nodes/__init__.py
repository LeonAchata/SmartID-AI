# Nodos simplificados del pipeline (solo imágenes)
from .image_processing import image_processing_node
from .llm import llm_node

import logging

logger = logging.getLogger(__name__)
logger.info(f"Nodos del pipeline inicializados")

handler = logging.StreamHandler()
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
handler.setFormatter(formatter)
logger.addHandler(handler)