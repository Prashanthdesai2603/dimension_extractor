/**
 * api.js
 * Centralized Axios API client for communicating with the Django backend.
 * All API calls go through this module to keep the base URL in one place.
 */

import axios from 'axios';

// Django backend base URL - adjust if running on a different port
const BACKEND_BASE_URL = 'http://127.0.0.1:8000';

const api = axios.create({
    baseURL: BACKEND_BASE_URL,
    timeout: 300000, // 5 minute timeout - Extraction can take time on large documents
});

/**
 * Upload a PDF file to the backend.
 * @param {File} file - The PDF File object to upload
 * @param {Function} onUploadProgress - Axios upload progress callback
 * @returns {Promise} - Resolves to { drawing_id, drawing, message }
 */
export const uploadPDF = (file, onUploadProgress) => {
    const formData = new FormData();
    formData.append('file', file);

    return api.post('/api/upload/', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress,
    });
};

/**
 * Trigger OCR suggestion for an uploaded drawing.
 * @param {number} drawingId
 * @returns {Promise} - Resolves to { bboxes: [{x, y, width, height, dim, utol, ltol}] }
 */
export const detectDimensions = (drawingId) => {
    return api.post('/api/detect/', { drawing_id: drawingId });
};

/**
 * Save structured dimensions and get a download link.
 * @param {number} drawingId
 * @param {Array} dimensions - [{dim, utol, ltol}]
 * @returns {Promise} - Resolves to { download_url }
 */
export const exportDimensions = (drawing_id, dimensions) => {
    return api.post('/api/export/', { drawing_id, dimensions });
};

/**
 * Extract dimensions from adjusted rectangles.
 * @param {number} drawing_id
 * @param {Array} rectangles - [{x, y, width, height}]
 * @returns {Promise} - Resolves to { dimensions: [{dim, utol, ltol, original}] }
 */
export const extractDimensions = (drawingId, rectangles) => {
    return api.post('/api/extract/', { drawing_id: drawingId, rectangles });
};

/**
 * Extract dimensions from boxes and trigger .txt export.
 * @param {number} drawingId
 * @param {Array} rectangles
 * @param {Object} viewerContext
 */
export const extractFromBoxes = (drawingId, rectangles, viewerContext, orientation = null) => {
    return api.post('/api/extract_from_boxes/', {
        drawing_id: drawingId,
        rectangles: rectangles,
        viewerContext: viewerContext,
        orientation: orientation
    });
};

/**
 * Trigger OCR processing for an uploaded drawing (Legacy Auto-process).
 * @param {number} drawingId - The ID returned from uploadPDF
 * @returns {Promise} - Resolves to { image_url, dimensions, dimension_count }
 */
export const processDrawing = (drawingId) => {
    return api.post(`/api/process/${drawingId}/`);
};

/**
 * Get the download URL for a drawing's dimensions .txt file.
 * @param {number} drawingId - The drawing ID
 * @returns {string} - Full URL for the download endpoint
 */
export const getDownloadUrl = (drawingId) => {
    return `${BACKEND_BASE_URL}/api/download/${drawingId}/`;
};

export default api;
