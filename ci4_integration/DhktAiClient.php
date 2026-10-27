<?php

namespace App\Libraries;

use CodeIgniter\HTTP\CURLRequest;
use Config\Services;
use RuntimeException;

/**
 * DhktAiClient
 * 
 * Library klien CodeIgniter 4 untuk berkomunikasi dengan microservice Python FastAPI RAG.
 * Mendukung pengiriman pesan chat, ingestion dokumen PDF, penghapusan dokumen,
 * serta enkripsi HMAC-SHA256 untuk keamanan antar-layanan.
 */
class DhktAiClient
{
    private CURLRequest $http;
    private string $baseUrl;
    private string $secret;
    private int $timeout;

    public function __construct(?CURLRequest $http = null)
    {
        $this->http = $http ?? Services::curlrequest([
            'http_errors' => false,
        ]);

        $this->baseUrl = rtrim((string) env('AI_GATEWAY_URL', env('DHKT_AI_URL', 'http://127.0.0.1:8000')), '/');
        $this->secret = (string) env('AI_INTERNAL_HMAC_SECRET', env('dhkt.ai_hmac_secret', 'dhkt_internal_secret_key_2026'));
        $this->timeout = (int) env('AI_TIMEOUT', env('DHKT_AI_TIMEOUT', 30));
    }

    /**
     * Kirim pertanyaan ke AI RAG
     *
     * @param string $sessionId   ID sesi per pengguna
     * @param array  $userContext Informasi user (id, role, unit)
     * @param string $message     Pertanyaan / pesan
     * @param array  $history     Riwayat chat sebelumnya [['role' => 'user'|'assistant', 'content' => '...']]
     * @return array              Array respons ['reply' => '...', 'sources' => [...], 'status' => 'success']
     */
    public function sendChat(
        string $sessionId,
        array $userContext,
        string $message,
        array $history = []
    ): array {
        return $this->request('POST', '/v1/chat', [
            'session_id'   => $sessionId,
            'user_context' => [
                'id'   => $userContext['id'] ?? $userContext['user_id'] ?? null,
                'role' => $userContext['role'] ?? 'staff',
                'unit' => $userContext['unit'] ?? null,
            ],
            'message'      => $message,
            'history'      => $history,
        ]);
    }

    /**
     * Ingest / daftarkan file PDF lokal server ke Vector Store AI
     *
     * @param int|string $documentId   ID unik dokumen di database CI4
     * @param string     $title        Judul dokumen SOP / berkas
     * @param string     $filePath     Path absolut file PDF di server
     * @param array      $allowedRoles Role yang berhak mengakses dokumen ini (misal ['admin', 'staff'] atau ['*'])
     * @return array
     */
    public function ingestDocument(
        $documentId,
        string $title,
        string $filePath,
        array $allowedRoles = ['*']
    ): array {
        return $this->request('POST', '/v1/documents/ingest', [
            'document_id'   => (string) $documentId,
            'doc_title'     => $title,
            'file_path'     => $filePath,
            'allowed_roles' => array_values($allowedRoles),
        ]);
    }

    /**
     * Hapus dokumen dari Vector Store AI
     *
     * @param int|string $documentId
     * @return array
     */
    public function deleteDocument($documentId): array
    {
        return $this->request('DELETE', '/v1/documents/' . $documentId);
    }

    /**
     * Dapatkan daftar seluruh dokumen yang telah diindeks
     *
     * @return array
     */
    public function listDocuments(): array
    {
        return $this->request('GET', '/v1/documents');
    }

    /**
     * Cek status koneksi ke AI service
     *
     * @return array
     */
    public function checkHealth(): array
    {
        return $this->request('GET', '/v1/health');
    }

    /**
     * Helper eksekusi HTTP request dengan header HMAC
     */
    private function request(string $method, string $path, ?array $payload = null): array
    {
        $body = $payload === null
            ? ''
            : json_encode($payload, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);

        if ($body === false) {
            throw new RuntimeException('Gagal mengenkripsi payload AI request ke JSON.');
        }

        $timestamp = (string) time();
        $signature = hash_hmac('sha256', $timestamp . '.' . $body, $this->secret);

        $options = [
            'headers' => [
                'Accept'          => 'application/json',
                'Content-Type'    => 'application/json',
                'X-Timestamp'     => $timestamp,
                'X-CI4-Signature' => $signature,
            ],
            'timeout' => $this->timeout,
        ];

        if ($body !== '' && in_array(strtoupper($method), ['POST', 'PUT', 'PATCH'])) {
            $options['body'] = $body;
        }

        $response = $this->http->request($method, $this->baseUrl . $path, $options);
        $status = $response->getStatusCode();
        $rawBody = (string) $response->getBody();
        $decoded = json_decode($rawBody, true);

        if ($status < 200 || $status >= 300) {
            $detail = is_array($decoded) ? ($decoded['detail'] ?? 'Permintaan ke AI service gagal') : $rawBody;
            throw new RuntimeException(sprintf('AI Service HTTP %d: %s', $status, $detail));
        }

        if (!is_array($decoded)) {
            throw new RuntimeException('AI Service mengembalikan format yang tidak valid (bukan JSON).');
        }

        return $decoded;
    }
}
