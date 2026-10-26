"""
Setup academico: popula tabelas DynamoDB com dados de teste.
Tabelas devem existir (criadas por setup_dynamodb.py):
  - cadastro-usuarios (PK=cpf, GSI=telefone-index)
  - catalogo-cursos (PK=curso_id)
  - academico (PK=cpf, documento unico)

Uso: source .env && python3 scripts/setup_academico.py
"""
import boto3
import json
from decimal import Decimal

REGION = 'us-east-1'
dynamodb = boto3.resource('dynamodb', region_name=REGION)

# ============================================================
# STEP 1: Populate cadastro-usuarios
# ============================================================
print('=== cadastro-usuarios ===')
tbl_usuarios = dynamodb.Table('cadastro-usuarios')

usuarios = [
    {
        'cpf': '123.456.789-00',
        'nome': 'Wembley Carvalho',
        'telefone': '+5511945746008',
        'tipo': 'aluno',
        'status': 'ativo',
        'curso': 'Engenharia de Software',
        'curso_id': 'eng-software'
    },
    {
        'cpf': '987.654.321-00',
        'nome': 'Maria Silva',
        'telefone': '+5511999998888',
        'tipo': 'paciente',
        'status': 'ativo',
        'especialidade': 'Cardiologia'
    },
    {
        'cpf': '111.222.333-44',
        'nome': 'Joao Santos',
        'telefone': '+5511977776666',
        'tipo': 'aluno',
        'status': 'ativo',
        'curso': 'Ciencia da Computacao',
        'curso_id': 'ciencia-computacao'
    }
]

for u in usuarios:
    tbl_usuarios.put_item(Item=u)
print(f'  {len(usuarios)} usuarios inseridos')

# ============================================================
# STEP 2: Populate catalogo-cursos (graduacao + extensao)
# ============================================================
print('\n=== catalogo-cursos ===')
tbl_cursos = dynamodb.Table('catalogo-cursos')

