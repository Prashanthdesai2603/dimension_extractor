/**
 * App.jsx
 * Root application component.
 *
 * Manages the simplified 2-step workflow:
 *   STEP 1 → Upload:   Single PDF upload
 *   STEP 2 → Analysis: PDF Viewer + Structured Table + Export
 */

import React, { useState } from 'react';
import 'bootstrap/dist/css/bootstrap.min.css';
import './index.css';

// Components
import StepIndicator from './components/StepIndicator';
import UploadSection from './components/UploadSection';
import DrawingViewer from './components/DrawingViewer';
import DimensionTable from './components/DimensionTable';
import { detectDimensions, exportDimensions, extractFromBoxes } from './api';

const App = () => {
    // ---- App State ----
    const [step, setStep] = useState(1);
    const [drawingId, setDrawingId] = useState(null);
    const [pdfUrl, setPdfUrl] = useState('');

    const [isDetecting, setIsDetecting] = useState(false);
    const [isExtracting, setIsExtracting] = useState(false);
    const [isExporting, setIsExporting] = useState(false);
    const [error, setError] = useState(null);

    // Array of {id, x, y, width, height, dim, utol, ltol, text}
    // dimensions: populated ONLY after "Extract Content"
    const [dimensions, setDimensions] = useState([]);
    // detectedBoxes: handles the visual rectangles for adjustment
    const [detectedBoxes, setDetectedBoxes] = useState([]);

    // ---- Callbacks ----

    const handleUploadSuccess = (id, name, url) => {
        setDrawingId(id);
        // Use relative path for proxy compatibility
        const relativeUrl = url.replace(/^(?:https?:\/\/[^/]+)/i, '');
        setPdfUrl(relativeUrl);
        setStep(2);
        // Automatically trigger detection on entering step 2
        triggerAutoDetect(id);
    };

    const triggerAutoDetect = async (id) => {
        const targetId = id || drawingId;
        if (!targetId || isDetecting) return;

        setIsDetecting(true);
        setError(null);
        try {
            const response = await detectDimensions(targetId);
            console.log("Detection response:", response.data);
            // Workflow Change: Only set detected boxes for the viewer, NOT the table
            setDetectedBoxes(response.data.bboxes || []);
            setDimensions([]); // Clear table on new detection
        } catch (err) {
            console.error('Detection failed:', err);
            setError('System failed to detect dimensions automatically.');
        } finally {
            setIsDetecting(false);
        }
    };

    const handleExtract = async () => {
        if (!drawingId || isExtracting || (detectedBoxes && detectedBoxes.length === 0)) return;

        setIsExtracting(true);
        setError(null);
        try {
            // NEW WORKFLOW: Call /api/extract_from_boxes/
            const response = await extractFromBoxes(drawingId, detectedBoxes);
            console.log("Extract response:", response.data);

            // Populate the table with extracted results
            const extractedDims = response.data.dimensions || [];
            setDimensions(extractedDims);

            // If backend sent a specific message (e.g. "No dimensions found"), notify user
            if (extractedDims.length === 0) {
                setError(response.data.message || 'No dimensions found in the selected regions.');
            } else {
                setError(null); // Clear errors on success
            }

        } catch (err) {
            console.error('Extraction failed:', err);
            // Handle both structured backend errors and generic failures
            const errorMsg = err.response?.data?.error || err.response?.data?.message || err.message || 'Failed to extract dimensions from regions.';
            setError(`Extraction Error: ${errorMsg}`);
        } finally {
            setIsExtracting(false);
        }
    };

    const handleTableUpdate = (updatedList) => {
        setDimensions(updatedList || []);
    };

    const handleRowDelete = (id) => {
        const updated = dimensions.filter(d => d.id !== id);
        setDimensions(updated);
    };

    const handleExport = async () => {
        if (!drawingId || isExporting) return;
        setIsExporting(true);
        setError(null);
        try {
            const response = await exportDimensions(drawingId, dimensions);
            if (response.data && response.data.download_url) {
                window.open(response.data.download_url, '_blank');
            }
        } catch (err) {
            console.error('Export failed:', err);
            setError('Failed to generate export file.');
        } finally {
            setIsExporting(false);
        }
    };

    const handleReset = () => {
        setStep(1);
        setDrawingId(null);
        setPdfUrl('');
        setDimensions([]);
        setDetectedBoxes([]);
        setError(null);
    };

    return (
        <div className="d-flex flex-column" style={{ minHeight: '100vh', background: 'var(--color-bg-primary)' }}>

            {/* ---- Modern Header ---- */}
            <header className="app-header">
                <div className="header-inner">
                    <div className="header-brand">
                        <div className="header-logo">📐</div>
                        <div>
                            <h1 className="header-title">Dimension Extractor</h1>
                            <div className="header-subtitle">Engineering Drawing Intelligence</div>
                        </div>
                    </div>
                    <div className="header-badge">Ver 3.0 Interactive</div>
                </div>
            </header>

            <main className="app-main flex-grow-1 d-flex flex-column" style={{ padding: '24px' }}>

                {/* Workflow Status Bar */}
                <div className="mb-4 d-flex justify-content-between align-items-center">
                    <StepIndicator currentStep={step} totalSteps={2} />
                    {step === 2 && (
                        <button className="btn-secondary-custom btn-sm" onClick={handleReset}>
                            ↺ New Drawing
                        </button>
                    )}
                </div>

                {error && (
                    <div className="alert-custom error mb-4">
                        <span className="alert-icon">⚠️</span>
                        <span>{error}</span>
                    </div>
                )}

                {/* STEP 1: UPLOAD */}
                {step === 1 && (
                    <div className="row justify-content-center pt-5">
                        <div className="col-lg-6">
                            <div className="text-center mb-5">
                                <h1 style={{ fontWeight: 800, fontSize: '2.5rem', marginBottom: '16px', color: 'var(--color-text-primary)' }}>
                                    Technical <span style={{ color: 'var(--color-accent-blue)' }}>Precision</span>, Automated.
                                </h1>
                                <p style={{ color: 'var(--color-text-secondary)', fontSize: '1.1rem' }}>
                                    Upload professional engineering drawings (PDF) to extract structured dimension data, tolerances, and metadata with AI.
                                </p>
                            </div>
                            <UploadSection onUploadSuccess={handleUploadSuccess} />
                        </div>
                    </div>
                )}

                {/* STEP 2: ANALYSIS & EXPORT */}
                {step === 2 && (
                    <div className="d-flex flex-row g-4 flex-grow-1 gap-4" style={{ minHeight: 0 }}>
                        {/* Viewer Column (Left) - 70% Width */}
                        <div className="d-flex flex-column" style={{ width: '70%' }}>
                            <div className="d-flex flex-column h-100">
                                <div className="viewer-toolbar mb-3 p-3 glass-card d-flex justify-content-between align-items-center">
                                    <div className="align-items-center gap-3 d-flex">
                                        <div className="status-indicator">
                                            <div className={`status-dot ${isDetecting || isExtracting ? 'pulse' : 'active'}`} />
                                            <span style={{ fontSize: '0.85rem', fontWeight: 500 }}>
                                                {isDetecting ? 'AI Detecting...' : isExtracting ? 'Extracting...' : 'Drawing Ready'}
                                            </span>
                                        </div>
                                    </div>
                                    <div className="d-flex gap-2">
                                        <button
                                            className="btn-secondary-custom"
                                            onClick={() => triggerAutoDetect()}
                                            disabled={isDetecting || isExtracting}
                                        >
                                            🔍 Detect Dimensions
                                        </button>
                                        <button
                                            className="btn-primary-custom"
                                            onClick={handleExtract}
                                            disabled={isDetecting || isExtracting || (detectedBoxes && detectedBoxes.length === 0)}
                                        >
                                            ⚙️ {isExtracting ? 'Extracting...' : 'Extract Content'}
                                        </button>
                                    </div>
                                </div>
                                <div className="flex-grow-1" style={{ minHeight: '800px' }}>
                                    <DrawingViewer
                                        pdfUrl={pdfUrl}
                                        bboxes={detectedBoxes}
                                        onBboxesChange={setDetectedBoxes}
                                    />
                                </div>
                            </div>
                        </div>

                        {/* Table Column (Right) - 30% Width */}
                        <div className="d-flex flex-column" style={{ width: '30%' }}>
                            <DimensionTable
                                dimensions={dimensions}
                                onUpdate={handleTableUpdate}
                                onDelete={handleRowDelete}
                                onExport={handleExport}
                                isExporting={isExporting}
                            />
                        </div>
                    </div>
                )}
            </main>

            <footer className="app-footer">
                <span>Enterprise Engineering Suite</span>
                &nbsp;·&nbsp;
                <span>© 2026 Dimension Extractor Tool</span>
                &nbsp;·&nbsp;
                <span>docTR AI Engine v2.0</span>
            </footer>

            <style jsx>{`
                .status-indicator {
                    display: flex;
                    align-items: center;
                    gap: 10px;
                    background: rgba(31, 111, 235, 0.08);
                    padding: 6px 14px;
                    border-radius: 20px;
                    border: 1px solid rgba(31, 111, 235, 0.15);
                }
                .status-dot {
                    width: 8px;
                    height: 8px;
                    border-radius: 50%;
                }
                .status-dot.active {
                    background: var(--color-accent-green);
                    box-shadow: 0 0 10px rgba(63, 185, 80, 0.5);
                }
                .status-dot.pulse {
                    background: var(--color-accent-orange);
                    animation: pulse-glow 1s infinite alternate;
                }
            `}</style>
        </div>
    );
};

export default App;
