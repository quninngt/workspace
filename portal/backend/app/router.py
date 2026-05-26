"""FastAPI router for the service portal."""
import asyncio
from fastapi import APIRouter, HTTPException
from app.services import SERVICES, get_service_status, start_backend, start_frontend, stop_service, restart_service

router = APIRouter(prefix="/api")


@router.get("/services")
async def list_services():
    """List all services with their current status."""
    results = await asyncio.gather(*[get_service_status(s) for s in SERVICES])
    return {"services": results}


@router.get("/services/{service_id}")
async def service_detail(service_id: str):
    """Get detailed status for a single service."""
    svc = next((s for s in SERVICES if s["id"] == service_id), None)
    if not svc:
        raise HTTPException(status_code=404, detail="Service not found")
    return await get_service_status(svc)


@router.post("/services/{service_id}/start")
async def start_service(service_id: str):
    """Start a service (both backend and frontend)."""
    svc = next((s for s in SERVICES if s["id"] == service_id), None)
    if not svc:
        raise HTTPException(status_code=404, detail="Service not found")
    
    bk = start_backend(svc)
    ft = start_frontend(svc)
    
    return {
        "id": service_id,
        "backend_started": bk,
        "frontend_started": ft,
    }


@router.post("/services/{service_id}/stop")
async def stop_service_endpoint(service_id: str):
    """Stop a service."""
    svc = next((s for s in SERVICES if s["id"] == service_id), None)
    if not svc:
        raise HTTPException(status_code=404, detail="Service not found")
    
    result = stop_service(svc)
    return {"id": service_id, **result}


@router.post("/services/{service_id}/restart")
async def restart_service_endpoint(service_id: str):
    """Restart a service."""
    svc = next((s for s in SERVICES if s["id"] == service_id), None)
    if not svc:
        raise HTTPException(status_code=404, detail="Service not found")
    
    result = restart_service(svc)
    return {"id": service_id, **result}
