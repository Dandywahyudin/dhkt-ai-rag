import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import io
import time
import pymupdf
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.security import generate_hmac_signature
from app.main import app
from app.services.pdf_service import pdf_service
from app.services.rag_service import rag_service
from app.services.vector_store import get_vector_store


def create_sample_pdf() -> bytes:
    """Create a sample in-memory PDF for testing."""
    doc = pymupdf.open()

    page1 = doc.new_page()
    page1.insert_text(
        (50, 72),
        "STANDAR OPERASIONAL PROSEDUR (SOP) DHKT ITB\n\n"
        "Bab 1: Peminjaman Ruangan dan Fasilitas\n"
        "1.1 Setiap civitas akademika berhak mengajukan peminjaman ruangan seminar.\n"
        "1.2 Pengajuan peminjaman harus diajukan minimal 3 hari kerja sebelum acara.\n"
        "1.3 Batas maksimal durasi peminjaman adalah 3 hari berturut-turut.\n"
        "1.4 Ruangan yang dipinjam wajib dijaga kebersihan dan ketertibannya.",
        fontsize=12,
    )

    page2 = doc.new_page()
    page2.insert_text(
        (50, 72),
        "Bab 2: Pemeliharaan Aset dan Sarana\n"
        "2.1 Kerusakan fasilitas harus dilaporkan melalui formulir pengaduan helpdesk.\n"
        "2.2 Petugas teknisi akan melakukan peninjauan dalam waktu 1x24 jam kerja.\n"
        "2.3 Biaya perbaikan kerusakan akibat kelalaian ditanggung oleh unit terkait.",
        fontsize=12,
    )

    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def test_pdf_extraction_and_chunking():
    """Verify PDF extraction and semantic chunking."""
    pdf_bytes = create_sample_pdf()
    chunks = pdf_service.process_pdf(
        file_source=pdf_bytes,
        document_id="test_sop_01",
        doc_title="SOP Pengujian",
        allowed_roles=["admin", "staff"],
    )

    assert len(chunks) >= 2
    assert chunks[0]["document_id"] == "test_sop_01"
    assert "Peminjaman" in chunks[0]["text"]
    assert chunks[0]["page"] in [1, 2]
    print(f"PDF extraction verified: {len(chunks)} chunks produced.")


def test_fastapi_endpoints():
    """Verify FastAPI endpoints via TestClient."""
    client = TestClient(app)

    # 1. Root & Health
    res_root = client.get("/")
    assert res_root.status_code == 200
    assert res_root.json()["status"] == "running"

    res_health = client.get("/v1/health")
    assert res_health.status_code == 200
    assert res_health.json()["status"] == "healthy"
    print("Health and Root endpoints verified.")

    # 2. Upload PDF
    pdf_bytes = create_sample_pdf()
    files = {"file": ("sop_dummy.pdf", pdf_bytes, "application/pdf")}
    data = {
        "document_id": "doc_test_100",
        "doc_title": "SOP Peminjaman Ruangan",
        "allowed_roles": "admin,staff",
    }
    res_upload = client.post("/v1/documents/upload", files=files, data=data)
    assert res_upload.status_code == 200
    upload_json = res_upload.json()
    assert upload_json["status"] == "success"
    assert upload_json["document_id"] == "doc_test_100"
    assert upload_json["chunks_count"] >= 2
    print(f"Document upload verified: {upload_json['chunks_count']} chunks indexed.")

    # 3. List Documents
    res_list = client.get("/v1/documents")
    assert res_list.status_code == 200
    list_json = res_list.json()
    assert list_json["total"] >= 1
    print(f"Document listing verified: {list_json['total']} documents found.")

    # 4. Chat Endpoint
    chat_payload = {
        "session_id": "test-session-01",
        "message": "Berapa hari minimal pengajuan peminjaman ruangan?",
        "user_context": {
            "id": 1,
            "role": "staff",
            "unit": "DHKT",
        },
        "history": [],
    }
    res_chat = client.post("/v1/chat", json=chat_payload)
    assert res_chat.status_code == 200
    chat_json = res_chat.json()
    assert chat_json["status"] == "success"
    assert "reply" in chat_json
    assert "**" not in chat_json["reply"], "Output chat tidak boleh mengandung tanda bintang (**)"
    assert len(chat_json["sources"]) > 0
    print("Chat endpoint verified. Clean reply (no asterisks). Top source score:", chat_json["sources"][0]["score"])

    # 4b. Form Autofill Detection in Chat
    form_payload = {
        "session_id": "test-form-01",
        "message": "Tolong buatkan peminjaman Ruang Miting 08 di STP Gedebage untuk Jumat berkah 30-10-2026 jam 07:00-16:00 dengan 13 orang dari unit DKST Sarpras",
        "user_context": {"id": 1, "role": "staff", "unit": "DHKT"},
        "history": [],
    }
    res_form = client.post("/v1/chat", json=form_payload)
    assert res_form.status_code == 200
    form_json = res_form.json()
    assert form_json.get("form_data") is not None, "form_data harus diekstrak untuk perintah peminjaman"
    assert form_json["form_data"].get("participant_count") == 13
    print("Chat Form Autofill verified: extracted form_data successfully.")

    # 5. Delete Document
    res_delete = client.delete("/v1/documents/doc_test_100")
    assert res_delete.status_code == 200
    assert res_delete.json()["status"] == "success"
    print("Document deletion verified.")


