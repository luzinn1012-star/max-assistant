# TODO

Atualizado em 2026-10-21.

## Preparação local concluída

- [x] Inspecionar Git, branch, histórico, arquivos rastreados e ausência de remote.
- [x] Reexecutar a suíte existente: 142 testes aprovados.
- [x] Ampliar .gitignore para ambientes, autenticação, credenciais, caches e logs.
- [x] Verificar exemplos de arquivos protegidos sem criar credenciais reais.
- [x] Revisar arquivos rastreados e histórico com padrões de segredos.
- [x] Consolidar README, CURRENT_STATE, ROADMAP, TODO, ARCHITECTURE, DECISIONS e CHANGELOG.
- [x] Preservar as evidências da fase 2.1 e as limitações conhecidas.

## Publicação pendente

- [ ] Obter confirmação explícita para criar o repositório privado max-assistant.
- [ ] Confirmar a conta proprietária durante a criação, sem inventar URL.
- [ ] Criar o repositório vazio, sem README ou commit inicial remoto.
- [ ] Configurar origin com a URL efetivamente retornada pelo GitHub.
- [ ] Conferir URL, branch e histórico remoto antes de enviar.
- [ ] Reexecutar testes, revisão de segredos e git diff imediatamente antes do push.
- [ ] Enviar main e a tag v0.2-phase2 com push normal, sem force.
- [ ] Registrar o resultado efetivo da publicação em CURRENT_STATE.

Sem remote, não há push. A tag local não comprova publicação no GitHub.
O .gitignore não remove arquivos que já estejam rastreados nem apaga histórico.

## Próximas etapas, sem implementação nesta entrega

- [ ] Abrir futuramente as seis Issues descritas em ROADMAP.
- [ ] Definir o escopo da fase 3 antes de começar novas integrações.
- [ ] Manter a limitação de foco de janelas documentada: Windows pode recusar SetForegroundWindow.
- [ ] Revalidar ações nativas quando os adaptadores correspondentes forem alterados.

Voz, wake word, Modo Jogo, memória persistente, tray e startup continuam fora do
escopo atual. A suíte padrão usa doubles/mocks; não substitui a validação real.
