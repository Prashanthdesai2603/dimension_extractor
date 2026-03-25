/**
 * ResultsSection.jsx
 *
 * Displays OCR processing results:
 *   - Annotated drawing image with bounding boxes
 *   - Statistics chips (dimension count)
 *   - Scrollable dimension list
 *   - Editable textarea of extracted text
 *   - Download as .txt button
 *   - Process another drawing button
 *
 * Props:
 *   imageUrl       {string}   - URL to the annotated image served by Django
 *   dimensions     {string[]} - Array of extracted dimension strings
 *   dimensionCount {number}   - Count of found dimensions
 *   drawingId      {number}   - For download link generation
 *   onReset        {Function} - Reset app to start over
 */

import React, { useState } from 'react';
import { getDownloadUrl } from '../api';

const ResultsSection = ({ imageUrl, dimensions, dimensionCount, totalDetected, filteredNoise, extractionMethod, drawingId, onReset }) => {
    // Allow user to edit the extracted text in the textarea
    const [editableText, setEditableText] = useState(dimensions.join('\n'));
    const [imageError, setImageError] = useState(false);

    // Build download link
    const downloadUrl = getDownloadUrl(drawingId);

    return (
        <div className="fade-in">
            {/* Success Banner */}
            <div className="alert-custom success" style={{ marginBottom: '24px' }}>
                <span className="alert-icon">🎉</span>
                <div>
                    <strong>Detection Complete!</strong>
                    &nbsp;Found <strong>{dimensionCount}</strong> dimension{dimensionCount !== 1 ? 's' : ''} using <strong>{extractionMethod}</strong> extraction.
                </div>
            </div>

            {/* ---- Stats Row ---- */}
            <div className="stats-row" style={{ marginBottom: '24px' }}>
                <div className="stat-chip green" title="Validated dimensions matching engineering patterns">
                    ✅ {dimensionCount} Dimensions Found
                </div>
                <div className="stat-chip blue" title="Extraction technique used (Vector = High Precision)">
                    🧠 {extractionMethod} Mode
                </div>
                <div className="stat-chip orange" title="Non-dimension text / title block info ignored">
                    🛡️ {filteredNoise} Noise Filtered
                </div>
                <div className="stat-chip" title="Internal DB ID">
                    🆔 ID: #{drawingId}
                </div>
            </div>

            {/* ---- Two-Column Layout ---- */}
            <div className="row g-4">

                {/* LEFT: Annotated Image */}
                <div className="col-lg-7">
                    <div className="glass-card" style={{ padding: '12px' }}>
                        <div className="section-label" style={{ paddingLeft: '8px', marginBottom: '12px' }}>
                            Annotated Drawing
                        </div>

                        <div className="result-image-wrapper">
                            {imageError || !imageUrl ? (
                                <div style={{
                                    padding: '48px 32px',
                                    textAlign: 'center',
                                    color: 'var(--color-text-muted)',
                                    background: 'var(--color-bg-secondary)',
                                    borderRadius: 'var(--radius-md)'
                                }}>
                                    <div style={{ fontSize: '36px', marginBottom: '12px' }}>📄</div>
                                    <div style={{ fontSize: '0.9rem' }}>
                                        {imageUrl ? 'Annotated image could not be loaded.' : 'Manual extraction complete.'}
                                        <br />
                                        <span style={{ fontSize: '0.8rem' }}>
                                            The dimensions were extracted directly from your selected regions.
                                        </span>
                                    </div>
                                </div>
                            ) : (
                                <img
                                    src={imageUrl}
                                    alt="Annotated engineering drawing"
                                    className="result-image"
                                    onError={() => setImageError(true)}
                                    id="annotated-image"
                                />
                            )}

                            {/* Overlay label */}
                            <div className="result-image-overlay">
                                🔴 Bounding boxes = Detected dimensions
                            </div>
                        </div>

                        {imageUrl && (
                            <div style={{ marginTop: '12px', paddingLeft: '4px' }}>
                                <a
                                    href={imageUrl}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    style={{
                                        fontSize: '0.8rem',
                                        color: 'var(--color-text-accent)',
                                        textDecoration: 'none',
                                        display: 'inline-flex',
                                        alignItems: 'center',
                                        gap: '4px',
                                    }}
                                >
                                    ↗ Open full image in new tab
                                </a>
                            </div>
                        )}
                    </div>
                </div>

                {/* RIGHT: Dimensions Data */}
                <div className="col-lg-5">

                    {/* Scrollable list */}
                    <div className="glass-card" style={{ marginBottom: '20px' }}>
                        <div className="section-label">Detected Dimensions</div>

                        {dimensions.length === 0 ? (
                            <div style={{
                                padding: '24px',
                                textAlign: 'center',
                                color: 'var(--color-text-muted)',
                                fontSize: '0.88rem',
                            }}>
                                No dimensions were detected.
                                <br />
                                Try a drawing with clearer text.
                            </div>
                        ) : (
                            <ul className="dimension-list" aria-label="List of detected dimensions">
                                {dimensions.map((dim, i) => (
                                    <li key={i} className="dimension-item">
                                        <span className="dim-index">{String(i + 1).padStart(2, '0')}</span>
                                        <span className="dim-value">{dim}</span>
                                        <span style={{ fontSize: '14px' }}>📏</span>
                                    </li>
                                ))}
                            </ul>
                        )}
                    </div>

                    {/* Editable Textarea */}
                    <div className="glass-card">
                        <div className="section-label">Edit / Review Extracted Text</div>
                        <textarea
                            id="dimensions-textarea"
                            className="dimensions-box"
                            value={editableText}
                            onChange={(e) => setEditableText(e.target.value)}
                            aria-label="Extracted dimension values, editable"
                            placeholder="No dimensions extracted..."
                            spellCheck={false}
                        />
                        <div style={{
                            fontSize: '0.76rem',
                            color: 'var(--color-text-muted)',
                            marginTop: '8px',
                        }}>
                            💡 You can edit the values above before downloading.
                        </div>
                    </div>
                </div>
            </div>

            {/* ---- Action Buttons ---- */}
            <div className="action-row" style={{ marginTop: '28px' }}>
                {/* Download as .txt */}
                <a
                    href={downloadUrl}
                    download={`dimensions_${drawingId}.txt`}
                    id="download-btn"
                    style={{ textDecoration: 'none' }}
                >
                    <button
                        className="btn-success-custom"
                        aria-label="Download extracted dimensions as text file"
                    >
                        ⬇ Download dimensions.txt
                    </button>
                </a>

                {/* Process another drawing */}
                <button
                    id="reset-btn"
                    className="btn-secondary-custom"
                    onClick={onReset}
                    aria-label="Process a new drawing"
                >
                    ↺ Process Another Drawing
                </button>
            </div>
        </div>
    );
};

export default ResultsSection;
