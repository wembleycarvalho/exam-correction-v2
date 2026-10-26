"""
Conteudo educacional detalhado para material de estudo (apostilas).
Importado por gerar_apostilas.py para gerar PDFs de material de estudo.
"""

# ============================================================
# Conteudo educacional detalhado por disciplina
# Cada disciplina tem conteudo por unidade com:
#   - explicacao: texto explicativo principal
#   - definicoes: lista de termos e definicoes
#   - exemplo: exemplo pratico (texto ou codigo)
#   - exemplo_tipo: 'texto' ou 'codigo'
#   - dica: nota/dica importante
#   - exercicios: lista de exercicios praticos
# ============================================================

MATERIAL_DISCIPLINAS = {
    'Introducao a Programacao (Python)': [
        {
            'titulo': 'Algoritmos e Logica de Programacao',
            'explicacao': (
                'Um algoritmo e uma sequencia finita e ordenada de passos para resolver um problema. '
                'Antes de escrever codigo, e fundamental pensar na logica da solucao. Podemos representar '
                'algoritmos usando pseudocodigo (linguagem informal estruturada) ou fluxogramas (diagramas visuais). '
                'O pseudocodigo usa palavras como INICIO, FIM, SE, ENTAO, SENAO, ENQUANTO, REPITA para descrever '
                'a logica. Ja o fluxograma usa simbolos graficos: retangulos para processos, losangos para decisoes, '
                'paralelogramos para entrada/saida e setas para indicar o fluxo. A capacidade de decompor problemas '
                'complexos em passos simples e a habilidade mais importante de um programador.'
            ),
            'definicoes': [
                'Algoritmo: sequencia finita de instrucoes bem definidas para resolver um problema.',
                'Pseudocodigo: representacao textual informal de um algoritmo usando linguagem natural estruturada.',
                'Fluxograma: representacao grafica de um algoritmo usando simbolos padronizados.',
                'Variavel: espaco na memoria do computador que armazena um valor que pode mudar durante a execucao.',
            ],
            'exemplo': (
                '# Pseudocodigo: calcular media de dois numeros\n'
                'INICIO\n'
                '  LEIA numero1\n'
                '  LEIA numero2\n'
                '  media = (numero1 + numero2) / 2\n'
                '  ESCREVA "A media e:", media\n'
                'FIM\n\n'
                '# Equivalente em Python:\n'
                'numero1 = float(input("Digite o primeiro numero: "))\n'
                'numero2 = float(input("Digite o segundo numero: "))\n'
                'media = (numero1 + numero2) / 2\n'
                'print(f"A media e: {media}")'
            ),
            'exemplo_tipo': 'codigo',
            'dica': (
                'Dica: Sempre planeje seu algoritmo antes de comecar a programar. '
                'Escreva os passos em portugues primeiro, depois traduza para Python. '
                'Isso evita erros logicos e torna o codigo mais claro.'
            ),
            'exercicios': [
                'Escreva um algoritmo em pseudocodigo que leia tres numeros e imprima o maior deles.',
                'Desenhe um fluxograma para um programa que verifica se um numero e par ou impar.',
                'Converta o seguinte pseudocodigo para Python: LEIA idade; SE idade >= 18 ENTAO ESCREVA "Maior de idade" SENAO ESCREVA "Menor de idade".',
            ],
        },
        {
            'titulo': 'Variaveis, Tipos de Dados, Entrada e Saida',
            'explicacao': (
                'Em Python, variaveis sao criadas automaticamente quando voce atribui um valor a elas. '
                'Nao e necessario declarar o tipo explicitamente - Python usa tipagem dinamica. Os tipos '
                'basicos sao: int (numeros inteiros como 42), float (numeros decimais como 3.14), str '
                '(textos entre aspas como "Ola"), bool (True ou False). A funcao input() le dados do '
                'teclado (sempre retorna string), e print() exibe dados na tela. Para converter tipos, '
                'use int(), float(), str(). Operadores aritmeticos incluem: + (soma), - (subtracao), '
                '* (multiplicacao), / (divisao real), // (divisao inteira), % (resto), ** (potencia).'
            ),
            'definicoes': [
                'int: tipo numerico inteiro (ex: 10, -3, 0).',
                'float: tipo numerico de ponto flutuante (ex: 3.14, -0.5).',
                'str: tipo texto/string (ex: "Python", \'Ola mundo\').',
                'bool: tipo logico com dois valores possiveis: True ou False.',
                'Tipagem dinamica: o tipo da variavel e determinado automaticamente pelo valor atribuido.',
            ],
            'exemplo': (
                '# Variaveis e tipos\n'
                'nome = "Maria"          # str\n'
                'idade = 25              # int\n'
                'altura = 1.68           # float\n'
                'estudante = True        # bool\n\n'
                '# Entrada e saida\n'
                'nome = input("Seu nome: ")\n'
                'idade = int(input("Sua idade: "))\n'
                'print(f"Ola {nome}, voce tem {idade} anos.")\n\n'
                '# Operadores\n'
                'soma = 10 + 3       # 13\n'
                'divisao = 10 / 3    # 3.333...\n'
                'div_int = 10 // 3   # 3\n'
                'resto = 10 % 3      # 1\n'
                'potencia = 2 ** 10   # 1024'
            ),
            'exemplo_tipo': 'codigo',
            'dica': (
                'Dica: input() sempre retorna uma string. Se voce precisa de um numero, '
                'converta com int() ou float(). Exemplo: idade = int(input("Idade: ")). '
                'Cuidado: se o usuario digitar texto quando voce espera numero, dara erro!'
            ),
            'exercicios': [
                'Crie um programa que leia o nome e a idade do usuario e imprima: "Ola [nome], em 10 anos voce tera [idade+10] anos."',
                'Escreva um programa que converta temperatura de Celsius para Fahrenheit (F = C * 9/5 + 32).',
                'Crie um programa que leia o raio de um circulo e calcule a area (A = pi * r^2) e o perimetro (P = 2 * pi * r).',
            ],
        },
        {
            'titulo': 'Estruturas Condicionais e de Repeticao',
            'explicacao': (
                'Estruturas condicionais permitem que o programa tome decisoes. Em Python, usamos if, elif e else. '
                'A condicao deve ser uma expressao booleana (que resulta em True ou False). Operadores de comparacao: '
                '== (igual), != (diferente), > (maior), < (menor), >= (maior ou igual), <= (menor ou igual). '
                'Operadores logicos: and (E), or (OU), not (NAO). Estruturas de repeticao executam um bloco de '
                'codigo varias vezes. O for itera sobre uma sequencia (range, lista, string). O while repete '
                'enquanto uma condicao for verdadeira. Use break para sair do loop e continue para pular para '
                'a proxima iteracao. A indentacao (4 espacos) e obrigatoria em Python para definir blocos de codigo.'
            ),
            'definicoes': [
                'if/elif/else: estrutura condicional que executa blocos diferentes conforme a condicao.',
                'for: laco de repeticao que itera sobre uma sequencia de valores.',
                'while: laco de repeticao que executa enquanto a condicao for verdadeira.',
                'range(n): gera uma sequencia de 0 ate n-1.',
                'break: interrompe o laco imediatamente.',
                'continue: pula para a proxima iteracao do laco.',
            ],
            'exemplo': (
                '# Condicional\n'
                'nota = float(input("Nota: "))\n'
                'if nota >= 7.0:\n'
                '    print("Aprovado!")\n'
                'elif nota >= 5.0:\n'
                '    print("Recuperacao")\n'
                'else:\n'
                '    print("Reprovado")\n\n'
                '# For - tabuada\n'
                'n = int(input("Tabuada de: "))\n'
                'for i in range(1, 11):\n'
                '    print(f"{n} x {i} = {n * i}")\n\n'
                '# While - adivinhar numero\n'
                'secreto = 42\n'
                'chute = 0\n'
                'while chute != secreto:\n'
                '    chute = int(input("Chute: "))\n'
                '    if chute < secreto:\n'
                '        print("Maior!")\n'
                '    elif chute > secreto:\n'
                '        print("Menor!")\n'
                'print("Acertou!")'
            ),
            'exemplo_tipo': 'codigo',
            'dica': (
                'Dica: Cuidado com loops infinitos no while! Sempre garanta que a condicao '
                'eventualmente se torne False. Se o programa travar, use Ctrl+C para interromper.'
            ),
            'exercicios': [
                'Escreva um programa que leia um numero e diga se ele e positivo, negativo ou zero.',
                'Crie um programa que imprima todos os numeros primos entre 1 e 100 usando for e if.',
                'Faca um programa que calcule o fatorial de um numero usando while (ex: 5! = 120).',
            ],
        },
        {
            'titulo': 'Funcoes, Parametros e Escopo',
            'explicacao': (
                'Funcoes sao blocos de codigo reutilizaveis que realizam uma tarefa especifica. Em Python, '
                'definimos funcoes com a palavra-chave def. Funcoes podem receber parametros (dados de entrada) '
                'e retornar valores com return. Parametros podem ter valores padrao (default). O escopo define '
                'onde uma variavel e visivel: variaveis criadas dentro de uma funcao sao locais (so existem '
                'dentro dela), enquanto variaveis criadas fora sao globais. A modularizacao (dividir o programa '
                'em funcoes) torna o codigo mais organizado, legivel e facil de manter. Cada funcao deve ter '
                'uma unica responsabilidade (principio da responsabilidade unica).'
            ),
            'definicoes': [
                'def: palavra-chave para definir uma funcao em Python.',
                'Parametro: variavel que recebe um valor quando a funcao e chamada.',
                'return: instrucao que retorna um valor da funcao para quem a chamou.',
                'Escopo local: variaveis criadas dentro de uma funcao, visiveis apenas nela.',
                'Escopo global: variaveis criadas fora de funcoes, visiveis em todo o programa.',
            ],
            'exemplo': (
                '# Funcao simples\n'
                'def saudacao(nome):\n'
                '    return f"Ola, {nome}!"\n\n'
                'print(saudacao("Ana"))  # Ola, Ana!\n\n'
                '# Funcao com valor padrao\n'
                'def calcular_desconto(preco, percentual=10):\n'
                '    desconto = preco * percentual / 100\n'
                '    return preco - desconto\n\n'
                'print(calcular_desconto(100))      # 90.0 (10% padrao)\n'
                'print(calcular_desconto(100, 20))   # 80.0 (20%)\n\n'
                '# Funcao com multiplos retornos\n'
                'def dividir(a, b):\n'
                '    if b == 0:\n'
                '        return None, "Divisao por zero!"\n'
                '    return a / b, "OK"\n\n'
                'resultado, status = dividir(10, 3)\n'
                'print(f"{resultado:.2f} - {status}")  # 3.33 - OK'
            ),
            'exemplo_tipo': 'codigo',
            'dica': (
                'Dica: Funcoes devem ser pequenas e fazer apenas uma coisa. Se sua funcao tem mais de '
                '20 linhas, considere dividi-la em funcoes menores. Use nomes descritivos como '
                'calcular_media() em vez de cm().'
            ),
            'exercicios': [
                'Crie uma funcao que receba uma lista de numeros e retorne a media, o maior e o menor valor.',
                'Escreva uma funcao eh_primo(n) que retorna True se n e primo e False caso contrario.',
                'Crie uma funcao que receba uma string e retorne ela invertida, sem usar [::-1].',
            ],
        },
        {
            'titulo': 'Listas, Tuplas e Dicionarios',
            'explicacao': (
                'Python oferece estruturas de dados poderosas para armazenar colecoes. Listas (list) sao '
                'colecoes ordenadas e mutaveis, criadas com colchetes []. Tuplas (tuple) sao como listas, '
                'mas imutaveis (nao podem ser alteradas apos criacao), criadas com parenteses (). Dicionarios '
                '(dict) armazenam pares chave-valor, criados com chaves {}. Listas suportam metodos como '
                'append(), remove(), sort(), pop(). List comprehension e uma forma concisa de criar listas: '
                '[expressao for item in iteravel if condicao]. Dicionarios sao ideais para representar '
                'entidades com atributos nomeados, como um aluno com nome, idade e notas.'
            ),
            'definicoes': [
                'Lista (list): colecao ordenada e mutavel de elementos. Ex: [1, 2, 3].',
                'Tupla (tuple): colecao ordenada e imutavel. Ex: (1, 2, 3).',
                'Dicionario (dict): colecao de pares chave-valor. Ex: {"nome": "Ana", "idade": 20}.',
                'Indexacao: acesso a elementos por posicao (comeca em 0). Ex: lista[0].',
                'Slicing: fatiar uma sequencia. Ex: lista[1:3] retorna do indice 1 ao 2.',
            ],
            'exemplo': (
                '# Listas\n'
                'notas = [8.5, 7.0, 9.0, 6.5]\n'
                'notas.append(8.0)          # adiciona ao final\n'
                'media = sum(notas) / len(notas)\n'
                'notas.sort()               # ordena in-place\n'
                'print(f"Notas: {notas}, Media: {media:.1f}")\n\n'
                '# List comprehension\n'
                'pares = [x for x in range(20) if x % 2 == 0]\n'
                'quadrados = [x**2 for x in range(1, 6)]  # [1,4,9,16,25]\n\n'
                '# Dicionario\n'
                'aluno = {\n'
                '    "nome": "Carlos",\n'
                '    "idade": 22,\n'
                '    "notas": [8.5, 7.0, 9.0]\n'
                '}\n'
                'print(aluno["nome"])       # Carlos\n'
                'aluno["email"] = "carlos@email.com"  # adiciona chave\n\n'
                '# Iterando dicionario\n'
                'for chave, valor in aluno.items():\n'
                '    print(f"{chave}: {valor}")'
            ),
            'exemplo_tipo': 'codigo',
            'dica': (
                'Dica: Use listas quando a ordem importa e voce precisa modificar os dados. '
                'Use tuplas para dados que nao devem mudar (como coordenadas). '
                'Use dicionarios quando precisa acessar dados por nome/chave.'
            ),
            'exercicios': [
                'Crie um programa que leia 5 notas, armazene em uma lista e imprima a media e a situacao (aprovado >= 7).',
                'Usando list comprehension, crie uma lista com os cubos dos numeros impares de 1 a 20.',
                'Crie um dicionario representando um produto (nome, preco, estoque) e uma funcao que aplica desconto ao preco.',
            ],
        },
        {
            'titulo': 'Manipulacao de Strings e Expressoes Regulares',
            'explicacao': (
                'Strings em Python sao sequencias imutaveis de caracteres. Elas suportam indexacao, slicing '
                'e diversos metodos uteis. Metodos comuns: upper(), lower(), strip(), split(), join(), '
                'replace(), find(), startswith(), endswith(), count(). F-strings (f"...{variavel}...") sao '
                'a forma mais moderna e legivel de formatar strings. Expressoes regulares (modulo re) permitem '
                'buscar padroes complexos em textos. Padroes basicos: \\d (digito), \\w (alfanumerico), '
                '. (qualquer caractere), * (zero ou mais), + (um ou mais), ? (zero ou um), [] (conjunto de '
                'caracteres), ^ (inicio), $ (fim). Funcoes principais: re.search(), re.findall(), re.sub().'
            ),
            'definicoes': [
                'String: sequencia imutavel de caracteres Unicode.',
                'F-string: string formatada com f"..." que permite inserir expressoes entre chaves.',
                'Expressao regular (regex): padrao de busca para encontrar/manipular texto.',
                'split(): divide string em lista usando um separador.',
                'join(): junta elementos de uma lista em uma string.',
            ],
            'exemplo': (
                '# Metodos de string\n'
                'texto = "  Python e incrivel!  "\n'
                'print(texto.strip())        # "Python e incrivel!"\n'
                'print(texto.upper())        # "  PYTHON E INCRIVEL!  "\n'
                'palavras = texto.split()    # ["Python", "e", "incrivel!"]\n'
                'print("-".join(palavras))   # "Python-e-incrivel!"\n\n'
                '# F-strings\n'
                'nome, nota = "Ana", 8.567\n'
                'print(f"{nome}: {nota:.1f}")  # Ana: 8.6\n\n'
                '# Expressoes regulares\n'
                'import re\n'
                'texto = "Meu email e joao@email.com e tel 11-99999-8888"\n'
                'emails = re.findall(r"[\\w.]+@[\\w.]+", texto)\n'
                'print(emails)  # ["joao@email.com"]\n'
                'tel = re.search(r"\\d{2}-\\d{5}-\\d{4}", texto)\n'
                'print(tel.group())  # "11-99999-8888"'
            ),
            'exemplo_tipo': 'codigo',
            'dica': (
                'Dica: Strings sao imutaveis! Metodos como upper() e replace() retornam uma NOVA string, '
                'nao modificam a original. Para regex, use r"..." (raw string) para evitar problemas com barras invertidas.'
            ),
            'exercicios': [
                'Escreva uma funcao que receba um CPF como string e valide o formato (XXX.XXX.XXX-XX) usando regex.',
                'Crie um programa que conte quantas vezes cada palavra aparece em um texto (use split e dicionario).',
                'Escreva uma funcao que converta "nome_composto" (snake_case) para "NomeComposto" (CamelCase).',
            ],
        },
        {
            'titulo': 'Tratamento de Excecoes e Arquivos',
            'explicacao': (
                'Excecoes sao erros que ocorrem durante a execucao do programa. Em vez de deixar o programa '
                'travar, podemos tratar excecoes com try/except. Excecoes comuns: ValueError (valor invalido), '
                'TypeError (tipo errado), FileNotFoundError (arquivo nao encontrado), ZeroDivisionError (divisao '
                'por zero), KeyError (chave inexistente em dicionario). O bloco finally executa sempre, '
                'independente de erro. Para arquivos, use open() com os modos: "r" (leitura), "w" (escrita, '
                'sobrescreve), "a" (append). O gerenciador de contexto with garante que o arquivo sera fechado '
                'automaticamente. Para JSON, use json.load() (ler) e json.dump() (escrever).'
            ),
            'definicoes': [
                'Excecao: erro que ocorre durante a execucao e pode ser tratado pelo programa.',
                'try/except: estrutura para capturar e tratar excecoes.',
                'finally: bloco que executa sempre, com ou sem excecao.',
                'with: gerenciador de contexto que garante limpeza de recursos (ex: fechar arquivo).',
                'JSON: formato de dados leve para troca de informacoes (JavaScript Object Notation).',
            ],
            'exemplo': (
                '# Tratamento de excecoes\n'
                'try:\n'
                '    numero = int(input("Digite um numero: "))\n'
                '    resultado = 100 / numero\n'
                '    print(f"Resultado: {resultado}")\n'
                'except ValueError:\n'
                '    print("Erro: digite um numero valido!")\n'
                'except ZeroDivisionError:\n'
                '    print("Erro: divisao por zero!")\n'
                'finally:\n'
                '    print("Fim da operacao.")\n\n'
                '# Leitura de arquivo\n'
                'with open("dados.txt", "r") as f:\n'
                '    conteudo = f.read()\n'
                '    print(conteudo)\n\n'
                '# Escrita em arquivo\n'
                'alunos = ["Ana", "Bruno", "Carlos"]\n'
                'with open("alunos.txt", "w") as f:\n'
                '    for aluno in alunos:\n'
                '        f.write(aluno + "\\n")\n\n'
                '# JSON\n'
                'import json\n'
                'dados = {"nome": "Ana", "notas": [8, 9, 7]}\n'
                'with open("dados.json", "w") as f:\n'
                '    json.dump(dados, f, indent=2)'
            ),
            'exemplo_tipo': 'codigo',
            'dica': (
                'Dica: Sempre use "with" ao trabalhar com arquivos - ele garante que o arquivo sera '
                'fechado mesmo se ocorrer um erro. Nunca capture excecoes genericas (except Exception) '
                'sem necessidade, pois isso pode esconder bugs.'
            ),
            'exercicios': [
                'Crie um programa que leia numeros de um arquivo (um por linha) e calcule a media, tratando erros de formato.',
                'Escreva um programa que salve um dicionario de contatos em JSON e depois leia de volta.',
                'Crie uma funcao que tente converter uma string para int, float ou mantenha como str, retornando o valor convertido.',
            ],
        },
        {
            'titulo': 'Introducao a Orientacao a Objetos',
            'explicacao': (
                'Orientacao a objetos (OO) e um paradigma que organiza o codigo em torno de objetos que '
                'combinam dados (atributos) e comportamentos (metodos). Uma classe e um molde/template para '
                'criar objetos. O metodo __init__ e o construtor, chamado automaticamente ao criar um objeto. '
                'O parametro self referencia o proprio objeto. Atributos armazenam o estado do objeto, e '
                'metodos definem suas acoes. Encapsulamento e o principio de esconder detalhes internos: '
                'em Python, usamos _ (protegido) e __ (privado) como convencao. A OO facilita a modelagem '
                'de problemas do mundo real e a reutilizacao de codigo.'
            ),
            'definicoes': [
                'Classe: molde/template que define atributos e metodos de um tipo de objeto.',
                'Objeto: instancia de uma classe, com valores proprios para os atributos.',
                '__init__: metodo construtor, executado automaticamente ao criar um objeto.',
                'self: referencia ao proprio objeto dentro dos metodos da classe.',
                'Atributo: variavel que pertence a um objeto (armazena seu estado).',
                'Metodo: funcao que pertence a uma classe (define comportamento do objeto).',
            ],
            'exemplo': (
                'class ContaBancaria:\n'
                '    def __init__(self, titular, saldo=0):\n'
                '        self.titular = titular\n'
                '        self._saldo = saldo  # protegido\n\n'
                '    def depositar(self, valor):\n'
                '        if valor > 0:\n'
                '            self._saldo += valor\n'
                '            print(f"Deposito de R${valor:.2f}. Saldo: R${self._saldo:.2f}")\n'
                '        else:\n'
                '            print("Valor invalido!")\n\n'
                '    def sacar(self, valor):\n'
                '        if 0 < valor <= self._saldo:\n'
                '            self._saldo -= valor\n'
                '            print(f"Saque de R${valor:.2f}. Saldo: R${self._saldo:.2f}")\n'
                '        else:\n'
                '            print("Saldo insuficiente!")\n\n'
                '    def extrato(self):\n'
                '        print(f"Titular: {self.titular} | Saldo: R${self._saldo:.2f}")\n\n'
                '# Uso\n'
                'conta = ContaBancaria("Ana", 1000)\n'
                'conta.depositar(500)   # Deposito de R$500.00. Saldo: R$1500.00\n'
                'conta.sacar(200)       # Saque de R$200.00. Saldo: R$1300.00\n'
                'conta.extrato()        # Titular: Ana | Saldo: R$1300.00'
            ),
            'exemplo_tipo': 'codigo',
            'dica': (
                'Dica: Pense em classes como substantivos (ContaBancaria, Aluno, Produto) e metodos como '
                'verbos (depositar, matricular, calcular_preco). Cada classe deve representar um conceito '
                'unico e coeso do seu dominio.'
            ),
            'exercicios': [
                'Crie uma classe Aluno com atributos nome, matricula e notas (lista). Adicione metodos para adicionar nota e calcular media.',
                'Implemente uma classe Retangulo com largura e altura, e metodos para calcular area e perimetro.',
                'Crie uma classe ListaDeTarefas com metodos para adicionar, remover, listar e marcar tarefas como concluidas.',
            ],
        },
    ],
    'Logica Matematica': [
        {
            'titulo': 'Proposicoes e Conectivos Logicos',
            'explicacao': (
                'Uma proposicao e uma sentenca declarativa que pode ser classificada como verdadeira (V) ou '
                'falsa (F), nunca ambas. Exemplos: "2 + 3 = 5" (V), "A Terra e plana" (F). Sentencas como '
                '"Que horas sao?" ou "x > 5" nao sao proposicoes. Conectivos logicos combinam proposicoes: '
                'negacao (nao, ~p), conjuncao (e, p ^ q), disjuncao (ou, p v q), condicional (se...entao, '
                'p -> q), bicondicional (se e somente se, p <-> q). A tabela-verdade lista todas as '
                'combinacoes possiveis de valores logicos e o resultado de cada operacao.'
            ),
            'definicoes': [
                'Proposicao: sentenca declarativa com valor logico definido (V ou F).',
                'Negacao (~p): inverte o valor logico. Se p e V, ~p e F.',
                'Conjuncao (p ^ q): verdadeira somente quando ambas sao verdadeiras.',
                'Disjuncao (p v q): falsa somente quando ambas sao falsas.',
                'Condicional (p -> q): falsa somente quando p e V e q e F.',
            ],
            'exemplo': (
                'Tabela-verdade da Condicional (p -> q):\n\n'
                '  p  |  q  | p -> q\n'
                '  V  |  V  |   V\n'
                '  V  |  F  |   F\n'
                '  F  |  V  |   V\n'
                '  F  |  F  |   V\n\n'
                'Exemplo pratico:\n'
                'p: "Chove" (V), q: "Levo guarda-chuva" (V)\n'
                'p -> q: "Se chove, entao levo guarda-chuva" (V)\n'
                'Nota: a condicional so e falsa quando a hipotese e V e a conclusao e F.'
            ),
            'exemplo_tipo': 'texto',
            'dica': (
                'Dica: A condicional p -> q e equivalente a ~p v q. Isso e muito util para '
                'simplificar expressoes logicas e e a base de muitas demonstracoes.'
            ),
            'exercicios': [
                'Construa a tabela-verdade para: (p ^ q) -> (p v r).',
                'Determine o valor logico de: "Se 2 + 2 = 5, entao a Lua e feita de queijo."',
                'Expresse em logica proposicional: "Se estudo e pratico, entao passo na prova."',
            ],
        },
        {
            'titulo': 'Equivalencias Logicas e Leis de De Morgan',
            'explicacao': (
                'Duas proposicoes compostas sao logicamente equivalentes quando possuem a mesma tabela-verdade. '
                'As Leis de De Morgan sao equivalencias fundamentais: ~(p ^ q) equivale a (~p v ~q), e '
                '~(p v q) equivale a (~p ^ ~q). Em palavras: a negacao de "A e B" e "nao-A ou nao-B", e '
                'a negacao de "A ou B" e "nao-A e nao-B". Outras equivalencias importantes: dupla negacao '
                '(~~p = p), contrapositiva (p -> q = ~q -> ~p), distributiva, absorpcao. Essas leis sao '
                'essenciais em programacao para simplificar condicoes complexas em if/while.'
            ),
            'definicoes': [
                'Equivalencia logica: duas expressoes com mesma tabela-verdade (simbolo: <==>).',
                'Leis de De Morgan: ~(p ^ q) <==> (~p v ~q) e ~(p v q) <==> (~p ^ ~q).',
                'Contrapositiva: p -> q <==> ~q -> ~p (sempre equivalentes).',
                'Tautologia: proposicao sempre verdadeira (ex: p v ~p).',
                'Contradicao: proposicao sempre falsa (ex: p ^ ~p).',
            ],
            'exemplo': (
                'Aplicacao em programacao (Python):\n\n'
                '# Condicao original complexa\n'
                'if not (idade >= 18 and tem_carteira):\n'
                '    print("Nao pode dirigir")\n\n'
                '# Aplicando De Morgan: ~(A ^ B) = ~A v ~B\n'
                'if idade < 18 or not tem_carteira:\n'
                '    print("Nao pode dirigir")\n\n'
                '# Ambas as formas sao equivalentes!\n'
                '# A segunda e mais legivel.'
            ),
            'exemplo_tipo': 'codigo',
            'dica': (
                'Dica: As Leis de De Morgan sao extremamente uteis na programacao. Quando voce tem '
                'not (A and B), pode reescrever como (not A) or (not B). Isso torna condicoes '
                'complexas mais legiveis.'
            ),
            'exercicios': [
                'Simplifique usando De Morgan: ~(p v (~q ^ r)).',
                'Prove que p -> q e equivalente a ~q -> ~p usando tabela-verdade.',
                'Reescreva a condicao Python: not (x > 0 and x < 100) de forma equivalente sem o not externo.',
            ],
        },
    ],
    'Calculo I': [
        {
            'titulo': 'Revisao de Funcoes',
            'explicacao': (
                'Uma funcao f: A -> B associa cada elemento x do dominio A a exatamente um elemento f(x) '
                'do contradominio B. O conjunto imagem e o subconjunto de B formado pelos valores efetivamente '
                'assumidos. Funcoes fundamentais: linear f(x) = ax + b, quadratica f(x) = ax^2 + bx + c, '
                'polinomial, racional, exponencial f(x) = a^x, logaritmica f(x) = log_a(x), trigonometricas '
                '(sen, cos, tan). Operacoes com funcoes: soma, produto, composicao (f o g)(x) = f(g(x)), '
                'inversa f^(-1). O grafico de uma funcao e o conjunto de pontos (x, f(x)) no plano cartesiano.'
            ),
            'definicoes': [
                'Dominio: conjunto de todos os valores de x para os quais f(x) esta definida.',
                'Imagem: conjunto de todos os valores f(x) efetivamente assumidos.',
                'Funcao injetora: f(x1) = f(x2) implica x1 = x2 (cada y tem no maximo um x).',
                'Funcao sobrejetora: todo elemento do contradominio e imagem de algum x.',
                'Composicao: (f o g)(x) = f(g(x)), aplica g primeiro, depois f.',
            ],
            'exemplo': (
                'Exemplo: Dominio de f(x) = sqrt(x - 2) / (x - 5)\n\n'
                'Restricoes:\n'
                '1) x - 2 >= 0  =>  x >= 2  (raiz de numero negativo nao existe em R)\n'
                '2) x - 5 != 0  =>  x != 5  (divisao por zero)\n\n'
                'Dominio: D(f) = [2, 5) U (5, +infinito)\n'
                'Ou seja: x >= 2, exceto x = 5.\n\n'
                'Composicao: Se f(x) = x^2 e g(x) = x + 1\n'
                '(f o g)(x) = f(g(x)) = f(x+1) = (x+1)^2 = x^2 + 2x + 1\n'
                '(g o f)(x) = g(f(x)) = g(x^2) = x^2 + 1\n'
                'Note: f o g != g o f (composicao nao e comutativa).'
            ),
            'exemplo_tipo': 'texto',
            'dica': (
                'Dica: Para encontrar o dominio, procure restricoes: denominador != 0, '
                'radicando >= 0 (raiz par), argumento do logaritmo > 0. '
                'O dominio e a interseccao de todas as restricoes.'
            ),
            'exercicios': [
                'Encontre o dominio de f(x) = ln(x^2 - 4) / sqrt(x - 3).',
                'Dadas f(x) = 2x - 1 e g(x) = x^2 + 3, calcule (f o g)(2) e (g o f)(2).',
                'Determine a funcao inversa de f(x) = (2x + 3) / (x - 1).',
            ],
        },
        {
            'titulo': 'Limites e Continuidade',
            'explicacao': (
                'O limite de f(x) quando x tende a "a" e o valor que f(x) se aproxima conforme x se '
                'aproxima de "a". Escrevemos lim(x->a) f(x) = L. O limite pode existir mesmo que f(a) '
                'nao esteja definida. Propriedades: limite da soma = soma dos limites, limite do produto = '
                'produto dos limites. Limites fundamentais: lim(x->0) sen(x)/x = 1, lim(x->infinito) '
                '(1 + 1/x)^x = e. Uma funcao e continua em "a" se: f(a) existe, lim(x->a) f(x) existe, '
                'e lim(x->a) f(x) = f(a). Descontinuidades podem ser removiveis, de salto ou essenciais.'
            ),
            'definicoes': [
                'Limite: valor que f(x) se aproxima quando x se aproxima de um ponto.',
                'Limite lateral: limite pela esquerda (x->a-) ou pela direita (x->a+).',
                'Continuidade: f e continua em a se lim(x->a) f(x) = f(a).',
                'Indeterminacao: formas como 0/0, infinito/infinito que requerem manipulacao algebrica.',
                'Teorema do Confronto: se g(x) <= f(x) <= h(x) e lim g = lim h = L, entao lim f = L.',
            ],
            'exemplo': (
                'Exemplo: Calcular lim(x->2) (x^2 - 4) / (x - 2)\n\n'
                'Substituicao direta: (4 - 4)/(2 - 2) = 0/0 (indeterminacao!)\n\n'
                'Fatorando: (x^2 - 4) = (x-2)(x+2)\n'
                'lim(x->2) (x-2)(x+2) / (x-2) = lim(x->2) (x+2) = 4\n\n'
                'Resposta: lim(x->2) (x^2 - 4)/(x - 2) = 4\n\n'
                'Note: f(2) nao existe (divisao por zero), mas o limite existe e vale 4.'
            ),
            'exemplo_tipo': 'texto',
            'dica': (
                'Dica: Quando a substituicao direta resulta em 0/0, tente fatorar, racionalizar '
                'ou usar a regra de L\'Hopital (derivada do numerador / derivada do denominador).'
            ),
            'exercicios': [
                'Calcule: lim(x->3) (x^2 - 9) / (x^2 - 5x + 6).',
                'Determine se f(x) = |x|/x e continua em x = 0. Justifique.',
                'Calcule: lim(x->0) sen(3x) / (2x) usando o limite fundamental.',
            ],
        },
    ],
    'Comunicacao e Expressao': [
        {
            'titulo': 'Leitura e Interpretacao de Textos Tecnicos',
            'explicacao': (
                'A leitura de textos tecnicos requer estrategias especificas. Diferente da leitura recreativa, '
                'textos tecnicos exigem atencao a terminologia, estrutura logica e precisao. Estrategias eficazes: '
                'leitura previa (scanning) para ter visao geral, leitura detalhada com anotacoes, identificacao '
                'da tese central e argumentos de suporte, analise critica das fontes e evidencias. Em textos de '
                'computacao, e comum encontrar pseudocodigo, diagramas e referencias a padroes tecnicos. '
                'A capacidade de ler e interpretar documentacao tecnica (APIs, RFCs, manuais) e essencial '
                'para qualquer profissional de tecnologia.'
            ),
            'definicoes': [
                'Texto tecnico: texto que comunica informacoes especializadas com linguagem precisa.',
                'Scanning: leitura rapida para identificar informacoes especificas.',
                'Skimming: leitura superficial para captar a ideia geral do texto.',
                'Coesao: ligacao entre as partes do texto (conectivos, pronomes, sinonimos).',
                'Coerencia: logica interna do texto, relacao de sentido entre as ideias.',
            ],
            'exemplo': (
                'Exemplo de analise de texto tecnico:\n\n'
                'Texto: "O protocolo HTTP utiliza o modelo requisicao-resposta. O cliente\n'
                'envia uma requisicao ao servidor, que processa e retorna uma resposta\n'
                'com um codigo de status (200 OK, 404 Not Found, 500 Internal Server Error)."\n\n'
                'Analise:\n'
                '- Tema: protocolo HTTP\n'
                '- Conceito-chave: modelo requisicao-resposta\n'
                '- Termos tecnicos: cliente, servidor, codigo de status\n'
                '- Estrutura: definicao -> funcionamento -> exemplos\n'
                '- Para aprofundar: consultar RFC 7231 (HTTP/1.1 Semantics)'
            ),
            'exemplo_tipo': 'texto',
            'dica': (
                'Dica: Ao ler documentacao tecnica, comece pelo indice/sumario para ter visao geral. '
                'Destaque termos desconhecidos e busque suas definicoes. Faca anotacoes com suas '
                'proprias palavras para fixar o conteudo.'
            ),
            'exercicios': [
                'Leia um artigo tecnico sobre uma tecnologia de seu interesse e faca um resumo de 200 palavras identificando: tema, tese, argumentos e conclusao.',
                'Identifique 5 conectivos em um texto tecnico e classifique-os (adicao, oposicao, causa, consequencia, conclusao).',
                'Reescreva um paragrafo tecnico complexo em linguagem acessivel para um leigo.',
            ],
        },
        {
            'titulo': 'Producao de Textos Tecnicos e Academicos',
            'explicacao': (
                'A producao de textos tecnicos segue principios de clareza, objetividade e precisao. '
                'Generos comuns na area de TI: relatorios tecnicos, documentacao de software (README, '
                'API docs), artigos cientificos, especificacoes de requisitos (SRS), propostas tecnicas. '
                'Estrutura basica: introducao (contexto e objetivo), desenvolvimento (metodologia e resultados), '
                'conclusao (sintese e recomendacoes). Use voz ativa quando possivel, paragrafos curtos, '
                'listas para enumerar itens, e tabelas/figuras para dados complexos. Evite jargoes '
                'desnecessarios e ambiguidades. Revise sempre antes de entregar.'
            ),
            'definicoes': [
                'Relatorio tecnico: documento que descreve atividades, resultados e conclusoes de um trabalho.',
                'README: documento que apresenta um projeto de software (o que faz, como instalar, como usar).',
                'SRS (Software Requirements Specification): documento de especificacao de requisitos de software.',
                'Abstract/Resumo: sintese do trabalho em 150-300 palavras.',
                'Normas ABNT: conjunto de normas brasileiras para formatacao de trabalhos academicos.',
            ],
            'exemplo': (
                'Estrutura de um README.md para projeto de software:\n\n'
                '# Nome do Projeto\n'
                'Descricao breve do que o projeto faz.\n\n'
                '## Tecnologias\n'
                '- Python 3.12\n'
                '- Flask\n'
                '- PostgreSQL\n\n'
                '## Instalacao\n'
                '```bash\n'
                'git clone https://github.com/user/projeto.git\n'
                'pip install -r requirements.txt\n'
                '```\n\n'
                '## Uso\n'
                '```bash\n'
                'python app.py\n'
                '```\n\n'
                '## Contribuicao\n'
                'Pull requests sao bem-vindos.'
            ),
            'exemplo_tipo': 'texto',
            'dica': (
                'Dica: Escreva pensando no leitor. Pergunte-se: "Quem vai ler isso? O que essa pessoa '
                'precisa saber?" Isso ajuda a definir o nivel de detalhe e a linguagem adequada.'
            ),
            'exercicios': [
                'Escreva um README.md para um projeto ficticio de calculadora em Python.',
                'Redija um relatorio tecnico de 1 pagina sobre a instalacao de um ambiente de desenvolvimento.',
                'Crie uma especificacao de requisitos simplificada para um sistema de cadastro de alunos.',
            ],
        },
    ],
    'Fundamentos de Computacao': [
        {
            'titulo': 'Arquitetura de Von Neumann',
            'explicacao': (
                'A arquitetura de Von Neumann, proposta em 1945, e a base dos computadores modernos. '
                'Seus componentes principais sao: CPU (Unidade Central de Processamento) com ULA (Unidade '
                'Logica e Aritmetica) e UC (Unidade de Controle), memoria principal (RAM), dispositivos de '
                'entrada/saida e barramento (canal de comunicacao). O conceito revolucionario e o programa '
                'armazenado: instrucoes e dados ficam na mesma memoria. O ciclo de instrucao segue: busca '
                '(fetch) da instrucao na memoria, decodificacao (decode) pela UC, e execucao (execute) pela '
                'ULA. O gargalo de Von Neumann e a limitacao de velocidade do barramento entre CPU e memoria.'
            ),
            'definicoes': [
                'CPU: processador que executa instrucoes. Composta por ULA, UC e registradores.',
                'RAM (Random Access Memory): memoria volatil de acesso rapido para dados e programas em execucao.',
                'Barramento: canal de comunicacao que conecta CPU, memoria e dispositivos de E/S.',
                'Programa armazenado: conceito de que instrucoes e dados residem na mesma memoria.',
                'Clock: sinal que sincroniza as operacoes do processador (medido em GHz).',
            ],
            'exemplo': (
                'Ciclo de instrucao simplificado:\n\n'
                '1. FETCH: CPU busca a proxima instrucao na memoria (endereco no PC)\n'
                '   PC (Program Counter) = 0x1000\n'
                '   Instrucao lida: ADD R1, R2, R3\n\n'
                '2. DECODE: UC decodifica a instrucao\n'
                '   Operacao: soma\n'
                '   Operandos: R2 e R3\n'
                '   Destino: R1\n\n'
                '3. EXECUTE: ULA executa a operacao\n'
                '   R1 = R2 + R3\n'
                '   Se R2 = 5 e R3 = 3, entao R1 = 8\n\n'
                '4. PC incrementa para proxima instrucao: PC = 0x1004'
            ),
            'exemplo_tipo': 'texto',
            'dica': (
                'Dica: Pense na CPU como o "cerebro" do computador, a RAM como a "mesa de trabalho" '
                '(rapida mas temporaria), e o HD/SSD como o "armario" (permanente mas mais lento). '
                'O barramento e o "corredor" entre eles.'
            ),
            'exercicios': [
                'Explique por que a RAM e chamada de memoria volatil e qual a consequencia pratica disso.',
                'Descreva o gargalo de Von Neumann e cite duas solucoes modernas para mitiga-lo.',
                'Se um processador tem clock de 3 GHz, quantos ciclos ele executa por segundo? E por milissegundo?',
            ],
        },
        {
            'titulo': 'Representacao de Dados - Binario e Hexadecimal',
            'explicacao': (
                'Computadores armazenam tudo em binario (base 2): sequencias de 0s e 1s. Cada digito binario '
                'e um bit; 8 bits formam 1 byte. Para converter decimal para binario, divida sucessivamente '
                'por 2 e leia os restos de baixo para cima. Hexadecimal (base 16) usa digitos 0-9 e letras '
                'A-F (A=10, B=11, ..., F=15). Cada digito hexadecimal representa exatamente 4 bits, o que '
                'torna a conversao binario-hexa muito simples. Hexadecimal e amplamente usado em programacao: '
                'enderecos de memoria, cores em HTML (#FF0000 = vermelho), codigos de caracteres Unicode.'
            ),
            'definicoes': [
                'Bit: menor unidade de informacao (0 ou 1).',
                'Byte: conjunto de 8 bits. Pode representar 256 valores diferentes (0 a 255).',
                'Base 2 (binario): sistema numerico com digitos 0 e 1.',
                'Base 16 (hexadecimal): sistema numerico com digitos 0-9 e A-F.',
                'Overflow: quando um resultado excede a capacidade de representacao.',
            ],
            'exemplo': (
                'Conversao Decimal -> Binario (42):\n'
                '42 / 2 = 21 resto 0\n'
                '21 / 2 = 10 resto 1\n'
                '10 / 2 = 5  resto 0\n'
                '5  / 2 = 2  resto 1\n'
                '2  / 2 = 1  resto 0\n'
                '1  / 2 = 0  resto 1\n'
                'Lendo de baixo para cima: 42 (decimal) = 101010 (binario)\n\n'
                'Binario -> Hexadecimal:\n'
                '101010 = 0010 1010 (agrupando de 4 em 4 da direita)\n'
                '0010 = 2, 1010 = A\n'
                '101010 (binario) = 2A (hexadecimal)\n\n'
                'Verificacao: 2A (hex) = 2*16 + 10 = 42 (decimal). Correto!'
            ),
            'exemplo_tipo': 'texto',
            'dica': (
                'Dica: Em Python, use bin(42) para converter para binario (0b101010), '
                'hex(42) para hexadecimal (0x2a), e int("101010", 2) ou int("2A", 16) '
                'para converter de volta para decimal.'
            ),
            'exercicios': [
                'Converta o numero decimal 200 para binario e hexadecimal.',
                'Converta o numero binario 11011011 para decimal e hexadecimal.',
                'Qual cor HTML e representada por #00FF80? Converta cada componente (R, G, B) para decimal.',
            ],
        },
    ],
    'Estrutura de Dados': [
        {
            'titulo': 'Listas Encadeadas',
            'explicacao': (
                'Uma lista encadeada e uma estrutura de dados linear onde cada elemento (no) contem um valor '
                'e um ponteiro para o proximo no. Diferente de arrays, listas encadeadas nao exigem memoria '
                'contiguia e permitem insercao/remocao em O(1) no inicio. Tipos: lista simplesmente encadeada '
                '(cada no aponta para o proximo), duplamente encadeada (aponta para proximo e anterior), '
                'circular (ultimo aponta para o primeiro). Desvantagem: acesso por indice e O(n), pois e '
                'necessario percorrer a lista desde o inicio. Em Python, a classe list ja e implementada '
                'como array dinamico, mas entender listas encadeadas e fundamental para compreender '
                'estruturas mais complexas como arvores e grafos.'
            ),
            'definicoes': [
                'No (Node): elemento da lista contendo dado e referencia ao proximo no.',
                'Head: referencia ao primeiro no da lista.',
                'Tail: referencia ao ultimo no da lista (aponta para None).',
                'Lista simplesmente encadeada: cada no aponta apenas para o proximo.',
                'Lista duplamente encadeada: cada no aponta para o proximo e o anterior.',
            ],
            'exemplo': (
                'class Node:\n'
                '    def __init__(self, data):\n'
                '        self.data = data\n'
                '        self.next = None\n\n'
                'class LinkedList:\n'
                '    def __init__(self):\n'
                '        self.head = None\n\n'
                '    def insert_front(self, data):\n'
                '        new_node = Node(data)\n'
                '        new_node.next = self.head\n'
                '        self.head = new_node  # O(1)\n\n'
                '    def display(self):\n'
                '        current = self.head\n'
                '        while current:\n'
                '            print(current.data, end=" -> ")\n'
                '            current = current.next\n'
                '        print("None")\n\n'
                '# Uso\n'
                'll = LinkedList()\n'
                'll.insert_front(3)\n'
                'll.insert_front(2)\n'
                'll.insert_front(1)\n'
                'll.display()  # 1 -> 2 -> 3 -> None'
            ),
            'exemplo_tipo': 'codigo',
            'dica': (
                'Dica: Ao manipular listas encadeadas, sempre desenhe os nos e ponteiros no papel. '
                'Erros comuns: perder a referencia ao proximo no ao inserir/remover, e nao tratar '
                'o caso da lista vazia (head == None).'
            ),
            'exercicios': [
                'Implemente um metodo remove(data) que remove a primeira ocorrencia de um valor na lista encadeada.',
                'Implemente um metodo reverse() que inverte a lista encadeada in-place.',
                'Compare a complexidade de insercao no inicio entre lista encadeada e array. Qual e mais eficiente e por que?',
            ],
        },
        {
            'titulo': 'Pilhas e Filas',
            'explicacao': (
                'Pilha (Stack) segue o principio LIFO (Last In, First Out): o ultimo elemento inserido e o '
                'primeiro a ser removido. Operacoes: push (inserir no topo), pop (remover do topo), peek/top '
                '(ver o topo sem remover). Aplicacoes: desfazer/refazer em editores, avaliacao de expressoes, '
                'chamadas de funcao (call stack). Fila (Queue) segue FIFO (First In, First Out): o primeiro '
                'a entrar e o primeiro a sair. Operacoes: enqueue (inserir no final), dequeue (remover do '
                'inicio). Aplicacoes: filas de impressao, BFS em grafos, buffers de dados. Ambas podem ser '
                'implementadas com arrays ou listas encadeadas, com todas as operacoes em O(1).'
            ),
            'definicoes': [
                'LIFO (Last In, First Out): ultimo a entrar, primeiro a sair (pilha).',
                'FIFO (First In, First Out): primeiro a entrar, primeiro a sair (fila).',
                'Push: inserir elemento no topo da pilha.',
                'Pop: remover e retornar elemento do topo da pilha.',
                'Enqueue/Dequeue: inserir no final / remover do inicio da fila.',
            ],
            'exemplo': (
                '# Pilha com lista Python\n'
                'pilha = []\n'
                'pilha.append(1)   # push\n'
                'pilha.append(2)\n'
                'pilha.append(3)\n'
                'print(pilha.pop())  # 3 (LIFO)\n'
                'print(pilha.pop())  # 2\n\n'
                '# Fila com collections.deque (eficiente)\n'
                'from collections import deque\n'
                'fila = deque()\n'
                'fila.append(1)      # enqueue\n'
                'fila.append(2)\n'
                'fila.append(3)\n'
                'print(fila.popleft())  # 1 (FIFO)\n'
                'print(fila.popleft())  # 2\n\n'
                '# Aplicacao: verificar parenteses balanceados\n'
                'def parenteses_validos(s):\n'
                '    pilha = []\n'
                '    pares = {"(": ")", "[": "]", "{": "}"}\n'
                '    for c in s:\n'
                '        if c in pares:\n'
                '            pilha.append(c)\n'
                '        elif pilha and pares.get(pilha[-1]) == c:\n'
                '            pilha.pop()\n'
                '        else:\n'
                '            return False\n'
                '    return len(pilha) == 0\n\n'
                'print(parenteses_validos("({[]})"))  # True\n'
                'print(parenteses_validos("({[})"))   # False'
            ),
            'exemplo_tipo': 'codigo',
            'dica': (
                'Dica: Em Python, use list como pilha (append/pop sao O(1) no final). '
                'Para filas, use collections.deque em vez de list, pois list.pop(0) e O(n) '
                'enquanto deque.popleft() e O(1).'
            ),
            'exercicios': [
                'Implemente uma funcao que converte um numero decimal para binario usando uma pilha.',
                'Implemente uma fila de prioridade simples onde elementos com maior prioridade sao atendidos primeiro.',
                'Use uma pilha para avaliar uma expressao pos-fixa (notacao polonesa reversa): "3 4 + 2 *" = 14.',
            ],
        },
    ],
    'Programacao Orientada a Objetos': [
        {
            'titulo': 'Encapsulamento e Modificadores de Acesso',
            'explicacao': (
                'Encapsulamento e o principio de esconder os detalhes internos de um objeto, expondo apenas '
                'uma interface publica. Isso protege os dados de acesso indevido e permite alterar a '
                'implementacao interna sem afetar o codigo que usa a classe. Em Python, a convencao e: '
                'atributos publicos (sem prefixo), protegidos (_prefixo com um underscore, convencao de '
                '"nao mexa"), privados (__prefixo com dois underscores, name mangling). Properties (@property) '
                'permitem criar getters e setters elegantes, validando dados ao atribuir valores. Em Java/C#, '
                'usamos public, protected e private explicitamente.'
            ),
            'definicoes': [
                'Encapsulamento: ocultar detalhes internos e expor apenas interface publica.',
                'Getter: metodo que retorna o valor de um atributo privado.',
                'Setter: metodo que define o valor de um atributo privado (com validacao).',
                '@property: decorador Python que transforma metodo em atributo de leitura.',
                'Name mangling: Python renomeia __atributo para _Classe__atributo internamente.',
            ],
            'exemplo': (
                'class Produto:\n'
                '    def __init__(self, nome, preco):\n'
                '        self._nome = nome\n'
                '        self.__preco = preco  # privado\n\n'
                '    @property\n'
                '    def preco(self):\n'
                '        """Getter para preco."""\n'
                '        return self.__preco\n\n'
                '    @preco.setter\n'
                '    def preco(self, valor):\n'
                '        """Setter com validacao."""\n'
                '        if valor < 0:\n'
                '            raise ValueError("Preco nao pode ser negativo!")\n'
                '        self.__preco = valor\n\n'
                '    def __str__(self):\n'
                '        return f"{self._nome}: R${self.__preco:.2f}"\n\n'
                '# Uso\n'
                'p = Produto("Notebook", 3500)\n'
                'print(p.preco)       # 3500 (usa getter)\n'
                'p.preco = 3200       # usa setter (valida)\n'
                'print(p)             # Notebook: R$3200.00\n'
                '# p.preco = -100     # ValueError!'
            ),
            'exemplo_tipo': 'codigo',
            'dica': (
                'Dica: Use @property quando precisar validar dados ou calcular valores derivados. '
                'Nao crie getters/setters para todos os atributos - so quando houver logica de '
                'validacao ou transformacao. Atributos simples podem ser publicos.'
            ),
            'exercicios': [
                'Crie uma classe ContaCorrente com saldo privado e metodos depositar/sacar que validam valores.',
                'Implemente uma classe Temperatura com property que converte automaticamente entre Celsius e Fahrenheit.',
                'Explique a diferenca entre _atributo e __atributo em Python com exemplos praticos.',
            ],
        },
        {
            'titulo': 'Heranca e Polimorfismo',
            'explicacao': (
                'Heranca permite criar novas classes (filhas) baseadas em classes existentes (pais), '
                'herdando atributos e metodos. A classe filha pode adicionar novos membros ou sobrescrever '
                '(override) metodos da classe pai. Use super() para chamar metodos da classe pai. '
                'Polimorfismo significa "muitas formas": objetos de classes diferentes podem responder '
                'a mesma mensagem de formas diferentes. Exemplo: um metodo area() pode calcular a area '
                'de um Circulo, Retangulo ou Triangulo, cada um com sua formula. Python suporta heranca '
                'multipla (uma classe pode herdar de varias), mas use com cuidado para evitar complexidade.'
            ),
            'definicoes': [
                'Heranca: mecanismo onde uma classe filha herda atributos e metodos da classe pai.',
                'Classe pai (superclasse): classe base da qual outras herdam.',
                'Classe filha (subclasse): classe que herda de outra e pode estender/modificar.',
                'Override: sobrescrever um metodo da classe pai na classe filha.',
                'Polimorfismo: capacidade de objetos diferentes responderem ao mesmo metodo de formas distintas.',
                'super(): funcao que referencia a classe pai para chamar seus metodos.',
            ],
            'exemplo': (
                'class Forma:\n'
                '    def area(self):\n'
                '        raise NotImplementedError("Subclasse deve implementar area()")\n\n'
                '    def __str__(self):\n'
                '        return f"{self.__class__.__name__}: area = {self.area():.2f}"\n\n'
                'class Circulo(Forma):\n'
                '    def __init__(self, raio):\n'
                '        self.raio = raio\n\n'
                '    def area(self):\n'
                '        return 3.14159 * self.raio ** 2\n\n'
                'class Retangulo(Forma):\n'
                '    def __init__(self, largura, altura):\n'
                '        self.largura = largura\n'
                '        self.altura = altura\n\n'
                '    def area(self):\n'
                '        return self.largura * self.altura\n\n'
                '# Polimorfismo em acao\n'
                'formas = [Circulo(5), Retangulo(4, 6), Circulo(3)]\n'
                'for f in formas:\n'
                '    print(f)  # Cada forma calcula area de forma diferente\n'
                '# Circulo: area = 78.54\n'
                '# Retangulo: area = 24.00\n'
                '# Circulo: area = 28.27'
            ),
            'exemplo_tipo': 'codigo',
            'dica': (
                'Dica: Prefira composicao sobre heranca quando possivel. Heranca cria acoplamento '
                'forte entre classes. Use heranca quando existe uma relacao "e um" (Circulo E UM Forma). '
                'Use composicao quando existe uma relacao "tem um" (Carro TEM UM Motor).'
            ),
            'exercicios': [
                'Crie uma hierarquia: Veiculo (pai) -> Carro e Moto (filhos) com metodo descrever() polimorfico.',
                'Implemente uma classe Quadrado que herda de Retangulo. Qual problema pode surgir? (Principio de Liskov)',
                'Crie classes Funcionario, Gerente e Estagiario com calculo de salario polimorfico (bonus diferente).',
            ],
        },
    ],
    'Calculo II': [
        {
            'titulo': 'Funcoes de Varias Variaveis',
            'explicacao': (
                'Funcoes de varias variaveis mapeiam pontos de R^n para R. Exemplo: f(x,y) = x^2 + y^2 '
                'associa cada ponto (x,y) do plano a um numero real. O grafico de f(x,y) e uma superficie '
                'no espaco 3D. Curvas de nivel sao conjuntos de pontos onde f(x,y) = c (constante), '
                'formando "contornos" como em mapas topograficos. O dominio e o conjunto de pontos (x,y) '
                'onde f esta definida. Limites em varias variaveis sao mais complexos: o limite deve ser '
                'o mesmo independente do caminho de aproximacao. Se caminhos diferentes dao limites '
                'diferentes, o limite nao existe.'
            ),
            'definicoes': [
                'Funcao de duas variaveis: f: R^2 -> R, associa (x,y) a f(x,y).',
                'Curva de nivel: conjunto {(x,y) : f(x,y) = c} para uma constante c.',
                'Superficie: grafico de f(x,y) no espaco tridimensional.',
                'Limite em varias variaveis: deve ser unico independente do caminho de aproximacao.',
            ],
            'exemplo': (
                'Exemplo: f(x,y) = x^2 + y^2\n\n'
                'Dominio: todo R^2 (qualquer par (x,y))\n'
                'Imagem: [0, +infinito)\n\n'
                'Curvas de nivel:\n'
                'f(x,y) = 1  =>  x^2 + y^2 = 1  (circulo de raio 1)\n'
                'f(x,y) = 4  =>  x^2 + y^2 = 4  (circulo de raio 2)\n'
                'f(x,y) = 9  =>  x^2 + y^2 = 9  (circulo de raio 3)\n\n'
                'O grafico e um paraboloide (forma de "tigela").\n'
                'As curvas de nivel sao circulos concentricos na origem.'
            ),
            'exemplo_tipo': 'texto',
            'dica': (
                'Dica: Para verificar se um limite em varias variaveis existe, teste caminhos '
                'diferentes (y=0, x=0, y=x, y=x^2). Se dois caminhos derem resultados diferentes, '
                'o limite NAO existe.'
            ),
            'exercicios': [
                'Determine o dominio e esboce as curvas de nivel de f(x,y) = ln(x^2 + y^2 - 1).',
                'Verifique se lim(x,y)->(0,0) xy/(x^2+y^2) existe testando os caminhos y=0, x=0 e y=x.',
                'Descreva geometricamente a superficie f(x,y) = sqrt(9 - x^2 - y^2).',
            ],
        },
    ],
    'Banco de Dados I': [
        {
            'titulo': 'Modelo Entidade-Relacionamento e SQL',
            'explicacao': (
                'O modelo Entidade-Relacionamento (ER) e a principal ferramenta para projetar bancos de dados. '
                'Entidades representam "coisas" do mundo real (Aluno, Disciplina, Professor). Atributos sao '
                'propriedades das entidades (nome, matricula, email). Relacionamentos conectam entidades '
                '(Aluno CURSA Disciplina). Cardinalidade define quantos elementos participam: 1:1 (um para um), '
                '1:N (um para muitos), N:M (muitos para muitos). O modelo ER e convertido para tabelas '
                'relacionais: cada entidade vira uma tabela, atributos viram colunas, e a chave primaria (PK) '
                'identifica unicamente cada registro. Chaves estrangeiras (FK) implementam relacionamentos.'
            ),
            'definicoes': [
                'Entidade: objeto do mundo real representado no banco (ex: Aluno, Produto).',
                'Atributo: propriedade de uma entidade (ex: nome, preco, data_nascimento).',
                'Chave primaria (PK): atributo que identifica unicamente cada registro.',
                'Chave estrangeira (FK): atributo que referencia a PK de outra tabela.',
                'Cardinalidade: quantificacao do relacionamento (1:1, 1:N, N:M).',
                'Normalizacao: processo de organizar tabelas para eliminar redundancias.',
            ],
            'exemplo': (
                '-- Criacao de tabelas (DDL)\n'
                'CREATE TABLE alunos (\n'
                '    matricula INT PRIMARY KEY,\n'
                '    nome VARCHAR(100) NOT NULL,\n'
                '    email VARCHAR(100) UNIQUE,\n'
                '    data_nascimento DATE\n'
                ');\n\n'
                'CREATE TABLE disciplinas (\n'
                '    codigo VARCHAR(10) PRIMARY KEY,\n'
                '    nome VARCHAR(100) NOT NULL,\n'
                '    carga_horaria INT DEFAULT 60\n'
                ');\n\n'
                'CREATE TABLE matriculas (\n'
                '    id SERIAL PRIMARY KEY,\n'
                '    aluno_matricula INT REFERENCES alunos(matricula),\n'
                '    disciplina_codigo VARCHAR(10) REFERENCES disciplinas(codigo),\n'
                '    semestre VARCHAR(6),\n'
                '    nota DECIMAL(3,1)\n'
                ');\n\n'
                '-- Consultas (DQL)\n'
                'SELECT a.nome, d.nome AS disciplina, m.nota\n'
                'FROM alunos a\n'
                'JOIN matriculas m ON a.matricula = m.aluno_matricula\n'
                'JOIN disciplinas d ON d.codigo = m.disciplina_codigo\n'
                'WHERE m.semestre = \'2024.1\'\n'
                'ORDER BY a.nome;'
            ),
            'exemplo_tipo': 'codigo',
            'dica': (
                'Dica: Sempre projete o modelo ER antes de criar tabelas. Relacionamentos N:M '
                'sempre geram uma tabela intermediaria (como "matriculas" no exemplo). '
                'Use REFERENCES para garantir integridade referencial.'
            ),
            'exercicios': [
                'Projete um modelo ER para uma biblioteca (Livro, Autor, Emprestimo, Usuario) e identifique as cardinalidades.',
                'Escreva comandos SQL para inserir 3 alunos e 2 disciplinas, e matricular os alunos.',
                'Escreva uma consulta que retorne a media de notas por disciplina, ordenada da maior para menor media.',
            ],
        },
    ],
    'Sistemas Operacionais': [
        {
            'titulo': 'Processos, Threads e Escalonamento',
            'explicacao': (
                'Um processo e um programa em execucao, com seu proprio espaco de memoria, registradores e '
                'recursos. Cada processo passa por estados: novo, pronto, executando, bloqueado, terminado. '
                'Threads sao "processos leves" que compartilham o espaco de memoria do processo pai, '
                'permitindo paralelismo com menor overhead. O escalonador de CPU decide qual processo/thread '
                'executa a cada momento. Algoritmos classicos: FCFS (First Come First Served - simples mas '
                'pode causar efeito comboio), SJF (Shortest Job First - otimo mas dificil prever), '
                'Round Robin (cada processo recebe um quantum de tempo, justo para sistemas interativos), '
                'Prioridade (processos com maior prioridade executam primeiro, risco de starvation).'
            ),
            'definicoes': [
                'Processo: programa em execucao com espaco de enderecamento proprio.',
                'Thread: unidade de execucao dentro de um processo, compartilha memoria.',
                'Escalonamento: algoritmo que decide qual processo usa a CPU.',
                'Quantum: fatia de tempo alocada a cada processo no Round Robin.',
                'Context switch: troca de processo na CPU (salva/restaura estado).',
                'Starvation: processo que nunca consegue executar por ter baixa prioridade.',
            ],
            'exemplo': (
                'Exemplo de Round Robin (quantum = 4ms):\n\n'
                'Processos: P1(burst=8ms), P2(burst=4ms), P3(burst=6ms)\n\n'
                'Tempo 0-4:   P1 executa (resta 4ms)\n'
                'Tempo 4-8:   P2 executa (termina!)\n'
                'Tempo 8-12:  P3 executa (resta 2ms)\n'
                'Tempo 12-16: P1 executa (termina!)\n'
                'Tempo 16-18: P3 executa (termina!)\n\n'
                'Tempo de espera:\n'
                'P1: 0 + (12-4) = 8ms\n'
                'P2: 4ms\n'
                'P3: 8 + (16-12) = 12ms\n'
                'Media: (8+4+12)/3 = 8ms'
            ),
            'exemplo_tipo': 'texto',
            'dica': (
                'Dica: Round Robin e o algoritmo mais usado em sistemas interativos (como seu SO). '
                'Um quantum muito pequeno causa muitos context switches (overhead). '
                'Um quantum muito grande se comporta como FCFS. O ideal e entre 10-100ms.'
            ),
            'exercicios': [
                'Calcule o tempo medio de espera para FCFS e SJF com processos: P1(6ms), P2(2ms), P3(8ms), P4(3ms).',
                'Explique a diferenca entre processo e thread. Quando usar cada um?',
                'Descreva o problema do deadlock e cite as 4 condicoes necessarias para que ocorra.',
            ],
        },
    ],
}


