import { useState } from 'react';
import { ArrowLeft, Download, ChevronDown, ChevronUp, FileText, FileSpreadsheet, ImageOff } from 'lucide-react';
import { urlCompleta } from '../../lib/api';
import type { DadosSessao } from '../App';

interface VisualizacaoTracadoProps {
  dadosSessao: DadosSessao;
  onVoltar: () => void;
}

export function VisualizacaoTracado({ dadosSessao, onVoltar }: VisualizacaoTracadoProps) {
  const [pilotosExpandidos, setPilotosExpandidos] = useState<Record<string, boolean>>(
    Object.fromEntries(dadosSessao.pilotos.map((p, i) => [p.nome, i === 0])),
  );

  // URLs vêm direto do JSON do POST /api/processar/sessao (ou do fallback nos GETs).
  const tracadoIdealUrl    = dadosSessao.tracadoIdealUrl    ? urlCompleta(dadosSessao.tracadoIdealUrl)    : null;
  const tracadoIdealCsvUrl = dadosSessao.tracadoIdealCsvUrl ? urlCompleta(dadosSessao.tracadoIdealCsvUrl) : null;
  const csvGeralUrl        = dadosSessao.csvGeralUrl        ? urlCompleta(dadosSessao.csvGeralUrl)        : null;

  const togglePiloto = (nome: string) => {
    setPilotosExpandidos((prev) => ({ ...prev, [nome]: !prev[nome] }));
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 p-6">
      <div className="max-w-7xl mx-auto">
        <div className="bg-white rounded-2xl shadow-2xl p-8">
          <div className="flex items-center mb-8">
            <button
              onClick={onVoltar}
              className="mr-4 p-2 hover:bg-gray-100 rounded-lg transition-colors"
            >
              <ArrowLeft size={24} />
            </button>
            <div>
              <h2 className="text-2xl font-bold text-gray-800">Visualização e Relatórios</h2>
              <p className="text-gray-600">Sessão: {dadosSessao.sessaoNome}</p>
            </div>
          </div>

          <div className="space-y-6">
            {/* DADOS GERAIS */}
            <div className="bg-gradient-to-r from-green-50 to-emerald-50 rounded-xl p-6 border-2 border-green-200">
              <h3 className="text-xl font-semibold text-gray-800 mb-4">Dados Gerais</h3>

              {/* Traçado Ideal */}
              <div className="mb-6">
                <div className="bg-white rounded-lg p-4">
                  <h4 className="font-medium text-gray-700 mb-3">Traçado Ideal</h4>
                  {tracadoIdealUrl ? (
                    <img
                      src={tracadoIdealUrl}
                      alt="Traçado Ideal"
                      className="w-full rounded-lg"
                    />
                  ) : (
                    <div className="flex flex-col items-center justify-center h-48 text-gray-400 gap-2">
                      <ImageOff size={40} />
                      <span className="text-sm">Gráfico não disponível</span>
                    </div>
                  )}
                </div>
              </div>

              {/* CSV do Traçado Ideal */}
              {tracadoIdealCsvUrl && (
                <div className="mb-6">
                  <h4 className="font-medium text-gray-700 mb-3">Dados do Traçado Ideal</h4>
                  <div className="flex items-center justify-between bg-white rounded-lg p-4">
                    <div className="flex items-center gap-3">
                      <div className="p-2 bg-emerald-100 rounded-lg">
                        <FileSpreadsheet className="text-emerald-600" size={20} />
                      </div>
                      <span className="font-medium text-gray-700">CSV — Traçado Ideal</span>
                    </div>
                    <a
                      href={tracadoIdealCsvUrl}
                      download
                      className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg font-medium flex items-center gap-2 transition-colors"
                    >
                      <Download size={18} />
                    </a>
                  </div>
                </div>
              )}

              {/* Rankings Gerais */}
              <div>
                <h4 className="font-medium text-gray-700 mb-3">Rankings Gerais</h4>
                {csvGeralUrl ? (
                  <div className="flex items-center justify-between bg-white rounded-lg p-4">
                    <div className="flex items-center gap-3">
                      <div className="p-2 bg-red-100 rounded-lg">
                        <FileText className="text-red-600" size={20} />
                      </div>
                      <span className="font-medium text-gray-700">Download CSV Geral</span>
                    </div>
                    <a
                      href={csvGeralUrl}
                      download
                      className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg font-medium flex items-center gap-2 transition-colors"
                    >
                      <Download size={18} />
                    </a>
                  </div>
                ) : (
                  <div className="flex items-center gap-3 bg-white rounded-lg p-4 opacity-50">
                    <div className="p-2 bg-gray-100 rounded-lg">
                      <FileText className="text-gray-400" size={20} />
                    </div>
                    <span className="text-gray-500">CSV Geral não disponível</span>
                  </div>
                )}
              </div>
            </div>

            {/* PILOTOS */}
            {dadosSessao.pilotos.map((piloto, index) => (
              <div
                key={piloto.nome}
                className="bg-gradient-to-r from-purple-50 to-pink-50 rounded-xl border-2 border-purple-200"
              >
                <div
                  className="flex items-center justify-between p-6 cursor-pointer hover:bg-purple-100 transition-colors rounded-t-xl"
                  onClick={() => togglePiloto(piloto.nome)}
                >
                  <h3 className="text-xl font-semibold text-gray-800">
                    Piloto {String(index + 1).padStart(2, '0')} - {piloto.nome}
                  </h3>
                  {pilotosExpandidos[piloto.nome] ? (
                    <ChevronUp size={24} className="text-gray-600" />
                  ) : (
                    <ChevronDown size={24} className="text-gray-600" />
                  )}
                </div>

                {pilotosExpandidos[piloto.nome] && (
                  <div className="px-6 pb-6 space-y-6">
                    {/* Análise Individual — gráficos por volta */}
                    <div>
                      <h4 className="font-semibold text-gray-700 mb-4">Análise Individual</h4>
                      {piloto.arquivos.graficos.length > 0 ? (
                        <div className="space-y-4">
                          {piloto.arquivos.graficos.map((url, gi) => (
                            <div key={url} className="bg-white rounded-lg p-4">
                              <p className="text-sm font-medium text-gray-600 mb-3">
                                Gráfico {gi + 1}
                              </p>
                              <img
                                src={urlCompleta(url)}
                                alt={`Gráfico ${gi + 1} - ${piloto.nome}`}
                                className="w-full rounded"
                              />
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div className="flex flex-col items-center justify-center h-32 bg-white rounded-lg text-gray-400 gap-2">
                          <ImageOff size={32} />
                          <span className="text-sm">Nenhum gráfico disponível para este piloto</span>
                        </div>
                      )}
                    </div>

                    {/* Relatório Individual */}
                    <div>
                      <h4 className="font-semibold text-gray-700 mb-4">Relatório Individual</h4>
                      <div className="space-y-3">
                        {piloto.arquivos.relatorio_pdf ? (
                          <div className="flex items-center justify-between bg-white rounded-lg p-4">
                            <div className="flex items-center gap-3">
                              <div className="p-2 bg-red-100 rounded-lg">
                                <FileText className="text-red-600" size={20} />
                              </div>
                              <span className="font-medium text-gray-700">Download PDF</span>
                            </div>
                            <a
                              href={urlCompleta(piloto.arquivos.relatorio_pdf)}
                              download
                              className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg font-medium flex items-center gap-2 transition-colors"
                            >
                              <Download size={18} />
                            </a>
                          </div>
                        ) : (
                          <div className="flex items-center gap-3 bg-white rounded-lg p-4 opacity-50">
                            <div className="p-2 bg-gray-100 rounded-lg">
                              <FileText className="text-gray-400" size={20} />
                            </div>
                            <span className="text-gray-500">PDF não disponível</span>
                          </div>
                        )}

                        {piloto.arquivos.csv ? (
                          <div className="flex items-center justify-between bg-white rounded-lg p-4">
                            <div className="flex items-center gap-3">
                              <div className="p-2 bg-green-100 rounded-lg">
                                <FileSpreadsheet className="text-green-600" size={20} />
                              </div>
                              <span className="font-medium text-gray-700">CSV do piloto</span>
                            </div>
                            <a
                              href={urlCompleta(piloto.arquivos.csv)}
                              download
                              className="px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg font-medium flex items-center gap-2 transition-colors"
                            >
                              <Download size={18} />
                            </a>
                          </div>
                        ) : (
                          <div className="flex items-center gap-3 bg-white rounded-lg p-4 opacity-50">
                            <div className="p-2 bg-gray-100 rounded-lg">
                              <FileSpreadsheet className="text-gray-400" size={20} />
                            </div>
                            <span className="text-gray-500">CSV não disponível</span>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
