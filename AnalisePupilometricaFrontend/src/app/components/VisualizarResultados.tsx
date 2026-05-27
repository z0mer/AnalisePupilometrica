import { ArrowLeft, Download, Brain, Eye, TrendingUp } from 'lucide-react';
import { LineChart, Line, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

interface VisualizarResultadosProps {
  onVoltar: () => void;
  onExportar: () => void;
  onCancelar: () => void;
}

const dadosCargaCognitiva = [
  { tempo: 0, carga: 30, velocidade: 120, fixacao: 200 },
  { tempo: 5, carga: 45, velocidade: 180, fixacao: 180 },
  { tempo: 10, carga: 65, velocidade: 220, fixacao: 150 },
  { tempo: 15, carga: 85, velocidade: 245, fixacao: 120 },
  { tempo: 20, carga: 78, velocidade: 230, fixacao: 140 },
  { tempo: 25, carga: 55, velocidade: 190, fixacao: 170 },
  { tempo: 30, carga: 40, velocidade: 150, fixacao: 190 },
  { tempo: 35, carga: 70, velocidade: 210, fixacao: 130 },
  { tempo: 40, carga: 88, velocidade: 250, fixacao: 110 },
  { tempo: 45, carga: 92, velocidade: 255, fixacao: 100 },
];

const dadosCorrelacao = [
  { tempo: 0, olhar: 50, telemetria: 45 },
  { tempo: 5, olhar: 60, telemetria: 58 },
  { tempo: 10, olhar: 75, telemetria: 70 },
  { tempo: 15, olhar: 85, telemetria: 82 },
  { tempo: 20, olhar: 70, telemetria: 75 },
  { tempo: 25, olhar: 55, telemetria: 60 },
  { tempo: 30, olhar: 45, telemetria: 50 },
  { tempo: 35, olhar: 80, telemetria: 78 },
  { tempo: 40, olhar: 90, telemetria: 88 },
  { tempo: 45, olhar: 95, telemetria: 92 },
];

export function VisualizarResultados({ onVoltar, onExportar, onCancelar }: VisualizarResultadosProps) {
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
                <h2 className="text-2xl font-bold text-gray-800">Visualizar Resultados</h2>
                <p className="text-gray-600">Tela 3 - Gráficos e análise de carga cognitiva</p>
              </div>
            </div>
            <button
              onClick={onCancelar}
              className="px-4 py-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors"
            >
              Cancelar Análise
            </button>
          </div>

          <div className="grid md:grid-cols-3 gap-4 mb-8">
            <div className="bg-gradient-to-br from-purple-500 to-purple-700 text-white rounded-xl p-6">
              <div className="flex items-center mb-2">
                <Brain className="mr-2" size={24} />
                <span className="text-sm opacity-90">Carga Cognitiva Média</span>
              </div>
              <p className="text-3xl font-bold">67%</p>
            </div>

            <div className="bg-gradient-to-br from-blue-500 to-blue-700 text-white rounded-xl p-6">
              <div className="flex items-center mb-2">
                <Eye className="mr-2" size={24} />
                <span className="text-sm opacity-90">Fixações Totais</span>
              </div>
              <p className="text-3xl font-bold">1,247</p>
            </div>

            <div className="bg-gradient-to-br from-green-500 to-green-700 text-white rounded-xl p-6">
              <div className="flex items-center mb-2">
                <TrendingUp className="mr-2" size={24} />
                <span className="text-sm opacity-90">Correlação Olhar/Velocidade</span>
              </div>
              <p className="text-3xl font-bold">0.89</p>
            </div>
          </div>

          <div className="space-y-6 mb-8">
            <div className="bg-gray-50 rounded-xl p-6">
              <h3 className="text-lg font-semibold text-gray-800 mb-4">
                Carga Cognitiva x Velocidade x Fixação
              </h3>
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={dadosCargaCognitiva}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="tempo" label={{ value: 'Tempo (s)', position: 'insideBottom', offset: -5 }} />
                  <YAxis />
                  <Tooltip />
                  <Legend />
                  <Line type="monotone" dataKey="carga" stroke="#8b5cf6" strokeWidth={2} name="Carga Cognitiva (%)" />
                  <Line type="monotone" dataKey="velocidade" stroke="#3b82f6" strokeWidth={2} name="Velocidade (km/h)" />
                  <Line type="monotone" dataKey="fixacao" stroke="#10b981" strokeWidth={2} name="Duração Fixação (ms)" />
                </LineChart>
              </ResponsiveContainer>
            </div>

            <div className="bg-gray-50 rounded-xl p-6">
              <h3 className="text-lg font-semibold text-gray-800 mb-4">
                Correlação Olhar x Telemetria
              </h3>
              <ResponsiveContainer width="100%" height={300}>
                <AreaChart data={dadosCorrelacao}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="tempo" label={{ value: 'Tempo (s)', position: 'insideBottom', offset: -5 }} />
                  <YAxis />
                  <Tooltip />
                  <Legend />
                  <Area type="monotone" dataKey="olhar" stackId="1" stroke="#f59e0b" fill="#fbbf24" name="Intensidade do Olhar" />
                  <Area type="monotone" dataKey="telemetria" stackId="2" stroke="#6366f1" fill="#818cf8" name="Intensidade Telemetria" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          <button
            onClick={onExportar}
            className="w-full py-4 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl font-semibold text-lg flex items-center justify-center transition-all shadow-lg hover:shadow-xl"
          >
            <Download className="mr-2" size={24} />
            <span>Exportar Relatório</span>
          </button>
        </div>
      </div>
    </div>
  );
}
