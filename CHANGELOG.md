# CHANGELOG

Somente mudanças e validações comprovadas. As fases anteriores foram importadas
no primeiro commit local consolidado; não há commits separados inventados.

## Fase 2.5 — 2026-10-21 (main, sem mover a tag anterior)

- Ruff, mypy, pytest-cov, pre-commit e ferramentas de desenvolvimento fixadas.
- Grupos de testes reorganizados; 142 testes originais preservados.
- Protocols de adapters, resultados e erros estruturados, capabilities e request_id.
- 195 testes e 87 subtestes aprovados; cobertura combinada de 83.98%.
- Benchmark reproduzível com doubles e workflow Windows 3.12/3.13.
- Nenhuma nova skill, integração avançada, voz, wake word ou Modo Jogo.

## v0.2-phase2 — 2026-10-21

Versão estável das fases 1/2, incluindo a validação real 2.1 e a organização
técnica local. A tag identifica um commit validado, não uma publicação remota.

### Implementado antes desta organização

- Terminal Python e iniciador run-max.cmd.
- Codex autenticado pelo ChatGPT e fallback automático para Ollama qwen3:4b.
- Roteador determinístico com normalização, confiança e tratamento de ambiguidade.
- Registry e skills apps, folders, volume, system e help.
- Confirmação de fechamento, APIs diretas do Windows e metadados de latência.
- 142 testes, incluindo os 38 testes da fase 1.

### Validação real 2.1

- Oito comandos locais aprovados sem chamadas ao LLM.
- Volume/mute/unmute relidos e estado de áudio anterior restaurado.
- CPU, RAM, disco e uptime verificados.
- Fechamento normal de Calculadora com confirmação e sem kill.
- Identidade confirmada por Codex e fallback real para Ollama após falha induzida.
- Limitação registrada: Windows recusou foco de Discord/Spotify já abertos.

### Organização técnica

- .gitignore ampliado para credenciais, autenticação, ambientes, caches e runtime.
- README/CURRENT_STATE revisados e ROADMAP/TODO/ARCHITECTURE/DECISIONS criados.
- Histórico mantido em commits pequenos, sem mudanças no funcionamento do MAX.
- Repositório privado luzinn1012-star/max-assistant criado após autorização.
- O navegador inicialmente exigiu login; a integração GitHub tornou-se disponível
  e criou o repositório. Git Credential Manager concluiu a autenticação oficial.
- Origin configurado e histórico completo/main/tag enviados por push normal,
  sem force. As referências remotas foram conferidas com as referências locais.
- Suíte de 142 testes novamente aprovada e histórico revisado para padrões de
  segredos antes do envio. Nenhuma funcionalidade foi alterada.

## Marco da fase 1 — 2026-10-19

Conversa básica e providers validados; 38 testes originais e respostas reais
"Meu nome é Max.". Evidência: phase1-validation.json.

## Marco da fase 2 — 2026-10-21

142 testes totais e roteamento local aprovados. O relatório inicial mantinha
ações reais como pendentes; real-windows-validation.json comprova a conclusão
posterior dessa validação no mesmo dia.
