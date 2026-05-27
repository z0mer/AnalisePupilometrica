import { ArrowLeft, Play, FileDown, Plus, Trash2, User } from 'lucide-react';
import { useState } from 'react';

interface AnomaliasGeraisProps {
  onVoltar: () => void;
  onProcessar: () => void;
}

interface PilotoFrame {
  id: number;
  nome: string;
  frame: string;
}

export function AnomaliasGerais({ onVoltar, onProcessar }: AnomaliasGeraisProps) {
  const [pilotos, setPilotos] = useState<PilotoFrame[]>([
    { id: 1, nome: 'Piloto 1', frame: '0' },
  ]);
  const [processado, setProcessado] = useState(false);

  const adicionarPiloto = () => {
    const novoId = Math.max(...pilotos.map((p) => p.id)) + 1;
    setPilotos([...pilotos, { id: novoId, nome: `Piloto ${novoId}`, frame: '0' }]);
  };

  const removerPiloto = (id: number) => {
    if (pilotos.length > 1) {
      setPilotos(pilotos.filter((p) => p.id !== id));
    }
  };

  const atualizarPiloto = (id: number, campo: keyof PilotoFrame, valor: string) => {
    setPilotos(pilotos.map((p) => (p.id === id ? { ...p, [campo]: valor } : p)));
  };

  const handleProcessar = () => {
    onProcessar();
    setProcessado(true);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 p-6">
      <div className="max-w-5xl mx-auto">
        <div className="bg-white rounded-2xl shadow-2xl p-8">
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center">
              <button
                onClick={onVoltar}
                className="mr-4 p-2 hover:bg-gray-100 rounded-lg transition-colors"
              >
                <ArrowLeft size={24} />
              </button>
              <div>
                <h2 className="text-2xl font-bold text-gray-800">Anomalias Gerais</h2>
                <p className="text-gray-600">Detecção de anomalias de todos os pilotos</p>
              </div>
            </div>
            {!processado && (
              <button
                onClick={adicionarPiloto}
                className="px-4 py-2 bg-orange-600 hover:bg-orange-700 text-white rounded-lg font-medium flex items-center transition-colors"
              >
                <Plus className="mr-2" size={20} />
                Adicionar Piloto
              </button>
            )}
          </div>

          {!processado ? (
            <>
              <div className="space-y-4 mb-8">
                {pilotos.map((piloto) => (
                  <div
                    key={piloto.id}
                    className="bg-gradient-to-r from-orange-50 to-yellow-50 rounded-xl p-6 border-2 border-orange-200"
                  >
                    <div className="flex items-center gap-4">
                      <div className="p-2 bg-orange-100 rounded-lg">
                        <User className="text-orange-600" size={24} />
                      </div>
                      <div className="flex-1">
                        <input
                          type="text"
                          value={piloto.nome}
                          onChange={(e) => atualizarPiloto(piloto.id, 'nome', e.target.value)}
                          className="w-full font-semibold bg-transparent border-b-2 border-transparent hover:border-orange-400 focus:border-orange-600 focus:outline-none px-2 py-1 mb-2"
                          placeholder="Nome do piloto"
                        />
                        <div className="flex items-center gap-3">
                          <label className="text-sm font-medium text-gray-700 whitespace-nowrap">
                            Frame:
                          </label>
                          <input
                            type="number"
                            value={piloto.frame}
                            onChange={(e) => atualizarPiloto(piloto.id, 'frame', e.target.value)}
                            className="flex-1 px-4 py-2 border-2 border-orange-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-transparent font-mono"
                            placeholder="0"
                          />
                        </div>
                      </div>
                      {pilotos.length > 1 && (
                        <button
                          onClick={() => removerPiloto(piloto.id)}
                          className="p-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                        >
                          <Trash2 size={20} />
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>

              <button
                onClick={handleProcessar}
                className="w-full py-4 bg-orange-600 hover:bg-orange-700 text-white rounded-xl font-semibold text-lg flex items-center justify-center transition-all shadow-lg hover:shadow-xl"
              >
                <Play className="mr-2" size={24} />
                <span>Processar Anomalias Gerais</span>
              </button>
            </>
          ) : (
            <div className="space-y-4">
              <div className="bg-green-50 border-2 border-green-300 rounded-xl p-6 text-center">
                <div className="inline-flex items-center justify-center w-16 h-16 bg-green-100 rounded-full mb-4">
                  <FileDown className="text-green-600" size={32} />
                </div>
                <h3 className="text-xl font-bold text-gray-800 mb-2">Processamento Concluído!</h3>
                <p className="text-gray-600 mb-4">CSV com anomalias de todos os pilotos gerado com sucesso</p>
              </div>

              <button className="w-full py-4 bg-orange-600 hover:bg-orange-700 text-white rounded-xl font-semibold text-lg flex items-center justify-center transition-all shadow-lg hover:shadow-xl">
                <FileDown className="mr-2" size={24} />
                <span>Baixar CSV de Anomalias Gerais</span>
              </button>

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
