# ARCHITECTURE

Estado implementado: fases 1, 2, validação 2.1 e hardening 2.5. Python 3.12+, terminal Windows.
Este documento descreve o código existente; não introduz funcionalidades futuras.

## Fluxo principal

```text
run-max.cmd -> main.py -> Assistant.ask
                         |
                         +-> normalizer -> Router -> Dispatcher
                         |                            |
                         |                 confiança suficiente
                         |                            |
                         |                 validação e permissões
                         |                            |
                         |                 Skill -> adaptador Windows
                         |
                         +-> desconhecido/ambíguo -> Codex -> Ollama
```

Comandos locais são resolvidos antes de consultar ou verificar providers.
router_threshold é configurável e vale 0.80 por padrão. O router usa fullmatch
de regras registradas pelas skills. Conflitos igualmente confiantes viram
unknown. A entrada original segue para o cérebro quando não há resolução local.
Uma falha de skill é reportada localmente, sem repetir a ação via LLM ou mouse.

## Módulos e responsabilidades

| Caminho | Responsabilidade |
| --- | --- |
| main.py, run-max.cmd | Terminal interativo, execução isolada e inicialização. |
| config.py, config.json | Validação de parâmetros simples e overrides de ambiente. |
| core/assistant.py | Composição, escolha do provider, fallback, cooldown e resposta estruturada. |
| core/normalizer.py, intent.py, router.py | Normalização, Intent/Rule e matching determinístico. |
| core/dispatcher.py, permissions.py | Execução local e confirmação de uso único na mesma sessão. |
| core/context.py | Contexto curto em RAM, sem persistência de conversa em disco. |
| core/logging_setup.py | Logs rotativos e metadados de desempenho. |
| brain/provider.py | Interface compartilhada dos providers e seus erros/diagnósticos. |
| brain/codex_provider.py | Chamada oficial codex exec; login gerenciado pela própria CLI. |
| brain/ollama_provider.py | HTTP local, modelo qwen3:4b e resposta final sem raciocínio interno. |
| skills/base.py, registry.py, bootstrap.py | Contrato de skill, registro e injeção dos adaptadores. |
| skills/apps.py, folders.py, volume.py, system.py, help.py | As cinco skills implementadas. |
| automation/windows.py | Processos/janelas, ShellExecuteW, Known Folders e métricas psutil. |
| automation/audio.py | Volume/mute por Core Audio via COM/ctypes e leitura de confirmação. |
| apps.json | Catálogo explícito de aplicativos, aliases e formas diretas de abertura. |
| tests/ | Suíte isolada, benchmarks e validadores reais opt-in. |

## Ações e segurança

SAFE permite abrir apps/pastas, alterar áudio e consultar status/ajuda.
CONFIRM é exigido para close_app. DANGEROUS existe na infraestrutura, mas sua
execução está bloqueada nesta fase. O fechamento envia WM_CLOSE somente após
confirmar o snapshot de janela/processo; não há kill forçado.

Texto produzido pelo LLM nunca é interpretado como comando do Windows.
O código não lê nem copia credenciais privadas do Codex. A CLI deve estar
autenticada com ChatGPT; não há requisito de API key paga por uso.

Ollama usa o endereço local 127.0.0.1:11434. Em provider auto, falha,
indisponibilidade ou timeout do Codex permite fallback para Ollama. Selecionar
um provider específico não desvia comandos locais para o cérebro.

## Estado e observabilidade

config.json e apps.json contêm configuração não secreta. Variáveis de ambiente
opcionais substituem campos compatíveis; .env não é carregado.
Preferências persistentes em SQLite pertencem à fase 7 e não estão implementadas.

As respostas registram rota, intent, confidence, skill, risco, provider, llm_used
e duração. Logs omitem perguntas livres e dados inválidos; arquivos de runtime,
autenticação, bancos locais e logs ficam fora do Git.

## Validação e limites

