import React, { useState, useEffect, useRef } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import { Stage, Layer, Rect, Transformer, Circle, Text, Group } from 'react-konva';

// Set worker for react-pdf
pdfjs.GlobalWorkerOptions.workerSrc = `https://unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.js`;

/**
 * Interactive Rectangle component with Transformer.
 * Vertical/curved dims are shown in cyan, horizontal in blue.
 */
const InteractiveRect = ({ shapeProps, isSelected, isHighlighted, onSelect, onChange }) => {
    const shapeRef = useRef();
    const trRef = useRef();

    useEffect(() => {
        if (isSelected) {
            trRef.current.nodes([shapeRef.current]);
            trRef.current.getLayer().batchDraw();
        }
    }, [isSelected]);

    const isVertical = shapeProps.vertical;
    const strokeColor = isHighlighted
        ? '#ff3333'
        : isSelected
            ? '#ffdd57'
            : isVertical ? '#39c5cf' : '#1f6feb';
    const fillColor = isHighlighted
        ? 'rgba(255, 51, 51, 0.25)'
        : isVertical
            ? 'rgba(57, 197, 207, 0.12)'
            : 'rgba(31, 111, 235, 0.10)';

    return (
        <React.Fragment>
            <Group
                ref={shapeRef}
                draggable
                x={shapeProps.x}
                y={shapeProps.y}
                rotation={shapeProps.rotation || 0}
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

                    // For groups, we might need to handle Rect size vs Group scale
                    // but for simplicity in this workflow, keeping Rect width/height in shapeProps
                    // and updating them here.
                    onChange({
                        ...shapeProps,
                        x: node.x(),
                        y: node.y(),
                        rotation: node.rotation(),
                        width: Math.max(5, shapeProps.width * scaleX),
                        height: Math.max(5, shapeProps.height * scaleY),
                    });
                }}
            >
                <Rect
                    x={0}
                    y={0}
                    width={shapeProps.width}
                    height={shapeProps.height}
                    onClick={onSelect}
                    onTap={onSelect}
                    fill={fillColor}
                    stroke={strokeColor}
                    strokeWidth={isHighlighted ? 4 : (isSelected ? 3 : 2)}
                    shadowEnabled={isHighlighted}
                    shadowColor="red"
                    shadowBlur={10}
                    shadowOpacity={0.6}
                />

                {shapeProps.serial && (
                    <Group
                        x={shapeProps.width + 2}
                        y={-2}
                    >
                        {/* Ensure circle doesn't rotate with group or does it? 
                            In nested group, it will rotate. This is usually what's wanted for engineering balloons. */}
                        <Circle
                            radius={10}
                            fill="white"
                            stroke="#333"
                            strokeWidth={1.5}
                            shadowColor="black"
                            shadowBlur={3}
                            shadowOpacity={0.2}
                            shadowOffset={{ x: 1, y: 1 }}
                        />
                        <Text
                            text={shapeProps.serial.toString()}
                            fontSize={9}
                            fontStyle="bold"
                            fill="#000"
                            align="center"
                            verticalAlign="middle"
                            width={20}
                            height={20}
                            offsetX={10}
                            offsetY={10}
                        />
                    </Group>
                )}
            </Group>

            {isSelected && (
                <Transformer
                    ref={trRef}
                    rotateEnabled={true}
                    anchorSize={8}
                    anchorCornerRadius={2}
                    anchorFill="#ffdd57"
                    borderStroke="#ffdd57"
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

const DrawingViewer = ({ pdfUrl, bboxes = [], onBboxesChange, onContextUpdate, highlightedId, manualSelectionMode = false, onManualSelectionDone }) => {
    // Increase default scale for better visibility
    const [scale, setScale] = useState(0.5);
    const [selectedId, setSelectedId] = useState(null);
    const [canvasSize, setCanvasSize] = useState({ width: 0, height: 0 });
    const [pdfSize, setPdfSize] = useState({ width: 0, height: 0 });
    // Local highlight state to allow fading
    const [activeHighlightId, setActiveHighlightId] = useState(null);
    const containerRef = useRef();
    const contentRef = useRef();

    // Manual drawing state
    const [isDrawing, setIsDrawing] = useState(false);
    const [drawStart, setDrawStart] = useState(null);
    const [drawingRect, setDrawingRect] = useState(null);

    // Use a higher DPI for rendering (e.g., 200) to ensure text is readable
    const DPI_RATIO = 200 / 72;

    const handlePageRenderSuccess = (page) => {
        const viewport = page.getViewport({ scale: DPI_RATIO * scale });
        setCanvasSize({ width: viewport.width, height: viewport.height });

        // Store original PDF dimensions (72 DPI points)
        const baseViewport = page.getViewport({ scale: 1.0 });
        setPdfSize({ width: baseViewport.width, height: baseViewport.height });
    };

    // Inform parent of current viewer/pdf context for coordinate translation
    useEffect(() => {
        if (onContextUpdate && canvasSize.width > 0 && pdfSize.width > 0) {
            onContextUpdate({
                viewerWidth: canvasSize.width,
                viewerHeight: canvasSize.height,
                pdfWidth: pdfSize.width,
                pdfHeight: pdfSize.height,
                zoomLevel: scale
            });
        }
    }, [scale, canvasSize, pdfSize, onContextUpdate]);

    // Handle Smart Zoom-to-Dimension (Requirement 1 & 2)
    useEffect(() => {
        if (highlightedId && bboxes.length > 0) {
            const target = bboxes.find(b => b.id === highlightedId);
            if (target) {
                // 1. Trigger highlight
                setActiveHighlightId(highlightedId);

                // 2. Clear highlight after 3 seconds
                const timer = setTimeout(() => {
                    setActiveHighlightId(null);
                }, 3000);

                // 3. Smart Zoom (200% zoom = scale 1.0 at 200 DPI)
                setScale(1.0);

                // 4. Scroll into view (defer until zoom/canvas update)
                setTimeout(() => {
                    if (contentRef.current) {
                        // The bboxes are stored in 200 DPI pixel space.
                        // When scale=1.0, the canvas pixels match the 200 DPI space.
                        const targetX = target.x * 1.0;
                        const targetY = target.y * 1.0;
                        const targetW = target.width * 1.0;
                        const targetH = target.height * 1.0;

                        const containerWidth = contentRef.current.clientWidth;
                        const containerHeight = contentRef.current.clientHeight;

                        // Scroll smoothly to center the box
                        contentRef.current.scrollTo({
                            left: targetX - (containerWidth / 2) + (targetW / 2),
                            top: targetY - (containerHeight / 2) + (targetH / 2),
                            behavior: 'smooth'
                        });
                    }
                }, 150);

                return () => clearTimeout(timer);
            }
        }
    }, [highlightedId, bboxes.length]);

    // We can expose the viewer context via a ref or a side effect if needed,
    // but the easiest is to attach it to the bboxes or have a callback.
    // For now, let's just make sure it's accessible when Extract is clicked.
    // We'll update the App handleExtract to pull these from a ref if we want,
    // or just pass them up via bboxes.

    const checkDeselect = (e) => {
        // Don't deselect when in manual selection mode (we handle drawing instead)
        if (manualSelectionMode) return;
        const clickedOnEmpty = e.target === e.target.getStage();
        if (clickedOnEmpty) {
            setSelectedId(null);
        }
    };

    // --- Manual Selection Drawing Handlers ---
    const handleStageMouseDown = (e) => {
        if (!manualSelectionMode) {
            checkDeselect(e);
            return;
        }
        // Only start drawing if clicking on empty stage area
        const clickedOnEmpty = e.target === e.target.getStage();
        if (!clickedOnEmpty) return;

        const stage = e.target.getStage();
        const pos = stage.getPointerPosition();
        setIsDrawing(true);
        setDrawStart({ x: pos.x, y: pos.y });
        setDrawingRect({ x: pos.x, y: pos.y, width: 0, height: 0 });
        setSelectedId(null);
    };

    const handleStageMouseMove = (e) => {
        if (!isDrawing || !drawStart) return;
        const stage = e.target.getStage();
        const pos = stage.getPointerPosition();

        const x = Math.min(drawStart.x, pos.x);
        const y = Math.min(drawStart.y, pos.y);
        const width = Math.abs(pos.x - drawStart.x);
        const height = Math.abs(pos.y - drawStart.y);

        setDrawingRect({ x, y, width, height });
    };

    const handleStageMouseUp = (e) => {
        if (!isDrawing || !drawingRect) {
            setIsDrawing(false);
            setDrawStart(null);
            setDrawingRect(null);
            return;
        }

        // Minimum size threshold (prevent accidental clicks)
        if (drawingRect.width > 10 && drawingRect.height > 10) {
            const id = `manual_${Date.now()}`;
            const maxSerial = bboxes.reduce((max, b) => Math.max(max, b.serial || 0), 0);

            const newRect = {
                id,
                serial: maxSerial + 1,
                // Store coordinates in unscaled (DPI_RATIO) space
                x: drawingRect.x / scale,
                y: drawingRect.y / scale,
                width: drawingRect.width / scale,
                height: drawingRect.height / scale,
                text: '',
                dim: '',
                utol: '',
                ltol: '',
                method: 'manual',
            };

            onBboxesChange([...bboxes, newRect]);
            setSelectedId(id);
        }

        setIsDrawing(false);
        setDrawStart(null);
        setDrawingRect(null);
    };

    const handleAddRect = () => {
        const id = `rect_${Date.now()}`;
        const maxSerial = bboxes.reduce((max, b) => Math.max(max, b.serial || 0), 0);

        // Calculate middle-top position
        // bboxes are in coordinates relative to DPI_RATIO (200 DPI)
        // canvasSize.width is (OriginalWidth * DPI_RATIO * scale)
        const drawingWidth = canvasSize.width > 0 ? (canvasSize.width / scale) : 2000;
        const rectWidth = 120;
        const centerX = (drawingWidth / 2) - (rectWidth / 2);

        const newRect = {
            id,
            serial: maxSerial + 1,
            x: centerX,
            y: 80,             // Positioned near the top
            width: rectWidth,
            height: 45,
            text: '',       // empty — triggers OCR path in backend
            dim: '',
            utol: '',
            ltol: '',
            method: 'manual',   // flag so backend always includes it
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
            <div className="viewer-header p-3 border-bottom d-flex justify-content-between align-items-center" style={{ background: 'var(--color-bg-secondary)' }}>
                <span className="d-flex align-items-center gap-2" style={{ fontWeight: 600, fontSize: '0.9rem' }}>
                    <span style={{ fontSize: '1.2rem' }}>📑</span> Engineering Drawing Viewer
                </span>
                <div className="d-flex gap-3 align-items-center">
                    <button className="btn btn-sm btn-primary-custom" onClick={handleAddRect}>
                        ➕ Add Box
                    </button>
                    <div className="d-flex gap-2 bg-light rounded px-2 py-1 border border-secondary align-items-center">
                        <button className="btn btn-xs text-dark p-0 px-2" title="Zoom Out" onClick={() => setScale(s => Math.max(0.2, s - 0.1))}>−</button>
                        <span
                            style={{ fontSize: '0.75rem', width: '45px', textAlign: 'center', fontWeight: 600, cursor: 'pointer' }}
                            title="Reset Zoom"
                            onClick={() => setScale(1.0)}
                        >
                            {Math.round(scale * 100)}%
                        </span>
                        <button className="btn btn-xs text-dark p-0 px-2" title="Zoom In" onClick={() => setScale(s => Math.min(2.0, s + 0.1))}>+</button>
                    </div>
                </div>
            </div>

            <div className="viewer-content flex-grow-1 overflow-auto p-4 scroll-custom"
                ref={contentRef}
                style={{ position: 'relative', cursor: manualSelectionMode ? 'crosshair' : 'default', background: '#f5f5f5' }}>
                <div style={{ position: 'relative', margin: '0 auto', width: 'fit-content', boxShadow: '0 4px 30px rgba(0,0,0,0.15)', border: '1px solid #ddd' }}>
                    <Document
                        file={pdfUrl}
                        loading={<div className="p-5 text-center text-muted"><div className="spinner-border spinner-border-sm me-2"></div>Loading High-Res Drawing...</div>}
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
                                onMouseDown={handleStageMouseDown}
                                onMouseMove={handleStageMouseMove}
                                onMouseUp={handleStageMouseUp}
                                onTouchStart={handleStageMouseDown}
                                style={{ cursor: manualSelectionMode ? 'crosshair' : 'default' }}
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
                                            isHighlighted={rect.id === activeHighlightId}
                                            onSelect={() => setSelectedId(rect.id)}
                                            onChange={(newAttrs) => {
                                                const rects = bboxes.slice();
                                                const index = rects.findIndex(r => r.id === rect.id);
                                                rects[index] = {
                                                    ...rects[index],
                                                    x: newAttrs.x / scale,
                                                    y: newAttrs.y / scale,
                                                    width: newAttrs.width / scale,
                                                    height: newAttrs.height / scale,
                                                    rotation: newAttrs.rotation
                                                };
                                                onBboxesChange(rects);
                                            }}
                                        />
                                    ))}

                                    {/* Preview rectangle while drawing */}
                                    {isDrawing && drawingRect && (
                                        <Rect
                                            x={drawingRect.x}
                                            y={drawingRect.y}
                                            width={drawingRect.width}
                                            height={drawingRect.height}
                                            fill="rgba(46, 204, 113, 0.15)"
                                            stroke="#2ecc71"
                                            strokeWidth={2}
                                            dash={[6, 3]}
                                        />
                                    )}
                                </Layer>
                            </Stage>
                        </div>
                    )}
                </div>
            </div>

            <div className="viewer-footer p-2 text-center border-top" style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)', background: 'var(--color-bg-secondary)' }}>
                DPI: 200 | Interactive Canvas Active | Zoom: {Math.round(scale * 100)}% | Select box to resize or move
            </div>

            <style jsx>{`
                .scroll-custom::-webkit-scrollbar {
                    width: 10px;
                    height: 10px;
                }
                .scroll-custom::-webkit-scrollbar-track {
                    background: #f1f1f1;
                }
                .scroll-custom::-webkit-scrollbar-thumb {
                    background: #ccc;
                    border-radius: 5px;
                }
                .scroll-custom::-webkit-scrollbar-thumb:hover {
                    background: #bbb;
                }
                .btn-xs {
                    padding: 1px 5px;
                    font-size: 12px;
                    line-height: 1.5;
                }
            `}</style>
        </div>
    );
};

export default DrawingViewer;
