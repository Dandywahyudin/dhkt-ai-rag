# DHKT AI — Microservice RAG Dokumen PDF (Python FastAPI + Gemini API)

Projek **RAG (Retrieval-Augmented Generation)** berbasis **Python FastAPI** yang dirancang sederhana, modular, dan mudah dikembangkan untuk menjawab pertanyaan berdasarkan dokumen PDF internal dengan **Google Gemini API**, serta siap diintegrasikan secara langsung dengan aplikasi web **CodeIgniter 4**.

---

## 🌟 Fitur Utama

1. **Pembaca & Parser PDF Cerdas**:
   - Mengekstrak teks per halaman dari dokumen `.pdf` menggunakan **PyMuPDF (`pymupdf`)**.
   - Memecah teks dokumen secara semantik (*chunking*) dengan **LangChain Text Splitters** (`RecursiveCharacterTextSplitter`) dengan informasi nomor halaman (*page number*) dan judul dokumen.

2. **Dual-Support Vector Store**:
   - **Local Vector Store (Default)**: Berjalan langsung tanpa perlu menginstal Docker atau database tambahan. Menggunakan **NumPy** untuk perhitungan cosine similarity dan menyimpan vektor secara persisten di folder `storage/index/`.
   - **Qdrant Vector DB (Scalable Option)**: Cukup ubah konfigurasi `.env` (`VECTOR_STORE_BACKEND=qdrant`) untuk beralih ke vector database Qdrant saat siap produksi.

3. **Tool Calling ke CodeIgniter 4 (Data Live Database)**:
   - Terhubung secara otomatis ke controller internal CodeIgniter (`POST /internal/ai/tools/{toolName}`).
   - Mendukung panggilan fungsi: `get_my_submission_status`, `get_submission_detail`, dan `get_dhkt_summary_stats`.
   - Dilengkapi otentikasi timbal balik berbasis **HMAC-SHA256**.
   - Memisahkan data transaksional (via Tool Calling) dari data dokumen SOP (via RAG).

4. **Integrasi Google Gemini API**:
   - Menggunakan SDK resmi terbaru **Google GenAI (`google-genai`)**.
   - **Embedding**: `text-embedding-004` (vektor dimensi 768).
   - **LLM Synthesis**: `gemini-1.5-flash` (atau `gemini-2.0-flash`), dilengkapi prompt anti-halusinasi dan pencantuman sumber dokumen.
   - Dilengkapi *mock fallback* saat API key belum diisi, sehingga pengujian lokal tetap dapat berjalan tanpa kendala error *crash*.

5. **Role-Based Access Control (RBAC) pada RAG**:
   - Mendukung filter dokumen berdasarkan hak akses role pengguna (misal: dokumen hanya boleh diakses oleh `admin` atau `staff`).

6. **Dirancang Khusus untuk Integrasi CodeIgniter 4**:
   - Menyediakan library drop-in **`DhktAiClient.php`** dan contoh controller untuk CodeIgniter 4 di folder `ci4_integration/`.
   - Mendukung autentikasi antar-layanan berbasis **HMAC-SHA256** (`X-Timestamp` & `X-CI4-Signature`).
---

## 📁 Struktur Direktori

```text
DHKT-AI/
├── app/
│   ├── __init__.py
│   ├── main.py                     # Entrypoint FastAPI, CORS, & Lifespan
│   ├── core/
│   │   ├── config.py               # Pydantic Settings & pemuatan .env
│   │   ├── security.py             # Verifikasi tanda tangan HMAC-SHA256 CI4
│   │   └── prompts.py              # Template System Prompt RAG & Anti-Halusinasi
│   ├── schemas/
│   │   ├── chat.py                 # Skema request/response chat & sumber referensi
│   │   └── document.py             # Skema request/response ingest & manajemen dokumen
│   ├── services/
│   │   ├── pdf_service.py          # Ekstraktor teks halaman PDF & Text Splitter
│   │   ├── gemini_service.py       # Wrapper Google GenAI (Embedding & Chat Completion)
│   │   ├── vector_store.py         # Abstraksi Vector Store (Local NumPy & Qdrant)
│   │   └── rag_service.py          # Orkestrator RAG (Retrieve -> Context Injection -> LLM)
│   └── api/
│       └── v1/
│           ├── router.py            # Penggabung route v1
│           └── endpoints/
│               ├── health.py        # GET /v1/health & status layanan
│               ├── chat.py          # POST /v1/chat
│               └── documents.py     # POST /v1/documents/ingest, /upload, GET & DELETE
├── storage/
│   ├── uploads/                    # File PDF yang diunggah
│   └── index/                      # Database vektor lokal (metadata.json & vectors.npy)
├── ci4_integration/
│   ├── DhktAiClient.php            # Klien siap pakai untuk CodeIgniter 4
│   ├── ChatbotControllerExample.php# Contoh Controller di CodeIgniter 4
│   └── README.md                   # Petunjuk integrasi CI4
├── .env.example                    # Template variabel lingkungan
├── .env                            # Variabel lingkungan aktif
├── requirements.txt                # Dependensi Python
├── run.py                          # Script cepat menjalankan server
└── README.md                       # Dokumentasi utama projek
```

