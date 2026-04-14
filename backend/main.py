"""
ONPE Election Tracker - Backend
FastAPI + Supabase + APScheduler

Endpoints:
  GET /                     → health check
  GET /api/latest           → último snapshot de todos los candidatos
  GET /api/history          → historial de snapshots (últimas 24h)
  GET /api/battle           → datos de la batalla entre 2 candidatos por DNI
  POST /api/fetch           → forzar captura manual (útil para testing)
"""

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
from supabase import create_client, Client
from datetime import datetime, timedelta
import requests
import os
import json
from dotenv import load_dotenv

load_dotenv()

# ── CONFIG ────────────────────────────────────────────────────
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
ONPE_BASE    = "https://resultadoelectoral.onpe.gob.pe/presentacion-backend/resumen-general"

ONPE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "*/*",
    "Referer": "https://resultadoelectoral.onpe.gob.pe/",
}

# ── APP ───────────────────────────────────────────────────────
app = FastAPI(title="ONPE Election Tracker", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── SUPABASE CLIENT ───────────────────────────────────────────
def get_supabase() -> Client:
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise HTTPException(500, "Supabase no configurado. Revisa las variables de entorno.")
    return create_client(SUPABASE_URL, SUPABASE_KEY)

# ── FETCH ONPE ────────────────────────────────────────────────
def fetch_and_save():
    """Consulta la API de ONPE y guarda un snapshot en Supabase."""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Fetching ONPE data...")
    try:
        # Participantes presidencial
        r1 = requests.get(
            f"{ONPE_BASE}/participantes?idEleccion=10&tipoFiltro=eleccion",
            headers=ONPE_HEADERS, timeout=15
        )
        data1 = json.loads(r1.content.decode("utf-8").strip())
        participantes = data1.get("data", [])

        # Totales
        totales = {}
        try:
            r2 = requests.get(
                f"{ONPE_BASE}/totales?idEleccion=10&tipoFiltro=eleccion",
                headers=ONPE_HEADERS, timeout=15
            )
            data2 = json.loads(r2.content.decode("utf-8").strip())
            totales = data2.get("data", {}) or {}
        except Exception as e:
            print(f"  [WARN] totales: {e}")

        if not participantes:
            print("  [WARN] Sin participantes, saltando...")
            return

        # Guardar en Supabase
        supabase = get_supabase()
        timestamp = datetime.utcnow().isoformat()

        # Un registro por candidato en este snapshot
        rows = []
        for c in participantes:
            rows.append({
                "timestamp":               timestamp,
                "dni_candidato":           c.get("dniCandidato"),
                "nombre_candidato":        c.get("nombreCandidato"),
                "nombre_partido":          c.get("nombreAgrupacionPolitica"),
                "codigo_partido":          c.get("codigoAgrupacionPolitica"),
                "total_votos_validos":     c.get("totalVotosValidos", 0),
                "porcentaje_votos_validos":c.get("porcentajeVotosValidos", 0.0),
                "porcentaje_votos_emitidos":c.get("porcentajeVotosEmitidos", 0.0),
                "pct_actas_contabilizadas":totales.get("porcentajeActasContabilizadas"),
                "total_actas":             totales.get("totalActas"),
            })

        supabase.table("snapshots").insert(rows).execute()
        print(f"  [OK] {len(rows)} candidatos guardados — {timestamp}")

    except Exception as e:
        print(f"  [ERROR] fetch_and_save: {e}")


# ── SCHEDULER ────────────────────────────────────────────────
scheduler = BackgroundScheduler()
scheduler.add_job(fetch_and_save, "interval", minutes=3, id="onpe_fetch")
scheduler.start()


# ── ENDPOINTS ────────────────────────────────────────────────

@app.get("/")
def health():
    return {"status": "ok", "service": "ONPE Election Tracker", "time": datetime.utcnow().isoformat()}


@app.get("/api/latest")
def get_latest():
    """Retorna el snapshot más reciente de todos los candidatos, ordenados por votos."""
    supabase = get_supabase()

    # Obtener el timestamp más reciente
    latest = (
        supabase.table("snapshots")
        .select("timestamp")
        .order("timestamp", desc=True)
        .limit(1)
        .execute()
    )
    if not latest.data:
        raise HTTPException(404, "No hay datos aún. Espera la primera captura.")

    ts = latest.data[0]["timestamp"]

    # Todos los candidatos de ese snapshot
    rows = (
        supabase.table("snapshots")
        .select("*")
        .eq("timestamp", ts)
        .order("total_votos_validos", desc=True)
        .execute()
    )

    return {
        "timestamp": ts,
        "candidatos": rows.data,
        "pct_actas": rows.data[0].get("pct_actas_contabilizadas") if rows.data else None,
    }


@app.get("/api/battle")
def get_battle(
    dni_a: str = Query("07845838", description="DNI candidato A (default: López Aliaga)"),
    dni_b: str = Query("06506278", description="DNI candidato B (default: Nieto Montesinos)"),
    horas: int = Query(720, description="Horas de historial a retornar (default 30 dias)")
):
    """
    Retorna el historial de 2 candidatos para mostrar la batalla entre ellos.
    Por defecto: López Aliaga vs Nieto Montesinos.
    """
    supabase = get_supabase()
    desde = (datetime.utcnow() - timedelta(hours=horas)).isoformat()

    rows = (
        supabase.table("snapshots")
        .select("timestamp, dni_candidato, nombre_candidato, nombre_partido, total_votos_validos, porcentaje_votos_validos, pct_actas_contabilizadas")
        .in_("dni_candidato", [dni_a, dni_b])
        .gte("timestamp", desde)
        .order("timestamp", desc=False)
        .execute()
    )

    # Agrupar por timestamp
    timeline = {}
    for row in rows.data:
        ts = row["timestamp"]
        if ts not in timeline:
            timeline[ts] = {"timestamp": ts, "candidatos": {}}
        timeline[ts]["candidatos"][row["dni_candidato"]] = row

    # Construir series ordenadas
    snapshots = sorted(timeline.values(), key=lambda x: x["timestamp"])

    # Datos del último snapshot para el header
    latest_a = next((r for r in reversed(rows.data) if r["dni_candidato"] == dni_a), None)
    latest_b = next((r for r in reversed(rows.data) if r["dni_candidato"] == dni_b), None)

    return {
        "candidato_a": latest_a,
        "candidato_b": latest_b,
        "timeline":    snapshots,
        "total_snapshots": len(snapshots),
    }


@app.get("/api/candidates")
def get_candidates():
    """Lista todos los candidatos disponibles (del último snapshot)."""
    supabase = get_supabase()

    latest = (
        supabase.table("snapshots")
        .select("timestamp")
        .order("timestamp", desc=True)
        .limit(1)
        .execute()
    )
    if not latest.data:
        raise HTTPException(404, "No hay datos aún.")

    ts = latest.data[0]["timestamp"]
    rows = (
        supabase.table("snapshots")
        .select("dni_candidato, nombre_candidato, nombre_partido, total_votos_validos, porcentaje_votos_validos")
        .eq("timestamp", ts)
        .order("total_votos_validos", desc=True)
        .execute()
    )
    return {"candidatos": rows.data}


@app.post("/api/fetch")
def force_fetch():
    """Fuerza una captura manual. Útil para testing."""
    fetch_and_save()
    return {"status": "ok", "message": "Captura forzada completada"}


# ── STARTUP ───────────────────────────────────────────────────
@app.on_event("startup")
async def on_startup():
    print("🚀 ONPE Tracker iniciado")
    print(f"   Supabase: {'✓ configurado' if SUPABASE_URL else '✗ falta SUPABASE_URL'}")
    # Primera captura al iniciar
    import threading
    threading.Thread(target=fetch_and_save, daemon=True).start()
