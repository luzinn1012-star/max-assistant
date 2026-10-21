# ROADMAP

Atualizado em 2026-10-21. Este arquivo registra direção e limites de escopo;
o estado comprovado está em [CURRENT_STATE.md](CURRENT_STATE.md).

| Marco | Estado | Resultado ou escopo futuro |
| --- | --- | --- |
| Fase 1 — Base e providers | Concluída | Terminal, Codex com login ChatGPT, Ollama e fallback; 38 testes originais. |
| Fase 2 — Router e primeiras skills | Concluída | Regras locais, registry, apps, pastas, áudio, status e confirmação; 142 testes totais. |
| Fase 2.1 — Validação real do Windows | Concluída | Oito comandos reais, áudio relido, fechamento confirmado e fallback real; relatórios preservados. |
| Fase 2.5 — Hardening | Validada localmente | Ruff, mypy, pytest-cov, pre-commit, capabilities, contratos e 195 testes; CI Windows configurado. |
| Organização do Git | Concluída | Repositório privado luzinn1012-star/max-assistant criado; main e tag estável publicadas sem force push. |
| Fase 3 — Integrações | Não iniciada | Definir integrações de Spotify/Discord e próximos recursos de navegador/arquivos, reutilizando as skills atuais. |
| Fase 4 — Modo Jogo | Não iniciada | Preparação reversível, estado anterior salvo e restauração; sem alterar proteções do Windows. |
| Fase 5 — Voz | Não iniciada | STT/TTS locais e intercambiáveis; começar por Push-to-Talk. |
| Fase 6 — Wake word | Não iniciada | Palavra Max com uso controlado de CPU, após a voz funcionar. |
| Fase 7 — Memória | Não iniciada | SQLite para preferências e caminhos conhecidos, sem senhas. |
| Fase 8 — Tray e startup | Não iniciada | Bandeja e início com Windows removível, apenas mediante autorização. |

## Planejamento no GitHub

No repositório privado já criado, usar futuramente Issues com os títulos:

- Fase 3 — Integrações
- Fase 4 — Modo Jogo
- Fase 5 — Voz
- Fase 6 — Wake word
- Fase 7 — Memória
- Fase 8 — Tray e startup

Essas Issues ainda não foram criadas. Cada uma deve definir escopo, critérios de
aceitação, dependências e testes antes da implementação. Uma Issue não autoriza
automaticamente operações de conta, instalação ou mudanças críticas.

Não iniciar a próxima fase nesta tarefa. Nenhuma data de entrega foi assumida.
