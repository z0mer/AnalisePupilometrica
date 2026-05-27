const BASE = 'http://localhost:8000';

// ---------------------------------------------------------------------------
// Interfaces
// ---------------------------------------------------------------------------

export interface Sessao {
  id: string;
  nome: string;
}

export interface PilotoExistente {
  id: string;
  nome: string;
  frame_sync: number | null;
  frame_ini_pupil: number | null;
  frame_fim_pupil: number | null;
  t_ini_motec_s: number | null;
  t_fim_motec_s: number | null;
  numero_volta: number;
  tem_csvs_salvos: boolean;
}

/** Volta vinda do banco de dados (via GET /api/pilotos/:nome/voltas) */
export interface VoltaPiloto {
  numero_volta: number;
  eh_volta_ouro: boolean;
}

/** Volta detectada no CSV do MoTeC (via POST /api/listar-voltas-motec) */
export interface VoltaMotec {
  numero_volta: number;
  t_ini: number;
  t_fim: number;
  duracao: number;
}

/** Resposta do endpoint /api/listar-voltas-motec */
export interface VoltasMotecResponse {
  voltas: VoltaMotec[];
  /** Tempo do MoTeC no Marco Zero (primeira queda de Car Pos Norm).
   *  Persistido em parametros_sync.t_sync_motec_s para alinhar MoTeC ↔ Pupil. */
  t_sync_motec_s: number | null;
}

export interface CadastroPayload {
  sessao_nome: string;
  piloto_nome: string;
  frame_sync: number | null;
  /** Marco Zero do MoTeC — vem de listarVoltasMotec.t_sync_motec_s */
  t_sync_motec_s: number | null;
  frame_ini_pupil: number | null;
  frame_fim_pupil: number | null;
  t_ini_motec_s: number | null;
  t_fim_motec_s: number | null;
  numero_volta: number;
}

export interface CadastroResposta {
  sessao_id: string;
  piloto_id: string;
  volta_id: string;
  ja_existia: boolean;
}

export interface ArquivosPiloto {
  graficos: string[];
  relatorio_pdf: string | null;
  csv: string | null;
}

// ---------------------------------------------------------------------------
// Sessões
// ---------------------------------------------------------------------------

export async function listarSessoes(): Promise<Sessao[]> {
  const res = await fetch(`${BASE}/api/sessoes`);
  if (!res.ok) throw new Error('Erro ao listar sessões');
  return res.json();
}

export async function criarSessao(nome: string): Promise<Sessao> {
  const res = await fetch(`${BASE}/api/sessoes`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ nome }),
  });
  if (!res.ok) throw new Error('Erro ao criar sessão');
  return res.json();
}

// ---------------------------------------------------------------------------
// Pilotos
// ---------------------------------------------------------------------------

export async function listarPilotos(): Promise<{ id: string; nome: string }[]> {
  const res = await fetch(`${BASE}/api/pilotos/lista`);
  if (!res.ok) throw new Error('Erro ao listar pilotos');
  return res.json();
}

export interface StatusPiloto {
  existe: boolean;
  processado: boolean;
  voltas?: number;
  anomalias?: number;
}

export async function getStatusPiloto(nome: string): Promise<StatusPiloto> {
  const res = await fetch(`${BASE}/api/pilotos/${encodeURIComponent(nome)}/status`);
  if (!res.ok) return { existe: false, processado: false };
  return res.json();
}

export async function buscarPiloto(nome: string): Promise<PilotoExistente | null> {
  const res = await fetch(`${BASE}/api/pilotos?nome=${encodeURIComponent(nome)}`);
  if (res.status === 404) return null;
  if (!res.ok) throw new Error('Erro ao buscar piloto');
  return res.json();
}

export async function listarVoltasPiloto(nome: string): Promise<VoltaPiloto[]> {
  const res = await fetch(`${BASE}/api/pilotos/${encodeURIComponent(nome)}/voltas`);
  if (res.status === 404) return [];
  if (!res.ok) throw new Error('Erro ao listar voltas do piloto');
  return res.json();
}

export async function buscarArquivosPiloto(nome: string): Promise<ArquivosPiloto> {
  const res = await fetch(`${BASE}/api/pilotos/${encodeURIComponent(nome)}/arquivos`);
  if (!res.ok) throw new Error('Erro ao buscar arquivos do piloto');
  return res.json();
}

// ---------------------------------------------------------------------------
// Cadastro
// ---------------------------------------------------------------------------

export async function cadastrar(dados: CadastroPayload): Promise<CadastroResposta> {
  const res = await fetch(`${BASE}/api/cadastro`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(dados),
  });
  if (!res.ok) throw new Error('Erro ao cadastrar dados');
  return res.json();
}

// ---------------------------------------------------------------------------
// Processamento de sessão
// ---------------------------------------------------------------------------

export interface PilotoProcessado {
  nome: string;
  graficos: string[];
  relatorio_pdf: string | null;
  csv: string | null;
}

