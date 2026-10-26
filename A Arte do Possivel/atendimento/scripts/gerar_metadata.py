"""
Gera arquivos .metadata.json para cada PDF de ementa/material/email na Knowledge Base.
Escaneia output/apostilas/ e gera metadata correspondente usando os dados de
GRADE_CURRICULAR e CURSOS_EXTENSAO (mesmos de gerar_apostilas.py e setup_academico.py).

Tipos de PDF suportados:
  - {slug}.pdf           -> ementa
  - {slug}_material.pdf  -> material didatico
  - {slug}_email.pdf     -> email/newsletter

Formato metadata graduacao:
{
  "metadataAttributes": {
    "tipo": "disciplina",
    "modalidade": "graduacao",
    "curso_id": "eng-software",
    "disciplina": "Introducao a Programacao (Python)",
    "semestre": "1"
  }
}

Formato metadata extensao:
{
  "metadataAttributes": {
    "tipo": "disciplina",
    "modalidade": "extensao",
    "curso_id": "ext-ia-aplicada",
    "disciplina": "Inteligencia Artificial Aplicada"
  }
}

Uso: python3 scripts/gerar_metadata.py
"""
import os
import re
import json

# ============================================================
# Diretorio base
# ============================================================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, 'output', 'apostilas')

CURSO_ID_GRAD = 'eng-software'

# ============================================================
# Grade curricular (mesma de setup_academico.py / gerar_apostilas.py)
# ============================================================
GRADE_CURRICULAR = {
    '1_semestre': ['Introducao a Programacao (Python)', 'Logica Matematica', 'Calculo I', 'Comunicacao e Expressao', 'Fundamentos de Computacao'],
    '2_semestre': ['Estrutura de Dados', 'Programacao Orientada a Objetos', 'Calculo II', 'Banco de Dados I', 'Sistemas Operacionais'],
    '3_semestre': ['Engenharia de Software I', 'Redes de Computadores', 'Estatistica', 'Banco de Dados II', 'Desenvolvimento Web'],
    '4_semestre': ['Engenharia de Software II', 'Arquitetura de Software', 'Testes de Software', 'Desenvolvimento Mobile', 'Projeto Integrador I'],
    '5_semestre': ['DevOps e Cloud Computing', 'Inteligencia Artificial', 'Seguranca da Informacao', 'Metodologias Ageis', 'Estagio Supervisionado I'],
    '6_semestre': ['Microsservicos e APIs', 'Machine Learning', 'Gestao de Projetos', 'UX/UI Design', 'Estagio Supervisionado II'],
    '7_semestre': ['Computacao em Nuvem Avancada', 'Big Data', 'Empreendedorismo Digital', 'Etica em TI', 'TCC I'],
    '8_semestre': ['IoT e Sistemas Embarcados', 'Blockchain', 'Inovacao Tecnologica', 'TCC II', 'Projeto Final'],
}

# ============================================================
# Cursos de extensao (mesmos de setup_academico.py / gerar_apostilas.py)
# ============================================================
CURSOS_EXTENSAO = [
    {'curso_id': 'ext-ia-aplicada', 'nome': 'Inteligencia Artificial Aplicada'},
    {'curso_id': 'ext-cybersecurity', 'nome': 'Cybersecurity Essentials'},
    {'curso_id': 'ext-data-science', 'nome': 'Data Science com Python'},
    {'curso_id': 'ext-cloud-aws', 'nome': 'Cloud Computing com AWS'},
    {'curso_id': 'ext-ux-design', 'nome': 'UX/UI Design'},
    {'curso_id': 'ext-gestao-projetos', 'nome': 'Gestao de Projetos e Metodologias Ageis'},
    {'curso_id': 'ext-marketing-digital', 'nome': 'Marketing Digital e Analytics'},
    {'curso_id': 'ext-devops', 'nome': 'DevOps e CI/CD'},
    {'curso_id': 'ext-blockchain', 'nome': 'Blockchain e Web3'},
    {'curso_id': 'ext-lideranca', 'nome': 'Lideranca e Gestao de Pessoas'},
    {'curso_id': 'ext-saude-mental', 'nome': 'Saude Mental no Trabalho'},
    {'curso_id': 'ext-primeiros-socorros', 'nome': 'Primeiros Socorros e Urgencias'},
    {'curso_id': 'ext-nutricao-esportiva', 'nome': 'Nutricao Esportiva'},
    {'curso_id': 'ext-direito-digital', 'nome': 'Direito Digital e LGPD'},
    {'curso_id': 'ext-ingles-negocios', 'nome': 'Ingles para Negocios'},
]


def sanitize_filename(nome):
    """Converte nome de disciplina em nome de arquivo seguro.
    Mesma logica de gerar_apostilas.py para garantir correspondencia."""
    nome = nome.lower()
    nome = nome.replace('(', '').replace(')', '').replace('/', '_')
    nome = re.sub(r'[^a-z0-9_]', '_', nome)
    nome = re.sub(r'_+', '_', nome).strip('_')
    return nome


