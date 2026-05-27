import { Download, FileText, Image, File, CheckCircle } from 'lucide-react';
import { useState } from 'react';

interface ExportarRelatorioProps {
  onConcluir: () => void;
}

export function ExportarRelatorio({ onConcluir }: ExportarRelatorioProps) {
  const [formato, setFormato] = useState<'pdf' | 'excel' | 'csv'>('pdf');
  const [incluirGraficos, setIncluirGraficos] = useState(true);
  const [incluirVideo, setIncluirVideo] = useState(false);
  const [incluirDadosBrutos, setIncluirDadosBrutos] = useState(false);
  const [exportado, setExportado] = useState(false);

  const handleExportar = () => {
    setTimeout(() => {
      setExportado(true);
      setTimeout(() => {
        onConcluir();
      }, 2000);
    }, 1000);
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-2xl shadow-2xl p-8 max-w-2xl w-full">
        {!exportado ? (
          <>
            <div className="text-center mb-6">
              <div className="inline-flex items-center justify-center w-16 h-16 bg-indigo-100 rounded-full mb-4">
                <Download className="text-indigo-600" size={32} />
              </div>
              <h2 className="text-2xl font-bold text-gray-800 mb-2">Exportar Relatório</h2>
              <p className="text-gray-600">Tela 4 - Configurar exportação de dados</p>
            </div>

            <div className="space-y-6 mb-8">
              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-3">
                  Formato do Relatório
                </label>
                <div className="grid grid-cols-3 gap-3">
                  <button
                    onClick={() => setFormato('pdf')}
                    className={`p-4 rounded-xl border-2 transition-all ${
                      formato === 'pdf'
                        ? 'border-indigo-600 bg-indigo-50'
                        : 'border-gray-200 hover:border-gray-300'
                    }`}
                  >
                    <FileText className={`mx-auto mb-2 ${formato === 'pdf' ? 'text-indigo-600' : 'text-gray-400'}`} size={32} />
                    <p className="text-sm font-medium">PDF</p>
                  </button>

                  <button
                    onClick={() => setFormato('excel')}
                    className={`p-4 rounded-xl border-2 transition-all ${
                      formato === 'excel'
                        ? 'border-indigo-600 bg-indigo-50'
                        : 'border-gray-200 hover:border-gray-300'
                    }`}
                  >
                    <File className={`mx-auto mb-2 ${formato === 'excel' ? 'text-indigo-600' : 'text-gray-400'}`} size={32} />
                    <p className="text-sm font-medium">Excel</p>
                  </button>

                  <button
                    onClick={() => setFormato('csv')}
                    className={`p-4 rounded-xl border-2 transition-all ${
                      formato === 'csv'
                        ? 'border-indigo-600 bg-indigo-50'
                        : 'border-gray-200 hover:border-gray-300'
                    }`}
                  >
                    <FileText className={`mx-auto mb-2 ${formato === 'csv' ? 'text-indigo-600' : 'text-gray-400'}`} size={32} />
                    <p className="text-sm font-medium">CSV</p>
                  </button>
                </div>
              </div>

              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-3">
                  Conteúdo do Relatório
                </label>
                <div className="space-y-2">
                  <label className="flex items-center p-3 bg-gray-50 rounded-lg cursor-pointer hover:bg-gray-100 transition-colors">
                    <input
                      type="checkbox"
                      checked={incluirGraficos}
                      onChange={(e) => setIncluirGraficos(e.target.checked)}
                      className="w-5 h-5 text-indigo-600 rounded focus:ring-2 focus:ring-indigo-500"
                    />
                    <span className="ml-3 text-sm font-medium text-gray-700">Incluir Gráficos e Visualizações</span>
                  </label>

                  <label className="flex items-center p-3 bg-gray-50 rounded-lg cursor-pointer hover:bg-gray-100 transition-colors">
                    <input
                      type="checkbox"
                      checked={incluirVideo}
                      onChange={(e) => setIncluirVideo(e.target.checked)}
                      className="w-5 h-5 text-indigo-600 rounded focus:ring-2 focus:ring-indigo-500"
                    />
                    <span className="ml-3 text-sm font-medium text-gray-700">Incluir Vídeo Sincronizado</span>
                  </label>

                  <label className="flex items-center p-3 bg-gray-50 rounded-lg cursor-pointer hover:bg-gray-100 transition-colors">
                    <input
                      type="checkbox"
                      checked={incluirDadosBrutos}
                      onChange={(e) => setIncluirDadosBrutos(e.target.checked)}
                      className="w-5 h-5 text-indigo-600 rounded focus:ring-2 focus:ring-indigo-500"
                    />
                    <span className="ml-3 text-sm font-medium text-gray-700">Incluir Dados Brutos (CSV)</span>
                  </label>
                </div>
              </div>
            </div>

            <button
              onClick={handleExportar}
              className="w-full py-4 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl font-semibold text-lg flex items-center justify-center transition-all shadow-lg hover:shadow-xl"
            >
              <Download className="mr-2" size={24} />
              <span>Salvar Relatório</span>
            </button>
          </>
        ) : (
          <div className="text-center py-8">
            <div className="inline-flex items-center justify-center w-20 h-20 bg-green-100 rounded-full mb-4">
              <CheckCircle className="text-green-600" size={48} />
            </div>
            <h3 className="text-2xl font-bold text-gray-800 mb-2">Relatório Salvo com Sucesso!</h3>
            <p className="text-gray-600">O arquivo foi exportado e está disponível para download.</p>
          </div>
        )}
      </div>
    </div>
  );
}
