/**
 * StepIndicator.jsx
 * Visual workflow stepper showing current progress in the 2-step pipeline:
 *   1. Upload PDF
 *   2. Analysis & Export
 */

import React from 'react';

const STEPS = [
    { id: 1, label: 'Upload PDF', icon: '📤' },
    { id: 2, label: 'Analysis & Export', icon: '🔍' },
];

/**
 * @param {number} currentStep - 1, 2, or 3 indicating the active step
 */
const StepIndicator = ({ currentStep }) => {
    return (
        <div className="steps-bar" role="list" aria-label="Progress steps">
            {STEPS.map((step, index) => {
                const isDone = step.id < currentStep;
                const isActive = step.id === currentStep;

                return (
                    <div className="step-item" key={step.id} role="listitem">
                        {/* Step circle */}
                        <div
                            className={`step-circle ${isDone ? 'done' : ''} ${isActive ? 'active' : ''}`}
                            aria-label={`Step ${step.id}: ${step.label} - ${isDone ? 'completed' : isActive ? 'current' : 'pending'}`}
                        >
                            {isDone ? '✓' : step.icon}
                        </div>

                        {/* Step label */}
                        <span className={`step-label ${isDone ? 'done' : ''} ${isActive ? 'active' : ''}`}>
                            {step.label}
                        </span>

                        {/* Connector line between steps */}
                        {index < STEPS.length - 1 && (
                            <div className={`step-connector ${isDone ? 'done' : ''}`} />
                        )}
                    </div>
                );
            })}
        </div>
    );
};

export default StepIndicator;
