import { ArrowLeft, Play, FileDown, FileText, User } from 'lucide-react';
import { useState } from 'react';

interface AnomaliasIndividuaisProps {
  onVoltar: () => void;
  onProcessar: () => void;
}

export function AnomaliasIndividuais({ onVoltar, onProcessar }: AnomaliasIndividuaisProps) {
  const [nomePiloto, setNomePiloto] = useState('');
  const [frame, setFrame] = useState('0');
  const [processado, setProcessado] = useState(false);

  const handleProcessar = () => {
    onProcessar();
    setProcessado(true);
  };

  const isValid = nomePiloto.trim() !== '';

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 p-6">
      <div className="max-w-4xl mx-auto">
        <div className="bg-white rounded-2xl shadow-2xl p-8">
          <div className="flex items-center mb-6">
            <button
              onClick={onVoltar}
              className="mr-4 p-2 hover:bg-gray-100 rounded-lg transition-colors"
            >
              <ArrowLeft size={24} />
            </button>
            <div>
              <h2 className="text-2xl font-bold text-gray-800">Anomalias Individuais</h2>
              <p className="text-gray-600">Relatório e CSV individual por piloto</p>
            </div>
          </div>

          {!processado ? (
            <>
              <div className="bg-red-50 rounded-xl p-6 mb-6 border-2 border-red-200">
                <div className="flex items-center mb-4">
                  <User className="mr-2 text-red-600" size={24} />
                  <h3 className="text-lg font-semibold text-gray-800">Identificação do Piloto</h3>
                </div>
                <input
                  type="text"
                  value={nomePiloto}
                  onChange={(e) => setNomePiloto(e.target.value)}
                  className="w-full px-4 py-3 border-2 border-red-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent text-lg"
                  placeholder="Digite o nome do piloto"
                />
              </div>

              <div className="bg-red-50 rounded-xl p-6 mb-8 border-2 border-red-200">
                <label className="block text-lg font-semibold text-gray-800 mb-4">
                  Frame
                </label>
                <input
                  type="number"
                  value={frame}
                  onChange={(e) => setFrame(e.target.value)}
                  className="w-full px-6 py-4 text-xl text-center border-2 border-red-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent font-mono"
                  placeholder="0"
                />
                <p className="text-sm text-gray-600 mt-3">
                  Defina o frame de referência para análise individual
                </p>
              </div>

              <button
                onClick={handleProcessar}
                disabled={!isValid}
                className={`w-full py-4 rounded-xl font-semibold text-lg flex items-center justify-center transition-all shadow-lg hover:shadow-xl ${
                  isValid
                    ? 'bg-red-600 hover:bg-red-700 text-white'
                    : 'bg-gray-300 text-gray-500 cursor-not-allowed'
                }`}
              >
                <Play className="mr-2" size={24} />
                <span>Processar Anomalias Individuais</span>
              </button>
            </>
          ) : (
            <div className="space-y-4">
              <div className="bg-green-50 border-2 border-green-300 rounded-xl p-6 text-center">
                <div className="inline-flex items-center justify-center w-16 h-16 bg-green-100 rounded-full mb-4">
                  <FileText className="text-green-600" size={32} />
                </div>
                <h3 className="text-xl font-bold text-gray-800 mb-2">Processamento Concluído!</h3>
                <p className="text-gray-600 mb-2">Relatório e CSV individual gerados com sucesso</p>
                <p className="font-semibold text-gray-800">Piloto: {nomePiloto}</p>
              </div>

              <div className="grid md:grid-cols-2 gap-4">
                <button className="py-4 bg-red-600 hover:bg-red-700 text-white rounded-xl font-semibold flex items-center justify-center transition-all shadow-lg hover:shadow-xl">
                  <FileText className="mr-2" size={20} />
                  <span>Baixar Relatório PDF</span>
                </button>

                <button className="py-4 bg-red-600 hover:bg-red-700 text-white rounded-xl font-semibold flex items-center justify-center transition-all shadow-lg hover:shadow-xl">
                  <FileDown className="mr-2" size={20} />
                  <span>Baixar CSV Individual</span>
                </button>
              </div>

              <button
                onClick={onVoltar}
                className="w-full py-3 bg-gray-200 hover:bg-gray-300 text-gray-800 rounded-xl font-medium transition-colors"
              >
                Voltar ao Menu
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
