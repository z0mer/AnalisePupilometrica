import { User, TrendingUp, AlertTriangle, UserX, Clock } from 'lucide-react';

interface MenuPrincipalProps {
  onAnaliseIndividual: () => void;
  onMediaVoltaIdeal: () => void;
  onAnomaliasGerais: () => void;
  onAnomaliasIndividuais: () => void;
}

interface HistoricoItem {
  id: number;
  tipo: string;
  data: string;
  piloto?: string;
}

const historicoExemplo: HistoricoItem[] = [
  { id: 1, tipo: 'Análise Individual', data: '2026-04-30 14:30', piloto: 'Piloto A' },
  { id: 2, tipo: 'Média Volta Ideal', data: '2026-04-29 10:15', piloto: 'Múltiplos' },
  { id: 3, tipo: 'Anomalias Gerais', data: '2026-04-28 16:45' },
];

export function MenuPrincipal({
  onAnaliseIndividual,
  onMediaVoltaIdeal,
  onAnomaliasGerais,
  onAnomaliasIndividuais
}: MenuPrincipalProps) {
  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 p-6">
      <div className="max-w-6xl mx-auto">
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold text-gray-800 mb-2">
            Sistema de Análise
          </h1>
          <p className="text-gray-600 text-lg">
            Telemetria e Eye Tracking
          </p>
        </div>

        <div className="grid md:grid-cols-2 gap-6 mb-8">
          <button
            onClick={onAnaliseIndividual}
            className="bg-white hover:bg-indigo-50 rounded-2xl p-8 shadow-lg hover:shadow-xl transition-all border-2 border-transparent hover:border-indigo-400 group"
          >
            <div className="flex items-center justify-between mb-4">
              <div className="p-3 bg-indigo-100 rounded-xl group-hover:bg-indigo-200 transition-colors">
                <User className="text-indigo-600" size={32} />
              </div>
              <span className="text-4xl font-bold text-gray-300">1</span>
            </div>
            <h3 className="text-xl font-bold text-gray-800 mb-2">Análise Individual</h3>
            <p className="text-gray-600 text-sm">Análise detalhada de um piloto específico</p>
          </button>

          <button
            onClick={onMediaVoltaIdeal}
            className="bg-white hover:bg-green-50 rounded-2xl p-8 shadow-lg hover:shadow-xl transition-all border-2 border-transparent hover:border-green-400 group"
          >
            <div className="flex items-center justify-between mb-4">
              <div className="p-3 bg-green-100 rounded-xl group-hover:bg-green-200 transition-colors">
                <TrendingUp className="text-green-600" size={32} />
              </div>
              <span className="text-4xl font-bold text-gray-300">2</span>
            </div>
            <h3 className="text-xl font-bold text-gray-800 mb-2">Média da Volta Ideal</h3>
            <p className="text-gray-600 text-sm">Cálculo da média ideal entre múltiplos pilotos</p>
          </button>

          <button
            onClick={onAnomaliasGerais}
            className="bg-white hover:bg-orange-50 rounded-2xl p-8 shadow-lg hover:shadow-xl transition-all border-2 border-transparent hover:border-orange-400 group"
          >
            <div className="flex items-center justify-between mb-4">
              <div className="p-3 bg-orange-100 rounded-xl group-hover:bg-orange-200 transition-colors">
                <AlertTriangle className="text-orange-600" size={32} />
              </div>
              <span className="text-4xl font-bold text-gray-300">3</span>
            </div>
            <h3 className="text-xl font-bold text-gray-800 mb-2">Anomalias Gerais</h3>
            <p className="text-gray-600 text-sm">Detecção de anomalias em todos os pilotos</p>
          </button>

          <button
            onClick={onAnomaliasIndividuais}
            className="bg-white hover:bg-red-50 rounded-2xl p-8 shadow-lg hover:shadow-xl transition-all border-2 border-transparent hover:border-red-400 group"
          >
            <div className="flex items-center justify-between mb-4">
              <div className="p-3 bg-red-100 rounded-xl group-hover:bg-red-200 transition-colors">
                <UserX className="text-red-600" size={32} />
              </div>
              <span className="text-4xl font-bold text-gray-300">4</span>
            </div>
            <h3 className="text-xl font-bold text-gray-800 mb-2">Anomalias Individuais</h3>
            <p className="text-gray-600 text-sm">Relatório de anomalias por piloto</p>
          </button>
        </div>

        <div className="bg-white rounded-2xl shadow-lg p-6">
          <div className="flex items-center mb-4">
            <Clock className="mr-2 text-gray-600" size={24} />
            <h2 className="text-xl font-bold text-gray-800">Histórico Recente</h2>
          </div>
          <div className="space-y-2">
            {historicoExemplo.map((item) => (
              <div
                key={item.id}
                className="flex items-center justify-between p-4 bg-gray-50 hover:bg-gray-100 rounded-xl transition-colors cursor-pointer"
              >
                <div>
                  <p className="font-semibold text-gray-800">{item.tipo}</p>
                  {item.piloto && <p className="text-sm text-gray-600">{item.piloto}</p>}
                </div>
                <p className="text-sm text-gray-500">{item.data}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