# ============================================================
# Conteudo educacional para cursos de extensao
# ============================================================
MATERIAL_EXTENSAO = {
    'ext-ia-aplicada': [
        {
            'titulo': 'Fundamentos de IA e Aprendizado de Maquina',
            'explicacao': (
                'Inteligencia Artificial (IA) e o campo da ciencia da computacao dedicado a criar sistemas '
                'capazes de realizar tarefas que normalmente requerem inteligencia humana. O Aprendizado de '
                'Maquina (ML) e um subcampo da IA onde algoritmos aprendem padroes a partir de dados, sem '
                'serem explicitamente programados. Tipos de aprendizado: supervisionado (dados rotulados - '
                'classificacao e regressao), nao-supervisionado (sem rotulos - clustering e reducao de '
                'dimensionalidade), e por reforco (agente aprende por tentativa e erro). O pipeline tipico '
                'de ML inclui: coleta de dados, preprocessamento, selecao de features, treinamento do modelo, '
                'avaliacao e deploy. Metricas comuns: acuracia, precisao, recall, F1-score para classificacao; '
                'MSE, RMSE, R^2 para regressao.'
            ),
            'definicoes': [
                'IA: campo que busca criar sistemas que simulam inteligencia humana.',
                'Machine Learning: algoritmos que aprendem padroes a partir de dados.',
                'Aprendizado supervisionado: treinamento com dados rotulados (entrada + saida esperada).',
                'Aprendizado nao-supervisionado: encontrar padroes em dados sem rotulos.',
                'Overfitting: modelo memoriza dados de treino e nao generaliza para dados novos.',
            ],
            'exemplo': (
                '# Classificacao com Scikit-learn\n'
                'from sklearn.model_selection import train_test_split\n'
                'from sklearn.ensemble import RandomForestClassifier\n'
                'from sklearn.metrics import accuracy_score\n'
                'import pandas as pd\n\n'
                '# Carregar dados\n'
                'df = pd.read_csv("dados.csv")\n'
                'X = df.drop("target", axis=1)\n'
                'y = df["target"]\n\n'
                '# Dividir treino/teste\n'
                'X_train, X_test, y_train, y_test = train_test_split(\n'
                '    X, y, test_size=0.2, random_state=42\n'
                ')\n\n'
                '# Treinar modelo\n'
                'modelo = RandomForestClassifier(n_estimators=100)\n'
                'modelo.fit(X_train, y_train)\n\n'
                '# Avaliar\n'
                'pred = modelo.predict(X_test)\n'
                'print(f"Acuracia: {accuracy_score(y_test, pred):.2%}")'
            ),
            'exemplo_tipo': 'codigo',
            'dica': (
                'Dica: Sempre divida seus dados em treino e teste ANTES de treinar o modelo. '
                'Nunca avalie o modelo nos mesmos dados usados para treino - isso da uma falsa '
                'impressao de performance (overfitting).'
            ),
            'exercicios': [
                'Carregue o dataset Iris do sklearn e treine um classificador KNN. Qual acuracia voce obteve?',
                'Explique a diferenca entre classificacao e regressao com exemplos praticos.',
                'O que e validacao cruzada (cross-validation) e por que e melhor que um unico split treino/teste?',
            ],
        },
        {
            'titulo': 'NLP e Chatbots com LLMs',
            'explicacao': (
                'Processamento de Linguagem Natural (NLP) permite que computadores entendam, interpretem e '
                'gerem linguagem humana. Tarefas classicas: tokenizacao (dividir texto em palavras/tokens), '
                'analise de sentimento, classificacao de texto, traducao, sumarizacao. Large Language Models '
                '(LLMs) como GPT, Claude e Llama revolucionaram o NLP ao aprender padroes linguisticos de '
                'bilhoes de textos. Para usar LLMs via API: envie um prompt (instrucao em texto) e receba '
                'uma resposta gerada. Tecnicas de prompt engineering: zero-shot (sem exemplos), few-shot '
                '(com exemplos), chain-of-thought (passo a passo). Chatbots modernos combinam LLMs com '
                'RAG (Retrieval-Augmented Generation) para responder com base em documentos especificos.'
            ),
            'definicoes': [
                'NLP: area da IA que lida com interacao entre computadores e linguagem humana.',
                'LLM: modelo de linguagem treinado em grandes volumes de texto.',
                'Prompt: instrucao em texto enviada ao modelo para obter uma resposta.',
                'RAG: tecnica que combina busca em documentos com geracao de texto por LLM.',
                'Tokenizacao: processo de dividir texto em unidades menores (tokens).',
            ],
            'exemplo': (
                '# Usando a API da OpenAI\n'
                'from openai import OpenAI\n\n'
                'client = OpenAI(api_key="sua-chave")\n\n'
                'response = client.chat.completions.create(\n'
                '    model="gpt-4",\n'
                '    messages=[\n'
                '        {"role": "system", "content": "Voce e um assistente util."},\n'
                '        {"role": "user", "content": "Explique o que e machine learning em 2 frases."}\n'
                '    ],\n'
                '    temperature=0.7\n'
                ')\n\n'
                'print(response.choices[0].message.content)\n\n'
                '# Analise de sentimento simples\n'
                'prompt = """Classifique o sentimento como positivo, negativo ou neutro:\n'
                'Texto: "O produto chegou rapido e funciona perfeitamente!"\n'
                'Sentimento:"""\n'
                '# Resposta esperada: positivo'
            ),
            'exemplo_tipo': 'codigo',
            'dica': (
                'Dica: Ao usar LLMs, seja especifico no prompt. Em vez de "Fale sobre Python", '
                'diga "Liste 5 vantagens de Python para data science, com exemplos praticos". '
                'Quanto mais contexto e restricoes, melhor a resposta.'
            ),
            'exercicios': [
                'Crie um prompt que classifique emails como spam ou nao-spam. Teste com 5 exemplos.',
                'Implemente um chatbot simples usando a API da OpenAI que responde perguntas sobre um tema especifico.',
                'Explique a diferenca entre fine-tuning e RAG. Quando usar cada abordagem?',
            ],
        },
    ],
    'ext-cybersecurity': [
        {
            'titulo': 'Fundamentos de Cybersecurity e OWASP Top 10',
            'explicacao': (
                'Cybersecurity e a pratica de proteger sistemas, redes e dados contra ataques digitais. '
                'Os tres pilares sao: Confidencialidade (dados acessiveis apenas a autorizados), Integridade '
                '(dados nao alterados indevidamente), Disponibilidade (sistemas acessiveis quando necessario) '
                '- conhecidos como triade CIA. O OWASP Top 10 lista as vulnerabilidades web mais criticas: '
                'Broken Access Control, Cryptographic Failures, Injection (SQL, XSS), Insecure Design, '
                'Security Misconfiguration, Vulnerable Components, Authentication Failures, Software Integrity '
                'Failures, Logging Failures, SSRF. SQL Injection ocorre quando entrada do usuario e inserida '
                'diretamente em queries SQL sem sanitizacao. XSS (Cross-Site Scripting) injeta scripts '
                'maliciosos em paginas web vistas por outros usuarios.'
            ),
            'definicoes': [
                'CIA Triad: Confidencialidade, Integridade e Disponibilidade.',
                'SQL Injection: ataque que insere codigo SQL malicioso via entrada do usuario.',
                'XSS: ataque que injeta scripts maliciosos em paginas web.',
                'CSRF: ataque que forca usuario autenticado a executar acoes indesejadas.',
                'Pentest: teste de penetracao - simular ataques para encontrar vulnerabilidades.',
            ],
            'exemplo': (
                '# VULNERAVEL a SQL Injection!\n'
                'query = f"SELECT * FROM users WHERE name = \'{user_input}\'"\n'
                '# Se user_input = "\' OR 1=1 --"\n'
                '# Query vira: SELECT * FROM users WHERE name = \'\' OR 1=1 --\'\n'
                '# Retorna TODOS os usuarios!\n\n'
                '# SEGURO - usando parametros\n'
                'cursor.execute(\n'
                '    "SELECT * FROM users WHERE name = %s",\n'
                '    (user_input,)\n'
                ')\n\n'
                '# VULNERAVEL a XSS!\n'
                'html = f"<p>Ola, {user_input}</p>"\n'
                '# Se user_input = "<script>alert(\'hack\')</script>"\n'
                '# O script sera executado no navegador!\n\n'
                '# SEGURO - escapando HTML\n'
                'from html import escape\n'
                'html = f"<p>Ola, {escape(user_input)}</p>"'
            ),
            'exemplo_tipo': 'codigo',
            'dica': (
                'Dica: NUNCA confie em dados vindos do usuario. Sempre valide, sanitize e use '
                'queries parametrizadas. A regra de ouro da seguranca: "Validate input, encode output."'
            ),
            'exercicios': [
                'Identifique 3 vulnerabilidades no seguinte codigo e proponha correcoes: login sem rate limiting, senha em texto plano, SQL concatenado.',
                'Explique como funciona um ataque CSRF e como o token anti-CSRF previne esse ataque.',
                'Use o OWASP ZAP ou Burp Suite para escanear uma aplicacao web de teste (ex: DVWA) e documente as vulnerabilidades encontradas.',
            ],
        },
    ],
    'ext-data-science': [
        {
            'titulo': 'Python para Analise de Dados com Pandas',
            'explicacao': (
                'Pandas e a biblioteca Python mais usada para analise de dados. O DataFrame e sua estrutura '
                'principal: uma tabela com linhas e colunas, similar a uma planilha Excel ou tabela SQL. '
                'Operacoes essenciais: ler dados (pd.read_csv, pd.read_excel), explorar (head(), info(), '
                'describe()), filtrar (df[df["coluna"] > valor]), agrupar (groupby), juntar (merge/join), '
                'tratar valores ausentes (fillna, dropna). A analise exploratoria (EDA) e o primeiro passo '
                'em qualquer projeto de data science: entender distribuicoes, correlacoes, outliers e '
                'padroes nos dados antes de aplicar modelos.'
            ),
            'definicoes': [
                'DataFrame: estrutura tabular 2D do Pandas (linhas x colunas).',
                'Series: coluna unica de um DataFrame (array 1D com indice).',
                'EDA: Analise Exploratoria de Dados - investigar dados antes de modelar.',
                'GroupBy: agrupar dados por categoria e aplicar funcoes de agregacao.',
                'Merge/Join: combinar DataFrames por colunas em comum (como SQL JOIN).',
            ],
            'exemplo': (
                'import pandas as pd\n\n'
                '# Ler CSV\n'
                'df = pd.read_csv("vendas.csv")\n'
                'print(df.head())        # primeiras 5 linhas\n'
                'print(df.info())        # tipos e nulos\n'
                'print(df.describe())    # estatisticas\n\n'
                '# Filtrar\n'
                'vendas_sp = df[df["estado"] == "SP"]\n'
                'vendas_altas = df[df["valor"] > 1000]\n\n'
                '# Agrupar\n'
                'por_estado = df.groupby("estado")["valor"].agg(["sum", "mean", "count"])\n'
                'print(por_estado.sort_values("sum", ascending=False))\n\n'
                '# Tratar nulos\n'
                'df["email"].fillna("nao informado", inplace=True)\n'
                'df.dropna(subset=["valor"], inplace=True)\n\n'
                '# Nova coluna calculada\n'
                'df["lucro"] = df["valor"] - df["custo"]'
            ),
            'exemplo_tipo': 'codigo',
            'dica': (
                'Dica: Sempre comece com df.info() e df.describe() para entender seus dados. '
                'Verifique valores nulos com df.isnull().sum() e duplicatas com df.duplicated().sum(). '
                'Esses passos simples evitam muitos problemas depois.'
            ),
            'exercicios': [
                'Carregue um CSV de vendas e calcule: total vendido por mes, produto mais vendido, e media de valor por categoria.',
                'Crie um grafico de barras mostrando vendas por estado usando matplotlib.',
                'Trate um dataset com valores ausentes: identifique colunas com nulos, decida estrategia (remover ou preencher) e justifique.',
            ],
        },
    ],
}


