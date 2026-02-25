import React, { useState, useEffect, useRef } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import { Stage, Layer, Rect, Transformer } from 'react-konva';

// Set worker for react-pdf
pdfjs.GlobalWorkerOptions.workerSrc = `https://unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.js`;

/**
 * Interactive Rectangle component with Transformer
 */
const InteractiveRect = ({ shapeProps, isSelected, onSelect, onChange, onDelete }) => {
    const shapeRef = useRef();
    const trRef = useRef();

    useEffect(() => {
        if (isSelected) {
            trRef.current.nodes([shapeRef.current]);
            trRef.current.getLayer().batchDraw();
        }
    }, [isSelected]);

    return (
        <React.Fragment>
            <Rect
                onClick={onSelect}
                onTap={onSelect}
                ref={shapeRef}
                {...shapeProps}
                draggable
                fill="rgba(31, 111, 235, 0.15)"
                stroke={isSelected ? "#39c5cf" : "#1f6feb"}
                strokeWidth={2}
                onDragEnd={(e) => {
                    onChange({
                        ...shapeProps,
                        x: e.target.x(),
                        y: e.target.y(),
                    });
                }}
                onTransformEnd={(e) => {
                    const node = shapeRef.current;
                    const scaleX = node.scaleX();
                    const scaleY = node.scaleY();

                    node.scaleX(1);
                    node.scaleY(1);
                    onChange({
                        ...shapeProps,
                        x: node.x(),
                        y: node.y(),
                        width: Math.max(5, node.width() * scaleX),
                        height: Math.max(5, node.height() * scaleY),
                    });
                }}
            />
            {isSelected && (
                <Transformer
                    ref={trRef}
                    boundBoxFunc={(oldBox, newBox) => {
                        if (newBox.width < 5 || newBox.height < 5) {
                            return oldBox;
                        }
                        return newBox;
                    }}
                />
            )}
        </React.Fragment>
    );
};

const DrawingViewer = ({ pdfUrl, bboxes = [], onBboxesChange }) => {
    const [scale, setScale] = useState(1.0);
    const [selectedId, setSelectedId] = useState(null);
    const [canvasSize, setCanvasSize] = useState({ width: 0, height: 0 });

    const containerRef = useRef();

    const DPI_RATIO = 200 / 72;

    const onDocumentLoadSuccess = () => {
        // No-op, just for loader compliance
    };

    const handlePageRenderSuccess = (page) => {
        const viewport = page.getViewport({ scale: DPI_RATIO * scale });
        setCanvasSize({ width: viewport.width, height: viewport.height });
    };

    const checkDeselect = (e) => {
        const clickedOnEmpty = e.target === e.target.getStage();
        if (clickedOnEmpty) {
            setSelectedId(null);
        }
    };

    const handleAddRect = () => {
        const id = `rect_${Date.now()}`;
        const newRect = {
            id,
            x: 50,
            y: 50,
            width: 100,
            height: 40,
            text: 'Manual',
            dim: '',
            utol: '',
            ltol: ''
        };
        onBboxesChange([...bboxes, newRect]);
        setSelectedId(id);
    };

    useEffect(() => {
        const handleKeyDown = (e) => {
            if (e.key === 'Delete' || e.key === 'Backspace') {
                if (selectedId) {
                    const updated = bboxes.filter(b => b.id !== selectedId);
                    onBboxesChange(updated);
                    setSelectedId(null);
                }
            }
        };

        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [selectedId, bboxes, onBboxesChange]);

    return (
        <div className="drawing-viewer-wrapper glass-card h-100 p-0 overflow-hidden d-flex flex-column" ref={containerRef}>
            <div className="viewer-header p-3 border-bottom d-flex justify-content-between align-items-center">
                <span style={{ fontWeight: 600, fontSize: '0.9rem' }}>📄 Engineering Drawing Viewer</span>
                <div className="d-flex gap-3 align-items-center">
                    <button className="btn btn-sm btn-outline-primary" onClick={handleAddRect}>
                        ➕ Add Box
                    </button>
                    <div className="d-flex gap-2">
                        <button className="btn btn-sm btn-outline-secondary" onClick={() => setScale(s => Math.max(0.5, s - 0.1))}>−</button>
                        <span className="text-muted" style={{ fontSize: '0.8rem', width: '40px', textAlign: 'center' }}>{Math.round(scale * 100)}%</span>
                        <button className="btn btn-sm btn-outline-secondary" onClick={() => setScale(s => Math.min(2.0, s + 0.1))}>+</button>
                    </div>
                </div>
            </div>

            <div className="viewer-content flex-grow-1 overflow-auto bg-dark p-4" style={{ position: 'relative' }}>
                <div style={{ position: 'relative', margin: '0 auto', width: 'fit-content' }}>
                    <Document
                        file={pdfUrl}
                        onLoadSuccess={onDocumentLoadSuccess}
                        loading={<div className="p-5 text-center text-muted">Loading Technical Drawing...</div>}
                    >
                        <Page
                            pageNumber={1}
                            scale={DPI_RATIO * scale}
                            renderAnnotationLayer={false}
                            renderTextLayer={false}
                            onRenderSuccess={handlePageRenderSuccess}
                        />
                    </Document>

                    {/* Konva Layer for interaction */}
                    {canvasSize.width > 0 && (
                        <div style={{ position: 'absolute', top: 0, left: 0 }}>
                            <Stage
                                width={canvasSize.width}
                                height={canvasSize.height}
                                onMouseDown={checkDeselect}
                                onTouchStart={checkDeselect}
                            >
                                <Layer>
                                    {bboxes.map((rect, i) => (
                                        <InteractiveRect
                                            key={rect.id || i}
                                            shapeProps={{
                                                ...rect,
                                                x: rect.x * scale,
                                                y: rect.y * scale,
                                                width: rect.width * scale,
                                                height: rect.height * scale
                                            }}
                                            isSelected={rect.id === selectedId}
                                            onSelect={() => setSelectedId(rect.id)}
                                            onChange={(newAttrs) => {
                                                const rects = bboxes.slice();
                                                const index = rects.findIndex(r => r.id === rect.id);
                                                rects[index] = {
                                                    ...rects[index],
                                                    x: newAttrs.x / scale,
                                                    y: newAttrs.y / scale,
                                                    width: newAttrs.width / scale,
                                                    height: newAttrs.height / scale
                                                };
                                                onBboxesChange(rects);
                                            }}
                                        />
                                    ))}
                                </Layer>
                            </Stage>
                        </div>
                    )}
                </div>
            </div>

            <div className="viewer-footer p-2 text-center" style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)' }}>
                DPI: 200 | Interactive Layer Active (Select Box → Move/Resize/Del)
            </div>
        </div>
    );
};

export default DrawingViewer;
