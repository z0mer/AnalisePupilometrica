# Análise Pupilométrica — Como rodar

Este repositório contém dois projetos principais:

- Backend (API e scripts): `AnalisePupilometricaBackend`
- Frontend (React + Vite): `AnalisePupilometricaFrontend`

**Pré-requisitos**

- Python 3.10+ com `venv` disponível
- Node.js 18+ e `npm` ou `pnpm`
- `iconv` (opcional, para converter `requirements.txt` se necessário)

**Backend — instruções rápidas**

1. Abra um terminal na raiz do repositório e entre na pasta do backend:

```bash
cd AnalisePupilometricaBackend
```

2. Crie e ative um ambiente virtual:

```bash
python -m venv .venv
source .venv/bin/activate
```

3. O arquivo `requirements.txt` foi salvo em UTF-16 em alguns casos. Se o `pip install -r requirements.txt` falhar por causa de codificação, converta antes:

```bash
iconv -f utf-16 -t utf-8 requirements.txt > req-utf8.txt
pip install -r req-utf8.txt
# ou, se não precisar de conversão:
pip install -r requirements.txt
```

4. Crie um arquivo `.env` contendo a variável `DATABASE_URL`. Para testes locais simples, use SQLite:

```bash
echo "DATABASE_URL=sqlite:///./analise.db" > .env
```

5. Rodando a API (FastAPI + Uvicorn):

```bash
# a partir da pasta AnalisePupilometricaBackend
uvicorn backend.api:app --reload --host 127.0.0.1 --port 8000
```

- A documentação Swagger ficará disponível em: http://127.0.0.1:8000/docs
- Se preferir rodar apenas os scripts CLI (análises), execute o menu:

```bash
python main.py
```

**Frontend — instruções rápidas**

1. Abra um terminal e entre na pasta do frontend:

```bash
cd AnalisePupilometricaFrontend
```

2. Instale dependências (recomendo `pnpm`, mas `npm` também funciona):

```bash
# com pnpm
pnpm install
# ou com npm
npm install
```

3. Iniciar servidor de desenvolvimento (Vite):

```bash
pnpm exec vite
# ou
npx vite
```

- O endereço será mostrado no terminal (geralmente http://127.0.0.1:5173).
- Para build de produção:

```bash
pnpm run build
# ou
npm run build
```

**Observações importantes**

- A API adiciona CORS permitindo `http://localhost:5173` e `http://localhost:3000`.
- Se usar PostgreSQL/Neon, configure `DATABASE_URL` corretamente no `.env` (ex.: `postgresql://user:pass@host:port/dbname`). O `database.py` ajusta a URL para `psycopg2` automaticamente.
- A pasta `saidas/` é usada pelo backend para arquivos estáticos gerados; a API serve esses arquivos em `/static`.

**Verificação rápida**

- Backend: acesse `http://127.0.0.1:8000/docs` e verifique os endpoints.
- Frontend: abra o endereço do Vite (geralmente `http://127.0.0.1:5173`) e navegue pela aplicação.

Se quiser, posso:

- Executar um teste simples de um endpoint (ex.: listar pilotos).
- Adicionar scripts `dev` ao `package.json` do frontend para facilitar o `pnpm run dev`.
