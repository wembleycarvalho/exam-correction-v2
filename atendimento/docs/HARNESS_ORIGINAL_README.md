# Assistente Virtual - Educacao e Saude

Assistente virtual via WhatsApp integrado com Amazon Connect AI Agent, AgentCore Gateway MCP e DynamoDB.

Atende dois dominios: **Educacao** (cursos, matriculas, notas, provas, financeiro, boletos, vestibular) e **Saude** (consultas, exames, cobrancas). Identifica automaticamente o usuario pelo telefone, chama pelo nome e personaliza o atendimento.

## Arquitetura

```
WhatsApp -> End User Messaging -> Amazon Connect -> AI Agent (Orchestration)
                                                        |
                                                        +-- connect_GetContactAttributes (telefone)
                                                        +-- consultar_usuario (telefone -> CPF + dados)
                                                        +-- listar_cursos (graduacao + extensao)
                                                        +-- detalhe_curso (ementa, diferenciais)
                                                        +-- consultar_academico (notas, provas, historico, financeiro)
                                                        +-- gerar_boleto (PDF fake -> S3 -> WhatsApp)
                                                        +-- Escalate -> fila -> agente humano
```

MCP tools expostas via AgentCore Gateway com autenticacao JWT do Connect.

## Estrutura

```
├── setup.py                    # Setup completo (--discover / --run)
├── .env.example                # Template de variaveis
├── docs/
│   ├── ARQUITETURA.md          # Componentes e configuracoes criticas
│   ├── SETUP.md                # Guia passo a passo
│   └── PROMPT_COMPLETO.md      # Prompt do AI Agent
├── lambdas/
│   ├── mcp_catalogo_cursos.py  # Lista/detalha cursos
│   ├── connect_user_lookup.py  # Busca usuario por telefone/CPF
│   ├── mcp_academico.py        # Disciplinas, notas, provas, financeiro
│   └── mcp_boleto.py           # Gera PDF boleto fake e envia via WhatsApp
├── scripts/
│   ├── env_helper.py           # Propaga variaveis entre scripts
│   ├── setup_*.py              # Scripts de infraestrutura
│   ├── manage_sessions.py      # Monitor/kill sessoes de chat
│   └── check_logs.py           # Verifica logs
└── tests/
    ├── test_harness.py         # Teste do harness via CLI
    └── list_memory.py          # Lista memoria do AgentCore
```

## Quick Start

```bash
python3 setup.py --discover
vi .env
source .env && python3 setup.py --run
# Configuracao manual no console (ver docs/SETUP.md)
```

## Regras de Negocio

- Identifica usuario pelo telefone automaticamente (sem perguntar)
- Chama pelo nome quando cadastrado
- Nunca exibe valores a menos que pergunte
- Alunos adimplentes recebem sugestao de cursos de extensao
- Disciplinas reprovadas sao informadas proativamente
- Presenca abaixo de 75% gera alerta
- Financeiro: status Pago/Nao pago, AI Agent deduz vencido/a vencer pela data
- Segunda via de boleto: PDF fake enviado como documento no WhatsApp com linha digitavel
- Vestibular: Knowledge Base do Bedrock com edital completo, respostas sobre processo seletivo
- Escalate transfere pra fila de agente humano

## Documentacao

- [Arquitetura detalhada](docs/ARQUITETURA.md)
- [Guia de setup](docs/SETUP.md)
- [Prompt do AI Agent](docs/PROMPT_COMPLETO.md)
