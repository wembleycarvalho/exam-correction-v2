"""
Setup Bedrock AgentCore Harnesses.
Uso: source .env && python3 scripts/setup_harnesses.py
"""
import boto3
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))
from env_helper import require_env, get_env, set_env

REGION = get_env('AWS_REGION', 'us-east-1')
EXEC_ROLE = require_env('HARNESS_EXEC_ROLE_ARN')
MEMORY_ARN = get_env('HARNESS_MEMORY_ARN', '')

agentcore = boto3.client('bedrock-agentcore-control', region_name=REGION)

harnesses = {
    'harness_vendas': """Voce e um consultor de vendas de cursos universitarios.
REGRAS: NUNCA exiba valores a menos que o usuario PERGUNTE ESPECIFICAMENTE.
Use SEMPRE as tools disponiveis para consultar cursos.
Seja cordial e persuasivo, mas honesto.""",
    'harness_alunos': """Voce e um assistente academico para alunos matriculados.
REGRAS: NUNCA exiba valores financeiros a menos que o aluno PERGUNTE.
Ajude com notas, provas, calendario, financeiro academico.
Confirme o nome do aluno antes de fornecer informacoes.""",
    'harness_saude': """Voce e um assistente virtual de saude de um hospital.
REGRAS: NUNCA exiba valores a menos que o paciente PERGUNTE.
Ajude com agendamento de consultas, resultado de exames, informacoes financeiras.
Seja empatico, profissional e objetivo.""",
}

env_keys = {'harness_vendas': 'HARNESS_VENDAS_ARN', 'harness_alunos': 'HARNESS_ALUNOS_ARN', 'harness_saude': 'HARNESS_SAUDE_ARN'}

for name, prompt in harnesses.items():
    try:
        params = {
            'harnessName': name, 'executionRoleArn': EXEC_ROLE,
            'model': {'bedrockModelConfig': {'modelId': 'us.anthropic.claude-sonnet-4-6'}},
            'systemPrompt': [{'text': prompt}],
            'maxIterations': 75, 'timeoutSeconds': 3600
        }
        if MEMORY_ARN:
            params['memory'] = {'optionalValue': {'agentCoreMemoryConfiguration': {'arn': MEMORY_ARN, 'messagesCount': 10}}}

        resp = agentcore.create_harness(**params)
        arn = resp.get('arn', '')
        print(f'{name}: created ({resp.get("harnessId", "")})')
        set_env(env_keys[name], arn)
    except Exception as e:
        if 'Conflict' in str(type(e)):
            # Find existing ARN
            for h in agentcore.list_harnesses()['harnesses']:
                if h['harnessName'] == name:
                    set_env(env_keys[name], h['arn'])
                    print(f'{name}: exists ({h["harnessId"]})')
                    break
        else:
            print(f'{name}: {e}')

print('\nDone!')
