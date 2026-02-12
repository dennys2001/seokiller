import { useState } from 'react';
import { Button } from './components/ui/button';
import { Input } from './components/ui/input';
import { Card } from './components/ui/card';
import { Checkbox } from './components/ui/checkbox';
import { Loader2, Copy, Check, Download } from 'lucide-react';

type DownloadFile = { filename: string; mimeType?: string; data: any };

export default function App() {
  const [url, setUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [loadingSummary, setLoadingSummary] = useState(false);
  const [result, setResult] = useState('');
  const [error, setError] = useState('');
  const [warning, setWarning] = useState('');
  const [copied, setCopied] = useState(false);
  const [files, setFiles] = useState<DownloadFile[]>([]);
  const [downloadingAll, setDownloadingAll] = useState(false);
  const [summaryOnlyMode, setSummaryOnlyMode] = useState(false);
  const [useCrawler, setUseCrawler] = useState(false);
  const [analysisDetails, setAnalysisDetails] = useState<any>(null);

  const REQUEST_TIMEOUT_MS = 180_000;
  const API_URL = import.meta.env.VITE_API_URL || '/avalie';

  const fetchWithTimeout = async (input: RequestInfo, init?: RequestInit) => {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
    try {
      return await fetch(input, { ...init, signal: controller.signal });
    } finally {
      clearTimeout(timeoutId);
    }
  };

  const resetOutputs = () => {
    setError('');
    setWarning('');
    setResult('');
    setFiles([]);
    setAnalysisDetails(null);
  };

  const applyResponse = (data: any) => {
    if (!data) {
      setError('Resposta invalida do servidor');
      return;
    }
    setResult(data.optimizedContent || data.content || data.result || JSON.stringify(data, null, 2));
    const incomingFiles =
      (Array.isArray(data?.files) && data.files) ||
      (Array.isArray(data?.engineResponse?.files) && data.engineResponse.files) ||
      [];
    setFiles(incomingFiles);
    setWarning(data?.warning || data?.engineResponse?.warning || '');
    setAnalysisDetails(data?.analysisDetails || data?.engineResponse?.analysisDetails || null);
  };

  const postAnalyze = async (opts?: { useCrawlerOverride?: boolean }) => {
    const useCrawlerFinal = typeof opts?.useCrawlerOverride === 'boolean' ? opts.useCrawlerOverride : useCrawler;
    return fetchWithTimeout(API_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, useCrawler: useCrawlerFinal }),
    });
  };

  const readJsonSafely = async (response: Response) => {
    try {
      return await response.json();
    } catch {
      return null;
    }
  };

  const handleSubmit = async () => {
    if (!url.trim()) {
      setError('Por favor, insira uma URL valida');
      return;
    }

    setLoading(true);
    setLoadingSummary(false);
    setSummaryOnlyMode(false);
    resetOutputs();

    try {
      const response = await postAnalyze();
      const data = await readJsonSafely(response);

      if (!response.ok) {
        // Extra safety: if crawler fails upstream, retry as "Somente Resumo" instead of breaking the UI.
        if (useCrawler && [403, 429, 502, 503, 504].includes(response.status)) {
          const fallbackResponse = await postAnalyze({ useCrawlerOverride: false });
          const fallbackData = await readJsonSafely(fallbackResponse);
          if (fallbackResponse.ok && fallbackData) {
            applyResponse(fallbackData);
            setWarning(
              fallbackData?.warning ||
                'Site possivelmente protegido por anti-bot ou em manutencao. Nao foi possivel realizar analise completa com crawler; exibindo somente resumo.'
            );
            return;
          }
        }

        throw new Error(data?.message || `Erro: ${response.status} ${response.statusText}`);
      }

      applyResponse(data);
    } catch (err) {
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
    resetOutputs();

    try {
      const response = await postAnalyze({ useCrawlerOverride: false });
      const data = await readJsonSafely(response);
      if (!response.ok) throw new Error(data?.message || `Erro: ${response.status} ${response.statusText}`);
      applyResponse(data);
    } catch (err) {
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

  const handleDownload = (file: DownloadFile) => {
    const payload = typeof file.data === 'string' ? file.data : JSON.stringify(file.data, null, 2);
    const blob = new Blob([payload], { type: file.mimeType || 'application/json' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = file.filename || 'arquivo.json';
    document.body.appendChild(link);
    link.click();
    URL.revokeObjectURL(link.href);
    document.body.removeChild(link);
  };

  const findFile = (matcher: (file: DownloadFile) => boolean) => files.find(matcher);

  const handleDownloadAll = async () => {
    try {
      setDownloadingAll(true);
      const response = await fetchWithTimeout(`${API_URL}?zip=1`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url, useCrawler }),
      });
      if (!response.ok) throw new Error(`Erro: ${response.status} ${response.statusText}`);
      const blob = await response.blob();
      const link = document.createElement('a');
      link.href = URL.createObjectURL(blob);
      let base = 'analysis';
      try {
        base = new URL(url).hostname || base;
      } catch {
        // ignore
      }
      link.download = `${base}-analysis.zip`;
      document.body.appendChild(link);
      link.click();
      URL.revokeObjectURL(link.href);
      document.body.removeChild(link);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Falha ao baixar arquivos');
    } finally {
      setDownloadingAll(false);
    }
  };

  const handleClearAll = () => {
    setUrl('');
    setCopied(false);
    setSummaryOnlyMode(false);
    setUseCrawler(false);
    setDownloadingAll(false);
    resetOutputs();
  };

  const handleKeyPress = (event: React.KeyboardEvent) => {
    if (event.key === 'Enter') handleSubmit();
  };

  const scoreFile = findFile((file) => file.filename.endsWith('_score.json') || file.filename === 'score.json')?.data || {};
  const meta = findFile((file) => file.filename === 'meta.json')?.data || {};
  const headings = findFile((file) => file.filename === 'headings.json')?.data || {};
  const scoreBreakdown = analysisDetails?.scoreBreakdown || scoreFile?.breakdown || {};
  const entities = analysisDetails?.topEntities || [];
  const issuesByCategory = analysisDetails?.issuesByCategory || {};
  const testReport = analysisDetails?.testReport || null;

  const directAnswerTag = (() => {
    const marker = '**Resposta direta:**';
    const index = result.indexOf(marker);
    if (index === -1) return '';
    const tail = result.slice(index + marker.length).trimStart();
    return (tail.split('\n')[0] || '').trim();
  })();

  const hasAnyOutput =
    !!result || files.length > 0 || !!error || !!warning || loading || loadingSummary;

  return (
    <div className={`page ${hasAnyOutput ? 'page--results' : 'page--home'}`}>
      <div className="container">
        <div className="space-y-8">
          <div className="text-center space-y-2">
            <h1 className="text-4xl">GEO AEO Optimizer</h1>
            <p className="text-gray-600">Otimize o conteudo do seu site para SEO</p>
          </div>

          <div className="flex flex-wrap items-center justify-center gap-2">
            <Input
              type="url"
              placeholder="Digite a URL do site (ex: https://exemplo.com)"
              value={url}
              onChange={(event) => setUrl(event.target.value)}
              onKeyPress={handleKeyPress}
              disabled={loading || loadingSummary}
              className="w-full max-w-lg"
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
            <Button variant="outline" onClick={handleClearAll} disabled={loading || loadingSummary}>
              Limpar Tudo
            </Button>
          </div>

          <div className="flex items-center justify-center gap-2 text-sm text-gray-700">
            <Checkbox
              id="use-crawler"
              checked={useCrawler}
              onCheckedChange={(value) => setUseCrawler(!!value)}
              disabled={loading || loadingSummary}
            />
            <label htmlFor="use-crawler" className="select-none cursor-pointer">
              Usar crawler para varrer o dominio inteiro antes de otimizar
            </label>
          </div>

          {error && (
            <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">{error}</div>
          )}
          {warning && (
            <div className="p-4 bg-amber-50 border border-amber-200 rounded-lg text-amber-800">
              {warning}
            </div>
          )}

          {files.length > 0 && !summaryOnlyMode && (
            <Card className="p-6 space-y-4">
              <div className="flex items-center justify-between">
                <h2>Arquivos gerados</h2>
                <div className="flex gap-2">
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
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      const file = findFile(
                        (item) => item.filename.endsWith('_schema.json') || item.filename === 'schema.json'
                      );
                      if (file) handleDownload(file);
                    }}
                  >
                    schema.json
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      const file = findFile(
                        (item) => item.filename.endsWith('_entities.json') || item.filename === 'entities.json'
                      );
                      if (file) handleDownload(file);
                    }}
                  >
                    entities.json
                  </Button>
                </div>
              </div>

              <div className="space-y-2">
                {files.map((file, index) => (
                  <div
                    key={`${file.filename}-${index}`}
                    className="flex items-center justify-between border rounded-md p-3"
                  >
                    <div>
                      <p className="font-medium">{file.filename || `arquivo-${index + 1}.json`}</p>
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

          {files.length > 0 && (
            <Card className="p-6 space-y-4">
              <h2>Resumo Estruturado</h2>

              <div className="grid grid-cols-2 gap-4">
                <div className="p-3 border rounded-md">
                  <p className="text-xs text-gray-500">Intencao detectada</p>
                  <p className="text-sm font-medium">{analysisDetails?.intent || '-'}</p>
                </div>
                <div className="p-3 border rounded-md">
                  <p className="text-xs text-gray-500">Pergunta principal</p>
                  <p className="text-sm">{analysisDetails?.primaryQuestion || '-'}</p>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="p-3 border rounded-md">
                  <p className="text-xs text-gray-500">Score</p>
                  <p className="text-lg font-semibold">{scoreFile?.total ?? '-'}</p>
                </div>
                <div className="p-3 border rounded-md">
                  <p className="text-xs text-gray-500">Meta Description</p>
                  <p className="text-sm break-words">{meta?.description ?? '-'}</p>
                  <p className="text-xs text-gray-500">Tamanho: {meta?.descriptionLength ?? 0}</p>
                </div>
                <div className="p-3 border rounded-md col-span-2">
                  <p className="text-xs text-gray-500">Titulo</p>
                  <p className="text-sm break-words">{headings?.title ?? '-'}</p>
                </div>
              </div>

              <div className="p-3 border rounded-md">
                <p className="text-sm font-medium mb-2">Top 10 entidades</p>
                {entities.length === 0 ? (
                  <p className="text-sm text-gray-500">Sem entidades mapeadas</p>
                ) : (
                  <div className="flex flex-wrap gap-2">
                    {entities.slice(0, 10).map((entity: any, index: number) => (
                      <span key={`${entity.entity_name}-${index}`} className="text-xs border rounded px-2 py-1">
                        {entity.entity_name} ({entity.entity_type})
                      </span>
                    ))}
                  </div>
                )}
              </div>

              <div className="p-3 border rounded-md">
                <p className="text-sm font-medium mb-2">Score breakdown</p>
                {Object.keys(scoreBreakdown).length === 0 ? (
                  <p className="text-sm text-gray-500">Sem breakdown disponivel</p>
                ) : (
                  <ul className="list-disc pl-5 space-y-1 text-sm">
                    {Object.entries(scoreBreakdown).map(([key, value]: any) => (
                      <li key={key}>
                        {key}: {value?.score ?? 0}/{value?.max ?? 20}
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              <div className="p-3 border rounded-md">
                <p className="text-sm font-medium mb-2">Issues por categoria</p>
                {Object.keys(issuesByCategory).length === 0 ? (
                  <p className="text-sm text-gray-500">Sem issues mapeadas</p>
                ) : (
                  <div className="space-y-2">
                    {Object.entries(issuesByCategory).map(([category, items]: any) => (
                      <div key={category}>
                        <p className="text-sm font-medium">{category}</p>
                        {Array.isArray(items) && items.length > 0 ? (
                          <ul className="list-disc pl-5 text-sm">
                            {items.map((item: string, index: number) => (
                              <li key={`${category}-${index}`}>{item}</li>
                            ))}
                          </ul>
                        ) : (
                          <p className="text-xs text-gray-500">Sem apontamentos</p>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="p-3 border rounded-md">
                <p className="text-sm font-medium mb-2">Test harness</p>
                {!testReport ? (
                  <p className="text-sm text-gray-500">Sem relatorio</p>
                ) : (
                  <>
                    <p className="text-sm mb-2">
                      Checks: {testReport.passed_checks}/{testReport.total_checks}
                    </p>
                    <ul className="list-disc pl-5 text-sm">
                      {Array.isArray(testReport.checks) &&
                        testReport.checks.map((check: any, index: number) => (
                          <li key={`check-${index}`}>
                            {check.name}: {check.passed ? 'ok' : 'falhou'} ({check.details})
                          </li>
                        ))}
                    </ul>
                  </>
                )}
              </div>
            </Card>
          )}

          {result && (
            <Card className="p-6 space-y-4">
              <div className="flex items-center justify-between">
                <h2>Conteudo Otimizado para SEO</h2>
                <Button variant="outline" size="sm" onClick={handleCopy} className="flex items-center gap-2">
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

              {directAnswerTag && (
                <div className="inline-flex items-center gap-2 rounded border border-emerald-300 bg-emerald-50 px-3 py-2 text-sm text-emerald-900">
                  <span className="font-medium">Resposta direta</span>
                  <span>{directAnswerTag}</span>
                </div>
              )}

              <div className="bg-gray-50 p-4 rounded-lg max-h-96 overflow-y-auto">
                <pre className="whitespace-pre-wrap text-sm">{result}</pre>
              </div>
            </Card>
          )}

          {(loading || loadingSummary) && (
            <div className="text-center text-gray-600">
              <p>Analisando o conteudo do site...</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
