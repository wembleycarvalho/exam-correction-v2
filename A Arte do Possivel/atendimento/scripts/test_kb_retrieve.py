"""
Teste de retrieve da Knowledge Base com filtros de metadata.
Valida que os documentos foram indexados corretamente e que os filtros
de metadata funcionam para controle de acesso.

Testes:
  1. Retrieve sem filtro — deve retornar resultados de qualquer documento
  2. Retrieve com filtro tipo=publico — deve retornar apenas conteudo publico
  3. Retrieve com filtro disciplina IN [...] — deve retornar conteudo da disciplina
  4. Retrieve com filtro combinado orAll — deve retornar publico + disciplinas permitidas

Uso: source .env && python3 scripts/test_kb_retrieve.py
"""
import boto3
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from env_helper import require_env, get_env

KB_ID = require_env('KB_VESTIBULAR_ID')
REGION = get_env('AWS_REGION', 'us-east-1')

bedrock_runtime = boto3.client('bedrock-agent-runtime', region_name=REGION)

# Contadores globais de resultado
total_tests = 0
passed_tests = 0
failed_tests = 0


def retrieve(query, retrieval_filter=None, num_results=5):
    """Executa retrieve na KB com filtro opcional de metadata."""
    config = {
        'vectorSearchConfiguration': {
            'numberOfResults': num_results
        }
    }
    if retrieval_filter:
        config['vectorSearchConfiguration']['filter'] = retrieval_filter

    resp = bedrock_runtime.retrieve(
        knowledgeBaseId=KB_ID,
        retrievalQuery={'text': query},
        retrievalConfiguration=config
    )
    return resp.get('retrievalResults', [])


def print_results(results, label):
    """Imprime os resultados de forma legivel."""
    print(f'\n  Resultados ({len(results)} encontrados):')
    if not results:
        print('    (nenhum resultado)')
        return

    for i, r in enumerate(results, 1):
        score = r.get('score', 0)
        text_preview = r.get('content', {}).get('text', '')[:120].replace('\n', ' ')
        metadata = r.get('metadata', {})

        # Extrair info da location (URI do S3)
        location = r.get('location', {})
        s3_uri = location.get('s3Location', {}).get('uri', 'N/A') if location.get('type') == 'S3' else 'N/A'

        print(f'    [{i}] score={score:.4f}')
        print(f'        S3: {s3_uri}')
        if metadata:
            print(f'        metadata: {json.dumps(metadata, ensure_ascii=False)}')
        print(f'        texto: {text_preview}...')


def check_results_have_metadata(results, key, expected_values, label):
    """Verifica se todos os resultados possuem metadata com valores esperados."""
    global passed_tests, failed_tests

    if not results:
        print(f'  ⚠ AVISO: Nenhum resultado retornado para verificar ({label})')
        return False

    all_ok = True
    for i, r in enumerate(results, 1):
        metadata = r.get('metadata', {})
        value = metadata.get(key, None)

        if expected_values is None:
            # Apenas verifica que retornou algo
            continue

        if isinstance(expected_values, list):
            if value not in expected_values:
                print(f'  ✗ Resultado [{i}]: metadata[{key}]={value}, esperado um de {expected_values}')
                all_ok = False
        else:
            if value != expected_values:
                print(f'  ✗ Resultado [{i}]: metadata[{key}]={value}, esperado={expected_values}')
                all_ok = False

    return all_ok


# ============================================================
# TESTE 1: Retrieve sem filtro
# ============================================================
def test_no_filter():
    global total_tests, passed_tests, failed_tests
    total_tests += 1

    print('\n' + '=' * 60)
    print('TESTE 1: Retrieve sem filtro')
    print('  Expectativa: retornar resultados de qualquer documento')
    print('=' * 60)

    query = 'Quais sao os cursos oferecidos pela instituicao?'
    print(f'  Query: "{query}"')

    try:
        results = retrieve(query)
        print_results(results, 'sem filtro')

        if len(results) > 0:
            print(f'\n  ✓ PASSOU — {len(results)} resultados retornados sem filtro')
            passed_tests += 1
        else:
            print('\n  ✗ FALHOU — nenhum resultado retornado (KB pode estar vazia ou nao sincronizada)')
            failed_tests += 1

    except Exception as e:
        print(f'\n  ✗ ERRO — {e}')
        failed_tests += 1


