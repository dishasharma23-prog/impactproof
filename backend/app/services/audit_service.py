from app.models import domain


def log(db, entity_type: str, entity_id: int, action: str, summary: str, detail: dict | None = None,
        actor: str = "system"):
    db.add(domain.AuditEvent(entity_type=entity_type, entity_id=entity_id, action=action, summary=summary,
                             detail=detail, actor=actor or "system"))


def to_dict(e: domain.AuditEvent) -> dict:
    return {"id": e.id, "entity_type": e.entity_type, "entity_id": e.entity_id, "action": e.action,
            "summary": e.summary, "detail": e.detail, "actor": e.actor,
            "created_at": e.created_at.isoformat() if e.created_at else None}
