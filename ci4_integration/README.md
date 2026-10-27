# Panduan Integrasi CodeIgniter 4 dengan DHKT AI RAG

Folder ini berisi file siap pakai untuk menghubungkan aplikasi web berbasis **CodeIgniter 4** dengan microservice **DHKT AI RAG (FastAPI)**.

---

## 1. Konfigurasi Environment di CodeIgniter 4

Tambahkan konfigurasi berikut ke file `.env` di root project CodeIgniter 4 Anda:

```ini
# URL AI Service FastAPI
AI_GATEWAY_URL = http://127.0.0.1:8000

# Secret Key HMAC (Harus SAMA dengan AI_INTERNAL_HMAC_SECRET di DHKT-AI/.env)
AI_INTERNAL_HMAC_SECRET = dhkt_internal_secret_key_2026

# Timeout HTTP Request (dalam detik)
AI_TIMEOUT = 30
```

---

## 2. Pemasangan Client Library

1. Salin file `DhktAiClient.php` ke folder project CodeIgniter 4 Anda:
   ```text
   app/Libraries/DhktAiClient.php
   ```

2. Pastikan namespace sesuai: `App\Libraries\DhktAiClient`.

---

## 3. Contoh Penggunaan di Controller CodeIgniter 4

### A. Mengirim Pesan Chat & Menerima Jawaban RAG

```php
use App\Libraries\DhktAiClient;

$aiClient = new DhktAiClient();

$response = $aiClient->sendChat(
    sessionId: session_id(),
    userContext: [
        'id'   => session('user_id'),
        'role' => session('role'), // misal 'admin', 'staff', 'pegawai'
        'unit' => session('unit'),
    ],
    message: 'Bagaimana prosedur peminjaman ruangan seminar?',
    history: [
        ['role' => 'user', 'content' => 'Halo'],
        ['role' => 'assistant', 'content' => 'Halo! Ada yang bisa saya bantu terkait SOP?'],
    ]
);

// $response berisi:
// [
//   'status'  => 'success',
//   'reply'   => 'Prosedur peminjaman ruangan...',
//   'sources' => [
//       ['doc_title' => 'SOP Ruangan 2026.pdf', 'page' => 3, 'score' => 0.89, ...]
//   ]
// ]
echo $response['reply'];
```

### B. Ingest / Index Dokumen PDF ke AI

Ketika admin mengunggah dokumen SOP baru di web CodeIgniter:

```php
$aiClient = new DhktAiClient();

$result = $aiClient->ingestDocument(
    documentId: 101,
    title: 'SOP Fasilitas dan Sarana Prasarana 2026',
    filePath: WRITEPATH . 'uploads/sop_fasilitas_2026.pdf',
    allowedRoles: ['admin', 'staff', 'pegawai']
);

log_message('info', 'Dokumen berhasil diindeks: ' . $result['chunks_count'] . ' chunks.');
```

### C. Menghapus Dokumen dari AI

Ketika dokumen dihapus dari database CodeIgniter:

```php
$aiClient = new DhktAiClient();
$aiClient->deleteDocument(101);
```

---

## 4. Keamanan Antar-Layanan (HMAC-SHA256)

Setiap request dari `DhktAiClient.php` ke FastAPI secara otomatis menyertakan:
- Header `X-Timestamp`: waktu saat request dikirim (mencegah *replay attacks*).
- Header `X-CI4-Signature`: tanda tangan digital `hash_hmac('sha256', timestamp . '.' . body, secret)`.

Pada fase pengembangan, verifikasi HMAC dapat dinonaktifkan di `DHKT-AI/.env` dengan `REQUIRE_HMAC=false` agar pengujian lewat Swagger UI (`/docs`) atau curl berjalan mudah.
