from fastapi import APIRouter, Depends, HTTPException, status
from ....core.security import verify_ci4_signature
from ....schemas.chat import ChatRequest, ChatResponse
from ....services.rag_service import rag_service

router = APIRouter()


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Kirim pertanyaan chat untuk dijawab oleh AI menggunakan konteks PDF RAG",
    dependencies=[Depends(verify_ci4_signature)],
)
async def chat_endpoint(request: ChatRequest) -> ChatResponse:
    """
    Endpoint utama percakapan AI RAG.
    Menerima pertanyaan, melakukan pencarian dokumen semantik di vector store,
    dan memanggil Gemini LLM untuk mensintesis jawaban berbasis konteks.
    Mendukung verifikasi HMAC dari CodeIgniter 4.
    """
    try:
        history_dicts = [
            {"role": msg.role, "content": msg.content}
            for msg in (request.history or [])
        ]

        response = await rag_service.answer_chat(
            session_id=request.session_id or "default-session",
            message=request.message,
            user_context=request.user_context,
            history=history_dicts,
        )
        return response

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal memproses permintaan chat: {str(e)}",
        )
