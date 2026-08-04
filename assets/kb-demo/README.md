# KB Demo — acervo sintético para demonstração

> **AVISO IMPORTANTE — CONTEÚDO SINTÉTICO.**
> Todo o material deste diretório é **gerado artificialmente, apenas para fins de
> demonstração** do módulo **Provas Online**. **Não há qualquer compromisso com
> correção técnica, precisão factual ou qualidade pedagógica.** Não use este conteúdo
> para estudo real, ensino ou avaliação de alunos. Em produção, substitua por um acervo
> real (veja "Como usar em produção" abaixo).

## O que é

Um acervo de exemplo que popula uma **Amazon Bedrock Knowledge Base** para o módulo de
estudo **Provas Online** (geração de questões via RAG + sugestão de material). Ele existe
para que qualquer pessoa consiga rodar a solução ponta a ponta **sem depender de um KB
externo pré-existente**.

Simula o acervo de um curso fictício de graduação em **Engenharia de Software** de uma
"Instituição de Ensino Demo": **40 disciplinas**, cada uma com três PDFs curtos e seus
metadados.

## Estrutura

```
privado/graduacao/eng-software/
  <disciplina>.pdf                     # documento base (ementa/plano resumido)
  <disciplina>_material.pdf            # apostila de conteúdo (priorizada nas sugestões de estudo)
  <disciplina>_email.pdf               # comunicado/e-mail (excluído da geração e do estudo)
  <disciplina>.pdf.metadata.json       # sidecar de metadados (idem para _material e _email)
```

- **240 objetos** = 40 disciplinas × (3 PDFs + 3 sidecars de metadados).
- Convenção de nome usada pelo código (`backend/common/online_grading.py`):
  - `*_material.pdf` → apostila de conteúdo (prioridade nas sugestões de estudo);
  - `*_email.pdf` → e-mail/comunicado (ignorado);
  - demais `*.pdf` → base (entra na recuperação, sem prioridade no estudo).
- Cada `*.pdf.metadata.json` segue o formato do Bedrock:

  ```json
  {
    "metadataAttributes": {
      "tipo": "disciplina",
      "modalidade": "graduacao",
      "curso_id": "eng-software",
      "disciplina": "Arquitetura de Software",
      "semestre": "4",
      "tipo_documento": "material",
      "is_apostila": true
    }
  }
  ```

  O código usa `disciplina` (vira o tema selecionável), `semestre` (ordenação) e `curso_id`.

## Disciplinas (40)

arquitetura_de_software, banco_de_dados_i, banco_de_dados_ii, big_data, blockchain,
calculo_i, calculo_ii, computacao_em_nuvem_avancada, comunicacao_e_expressao,
desenvolvimento_mobile, desenvolvimento_web, devops_e_cloud_computing,
empreendedorismo_digital, engenharia_de_software_i, engenharia_de_software_ii,
estagio_supervisionado_i, estagio_supervisionado_ii, estatistica, estrutura_de_dados,
etica_em_ti, fundamentos_de_computacao, gestao_de_projetos, inovacao_tecnologica,
inteligencia_artificial, introducao_a_programacao_python, iot_e_sistemas_embarcados,
logica_matematica, machine_learning, metodologias_ageis, microsservicos_e_apis,
programacao_orientada_a_objetos, projeto_final, projeto_integrador_i,
redes_de_computadores, seguranca_da_informacao, sistemas_operacionais, tcc_i, tcc_ii,
testes_de_software, ux_ui_design.

## Como provisionar (demo)

O script `scripts/deploy-kb.sh` cria o bucket de origem, sobe este acervo, provisiona a
Bedrock Knowledge Base e dispara a ingestão. Ver README principal, seção
"Provas Online (Knowledge Base)".

## Como usar em produção

Não use este acervo. Aponte `kbId`/`kbBucket` (contexto do CDK / `.env`) para a sua própria
Knowledge Base, com material real e as mesmas convenções de nome/metadados descritas acima.
