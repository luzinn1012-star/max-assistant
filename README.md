# MAX — fase 2.5: hardening

Assistente pessoal para Windows, em português do Brasil, com terminal, conversa,
provider Codex autenticado pelo ChatGPT e fallback local para Ollama.
Python 3.12 ou superior. A fase dois usa psutil para métricas e processos;
não é necessário fornecer OPENAI_API_KEY. Comandos simples passam primeiro
pelo roteador local e pelas skills documentados no fim deste arquivo.


## Memória técnica e versionamento

Versão estável de referência: `v0.2-phase2`. O marco anterior tem 142 testes
e oito comandos validados no Windows real; a main agora inclui o hardening
2.5 com 195 testes, descrito no fim deste documento. O repositório privado está em
[GitHub: luzinn1012-star/max-assistant](https://github.com/luzinn1012-star/max-assistant).
A branch `main` acompanha `origin/main`; o histórico e a tag estável foram enviados
com push normal, sem force. A tag permanece no commit estável, mesmo quando novos
commits apenas de documentação são adicionados à main.

- [Estado comprovado e limitações](CURRENT_STATE.md)
- [Arquitetura implementada](ARCHITECTURE.md)
- [Decisões técnicas](DECISIONS.md)
- [Plano por fases e Issues futuras](ROADMAP.md)
- [Pendências de publicação e desenvolvimento](TODO.md)
- [Histórico de entregas](CHANGELOG.md)

O .gitignore protege .env, autenticação, credenciais, chaves, ambientes, caches,
bancos e logs. O exemplo .env.example permanece sem credenciais. Ignorar arquivos
não remove segredos já rastreados: revisar também o histórico antes de publicar.
Os relatórios reais incluem caminhos e metadados locais e devem permanecer privados.

Antes de qualquer push: executar a suíte, revisar segredos nos arquivos e no
histórico, conferir `git diff --check`, `git diff --cached`, `git status` e a URL
do remote. Não usar force push. A tag local e os commits não comprovam publicação.

## Iniciar

No terminal, dentro desta pasta:

```powershell
.\.venv\Scripts\python.exe main.py
```

Também é possível abrir `run-max.cmd` pelo Explorador de Arquivos.

Digite uma mensagem normalmente. Comandos do terminal:
- `/status`: disponibilidade dos providers e último provider usado.
- `/limpar`: apaga o contexto temporário da conversa.
- `/tentar`: permite nova tentativa imediata após falha de provider.
- `/sair`: encerra o MAX. Ctrl+C também encerra e cancela o subprocesso Codex atual.

Testar uma pergunta:

```powershell
.\.venv\Scripts\python.exe main.py --ask "Qual é o seu nome?"
.\.venv\Scripts\python.exe main.py --provider ollama --ask "Qual é o seu nome?"
.\.venv\Scripts\python.exe main.py --health --json
```

O diagnóstico confirma instalação/login/modelo. Somente uma resposta concluída
confirma inferência. A interface mostra o provider efetivamente usado e o tempo
total da solicitação, incluindo checagens e fallback quando houver.

## Instalação reproduzível

Python, Git, Codex CLI e Ollama já foram detectados nesta máquina; o ambiente
virtual foi criado. Em outra instalação, após disponibilizar Python:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Não é preciso ativar a venv nem alterar a política de execução do PowerShell.
A dependência da fase dois está fixada no requirements.txt e fica apenas na venv.
Git é útil para versionamento, mas não é obrigatório para executar a conversa.

## Codex e a assinatura ChatGPT

O provider usa o método oficial `codex exec --json`, com prompt via stdin e
autenticação gerenciada pela própria CLI. `codex login status` verifica o método
de login. Se for necessário entrar novamente, execute `codex login` no seu terminal
e conclua a autenticação oficial pelo navegador.

O MAX não abre, copia, extrai nem armazena credenciais do Codex. Não chama endpoints
privados nem utiliza uma API key de cobrança por uso. A CLI precisa estar autenticada
pelo ChatGPT. Chaves e tokens de API herdados do ambiente não são enviados ao
subprocesso. O uso continua sujeito aos limites e à disponibilidade da sua conta.

As opções exigidas são verificadas em `codex exec --help`. Versões sem
`--ignore-user-config`, `--ephemeral`, `--json` ou `--sandbox` são recusadas com
orientação para atualizar a CLI; em modo auto, o Ollama assume.

Cada chamada abre um processo Codex em diretório próprio, usa sandbox somente leitura,
desativa shell, aplicativos conectados, hooks, pesquisa e subagentes, e ignora a
configuração pessoal de ferramentas. O contexto curto da conversa é reenviado a cada
chamada. A resposta só é aceita se houver mensagem final e evento de conclusão.
Nenhuma resposta do modelo é interpretada como comando.

Esse método é suportado para uso programático da CLI, mas inicia um processo por
pergunta e não promete latência de uma API de chat persistente. `codex_model` vazio
usa a escolha padrão da CLI instalada, sem herdar a preferência do config.toml pessoal.
Um modelo específico pode ser configurado caso esteja disponível na conta.

Fontes oficiais:
- [Modo não interativo e reutilização do login](https://learn.chatgpt.com/docs/non-interactive-mode).
- [Autenticação ChatGPT e API](https://learn.chatgpt.com/docs/auth).
- [Opções da CLI](https://learn.chatgpt.com/docs/developer-commands?surface=cli).
- [Configuração do Codex](https://learn.chatgpt.com/docs/config-file/config-reference).

## Ollama local

Padrão: `http://127.0.0.1:11434`, modelo `qwen3:4b`. O provider conversa diretamente
com a API HTTP local. O modelo já estava instalado; nenhum modelo foi baixado.

Se o servidor estiver parado, execute em outro terminal:

```powershell
ollama serve
```

Se o modelo estiver ausente em outra máquina, `ollama pull qwen3:4b` faz o download.
O MAX apenas informa a ausência; não instala nem baixa modelos automaticamente.

Para reduzir latência, o provider solicita `think=false`, usa `/no_think` no Qwen3,
limita o contexto e mantém o modelo carregado por dez minutos. Templates locais que
ainda emitam marcadores internos são tratados: apenas a resposta final é mostrada,
sem texto de raciocínio. O carregamento inicial pode ser mais lento.

A URL é limitada ao computador local; proxies e redirecionamentos HTTP são desativados.
O funcionamento do modelo local não depende de uma chave nem de conexão com a OpenAI.

Fontes: [API de chat do Ollama](https://docs.ollama.com/api/chat) e
[controle de modo do Qwen3](https://qwenlm.github.io/blog/qwen3/).

## Configuração e fallback

Edite `config.json` para mudar configurações simples. Nenhuma credencial pertence a
esse arquivo. O arquivo .env não é necessário e não é carregado. .env.example explica
as variáveis opcionais de ambiente: MAX_PROVIDER, MAX_OLLAMA_URL, MAX_OLLAMA_MODEL,
MAX_CODEX_MODEL. Essas variáveis prevalecem sobre o JSON; --provider prevalece sobre ambas.

- `provider: "auto"`: tenta Codex; em indisponibilidade, erro ou timeout, usa Ollama.
- `provider: "codex"` ou `"ollama"`: força esse provider para conversa; as skills locais continuam tendo prioridade.
- `codex_timeout`: trinta segundos por inferência.
- `ollama_timeout`: noventa segundos, incluindo carregamento local.
- `health_timeout`: cinco segundos por verificação.
- `retry_cooldown`: sessenta segundos antes de repetir um provider que falhou.
- `history_turns`: até seis pares de mensagens temporários.
- `context_chars` e `max_input_chars`: limites de contexto e entrada.
- `ollama_context_tokens` e `ollama_max_tokens`: limites do modelo local.

O fallback reutiliza o contexto da conversa. Falhas não são gravadas como respostas
no histórico. Se todos falharem, o terminal informa isso sem inventar sucesso.
Durante o cooldown, novas mensagens usam o provider restante; /tentar limpa a espera.
Nenhuma configuração global do Codex ou do Ollama é modificada.

## Estrutura base preservada da fase um

```text
max-assistant/
  main.py
  config.py
  config.json
  requirements.txt
  .env.example
  .gitignore
  run-max.cmd
  README.md
  phase1-validation.json     relatório dos testes reais
  .venv/                    ambiente Python isolado
  brain/
    __init__.py
    provider.py             contrato ask/available/health_check
    codex_provider.py       CLI oficial com login ChatGPT
    ollama_provider.py      HTTP local
    prompts.py
    personality.txt         personalidade compartilhada
  core/
    __init__.py
    assistant.py            seleção, fallback e duração
    context.py              contexto temporário limitado
    logging_setup.py
  tests/
    __init__.py
    unit/                   normalização, router, skills, config e CLI
    integration/            Assistant, fallback, capabilities e confirmações
    providers/              Codex e Ollama com doubles
    windows/                adaptadores nativos com mocks
    live_smoke.py            teste real opt-in
  data/
    README.md
    codex-work/              diretório de execução da CLI
  logs/
    max.log
```

SQLite será usado para memória persistente na fase sete. Não há um max.db vazio
fingindo persistência nesta fase; fechar o MAX descarta o histórico da conversa.
As skills e seus adaptadores diretos estão integrados na fase dois. Voz, modo jogo,
bandeja e inicialização com Windows ficam para etapas posteriores. O servidor Ollama iniciado durante a preparação não foi registrado
por este projeto para iniciar com o Windows.

## Logs

`logs/max.log` registra horário, categoria da operação, provider, skill,
duração em milissegundos, sucesso/falha e código técnico do erro. Os campos
adicionais de roteamento da fase dois estão descritos ao final. Há rotação
de arquivos. O conteúdo livre das perguntas/respostas e o stderr bruto da CLI não
são gravados, para evitar guardar senhas ou tokens inseridos acidentalmente.
A conversa fica apenas na RAM do MAX; o Codex recebe esse contexto para responder
e seu tratamento de dados continua seguindo as condições da conta.

## Testes

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m tests.live_smoke
```

A suíte padrão usa fakes, mocks e um servidor HTTP de teste no localhost, sem consumir
sua assinatura. Cobre seleção/fallback, cooldown, histórico, autenticação, argumentos
seguros, cancelamento de subprocesso, respostas inválidas/incompletas, logs e configuração.

O teste live é opt-in: chama Codex e Ollama reais, exige a resposta exata
"Meu nome é Max.", verifica contexto de conversa e provoca um timeout de um
milissegundo em uma instância isolada do Codex para validar fallback real.
Ele não modifica config.json nem a autenticação. O resultado só é salvo como aprovado
após todas as verificações passarem, em phase1-validation.json.

## Próxima etapa

A fase dois e sua validação real no Windows estão concluídas. O próximo marco
funcional planejado é a fase três; esta organização do Git não inicia sua implementação.

## Fase dois: comandos locais antes do cérebro

A fase dois integra os módulos locais já existentes ao Assistant. A cadeia de
providers foi preservada. Houve apenas uma correção pontual no OllamaProvider:
fechar a resposta HTTP também nos caminhos de erro, identificada pela suíte.

Fluxo:

```text
texto -> normalizer -> router -> confiança
                          |
            confiança >= router_threshold e skill registrada
                          |
                   permissões -> skill -> adaptador nativo
                          |
        desconhecido / confiança baixa / conflito entre regras
                          |
                     Codex -> Ollama
```

O router usa fullmatch de regex e aliases, sem LLM. O prefixo Max, acentos,
pontuação irrelevante e "por favor" são normalizados. Sinais, casas decimais e
percentuais são preservados. Duas regras igualmente confiantes e contraditórias
produzem unknown. Frases negativas, explicações e comandos combinados não são
executados parcialmente. Um erro de skill é reportado localmente; não há nova
tentativa por LLM, mouse ou outro transporte.

O comando desconhecido original, completo, segue para o cérebro. A resposta do
cérebro nunca é interpretada como ação. --provider codex e --provider ollama
selecionam somente o provider de conversa: comandos locais continuam locais.

Novos arquivos e responsabilidades:

- core/normalizer.py: normalização conservadora.
- core/intent.py: Intent com intent, confidence e slots; Rule com regex e resolver.
- core/router.py: matching determinístico e atualização após registro de skills.
- core/dispatcher.py: validação, permissões, execução e tempos por etapa.
- core/permissions.py: SAFE, CONFIRM, DANGEROUS e confirmação temporária.
- skills/base.py e skills/registry.py: contrato e registro das skills.
- skills/apps.py, volume.py, folders.py, system.py e help.py: cinco skills.
- skills/bootstrap.py: composição das skills e injeção dos adaptadores.
- automation/windows.py: processos, janelas, ShellExecuteW, Known Folders e métricas.
- automation/audio.py: Core Audio via COM/ctypes.
- apps.json: catálogo explícito de aplicativos e aliases.
- tests/test_phase2_*.py: testes novos com doubles e mocks.
- tests/validate_phase2.py: testes, benchmark e relatório reproduzível.

### Comandos

| Exemplo | Intent | Skill |
| --- | --- | --- |
| Max, abra o Spotify. | open_app | apps |
| abrir discord | open_app | apps |
| abra a calculadora | open_app | apps |
| feche o Bloco de Notas | close_app | apps, confirmação |
| abra Downloads | open_folder | folders |
| abra a pasta Music | open_folder | folders |
| volume 30 | set_volume | volume |
| coloca o volume em 60% | set_volume | volume |
| aumenta o volume | set_volume, delta positivo | volume |
| diminui o volume | set_volume, delta negativo | volume |
| mute / muta o pc | mute_volume | volume |
| unmute / tira do mudo | unmute_volume | volume |
| como está o PC? | system_status | system |
| quanta RAM estou usando? | system_status | system |
| qual o uso da CPU? | system_status | system |
| principais processos / uptime | system_status | system |
| ajuda | help | help |
| Max, explique relatividade. | unknown | cérebro |

Os aplicativos cadastrados são Spotify, Discord, Calculadora, Bloco de Notas,
Explorador, Configurações e navegador padrão. A abertura prioriza URI registrada,
executável conhecido e atalho cadastrado. Não há busca arbitrária no disco,
cmd.exe, PowerShell gerado pelo modelo, automação visual ou mouse.

Uma janela existente é reutilizada quando identificada. O Windows pode negar a
mudança de foco; o MAX informa isso sem abrir outra instância por esse motivo.
Para aplicativos em bandeja sem janela reconhecível, o protocolo do app pode ser
usado para reativação. A verificação de processo confirma que o app está em
execução; não confirma que toda a interface terminou de carregar. Quando o Windows
apenas aceitou a abertura, o resultado é launch_requested, sem alegar verificação.
O navegador é aberto pelo protocolo HTTPS padrão, inicialmente em google.com;
a URI é configurável no catálogo.

As pastas Desktop, Downloads, Documents, Pictures, Videos e Music usam
SHGetKnownFolderPath do usuário atual. Isso respeita redirecionamentos, inclusive
OneDrive, sem fixar um caminho de perfil. "abra música/music" é alias de Spotify;
"abra a pasta música/music" e "abra músicas" abrem a pasta Music.

Volume é o volume mestre do dispositivo de saída padrão, pela API Core Audio.
Os valores são limitados a zero até cem. Alterar volume preserva o estado de mudo;
unmute é um comando separado. O estado é relido para confirmar a alteração,
com tolerância de um ponto percentual no volume. Não há mixer gráfico.

CPU, RAM, armazenamento principal, processos mais ativos e uptime vêm do psutil.
Há uma amostra curta de CPU, com espera de aproximadamente cento e vinte
milissegundos, para medir uso atual. GiB significa gibibytes. Uso de GPU e
temperaturas não são estimados: não há sensor confiável incluído nesta fase.

### Configuração da rota local

Novos campos de config.json:

```json
{
  "router_threshold": 0.80,
  "volume_step": 10,
  "confirmation_timeout": 30,
  "launch_verify_timeout": 2
}
```

router_threshold está no intervalo maior que zero e menor ou igual a um.
volume_step é o incremento padrão, em pontos percentuais, entre um e cem.
Os demais valores são segundos positivos. Nenhum deles altera a configuração
global do Windows, do Codex ou do Ollama.

### Risco e confirmação

SAFE inclui abrir aplicativos e pastas, áudio, ajuda e consultas.
CONFIRM inclui close_app. DANGEROUS existe na infraestrutura, mas sua execução
é bloqueada nesta fase.

O fechamento exige uma resposta explícita, como "sim" ou "confirmo", na mesma
sessão do terminal. "não" ou "cancelar" cancela. Outra mensagem, /limpar, expiração
ou uma janela cuja identidade mudou invalida o pedido. A confirmação é de uso único.

O snapshot contém HWND, PID e horário de criação do processo. Antes de enviar
WM_CLOSE, o adaptador verifica a identidade novamente e bloqueia serviços do
Windows e processos protegidos, inclusive explorer.exe. Se a consulta de serviços
for negada, o fechamento falha de forma segura. Nenhum kill forçado é implementado.
O app pode mostrar um aviso de salvamento ou ir para a bandeja; close_requested
significa que o pedido normal foi enviado, sem prometer que o processo terminou.
O MAX não responde automaticamente a avisos de salvamento.

Para confirmar, use o terminal interativo. Um --ask isolado não conserva pedidos
para uma segunda execução do programa. pending_confirmation=true e
status=confirmation_required sinalizam que a ação ainda não foi executada.

### Adicionar um aplicativo ou alias

Edite apps.json, um array de objetos, e reinicie o MAX para recarregar o catálogo.
Exemplo de entrada adicional:

```json
{
  "id": "editor",
  "label": "Meu Editor",
  "aliases": ["meu editor", "editor de texto"],
  "process_names": ["Editor.exe"],
  "uri": "",
  "executables": ["%LOCALAPPDATA%\\MeuEditor\\Editor.exe"],
  "arguments": [],
  "allow_close": true
}
```

id é um identificador minúsculo com letras, números e sublinhado. Aliases podem
conter acentos; colisões entre aplicativos são rejeitadas. Use variáveis de
ambiente para instalações dependentes do usuário. Os arguments são fixos do
cadastro; texto livre de uma pergunta não vira argumento de shell. O catálogo
é configuração confiável e deve ser editado apenas por quem usa o computador.
Não coloque senhas, tokens ou comandos destrutivos nele.

Para cadastrar outro alias de Spotify, adicione o nome à lista aliases do objeto
spotify. Palavras genéricas só são resolvidas em um padrão de comando de app:
"música" sozinho não abre nada.

### Criar outra skill

Crie um módulo em skills e derive de Skill. Informe name, description, intents,
aliases, risk_level, requires_confirmation e rules. Cada Rule contém um padrão
para fullmatch e um resolver que retorna Intent com slots validados. Implemente
validate e execute; prepare pode capturar o snapshot da ação a confirmar.
execute retorna SkillResult com texto, status, sucesso e dados estruturados.

Instancie e registre a skill em build_registry, em skills/bootstrap.py:

```python
registry.register(MinhaSkill(meu_adaptador))
```

Não é necessário alterar o Router. Uma intent só pode pertencer a uma skill.
Registro novo incrementa a revisão do registry e atualiza as regras compiladas.
requires_confirmation=true também é aplicado à skill SAFE; DANGEROUS continua
bloqueado. Para testes, injete adaptadores falsos, sem chamar Windows ou providers.

### Logs e medição

Cada dispatch registra input normalizado de um comando local validado,
intent, confidence, skill, parâmetros canônicos, risco, provider, llm_used,
status, sucesso e os tempos normalization_ms, routing_ms, skill_ms e total_ms.
Perguntas livres, parâmetros inválidos e texto não confiável são omitidos.
Os snapshots de janelas e caminhos de pastas não são gravados no log.

O campo success indica sucesso da etapa reportada. Para verificar uma ação,
observe também status, pending_confirmation e data. Um pedido de abertura ou de
fechamento aceito não é equivalente a concluir toda a interface do aplicativo.

Os tempos medem a solicitação em um Assistant já inicializado, desde a
normalização até a resposta; não incluem iniciar o Python nem importar módulos.
Medições com test doubles são identificadas e não representam o tempo real de
abrir um aplicativo no Windows.

### Testar e gerar o relatório da fase dois

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -B -m tests.validate_phase2
.\.venv\Scripts\python.exe -B -m tests.validate_phase2 --live-brains --read-only-system
```

O primeiro comando executa todos os testes existentes, incluindo os da fase um.
O segundo executa testes e benchmark local com doubles, sem consumir providers.
O terceiro mede também Codex e Ollama reais e consulta o sistema em modo de leitura.
Se o Ollama estiver parado, inicie ollama serve antes do teste real; nenhuma chave
paga de API é usada.

O relatório phase2-validation.json contém timestamp, contagens e resultados,
regressões da fase um, intents, skills, prova de zero chamadas aos providers nos
comandos locais, benchmark e pendências da validação real do Windows. O fallback
live usa falha sintética do Codex e resposta real do Ollama, sem matar processos.

Nenhum comando desse validador da fase dois abre ou fecha apps, abre pastas, muda
foco ou altera áudio no Windows. Essas operações usam doubles e mocks nesse roteiro.
A pendência histórica de validação real foi resolvida depois, na fase 2.1,
com roteiro separado e evidências em real-windows-validation.json. A aprovação
real não foi inferida dos mocks.

### Próximos passos da fase três

Integrações dedicadas de Spotify e Discord, navegação e arquivos ficam para a
fase três. Não foram incluídos Spotify API, Discord API, modo jogo, voz, wake word,
memória avançada, GUI, bandeja, scheduler ou automação visual nesta entrega.

## Fase 2.1: validação real do Windows

A validação real foi executada e está documentada em [CURRENT_STATE.md](CURRENT_STATE.md).
O relatório [real-windows-validation.json](real-windows-validation.json) registra
os oito comandos nativos, a confirmação de fechamento, a leitura real do áudio,
Codex, fallback real para Ollama e os cento e quarenta e dois testes aprovados.
A limitação de troca de foco de Discord e Spotify foi registrada explicitamente.
Os roteiros de validação não adicionam novas skills e não são executados pela
suíte unitária padrão.

## Fase 2.5: ferramentas de qualidade

A main inclui hardening do núcleo, sem novas skills. São 195 testes e 87 subtestes;
os 142 testes anteriores foram preservados e reexecutados separadamente.
O relatório [phase2-hardening-validation.json](phase2-hardening-validation.json)
registra checks, cobertura, inventário legado e benchmark. A tag v0.2-phase2
permanece no marco estável anterior; não foi movida.

Instale as ferramentas de desenvolvimento na venv, sem mudar as dependências
mínimas de execução:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pre_commit install
.\.venv\Scripts\python.exe -m scripts.validate_hardening
```

O validador roda pip check, Ruff lint/formatação, mypy, pre-commit e pytest-cov.
Também verifica os 142 métodos de teste originais pelo inventário versionado.
Os hooks usam scripts/dev.py para localizar a venv mesmo em um git commit sem
ativação do ambiente. Se a venv não existir, usam o Python atual.

```powershell
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m mypy
.\.venv\Scripts\python.exe -m pytest --cov --cov-report=term-missing
.\.venv\Scripts\python.exe -m pytest -m unit
.\.venv\Scripts\python.exe -m pytest -m integration
.\.venv\Scripts\python.exe -m pytest -m windows
.\.venv\Scripts\python.exe -m pytest -m providers
.\.venv\Scripts\python.exe -m benchmarks.local --samples 5000 --warmup 200
```

Os grupos são diretórios e markers: unit, integration, windows e providers.
Os testes windows usam mocks das APIs nativas; não abrem apps nem mudam áudio.
Os validadores reais antigos continuam opt-in, fora da descoberta padrão.
unittest discover continua exercitando os 142 testes de classe anteriores;
pytest inclui também os novos testes de função e parametrizações.

A cobertura inclui main, config, core, brain, skills e automation, com ramificações.
O mínimo exigido é 80% combinado; a medição local foi 83.98%, ou 85.58% de linhas.
Não foram excluídos os adaptadores nativos para melhorar artificialmente a métrica.
As partes de Win32/COM não exercitadas seguem visíveis no relatório de cobertura.

mypy verifica todos os módulos de produção e os scripts/benchmarks. Contratos,
erros, intents e capabilities exigem assinaturas completas; os demais módulos
também têm seus corpos verificados, sem ignorar erros globalmente. A tipagem é
incremental, não uma declaração de strict em todo código legado.

O benchmark usa doubles, aquecimento e perf_counter_ns; retorna média, mediana,
p95, mínimo e máximo. O logging de saída é desativado para a medição e essa
condição é registrada. Não representa latência de disco, áudio, interface real
ou providers, e não consome a assinatura ChatGPT.

GitHub Actions está configurado em .github/workflows/quality.yml para Windows
com Python 3.12 e 3.13, em push para main e pull requests. Executa Ruff, mypy
e pytest-cov sem login Codex, Ollama ou segredos. As actions oficiais estão
fixadas por SHA e recebem apenas contents: read. O resultado remoto deve ser
conferido na aba Actions; o relatório local não presume sucesso no GitHub.

Referências de configuração:
[Ruff](https://docs.astral.sh/ruff/configuration/),
[mypy](https://mypy.readthedocs.io/en/stable/config_file.html),
[pytest-cov](https://pytest-cov.readthedocs.io/en/stable/config.html),
[pre-commit](https://pre-commit.com/).
