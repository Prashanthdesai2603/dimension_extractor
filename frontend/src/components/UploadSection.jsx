/**
 * UploadSection.jsx
 *
 * Handles PDF file selection and upload to the Django backend.
 * Features:
 *   - Drag-and-drop upload zone
 *   - Click-to-browse file input
 *   - File validation (type, size)
 *   - Upload progress feedback
 *   - Error display
 */

import React, { useState, useRef, useCallback } from 'react';
import { uploadPDF } from '../api';

/**
 * Format file size from bytes to human-readable string.
 * @param {number} bytes
 * @returns {string}
 */
const formatFileSize = (bytes) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1048576).toFixed(1)} MB`;
};

/**
 * @param {Function} onUploadSuccess - Called with drawing_id when upload completes
 */
const UploadSection = ({ onUploadSuccess }) => {
    const [selectedFile, setSelectedFile] = useState(null);
    const [isDragOver, setIsDragOver] = useState(false);
    const [isUploading, setIsUploading] = useState(false);
    const [uploadProgress, setUploadProgress] = useState(0);
    const [error, setError] = useState(null);

    // Hidden file input reference
    const fileInputRef = useRef(null);

    /**
     * Validate the chosen file (must be PDF, max 50MB).
     * Returns an error string or null if valid.
     */
    const validateFile = (file) => {
        if (!file) return 'No file selected.';
        if (!file.name.toLowerCase().endsWith('.pdf')) {
            return 'Invalid file type. Please upload a PDF file.';
        }
        if (file.size > 52428800) {
            return 'File is too large. Maximum size is 50 MB.';
        }
        return null;
    };

    /** Handle file selection from the input element or drop event. */
    const handleFileSelect = useCallback((file) => {
        setError(null);
        const validationError = validateFile(file);
        if (validationError) {
            setError(validationError);
            setSelectedFile(null);
            return;
        }
        setSelectedFile(file);
    }, []);

    // ---- Drag events ----
    const handleDragOver = (e) => { e.preventDefault(); setIsDragOver(true); };
    const handleDragLeave = (e) => { e.preventDefault(); setIsDragOver(false); };
    const handleDrop = (e) => {
        e.preventDefault();
        setIsDragOver(false);
        const file = e.dataTransfer.files[0];
        if (file) handleFileSelect(file);
    };

    // ---- File input change ----
    const handleInputChange = (e) => {
        const file = e.target.files[0];
        if (file) handleFileSelect(file);
    };

    // ---- Upload Handler ----
    const handleUpload = async () => {
        if (!selectedFile) {
            setError('Please select a PDF file first.');
            return;
        }

        setIsUploading(true);
        setError(null);
        setUploadProgress(0);

        try {
            const response = await uploadPDF(selectedFile, (progressEvent) => {
                const pct = Math.round((progressEvent.loaded * 100) / progressEvent.total);
                setUploadProgress(pct);
            });

            const { drawing_id, drawing } = response.data;
            // Notify parent component of successful upload
            onUploadSuccess(drawing_id, selectedFile.name, drawing.file_url);

        } catch (err) {
            console.error('Upload error:', err);
            const msg = err.response?.data?.error || 'Upload failed. Is the Django server running on port 8000?';
            setError(msg);
        } finally {
            setIsUploading(false);
            setUploadProgress(0);
        }
    };

    return (
        <div className="glass-card">
            <div className="section-label">Step 1 — Upload Drawing</div>

            {/* Drop Zone */}
            <div
                className={`upload-zone ${isDragOver ? 'drag-over' : ''}`}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
                role="button"
                aria-label="Click or drag to upload PDF"
                tabIndex={0}
                onKeyDown={(e) => e.key === 'Enter' && fileInputRef.current?.click()}
            >
                {/* Hidden real input */}
                <input
                    ref={fileInputRef}
                    type="file"
                    accept=".pdf,application/pdf"
                    onChange={handleInputChange}
                    id="pdf-file-input"
                    aria-label="PDF file upload input"
                />

                <div className="upload-icon-wrapper">
                    {selectedFile ? '📄' : '📂'}
                </div>

                {selectedFile ? (
                    <>
                        <div className="upload-title" style={{ color: 'var(--color-accent-green)' }}>
                            File Ready to Upload
                        </div>
                        <div className="upload-subtitle">
                            Click upload below, or drop a different file here
                        </div>
                    </>
                ) : (
                    <>
                        <div className="upload-title">Drop your PDF here</div>
                        <div className="upload-subtitle">
                            or <span style={{ color: 'var(--color-text-accent)' }}>click to browse</span>
                            &nbsp;· PDF only, max 50 MB
                        </div>
                    </>
                )}
            </div>

            {/* File Preview Bar */}
            {selectedFile && (
                <div className="file-preview-bar">
                    <span className="file-preview-icon">📑</span>
                    <span className="file-preview-name">{selectedFile.name}</span>
                    <span className="file-preview-size">{formatFileSize(selectedFile.size)}</span>
                    {/* Clear selection */}
                    <button
                        style={{
                            background: 'none',
                            border: 'none',
                            color: 'var(--color-text-muted)',
                            cursor: 'pointer',
                            fontSize: '16px',
                            padding: '0 4px',
                        }}
                        onClick={(e) => { e.stopPropagation(); setSelectedFile(null); setError(null); }}
                        title="Remove file"
                        aria-label="Remove selected file"
                    >
                        ✕
                    </button>
                </div>
            )}

            {/* Upload Progress Bar */}
            {isUploading && (
                <div style={{ marginTop: '16px' }}>
                    <div style={{
                        background: 'var(--color-bg-primary)',
                        borderRadius: '4px',
                        overflow: 'hidden',
                        height: '6px',
                        border: '1px solid var(--color-border)',
                    }}>
                        <div style={{
                            height: '100%',
                            width: `${uploadProgress}%`,
                            background: 'var(--gradient-brand)',
                            transition: 'width 0.2s ease',
                            borderRadius: '4px',
                        }} />
                    </div>
                    <div style={{ fontSize: '0.78rem', color: 'var(--color-text-muted)', marginTop: '6px', textAlign: 'center' }}>
                        Uploading… {uploadProgress}%
                    </div>
                </div>
            )}

            {/* Error Alert */}
            {error && (
                <div className="alert-custom error" style={{ marginTop: '16px' }}>
                    <span className="alert-icon">⚠️</span>
                    <span>{error}</span>
                </div>
            )}

            {/* Action Buttons */}
            <div className="action-row" style={{ marginTop: '20px' }}>
                <button
                    id="upload-btn"
                    className="btn-primary-custom"
                    onClick={handleUpload}
                    disabled={!selectedFile || isUploading}
                    aria-label="Upload PDF to server"
                >
                    {isUploading ? (
                        <>
                            <div className="spinner-ring" style={{ width: '16px', height: '16px', borderWidth: '2px' }} />
                            Uploading…
                        </>
                    ) : (
                        <> 📤 Upload PDF </>
                    )}
                </button>

                {selectedFile && !isUploading && (
                    <button
                        className="btn-secondary-custom"
                        onClick={() => { setSelectedFile(null); setError(null); fileInputRef.current.value = ''; }}
                        aria-label="Clear selection"
                    >
                        ✕ Clear
                    </button>
                )}
            </div>
        </div>
    );
};

export default UploadSection;
