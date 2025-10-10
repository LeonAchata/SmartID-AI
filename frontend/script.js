// ================================
// CONFIGURACIÓN Y VARIABLES GLOBALES
// ================================

const API_BASE_URL = 'http://localhost:8000';
let currentJobId = null;
let pollingInterval = null;
let lastSavedData = null;

// Referencias a elementos DOM
const uploadArea = document.getElementById('uploadArea');
const fileInput = document.getElementById('fileInput');
const statusIndicator = document.getElementById('statusIndicator');
const loadingSpinner = document.getElementById('loadingSpinner');
const progressContainer = document.getElementById('progressContainer');
const progressFill = document.getElementById('progressFill');
const progressText = document.getElementById('progressText');
const form = document.getElementById('documentForm');
const downloadSection = document.getElementById('download-section');

// ================================
// CONFIGURACIÓN DE EVENTOS
// ================================

// Eventos de drag & drop
uploadArea.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadArea.classList.add('dragover');
});

uploadArea.addEventListener('dragleave', () => {
    uploadArea.classList.remove('dragover');
});

uploadArea.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadArea.classList.remove('dragover');
    
    const files = e.dataTransfer.files;
    if (files.length > 0) {
        handleFileSelection(files[0]);
    } else {
        showStatus('error', 'Por favor selecciona un archivo válido');
    }
});

// Evento de click en área de upload
uploadArea.addEventListener('click', () => {
    fileInput.click();
});

// Evento de selección de archivo
fileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
        handleFileSelection(e.target.files[0]);
    }
});

// Evento de envío del formulario
form.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const formData = collectFormData();
    
    try {
        showStatus('processing', 'Generando archivo TXT...');
        
        // Generar contenido del archivo TXT
        const txtContent = generateTxtContent(formData);
        
        // Crear y descargar archivo
        downloadTxtFile(txtContent, `documento_identidad_${getCurrentTimestamp()}.txt`);
        
        // Guardar datos para posterior descarga
        lastSavedData = { content: txtContent, data: formData };
        
        showStatus('success', '✅ Archivo TXT generado exitosamente');
        showDownloadSection();
        
    } catch (error) {
        console.error('Error generando archivo:', error);
        showStatus('error', `Error: ${error.message}`);
    }
});

// ================================
// FUNCIONES PRINCIPALES DE PROCESAMIENTO
// ================================

async function handleFileSelection(file) {
    const allowedTypes = ['application/pdf', 'image/png', 'image/jpeg', 'image/jpg', 'image/tiff', 'image/tif', 'image/bmp'];
    const allowedExtensions = ['.pdf', '.png', '.jpg', '.jpeg', '.tiff', '.tif', '.bmp'];
    
    // Validar tipo de archivo
    const fileExtension = file.name.toLowerCase().substring(file.name.lastIndexOf('.'));
    if (!allowedTypes.includes(file.type) && !allowedExtensions.includes(fileExtension)) {
        showStatus('error', 'Solo se permiten archivos PDF e imágenes (PNG, JPG, TIFF, BMP)');
        return;
    }

    if (file.size > 20 * 1024 * 1024) { // 20MB límite
        showStatus('error', 'El archivo es demasiado grande (máximo 20MB)');
        return;
    }

    // Limpiar cualquier polling anterior
    if (pollingInterval) {
        clearInterval(pollingInterval);
        pollingInterval = null;
    }

    try {
        // Fase 1: Upload
        showStatus('processing', `Subiendo: ${file.name}`);
        showLoading(true);
        updateProgress(10, 'Subiendo archivo...');

        const uploadResult = await uploadFile(file);
        currentJobId = uploadResult.job_id;

        // Fase 2: Polling para estado
        updateProgress(20, 'Procesamiento iniciado...');
        showStatus('processing', `Procesando: ${file.name}`);
        
        startPolling(currentJobId);

    } catch (error) {
        console.error('Error:', error);
        showStatus('error', `❌ Error: ${error.message}`);
        hideProgress();
        showLoading(false);
    }
}

