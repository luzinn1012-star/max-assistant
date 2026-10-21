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
