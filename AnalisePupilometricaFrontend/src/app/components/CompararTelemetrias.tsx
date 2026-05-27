import { ArrowLeft, Play, Pause, RotateCcw, ArrowRight, Target } from 'lucide-react';
import { useState } from 'react';

interface CompararTelemetriasProps {
  onVoltar: () => void;
  onAvancar: () => void;
  onCancelar: () => void;
  fromHistorico: boolean;
}

export function CompararTelemetrias({ onVoltar, onAvancar, onCancelar, fromHistorico }: CompararTelemetriasProps) {
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [syncOffset, setSyncOffset] = useState(0);

  const telemetriaData = {
    velocidade: 245,
    rpm: 8500,
    marcha: 6,
    aceleracao: 1.2,
    freio: 0,
    temperatura: 98
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 p-6">
      <div className="max-w-7xl mx-auto">
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
                <h2 className="text-2xl font-bold text-gray-800">Comparar Telemetrias</h2>
                <p className="text-gray-600">Tela 2 - Vídeo sincronizado com Gaze Point</p>
              </div>
            </div>
            <button
              onClick={onCancelar}
              className="px-4 py-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors"
            >
              Cancelar Análise
            </button>
          </div>

          <div className="grid lg:grid-cols-3 gap-6 mb-8">
            <div className="lg:col-span-2 space-y-4">
              <div className="bg-black rounded-xl overflow-hidden relative aspect-video">
                <div className="absolute inset-0 flex items-center justify-center">
                  <div className="text-center text-white">
                    <Play size={64} className="mx-auto mb-2 opacity-50" />
                    <p className="text-sm">Vídeo Sincronizado com Eye Tracking</p>
                  </div>
                </div>
                <div className="absolute top-4 left-4 bg-red-600 text-white px-3 py-1 rounded-full text-sm font-medium flex items-center">
                  <Target size={16} className="mr-1" />
                  Gaze Point Ativo
                </div>
              </div>

              <div className="bg-gray-100 rounded-xl p-4">
                <div className="flex items-center justify-between mb-4">
                  <button
                    onClick={() => setIsPlaying(!isPlaying)}
                    className="p-3 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg transition-colors"
                  >
                    {isPlaying ? <Pause size={24} /> : <Play size={24} />}
                  </button>
                  <button
                    onClick={() => setCurrentTime(0)}
                    className="p-3 bg-gray-300 hover:bg-gray-400 text-gray-800 rounded-lg transition-colors"
                  >
                    <RotateCcw size={24} />
                  </button>
                  <span className="text-lg font-mono font-semibold">
                    {Math.floor(currentTime / 60)}:{(currentTime % 60).toString().padStart(2, '0')}
                  </span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="180"
                  value={currentTime}
                  onChange={(e) => setCurrentTime(Number(e.target.value))}
                  className="w-full"
                />
              </div>

              <div className="bg-yellow-50 border-2 border-yellow-300 rounded-xl p-4">
                <h3 className="font-semibold text-gray-800 mb-3">Ajuste de Sincronia Manual</h3>
                <div className="flex items-center gap-4">
                  <label className="text-sm font-medium text-gray-700">Offset (ms):</label>
                  <input
                    type="range"
                    min="-1000"
                    max="1000"
                    step="10"
                    value={syncOffset}
                    onChange={(e) => setSyncOffset(Number(e.target.value))}
                    className="flex-1"
                  />
                  <span className="font-mono font-semibold text-gray-800 w-20 text-right">
                    {syncOffset > 0 ? '+' : ''}{syncOffset}ms
                  </span>
                </div>
              </div>
            </div>

            <div className="space-y-4">
              <div className="bg-gradient-to-br from-indigo-600 to-purple-600 text-white rounded-xl p-6">
                <h3 className="font-semibold mb-4">Telemetria Veicular</h3>
                <div className="space-y-3">
                  <div className="flex justify-between items-center">
                    <span className="text-sm opacity-90">Velocidade</span>
                    <span className="text-2xl font-bold">{telemetriaData.velocidade} km/h</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-sm opacity-90">RPM</span>
                    <span className="text-xl font-bold">{telemetriaData.rpm}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-sm opacity-90">Marcha</span>
                    <span className="text-xl font-bold">{telemetriaData.marcha}ª</span>
                  </div>
                </div>
              </div>

              <div className="bg-gray-50 rounded-xl p-6">
                <h3 className="font-semibold text-gray-800 mb-4">Dados Adicionais</h3>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-gray-600">Aceleração G</span>
                    <span className="font-semibold">{telemetriaData.aceleracao}g</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">Freio %</span>
                    <span className="font-semibold">{telemetriaData.freio}%</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">Temp. Água</span>
                    <span className="font-semibold">{telemetriaData.temperatura}°C</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <button
            onClick={onAvancar}
            className="w-full py-4 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl font-semibold text-lg flex items-center justify-center transition-all shadow-lg hover:shadow-xl"
          >
            <span>Plotar os Gráficos</span>
            <ArrowRight className="ml-2" size={24} />
          </button>
        </div>
      </div>
    </div>
  );
}
