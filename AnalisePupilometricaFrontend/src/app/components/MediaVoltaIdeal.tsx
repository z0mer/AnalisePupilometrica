import { ArrowLeft, Upload, Plus, Trash2, Play, User } from 'lucide-react';
import { useState } from 'react';

interface MediaVoltaIdealProps {
  onVoltar: () => void;
  onProcessar: () => void;
}

interface Piloto {
  id: number;
  nome: string;
  csvMotec: File | null;
  csvEyeTracker: File | null;
  frameInicial: string;
  frameFinal: string;
  motecInicial: string;
  motecFinal: string;
}

export function MediaVoltaIdeal({ onVoltar, onProcessar }: MediaVoltaIdealProps) {
  const [pilotos, setPilotos] = useState<Piloto[]>([
    {
      id: 1,
      nome: 'Piloto 1',
      csvMotec: null,
      csvEyeTracker: null,
      frameInicial: '0',
      frameFinal: '0',
      motecInicial: '0',
      motecFinal: '0',
    },
  ]);

  const adicionarPiloto = () => {
    const novoId = Math.max(...pilotos.map((p) => p.id)) + 1;
    setPilotos([
      ...pilotos,
      {
        id: novoId,
        nome: `Piloto ${novoId}`,
        csvMotec: null,
        csvEyeTracker: null,
        frameInicial: '0',
        frameFinal: '0',
        motecInicial: '0',
        motecFinal: '0',
      },
    ]);
  };

  const removerPiloto = (id: number) => {
    if (pilotos.length > 1) {
      setPilotos(pilotos.filter((p) => p.id !== id));
    }
  };

  const atualizarPiloto = (id: number, campo: keyof Piloto, valor: any) => {
    setPilotos(pilotos.map((p) => (p.id === id ? { ...p, [campo]: valor } : p)));
  };

  const isValid = pilotos.every((p) => p.csvMotec && p.csvEyeTracker);

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 p-6">
      <div className="max-w-6xl mx-auto">
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
                <h2 className="text-2xl font-bold text-gray-800">Média da Volta Ideal</h2>
                <p className="text-gray-600">Configuração para múltiplos pilotos</p>
              </div>
            </div>
            <button
              onClick={adicionarPiloto}
              className="px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg font-medium flex items-center transition-colors"
            >
              <Plus className="mr-2" size={20} />
              Adicionar Piloto
            </button>
          </div>

          <div className="space-y-6 mb-8">
            {pilotos.map((piloto, index) => (
              <div key={piloto.id} className="bg-gradient-to-r from-gray-50 to-green-50 rounded-xl p-6 border-2 border-green-200">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center">
                    <div className="p-2 bg-green-100 rounded-lg mr-3">
                      <User className="text-green-600" size={24} />
                    </div>
                    <input
                      type="text"
                      value={piloto.nome}
                      onChange={(e) => atualizarPiloto(piloto.id, 'nome', e.target.value)}
                      className="text-lg font-semibold bg-transparent border-b-2 border-transparent hover:border-green-400 focus:border-green-600 focus:outline-none px-2 py-1"
                    />
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

                <div className="grid md:grid-cols-2 gap-4 mb-4">
                  <div className="border-2 border-dashed border-gray-300 rounded-lg p-4 hover:border-green-400 transition-colors">
                    <label className="cursor-pointer block">
                      <input
                        type="file"
                        className="hidden"
                        accept=".csv"
                        onChange={(e) => atualizarPiloto(piloto.id, 'csvMotec', e.target.files?.[0] || null)}
                      />
                      <div className="text-center">
                        <Upload className="mx-auto mb-2 text-green-600" size={32} />
                        <p className="font-medium text-gray-800 text-sm mb-1">CSV MoTeC</p>
                        {piloto.csvMotec ? (
                          <p className="text-xs text-green-600 font-medium truncate">{piloto.csvMotec.name}</p>
                        ) : (
                          <p className="text-xs text-gray-500">Clique para selecionar</p>
                        )}
                      </div>
                    </label>
                  </div>

                  <div className="border-2 border-dashed border-gray-300 rounded-lg p-4 hover:border-green-400 transition-colors">
                    <label className="cursor-pointer block">
                      <input
                        type="file"
                        className="hidden"
                        accept=".csv"
                        onChange={(e) => atualizarPiloto(piloto.id, 'csvEyeTracker', e.target.files?.[0] || null)}
                      />
                      <div className="text-center">
                        <Upload className="mx-auto mb-2 text-green-600" size={32} />
                        <p className="font-medium text-gray-800 text-sm mb-1">CSV Eye Tracker</p>
                        {piloto.csvEyeTracker ? (
                          <p className="text-xs text-green-600 font-medium truncate">{piloto.csvEyeTracker.name}</p>
                        ) : (
                          <p className="text-xs text-gray-500">Clique para selecionar</p>
                        )}
                      </div>
                    </label>
                  </div>
                </div>

                <div className="grid md:grid-cols-2 gap-6">
                  <div>
                    <h4 className="font-semibold text-gray-700 mb-2 text-sm">Frames</h4>
                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <label className="block text-xs font-medium text-gray-600 mb-1">Inicial</label>
                        <input
                          type="number"
                          value={piloto.frameInicial}
                          onChange={(e) => atualizarPiloto(piloto.id, 'frameInicial', e.target.value)}
                          className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-medium text-gray-600 mb-1">Final</label>
                        <input
                          type="number"
                          value={piloto.frameFinal}
                          onChange={(e) => atualizarPiloto(piloto.id, 'frameFinal', e.target.value)}
                          className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent"
                        />
                      </div>
                    </div>
                  </div>

                  <div>
                    <h4 className="font-semibold text-gray-700 mb-2 text-sm">MoTeC</h4>
                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <label className="block text-xs font-medium text-gray-600 mb-1">Inicial</label>
                        <input
                          type="number"
                          value={piloto.motecInicial}
                          onChange={(e) => atualizarPiloto(piloto.id, 'motecInicial', e.target.value)}
                          className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-medium text-gray-600 mb-1">Final</label>
                        <input
                          type="number"
                          value={piloto.motecFinal}
                          onChange={(e) => atualizarPiloto(piloto.id, 'motecFinal', e.target.value)}
                          className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent"
                        />
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>

          <button
            onClick={onProcessar}
            disabled={!isValid}
            className={`w-full py-4 rounded-xl font-semibold text-lg flex items-center justify-center transition-all ${
              isValid
                ? 'bg-green-600 hover:bg-green-700 text-white shadow-lg hover:shadow-xl'
                : 'bg-gray-300 text-gray-500 cursor-not-allowed'
            }`}
          >
            <Play className="mr-2" size={24} />
            <span>Gerar Média da Volta Ideal</span>
          </button>
        </div>
      </div>
    </div>
  );
}
