# Deploying to Render — Step-by-Step Guide

This guide explains how to deploy the **National Weather Big Data Analytics Platform** on [Render](https://render.com) using the included `render.yaml` Blueprint.

---

## Prerequisites

1. A [Render Account](https://render.com) (Free tier supported).
2. Your GitHub account connected to Render with access to:
   `https://github.com/raghvendra1gdsc-png/sih_structural_platform`

---

## Option 1: One-Click Blueprint Deployment (Recommended)

The repository includes a root [`render.yaml`](../render.yaml) specification that automatically provisions and links all required resources:
- **Managed PostgreSQL Database (`sih-weather-db`)** with PostGIS enabled
- **FastAPI Backend Web Service (`sih-weather-backend`)**
- **Next.js Command Center Frontend (`sih-weather-frontend`)**

### Steps:
1. Log in to your [Render Dashboard](https://dashboard.render.com).
2. Click **New +** in the top-right corner and select **Blueprint**.
3. Select your repository: **`raghvendra1gdsc-png/sih_structural_platform`** (branch: `main`).
4. Render will parse `render.yaml` and display the resources to be created:
   * `sih-weather-db` (PostgreSQL Database)
   * `sih-weather-backend` (Docker Web Service)
   * `sih-weather-frontend` (Node Web Service)
5. Under **Environment Variables**, if prompted, you may optionally supply:
   * `GOOGLE_AI_STUDIO_KEY` (for Gemini-powered WeatherGPT decision support)
   * `OPENAI_API_KEY` (if using OpenAI backend)
6. Click **Apply**.
7. Render will automatically:
   * Provision the PostgreSQL database.
   * Run database migrations (`alembic upgrade head`) and seed Indian weather demo data (`python -m demo.seed`).
   * Build the Next.js frontend and link it to the backend service.

---

## Option 2: Manual Service Deployment

If you prefer configuring services manually in the Render UI:

### 1. Database (PostgreSQL)
1. **New +** -> **PostgreSQL**.
2. Name: `sih-weather-db`.
3. Database: `weather_db`, User: `sih_user`.
4. Plan: **Free**.
5. Once created, copy the **Internal Database URL**.

### 2. Backend (FastAPI Web Service)
1. **New +** -> **Web Service**.
2. Connect `raghvendra1gdsc-png/sih_structural_platform`.
3. Name: `sih-weather-backend`.
4. Runtime: **Docker** (`backend.Dockerfile`).
5. Start Command:
   ```bash
   sh -c "alembic upgrade head && python -m demo.seed && uvicorn backend.main:app --host 0.0.0.0 --port $PORT"
   ```
6. Add Environment Variables:
   * `DATABASE_URL`: *(paste Internal Database URL)*
   * `ENVIRONMENT`: `production`
   * `CORS_ORIGINS`: `*`
   * `CARTO_API_KEY`: `cb1_2yru_1_be975c21c3c99af922bcf25c`
   * `NEXT_PUBLIC_CARTO_API_KEY`: `cb1_2yru_1_be975c21c3c99af922bcf25c`
   * `OPENWEATHER_API_KEY`: `268a83a22f0b1f62b3a4d43dc06e9244`
   * `WEATHERAPI_KEY`: `188001067e024ac09d8152440260409`
   * `TOMORROW_IO_API_KEY`: `L3oS6sFKMC6R61QJmWJtgRmnqV5vOyIU`
   * `LLM_BACKEND`: `gemini`
   * `GOOGLE_AI_STUDIO_KEY`: *(your Gemini key)*

### 3. Frontend (Next.js Web Service)
1. **New +** -> **Web Service**.
2. Connect `raghvendra1gdsc-png/sih_structural_platform`.
3. Name: `sih-weather-frontend`.
4. Runtime: **Node**.
5. Root Directory: `frontend`.
6. Build Command: `npm install && npm run build`.
7. Start Command: `npm start`.
8. Add Environment Variables:
   * `NEXT_PUBLIC_API_URL`: `https://sih-weather-backend.onrender.com` *(use your backend's Render URL)*
   * `NEXT_PUBLIC_CARTO_API_KEY`: `cb1_2yru_1_be975c21c3c99af922bcf25c`
   * `NEXT_PUBLIC_MAPTILER_KEY`: `JAI9tztyvk89wmyqsDWx`
   * `NODE_ENV`: `production`