---

## 🚀 Panduan Instalasi & Menjalankan

### 1. Prasyarat
- Python 3.10 atau lebih baru.
- Koneksi internet (untuk mengunduh paket dan mengakses Gemini API).

### 2. Instalasi Dependensi
Buka terminal di dalam folder `DHKT-AI`:
```bash
pip install -r requirements.txt
```

### 3. Konfigurasi `.env`
Buka file `.env` dan masukkan kunci API Google Gemini:
```ini
# Dapatkan API Key gratis di https://aistudio.google.com/
GEMINI_API_KEY=AIzaSy...

# Model yang digunakan
GEMINI_MODEL=gemini-1.5-flash
GEMINI_EMBEDDING_MODEL=text-embedding-004

# Keamanan (samakan secret dengan CodeIgniter 4)
AI_INTERNAL_HMAC_SECRET=dhkt_internal_secret_key_2026
REQUIRE_HMAC=false
```

### 4. Menjalankan Server FastAPI
Jalankan perintah:
```bash
python app.py
# atau: python run.py
```
atau menggunakan uvicorn langsung:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Akses dokumentasi interaktif Swagger di browser:
👉 **`http://localhost:8000/docs`**

---

## 🔌 Dokumentasi Endpoint API

| Method | Endpoint | Deskripsi |
|---|---|---|
| `GET` | `/` | Informasi root & status layanan |
| `GET` | `/v1/health` | Health check & status vector store |
| `POST` | `/v1/chat` | Mengirim pertanyaan pengguna & menerima jawaban AI RAG |
| `POST` | `/v1/documents/upload` | Mengunggah file PDF langsung via form multipart |
| `POST` | `/v1/documents/ingest` | Mendaftarkan file PDF yang sudah ada di server lokal |
| `GET` | `/v1/documents` | Menampilkan seluruh dokumen yang telah terindeks |
| `DELETE` | `/v1/documents/{document_id}` | Menghapus dokumen dari indeks vector store |

---

## 📝 Contoh Penggunaan API

### 1. Upload & Ingest PDF Langsung (cURL)
```bash
curl -X POST "http://localhost:8000/v1/documents/upload" \
  -F "file=@/path/to/dokumen_sop.pdf" \
  -F "doc_title=SOP Peminjaman Ruangan" \
  -F "allowed_roles=admin,staff,pegawai"
```

### 2. Chat Tanya Jawab Berbasis Dokumen (cURL)
```bash
curl -X POST "http://localhost:8000/v1/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "sesi-123",
    "message": "Berapa hari batas maksimal peminjaman ruangan?",
    "user_context": {
      "role": "pegawai",
      "unit": "DHKT"
    },
    "history": []
  }'
```

**Contoh Response:**
```json
{
  "status": "success",
  "session_id": "sesi-123",
  "reply": "Berdasarkan SOP Peminjaman Ruangan (Halaman 2), batas maksimal peminjaman ruangan adalah 3 hari kerja berturut-turut...",
  "sources": [
    {
      "document_id": "sop_001",
      "doc_title": "SOP Peminjaman Ruangan",
      "page": 2,
      "chunk_index": 3,
      "snippet": "Ketentuan waktu peminjaman fasilitas ruangan paling lama adalah 3 (tiga) hari kerja berturut-turut...",
      "score": 0.8841
    }
  ]
}
```

---

## 🔗 Integrasi dengan CodeIgniter 4

Silakan buka folder `ci4_integration/` untuk melihat kode klien siap pakai:
1. Salin `ci4_integration/DhktAiClient.php` ke folder `app/Libraries/` di CodeIgniter 4.
2. Tambahkan variabel `AI_GATEWAY_URL` dan `AI_INTERNAL_HMAC_SECRET` pada `.env` CodeIgniter 4.
3. Panggil melalui Controller CI4:
   ```php
   $ai = new \App\Libraries\DhktAiClient();
   $res = $ai->sendChat(session_id(), ['role' => 'staff'], 'Pertanyaan user...');
   ```
   Detail lengkap tersedia di `ci4_integration/README.md`.
