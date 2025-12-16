from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

router = APIRouter()

class ResearchRequest(BaseModel):
    query: str
    mode: str = "realtime"  # realtime | background


@router.post("/start")
async def start_research(request: ResearchRequest):
    """백그라운드 리서치 시작"""
    # TODO: Celery 태스크 등록
    return {
        "session_id": "temp-session-id",
        "status": "queued",
        "message": "리서치가 시작되었습니다"
    }


@router.get("/status/{session_id}")
async def get_research_status(session_id: str):
    """리서치 진행 상태 조회"""
    # TODO: DB에서 상태 조회
    return {
        "session_id": session_id,
        "status": "in_progress",
        "progress": 50
    }


@router.websocket("/ws/{session_id}")
async def research_websocket(websocket: WebSocket, session_id: str):
    """실시간 리서치 스트리밍"""
    await websocket.accept()

    try:
        while True:
            # TODO: 에이전트 실행 및 실시간 전송
            data = await websocket.receive_text()
            await websocket.send_json({
                "type": "thinking",
                "message": f"'{data}' 에 대해 조사 중..."
            })
    except WebSocketDisconnect:
        print(f"WebSocket 연결 종료: {session_id}")