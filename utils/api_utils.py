from pathlib import Path
from fastapi import UploadFile, HTTPException
import uuid
from models.settings import settings


def validate_document(file: UploadFile) -> bytes:
    """
    Valida que el archivo subido sea una imagen válida y cumple con las restricciones de tamaño.
    Solo acepta imágenes (JPG, PNG, TIFF, BMP). No soporta PDFs.

    Args:
        file: Archivo subido por el usuario.

    Returns:
        El contenido del archivo en bytes.

    Raises:
        HTTPException: Si el archivo no es válido.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="El archivo debe tener un nombre")

    # Extensiones permitidas (solo imágenes)
    image_extensions = ['.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp']
    
    filename_lower = file.filename.lower()
    is_image = any(filename_lower.endswith(ext) for ext in image_extensions)
    
    if not is_image:
        allowed_formats = ", ".join(image_extensions)
        raise HTTPException(
            status_code=400, 
            detail=f"Solo se aceptan imágenes. Formatos permitidos: {allowed_formats}"
        )

    # Leer contenido del archivo
    file_content = file.file.read()
    file_size_mb = len(file_content) / (1024 * 1024)

    # Validar tamaño de imagen
    max_size = settings.max_image_size_mb
    if file_size_mb > max_size:
        raise HTTPException(
            status_code=413,
            detail=f"Imagen demasiado grande: {file_size_mb:.1f}MB. Máximo permitido: {max_size}MB"
        )
    
    # Validar firmas básicas de imagen
    if not _is_valid_image_content(file_content, filename_lower):
        raise HTTPException(status_code=400, detail="El archivo no es una imagen válida")

    return file_content


def _is_valid_image_content(content: bytes, filename: str) -> bool:
    """
    Valida que el contenido sea una imagen válida basándose en magic bytes.
    
    Args:
        content: Contenido del archivo en bytes
        filename: Nombre del archivo (para extensión)
        
    Returns:
        True si es una imagen válida
    """
    if not content:
        return False
    
    # Magic bytes para diferentes formatos de imagen
    magic_bytes = {
        'jpg': [b'\xff\xd8\xff'],
        'jpeg': [b'\xff\xd8\xff'],
        'png': [b'\x89\x50\x4e\x47'],
        'tiff': [b'\x49\x49\x2a\x00', b'\x4d\x4d\x00\x2a'],
        'tif': [b'\x49\x49\x2a\x00', b'\x4d\x4d\x00\x2a'],
        'bmp': [b'\x42\x4d']
    }
    
    # Obtener extensión del archivo
    ext = filename.split('.')[-1].lower() if '.' in filename else ''
    
    # Verificar magic bytes
    if ext in magic_bytes:
        return any(content.startswith(magic) for magic in magic_bytes[ext])
    
    return False


def save_temp_file(file_content: bytes, filename: str, temp_dir: Path) -> Path:
    """
    Guarda el contenido del archivo en un archivo temporal.

    Args:
        file_content: Contenido del archivo en bytes.
        filename: Nombre original del archivo.
        temp_dir: Directorio temporal donde guardar el archivo.

    Returns:
        La ruta al archivo temporal creado.
    """
    temp_dir.mkdir(exist_ok=True)
    temp_filename = f"upload_{uuid.uuid4().hex}_{filename}"
    temp_file_path = temp_dir / temp_filename

    with open(temp_file_path, 'wb') as temp_file:
        temp_file.write(file_content)

    return temp_file_path