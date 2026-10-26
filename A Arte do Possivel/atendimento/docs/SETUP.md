# Guia de Setup Completo

## Pre-requisitos
- Conta AWS com acesso a us-east-1
- Python 3.10+ com boto3
- Acesso ao console do Amazon Connect e AgentCore

## Setup Automatizado

```bash
python3 setup.py --discover   # Descobre recursos e gera .env
source .env && python3 setup.py --run  # Executa scripts na ordem
```

## Ordem Manual

### 1. IAM Roles
```bash
source .env && python3 scripts/setup_iam.py
```
Cria: EndUserMessagingConnectRole, AgentCoreGatewayRole, LambdaMCPCursosRole, ConnectHarnessLambdaRole

### 2. DynamoDB
```bash
source .env && python3 scripts/setup_dynamodb.py
```
Cria 3 tabelas:
- `cadastro-usuarios`: PK=cpf (S), GSI=telefone-index (telefone S)
- `catalogo-cursos`: PK=curso_id (S)
- `academico`: PK=cpf (S), documento unico com disciplinas_atuais, provas, historico, financeiro

### 3. Dados Academicos
```bash
source .env && python3 scripts/setup_academico.py
```
Popula:
- `cadastro-usuarios`: usuarios de teste (alunos, pacientes)
- `catalogo-cursos`: 6 cursos de graduacao + 15 cursos de extensao
- `academico`: dados completos do aluno teste (disciplinas, provas, historico com notas/faltas/presenca, financeiro com status Pago/Nao pago)

### 4. Lambda Layer (boto3)
```bash
source .env && python3 scripts/setup_boto3_layer.py
```

### 4b. Lambda Layer (reportlab)
```bash
source .env && python3 scripts/setup_reportlab_layer.py
```
Cria layer com reportlab para geracao de PDF (usada pela Lambda mcp-boleto).

### 4c. Infraestrutura do Boleto
```bash
source .env && python3 scripts/setup_boleto_infra.py
```
Cria:
- S3 bucket `boletos-demo-{account_id}` com lifecycle de 7 dias
- IAM Role `LambdaBoletoRole` (DynamoDB read, S3 put/get, Social Messaging)
- Atualiza `AgentCoreGatewayLambdaPolicy` para incluir mcp-boleto

### 5. Lambda Functions
```bash
source .env && python3 scripts/setup_lambdas.py
```
Deploya:
- `connect-user-lookup`: busca usuario por telefone (GSI) ou CPF (PK)
- `mcp-catalogo-cursos`: lista/detalha cursos (graduacao + extensao)
- `mcp-academico`: consulta academica por CPF (disciplinas, provas, historico, financeiro)
- `mcp-boleto`: gera PDF de boleto fake e envia via WhatsApp (requer reportlab layer)

### 6. Harnesses (opcional)
```bash
source .env && python3 scripts/setup_harnesses.py
```

### 7. Gateway MCP
```bash
source .env && python3 scripts/setup_gateway.py
```
Cria 2 gateways:
- `connect-jwt-gateway`: CUSTOM_JWT auth (para Connect AI Agent)
- `harness-mcp-gateway`: AWS_IAM auth (para harnesses)

Targets em ambos: catalogo-cursos, user-lookup, academico, boleto

### 8. Knowledge Base do Vestibular
```bash
python3 scripts/gerar_edital_vestibular.py  # Gera PDF do edital
source .env && python3 scripts/setup_kb_vestibular.py  # Cria KB completa
```
Cria:
- Bucket S3 `kb-vestibular-demo-{account_id}` com PDF do edital
- IAM Role `BedrockKBVestibularRole`
- Collection OpenSearch Serverless (vector store)
- Knowledge Base no Bedrock (`kb-vestibular`)
- Data source S3 e sincroniza

Requer: `pip install opensearch-py requests-aws4auth`

### 8b. Apostilas e Material Didatico (KB)

Gerar e fazer upload de apostilas, material didatico e newsletters para a Knowledge Base:

1. Gerar ementas (PDFs de ementa para graduacao e extensao):
```bash
source .env && python3 scripts/gerar_apostilas.py
```

2. Gerar material didatico (PDFs de estudo para graduacao semestres 1-4):
```bash
source .env && python3 scripts/gerar_material_graduacao_sem1a4.py
```

3. Gerar material didatico (PDFs de estudo para graduacao semestres 5-8):
```bash
source .env && python3 scripts/gerar_material_graduacao_sem5a8.py
```

4. Gerar material didatico (PDFs de estudo para extensao):
```bash
source .env && python3 scripts/gerar_material_extensao.py
```

5. Gerar newsletters/emails (resumos por disciplina):
```bash
source .env && python3 scripts/gerar_email_graduacao.py
source .env && python3 scripts/gerar_email_extensao.py
```

6. Gerar PDF institucional e metadata do edital:
```bash
source .env && python3 scripts/gerar_edital_vestibular.py
```

7. Gerar metadata JSONs para todos os PDFs:
```bash
source .env && python3 scripts/gerar_metadata.py
```

8. Upload para S3 e re-sync da KB:
```bash
source .env && python3 scripts/upload_apostilas_s3.py
```

9. Validar indexacao (apos sync completar):
```bash
source .env && python3 scripts/test_kb_retrieve.py
```

10. Deploy da Lambda atualizada (mcp-vestibular com filtro de metadata):
```bash
source .env && python3 scripts/setup_lambdas.py
```

11. Atualizar gateway com novo target (consultar_conteudo):
```bash
source .env && python3 scripts/setup_gateway.py
```

