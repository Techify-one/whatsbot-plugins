"""REST do plugin (montado em /api/plugins/agendamento_e_retorno).

Shell fino sobre ``logic``. As settings usam o endpoint genérico do core
(``/api/plugins/<id>/settings``) — a tela de configuração fala com ele direto.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from . import common, logic

router = APIRouter()


def _err(msg: str, status: int = 400):
    return JSONResponse({"ok": False, "error": msg}, status_code=status)


@router.get("/items")
async def list_items(status: str | None = None, phone: str | None = None,
                     contact_id: int | None = None):
    return {"ok": True, "data": logic.list_items(status=status, phone=phone, contact_id=contact_id)}


@router.post("/items")
async def create_item(body: dict):
    item, err = logic.create_item(
        phone=(body.get("phone") or "").strip(),
        contact_name=(body.get("contact_name") or "").strip() or None,
        due_at=body.get("due_at"),
        description=body.get("description"),
    )
    if err:
        return _err(err)
    return {"ok": True, "data": item}


@router.post("/items/{item_id}/cancel")
async def cancel_item(item_id: int):
    item, err = logic.cancel_item(item_id)
    if err:
        return _err(err, status=404)
    return {"ok": True, "data": item}


@router.delete("/items/{item_id}")
async def delete_item(item_id: int):
    if not logic.delete_item(item_id):
        return _err("Agendamento não encontrado.", status=404)
    return {"ok": True}


@router.get("/status")
async def status():
    """Avisos para a tela de configuração (plugins antigos ainda habilitados)."""
    legacy = common.legacy_enabled()
    return {"ok": True, "data": {
        "legacy_enabled": legacy,
        "auto_paused": "retorno_automatico" in legacy,
    }}
