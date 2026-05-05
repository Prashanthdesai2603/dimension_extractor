# 📐 Engineering Drawing Dimension Extractor

Welcome to the **Dimension Extractor** project. This tool automates the extraction of dimensional data (Values, Units, Tolerances) from engineering drawings (PDFs/Scans) using a hybrid approach of Vector Parsing and Local AI (PaddleOCR/docTR).

---

## 🚀 1. The Core Objective
This tool provides a professional workflow for technical data extraction:
1.  **Upload**: Upload a PDF via the React portal.
2.  **Detection**: Backend runs a Hybrid Pipeline to suggest initial dimension locations.
3.  **Refine**: Use the interactive Konva.js canvas to adjust or add red bounding boxes.
4.  **Extract**: Backend crops these specific regions and runs high-precision OCR.
5.  **Export**: Data is parsed into structured fields and exported as a `.txt` report.

---

## 🛠️ 2. Technology Stack
*   **Backend**: Django 4.2 (Python), PaddleOCR, docTR, OpenCV, PyMuPDF.
*   **Frontend**: React 18, Konva.js (Canvas API), Axios, Bootstrap 5.
*   **Database**: MySQL.

---

## 💻 3. Setup from Scratch (GitHub Clone)

Follow these steps to set up the project on a new system.

### 📋 Prerequisites
*   **Python**: 3.10 or higher.
*   **Node.js**: 18.x or higher.
*   **MySQL**: Installed and running.
*   **Poppler**: Required for `pdf2image`. 
    *   *Windows*: Download from [GitHub](https://github.com/oschwartz10612/poppler-windows/releases) and add the `bin` folder to your System PATH.
    *   *Linux*: `sudo apt-get install poppler-utils`.

### 📂 Step 1: Clone the Repository
```bash
git clone <your-repository-url>
cd dimension_extractor
```

### 🗄️ Step 2: Database Setup
1. Open your MySQL terminal or GUI (like Workbench).
2. Create a new database:
   ```sql
   CREATE DATABASE dimension_db;
   ```

### 🐍 Step 3: Backend Configuration
1. Navigate to the backend folder:
   ```bash
   cd backend
   ```
2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Configure environment variables:
   *   Create a `.env` file in the `backend/` directory.
   *   Copy the following and update with your MySQL credentials:
   ```env
   SECRET_KEY=your-secret-key
   DEBUG=True
   DB_NAME=dimension_db
   DB_USER=your_username
   DB_PASSWORD=your_password
   DB_HOST=localhost
   DB_PORT=3306
   ```
5. Run migrations:
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```
6. Start the server:
   ```bash
   python manage.py runserver
   ```

### ⚛️ Step 4: Frontend Configuration
1. Open a new terminal and navigate to the frontend folder:
   ```bash
   cd frontend
   ```
2. Install dependencies:
   ```bash
   npm install
   ```
3. Start the React app:
   ```bash
   npm start
   ```

---

## 📂 4. Project Structure
*   `backend/services/`: Contains the OCR logic, vector engines, and parsing heuristics.
*   `backend/extractor/`: Django app handling API endpoints and database models.
*   `frontend/src/components/`: React components for the interactive drawing viewer.

---

## 🔄 5. Processing Flow
```mermaid
graph TD
    A[User Uploads PDF] --> B{Is it a Vector PDF?}
    B -- Yes --> C[PyMuPDF Vector Extraction]
    B -- No --> D[PaddleOCR Local AI Engine]
    C --> E[Spatial Grouping Engine]
    D --> E
    E --> F[Heuristic Noise Filter]
    F --> G[Display Boxes in React Canvas]
    G --> H[User Refines Boxes]
    H --> I[OpenCV Targeted Crop]
    I --> J[Paddle Multi-Orientation OCR]
    J --> K[Regex Parsing & Tolerance Logic]
    K --> L[Generate Final .txt Export]
```

---
*Updated: May 2026*  
*This project is optimized for local execution without cloud dependencies (Google Vision/Gemini).*