cursos_graduacao = [
    {
        'curso_id': 'eng-software',
        'nome': 'Engenharia de Software',
        'area': 'Tecnologia',
        'modalidade': 'Presencial',
        'duracao_semestres': 8,
        'vagas_disponiveis': 40,
        'mensalidade': Decimal('1200.00'),
        'diferenciais': 'Laboratorios modernos, parcerias com empresas de tecnologia, projetos praticos desde o 1o semestre',
        'mercado': 'Desenvolvedores, arquitetos de software, tech leads, CTOs',
        'grade_curricular': {
            '1_semestre': ['Introducao a Programacao (Python)', 'Logica Matematica', 'Calculo I', 'Comunicacao e Expressao', 'Fundamentos de Computacao'],
            '2_semestre': ['Estrutura de Dados', 'Programacao Orientada a Objetos', 'Calculo II', 'Banco de Dados I', 'Sistemas Operacionais'],
            '3_semestre': ['Engenharia de Software I', 'Redes de Computadores', 'Estatistica', 'Banco de Dados II', 'Desenvolvimento Web'],
            '4_semestre': ['Engenharia de Software II', 'Arquitetura de Software', 'Testes de Software', 'Desenvolvimento Mobile', 'Projeto Integrador I'],
            '5_semestre': ['DevOps e Cloud Computing', 'Inteligencia Artificial', 'Seguranca da Informacao', 'Metodologias Ageis', 'Estagio Supervisionado I'],
            '6_semestre': ['Microsservicos e APIs', 'Machine Learning', 'Gestao de Projetos', 'UX/UI Design', 'Estagio Supervisionado II'],
            '7_semestre': ['Computacao em Nuvem Avancada', 'Big Data', 'Empreendedorismo Digital', 'Etica em TI', 'TCC I'],
            '8_semestre': ['IoT e Sistemas Embarcados', 'Blockchain', 'Inovacao Tecnologica', 'TCC II', 'Projeto Final']
        }
    },
    {
        'curso_id': 'ciencia-computacao',
        'nome': 'Ciencia da Computacao',
        'area': 'Tecnologia',
        'modalidade': 'Presencial',
        'duracao_semestres': 8,
        'vagas_disponiveis': 35,
        'mensalidade': Decimal('1150.00'),
        'diferenciais': 'Foco em pesquisa e inovacao, laboratorios de IA e computacao de alto desempenho',
        'mercado': 'Pesquisadores, cientistas de dados, engenheiros de ML, desenvolvedores de sistemas'
    },
    {
        'curso_id': 'ads',
        'nome': 'Analise e Desenvolvimento de Sistemas',
        'area': 'Tecnologia',
        'modalidade': 'EAD',
        'duracao_semestres': 5,
        'vagas_disponiveis': 60,
        'mensalidade': Decimal('650.00'),
        'diferenciais': 'Curso 100% online, foco pratico, certificacoes intermediarias',
        'mercado': 'Desenvolvedores full-stack, analistas de sistemas, programadores'
    },
    {
        'curso_id': 'enfermagem',
        'nome': 'Enfermagem',
        'area': 'Saude',
        'modalidade': 'Presencial',
        'duracao_semestres': 10,
        'vagas_disponiveis': 50,
        'mensalidade': Decimal('1800.00'),
        'diferenciais': 'Hospital-escola proprio, estagios desde o 3o semestre, laboratorios de simulacao',
        'mercado': 'Enfermeiros, gestores de saude, pesquisadores em saude'
    },
    {
        'curso_id': 'administracao',
        'nome': 'Administracao',
        'area': 'Negocios',
        'modalidade': 'Presencial',
        'duracao_semestres': 8,
        'vagas_disponiveis': 45,
        'mensalidade': Decimal('950.00'),
        'diferenciais': 'Empresa junior ativa, parcerias com grandes empresas, foco em empreendedorismo',
        'mercado': 'Gestores, consultores, empreendedores, analistas de negocios'
    },
    {
        'curso_id': 'direito',
        'nome': 'Direito',
        'area': 'Humanas',
        'modalidade': 'Presencial',
        'duracao_semestres': 10,
        'vagas_disponiveis': 55,
        'mensalidade': Decimal('1500.00'),
        'diferenciais': 'Nucleo de pratica juridica, convenioes com tribunais, alto indice de aprovacao na OAB',
        'mercado': 'Advogados, juizes, promotores, consultores juridicos'
    }
]

