import { ArrowLeft, FileText, Calendar, Clock } from 'lucide-react';

interface HistoricoProps {
  onVoltar: () => void;
  onCarregarSessao: (id: number) => void;
}

interface SessaoSalva {
  id: number;
  nome: string;
  data: string;
  hora: string;
  piloto: string;
  pista: string;
}

const sessoesExemplo: SessaoSalva[] = [
  { id: 1, nome: 'Análise Interlagos - Volta Rápida', data: '2026-04-28', hora: '14:30', piloto: 'Piloto A', pista: 'Interlagos' },
  { id: 2, nome: 'Treino Livre - Sessão Manhã', data: '2026-04-25', hora: '09:15', piloto: 'Piloto B', pista: 'Spa-Francorchamps' },
  { id: 3, nome: 'Classificação - Q3', data: '2026-04-20', hora: '16:45', piloto: 'Piloto A', pista: 'Monza' },
  { id: 4, nome: 'Race Simulation', data: '2026-04-18', hora: '11:00', piloto: 'Piloto C', pista: 'Silverstone' },
];

export function Historico({ onVoltar, onCarregarSessao }: HistoricoProps) {
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
              <h2 className="text-2xl font-bold text-gray-800">Histórico de Análises</h2>
              <p className="text-gray-600">Sessões salvas anteriormente</p>
            </div>
          </div>

          <div className="space-y-4">
            {sessoesExemplo.map((sessao) => (
              <div
                key={sessao.id}
                onClick={() => onCarregarSessao(sessao.id)}
                className="bg-gradient-to-r from-gray-50 to-indigo-50 rounded-xl p-6 hover:shadow-lg transition-all cursor-pointer border-2 border-transparent hover:border-indigo-400"
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center mb-2">
                      <FileText className="mr-2 text-indigo-600" size={24} />
                      <h3 className="text-lg font-semibold text-gray-800">{sessao.nome}</h3>
                    </div>
                    <div className="grid md:grid-cols-2 gap-4 ml-8">
                      <div className="flex items-center text-gray-600">
                        <Calendar className="mr-2" size={16} />
                        <span className="text-sm">{sessao.data}</span>
                      </div>
                      <div className="flex items-center text-gray-600">
                        <Clock className="mr-2" size={16} />
                        <span className="text-sm">{sessao.hora}</span>
                      </div>
                      <div className="text-sm text-gray-700">
                        <span className="font-medium">Piloto:</span> {sessao.piloto}
                      </div>
                      <div className="text-sm text-gray-700">
                        <span className="font-medium">Pista:</span> {sessao.pista}
                      </div>
                    </div>
                  </div>
                  <button className="ml-4 px-6 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg font-medium transition-colors">
                    Carregar
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
