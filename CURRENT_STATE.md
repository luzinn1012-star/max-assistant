# CURRENT_STATE: MAX

## FASE 2.5: hardening do núcleo

Estado: Fase 2.5 validada localmente e no CI, sem novas skills ou avanço para a fase 3.
195 testes principais e 87 subtestes passaram; os 142 métodos originais foram
preservados em unit/integration/windows/providers e reexecutados separadamente.

Ruff lint/formatação, mypy (37 módulos), pip check e todos os hooks pre-commit
passaram. Cobertura de linhas: 85.58%; combinada com ramificações: 83.98%.
O gate mínimo combinado é 80%, incluindo os módulos nativos.

Foram formalizados os contratos WindowsAdapter/AudioDevice, IntentResult,
SkillResult e ProviderResult; aliases antigos permanecem compatíveis.
Erros específicos, capabilities e request_id estão integrados. Abrir/fechar,
áudio, pastas e status preservam o comportamento anterior. Fechamento continua
exigindo confirmação; não há kill forçado.

phase2-hardening-validation.json é o relatório desta etapa.
O benchmark usa 5000 amostras, 200 de aquecimento e doubles: mediana do fluxo
local de aproximadamente 0.05 ms, sem LLM e sem medir abertura real de janelas.
Logging de saída foi desativado para a medição e isso consta no relatório.

O workflow MAX quality (.github/workflows/quality.yml) foi concluído com sucesso
para o commit af996d4ab42b188f1e5bc8e094b36b49ff63df4c, no evento push.
A execução foi confirmada pela API oficial do GitHub em 2026-10-21:
https://github.com/luzinn1012-star/max-assistant/actions/runs/39630243668

Os dois jobs quality (3.12) e quality (3.13), em Windows, passaram. Instalação de
dependências, pip check, Ruff lint/formatação, mypy e pytest com cobertura foram
aprovados em ambos. A execução terminou em 2026-10-21 às 15:57:45 UTC.
Nenhuma correção de código foi necessária nesta conferência; somente este
registro e o ROADMAP foram atualizados.
Nenhuma ação real do Windows ou inferência live foi repetida nesta fase.
A evidência real anterior continua preservada abaixo.
A tag estável v0.2-phase2 permanece no commit anterior e não foi movida.

## Histórico: FASE 2.1, validação real do Windows

Estado: validação real concluída. Nenhuma nova skill ou funcionalidade foi adicionada.
Os adaptadores de produção funcionaram sem necessidade de correções.

O MAX foi iniciado normalmente pelo run-max.cmd em uma janela real do Windows.
Os comandos de validação também usaram o mesmo iniciador, com execução autorizada
fora do sandbox e sem mocks, automação por mouse ou comandos gerados por LLM.

## Comandos reais

| Comando | Intent | Skill | LLM | Duração interna em ms | Resultado |
| --- | --- | --- | --- | --- | --- |
| Max, abra a Calculadora. | open_app | apps | Não | 708.2 | Aprovado |
| Max, abra o Discord. | open_app | apps | Não | 13.2 | Aprovado |
| Max, abra o Spotify. | open_app | apps | Não | 13.2 | Aprovado |
| Max, abra Downloads. | open_folder | folders | Não | 84.5 | Aprovado |
| Max, volume 30. | set_volume | volume | Não | 9.4 | Aprovado |
| Max, mute. | mute_volume | volume | Não | 9.8 | Aprovado |
| Max, unmute. | unmute_volume | volume | Não | 8.9 | Aprovado |
| Max, como está o PC? | system_status | system | Não | 134.3 | Aprovado |

Discord e Spotify já estavam em execução e suas janelas visíveis foram confirmadas.
O Windows recusou SetForegroundWindow nesses dois testes. A abertura/reutilização
foi validada; a troca de foco não foi garantida pelo sistema e não foi forçada.
A Calculadora foi aberta por URI. Downloads foi localizado por Known Folders e
sua janela foi conferida pelo caminho real via Shell.Application.

Volume de trinta por cento, mute e unmute foram confirmados por novas leituras
Core Audio. O estado anterior do áudio foi restaurado ao final e verificado.
CPU, RAM, disco e uptime passaram por verificações independentes; uptime também
foi comparado com GetTickCount64.