# ============================================================
# TESTE 2: Retrieve com filtro tipo=publico
# ============================================================
def test_tipo_publico():
    global total_tests, passed_tests, failed_tests
    total_tests += 1

    print('\n' + '=' * 60)
    print('TESTE 2: Retrieve com filtro tipo=publico')
    print('  Expectativa: retornar apenas conteudo publico (edital, institucional)')
    print('=' * 60)

    query = 'Informacoes sobre o vestibular e a instituicao'
    filtro = {'equals': {'key': 'tipo', 'value': 'publico'}}
    print(f'  Query: "{query}"')
    print(f'  Filtro: {json.dumps(filtro, ensure_ascii=False)}')

    try:
        results = retrieve(query, retrieval_filter=filtro)
        print_results(results, 'tipo=publico')

        if len(results) == 0:
            print('\n  ✗ FALHOU — nenhum resultado retornado com filtro tipo=publico')
            failed_tests += 1
            return

        # Verificar que todos os resultados sao publicos
        all_public = True
        for i, r in enumerate(results, 1):
            metadata = r.get('metadata', {})
            tipo = metadata.get('tipo', 'N/A')
            if tipo != 'publico':
                print(f'  ✗ Resultado [{i}] tem tipo={tipo}, esperado tipo=publico')
                all_public = False

        if all_public:
            print(f'\n  ✓ PASSOU — todos os {len(results)} resultados sao tipo=publico')
            passed_tests += 1
        else:
            print(f'\n  ✗ FALHOU — alguns resultados nao sao tipo=publico')
            failed_tests += 1

    except Exception as e:
        print(f'\n  ✗ ERRO — {e}')
        failed_tests += 1


# ============================================================
# TESTE 3: Retrieve com filtro disciplina IN [...]
# ============================================================
def test_disciplina_filter():
    global total_tests, passed_tests, failed_tests
    total_tests += 1

    print('\n' + '=' * 60)
    print('TESTE 3: Retrieve com filtro disciplina IN [...]')
    print('  Expectativa: retornar conteudo apenas da disciplina filtrada')
    print('=' * 60)

    disciplinas_filtro = ['Introducao a Programacao (Python)']
    query = 'O que se aprende em programacao Python?'
    filtro = {'in': {'key': 'disciplina', 'value': disciplinas_filtro}}
    print(f'  Query: "{query}"')
    print(f'  Filtro: {json.dumps(filtro, ensure_ascii=False)}')

    try:
        results = retrieve(query, retrieval_filter=filtro)
        print_results(results, 'disciplina filter')

        if len(results) == 0:
            print('\n  ✗ FALHOU — nenhum resultado retornado com filtro de disciplina')
            failed_tests += 1
            return

        # Verificar que todos os resultados sao da disciplina filtrada
        all_match = True
        for i, r in enumerate(results, 1):
            metadata = r.get('metadata', {})
            disc = metadata.get('disciplina', 'N/A')
            if disc not in disciplinas_filtro:
                print(f'  ✗ Resultado [{i}] tem disciplina={disc}, esperado uma de {disciplinas_filtro}')
                all_match = False

        if all_match:
            print(f'\n  ✓ PASSOU — todos os {len(results)} resultados sao da disciplina filtrada')
            passed_tests += 1
        else:
            print(f'\n  ✗ FALHOU — alguns resultados nao correspondem a disciplina filtrada')
            failed_tests += 1

    except Exception as e:
        print(f'\n  ✗ ERRO — {e}')
        failed_tests += 1