# ============================================================
# Gerador de conteudo generico para disciplinas sem material
# detalhado. Produz conteudo educacional realista baseado nos
# topicos e ementa existentes.
# ============================================================
def gerar_conteudo_unidade_generico(disciplina_nome, topico, indice, total_topicos, ementa=''):
    """Gera conteudo educacional generico para uma unidade/topico."""
    # Extrair nome do topico (apos o ":")
    if ':' in topico:
        parts = topico.split(':', 1)
        unidade_label = parts[0].strip()
        topico_nome = parts[1].strip()
    else:
        unidade_label = f'Unidade {indice + 1}' if 'Unidade' not in topico and 'Modulo' not in topico else topico.split('-')[0].strip() if '-' in topico else topico
        topico_nome = topico

    # Determinar se e disciplina de programacao/tech
    tech_keywords = ['programacao', 'python', 'java', 'dados', 'web', 'mobile', 'devops', 'cloud',
                     'api', 'microsservico', 'docker', 'kubernetes', 'sql', 'nosql', 'react',
                     'machine learning', 'ia', 'inteligencia artificial', 'blockchain', 'iot',
                     'seguranca', 'teste', 'software', 'ci/cd', 'git', 'data science',
                     'cybersecurity', 'terraform', 'aws', 'lambda']
    is_tech = any(kw in disciplina_nome.lower() or kw in topico_nome.lower() for kw in tech_keywords)

    explicacao = (
        f'Nesta unidade, estudaremos {topico_nome.lower()}. '
        f'Este e um tema fundamental dentro de {disciplina_nome}, pois fornece a base conceitual '
        f'e pratica necessaria para o desenvolvimento profissional na area. '
        f'Compreender {topico_nome.lower()} permite ao aluno analisar problemas de forma mais '
        f'estruturada e aplicar solucoes adequadas em contextos reais. '
        f'Ao longo desta unidade, abordaremos os conceitos teoricos fundamentais, '
        f'apresentaremos exemplos praticos e discutiremos aplicacoes no mercado de trabalho. '
        f'E importante que o aluno acompanhe os exercicios propostos e busque aprofundar '
        f'o conhecimento com as leituras complementares indicadas na bibliografia.'
    )

    definicoes = [
        f'{topico_nome}: conceito central desta unidade, abordando os fundamentos teoricos e praticos.',
        f'Aplicacao pratica: como os conceitos de {topico_nome.lower()} sao utilizados em cenarios reais.',
    ]

    if is_tech:
        exemplo = (
            f'# Exemplo pratico: {topico_nome}\n'
            f'# Este exemplo demonstra a aplicacao dos conceitos\n'
            f'# estudados nesta unidade.\n\n'
            f'# Passo 1: Definir o problema\n'
            f'print("Aplicando conceitos de {topico_nome}")\n\n'
            f'# Passo 2: Implementar a solucao\n'
            f'def exemplo_{sanitize_for_func(topico_nome)}():\n'
            f'    """Demonstracao pratica dos conceitos."""\n'
            f'    # Implementacao baseada nos conceitos da unidade\n'
            f'    resultado = "Conceito aplicado com sucesso"\n'
            f'    return resultado\n\n'
            f'# Passo 3: Verificar o resultado\n'
            f'print(exemplo_{sanitize_for_func(topico_nome)}())'
        )
        exemplo_tipo = 'codigo'
    else:
        exemplo = (
            f'Exemplo pratico de {topico_nome}:\n\n'
            f'Cenario: Considere uma situacao profissional onde os conceitos de\n'
            f'{topico_nome.lower()} precisam ser aplicados.\n\n'
            f'Passo 1: Identificar o contexto e os requisitos do problema.\n'
            f'Passo 2: Aplicar os conceitos teoricos estudados nesta unidade.\n'
            f'Passo 3: Avaliar os resultados e propor melhorias.\n\n'
            f'Este tipo de analise e fundamental para profissionais da area\n'
            f'e sera aprofundado nas atividades praticas da disciplina.'
        )
        exemplo_tipo = 'texto'

    dica = (
        f'Dica importante: Ao estudar {topico_nome.lower()}, foque primeiro nos conceitos '
        f'fundamentais antes de partir para aplicacoes avancadas. Faca anotacoes, resolva os '
        f'exercicios propostos e busque exemplos adicionais na bibliografia recomendada.'
    )

    exercicios = [
        f'Explique com suas palavras os principais conceitos de {topico_nome.lower()} e sua importancia para {disciplina_nome}.',
        f'Apresente um exemplo pratico de aplicacao de {topico_nome.lower()} em um cenario profissional real.',
        f'Compare duas abordagens diferentes para {topico_nome.lower()} e discuta vantagens e desvantagens de cada uma.',
    ]

    return {
        'titulo': topico_nome if ':' in topico else topico,
        'explicacao': explicacao,
        'definicoes': definicoes,
        'exemplo': exemplo,
        'exemplo_tipo': exemplo_tipo,
        'dica': dica,
        'exercicios': exercicios,
    }


def sanitize_for_func(nome):
    """Converte nome para identificador Python valido."""
    import re as _re
    nome = nome.lower()
    nome = _re.sub(r'[^a-z0-9]', '_', nome)
    nome = _re.sub(r'_+', '_', nome).strip('_')
    return nome[:30]