## Fechamento e permissões

A Calculadora de teste passou por uma sessão real interativa do MAX. O pedido
produziu confirmation_required, a janela permaneceu aberta antes da confirmação
e a entrada explícita de teste produziu close_requested. O desaparecimento da
janela foi verificado. Nenhum encerramento forçado foi usado.

## Cérebro e fallback

Codex continua como provider principal, usando o login ChatGPT existente.
A pergunta "Qual é o seu nome?" recebeu "Meu nome é Max." pelo Codex.

Uma configuração temporária exclusiva de validação solicitou ao Codex um modelo
intencionalmente inexistente. A falha real da CLI acionou o Ollama automaticamente,
que respondeu "Meu nome é Max.". O arquivo temporário foi removido e config.json
permaneceu inalterado. Nenhuma chave de API paga foi usada.

## Testes e desempenho

- Suíte completa: 142 testes aprovados.
- Testes anteriores preservados; nenhum novo teste unitário foi necessário.
- Os oito comandos locais usaram provider local e llm_used=false.
- Média dentro do MAX: 122.7 ms.
- Média por chamada ao iniciador, incluindo partida do Python: 683.8 ms.

As médias se referem aos oito comandos locais da sequência de validação, sem o
custo adicional das verificações externas nem as perguntas aos providers.

## Artefatos e reprodução

- real-windows-validation.json: evidências, tempos, observações nativas, falha real
  do Codex, fallback e resultado da suíte.
- tests/real_windows_validation.py: roteiro opt-in de validação dos oito comandos.
- tests/real_windows_close_validation.py: roteiro real da confirmação e fechamento
  normal de uma Calculadora de teste.

Em um Windows autorizado para as ações reais:

```powershell
.\.venv\Scripts\python.exe -B -m tests.real_windows_validation --execute
.\.venv\Scripts\python.exe -B -m tests.real_windows_close_validation
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -q
```

Esses roteiros são de validação e não entram na descoberta padrão de testes unitários.
Eles abrem aplicativos reais e o teste de fechamento envia uma confirmação explícita
de teste somente para a Calculadora. O primeiro restaura o áudio anterior.

## Git e escopo

Organização técnica revisada em 2026-10-21. Repositório privado criado após
confirmação explícita do usuário:
https://github.com/luzinn1012-star/max-assistant

Conta, URL de clone e visibilidade private foram verificadas pela integração
GitHub. Origin: https://github.com/luzinn1012-star/max-assistant.git.
A branch main acompanha origin/main. O histórico completo e a tag v0.2-phase2
foram publicados com push normal, sem force, e as referências remotas conferidas.

A tentativa inicial pelo navegador encontrou a tela de login. Depois, a
integração GitHub passou a estar disponível e criou o repositório vazio.
A autenticação do Git local foi concluída pelo Git Credential Manager oficial,
sem copiar tokens da integração ou ler arquivos privados de autenticação.

A referência estável v0.2-phase2 permanece no commit
05bde59e0dfee89b779da4d09e9945e1c4712f4f, com fases 1/2 e validação 2.1.
Commits posteriores apenas de documentação não movem essa tag.
O primeiro commit consolidado da validação é
b39bfaa2e3446abf2a2c6b65c01289e23443df44.

A suíte de 142 testes foi reexecutada antes do envio. A revisão de todo o
histórico não identificou segredos reais nos padrões verificados; a única
ocorrência revisada foi uma URL fictícia em teste de rejeição de credenciais.
O .gitignore foi verificado com 40 casos. Relatórios incluem metadados da máquina
e permanecem no repositório privado. Repetir a revisão antes de novos pushes.

Autoria técnica MAX <max@localhost>, limitada aos commits desta organização;
nenhuma configuração global do Git foi alterada. Consultar git log para o hash
mais recente, git status para sincronização e git show v0.2-phase2 para a tag.
Não incluir o hash do próprio commit neste documento.

README, ROADMAP, TODO, ARCHITECTURE, DECISIONS e CHANGELOG complementam este
estado. As seis Issues das fases futuras estão planejadas, ainda não criadas.
Nenhuma funcionalidade foi alterada. Voz, wake word, novas skills, Spotify API
e Modo Jogo continuam sem implementação.
