import React, { useState, useEffect, useRef } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import { Stage, Layer, Rect, Transformer, Circle, Text, Group } from 'react-konva';

// Set worker for react-pdf
pdfjs.GlobalWorkerOptions.workerSrc = `https://unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.js`;

/**
 * Interactive Rectangle component with Transformer.
 * Vertical/curved dims are shown in cyan, horizontal in blue.
 */
const InteractiveRect = ({ shapeProps, isSelected, onSelect, onChange }) => {
    const shapeRef = useRef();
    const trRef = useRef();

    useEffect(() => {
        if (isSelected) {
            trRef.current.nodes([shapeRef.current]);
            trRef.current.getLayer().batchDraw();
        }
    }, [isSelected]);

    const isVertical = shapeProps.vertical;
    const strokeColor = isSelected
        ? '#ffdd57'
        : isVertical ? '#39c5cf' : '#1f6feb';
    const fillColor = isVertical
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
                    strokeWidth={isSelected ? 3 : 2}
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

const DrawingViewer = ({ pdfUrl, bboxes = [], onBboxesChange }) => {
    // Increase default scale for better visibility
    const [scale, setScale] = useState(0.5);
    const [selectedId, setSelectedId] = useState(null);
    const [canvasSize, setCanvasSize] = useState({ width: 0, height: 0 });

    const containerRef = useRef();

    // Use a higher DPI for rendering (e.g., 200) to ensure text is readable
    const DPI_RATIO = 200 / 72;

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
                        <button className="btn btn-xs text-dark p-0 px-2" title="Zoom Out" onClick={() => setScale(s => Math.max(0.1, s - 0.1))}>−</button>
                        <span
                            style={{ fontSize: '0.75rem', width: '45px', textAlign: 'center', fontWeight: 600, cursor: 'pointer' }}
                            title="Reset Zoom"
                            onClick={() => setScale(1.0)}
                        >
                            {Math.round(scale * 100)}%
                        </span>
                        <button className="btn btn-xs text-dark p-0 px-2" title="Zoom In" onClick={() => setScale(s => Math.min(5.0, s + 0.1))}>+</button>
                    </div>
                </div>
            </div>

            <div className="viewer-content flex-grow-1 overflow-auto p-4 scroll-custom" style={{ position: 'relative', cursor: 'crosshair', background: '#f5f5f5' }}>
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
                                                    height: newAttrs.height / scale,
                                                    rotation: newAttrs.rotation
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
