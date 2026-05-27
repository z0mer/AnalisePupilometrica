import { useState, useEffect, useRef } from 'react';
import { Plus, Upload, Trash2, User, Info, Eye, ChevronDown, ChevronUp, AlertTriangle, CheckCircle, Loader2 } from 'lucide-react';
import * as Tooltip from '@radix-ui/react-tooltip';
import {
  listarSessoes,
  listarPilotos,
  criarSessao,
  buscarPiloto,
  cadastrar,
  buscarArquivosPiloto,
  listarVoltasPiloto,
  listarVoltasMotec,
  processarSessao,
  getStatusPiloto,
  buscarTracadoIdeal,
  buscarTracadoIdealCsv,
  buscarCsvGeral,
} from '../../lib/api';
import type {
  Sessao,
  VoltaPiloto,
  VoltaMotec,
  ProcessarSessaoResposta,
} from '../../lib/api';
import type { DadosSessao, PilotoComArquivos } from '../App';

interface PilotoData {
  id: number;
  nome: string;
  csvPupil: File | null;
  csvMotec: File | null;
  csvFixations: File | null;
  linkVideo: string;
  videoCarregado: boolean;
  fixacoes: string;
  fixacaoInicial: string;
  fixacaoFinal: string;
  motecIni: string;
  motecFim: string;
  identificacaoVolta: string;
  /** Voltas do banco (piloto já existente) */
  voltasDisponiveis: VoltaPiloto[];
  /** Voltas detectadas no CSV do MoTeC — tem prioridade sobre voltasDisponiveis */
  voltasMotec: VoltaMotec[];
  /** true = carregando voltas do MoTeC */
  carregandoVoltas: boolean;
  expandido: boolean;
  jaExiste: boolean | null;
  /** true = piloto já tem voltas e anomalias no banco (bloqueia upload) */
  jaProcessado: boolean;
  /** true = piloto existe mas a volta de ouro está faltando frames/tempos —
   *  libera reedição (motecIni/Fim editáveis) e reupload de CSV. */
  dadosIncompletos: boolean;
  /** true = backend tem caminho_pupil + caminho_motec persistidos.
   *  Habilita reprocessamento via disco sem precisar de upload novo. */
  temCsvsSalvos: boolean;
  /** Marco Zero do MoTeC capturado ao subir o CSV. Preenchido por
   *  handleMotecUpload via /api/listar-voltas-motec. Persistido no banco
   *  pelo cadastro — sem isso o tracado ideal sai dessincronizado. */
  tSyncMotecS: number | null;
}

interface FormularioDadosProps {
  onVisualizar: (dados: DadosSessao) => void;
}

function drivePreviewUrl(link: string): string | null {
  const m = link.match(/\/file\/d\/([^/?]+)/);
  return m ? `https://drive.google.com/file/d/${m[1]}/preview` : null;
}

const PILOTO_VAZIO = (id: number): PilotoData => ({
  id,
  nome: '',
  csvPupil: null,
  csvMotec: null,
  csvFixations: null,
  linkVideo: '',
  videoCarregado: false,
  fixacoes: '',
  fixacaoInicial: '',
  fixacaoFinal: '',
  motecIni: '',
  motecFim: '',
  identificacaoVolta: '1',
  voltasDisponiveis: [],
  voltasMotec: [],
  carregandoVoltas: false,
  expandido: true,
  jaExiste: null,
  jaProcessado: false,
  dadosIncompletos: false,
  temCsvsSalvos: false,
  tSyncMotecS: null,
});