def build_grad_lookup():
    """Constroi mapa: sanitized_filename -> (disciplina_original, semestre_num)"""
    lookup = {}
    for semestre_key, disciplinas in GRADE_CURRICULAR.items():
        semestre_num = int(semestre_key.split('_')[0])
        for disciplina in disciplinas:
            slug = sanitize_filename(disciplina)
            lookup[slug] = (disciplina, str(semestre_num))
    return lookup


def build_ext_lookup():
    """Constroi mapa: sanitized_filename -> (nome_original, curso_id)"""
    lookup = {}
    for curso in CURSOS_EXTENSAO:
        slug = sanitize_filename(curso['nome'])
        lookup[slug] = (curso['nome'], curso['curso_id'])
    return lookup


def write_metadata(filepath, metadata):
    """Escreve arquivo .metadata.json ao lado do PDF."""
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)


def main():
    grad_lookup = build_grad_lookup()
    ext_lookup = build_ext_lookup()

    total_grad = 0
    total_ext = 0
    warnings = []

    # --- Graduacao ---
    grad_dir = os.path.join(OUTPUT_DIR, 'privado', 'graduacao', CURSO_ID_GRAD)
    if os.path.isdir(grad_dir):
        print('=== Gerando metadata para graduacao (Eng. Software) ===')
        for filename in sorted(os.listdir(grad_dir)):
            if not filename.endswith('.pdf'):
                continue

            # Extrair slug: remove .pdf e _material/_email suffix
            slug = filename[:-4]  # remove .pdf
            is_material = slug.endswith('_material')
            is_email = slug.endswith('_email')
            if is_material:
                slug = slug[:-9]  # remove _material
            elif is_email:
                slug = slug[:-6]  # remove _email

            if slug not in grad_lookup:
                warnings.append(f'  WARN: Sem mapeamento para "{filename}" (slug: {slug})')
                continue

            disciplina, semestre = grad_lookup[slug]
            metadata = {
                'metadataAttributes': {
                    'tipo': 'disciplina',
                    'modalidade': 'graduacao',
                    'curso_id': CURSO_ID_GRAD,
                    'disciplina': disciplina,
                    'semestre': semestre,
                }
            }

            meta_path = os.path.join(grad_dir, filename + '.metadata.json')
            write_metadata(meta_path, metadata)
            total_grad += 1
            tipo_label = 'material' if is_material else ('email' if is_email else 'ementa')
            print(f'  [{semestre}o sem] {disciplina} ({tipo_label}) -> {filename}.metadata.json')
    else:
        print(f'WARN: Diretorio de graduacao nao encontrado: {grad_dir}')

    # --- Extensao ---
    ext_base = os.path.join(OUTPUT_DIR, 'privado', 'extensao')
    if os.path.isdir(ext_base):
        print('\n=== Gerando metadata para extensao ===')
        for curso_dir_name in sorted(os.listdir(ext_base)):
            curso_dir = os.path.join(ext_base, curso_dir_name)
            if not os.path.isdir(curso_dir):
                continue

            for filename in sorted(os.listdir(curso_dir)):
                if not filename.endswith('.pdf'):
                    continue

                # Extrair slug: remove .pdf e _material/_email suffix
                slug = filename[:-4]  # remove .pdf
                is_material = slug.endswith('_material')
                is_email = slug.endswith('_email')
                if is_material:
                    slug = slug[:-9]  # remove _material
                elif is_email:
                    slug = slug[:-6]  # remove _email

                if slug not in ext_lookup:
                    warnings.append(f'  WARN: Sem mapeamento para "{curso_dir_name}/{filename}" (slug: {slug})')
                    continue

                nome_curso, curso_id = ext_lookup[slug]
                metadata = {
                    'metadataAttributes': {
                        'tipo': 'disciplina',
                        'modalidade': 'extensao',
                        'curso_id': curso_id,
                        'disciplina': nome_curso,
                    }
                }

                meta_path = os.path.join(curso_dir, filename + '.metadata.json')
                write_metadata(meta_path, metadata)
                total_ext += 1
                tipo_label = 'material' if is_material else ('email' if is_email else 'ementa')
                print(f'  {nome_curso} ({tipo_label}) -> {curso_dir_name}/{filename}.metadata.json')
    else:
        print(f'WARN: Diretorio de extensao nao encontrado: {ext_base}')

    # --- Warnings ---
    if warnings:
        print('\n=== Warnings ===')
        for w in warnings:
            print(w)

    # --- Resumo ---
    total = total_grad + total_ext
    print(f'\nDone!')
    print(f'  Graduacao: {total_grad} metadata JSONs')
    print(f'  Extensao:  {total_ext} metadata JSONs')
    print(f'  TOTAL:     {total} metadata JSONs gerados')
    print(f'  Diretorio: {OUTPUT_DIR}')


if __name__ == '__main__':
    main()
