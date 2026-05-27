import { ArrowLeft, Upload, Settings, Play } from 'lucide-react';
import { useState } from 'react';

interface AnaliseIndividualProps {
  onVoltar: () => void;
  onProcessar: () => void;
}

export function AnaliseIndividual({ onVoltar, onProcessar }: AnaliseIndividualProps) {
  const [csvMotec, setCsvMotec] = useState<File | null>(null);
  const [csvEyeTracker, setCsvEyeTracker] = useState<File | null>(null);

  const [syncFrame, setSyncFrame] = useState('0');
  const [syncMotec, setSyncMotec] = useState('0');

  const [frameInicial, setFrameInicial] = useState('0');
  const [frameFinal, setFrameFinal] = useState('0');
  const [motecInicial, setMotecInicial] = useState('0');
  const [motecFinal, setMotecFinal] = useState('0');

  const isValid = csvMotec && csvEyeTracker;

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 p-6">
      <div className="max-w-5xl mx-auto">
        <div className="bg-white rounded-2xl shadow-2xl p-8">
          <div className="flex items-center mb-6">
            <button
              onClick={onVoltar}
              className="mr-4 p-2 hover:bg-gray-100 rounded-lg transition-colors"
            >
              <ArrowLeft size={24} />
            </button>
            <div>
              <h2 className="text-2xl font-bold text-gray-800">Análise Individual</h2>
              <p className="text-gray-600">Upload de dados e configuração de sincronização</p>
            </div>
          </div>

          <div className="grid md:grid-cols-2 gap-6 mb-8">
            <div className="border-2 border-dashed border-gray-300 rounded-xl p-6 hover:border-indigo-400 transition-colors">
              <label className="cursor-pointer block">
                <input
                  type="file"
                  className="hidden"
                  accept=".csv"
                  onChange={(e) => setCsvMotec(e.target.files?.[0] || null)}
                />
                <div className="text-center">
                  <Upload className="mx-auto mb-3 text-indigo-600" size={40} />
                  <p className="font-semibold text-gray-800 mb-1">CSV MoTeC</p>
                  {csvMotec ? (
                    <p className="text-sm text-green-600 font-medium">{csvMotec.name}</p>
                  ) : (
                    <p className="text-sm text-gray-500">Clique para selecionar arquivo</p>
                  )}
                </div>
              </label>
            </div>

            <div className="border-2 border-dashed border-gray-300 rounded-xl p-6 hover:border-indigo-400 transition-colors">
              <label className="cursor-pointer block">
                <input
                  type="file"
                  className="hidden"
                  accept=".csv"
                  onChange={(e) => setCsvEyeTracker(e.target.files?.[0] || null)}
                />
                <div className="text-center">
                  <Upload className="mx-auto mb-3 text-indigo-600" size={40} />
                  <p className="font-semibold text-gray-800 mb-1">CSV Eye Tracker</p>
                  {csvEyeTracker ? (
                    <p className="text-sm text-green-600 font-medium">{csvEyeTracker.name}</p>
                  ) : (
                    <p className="text-sm text-gray-500">Clique para selecionar arquivo</p>
                  )}
                </div>
              </label>
            </div>
          </div>

          <div className="bg-gray-50 rounded-xl p-6 mb-6">
            <div className="flex items-center mb-4">
              <Settings className="mr-2 text-indigo-600" size={24} />
              <h3 className="text-lg font-semibold text-gray-800">Valores de Sincronização</h3>
            </div>
            <div className="grid md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Frame
                </label>
                <input
                  type="number"
                  value={syncFrame}
                  onChange={(e) => setSyncFrame(e.target.value)}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                  placeholder="0"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  MoTeC
                </label>
                <input
                  type="number"
                  value={syncMotec}
                  onChange={(e) => setSyncMotec(e.target.value)}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                  placeholder="0"
                />
              </div>
            </div>
          </div>

          <div className="bg-indigo-50 rounded-xl p-6 mb-8">
            <div className="flex items-center mb-4">
              <Settings className="mr-2 text-indigo-600" size={24} />
              <h3 className="text-lg font-semibold text-gray-800">Valores da Volta de Ouro</h3>
            </div>
            <div className="grid md:grid-cols-2 gap-6">
              <div>
                <h4 className="font-semibold text-gray-700 mb-3">Frames</h4>
                <div className="space-y-3">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Frame Inicial
                    </label>
                    <input
                      type="number"
                      value={frameInicial}
                      onChange={(e) => setFrameInicial(e.target.value)}
                      className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                      placeholder="0"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Frame Final
                    </label>
                    <input
                      type="number"
                      value={frameFinal}
                      onChange={(e) => setFrameFinal(e.target.value)}
                      className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                      placeholder="0"
                    />
                  </div>
                </div>
              </div>

              <div>
                <h4 className="font-semibold text-gray-700 mb-3">MoTeC</h4>
                <div className="space-y-3">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      MoTeC Inicial
                    </label>
                    <input
                      type="number"
                      value={motecInicial}
                      onChange={(e) => setMotecInicial(e.target.value)}
                      className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                      placeholder="0"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      MoTeC Final
                    </label>
                    <input
                      type="number"
                      value={motecFinal}
                      onChange={(e) => setMotecFinal(e.target.value)}
                      className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                      placeholder="0"
                    />
                  </div>
                </div>
              </div>
            </div>
          </div>

          <button
            onClick={onProcessar}
            disabled={!isValid}
            className={`w-full py-4 rounded-xl font-semibold text-lg flex items-center justify-center transition-all ${
              isValid
                ? 'bg-indigo-600 hover:bg-indigo-700 text-white shadow-lg hover:shadow-xl'
                : 'bg-gray-300 text-gray-500 cursor-not-allowed'
            }`}
          >
            <Play className="mr-2" size={24} />
            <span>Processar Análise</span>
          </button>
        </div>
      </div>
    </div>
  );
}