export interface PilotoPulado {
  nome: string;
  motivo: string;
}

export interface ProcessarSessaoResposta {
  sessao: string;
  pilotos_processados: number;
  pilotos_pulados: PilotoPulado[];
  tracado_ideal_url: string | null;
  tracado_ideal_csv: string | null;
  graficos_voltas: string[];
  total_anomalias: number;
  csv_geral_url: string | null;
  pilotos: PilotoProcessado[];
}

/**
 * Envia os CSVs de cada piloto + parâmetros de sincronização (frames, tempos)
 * como listas paralelas no FormData. A requisição é self-contained: o backend
 * persiste esses valores antes de validar, eliminando dependência de cadastro
 * prévio. String vazia = null.
 */
export async function processarSessao(
  sessaoNome: string,
  pilotos: Array<{
    nome: string;
    pupilCsv: File | null;
    motecCsv: File | null;
    fixacoesCsv?: File | null;
    frame_sync: number | null;
    frame_ini_pupil: number | null;
    frame_fim_pupil: number | null;
    t_ini_motec_s: number | null;
    t_fim_motec_s: number | null;
    numero_volta: number;
  }>,
): Promise<ProcessarSessaoResposta> {
  const form = new FormData();
  form.append('sessao_nome', sessaoNome);
  // Pilotos sem upload novo dependem de _resolver_bytes_csv lendo do disco no
  // backend. Para isso funcionar com listas paralelas posicionais, o caller
  // deve enviar primeiro os pilotos COM upload e depois os sem — o backend
  // detecta `i >= len(files)` e cai no caminho do disco.
  pilotos.forEach(p => {
    form.append('piloto_nomes', p.nome);
    if (p.pupilCsv) form.append('pupil_csvs', p.pupilCsv);
    if (p.motecCsv) form.append('motec_csvs', p.motecCsv);
    if (p.fixacoesCsv) form.append('fixacoes_csvs', p.fixacoesCsv);
    form.append('frame_syncs',        p.frame_sync      == null ? '' : String(p.frame_sync));
    form.append('frame_ini_pupils',   p.frame_ini_pupil == null ? '' : String(p.frame_ini_pupil));
    form.append('frame_fim_pupils',   p.frame_fim_pupil == null ? '' : String(p.frame_fim_pupil));
    form.append('t_ini_motec_s_list', p.t_ini_motec_s   == null ? '' : String(p.t_ini_motec_s));
    form.append('t_fim_motec_s_list', p.t_fim_motec_s   == null ? '' : String(p.t_fim_motec_s));
    form.append('numero_voltas',      String(p.numero_volta));
  });
  const res = await fetch(`${BASE}/api/processar/sessao`, {
    method: 'POST',
    body: form,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const detail = body?.detail;
    let msg: string;
    if (typeof detail === 'string') {
      msg = detail;
    } else if (detail && typeof detail === 'object') {
      const pulados = (detail.pilotos_pulados ?? []) as Array<{ nome: string; motivo: string }>;
      const linhas = pulados.map(p => `• ${p.nome}: ${p.motivo}`).join('\n');
      msg = `${detail.mensagem ?? 'Erro ao processar sessão'}${linhas ? '\n' + linhas : ''}`;
    } else {
      msg = 'Erro ao processar sessão';
    }
    throw new Error(msg);
  }
  const data = await res.json();
  console.log('[processarSessao] resposta:', data);
  return data;
}

// ---------------------------------------------------------------------------
// MoTeC
// ---------------------------------------------------------------------------

/**
 * Envia o CSV do MoTeC para o backend e recebe a lista de voltas
 * com seus limites de tempo (ignora volta 0 e última volta).
 */
export async function listarVoltasMotec(motecCsv: File): Promise<VoltasMotecResponse> {
  const form = new FormData();
  form.append('motec_csv', motecCsv);
  const res = await fetch(`${BASE}/api/listar-voltas-motec`, {
    method: 'POST',
    body: form,
  });
  if (!res.ok) throw new Error('Erro ao analisar CSV do MoTeC');
  return res.json();
}

// ---------------------------------------------------------------------------
// Utilitários
// ---------------------------------------------------------------------------

export async function buscarTracadoIdeal(): Promise<{ url: string | null }> {
  const res = await fetch(`${BASE}/api/tracado-ideal`);
  if (!res.ok) throw new Error('Erro ao buscar traçado ideal');
  return res.json();
}

export async function buscarTracadoIdealCsv(): Promise<{ url: string | null }> {
  const res = await fetch(`${BASE}/api/tracado-ideal-csv`);
  if (!res.ok) throw new Error('Erro ao buscar CSV do traçado ideal');
  return res.json();
}

export async function buscarCsvGeral(): Promise<{ url: string | null }> {
  const res = await fetch(`${BASE}/api/csv-geral`);
  if (!res.ok) throw new Error('Erro ao buscar CSV geral');
  return res.json();
}

export function urlCompleta(path: string): string {
  return `${BASE}${path}`;
}
