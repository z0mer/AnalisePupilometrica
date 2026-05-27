import { Upload, Settings, ArrowLeft, ArrowRight } from 'lucide-react';
import { useState } from 'react';

interface ConfigurarAnaliseProps {
  onVoltar: () => void;
  onProcessar: (config: AnaliseConfig) => void;
}

export interface AnaliseConfig {
  logMoTeC: File | null;
  logEyeTracker: File | null;
  calibracaoX: string;
  calibracaoY: string;
  calibracaoZ: string;
}

export function ConfigurarAnalise({ onVoltar, onProcessar }: ConfigurarAnaliseProps) {
  const [logMoTeC, setLogMoTeC] = useState<File | null>(null);
  const [logEyeTracker, setLogEyeTracker] = useState<File | null>(null);
  const [calibracaoX, setCalibracaoX] = useState('0.0');
  const [calibracaoY, setCalibracaoY] = useState('0.0');
  const [calibracaoZ, setCalibracaoZ] = useState('0.0');

  const handleSubmit = () => {
    if (logMoTeC && logEyeTracker) {
      onProcessar({ logMoTeC, logEyeTracker, calibracaoX, calibracaoY, calibracaoZ });
    }
  };

  const isValid = logMoTeC && logEyeTracker;

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
              <h2 className="text-2xl font-bold text-gray-800">Configurar Análise</h2>
              <p className="text-gray-600">Tela 1 - Upload de dados e calibração</p>
            </div>
          </div>

          <div className="grid md:grid-cols-2 gap-6 mb-8">
            <div className="border-2 border-dashed border-gray-300 rounded-xl p-6 hover:border-indigo-400 transition-colors">
              <label className="cursor-pointer block">
                <input
                  type="file"
                  className="hidden"
                  accept=".csv,.ld,.log"
                  onChange={(e) => setLogMoTeC(e.target.files?.[0] || null)}
                />
                <div className="text-center">
                  <Upload className="mx-auto mb-3 text-indigo-600" size={40} />
                  <p className="font-semibold text-gray-800 mb-1">Log MoTeC</p>
                  {logMoTeC ? (
                    <p className="text-sm text-green-600 font-medium">{logMoTeC.name}</p>
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
                  accept=".csv,.txt,.log"
                  onChange={(e) => setLogEyeTracker(e.target.files?.[0] || null)}
                />
                <div className="text-center">
                  <Upload className="mx-auto mb-3 text-indigo-600" size={40} />
                  <p className="font-semibold text-gray-800 mb-1">Log Eye Tracker</p>
                  {logEyeTracker ? (
                    <p className="text-sm text-green-600 font-medium">{logEyeTracker.name}</p>
                  ) : (
                    <p className="text-sm text-gray-500">Clique para selecionar arquivo</p>
                  )}
                </div>
              </label>
            </div>
          </div>

          <div className="bg-gray-50 rounded-xl p-6 mb-8">
            <div className="flex items-center mb-4">
              <Settings className="mr-2 text-indigo-600" size={24} />
              <h3 className="text-lg font-semibold text-gray-800">Valores de Calibração</h3>
            </div>
            <div className="grid md:grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Calibração X
                </label>
                <input
                  type="number"
                  step="0.1"
                  value={calibracaoX}
                  onChange={(e) => setCalibracaoX(e.target.value)}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Calibração Y
                </label>
                <input
                  type="number"
                  step="0.1"
                  value={calibracaoY}
                  onChange={(e) => setCalibracaoY(e.target.value)}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Calibração Z
                </label>
                <input
                  type="number"
                  step="0.1"
                  value={calibracaoZ}
                  onChange={(e) => setCalibracaoZ(e.target.value)}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                />
              </div>
            </div>
          </div>

          <button
            onClick={handleSubmit}
            disabled={!isValid}
            className={`w-full py-4 rounded-xl font-semibold text-lg flex items-center justify-center transition-all ${
              isValid
                ? 'bg-indigo-600 hover:bg-indigo-700 text-white shadow-lg hover:shadow-xl'
                : 'bg-gray-300 text-gray-500 cursor-not-allowed'
            }`}
          >
            <span>Processar e Enviar</span>
            <ArrowRight className="ml-2" size={24} />
          </button>
        </div>
      </div>
    </div>
  );
}