142 testes cobrem o comportamento com doubles/mocks e HTTP local de teste.
A fase 2.1 verificou oito comandos no Windows real, leituras de áudio,
CPU/RAM/disco/uptime, confirmação de fechamento e fallback com falha real do Codex.
A média interna registrada foi 122.7 ms; não é garantia de tempo em outra máquina.

Discord e Spotify foram reutilizados, porém Windows negou a troca de foco em
ambos os testes. GPU/temperatura não são estimadas. Não há voz, automação visual,
Spotify/Discord API, scheduler, tray ou inicialização automática.

Detalhes de extensão de skills e aliases estão no README. Evidências históricas
estão nos relatórios phase1-validation.json, phase2-validation.json e
real-windows-validation.json; a validação 2.1 complementa o relatório da fase 2.

## Hardening 2.5

automation/contracts.py define WindowsAdapter e AudioDevice/AudioFactory como
Protocols injetáveis. WindowsBackend e AudioEndpoint continuam sendo as
implementações nativas. Skills dependem desses contratos e não importam
subprocess, ctypes ou winreg. As chamadas à CLI Codex continuam no provider,
não nas skills; scripts de desenvolvimento podem iniciar ferramentas de teste.

IntentResult valida o formato, a confiança finita entre zero e um e os slots.
SkillResult valida seus campos, separa success/status/error e mantém dados
estruturados. ProviderResult tipa o resultado de inferência. Os nomes Intent
e Answer são aliases compatíveis, e SkillError continua compatível com
SkillExecutionError. Não é necessário reescrever consumidores anteriores.

core/errors.py define ProviderUnavailable, SkillExecutionError, PermissionDenied,
ConfirmationRequired, AppNotFound e InvalidParameter. Códigos anteriores são
preservados para não quebrar respostas estruturadas e testes.

### Capabilities

Cada skill declara capabilities por intent. O Dispatcher verifica a política
antes de prepare e execute, inclusive quando uma confirmação é consumida.
Revogar a permissão durante uma confirmação bloqueia a ação, sem nova tentativa
por LLM. O Assistant também exige network.request antes de acessar providers
e impede health checks quando a rede é negada.

| Capability | Padrão atual |
| --- | --- |
| app.launch | Permitida; abrir apps ou pastas pelas skills existentes. |
| app.close | Permitida, mas exige confirmação e fechamento normal. |
| process.inspect | Permitida para identificação e status. |
| process.terminate | Negada; não há kill forçado implementado. |
| audio.read | Permitida. |
| audio.write | Permitida. |
| filesystem.read | Permitida para pastas conhecidas. |
| filesystem.write | Negada; não há skill de escrita. |
| system.power | Negada; desligar/reiniciar não foram adicionados. |
| network.request | Permitida para os providers já existentes. |

CapabilityPolicy pode ser injetada no construtor do Assistant. As capabilities
são verificações do dispatcher para operações declaradas, não um sandbox de
execução de Python. Código de extensões continua sendo código confiável.
DANGEROUS permanece bloqueado independentemente da capability.

### Requisições e qualidade

Cada ask cria um request_id por ContextVar e restaura o contexto ao terminar.
IDs correlacionam tentativas de provider, fallback e dispatch; os logs registram
intent, confidence, skill, provider, duração, fallback e código de erro, mantendo
a omissão de texto livre e credenciais. IDs isolados não tornam o contexto
conversacional ou as confirmações compartilhadas seguros para uso simultâneo:
cada sessão continua tendo seu próprio Assistant.

Os testes estão em tests/unit, integration, windows e providers. O inventário
tests/legacy_manifest.json liga os 142 métodos originais aos caminhos novos.
A suíte atual tem 195 testes principais e 87 subtestes.

pyproject.toml centraliza Ruff, mypy, pytest e cobertura. requirements-dev.txt
fixa ferramentas e dependências, sem adicionar requisitos ao runtime.
scripts/validate_hardening.py gera o relatório local e benchmarks/local.py
mede somente o fluxo com doubles. O workflow Windows usa Python 3.12/3.13.
Cobertura real combinada local: 83.98%; não comprova exercício real de cada API.
