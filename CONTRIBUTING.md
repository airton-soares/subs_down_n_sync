# Como contribuir

Obrigado pelo interesse! Veja como começar.

## Reportar um bug

Abra uma [issue](https://github.com/airton-soares/subs_down_n_sync/issues/new?template=bug_report.yml) descrevendo o problema.

## Sugerir uma feature

Abra uma [issue](https://github.com/airton-soares/subs_down_n_sync/issues/new?template=feature_request.yml) descrevendo o caso de uso.

## Enviar código

1. Fork o repositório e clone localmente
2. Crie um ambiente virtual e instale as dependências:
   ```bash
   python -m venv .venv
   source .venv/bin/activate   # Linux/macOS
   .venv\Scripts\activate      # Windows
   pip install -e ".[dev]"
   ```
3. Crie uma branch a partir de `main`:
   ```bash
   git checkout -b feat/minha-feature
   # ou
   git checkout -b fix/meu-bug
   ```
4. Faça commits seguindo [Conventional Commits](https://www.conventionalcommits.org/):
   - `feat: adicionar suporte a X` — nova funcionalidade (bump minor)
   - `fix: corrigir Y` — correção de bug (bump patch)
   - `docs: atualizar README` — documentação (sem bump)
   - `BREAKING CHANGE` no rodapé — mudança incompatível (bump major)
5. Rode os testes (cobertura mínima de 90%):
   ```bash
   pytest
   ```
6. Abra um Pull Request para `main`

## Padrões do projeto

- Identificadores em inglês; comentários e mensagens de UX em português
- Todas as exceções em `src/subs_down_n_sync/exceptions.py`
- Lint e formatação via Ruff: `ruff check . && ruff format --check .`