async function uploadFile(file) {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(`${API_BASE_URL}/upload`, {
        method: 'POST',
        body: formData
    });

    if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Error del servidor: ${response.status} - ${errorText}`);
    }

    return await response.json();
}

function startPolling(jobId) {
    let attempts = 0;
    const maxAttempts = 60; // 2 minutos máximo

    pollingInterval = setInterval(async () => {
        attempts++;
        
        try {
            const status = await checkJobStatus(jobId);
            
            switch (status.status) {
                case 'PENDING':
                    updateProgress(30, 'En cola de procesamiento...');
                    break;
                    
                case 'PROCESSING':
                    updateProgress(60, 'Extrayendo datos con OCR...');
                    break;
                    
                case 'COMPLETED':
                    clearInterval(pollingInterval);
                    await handleJobCompletion(jobId);
                    break;
                    
                case 'FAILED':
                    clearInterval(pollingInterval);
                    handleJobFailure(status.error);
                    break;
            }
            
            if (attempts >= maxAttempts) {
                clearInterval(pollingInterval);
                showStatus('error', 'Timeout: El procesamiento está tomando demasiado tiempo');
                hideProgress();
                showLoading(false);
            }
            
        } catch (error) {
            console.error('Error en polling:', error);
            
            if (attempts >= 5) {
                clearInterval(pollingInterval);
                showStatus('error', 'Error de conexión durante el procesamiento');
                hideProgress();
                showLoading(false);
            }
        }
    }, 2000);
}

async function checkJobStatus(jobId) {
    const response = await fetch(`${API_BASE_URL}/status/${jobId}`);
    
    if (!response.ok) {
        throw new Error(`Error al consultar estado: ${response.status}`);
    }
    
    return await response.json();
}

async function handleJobCompletion(jobId) {
    try {
        updateProgress(90, 'Obteniendo resultados...');
        
        const result = await getJobResult(jobId);
        
        updateProgress(100, '¡Completado!');
        
        if (result.extracted_data) {
            fillFormWithExtractedData(result.extracted_data);
            showStatus('success', '✅ Datos extraídos automáticamente del documento');
        } else {
            showStatus('error', 'No se pudieron extraer datos del documento');
        }
        
        setTimeout(() => {
            hideProgress();
        }, 2000);
        
    } catch (error) {
        console.error('Error al obtener resultado:', error);
        showStatus('error', `Error al obtener resultado: ${error.message}`);
        hideProgress();
    } finally {
        showLoading(false);
    }
}

async function getJobResult(jobId) {
    const response = await fetch(`${API_BASE_URL}/result/${jobId}`);
    
    if (!response.ok) {
        throw new Error(`Error al obtener resultado: ${response.status}`);
    }
    
    return await response.json();
}

function handleJobFailure(error) {
    showStatus('error', `❌ Error en procesamiento: ${error}`);
    hideProgress();
    showLoading(false);
}

// ================================
// FUNCIONES DE LLENADO DE FORMULARIO
// ================================

function fillFormWithExtractedData(data) {
    console.log('Datos recibidos del backend:', data);
    
    // Llenar campos principales
    fillField('apellido_paterno', data.apellido_paterno);
    fillField('apellido_materno', data.apellido_materno);
    fillField('nombres', data.nombres);
    fillField('fecha_emision', data.fecha_emision);
    fillField('fecha_caducidad', data.fecha_caducidad);
    
    // Campos adicionales que pueden estar presentes
    fillField('numero_documento', data.numero_documento);
    
    // Detectar tipo de documento basado en el contenido
    if (data.tipo_documento) {
        fillField('tipo_documento', data.tipo_documento);
    } else {
        // Autodetección simple
        const textoCompleto = (data.texto_extraido || '').toLowerCase();
        if (textoCompleto.includes('licencia') || textoCompleto.includes('conducir')) {
            fillField('tipo_documento', 'LICENCIA');
        } else if (textoCompleto.includes('dni') || textoCompleto.includes('identidad')) {
            fillField('tipo_documento', 'DNI');
        } else if (textoCompleto.includes('pasaporte')) {
            fillField('tipo_documento', 'PASAPORTE');
        }
    }
    
    // Llenar texto extraído si está disponible
    if (data.texto_extraido) {
        document.getElementById('texto_extraido').value = data.texto_extraido;
    }
    
    // Scroll suave hacia el formulario
    document.querySelector('.form-section').scrollIntoView({ 
        behavior: 'smooth' 
    });
}

function updateInfoField(fieldId, value) {
    const element = document.getElementById(fieldId);
    if (element) {
        element.textContent = value;
        element.classList.add('auto-filled');
        setTimeout(() => element.classList.remove('auto-filled'), 2000);
    }
}

function fillField(fieldId, value) {
    const input = document.getElementById(fieldId);
    if (input && value !== null && value !== undefined && value !== '') {
        input.value = value;
        input.classList.add('auto-filled');
        setTimeout(() => input.classList.remove('auto-filled'), 3000);
    }
}

// ================================
// FUNCIONES DE RECOLECCIÓN Y EXPORTACIÓN
// ================================

function collectFormData() {
    return {
        apellido_paterno: document.getElementById('apellido_paterno').value || null,
        apellido_materno: document.getElementById('apellido_materno').value || null,
        nombres: document.getElementById('nombres').value || null,
        fecha_emision: document.getElementById('fecha_emision').value || null,
        fecha_caducidad: document.getElementById('fecha_caducidad').value || null,
        numero_documento: document.getElementById('numero_documento').value || null,
        tipo_documento: document.getElementById('tipo_documento').value || null,
        texto_extraido: document.getElementById('texto_extraido').value || null,
    };
}

function generateTxtContent(data) {
    const timestamp = new Date().toLocaleString('es-ES');
    
    let content = `DOCUMENTO DE IDENTIDAD - DATOS EXTRAÍDOS\\n`;
    content += `Generado el: ${timestamp}\\n`;
    content += `${'='.repeat(60)}\\n\\n`;
    
    // Formato más legible y organizado
    content += `DATOS DEL DOCUMENTO:\\n`;
    content += `Numero: ${data.numero_documento || 'No detectado'}\\n`;
    content += `Tipo: ${data.tipo_documento || 'No detectado'}\\n\\n`;
    
    content += `DATOS PERSONALES:\\n`;
    content += `Nombres: ${data.nombres || 'No detectado'}\\n`;
    content += `Apellido Paterno: ${data.apellido_paterno || 'No detectado'}\\n`;
    content += `Apellido Materno: ${data.apellido_materno || 'No detectado'}\\n\\n`;
    
    content += `FECHAS IMPORTANTES:\\n`;
    content += `Fecha de Emision: ${data.fecha_emision || 'No detectado'}\\n`;
    content += `Fecha de Caducidad: ${data.fecha_caducidad || 'No detectado'}\\n\\n`;
    
    return content;
}

function downloadTxtFile(content, filename) {
    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
}

function downloadFile() {
    if (lastSavedData) {
        downloadTxtFile(lastSavedData.content, `documento_identidad_${getCurrentTimestamp()}.txt`);
        showStatus('success', '📥 Archivo descargado nuevamente');
    }
}

function getCurrentTimestamp() {
    const now = new Date();
    return now.toISOString().slice(0, 19).replace(/[:-]/g, '').replace('T', '_');
}

// ================================
// FUNCIONES DE INTERFAZ
// ================================

function showStatus(type, message) {
    statusIndicator.className = `status-indicator ${type}`;
    statusIndicator.textContent = message;
    statusIndicator.style.display = 'block';

    if (type === 'success' || type === 'error' || type === 'warning') {
        setTimeout(() => {
            statusIndicator.style.display = 'none';
        }, 5000);
    }
}

function showLoading(show) {
    loadingSpinner.style.display = show ? 'block' : 'none';
}

function updateProgress(percentage, text) {
    progressContainer.style.display = 'block';
    progressFill.style.width = `${percentage}%`;
    progressText.textContent = text;
}

function hideProgress() {
    progressContainer.style.display = 'none';
    progressFill.style.width = '0%';
}

function showDownloadSection() {
    downloadSection.style.display = 'block';
    downloadSection.scrollIntoView({ behavior: 'smooth' });
}



function clearForm() {
    // Limpiar formulario
    form.reset();
    
    // Limpiar clases de auto-filled
    document.querySelectorAll('.auto-filled').forEach(element => {
        element.classList.remove('auto-filled');
    });
    
    // Ocultar secciones
    downloadSection.style.display = 'none';
    
    // Limpiar datos guardados
    lastSavedData = null;
    
    showStatus('success', '🗑️ Formulario limpiado');
}

// ================================
// INICIALIZACIÓN
// ================================

document.addEventListener('DOMContentLoaded', () => {
    console.log('🚀 Procesador de Documentos de Identidad - Demo inicializado');
    console.log('📡 API URL:', API_BASE_URL);
    
    // Configuración inicial
    hideProgress();
    downloadSection.style.display = 'none';
});

// Limpiar polling si se cierra la página
window.addEventListener('beforeunload', () => {
    if (pollingInterval) {
        clearInterval(pollingInterval);
    }
});