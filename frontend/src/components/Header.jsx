/**
 * Header.jsx
 * Application top navigation bar.
 * Displays brand logo, title, and an "Internal Tool" badge.
 */

import React from 'react';

const Header = () => {
    return (
        <header className="app-header">
            <div className="header-inner">
                {/* Brand section */}
                <div className="header-brand">
                    <div className="header-logo">
                        📐
                    </div>
                    <div>
                        <div className="header-title">Dimension Extractor</div>
                        <div className="header-subtitle">Engineering Drawing OCR Tool</div>
                    </div>
                </div>

                {/* Badge */}
                <div className="header-badge">
                    🏭 Internal Tool
                </div>
            </div>
        </header>
    );
};

export default Header;
