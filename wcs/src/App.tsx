import { useState } from 'react';
import { Button } from './components/ui/button';
import { Input } from './components/ui/input';
import { Card } from './components/ui/card';
import { Loader2, Copy, Check, Download } from 'lucide-react';

export default function App() {
  const [url, setUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [loadingSummary, setLoadingSummary] = useState(false);
  const [result, setResult] = useState('');
  const [error, setError] = useState('');
  const [copied, setCopied] = useState(false);
  const [files, setFiles] = useState<Array<{ filename: string; mimeType?: string; data: any }>>([]);
  const [downloadingAll, setDownloadingAll] = useState(false);
  const [summaryOnlyMode, setSummaryOnlyMode] = useState(false);

  // API URL via Vite env (middleware). Default to same-origin path using Vite proxy in dev
  const API_URL = import.meta.env.VITE_API_URL || '/avalie';
  const WCE_KEY = import.meta.env.VITE_WCE_KEY || '';

  const buildHeaders = () => {
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (WCE_KEY) {
      headers['x-wce-key'] = WCE_KEY;
    }
    return headers;
  };

  // Warn if pointing directly to engine (likely missing CORS on engine)
  if (API_URL.includes('/analyze')) {
    console.warn(
      `VITE_API_URL appears to point to the engine ("${API_URL}"). ` +
        'Point it to the middleware endpoint, e.g., http://localhost:3001/avalie.'
    );
  }

  const handleSubmit = async () => {
    if (!url.trim()) {
      setError('Por favor, insira uma URL válida');
      return;
    }

    setLoading(true);
    setLoadingSummary(false);
    setSummaryOnlyMode(false);
    setError('');
    setResult('');
    setFiles([]);

    try {
      const response = await fetch(API_URL, {
        method: 'POST',
        headers: buildHeaders(),
        body: JSON.stringify({ url }),
      });

      if (!response.ok) {
        throw new Error(`Erro: ${response.status} ${response.statusText}`);
      }

      const data = await response.json();
      
      // Ajuste este campo conforme a resposta do seu engine
      // Ex: data.content, data.optimizedText, data.result, etc.
      setResult(data.optimizedContent || data.content || data.result || JSON.stringify(data, null, 2));

      // Recebe arquivos retornados pela API (top-level) ou vindos dentro de engineResponse
      const incomingFiles =
        (Array.isArray(data?.files) && data.files) ||
        (Array.isArray(data?.engineResponse?.files) && data.engineResponse.files) ||
        [];
      setFiles(incomingFiles);
      
    } catch (err) {
      console.error('Error calling engine:', err);
      setError(err instanceof Error ? err.message : 'Erro ao conectar com o engine');
    } finally {
      setLoading(false);
    }
  };

  const handleSummaryOnly = async () => {
    if (!url.trim()) {
      setError('Por favor, insira uma URL valida');
      return;
    }

    setLoadingSummary(true);
    setLoading(false);
    setSummaryOnlyMode(true);
    setError('');
    setResult('');
    setFiles([]);

    try {
      const response = await fetch(API_URL, {
        method: 'POST',
        headers: buildHeaders(),
        body: JSON.stringify({ url }),
      });
      if (!response.ok) {
        throw new Error(`Erro: ${response.status} ${response.statusText}`);
      }
      const data = await response.json();
      const incomingFiles =
        (Array.isArray(data?.files) && data.files) ||
        (Array.isArray(data?.engineResponse?.files) && data.engineResponse.files) ||
        [];
      setFiles(incomingFiles);
    } catch (err) {
      console.error('Error calling engine (summary-only):', err);
      setError(err instanceof Error ? err.message : 'Erro ao conectar com o engine');
    } finally {
      setLoadingSummary(false);
    }
  };

  const handleCopy = async () => {
    await navigator.clipboard.writeText(result);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownload = (file: { filename: string; mimeType?: string; data: any }) => {
    const jsonString = JSON.stringify(file.data, null, 2);
    const blob = new Blob([jsonString], { type: file.mimeType || 'application/json' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = file.filename || 'arquivo.json';
    document.body.appendChild(link);
    link.click();
    URL.revokeObjectURL(link.href);
    document.body.removeChild(link);
  };

  const handleDownloadAll = async () => {
    try {
      setDownloadingAll(true);
      const response = await fetch(`${API_URL}?zip=1`, {
        method: 'POST',
        headers: buildHeaders(),
        body: JSON.stringify({ url }),
      });
      if (!response.ok) throw new Error(`Erro: ${response.status} ${response.statusText}`);
      const blob = await response.blob();
      const link = document.createElement('a');
      link.href = URL.createObjectURL(blob);
      let base = 'analysis';
      try { base = new URL(url).hostname || base; } catch {}
      link.download = `${base}-analysis.zip`;
      document.body.appendChild(link);
      link.click();
      URL.revokeObjectURL(link.href);
      document.body.removeChild(link);
    } catch (e) {
      console.error('Erro ao baixar zip:', e);
      setError(e instanceof Error ? e.message : 'Falha ao baixar os arquivos');
    } finally {
      setDownloadingAll(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSubmit();
    }
  };

  return (
    <div className="min-h-screen bg-white flex flex-col items-center justify-center p-4">
      <div className="w-full max-w-2xl space-y-8">
        {/* Logo/Title */}
        <div className="text-center space-y-2">
          <h1 className="text-4xl">GEO AEO Optimizer</h1>
          <p className="text-gray-600">
            Otimize o conteúdo do seu site para SEO
          </p>
        </div>

        {/* Search Box */}
        <div className="flex gap-2">
          <Input
            type="url"
            placeholder="Digite a URL do site (ex: https://exemplo.com)"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            onKeyPress={handleKeyPress}
            disabled={loading || loadingSummary}
            className="flex-1"
          />
          <Button onClick={handleSubmit} disabled={loading || loadingSummary}>
            {loading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Processando
              </>
            ) : (
              'Enviar'
            )}
          </Button>
          <Button onClick={handleSummaryOnly} disabled={loading || loadingSummary}>
            {loadingSummary ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Analisando
              </>
            ) : (
              'Somente Resumo'
            )}
          </Button>
        </div>

        {/* Error Message */}
        {error && (
          <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
            {error}
          </div>
        )}

        {/* Files List */}
        {files.length > 0 && !summaryOnlyMode && (
          <Card className="p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h2>Arquivos gerados</h2>
              <Button
                variant="default"
                size="sm"
                onClick={handleDownloadAll}
                disabled={downloadingAll || !url}
                className="flex items-center gap-2"
              >
                {downloadingAll ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" /> Baixando...
                  </>
                ) : (
                  <>
                    <Download className="h-4 w-4" /> Download tudo (.zip)
                  </>
                )}
              </Button>
            </div>
            <div className="space-y-2">
              {files.map((file, idx) => (
                <div key={`${file.filename}-${idx}`} className="flex items-center justify-between border rounded-md p-3">
                  <div>
                    <p className="font-medium">{file.filename || `arquivo-${idx + 1}.json`}</p>
                    <p className="text-xs text-gray-500">{file.mimeType || 'application/json'}</p>
                  </div>
                  <Button variant="outline" size="sm" onClick={() => handleDownload(file)}>
                    Baixar
                  </Button>
                </div>
              ))}
            </div>
          </Card>
        )}

        {/* Structured Results */}
        {files.length > 0 && (
          <Card className="p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h2>Resumo Estruturado</h2>
            </div>
            {(() => {
              const get = (name: string) => files.find((f) => f.filename === name)?.data || {};
              const summary: any = get('summary.json');
              const headings: any = get('headings.json');
              const meta: any = get('meta.json');
              const issues: Array<any> = Array.isArray(summary?.issues) ? summary.issues : [];
              return (
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div className="p-3 border rounded-md">
                      <p className="text-xs text-gray-500">Score</p>
                      <p className="text-lg font-semibold">{summary?.score ?? '-'}</p>
                    </div>
                    <div className="p-3 border rounded-md">
                      <p className="text-xs text-gray-500">Meta Description</p>
                      <p className="text-sm break-words">{meta?.description ?? '—'}</p>
                      <p className="text-xs text-gray-500">Tamanho: {meta?.descriptionLength ?? 0}</p>
                    </div>
                    <div className="p-3 border rounded-md col-span-2">
                      <p className="text-xs text-gray-500">Título</p>
                      <p className="text-sm break-words">{headings?.title ?? '—'}</p>
                    </div>
                    <div className="p-3 border rounded-md">
                      <p className="text-xs text-gray-500">H1</p>
                      <p className="text-sm">{Array.isArray(headings?.h1) ? headings.h1.join(', ') : '—'}</p>
                    </div>
                    <div className="p-3 border rounded-md">
                      <p className="text-xs text-gray-500">H2</p>
                      <p className="text-sm">{Array.isArray(headings?.h2) ? headings.h2.join(', ') : '—'}</p>
                    </div>
                  </div>
                  <div>
                    <p className="text-sm font-medium mb-2">Issues</p>
                    {issues.length === 0 ? (
                      <p className="text-sm text-gray-500">Nenhuma issue encontrada</p>
                    ) : (
                      <ul className="list-disc pl-5 space-y-1 text-sm">
                        {issues.map((it, i) => (
                          <li key={i}>{it?.message ?? JSON.stringify(it)}</li>
                        ))}
                      </ul>
                    )}
                  </div>
                </div>
              );
            })()}
          </Card>
        )}

        {/* Result Box */}
        {result && (
          <Card className="p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h2>Conteúdo Otimizado para SEO</h2>
              <Button
                variant="outline"
                size="sm"
                onClick={handleCopy}
                className="flex items-center gap-2"
              >
                {copied ? (
                  <>
                    <Check className="h-4 w-4" />
                    Copiado!
                  </>
                ) : (
                  <>
                    <Copy className="h-4 w-4" />
                    Copiar
                  </>
                )}
              </Button>
            </div>
            <div className="bg-gray-50 p-4 rounded-lg max-h-96 overflow-y-auto">
              <pre className="whitespace-pre-wrap text-sm">{result}</pre>
            </div>
          </Card>
        )}

        {/* Loading State */}
        {(loading || loadingSummary) && (
          <div className="text-center text-gray-600">
            <p>Analisando o conteúdo do site...</p>
          </div>
        )}
      </div>
    </div>
  );
}