cursos_extensao = [
    {
        'curso_id': 'ext-ia-aplicada',
        'nome': 'Inteligencia Artificial Aplicada',
        'area': 'Tecnologia',
        'modalidade': 'EAD',
        'tipo': 'extensao',
        'duracao_horas': 60,
        'duracao_meses': 3,
        'vagas_disponiveis': 30,
        'mensalidade': Decimal('350.00'),
        'diferenciais': 'Projetos praticos com ChatGPT, visao computacional e NLP',
        'mercado': 'Profissionais que querem aplicar IA no dia a dia'
    },
    {
        'curso_id': 'ext-cybersecurity',
        'nome': 'Cybersecurity Essentials',
        'area': 'Tecnologia',
        'modalidade': 'EAD',
        'tipo': 'extensao',
        'duracao_horas': 40,
        'duracao_meses': 2,
        'vagas_disponiveis': 25,
        'mensalidade': Decimal('280.00'),
        'diferenciais': 'Laboratorios virtuais de pentest, certificacao preparatoria CompTIA Security+',
        'mercado': 'Analistas de seguranca, pentesters, gestores de TI'
    },
    {
        'curso_id': 'ext-data-science',
        'nome': 'Data Science com Python',
        'area': 'Tecnologia',
        'modalidade': 'EAD',
        'tipo': 'extensao',
        'duracao_horas': 80,
        'duracao_meses': 4,
        'vagas_disponiveis': 35,
        'mensalidade': Decimal('400.00'),
        'diferenciais': 'Pandas, Scikit-learn, projetos com dados reais',
        'mercado': 'Cientistas de dados, analistas de BI, engenheiros de dados'
    },
    {
        'curso_id': 'ext-cloud-aws',
        'nome': 'Cloud Computing com AWS',
        'area': 'Tecnologia',
        'modalidade': 'EAD',
        'tipo': 'extensao',
        'duracao_horas': 60,
        'duracao_meses': 3,
        'vagas_disponiveis': 30,
        'mensalidade': Decimal('380.00'),
        'diferenciais': 'Preparatorio AWS Solutions Architect, laboratorios praticos',
        'mercado': 'Arquitetos cloud, DevOps engineers, SREs'
    },
    {
        'curso_id': 'ext-ux-design',
        'nome': 'UX/UI Design',
        'area': 'Design',
        'modalidade': 'EAD',
        'tipo': 'extensao',
        'duracao_horas': 50,
        'duracao_meses': 3,
        'vagas_disponiveis': 25,
        'mensalidade': Decimal('320.00'),
        'diferenciais': 'Figma, pesquisa com usuarios, portfolio profissional',
        'mercado': 'UX designers, UI designers, product designers'
    },
    {
        'curso_id': 'ext-gestao-projetos',
        'nome': 'Gestao de Projetos e Metodologias Ageis',
        'area': 'Negocios',
        'modalidade': 'EAD',
        'tipo': 'extensao',
        'duracao_horas': 40,
        'duracao_meses': 2,
        'vagas_disponiveis': 40,
        'mensalidade': Decimal('250.00'),
        'diferenciais': 'Scrum, Kanban, preparatorio PSM I',
        'mercado': 'Scrum masters, product owners, gerentes de projeto'
    },
    {
        'curso_id': 'ext-marketing-digital',
        'nome': 'Marketing Digital e Analytics',
        'area': 'Negocios',
        'modalidade': 'EAD',
        'tipo': 'extensao',
        'duracao_horas': 45,
        'duracao_meses': 2,
        'vagas_disponiveis': 35,
        'mensalidade': Decimal('280.00'),
        'diferenciais': 'Google Ads, SEO, analytics, redes sociais',
        'mercado': 'Analistas de marketing, social media, growth hackers'
    },
    {
        'curso_id': 'ext-devops',
        'nome': 'DevOps e CI/CD',
        'area': 'Tecnologia',
        'modalidade': 'EAD',
        'tipo': 'extensao',
        'duracao_horas': 60,
        'duracao_meses': 3,
        'vagas_disponiveis': 25,
        'mensalidade': Decimal('380.00'),
        'diferenciais': 'Docker, Kubernetes, Jenkins, GitHub Actions, Terraform',
        'mercado': 'DevOps engineers, SREs, platform engineers'
    },
    {
        'curso_id': 'ext-blockchain',
        'nome': 'Blockchain e Web3',
        'area': 'Tecnologia',
        'modalidade': 'EAD',
        'tipo': 'extensao',
        'duracao_horas': 40,
        'duracao_meses': 2,
        'vagas_disponiveis': 20,
        'mensalidade': Decimal('350.00'),
        'diferenciais': 'Smart contracts, Solidity, DeFi, NFTs',
        'mercado': 'Desenvolvedores blockchain, consultores Web3'
    },
    {
        'curso_id': 'ext-lideranca',
        'nome': 'Lideranca e Gestao de Pessoas',
        'area': 'Negocios',
        'modalidade': 'EAD',
        'tipo': 'extensao',
        'duracao_horas': 30,
        'duracao_meses': 2,
        'vagas_disponiveis': 40,
        'mensalidade': Decimal('220.00'),
        'diferenciais': 'Coaching, feedback, gestao de conflitos, lideranca situacional',
        'mercado': 'Lideres, gestores, coordenadores, supervisores'
    },
    {
        'curso_id': 'ext-saude-mental',
        'nome': 'Saude Mental no Trabalho',
        'area': 'Saude',
        'modalidade': 'EAD',
        'tipo': 'extensao',
        'duracao_horas': 30,
        'duracao_meses': 2,
        'vagas_disponiveis': 30,
        'mensalidade': Decimal('200.00'),
        'diferenciais': 'Burnout, ansiedade, mindfulness, qualidade de vida',
        'mercado': 'Profissionais de RH, gestores, profissionais de saude'
    },
    {
        'curso_id': 'ext-primeiros-socorros',
        'nome': 'Primeiros Socorros e Urgencias',
        'area': 'Saude',
        'modalidade': 'Presencial',
        'tipo': 'extensao',
        'duracao_horas': 20,
        'duracao_meses': 1,
        'vagas_disponiveis': 20,
        'mensalidade': Decimal('180.00'),
        'diferenciais': 'Pratica em manequins, certificado de socorrista',
        'mercado': 'Profissionais de saude, bombeiros, brigadistas'
    },
    {
        'curso_id': 'ext-nutricao-esportiva',
        'nome': 'Nutricao Esportiva',
        'area': 'Saude',
        'modalidade': 'EAD',
        'tipo': 'extensao',
        'duracao_horas': 40,
        'duracao_meses': 2,
        'vagas_disponiveis': 25,
        'mensalidade': Decimal('300.00'),
        'diferenciais': 'Suplementacao, periodizacao nutricional, composicao corporal',
        'mercado': 'Nutricionistas, personal trainers, atletas'
    },
    {
        'curso_id': 'ext-direito-digital',
        'nome': 'Direito Digital e LGPD',
        'area': 'Humanas',
        'modalidade': 'EAD',
        'tipo': 'extensao',
        'duracao_horas': 30,
        'duracao_meses': 2,
        'vagas_disponiveis': 30,
        'mensalidade': Decimal('250.00'),
        'diferenciais': 'LGPD, crimes digitais, contratos eletronicos, Marco Civil',
        'mercado': 'Advogados, DPOs, compliance officers, profissionais de TI'
    },
    {
        'curso_id': 'ext-ingles-negocios',
        'nome': 'Ingles para Negocios',
        'area': 'Negocios',
        'modalidade': 'EAD',
        'tipo': 'extensao',
        'duracao_horas': 60,
        'duracao_meses': 3,
        'vagas_disponiveis': 35,
        'mensalidade': Decimal('300.00'),
        'diferenciais': 'Business English, apresentacoes, negociacoes, emails profissionais',
        'mercado': 'Executivos, gestores, profissionais em empresas multinacionais'
    }
]