# ============================================================
# TESTE 4: Retrieve com filtro combinado orAll
# ============================================================
def test_combined_filter():
    global total_tests, passed_tests, failed_tests
    total_tests += 1

    print('\n' + '=' * 60)
    print('TESTE 4: Retrieve com filtro combinado orAll')
    print('  Expectativa: retornar conteudo publico + disciplinas permitidas')
    print('  Simula o filtro de um aluno do 1o semestre de Eng. Software')
    print('=' * 60)

    disciplinas_permitidas = [
        'Introducao a Programacao (Python)',
        'Logica Matematica',
        'Calculo I',
        'Comunicacao e Expressao',
        'Fundamentos de Computacao'
    ]

    query = 'Conte sobre a instituicao e sobre programacao'
    filtro = {
        'orAll': [
            {'equals': {'key': 'tipo', 'value': 'publico'}},
            {'in': {'key': 'disciplina', 'value': disciplinas_permitidas}}
        ]
    }
    print(f'  Query: "{query}"')
    print(f'  Filtro: orAll [tipo=publico, disciplina IN {disciplinas_permitidas[:2]}...]')

    try:
        results = retrieve(query, retrieval_filter=filtro)
        print_results(results, 'orAll combinado')

        if len(results) == 0:
            print('\n  ✗ FALHOU — nenhum resultado retornado com filtro combinado')
            failed_tests += 1
            return

        # Verificar que cada resultado e publico OU de uma disciplina permitida
        all_valid = True
        for i, r in enumerate(results, 1):
            metadata = r.get('metadata', {})
            tipo = metadata.get('tipo', 'N/A')
            disc = metadata.get('disciplina', None)

            is_public = (tipo == 'publico')
            is_allowed_disc = (disc in disciplinas_permitidas) if disc else False

            if not is_public and not is_allowed_disc:
                print(f'  ✗ Resultado [{i}] tipo={tipo}, disciplina={disc} — nao e publico nem disciplina permitida')
                all_valid = False

        if all_valid:
            print(f'\n  ✓ PASSOU — todos os {len(results)} resultados sao publicos ou de disciplinas permitidas')
            passed_tests += 1
        else:
            print(f'\n  ✗ FALHOU — alguns resultados nao correspondem ao filtro combinado')
            failed_tests += 1

    except Exception as e:
        print(f'\n  ✗ ERRO — {e}')
        failed_tests += 1


# ============================================================
# TESTE 5 (bonus): Verificar que filtro bloqueia disciplinas nao permitidas
# ============================================================
def test_blocked_discipline():
    global total_tests, passed_tests, failed_tests
    total_tests += 1

    print('\n' + '=' * 60)
    print('TESTE 5 (bonus): Verificar bloqueio de disciplinas nao permitidas')
    print('  Expectativa: com filtro de 1o semestre, NAO retornar disciplinas do 5o+')
    print('=' * 60)

    # Simula aluno do 1o semestre — so tem acesso a 5 disciplinas
    disciplinas_sem1 = [
        'Introducao a Programacao (Python)',
        'Logica Matematica',
        'Calculo I',
        'Comunicacao e Expressao',
        'Fundamentos de Computacao'
    ]

    # Disciplinas que NAO devem aparecer (semestres 5+)
    disciplinas_bloqueadas = [
        'DevOps e Cloud Computing',
        'Inteligencia Artificial',
        'Machine Learning',
        'Big Data',
        'Blockchain'
    ]

    query = 'O que e DevOps e inteligencia artificial?'
    filtro = {
        'orAll': [
            {'equals': {'key': 'tipo', 'value': 'publico'}},
            {'in': {'key': 'disciplina', 'value': disciplinas_sem1}}
        ]
    }
    print(f'  Query: "{query}"')
    print(f'  Filtro: orAll [tipo=publico, disciplina IN (apenas 1o semestre)]')

    try:
        results = retrieve(query, retrieval_filter=filtro)
        print_results(results, 'bloqueio disciplinas')

        # Verificar que nenhum resultado e de disciplina bloqueada
        has_blocked = False
        for i, r in enumerate(results, 1):
            metadata = r.get('metadata', {})
            disc = metadata.get('disciplina', None)
            if disc in disciplinas_bloqueadas:
                print(f'  ✗ Resultado [{i}] retornou disciplina bloqueada: {disc}')
                has_blocked = True

        if not has_blocked:
            print(f'\n  ✓ PASSOU — nenhuma disciplina bloqueada foi retornada')
            passed_tests += 1
        else:
            print(f'\n  ✗ FALHOU — disciplinas bloqueadas foram retornadas (filtro nao funcionou)')
            failed_tests += 1

    except Exception as e:
        print(f'\n  ✗ ERRO — {e}')
        failed_tests += 1


# ============================================================
# MAIN
# ============================================================
if __name__ == '__main__':
    print('=' * 60)
    print(f'  Teste de Retrieve da KB com Filtros de Metadata')
    print(f'  KB ID: {KB_ID}')
    print(f'  Region: {REGION}')
    print('=' * 60)

    test_no_filter()
    test_tipo_publico()
    test_disciplina_filter()
    test_combined_filter()
    test_blocked_discipline()

    # Resumo
    print('\n' + '=' * 60)
    print(f'  RESUMO: {passed_tests}/{total_tests} testes passaram')
    if failed_tests > 0:
        print(f'  {failed_tests} teste(s) falharam')
    print('=' * 60)

    sys.exit(0 if failed_tests == 0 else 1)