export function FormularioDados({ onVisualizar }: FormularioDadosProps) {
  const [sessao, setSessao] = useState('');
  const [mostrarNovaSessao, setMostrarNovaSessao] = useState(false);
  const [novaSessao, setNovaSessao] = useState('');
  const [sessoesDisponiveis, setSessoesDisponiveis] = useState<Sessao[]>([]);
  const [pilotosDisponiveis, setPilotosDisponiveis] = useState<{ id: string; nome: string }[]>([]);
  const [pilotos, setPilotos] = useState<PilotoData[]>([PILOTO_VAZIO(1)]);
  const [fase, setFase] = useState<'idle' | 'salvando' | 'processando'>('idle');
  const [erro, setErro] = useState<string | null>(null);
  // controla qual card está no modo "novo piloto" (digitando nome livre)
  const [modoNovoPiloto, setModoNovoPiloto] = useState<Record<number, boolean>>({});

  const debounceTimers = useRef<Record<number, ReturnType<typeof setTimeout>>>({});

  useEffect(() => {
    listarSessoes().then(setSessoesDisponiveis).catch(() => {});
    listarPilotos().then(setPilotosDisponiveis).catch(() => {});
  }, []);

  // -------------------------------------------------------------------------
  // Helpers de estado
  // -------------------------------------------------------------------------

  const atualizarPiloto = (id: number, campos: Partial<PilotoData>) => {
    setPilotos(prev => prev.map(p => (p.id === id ? { ...p, ...campos } : p)));
  };

  const adicionarPiloto = () => {
    setPilotos(prev => {
      const novoId = Math.max(...prev.map(p => p.id)) + 1;
      return [...prev, PILOTO_VAZIO(novoId)];
    });
  };

  const removerPiloto = (id: number) => {
    setPilotos(prev => (prev.length > 1 ? prev.filter(p => p.id !== id) : prev));
    setModoNovoPiloto(prev => { const n = { ...prev }; delete n[id]; return n; });
  };

  const togglePiloto = (id: number) => {
    setPilotos(prev => prev.map(p => (p.id === id ? { ...p, expandido: !p.expandido } : p)));
  };

  // -------------------------------------------------------------------------
  // Nome do piloto — busca dados existentes no banco com debounce
  // -------------------------------------------------------------------------

  const handleNomePiloto = (id: number, nome: string) => {
    atualizarPiloto(id, {
      nome, jaExiste: null, jaProcessado: false, dadosIncompletos: false, temCsvsSalvos: false,
    });

    if (debounceTimers.current[id]) clearTimeout(debounceTimers.current[id]);
    if (!nome.trim()) return;

    debounceTimers.current[id] = setTimeout(async () => {
      try {
        const [piloto, voltas, status] = await Promise.all([
          buscarPiloto(nome.trim()),
          listarVoltasPiloto(nome.trim()),
          getStatusPiloto(nome.trim()),
        ]);

        if (piloto) {
          // Volta de ouro pode vir incompleta (frames/tempos null) mesmo com
          // status.processado=true — nesse caso liberamos reedição/reupload.
          const incompleto =
            piloto.frame_ini_pupil == null ||
            piloto.frame_fim_pupil == null ||
            piloto.t_ini_motec_s   == null ||
            piloto.t_fim_motec_s   == null;

          const ehProcessadoCompleto = status.processado && !incompleto;
          const limparCsvs = ehProcessadoCompleto
            ? { csvPupil: null, csvMotec: null, csvFixations: null }
            : {};

          atualizarPiloto(id, {
            jaExiste: true,
            jaProcessado: ehProcessadoCompleto,
            dadosIncompletos: incompleto,
            temCsvsSalvos: piloto.tem_csvs_salvos,
            fixacoes:         piloto.frame_sync      != null ? String(piloto.frame_sync)      : '',
            fixacaoInicial:   piloto.frame_ini_pupil != null ? String(piloto.frame_ini_pupil) : '',
            fixacaoFinal:     piloto.frame_fim_pupil != null ? String(piloto.frame_fim_pupil) : '',
            motecIni:         piloto.t_ini_motec_s   != null ? String(piloto.t_ini_motec_s)   : '',
            motecFim:         piloto.t_fim_motec_s   != null ? String(piloto.t_fim_motec_s)   : '',
            identificacaoVolta: String(piloto.numero_volta),
            voltasDisponiveis:  voltas,
            ...limparCsvs,
          });
        } else {
          atualizarPiloto(id, {
            jaExiste: false, jaProcessado: false, dadosIncompletos: false,
            temCsvsSalvos: false, voltasDisponiveis: [],
          });
        }
      } catch {
        // backend offline — não bloqueia
      }
    }, 500);
  };

  // -------------------------------------------------------------------------
  // Upload do CSV do MoTeC — chama API e preenche dropdown + tempos
  // -------------------------------------------------------------------------

  const handleMotecUpload = async (id: number, file: File | null) => {
    // Atualiza o arquivo imediatamente; reseta voltas antigas
    atualizarPiloto(id, {
      csvMotec: file, voltasMotec: [], carregandoVoltas: !!file, tSyncMotecS: null,
    });
    if (!file) return;

    try {
      const resp = await listarVoltasMotec(file);
      const voltas = resp.voltas;
      const tSync = resp.t_sync_motec_s;

      if (voltas.length > 0) {
        // Seleciona automaticamente a primeira volta e preenche os tempos.
        // O tSyncMotecS sai do CSV (primeira queda de Car Pos Norm) e será
        // persistido no cadastro — sem ele o tracado ideal fica errado.
        atualizarPiloto(id, {
          voltasMotec:        voltas,
          carregandoVoltas:   false,
          identificacaoVolta: String(voltas[0].numero_volta),
          motecIni:           String(voltas[0].t_ini),
          motecFim:           String(voltas[0].t_fim),
          tSyncMotecS:        tSync,
        });
      } else {
        atualizarPiloto(id, { voltasMotec: [], carregandoVoltas: false, tSyncMotecS: tSync });
      }
    } catch {
      // backend offline ou CSV inválido — não bloqueia o usuário
      atualizarPiloto(id, { carregandoVoltas: false });
    }
  };

  // -------------------------------------------------------------------------
  // Seleção de volta — auto-preenche MoTeC Inicial/Final
  // -------------------------------------------------------------------------

  const handleIdentificacaoVolta = (id: number, valor: string, voltasMotec: VoltaMotec[]) => {
    const num = Number(valor);
    const volta = voltasMotec.find(v => v.numero_volta === num);
    const updates: Partial<PilotoData> = { identificacaoVolta: valor };
    if (volta) {
      updates.motecIni = String(volta.t_ini);
      updates.motecFim = String(volta.t_fim);
    }
    atualizarPiloto(id, updates);
  };

  // -------------------------------------------------------------------------
  // Sessão
  // -------------------------------------------------------------------------

  const handleSessaoChange = (value: string) => {
    if (value === 'nova') {
      setMostrarNovaSessao(true);
      setSessao('');
    } else {
      setMostrarNovaSessao(false);
      setSessao(value);
    }
  };

  const handleSalvarNovaSessao = async () => {
    if (!novaSessao.trim()) return;
    try {
      const nova = await criarSessao(novaSessao.trim());
      setSessoesDisponiveis(prev => [nova, ...prev]);
      setSessao(nova.nome);
    } catch {
      setSessao(novaSessao.trim());
    } finally {
      setMostrarNovaSessao(false);
      setNovaSessao('');
    }
  };

  // -------------------------------------------------------------------------
  // Submissão
  // -------------------------------------------------------------------------

  const handleVisualizar = async () => {
    const nomeSessao = sessao.trim();
    const pilotosValidos = pilotos.filter(p => p.nome.trim());

    if (!nomeSessao) {
      setErro('Selecione ou crie uma sessão antes de continuar.');
      return;
    }
    if (pilotosValidos.length === 0) {
      setErro('Adicione ao menos um piloto com nome preenchido.');
      return;
    }

    // Bloqueia upload parcial (pupil sem motec ou vice-versa) — não dá pra
    // misturar CSVs novos de um lado com CSVs antigos do outro.
    const pilotoCsvParcial = pilotosValidos.find(
      p => (p.csvPupil || p.csvMotec) && !(p.csvPupil && p.csvMotec),
    );
    if (pilotoCsvParcial) {
      const falta = !pilotoCsvParcial.csvPupil ? 'Pupil' : 'MoTeC';
      setErro(
        `O piloto "${pilotoCsvParcial.nome}" tem upload parcial — falta o CSV ${falta} ` +
        `para o pipeline gerar gráficos, PDFs e CSVs.`,
      );
      return;
    }
    // Piloto novo (jaExiste=false) precisa subir CSVs — não há fonte no disco.
    const novoPilotoSemCsv = pilotosValidos.find(
      p => p.jaExiste === false && !(p.csvPupil && p.csvMotec),
    );
    if (novoPilotoSemCsv) {
      setErro(
        `O piloto "${novoPilotoSemCsv.nome}" é novo e precisa dos CSVs de Pupil e MoTeC para ser processado.`,
      );
      return;
    }

    setErro(null);
    setFase('salvando');

    try {
      // Etapa 1 — salva parâmetros de todos os pilotos no banco
      await Promise.all(
        pilotosValidos.map(p =>
          cadastrar({
            sessao_nome:     nomeSessao,
            piloto_nome:     p.nome.trim(),
            frame_sync:      p.fixacoes       ? parseInt(p.fixacoes)       : null,
            t_sync_motec_s:  p.tSyncMotecS,
            frame_ini_pupil: p.fixacaoInicial ? parseInt(p.fixacaoInicial) : null,
            frame_fim_pupil: p.fixacaoFinal   ? parseInt(p.fixacaoFinal)   : null,
            t_ini_motec_s:   p.motecIni       ? parseFloat(p.motecIni)     : null,
            t_fim_motec_s:   p.motecFim       ? parseFloat(p.motecFim)     : null,
            numero_volta:    parseInt(p.identificacaoVolta) || 1,
          }),
        ),
      );

      // Etapa 2 — processa todos os pilotos com fonte de dados disponível:
      // CSV upload novo OU CSVs persistidos no banco (lidos do disco pelo backend).
      console.table(
        pilotosValidos.map(p => ({
          nome:           p.nome,
          jaExiste:       p.jaExiste,
          temCsvsSalvos:  p.temCsvsSalvos,
          csvPupil:       p.csvPupil ? p.csvPupil.name : null,
          csvMotec:       p.csvMotec ? p.csvMotec.name : null,
          csvFixations:   p.csvFixations ? p.csvFixations.name : null,
        })),
      );
      const pilotosParaProcessar = pilotosValidos.filter(
        p => (p.csvPupil && p.csvMotec) || p.temCsvsSalvos,
      );
      // Backend usa listas paralelas posicionais (`pupil_csvs[i]` ↔ `piloto_nomes[i]`).
      // Pilotos sem upload omitem o arquivo da lista — para o índice continuar
      // alinhado, enviamos PRIMEIRO os com upload e DEPOIS os sem.
      // O `_has_upload(files, i)` cai em False naturalmente quando i >= len(files)
      // e o `_resolver_bytes_csv` busca via caminho_pupil/caminho_motec do banco.
      const pilotosOrdenados = [
        ...pilotosParaProcessar.filter(p => p.csvPupil && p.csvMotec),
        ...pilotosParaProcessar.filter(p => !(p.csvPupil && p.csvMotec)),
      ];
      console.log(
        `[handleVisualizar] pilotosParaProcessar=${pilotosOrdenados.length} de ${pilotosValidos.length} ` +
        `→ processarSessao ${pilotosOrdenados.length > 0 ? 'SERÁ' : 'NÃO será'} chamado.`,
      );
      let respProc: ProcessarSessaoResposta | null = null;
      if (pilotosOrdenados.length > 0) {
        setFase('processando');
        respProc = await processarSessao(
          nomeSessao,
          pilotosOrdenados.map(p => ({
            nome:            p.nome.trim(),
            pupilCsv:        p.csvPupil ?? null,
            motecCsv:        p.csvMotec ?? null,
            fixacoesCsv:     p.csvFixations ?? null,
            frame_sync:      p.fixacoes       ? parseInt(p.fixacoes)       : null,
            frame_ini_pupil: p.fixacaoInicial ? parseInt(p.fixacaoInicial) : null,
            frame_fim_pupil: p.fixacaoFinal   ? parseInt(p.fixacaoFinal)   : null,
            t_ini_motec_s:   p.motecIni       ? parseFloat(p.motecIni)     : null,
            t_fim_motec_s:   p.motecFim       ? parseFloat(p.motecFim)     : null,
            numero_volta:    parseInt(p.identificacaoVolta) || 1,
          })),
        );
      }

      // Atualiza lista do dropdown com novos pilotos cadastrados
      listarPilotos().then(setPilotosDisponiveis).catch(() => {});

      // Avisa sobre pilotos pulados pelo backend (sem CSV salvo no disco etc)
      if (respProc?.pilotos_pulados?.length) {
        const linhas = respProc.pilotos_pulados
          .map(p => `• ${p.nome}: ${p.motivo}`)
          .join('\n');
        setErro(
          `Atenção — ${respProc.pilotos_pulados.length} piloto(s) não foram processados:\n${linhas}\n\n` +
          `Suba o CSV do(s) piloto(s) acima uma vez para o backend persistir os caminhos.`,
        );
      }

      // Etapa 3 — monta DadosSessao a partir da resposta do processamento (fonte da verdade).
      // Quando processamento foi pulado (pilotos já processados), cai nos GETs que varrem disco.
      let pilotosComArquivos: PilotoComArquivos[];
      let tracadoIdealUrl: string | null = null;
      let tracadoIdealCsvUrl: string | null = null;
      let csvGeralUrl: string | null = null;

      if (respProc) {
        tracadoIdealUrl    = respProc.tracado_ideal_url;
        tracadoIdealCsvUrl = respProc.tracado_ideal_csv;
        csvGeralUrl        = respProc.csv_geral_url;
        const mapa = new Map(respProc.pilotos.map(p => [p.nome, p]));
        // Fallback: para pilotos validos que nao apareceram em respProc.pilotos,
        // varre disco via /api/pilotos/<nome>/arquivos para pegar PNGs/PDF/CSV antigos.
        pilotosComArquivos = await Promise.all(
          pilotosValidos.map(async p => {
            const nome = p.nome.trim();
            const r = mapa.get(nome);
            if (r) {
              return {
                nome,
                arquivos: { graficos: r.graficos, relatorio_pdf: r.relatorio_pdf, csv: r.csv },
              };
            }
            console.log(`[handleVisualizar] ${nome} ausente do payload — buscando arquivos antigos via API.`);
            const arquivos = await buscarArquivosPiloto(nome).catch(() => ({
              graficos: [], relatorio_pdf: null, csv: null,
            }));
            return { nome, arquivos };
          }),
        );
      } else {
        pilotosComArquivos = await Promise.all(
          pilotosValidos.map(async p => ({
            nome:     p.nome.trim(),
            arquivos: await buscarArquivosPiloto(p.nome.trim()),
          })),
        );
        const [tIdeal, tIdealCsv, csvG] = await Promise.all([
          buscarTracadoIdeal().catch(() => ({ url: null })),
          buscarTracadoIdealCsv().catch(() => ({ url: null })),
          buscarCsvGeral().catch(() => ({ url: null })),
        ]);
        tracadoIdealUrl    = tIdeal.url;
        tracadoIdealCsvUrl = tIdealCsv.url;
        csvGeralUrl        = csvG.url;
      }

      const dadosFinais = {
        sessaoNome:         nomeSessao,
        tracadoIdealUrl,
        tracadoIdealCsvUrl,
        csvGeralUrl,
        pilotos:            pilotosComArquivos,
      };
      console.log('[handleVisualizar] indo para tela 2 com:', dadosFinais);
      onVisualizar(dadosFinais);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Erro desconhecido';
      setErro(`Erro ao processar: ${msg}. Verifique se o servidor está rodando.`);
    } finally {
      setFase('idle');
    }
  };

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------

  return (
    <Tooltip.Provider>
      <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 p-6">
        <div className="max-w-6xl mx-auto">
          <div className="bg-white rounded-2xl shadow-2xl p-8">

            {/* Cabeçalho */}
            <div className="flex justify-between items-center mb-8">
              <div>
                <h1 className="text-3xl font-bold text-gray-800">Cadastro de Dados</h1>
                <p className="text-gray-600">Inserção de informações para análise</p>
              </div>
              <button
                onClick={adicionarPiloto}
                className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg font-medium flex items-center gap-2 transition-colors"
              >
                <Plus size={20} />
                Novo Piloto
              </button>
            </div>

            {erro && (
              <div className="mb-6 flex items-center gap-3 bg-red-50 border border-red-200 text-red-700 rounded-lg p-4">
                <AlertTriangle size={20} className="shrink-0" />
                <span>{erro}</span>
              </div>
            )}

            <div className="space-y-8">

              {/* ── Sessão ─────────────────────────────────────────────── */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Sessão</label>
                {!mostrarNovaSessao ? (
                  <select
                    value={sessao ?? ''}
                    onChange={e => handleSessaoChange(e.target.value)}
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent bg-white"
                  >
                    <option value="">Selecione uma sessão</option>
                    {sessoesDisponiveis.map(s => (
                      <option key={s.id} value={s.nome}>{s.nome}</option>
                    ))}
                    <option value="nova">+ Cadastrar Nova Sessão</option>
                  </select>
                ) : (
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={novaSessao ?? ''}
                      onChange={e => setNovaSessao(e.target.value)}
                      className="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                      placeholder="Digite o nome da nova sessão"
                    />
                    <button
                      onClick={handleSalvarNovaSessao}
                      className="px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg font-medium"
                    >
                      Salvar
                    </button>
                    <button
                      onClick={() => { setMostrarNovaSessao(false); setNovaSessao(''); }}
                      className="px-4 py-2 bg-gray-300 hover:bg-gray-400 text-gray-800 rounded-lg font-medium"
                    >
                      Cancelar
                    </button>
                  </div>
                )}
              </div>

              {/* ── Pilotos ────────────────────────────────────────────── */}
              <div className="space-y-4">
                {pilotos.map((piloto, index) => {
                  const previewUrl = drivePreviewUrl(piloto.linkVideo);

                  // Prioridade do dropdown: MoTeC > Banco > Fallback 1-10
                  const temVoltasMotec = piloto.voltasMotec.length > 0;
                  const temVoltasBanco = piloto.voltasDisponiveis.length > 0;

                  return (
                    <div
                      key={piloto.id}
                      className="bg-gradient-to-r from-indigo-50 to-purple-50 rounded-xl border-2 border-indigo-200"
                    >
                      {/* Cabeçalho do card */}
                      <div
                        className="flex items-center justify-between p-4 cursor-pointer"
                        onClick={() => togglePiloto(piloto.id)}
                      >
                        <div className="flex items-center gap-3">
                          <div className="p-2 bg-indigo-100 rounded-lg">
                            <User className="text-indigo-600" size={24} />
                          </div>
                          <h3 className="text-lg font-semibold text-gray-800">
                            Piloto {index + 1}{piloto.nome && ` — ${piloto.nome}`}
                          </h3>
                        </div>
                        <div className="flex items-center gap-2">
                          {pilotos.length > 1 && (
                            <button
                              onClick={e => { e.stopPropagation(); removerPiloto(piloto.id); }}
                              className="p-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                            >
                              <Trash2 size={20} />
                            </button>
                          )}
                          {piloto.expandido ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
                        </div>
                      </div>

                      {piloto.expandido && (
                        <div className="p-6 pt-0 space-y-6">

                          {/* Nome */}
                          <div>
                            <label className="block text-sm font-medium text-gray-700 mb-2">
                              Nome do Piloto
                            </label>
                            {!modoNovoPiloto[piloto.id] ? (
                              /* Dropdown de pilotos existentes */
                              <select
                                value={piloto.nome ?? ''}
                                onChange={e => {
                                  const val = e.target.value;
                                  if (val === '__novo__') {
                                    setModoNovoPiloto(prev => ({ ...prev, [piloto.id]: true }));
                                    atualizarPiloto(piloto.id, { nome: '', jaExiste: null });
                                  } else {
                                    handleNomePiloto(piloto.id, val);
                                  }
                                }}
                                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent bg-white"
                              >
                                <option value="">Selecione um piloto</option>
                                {pilotosDisponiveis.map(p => (
                                  <option key={p.id} value={p.nome}>{p.nome}</option>
                                ))}
                                <option value="__novo__">+ Cadastrar Novo Piloto</option>
                              </select>
                            ) : (
                              /* Modo digitação livre para novo piloto */
                              <div className="flex gap-2">
                                <input
                                  type="text"
                                  value={piloto.nome ?? ''}
                                  onChange={e => handleNomePiloto(piloto.id, e.target.value)}
                                  autoFocus
                                  className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                                  placeholder="Digite o nome do novo piloto"
                                />
                                <button
                                  type="button"
                                  onClick={() => {
                                    setModoNovoPiloto(prev => ({ ...prev, [piloto.id]: false }));
                                    atualizarPiloto(piloto.id, { nome: '', jaExiste: null });
                                  }}
                                  className="px-3 py-2 bg-gray-200 hover:bg-gray-300 text-gray-700 rounded-lg text-sm font-medium"
                                >
                                  Cancelar
                                </button>
                              </div>
                            )}
                            {piloto.jaExiste === true && !piloto.dadosIncompletos && (
                              <div className="mt-2 flex items-center gap-2 bg-yellow-50 border border-yellow-300 text-yellow-800 rounded-lg px-3 py-2 text-sm">
                                <CheckCircle size={16} className="text-yellow-600 shrink-0" />
                                Piloto já cadastrado — dados preenchidos automaticamente com o último registro.
                              </div>
                            )}
                            {piloto.dadosIncompletos && (
                              <div className="mt-2 flex items-center gap-2 bg-amber-50 border border-amber-300 text-amber-800 rounded-lg px-3 py-2 text-sm">
                                <AlertTriangle size={16} className="text-amber-600 shrink-0" />
                                Cadastro incompleto — preencha os campos da volta de ouro abaixo e clique em
                                "Processar e Visualizar" para atualizar.
                              </div>
                            )}
                          </div>

                          {/* Upload CSV */}
                          <div>
                            <div className="flex items-center gap-2 mb-3">
                              <label className="text-sm font-medium text-gray-700">
                                Upload de Arquivos CSV
                              </label>
                              {piloto.jaExiste === true ? (
                                <span className="text-xs text-blue-600 font-medium bg-blue-50 border border-blue-200 px-2 py-0.5 rounded-full">
                                  opcional — apenas para substituir dados existentes
                                </span>
                              ) : piloto.jaExiste === false ? (
                                <span className="text-xs text-red-600 font-medium bg-red-50 border border-red-200 px-2 py-0.5 rounded-full">
                                  obrigatório
                                </span>
                              ) : null}
                            </div>
                            <div className="grid md:grid-cols-3 gap-3">
                              {(['csvPupil', 'csvMotec', 'csvFixations'] as const).map(campo => {
                                const labels: Record<string, string> = {
                                  csvPupil:     'Pupil',
                                  csvMotec:     'MoTeC',
                                  csvFixations: 'Fixations',
                                };
                                const arquivo = piloto[campo];
                                const isMotec = campo === 'csvMotec';

                                return (
                                  <label key={campo} className="cursor-pointer">
                                    <input
                                      type="file"
                                      accept=".csv"
                                      onChange={e => {
                                        const file = e.target.files?.[0] || null;
                                        if (isMotec) {
                                          handleMotecUpload(piloto.id, file);
                                        } else {
                                          atualizarPiloto(piloto.id, { [campo]: file });
                                        }
                                      }}
                                      className="hidden"
                                    />
                                    <div
                                      className={`border-2 border-dashed rounded-lg p-4 text-center transition-all ${
                                        arquivo
                                          ? 'border-green-400 bg-green-50'
                                          : 'border-gray-300 hover:border-indigo-400'
                                      }`}
                                    >
                                      {isMotec && piloto.carregandoVoltas ? (
                                        <Loader2 className="mx-auto mb-2 text-indigo-500 animate-spin" size={24} />
                                      ) : (
                                        <Upload
                                          className={`mx-auto mb-2 ${arquivo ? 'text-green-600' : 'text-gray-400'}`}
                                          size={24}
                                        />
                                      )}
                                      <p className="text-sm font-medium text-gray-700">{labels[campo]}</p>
                                      {arquivo && (
                                        <p className="text-xs text-green-600 mt-1 truncate">{arquivo.name}</p>
                                      )}
                                      {isMotec && temVoltasMotec && (
                                        <p className="text-xs text-indigo-600 mt-1">
                                          {piloto.voltasMotec.length} volta{piloto.voltasMotec.length !== 1 ? 's' : ''} detectada{piloto.voltasMotec.length !== 1 ? 's' : ''}
                                        </p>
                                      )}
                                    </div>
                                  </label>
                                );
                              })}
                            </div>
                          </div>

                          {/* Vídeo — obrigatório para novo piloto, opcional para existente */}
                          <div className="bg-gray-50 rounded-xl p-6">
                            <div className="flex items-center gap-2 mb-4">
                              <h3 className="text-lg font-semibold text-gray-800">Vídeo da Sessão</h3>
                              {piloto.jaExiste === true && (
                                <span className="text-xs text-blue-600 font-medium bg-blue-50 border border-blue-200 px-2 py-0.5 rounded-full">
                                  opcional
                                </span>
                              )}
                              {piloto.jaExiste === false && (
                                <span className="text-xs text-red-600 font-medium bg-red-50 border border-red-200 px-2 py-0.5 rounded-full">
                                  necessário para anotar frames
                                </span>
                              )}
                            </div>
                            <div className="space-y-4">
                              <div>
                                <div className="flex items-center gap-2 mb-2">
                                  <label className="text-sm font-medium text-gray-700">
                                    Link do Vídeo no Drive
                                  </label>
                                  <Tooltip.Root>
                                    <Tooltip.Trigger asChild>
                                      <button className="text-indigo-600 hover:text-indigo-700"><Info size={16} /></button>
                                    </Tooltip.Trigger>
                                    <Tooltip.Portal>
                                      <Tooltip.Content className="bg-gray-900 text-white px-3 py-2 rounded-lg text-sm max-w-xs" sideOffset={5}>
                                        Lembre-se de deixar o vídeo público para qualquer pessoa com o link
                                        <Tooltip.Arrow className="fill-gray-900" />
                                      </Tooltip.Content>
                                    </Tooltip.Portal>
                                  </Tooltip.Root>
                                </div>
                                <input
                                  type="text"
                                  value={piloto.linkVideo ?? ''}
                                  onChange={e => atualizarPiloto(piloto.id, { linkVideo: e.target.value, videoCarregado: false })}
                                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                                  placeholder="https://drive.google.com/..."
                                />
                              </div>

                              {previewUrl ? (
                                <div className="rounded-lg overflow-hidden aspect-video bg-black">
                                  <iframe
                                    src={previewUrl}
                                    className="w-full h-full"
                                    allow="autoplay"
                                    onLoad={() => atualizarPiloto(piloto.id, { videoCarregado: true })}
                                    title={`Vídeo — Piloto ${index + 1}`}
                                  />
                                </div>
                              ) : piloto.jaExiste === false ? (
                                /* Novo piloto: mostra placeholder como instrução */
                                <div className="bg-black rounded-lg overflow-hidden aspect-video flex items-center justify-center">
                                  <p className="text-gray-500 text-sm">
                                    Cole o link do Drive acima para visualizar o vídeo e anotar os frames
                                  </p>
                                </div>
                              ) : null}
                            </div>
                          </div>

                          {/* Fixações + Volta de Ouro — aparecem após vídeo carregar */}
                          {/* Fixações + Volta de Ouro — sempre visíveis */}
                          <>
                              {/* Fixações (Marco Zero) */}
                              <div className="bg-blue-50 rounded-xl p-6 border-2 border-blue-200">
                                <div className="flex items-center gap-2 mb-3">
                                  <h3 className="text-lg font-semibold text-gray-800">Fixações</h3>
                                  <Tooltip.Root>
                                    <Tooltip.Trigger asChild>
                                      <button className="text-blue-600 hover:text-blue-700"><Info size={16} /></button>
                                    </Tooltip.Trigger>
                                    <Tooltip.Portal>
                                      <Tooltip.Content className="bg-gray-900 text-white px-3 py-2 rounded-lg text-sm max-w-xs" sideOffset={5}>
                                        Inserir fixação ao passar pela linha de largada
                                        <Tooltip.Arrow className="fill-gray-900" />
                                      </Tooltip.Content>
                                    </Tooltip.Portal>
                                  </Tooltip.Root>
                                </div>
                                <input
                                  type="text"
                                  value={piloto.fixacoes ?? ''}
                                  onChange={e => atualizarPiloto(piloto.id, { fixacoes: e.target.value })}
                                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                                  placeholder="Frame do Marco Zero (ex: 1135)"
                                />
                              </div>

                              {/* Volta de Ouro */}
                              <div className="bg-purple-50 rounded-xl p-6 border-2 border-purple-200">
                                <h3 className="text-lg font-semibold text-gray-800 mb-4">Volta de Ouro</h3>
                                <div className="space-y-4">

                                  {/* Fixação Inicial (Pupil) */}
                                  <div>
                                    <div className="flex items-center gap-2 mb-2">
                                      <label className="text-sm font-medium text-gray-700">Fixação Inicial (Pupil)</label>
                                      <Tooltip.Root>
                                        <Tooltip.Trigger asChild>
                                          <button className="text-purple-600 hover:text-purple-700"><Info size={16} /></button>
                                        </Tooltip.Trigger>
                                        <Tooltip.Portal>
                                          <Tooltip.Content className="bg-gray-900 text-white px-3 py-2 rounded-lg text-sm max-w-xs" sideOffset={5}>
                                            Frame do Pupil Player ao passar pela linha de largada desta volta
                                            <Tooltip.Arrow className="fill-gray-900" />
                                          </Tooltip.Content>
                                        </Tooltip.Portal>
                                      </Tooltip.Root>
                                    </div>
                                    <input
                                      type="text"
                                      value={piloto.fixacaoInicial ?? ''}
                                      onChange={e => atualizarPiloto(piloto.id, { fixacaoInicial: e.target.value })}
                                      className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                                      placeholder="Ex: 1135"
                                    />
                                  </div>

                                  {/* Fixação Final (Pupil) */}
                                  <div>
                                    <div className="flex items-center gap-2 mb-2">
                                      <label className="text-sm font-medium text-gray-700">Fixação Final (Pupil)</label>
                                      <Tooltip.Root>
                                        <Tooltip.Trigger asChild>
                                          <button className="text-purple-600 hover:text-purple-700"><Info size={16} /></button>
                                        </Tooltip.Trigger>
                                        <Tooltip.Portal>
                                          <Tooltip.Content className="bg-gray-900 text-white px-3 py-2 rounded-lg text-sm max-w-xs" sideOffset={5}>
                                            Frame do Pupil Player ao passar pela linha de chegada desta volta
                                            <Tooltip.Arrow className="fill-gray-900" />
                                          </Tooltip.Content>
                                        </Tooltip.Portal>
                                      </Tooltip.Root>
                                    </div>
                                    <input
                                      type="text"
                                      value={piloto.fixacaoFinal ?? ''}
                                      onChange={e => atualizarPiloto(piloto.id, { fixacaoFinal: e.target.value })}
                                      className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                                      placeholder="Ex: 1668"
                                    />
                                  </div>

                                  {/* Identificação da Volta */}
                                  <div>
                                    <div className="flex items-center gap-2 mb-2">
                                      <label className="text-sm font-medium text-gray-700">
                                        Identificação da Volta
                                      </label>
                                      {piloto.carregandoVoltas && (
                                        <Loader2 size={14} className="text-indigo-500 animate-spin" />
                                      )}
                                      {temVoltasMotec && (
                                        <span className="text-xs text-green-600 font-medium">
                                          ✓ voltas do MoTeC
                                        </span>
                                      )}
                                    </div>
                                    <select
                                      value={piloto.identificacaoVolta ?? ''}
                                      onChange={e =>
                                        handleIdentificacaoVolta(piloto.id, e.target.value, piloto.voltasMotec)
                                      }
                                      className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent bg-white"
                                    >
                                      {temVoltasMotec ? (
                                        // Prioridade 1: voltas detectadas no CSV do MoTeC
                                        piloto.voltasMotec.map(v => (
                                          <option key={v.numero_volta} value={v.numero_volta}>
                                            Volta {v.numero_volta} — {v.duracao.toFixed(1)}s
                                          </option>
                                        ))
                                      ) : temVoltasBanco ? (
                                        // Prioridade 2: voltas do banco (piloto já existente)
                                        piloto.voltasDisponiveis.map(v => (
                                          <option key={v.numero_volta} value={v.numero_volta}>
                                            Volta {v.numero_volta}{v.eh_volta_ouro ? ' ★' : ''}
                                          </option>
                                        ))
                                      ) : (
                                        // Fallback: 1-10
                                        [1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map(n => (
                                          <option key={n} value={n}>Volta {n}</option>
                                        ))
                                      )}
                                    </select>
                                  </div>

                                  {/* MoTeC Inicial */}
                                  <div>
                                    <div className="flex items-center gap-2 mb-2">
                                      <label className="text-sm font-medium text-gray-700">MoTeC Inicial (s)</label>
                                      <Tooltip.Root>
                                        <Tooltip.Trigger asChild>
                                          <button className="text-purple-600 hover:text-purple-700"><Info size={16} /></button>
                                        </Tooltip.Trigger>
                                        <Tooltip.Portal>
                                          <Tooltip.Content className="bg-gray-900 text-white px-3 py-2 rounded-lg text-sm max-w-xs" sideOffset={5}>
                                            Preenchido automaticamente ao selecionar a volta no MoTeC CSV
                                            <Tooltip.Arrow className="fill-gray-900" />
                                          </Tooltip.Content>
                                        </Tooltip.Portal>
                                      </Tooltip.Root>
                                    </div>
                                    <input
                                      type="text"
                                      value={piloto.motecIni ?? ''}
                                      readOnly={!piloto.dadosIncompletos}
                                      onChange={
                                        piloto.dadosIncompletos
                                          ? e => atualizarPiloto(piloto.id, { motecIni: e.target.value })
                                          : undefined
                                      }
                                      className={`w-full px-4 py-2 border rounded-lg ${
                                        piloto.dadosIncompletos
                                          ? 'border-amber-300 focus:ring-2 focus:ring-amber-500 focus:border-transparent'
                                          : 'border-gray-200 bg-gray-50 text-gray-600 cursor-not-allowed select-none'
                                      }`}
                                      placeholder={
                                        piloto.dadosIncompletos
                                          ? 'Digite manualmente — cadastro estava incompleto'
                                          : 'Selecionado automaticamente pelo CSV MoTeC'
                                      }
                                    />
                                  </div>

                                  {/* MoTeC Final */}
                                  <div>
                                    <div className="flex items-center gap-2 mb-2">
                                      <label className="text-sm font-medium text-gray-700">MoTeC Final (s)</label>
                                      <Tooltip.Root>
                                        <Tooltip.Trigger asChild>
                                          <button className="text-purple-600 hover:text-purple-700"><Info size={16} /></button>
                                        </Tooltip.Trigger>
                                        <Tooltip.Portal>
                                          <Tooltip.Content className="bg-gray-900 text-white px-3 py-2 rounded-lg text-sm max-w-xs" sideOffset={5}>
                                            Preenchido automaticamente ao selecionar a volta no MoTeC CSV
                                            <Tooltip.Arrow className="fill-gray-900" />
                                          </Tooltip.Content>
                                        </Tooltip.Portal>
                                      </Tooltip.Root>
                                    </div>
                                    <input
                                      type="text"
                                      value={piloto.motecFim ?? ''}
                                      readOnly={!piloto.dadosIncompletos}
                                      onChange={
                                        piloto.dadosIncompletos
                                          ? e => atualizarPiloto(piloto.id, { motecFim: e.target.value })
                                          : undefined
                                      }
                                      className={`w-full px-4 py-2 border rounded-lg ${
                                        piloto.dadosIncompletos
                                          ? 'border-amber-300 focus:ring-2 focus:ring-amber-500 focus:border-transparent'
                                          : 'border-gray-200 bg-gray-50 text-gray-600 cursor-not-allowed select-none'
                                      }`}
                                      placeholder={
                                        piloto.dadosIncompletos
                                          ? 'Digite manualmente — cadastro estava incompleto'
                                          : 'Selecionado automaticamente pelo CSV MoTeC'
                                      }
                                    />
                                  </div>

                                </div>
                              </div>
                            </>

                        </div>
                      )}
                    </div>
                  );
                })}
              </div>

              {/* Aviso só para pilotos NOVOS (sem CSVs salvos no banco) que ainda
                  não subiram os arquivos. Pilotos existentes sem upload são OK
                  porque o backend lê do disco via caminho_pupil/caminho_motec. */}
              {pilotos.some(p => p.nome.trim() && !p.temCsvsSalvos && !(p.csvPupil && p.csvMotec)) && (
                <div className="flex items-start gap-3 bg-amber-50 border border-amber-200 text-amber-800 rounded-lg p-4 text-sm">
                  <AlertTriangle size={18} className="shrink-0 mt-0.5 text-amber-500" />
                  <span>
                    <strong>Atenção:</strong> pilotos novos precisam dos CSVs de{' '}
                    <strong>Pupil</strong> e <strong>MoTeC</strong> para gerar gráficos e relatórios.
                  </span>
                </div>
              )}

              {/* Botão principal */}
              {(() => {
                const temCsvParaProcessar = pilotos.some(
                  p => p.nome.trim() && p.csvPupil && p.csvMotec,
                );
                return (
                  <button
                    onClick={handleVisualizar}
                    disabled={fase !== 'idle'}
                    className="w-full py-4 bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-400 disabled:cursor-not-allowed text-white rounded-xl font-semibold text-lg flex items-center justify-center gap-2 transition-all shadow-lg hover:shadow-xl mt-8"
                  >
                    {fase === 'salvando' && (
                      <>
                        <svg className="animate-spin h-6 w-6 text-white" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                        </svg>
                        Salvando...
                      </>
                    )}
                    {fase === 'processando' && (
                      <>
                        <svg className="animate-spin h-6 w-6 text-white" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                        </svg>
                        Processando dados...
                      </>
                    )}
                    {fase === 'idle' && (
                      <>
                        <Eye size={24} />
                        {temCsvParaProcessar ? 'Processar e Visualizar' : 'Visualizar resultados existentes'}
                      </>
                    )}
                  </button>
                );
              })()}

            </div>
          </div>
        </div>
      </div>
    </Tooltip.Provider>
  );
}
