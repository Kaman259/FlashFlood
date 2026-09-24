# FlashFlood

**Hyperlocal Early-Warning & Resilient Evacuation Support System**

FlashFlood is an educational prototype for demonstrating a local flash-flood warning and evacuation-support workflow. It is not an operational emergency-warning system.

## Stage 1 status

This stage contains only the project skeleton and runnable frontend/backend setup.

Implemented:

- React + Vite frontend
- Tailwind CSS via the official Vite plugin
- FastAPI backend application bootstrap
- Environment templates
- Git ignore rules for secrets, virtual environments, build output, Firebase Admin files, and local databases
- Base documentation structure

Not implemented yet:

- Health endpoint
- Warning state machine
- River telemetry
- Open-Meteo integration
- Dashboard API connection
- Map, risk polygons, shelters, geolocation
- Firebase, notifications, SMS simulation, offline support

## Requirements

- Git
- Node.js 20.19+ or 22.12+
- npm
- Python 3.10+

## Run backend

### Windows PowerShell

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
fastapi dev app/main.py
```

The API server should start on `http://127.0.0.1:8000`. No custom endpoint is expected in Stage 1. FastAPI's generated docs are available at `/docs`.

## Run frontend

Open a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

## Production build check

```powershell
cd frontend
npm run build
```

A successful build creates `frontend/dist/`.
