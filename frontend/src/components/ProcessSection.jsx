/**
 * ProcessSection.jsx
 *
 * Shows after a successful upload.
 * Displays the uploaded drawing name and a "Detect Dimensions" button.
 * Calls the /api/process/<id>/ endpoint and shows a spinner while processing.
 *
 * Props:
 *   drawingId    {number}   - ID of the uploaded drawing record
 *   fileName     {string}   - Display name of the uploaded file
 *   onProcessed  {Function} - Callback with { imageUrl, dimensions } on success
 */

import React, { useState } from 'react';
import { processDrawing } from '../api';

const ProcessSection = ({ drawingId, fileName, onProcessed }) => {
    const [isProcessing, setIsProcessing] = useState(false);
    const [error, setError] = useState(null);

    const handleProcess = async () => {
        setIsProcessing(true);
        setError(null);

        try {
            const response = await processDrawing(drawingId);
            const { image_url, dimensions, dimension_count, total_detected, filtered_noise, extraction_method } = response.data;

            // Notify parent of results
            onProcessed({
                imageUrl: image_url,
                dimensions,
                dimensionCount: dimension_count,
                totalDetected: total_detected,
                filteredNoise: filtered_noise,
                extractionMethod: extraction_method
            });

        } catch (err) {
            console.error('Processing error:', err);
            const msg =
                err.response?.data?.error ||
                err.response?.data?.details ||
                'OCR processing failed. Make sure docTR and Poppler (pdf2image) are configured correctly.';
            setError(msg);
        } finally {
            setIsProcessing(false);
        }
    };

    return (
        <div className="glass-card">
            <div className="section-label">Step 2 — Detect Dimensions</div>

            {/* Uploaded file info */}
            <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: '12px',
                padding: '12px 16px',
                background: 'var(--color-bg-primary)',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--color-border)',
                marginBottom: '20px',
            }}>
                <span style={{ fontSize: '20px' }}>✅</span>
                <div>
                    <div style={{ fontSize: '0.88rem', fontWeight: 600, color: 'var(--color-text-primary)' }}>
                        Drawing Uploaded Successfully
                    </div>
                    <div style={{ fontSize: '0.8rem', color: 'var(--color-text-secondary)', marginTop: '2px' }}>
                        {fileName} · Drawing ID: #{drawingId}
                    </div>
                </div>
            </div>

            {/* Processing spinner or info */}
            {isProcessing ? (
                <div className="processing-overlay">
                    <div className="spinner-ring" />
                    <div className="processing-text">Running OCR Analysis…</div>
                    <div className="processing-subtext">
                        Converting PDF → Running docTR AI → Detecting dimension patterns → Drawing bounding boxes
                    </div>
                    <div className="processing-subtext" style={{ marginTop: '4px' }}>
                        This may take 15–60 seconds depending on drawing size.
                    </div>
                </div>
            ) : (
                <>
                    {/* Instruction text */}
                    <div style={{
                        padding: '14px 16px',
                        background: 'rgba(31,111,235,0.06)',
                        border: '1px solid rgba(31,111,235,0.2)',
                        borderRadius: 'var(--radius-md)',
                        marginBottom: '20px',
                    }}>
                        <div style={{ fontSize: '0.88rem', color: 'var(--color-text-secondary)', lineHeight: 1.6 }}>
                            <strong style={{ color: 'var(--color-text-accent)' }}>What happens next:</strong>
                            <br />
                            The system will convert your PDF to an image, run docTR (Computer Vision AI) to extract text,
                            detect engineering dimension patterns (e.g.&nbsp;
                            <code style={{ fontFamily: 'var(--font-mono)', color: 'var(--color-accent-cyan)', fontSize: '0.82rem' }}>
                                25.4 ± 0.05
                            </code>,&nbsp;
                            <code style={{ fontFamily: 'var(--font-mono)', color: 'var(--color-accent-cyan)', fontSize: '0.82rem' }}>
                                Ø12
                            </code>),
                            and draw red bounding boxes around them.
                        </div>
                    </div>

                    {/* CTA Button */}
                    <div className="action-row">
                        <button
                            id="detect-btn"
                            className="btn-primary-custom pulse-glow"
                            onClick={handleProcess}
                            aria-label="Start dimension detection"
                        >
                            🔍 Detect Dimensions
                        </button>
                    </div>
                </>
            )}

            {/* Error Alert */}
            {error && !isProcessing && (
                <div className="alert-custom error" style={{ marginTop: '16px' }}>
                    <span className="alert-icon">⚠️</span>
                    <div>
                        <strong>Processing Error</strong>
                        <br />
                        {error}
                    </div>
                </div>
            )}
        </div>
    );
};

export default ProcessSection;