all_cursos = cursos_graduacao + cursos_extensao
for c in all_cursos:
    tbl_cursos.put_item(Item=c)
print(f'  {len(cursos_graduacao)} cursos de graduacao + {len(cursos_extensao)} cursos de extensao = {len(all_cursos)} total')

# ============================================================
# STEP 3: Populate academico (documento unico por CPF)
# ============================================================
print('\n=== academico ===')
tbl_academico = dynamodb.Table('academico')

# Wembley - Engenharia de Software - 5o semestre (2026.1)
academico_wembley = {
    'cpf': '123.456.789-00',
    'semestre_atual': '2026.1',
    'cr_acumulado': Decimal('8.0'),
    'disciplinas_atuais': [
        {
            'nome': 'DevOps e Cloud Computing',
            'codigo': 'ES501',
            'professor': 'Prof. Carlos Mendes',
            'horario': 'Seg/Qua 19h-21h',
            'sala': 'Lab 2',
            'faltas': 3,
            'presenca_percentual': Decimal('89'),
            'nota_p1': Decimal('8.5'),
            'nota_p2': Decimal('7.0'),
            'nota_trabalho': Decimal('9.0'),
            'media': Decimal('8.2'),
            'situacao': 'Cursando'
        },
        {
            'nome': 'Inteligencia Artificial',
            'codigo': 'ES502',
            'professor': 'Profa. Ana Lucia Silva',
            'horario': 'Ter/Qui 19h-21h',
            'sala': 'Lab 3',
            'faltas': 5,
            'presenca_percentual': Decimal('82'),
            'nota_p1': Decimal('7.5'),
            'situacao': 'Cursando'
        },
        {
            'nome': 'Seguranca da Informacao',
            'codigo': 'ES503',
            'professor': 'Prof. Roberto Alves',
            'horario': 'Seg/Qua 21h-22h30',
            'sala': 'Sala 201',
            'faltas': 2,
            'presenca_percentual': Decimal('90'),
            'nota_p1': Decimal('9.0'),
            'nota_trabalho': Decimal('8.0'),
            'situacao': 'Cursando'
        },
        {
            'nome': 'Metodologias Ageis',
            'codigo': 'ES504',
            'professor': 'Prof. Fernando Costa',
            'horario': 'Ter/Qui 21h-22h30',
            'sala': 'Sala 105',
            'faltas': 1,
            'presenca_percentual': Decimal('93'),
            'nota_p1': Decimal('8.0'),
            'nota_p2': Decimal('8.5'),
            'nota_trabalho': Decimal('9.5'),
            'media': Decimal('8.7'),
            'situacao': 'Cursando'
        },
        {
            'nome': 'Estagio Supervisionado I',
            'codigo': 'ES505',
            'professor': 'Profa. Juliana Mendes',
            'horario': 'Sex 18h-20h',
            'sala': 'Online',
            'faltas': 0,
            'presenca_percentual': Decimal('100'),
            'situacao': 'Cursando - Avaliacao por relatorio'
        }
    ],
    'provas': [
        {
            'disciplina': 'Inteligencia Artificial',
            'tipo': 'P2',
            'data': '2026-05-05',
            'horario': '19:00',
            'sala': 'Lab 3',
            'conteudo': 'Redes Neurais, Deep Learning, NLP'
        },
        {
            'disciplina': 'Seguranca da Informacao',
            'tipo': 'P2',
            'data': '2026-05-07',
            'horario': '19:00',
            'sala': 'Sala 201',
            'conteudo': 'Criptografia, Pentest, OWASP Top 10'
        },
        {
            'disciplina': 'Estagio Supervisionado I',
            'tipo': 'Entrega de Relatorio Parcial',
            'data': '2026-05-15',
            'horario': '18:00',
            'sala': 'Online',
            'conteudo': 'Relatorio de atividades do estagio'
        },
        {
            'disciplina': 'DevOps e Cloud Computing',
            'tipo': 'Prova Final',
            'data': '2026-06-16',
            'horario': '19:00',
            'sala': 'Lab 2',
            'conteudo': 'Kubernetes, Terraform, CI/CD, Monitoramento'
        },
        {
            'disciplina': 'Inteligencia Artificial',
            'tipo': 'Prova Final',
            'data': '2026-06-18',
            'horario': '19:00',
            'sala': 'Lab 3',
            'conteudo': 'Todo o conteudo do semestre'
        }
    ],
    'historico': [
        {
            'semestre': '2024.1',
            'disciplinas': [
                {'nome': 'Introducao a Programacao (Python)', 'nota': Decimal('8.5'), 'status': 'aprovado', 'faltas': 3, 'presenca_percentual': 85},
                {'nome': 'Logica Matematica', 'nota': Decimal('7.0'), 'status': 'aprovado', 'faltas': 4, 'presenca_percentual': 80},
                {'nome': 'Calculo I', 'nota': Decimal('4.0'), 'status': 'reprovado', 'faltas': 10, 'presenca_percentual': 60},
                {'nome': 'Comunicacao e Expressao', 'nota': Decimal('8.0'), 'status': 'aprovado', 'faltas': 2, 'presenca_percentual': 90},
                {'nome': 'Fundamentos de Computacao', 'nota': Decimal('8.5'), 'status': 'aprovado', 'faltas': 1, 'presenca_percentual': 95}
            ],
            'media_semestre': Decimal('7.2')
        },
        {
            'semestre': '2024.2',
            'disciplinas': [
                {'nome': 'Estrutura de Dados', 'nota': Decimal('8.0'), 'status': 'aprovado', 'faltas': 2, 'presenca_percentual': 90},
                {'nome': 'Programacao Orientada a Objetos', 'nota': Decimal('9.0'), 'status': 'aprovado', 'faltas': 1, 'presenca_percentual': 95},
                {'nome': 'Calculo II', 'nota': Decimal('7.5'), 'status': 'aprovado', 'faltas': 4, 'presenca_percentual': 80},
                {'nome': 'Banco de Dados I', 'nota': Decimal('8.5'), 'status': 'aprovado', 'faltas': 2, 'presenca_percentual': 90},
                {'nome': 'Sistemas Operacionais', 'nota': Decimal('8.5'), 'status': 'aprovado', 'faltas': 3, 'presenca_percentual': 85}
            ],
            'media_semestre': Decimal('8.3')
        },
        {
            'semestre': '2025.1',
            'disciplinas': [
                {'nome': 'Engenharia de Software I', 'nota': Decimal('7.5'), 'status': 'aprovado', 'faltas': 3, 'presenca_percentual': 85},
                {'nome': 'Redes de Computadores', 'nota': Decimal('7.0'), 'status': 'aprovado', 'faltas': 5, 'presenca_percentual': 75},
                {'nome': 'Estatistica', 'nota': Decimal('8.0'), 'status': 'aprovado', 'faltas': 2, 'presenca_percentual': 90},
                {'nome': 'Banco de Dados II', 'nota': Decimal('8.5'), 'status': 'aprovado', 'faltas': 1, 'presenca_percentual': 95},
                {'nome': 'Desenvolvimento Web', 'nota': Decimal('8.0'), 'status': 'aprovado', 'faltas': 3, 'presenca_percentual': 85}
            ],
            'media_semestre': Decimal('7.8')
        },
        {
            'semestre': '2025.2',
            'disciplinas': [
                {'nome': 'Engenharia de Software II', 'nota': Decimal('8.0'), 'status': 'aprovado', 'faltas': 2, 'presenca_percentual': 90},
                {'nome': 'Arquitetura de Software', 'nota': Decimal('8.5'), 'status': 'aprovado', 'faltas': 1, 'presenca_percentual': 95},
                {'nome': 'Testes de Software', 'nota': Decimal('7.5'), 'status': 'aprovado', 'faltas': 3, 'presenca_percentual': 85},
                {'nome': 'Desenvolvimento Mobile', 'nota': Decimal('8.5'), 'status': 'aprovado', 'faltas': 2, 'presenca_percentual': 90},
                {'nome': 'Projeto Integrador I', 'nota': Decimal('8.0'), 'status': 'aprovado', 'faltas': 0, 'presenca_percentual': 100}
            ],
            'media_semestre': Decimal('8.1')
        }
    ],
    'financeiro': [
        {'mes': 'Janeiro/2026', 'valor': Decimal('1200.00'), 'vencimento': '2026-01-10', 'status': 'Pago'},
        {'mes': 'Fevereiro/2026', 'valor': Decimal('1200.00'), 'vencimento': '2026-02-10', 'status': 'Pago'},
        {'mes': 'Marco/2026', 'valor': Decimal('1200.00'), 'vencimento': '2026-03-10', 'status': 'Pago'},
        {'mes': 'Abril/2026', 'valor': Decimal('1200.00'), 'vencimento': '2026-04-10', 'status': 'Pago'},
        {'mes': 'Maio/2026', 'valor': Decimal('1200.00'), 'vencimento': '2026-05-10', 'status': 'Nao pago'},
        {'mes': 'Junho/2026', 'valor': Decimal('1200.00'), 'vencimento': '2026-06-10', 'status': 'Nao pago'}
    ]
}

tbl_academico.put_item(Item=academico_wembley)
print('  Wembley: documento academico completo inserido')

print('\nDone! Dados de teste populados.')
print('Usuarios: 3 (Wembley=aluno, Maria=paciente, Joao=aluno)')
print('Cursos: 6 graduacao + 15 extensao = 21 total')
print('Academico: Wembley com 4 semestres de historico + semestre atual + provas + financeiro')
