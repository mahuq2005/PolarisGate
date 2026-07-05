from fastapi import APIRouter, BackgroundTasks, HTTPException
from shared.models.trace import TraceIn, TraceOut
from ..services.trace_ingestion import ingest_trace, publish_to_stream
import uuid, re
from shared.redis_client import get_redis

router = APIRouter()

@router.post("/", response_model=TraceOut, status_code=201)
async def create_trace(trace: TraceIn, background_tasks: BackgroundTasks, idempotency_key: str = None):
    # Input sanitisation
    trace.prompt = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', trace.prompt)
    trace.completion = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', trace.completion)

    if idempotency_key:
        redis = await get_redis()
        key = f"idempotent:{idempotency_key}"
        existing = await redis.get(key)
        if existing:
            return TraceOut(id=existing, status="already_received")
        trace_id = str(uuid.uuid4())
        await redis.setex(key, 86400, trace_id)
    else:
        trace_id = str(uuid.uuid4())

    await ingest_trace(trace, trace_id)
    background_tasks.add_task(publish_to_stream, trace, trace_id)
    return TraceOut(id=trace_id, status="received")
