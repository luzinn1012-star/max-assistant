# CURRENT_STATE: MAX

## FASE 2.1: Validação real do Windows

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

Organização técnica revisada em 2026-10-21. Branch main, sem remote e sem
push. Sugestão: repositório GitHub privado max-assistant, cuja criação depende
de confirmação explícita do usuário. Nenhuma conta ou URL foi presumida.

A referência estável é v0.2-phase2: fases 1/2 e validação 2.1, com 142 testes
novamente aprovados durante a organização do Git. A tag local não comprova push.
O primeiro commit consolidado da validação é b39bfaa2e3446abf2a2c6b65c01289e23443df44.

O .gitignore foi ampliado e verificado com 40 casos de arquivos protegidos ou
permitidos. A revisão do histórico não encontrou padrões de segredos; isso não
substitui nova revisão antes de publicar. Os relatórios contêm metadados da
máquina, portanto o destino proposto é privado. Nenhum arquivo de autenticação
do Codex foi lido ou copiado nesta organização.

Autoria técnica MAX <max@localhost>, limitada aos commits desta tarefa; nenhuma
configuração global do Git foi alterada. Consultar os hashes com git log e a tag
com git show v0.2-phase2. Não incluir o hash do próprio commit neste documento.

README, ROADMAP, TODO, ARCHITECTURE, DECISIONS e CHANGELOG complementam este
estado. As seis Issues das fases futuras estão planejadas, ainda não criadas.
Nenhuma funcionalidade foi alterada nesta organização. Voz, wake word, novas
skills, Spotify API e Modo Jogo continuam sem implementação.