### 9. Configuracao Manual (Console)

#### WhatsApp -> Connect
- Console End User Messaging Social > Event destination > Amazon Connect
- Selecionar instancia e role EndUserMessagingConnectRole
- NUNCA re-setar via API

#### Gateway MCP no Connect
- Console AWS > Connect > Integrations > Add integration > MCP server
- Selecionar gateway connect-jwt-gateway
- Associar instancia connect-demo-ps

#### AI Agent
- Console Connect > AI agent designer > Create AI agent (Orchestration from SelfServiceOrchestrator)
- Adicionar MCP tools do namespace do Gateway:
  - consultar_usuario
  - listar_cursos
  - detalhe_curso
  - consultar_academico
  - gerar_boleto
- Adicionar tool connect_GetContactAttributes do namespace Amazon Connect
- Atribuir Security Profile Admin com permissoes "Sufficient" para os tools
- Editar prompt (ver docs/PROMPT_COMPLETO.md)
- Definir como default Self Service agent

#### Fluxo Connect
- No editor visual do fluxo connect-whatsapp-interaction
- Bloco Set contact attributes: salvar telefone como atributo "phone"
- Bloco Set voice: pt-BR
- Bloco Get Customer Input: habilitar "Agente de IA", selecionar AI Agent
- Saida Default e NoMatchingCondition -> set-queue (pra Escalate funcionar)

## DynamoDB - Estrutura de Dados

### cadastro-usuarios
```json
{
  "cpf": "123.456.789-00",
  "nome": "Wembley Carvalho",
  "telefone": "+5511945746008",
  "tipo": "aluno",
  "status": "ativo",
  "curso": "Engenharia de Software",
  "curso_id": "eng-software"
}
```

### academico (documento unico por CPF)
```json
{
  "cpf": "123.456.789-00",
  "semestre_atual": "2026.1",
  "cr_acumulado": 8.0,
  "disciplinas_atuais": [
    {
      "nome": "Inteligencia Artificial",
      "professor": "Dr. Santos",
      "horario": "Seg/Qua 19h-21h",
      "sala": "Lab 3",
      "faltas": 2,
      "presenca_percentual": 90
    }
  ],
  "provas": [
    {
      "disciplina": "Inteligencia Artificial",
      "tipo": "P2",
      "data": "2026-05-05",
      "horario": "19:00",
      "sala": "Lab 3",
      "conteudo": "Redes Neurais, Deep Learning, NLP"
    }
  ],
  "historico": [
    {
      "semestre": "2024.1",
      "disciplinas": [
        {"nome": "Introducao a Programacao", "nota": 8.5, "status": "aprovado", "faltas": 3, "presenca_percentual": 85},
        {"nome": "Calculo I", "nota": 4.0, "status": "reprovado", "faltas": 10, "presenca_percentual": 60}
      ],
      "media_semestre": 7.2
    }
  ],
  "financeiro": [
    {"mes": "Janeiro/2026", "valor": 1200.00, "vencimento": "2026-01-10", "status": "Pago"},
    {"mes": "Maio/2026", "valor": 1200.00, "vencimento": "2026-05-10", "status": "Nao pago"}
  ]
}
```

### catalogo-cursos
```json
{
  "curso_id": "eng-software",
  "nome": "Engenharia de Software",
  "area": "Tecnologia",
  "modalidade": "Presencial",
  "duracao_semestres": 8,
  "vagas_disponiveis": 40,
  "mensalidade": 1200.00,
  "grade_curricular": {
    "1_semestre": ["Introducao a Programacao", "Logica Matematica", ...],
    "2_semestre": [...]
  }
}
```
Cursos de extensao tem `tipo=extensao`, `duracao_horas`, `duracao_meses` em vez de `duracao_semestres`.

## Utilitarios
```bash
source .env && python3 scripts/manage_sessions.py        # Listar sessoes
source .env && python3 scripts/manage_sessions.py kill    # Matar todas
source .env && python3 tests/test_harness.py "mensagem"  # Testar harness
source .env && python3 tests/list_memory.py               # Listar memoria
```

## Troubleshooting

### MCP tools falham ("dificuldades tecnicas")
1. Verificar log: /aws/vendedlogs/bedrock-agentcore/gateway/APPLICATION_LOGS/<gateway-id>
2. Se "Authorization error - Insufficient permissions":
   - Resource policy DEVE usar Principal: * (NAO Service: connect.amazonaws.com)
   - allowedAudience DEVE ser o Gateway ID
3. Se Lambda nao invocada: verificar Gateway role tem lambda:InvokeFunction
4. Se Lambda da erro: verificar logs em /aws/lambda/<function-name>

### WhatsApp nao responde
1. Verificar event destination no console End User Messaging
2. Verificar phone number importado no Connect (Channels > Phone numbers)
3. Verificar fluxo associado ao phone number
4. Matar sessoes ativas: python3 scripts/manage_sessions.py kill
5. NUNCA re-setar event destination via API

### AI Agent nao aparece no Connect
- Criar pelo console (NAO via API)
- Habilitar "Agente de IA" no bloco Get Customer Input do fluxo
- Prompt deve ser editado pelo console (API cria prompts incompativeis)

### Escalate nao transfere pra fila
- No fluxo, saida NoMatchingCondition do bloco Lex deve ir pra set-queue (nao disconnect)

### Sessoes de chat ficam ativas
- Sessoes ficam ativas mesmo apos encerrar no CCP
- Novas mensagens vao pra sessao ativa existente (nao pro AI Agent)
- Usar `python3 scripts/manage_sessions.py kill` antes de testar
