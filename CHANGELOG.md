# CHANGELOG

<!-- version list -->

## v1.2.0 (2026-04-27)

### Bug Fixes

- _pick_subtitle usa _compute_needs_sync; release e fallback com alta similaridade não sincronizam
  ([`33989c4`](https://github.com/airton-soares/subs_down_n_sync/commit/33989c460247ce7402da3b4b963b12157ff473aa))

- Aumentar SYNC_THRESHOLD_SECONDS de 0.1s para 0.2s para reduzir falsos positivos de sync
  ([`f5d54be`](https://github.com/airton-soares/subs_down_n_sync/commit/f5d54be88c730240b1ec8ffc1279eaf0ba726b8d))

- Evitar duplo cálculo de similarity em _pick_subtitle; clarificar teste de alta similaridade
  ([`f01c7a8`](https://github.com/airton-soares/subs_down_n_sync/commit/f01c7a85af2a6ca028edefef152eebca9bd409ae))

- Find_reference_subtitle usa _pick_subtitle para seleção de legenda EN; remove _download_sub
  ([`90caf61`](https://github.com/airton-soares/subs_down_n_sync/commit/90caf6196ad3049a03a988e46e28e69fcb2be11a))

- Resync usa similaridade de nome para decidir needs_sync em vez de True hardcoded
  ([`76f5e49`](https://github.com/airton-soares/subs_down_n_sync/commit/76f5e49f62e91ea4def1ceda66ab174518ea5fc2))

### Chores

- Corrigir linhas longas no lint
  ([`1c7b8bb`](https://github.com/airton-soares/subs_down_n_sync/commit/1c7b8bb66e738a70b886a4fe306369a16dd20710))

### Features

- Adicionar _compute_needs_sync como fonte única de decisão de sync
  ([`f598abe`](https://github.com/airton-soares/subs_down_n_sync/commit/f598abe425ef58d40ddb553b15018a84a6cc83ae))

- Suporte a --overwrite no caminho de arquivo único
  ([`adbe0c5`](https://github.com/airton-soares/subs_down_n_sync/commit/adbe0c587360d02b677ff1458f97701b6ace1050))

### Testing

- Aumentar cobertura para 99%; remover _classify_match (código morto)
  ([`38f04c9`](https://github.com/airton-soares/subs_down_n_sync/commit/38f04c9439c3201f9df5215839066c65349d3965))


## v1.1.3 (2026-04-26)


## v1.1.2 (2026-04-26)

### Bug Fixes

- Corrigir detecção de legenda existente em nomes com pontos
  ([`c21ccc4`](https://github.com/airton-soares/subs_down_n_sync/commit/c21ccc49550cf3fe5b73ca51d172777966229c49))

### Chores

- Adicionar .worktrees ao .gitignore
  ([`b28a39d`](https://github.com/airton-soares/subs_down_n_sync/commit/b28a39d80033b307b5ee79019199cfdda3232685))

### Documentation

- Documentar pipx como instalação recomendada e corrigir PATH warning
  ([`3e04986`](https://github.com/airton-soares/subs_down_n_sync/commit/3e049865b76a02c21e1611f534bc1ed5f1a7a9c5))


## v1.1.1 (2026-04-26)

### Bug Fixes

- Corrigir linhas longas apontadas pelo ruff (E501)
  ([`1fb4998`](https://github.com/airton-soares/subs_down_n_sync/commit/1fb4998e0fb71a9596039a4539f703a20d683f81))


## v1.1.0 (2026-04-26)

### Documentation

- Atualizar cache bust dos badges PyPI para v2
  ([`1fbf8d0`](https://github.com/airton-soares/subs_down_n_sync/commit/1fbf8d0a1cb99000b7f25728a3887b63fea263a6))

- Remover cache bust manual dos badges PyPI
  ([`908e8e8`](https://github.com/airton-soares/subs_down_n_sync/commit/908e8e882d46235f521962fd55c70929e648f21c))

### Features

- Adicionar --resync na CLI mantendo --overwrite com prioridade
  ([`f28e9e3`](https://github.com/airton-soares/subs_down_n_sync/commit/f28e9e3e813e586b11137355c6a3e6b50398691f))

- Adicionar parâmetro resync em core.run() com desvio de download
  ([`da41b30`](https://github.com/airton-soares/subs_down_n_sync/commit/da41b304873afad1c0fb31ac3f5a6e8ba3d5cdaa))


## v1.0.4 (2026-04-26)

### Bug Fixes

- Reduzir versão mínima do Python de 3.12 para 3.9
  ([`fbe8928`](https://github.com/airton-soares/subs_down_n_sync/commit/fbe892818cd53e3993c6f733e282c9a20b3a932d))

- Usar RELEASE_TOKEN no workflow de release
  ([`93e528b`](https://github.com/airton-soares/subs_down_n_sync/commit/93e528bd3aaca0ff5d1b8828f786ea3affb2d3ed))

### Continuous Integration

- Re-trigger release pipeline
  ([`4b3d2d1`](https://github.com/airton-soares/subs_down_n_sync/commit/4b3d2d15635289da768315f5241d149c362a054f))


## v1.0.3 (2026-04-25)

### Bug Fixes

- Adicionar cache bust nos badges PyPI
  ([`8d1989c`](https://github.com/airton-soares/subs_down_n_sync/commit/8d1989c1b432d3860294a8ad8c846f1bef2b4743))


## v1.0.2 (2026-04-25)

### Bug Fixes

- Trocar badge de licença para fonte PyPI
  ([`2f64ada`](https://github.com/airton-soares/subs_down_n_sync/commit/2f64ada4a31cc319bbcfa1e4742f5299f1fb8d76))


## v1.0.1 (2026-04-25)

### Bug Fixes

- Remover license classifier redundante com SPDX expression
  ([`dbf7031`](https://github.com/airton-soares/subs_down_n_sync/commit/dbf70310ac2085c519232f9bd36a5d275624c616))

### Chores

- Trocar licença de MIT para GPL-3.0-or-later
  ([`b4c7386`](https://github.com/airton-soares/subs_down_n_sync/commit/b4c7386fce96d6c1fbd198b09a7e131a8c114ce5))


## v1.0.0 (2026-04-25)

- Initial Release
