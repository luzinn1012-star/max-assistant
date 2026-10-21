# TODO

Atualizado em 2026-10-21.

## Organização e publicação concluídas

- [x] Inspecionar Git, branch, histórico e arquivos rastreados.
- [x] Reexecutar a suíte existente: 142 testes aprovados.
- [x] Ampliar .gitignore para ambientes, autenticação, credenciais, caches e logs.
- [x] Verificar 40 casos de arquivos protegidos/permitidos sem criar credenciais.
- [x] Revisar arquivos e todo o histórico com padrões de segredos.
- [x] Consolidar README, CURRENT_STATE, ROADMAP, TODO, ARCHITECTURE, DECISIONS e CHANGELOG.
- [x] Preservar as evidências da fase 2.1 e as limitações conhecidas.
- [x] Obter confirmação explícita para criar o repositório privado max-assistant.
- [x] Confirmar conta luzinn1012-star e criar o repositório privado vazio.
- [x] Configurar origin com a URL de clone confirmada pelo GitHub.
- [x] Concluir autenticação oficial do Git local pelo Git Credential Manager.
- [x] Conferir URL, branch, visibilidade e histórico remoto antes de enviar.
- [x] Reexecutar testes, revisão de segredos e git diff antes do push.
- [x] Enviar main e a tag v0.2-phase2 com push normal, sem force.
- [x] Verificar as referências remotas e registrar a publicação em CURRENT_STATE.

Repositório: https://github.com/luzinn1012-star/max-assistant (privado).
O .gitignore não remove arquivos já rastreados nem apaga histórico. Repetir
testes, revisão de segredos e git diff antes de qualquer novo push.

## Próximas etapas, sem implementação nesta entrega

- [ ] Abrir futuramente as seis Issues descritas em ROADMAP.
- [ ] Definir o escopo da fase 3 antes de começar novas integrações.
- [ ] Manter a limitação de foco documentada: Windows pode recusar SetForegroundWindow.
- [ ] Revalidar ações nativas quando os adaptadores correspondentes forem alterados.

Voz, wake word, Modo Jogo, memória persistente, tray e startup continuam fora do
escopo atual. A suíte padrão usa doubles/mocks; não substitui a validação real.

## Fase 2.5 — hardening local concluído

- [x] Ruff e formatação verificados, com configuração versionada.
- [x] mypy sem erros; contratos novos com assinaturas completas.
- [x] pytest-cov com cobertura de linhas e ramificações, mínimo combinado de 80%.
- [x] pre-commit configurado, instalado neste checkout e executado integralmente.
- [x] Grupos unit/integration/windows/providers e 142 métodos originais preservados.
- [x] Protocols para os adaptadores nativos, sem subprocessos nas skills.
- [x] IntentResult, SkillResult, ProviderResult e erros específicos integrados.
- [x] Capabilities verificadas antes de preparar e executar ações.
- [x] request_id e metadados de fallback/erro nos logs.
- [x] Benchmark reproduzível, sem ações reais ou chamadas a LLM.
- [x] Workflow GitHub Actions para Ruff, mypy e pytest em Windows.
- [x] Relatório phase2-hardening-validation.json gerado com checks aprovados.
- [ ] Conferir a execução remota do workflow após o push da fase 2.5.

A suíte tem 195 testes e 87 subtestes; cobertura local combinada de 83.98%.
A fase 2.5 usou mocks/doubles. Nenhum novo teste de controle real do Windows
ou inferência live foi executado; a evidência histórica 2.1 permanece preservada.
