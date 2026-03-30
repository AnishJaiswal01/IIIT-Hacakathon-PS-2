# Autonomous Structural Intelligence System (ASIS) 🏗️🤖

**IIIT Hackathon — Problem Statement 2 (Hard Difficulty)**

ASIS is an AI-powered pipeline that takes a standard 2D digital floor plan image, automatically reconstructs it as a 3D structural model, and recommends optimal construction materials by analyzing cost vs. strength tradeoffs—complete with human-readable justifications.

## 🚀 The Core Pipeline
1. **Floor Plan Parsing (OpenCV):** Detects walls, rooms, and openings from raw 2D image pixels without relying on text labels.
2. **Geometry Reconstruction (Shapely):** Converts detected elements into an orthogonal architectural graph, enforcing structural boundaries.
3. **3D Generation (Three.js):** Extrudes the 2D layout into a fully viewable, interactive 3D structural twin.
4. **Material Optimization (LLM):** Cross-references structural elements against a material database to calculate Cost-Strength tradeoffs.
5. **Explainable AI (XAI):** Generates plain-language reports justifying why specific materials (e.g., AAC Blocks vs. RCC) were chosen.

## 💻 Tech Stack
* **Frontend:** React, Three.js, Node.js
* **Backend:** FastAPI, Python
* **Computer Vision:** OpenCV, Shapely
* **Intelligence:** LLM API Integration

## 📂 Repository Structure
* `/backend` - FastAPI server, OpenCV parsing logic, and LLM material generation routes.
* `/frontend` - React application and Three.js 3D viewer.