def test_hmac_signature():
    """Verify HMAC signature generation and validation."""
    client = TestClient(app)
    secret = settings.AI_INTERNAL_HMAC_SECRET

    import json
    timestamp = str(int(time.time()))
    payload = {"session_id": "test-session-hmac", "message": "Halo test"}
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    valid_sig = generate_hmac_signature(timestamp, body, secret)

    # Valid signature
    headers = {
        "Content-Type": "application/json",
        "X-Timestamp": timestamp,
        "X-CI4-Signature": valid_sig,
    }
    res_valid = client.post("/v1/chat", headers=headers, content=body)
    assert res_valid.status_code == 200

    # Invalid signature should be rejected with 403
    bad_headers = {
        "Content-Type": "application/json",
        "X-Timestamp": timestamp,
        "X-CI4-Signature": "invalid_signature_hash_12345",
    }
    res_invalid = client.post("/v1/chat", headers=bad_headers, content=body)
    assert res_invalid.status_code == 403
    print("HMAC verification verified: valid passes, invalid rejected (403).")

def test_tool_calling():
    """Verify Tool Calling integration via FastAPI chat endpoint."""
    client = TestClient(app)

    # 1. Query about submission status
    chat_payload = {
        "session_id": "test-session-tool",
        "message": "Tolong cek status pengajuan saya terbaru",
        "user_context": {
            "id": 101,
            "role": "staff",
            "unit": "DHKT",
        },
    }
    res = client.post("/v1/chat", json=chat_payload)
    assert res.status_code == 200
    res_json = res.json()
    assert "tools_used" in res_json
    assert "get_my_submission_status" in res_json["tools_used"]
    assert "pengajuan" in res_json["reply"].lower()
    print("Tool Calling (get_my_submission_status) verified: tools_used =", res_json["tools_used"])

    # 2. Query about summary stats
    chat_payload_stats = {
        "session_id": "test-session-stats",
        "message": "Berapa total statistik rekap pengajuan sistem?",
        "user_context": {
            "id": 1,
            "role": "admin",
        },
    }
    res_stats = client.post("/v1/chat", json=chat_payload_stats)
    assert res_stats.status_code == 200
    stats_json = res_stats.json()
    assert "get_dhkt_summary_stats" in stats_json["tools_used"]
    print("Tool Calling (get_dhkt_summary_stats) verified: tools_used =", stats_json["tools_used"])


if __name__ == "__main__":
    print("Running RAG verification tests...")
    test_pdf_extraction_and_chunking()
    test_fastapi_endpoints()
    test_hmac_signature()
    test_tool_calling()
    print("ALL TESTS PASSED SUCCESSFULLY!")
