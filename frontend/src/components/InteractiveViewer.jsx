import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import { fabric } from 'fabric';
import { detectDimensions, extractDimensions } from '../api';

// Use unpkg as a reliable fallback for the worker
pdfjs.GlobalWorkerOptions.workerSrc = `https://unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.js`;

/**
 * InteractiveViewer.jsx
 * 
 * 1. Loads PDF using react-pdf.
 * 2. Overlays a Fabric.js canvas to allow user to draw/edit rectangles.
 * 3. Calls /api/detect/ to get initial suggestions.
 * 4. Calls /api/extract/ to get final text.
 */
const InteractiveViewer = ({ drawingId, pdfUrl, onProcessed }) => {
    const [numPages, setNumPages] = useState(null);
    const [isDetecting, setIsDetecting] = useState(false);
    const [isExtracting, setIsExtracting] = useState(false);
    const [error, setError] = useState(null);
    const [canvas, setCanvas] = useState(null);
    const [pageScale, setPageScale] = useState(1);

    // Using 200 DPI for rendering to match backend extraction scaling
    const DPI = 200;
    const PDF_RESOLUTION_RATIO = DPI / 72; // Standard PDF 72 DPI to our 200 DPI

    const fabricRef = useRef(null);
    const containerRef = useRef(null);

    // Initialize Fabric.js Canvas
    useEffect(() => {
        const fCanvas = new fabric.Canvas(fabricRef.current, {
            selection: true,
            backgroundColor: 'transparent'
        });
        setCanvas(fCanvas);

        // Add Delete functionality with Backspace/Delete key
        const handleKeyDown = (e) => {
            if (e.key === 'Delete' || e.key === 'Backspace') {
                const activeObjects = fCanvas.getActiveObjects();
                if (activeObjects.length) {
                    activeObjects.forEach(obj => fCanvas.remove(obj));
                    fCanvas.discardActiveObject().renderAll();
                }
            }
        };

        window.addEventListener('keydown', handleKeyDown);

        return () => {
            fCanvas.dispose();
            window.removeEventListener('keydown', handleKeyDown);
        };
    }, []);

    // Function to handle PDF Load Success
    const onDocumentLoadSuccess = ({ numPages }) => {
        setNumPages(numPages);
        setError(null);
    };

    const onDocumentLoadError = (err) => {
        console.error('PDF Load Error:', err);
        setError(`Failed to load PDF from: ${pdfUrl}. Error: ${err.message}.`);
    };

    // Auto-detect dimensions on load
    const handleAutoDetect = useCallback(async () => {
        if (!canvas || isDetecting) return;
        setIsDetecting(true);
        setError(null);

        try {
            const response = await detectDimensions(drawingId);
            const { bboxes } = response.data;

            // Clear existing rectangles first? 
            // Better to keep user ones? User choice, but let's clear for fresh start
            canvas.clear();

            bboxes.forEach(box => {
                const rect = new fabric.Rect({
                    left: box.x,
                    top: box.y,
                    width: box.width,
                    height: box.height,
                    fill: 'rgba(31, 111, 235, 0.15)',
                    stroke: '#1f6feb',
                    strokeWidth: 2,
                    cornerColor: '#39c5cf',
                    cornerSize: 8,
                    transparentCorners: false,
                    data: { text: box.text }
                });
                canvas.add(rect);
            });
            canvas.renderAll();

        } catch (err) {
            console.error('Detection error:', err);
            setError('AI detection failed. You can still draw boxes manually.');
        } finally {
            setIsDetecting(false);
        }
    }, [canvas, drawingId, isDetecting]);

    // Add manual rectangle
    const addManualRect = () => {
        if (!canvas) return;
        const rect = new fabric.Rect({
            left: 50,
            top: 50,
            width: 100,
            height: 40,
            fill: 'rgba(63, 185, 80, 0.15)',
            stroke: '#3fb950',
            strokeWidth: 2,
            cornerColor: '#3fb950',
            cornerSize: 8,
            transparentCorners: false
        });
        canvas.add(rect);
        canvas.setActiveObject(rect);
        canvas.renderAll();
    };

    // Extract Logic
    const handleExtract = async () => {
        if (!canvas || isExtracting) return;

        const objects = canvas.getObjects('rect');
        if (objects.length === 0) {
            setError('Please add or detect at least one rectangle.');
            return;
        }

        setIsExtracting(true);
        setError(null);

        // Map Fabric rectangles to backend format
        const rectangles = objects.map(obj => ({
            x: obj.left,
            y: obj.top,
            width: obj.width * obj.scaleX,
            height: obj.height * obj.scaleY
        }));

        try {
            const response = await extractDimensions(drawingId, rectangles);
            // Result structure for ResultsSection
            onProcessed({
                imageUrl: null, // We are in viewer mode, maybe image url is not needed or we keep pdf
                dimensions: response.data.dimensions,
                dimensionCount: response.data.count,
                extractionMethod: 'Manual Adjustment',
                totalDetected: rectangles.length,
                filteredNoise: 0,
                // Pass download URL if needed
                downloadUrl: response.data.download_url
            });
        } catch (err) {
            console.error('Extraction error:', err);
            setError('Targeted extraction failed. Check backend logs.');
        } finally {
            setIsExtracting(false);
        }
    };

    return (
        <div className="interactive-viewer-wrapper">
            <div className="viewer-controls glass-card" style={{ marginBottom: '16px', display: 'flex', gap: '12px', alignItems: 'center' }}>
                <button
                    className="btn-primary-custom"
                    onClick={handleAutoDetect}
                    disabled={isDetecting}
                >
                    {isDetecting ? 'AI Searching...' : '🔍 Auto-Detect AI'}
                </button>
                <button className="btn-secondary-custom" onClick={addManualRect}>
                    ➕ Add Box
                </button>
                <div style={{ flex: 1 }} />
                <button
                    className="btn-success-custom"
                    onClick={handleExtract}
                    disabled={isExtracting}
                >
                    {isExtracting ? 'Extracting...' : '🔢 Extract Selected'}
                </button>
            </div>

            {error && (
                <div className="alert-custom error" style={{ marginBottom: '16px' }}>
                    <span className="alert-icon">⚠️</span>
                    <span>{error}</span>
                </div>
            )}

            <div
                className="pdf-canvas-container"
                ref={containerRef}
                style={{
                    position: 'relative',
                    background: '#161b22',
                    border: '1px solid var(--color-border)',
                    borderRadius: 'var(--radius-md)',
                    overflow: 'auto',
                    minHeight: '600px',
                    display: 'flex',
                    justifyContent: 'center'
                }}
            >
                {/* PDF Documentation Layer */}
                <Document
                    file={pdfUrl}
                    onLoadSuccess={onDocumentLoadSuccess}
                    onLoadError={onDocumentLoadError}
                    loading={<div className="processing-text">Loading PDF Document...</div>}
                >
                    <Page
                        pageNumber={1}
                        scale={PDF_RESOLUTION_RATIO}
                        renderAnnotationLayer={false}
                        renderTextLayer={false}
                        onLoadSuccess={(page) => {
                            // Sync fabric canvas size with PDF page size
                            if (canvas) {
                                const viewport = page.getViewport({ scale: PDF_RESOLUTION_RATIO });
                                canvas.setWidth(viewport.width);
                                canvas.setHeight(viewport.height);
                            }
                        }}
                    />
                </Document>

                {/* Fabric.js Interaction Layer */}
                <div style={{
                    position: 'absolute',
                    top: 0,
                    left: '50%',
                    transform: 'translateX(-50%)',
                    pointerEvents: 'auto'
                }}>
                    <canvas ref={fabricRef} />
                </div>
            </div>

            <div style={{ marginTop: '12px', fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>
                💡 Tip: Click to select, Drag to move, Shift-click for multiple, Delete/Backspace to remove.
            </div>
        </div>
    );
};

export default InteractiveViewer;
