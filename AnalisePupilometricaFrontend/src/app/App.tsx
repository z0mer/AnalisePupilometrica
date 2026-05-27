import { useState } from 'react';
import { FormularioDados } from './components/FormularioDados';
import { VisualizacaoTracado } from './components/VisualizacaoTracado';
import type { ArquivosPiloto } from '../lib/api';

type Tela = 'formulario' | 'visualizacao';

export interface PilotoComArquivos {
  nome: string;
  arquivos: ArquivosPiloto;
}

export interface DadosSessao {
  sessaoNome: string;
  tracadoIdealUrl: string | null;
  tracadoIdealCsvUrl: string | null;
  csvGeralUrl: string | null;
  pilotos: PilotoComArquivos[];
}

export default function App() {
  const [telaAtual, setTelaAtual] = useState<Tela>('formulario');
  const [dadosSessao, setDadosSessao] = useState<DadosSessao | null>(null);

  return (
    <div className="size-full">
      {telaAtual === 'formulario' && (
        <FormularioDados
          onVisualizar={(dados) => {
            setDadosSessao(dados);
            setTelaAtual('visualizacao');
          }}
        />
      )}
      {telaAtual === 'visualizacao' && dadosSessao && (
        <VisualizacaoTracado
          dadosSessao={dadosSessao}
          onVoltar={() => setTelaAtual('formulario')}
        />
      )}
    </div>
  );
}
