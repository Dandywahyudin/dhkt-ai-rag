<?php

namespace App\Controllers;

use App\Controllers\BaseController;
use App\Libraries\DhktAiClient;
use CodeIgniter\HTTP\ResponseInterface;
use Throwable;

class ChatbotControllerExample extends BaseController
{
    /**
     * Endpoint chat yang diakses dari antarmuka Web CodeIgniter 4
     * Route: POST /api/chat
     */
    public function chat(): ResponseInterface
    {
        $payload = $this->request->getJSON(true);
        if (!is_array($payload)) {
            return $this->response->setStatusCode(400)->setJSON([
                'status'   => 'error',
                'message'  => 'Payload harus berupa JSON object.',
                'csrfHash' => csrf_hash(),
            ]);
        }

        $message = trim((string) ($payload['message'] ?? ''));
        if ($message === '') {
            return $this->response->setStatusCode(400)->setJSON([
                'status'   => 'error',
                'message'  => 'Parameter message tidak boleh kosong.',
                'csrfHash' => csrf_hash(),
            ]);
        }

        // Ambil data user dari sesi login CodeIgniter 4
        $session = session();
        $userContext = [
            'id'   => $session->get('user_id') ?? 1,
            'role' => $session->get('role') ?? 'pegawai',
            'unit' => $session->get('unit') ?? 'DHKT',
        ];

        $sessionId = (string) ($payload['session_id'] ?? session_id());
        $history = is_array($payload['history'] ?? null) ? $payload['history'] : [];

        try {
            $client = new DhktAiClient();
            $aiResponse = $client->sendChat($sessionId, $userContext, $message, $history);

            return $this->response->setJSON([
                'status'   => 'success',
                'reply'    => $aiResponse['reply'],
                'sources'  => $aiResponse['sources'] ?? [],
                'csrfHash' => csrf_hash(),
            ]);
        } catch (Throwable $e) {
            log_message('error', 'Gagal memanggil DHKT AI: ' . $e->getMessage());

            return $this->response->setStatusCode(502)->setJSON([
                'status'   => 'error',
                'message'  => 'Layanan AI sedang tidak dapat dihubungi: ' . $e->getMessage(),
                'csrfHash' => csrf_hash(),
            ]);
        }
    }

    /**
     * Contoh mendaftarkan dokumen PDF yang baru diunggah di CI4 ke AI RAG
     * Route: POST /admin/documents/sync-ai/(:num)
     */
    public function syncPdfToAi(int $documentId): ResponseInterface
    {
        // Contoh: ambil data dokumen dari Model
        // $document = (new DocumentModel())->find($documentId);
        $title = "SOP Peminjaman Ruangan 2026";
        $pdfPath = WRITEPATH . 'uploads/sop_peminjaman.pdf';
        $allowedRoles = ['admin', 'staff', 'pegawai'];

        try {
            $client = new DhktAiClient();
            $result = $client->ingestDocument($documentId, $title, $pdfPath, $allowedRoles);

            return $this->response->setJSON([
                'status'  => 'success',
                'message' => 'Dokumen berhasil diindeks ke AI RAG.',
                'detail'  => $result,
            ]);
        } catch (Throwable $e) {
            return $this->response->setStatusCode(500)->setJSON([
                'status'  => 'error',
                'message' => 'Gagal mengindeks dokumen ke AI: ' . $e->getMessage(),
            ]);
        }
    }
}
