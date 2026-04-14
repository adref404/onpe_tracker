# 🗳️ ONPE Election Tracker 2026

Dashboard en tiempo real para seguir los resultados electorales de Perú 2026.
Compara candidatos, ve quién va ganando y sigue el historial completo de la batalla.

**Stack:** FastAPI · Supabase (PostgreSQL) · Vercel · Render

---

## 🚀 Deploy paso a paso

### 1. Supabase — Base de datos

1. Ve a [supabase.com](https://supabase.com) → **New project**
2. Copia tu `Project URL` y `anon public key` (Settings → API)
3. Ve a **SQL Editor** y ejecuta:

```sql
CREATE TABLE snapshots (
  id                        BIGSERIAL PRIMARY KEY,
  timestamp                 TIMESTAMPTZ NOT NULL,
  dni_candidato             TEXT,
  nombre_candidato          TEXT,
  nombre_partido            TEXT,
  codigo_partido            INT,
  total_votos_validos       BIGINT DEFAULT 0,
  porcentaje_votos_validos  FLOAT DEFAULT 0,
  porcentaje_votos_emitidos FLOAT DEFAULT 0,
  pct_actas_contabilizadas  FLOAT,
  total_actas               INT
);

-- Índices para consultas rápidas
CREATE INDEX idx_snapshots_timestamp     ON snapshots(timestamp DESC);
CREATE INDEX idx_snapshots_dni           ON snapshots(dni_candidato);
CREATE INDEX idx_snapshots_dni_timestamp ON snapshots(dni_candidato, timestamp DESC);
```

---

### 2. Backend — Render

1. Sube el proyecto a GitHub
2. Ve a [render.com](https://render.com) → **New Web Service**
3. Conecta tu repo → selecciona la carpeta `backend/`
4. Configura:
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. En **Environment Variables** agrega:
   - `SUPABASE_URL` → tu URL de Supabase
   - `SUPABASE_KEY` → tu anon key de Supabase
6. Deploy → copia la URL que te da Render (ej: `https://onpe-tracker.onrender.com`)

---

### 3. Frontend — Vercel

1. En `frontend/index.html`, reemplaza esta línea:
   ```js
   : 'https://TU-BACKEND.onrender.com';
   ```
   por la URL real de tu backend en Render.

2. Ve a [vercel.com](https://vercel.com) → **New Project**
3. Conecta tu repo → selecciona la carpeta `frontend/`
4. Deploy → listo 🎉

---

## 🖥️ Desarrollo local

```bash
# Backend
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1       # Windows
source venv/bin/activate           # Mac/Linux

pip install -r requirements.txt

# Crea tu .env con las credenciales de Supabase
cp .env.example .env
# Edita .env con tus valores reales

uvicorn main:app --reload
# Backend corre en http://localhost:8000
```

Abre `frontend/index.html` directamente en el navegador
(ya detecta automáticamente si estás en localhost).

---

## 📡 Endpoints de la API

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/` | Health check |
| GET | `/api/latest` | Último snapshot completo |
| GET | `/api/candidates` | Lista de candidatos |
| GET | `/api/battle?dni_a=X&dni_b=Y&horas=24` | Historial de batalla entre 2 candidatos |
| POST | `/api/fetch` | Forzar captura manual |

---

## 📁 Estructura del proyecto

```
onpe-tracker/
├── backend/
│   ├── main.py           ← FastAPI app + scheduler
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   └── index.html        ← Dashboard completo
└── README.md
```

---

## ✨ Features

- ⚔️ **Batalla entre cualquier par de candidatos** — seleccionable desde la UI
- 📊 **Rankings en tiempo real** de todos los candidatos
- 📈 **Gráfico histórico** que persiste en Supabase (no se borra al recargar)
- 🔄 **Auto-refresh cada 3 minutos**
- ☁️ **100% en la nube** — no necesita PC encendida

---

*Datos oficiales: [resultadoelectoral.onpe.gob.pe](https://resultadoelectoral.onpe.gob.pe)*
