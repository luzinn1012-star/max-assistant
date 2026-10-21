# DECISIONS

Decisões técnicas consolidadas em 2026-10-21 a partir do código e das validações
existentes. O histórico Git começa com a entrega consolidada das fases 1/2/2.1;
estas entradas não representam commits antigos separados.

## D001 — Python modular e terminal primeiro

Adotar Python 3.12+, .venv e módulos separados para cérebro, roteamento, skills
e adaptadores. Manter uma interface de terminal até as etapas posteriores.
Consequência: evolução incremental sem acoplar interface e execução.

## D002 — Login oficial do Codex, sem API key como requisito

Usar codex exec com autenticação ChatGPT administrada pela CLI, sem extrair
tokens. O subprocesso é limitado a conversa e não recebe credenciais de API
herdadas do ambiente. O uso depende da disponibilidade e dos limites da conta.

## D003 — Ollama local como fallback

No modo auto, Codex é a primeira opção e Ollama qwen3:4b é a alternativa após
erro/timeout/indisponibilidade. Há cooldown para evitar tentativas repetidas.
O fallback foi validado com uma falha real do Codex. Não há troca para API paga.

## D004 — Roteamento determinístico antes do LLM

Regras e aliases registrados nas skills resolvem comandos simples localmente.
Confiança baixa, conflitos ou entradas desconhecidas vão para o cérebro.
Consequência: menor latência e nenhuma chamada de provider nos comandos locais
validados. Texto retornado pelo modelo não recebe autoridade para executar ações.

## D005 — Adaptadores diretos, sem mouse

Apps usam protocolos/executáveis conhecidos e APIs nativas. Pastas usam Known
Folders do usuário atual. Áudio usa Core Audio. Preservar caminhos dinâmicos.
O sistema pode recusar foco de janelas; não contornar essa limitação à força.

## D006 — Confirmação curta e fechamento normal

close_app exige confirmação vinculada a snapshot e à mesma sessão.
Validar identidade antes de WM_CLOSE, bloquear processos protegidos e nunca
fechar automaticamente avisos de salvamento. Não implementar kill agressivo.

## D007 — Evidência separada de intenção

Sucesso de lançamento não prova que toda a interface terminou de carregar.
Distinguir launch_requested, confirmação pendente e conclusão observada.
Manter relatórios com doubles e validação real separados, incluindo limitações.

## D008 — Dados privados fora do Git

Versionar código, exemplos sem credenciais, documentos e evidências revisadas.
Excluir .env, estado de autenticação, chaves, .venv, caches, bancos locais e logs.
O .gitignore não protege arquivos já rastreados; revisar também todo o histórico.
Relatórios reais incluem caminhos/metadados da máquina e devem permanecer em
repositório privado; publicação pública exigiria revisão própria desses dados.

## D009 — Publicação controlada e histórico sem reescrita

Destino confirmado: repositório privado luzinn1012-star/max-assistant, criado
após confirmação explícita do usuário. Conta, URL e visibilidade foram verificadas.
O histórico e a tag foram enviados com Git normal; não fazer force push.
Usar commits pequenos, Issues futuras por fase e a tag estável v0.2-phase2
após a suíte passar e as evidências da fase 2.1 serem verificadas.

## D010 — Preservar escopo de desenvolvimento

Esta entrega organiza apenas Git e documentação. Nenhuma nova skill, voz,
integração, memória persistente ou Modo Jogo é implementado. Mudanças funcionais
futuras devem referenciar uma Issue e trazer testes proporcionais ao risco.

## D011 — Contratos explícitos sem substituir integrações validadas

Formalizar WindowsAdapter e AudioDevice como Protocols e injetá-los nas skills.
Preservar WindowsBackend/Core Audio, aliases Intent/Answer e códigos de erro
anteriores. Adotar IntentResult, SkillResult e ProviderResult tipados com
validação onde o dado entra no contrato. Consequência: doubles pequenos e
checagem estática sem reimplementar ações de Windows.

## D012 — Capabilities antes de preparar e executar

Separar capability e nível de risco. A política padrão só permite operações
necessárias às skills/providers atuais; terminate, escrita e energia ficam
negados. Revalidar após confirmação. Negação é final para a solicitação,
sem fallback para outro transporte. Capabilities não são um sandbox para
plugins Python arbitrários e não acrescentam novas operações de sistema.

## D013 — Correlação sem guardar texto livre

Gerar request_id por solicitação com ContextVar, incluindo tentativas e
fallback. Registrar apenas códigos seguros e parâmetros canônicos já validados.
Manter contextos conversacionais separados por sessão; a correlação não promete
thread safety de uma instância compartilhada do Assistant.

## D014 — Checks reproduzíveis antes de novas features

Usar Ruff, mypy, pytest-cov e pre-commit com versões fixadas e workflow Windows
3.12/3.13. Cobertura mínima combinada de 80%, incluindo módulos nativos mesmo
quando não completamente cobertos. Preservar o inventário dos 142 testes.
Benchmarks com doubles indicam seu escopo e não são apresentados como tempos
reais de apps ou LLMs. A fase 3 continua não iniciada.
