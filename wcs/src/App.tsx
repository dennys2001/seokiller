import { useState } from 'react';
import { Button } from './components/ui/button';
import { Input } from './components/ui/input';
import { Card } from './components/ui/card';
import { Loader2, Copy, Check } from 'lucide-react';

export default function App() {
  const [url, setUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState('');
  const [error, setError] = useState('');
  const [copied, setCopied] = useState(false);

  // CONFIGURE AQUI A URL DO SEU ENGINE
  const ENGINE_URL = 'http://localhost:3001/avalie'; // Altere para a URL do seu engine

  const handleSubmit = async () => {
    if (!url.trim()) {
      setError('Por favor, insira uma URL válida');
      return;
    }

    setLoading(true);
    setError('');
    setResult('');

    try {
      const response = await fetch(ENGINE_URL, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ url }),
      });

      if (!response.ok) {
        throw new Error(`Erro: ${response.status} ${response.statusText}`);
      }

      const data = await response.json();
      
      // Ajuste este campo conforme a resposta do seu engine
      // Ex: data.content, data.optimizedText, data.result, etc.
      setResult(data.optimizedContent || data.content || data.result || JSON.stringify(data, null, 2));
      
    } catch (err) {
      console.error('Error calling engine:', err);
      setError(err instanceof Error ? err.message : 'Erro ao conectar com o engine');
    } finally {
      setLoading(false);
    }
  };

  const handleCopy = async () => {
    await navigator.clipboard.writeText(result);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
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
          <h1 className="text-4xl">SEO AI Optimizer</h1>
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
            disabled={loading}
            className="flex-1"
          />
          <Button onClick={handleSubmit} disabled={loading}>
            {loading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Processando
              </>
            ) : (
              'Enviar'
            )}
          </Button>
        </div>

        {/* Error Message */}
        {error && (
          <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
            {error}
          </div>
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
        {loading && (
          <div className="text-center text-gray-600">
            <p>Analisando o conteúdo do site...</p>
          </div>
        )}
      </div>
    </div>
  );
}
