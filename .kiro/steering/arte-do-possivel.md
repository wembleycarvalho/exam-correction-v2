# Premissa — "A Arte do Possível"

O portal **A Arte do Possível WEB** existe para **provar conceitos com tecnologia, sempre
ligados a problemas reais**. Não é demo pela demo: cada módulo/ideia mostra o que dá para
fazer com a tecnologia **resolvendo (ou aproximando de) um problema real** de uma instituição
de ensino.

## Regra para sugerir novas ideias e tecnologias

Ao propor qualquer nova funcionalidade, serviço AWS ou tecnologia, avalie e explicite:

1. **Problema real** — qual dor concreta de uma escola/universidade isso resolve? (ex.: montar
   grade, evitar evasão, orientar carreira, corrigir em escala, atendimento ao aluno.)
2. **Prova de conceito** — o que a tecnologia demonstra de novo/possível que antes era difícil.
3. **Aterramento em dado/fluxo real** — prefira dados e integrações que se pareçam com o mundo
   real (LMS/SIS como Moodle, catálogos, matrículas, notas) em vez de dados puramente
   artificiais. Dado sintético é aceitável como ponte, mas o **volume e o formato** devem se
   aproximar do real para o conceito ser convincente.
4. **Valor tangível** — ganho mensurável (custo, tempo, acurácia, acesso) e, quando possível,
   medível no próprio portal.
5. **Fidelidade aos princípios de engenharia** — simplicidade → serverless → segurança → custo
   (ver `tech.md`/`principles.md`).

## Como isso orienta decisões

- Preferir fontes de dados **realistas** (ex.: um Moodle populado em volume próximo ao de uma
  universidade) a datasets sintéticos bespoke, quando isso tornar o conceito mais crível e
  destravar serviços que brilham sobre dado real (ex.: AWS Context, analytics, governança).
- Cada módulo deve ter uma **narrativa de problema real** clara no seu README.
- Ao trazer um serviço novo, dizer honestamente onde o encaixe é **forte** (produção real) vs
  **conceitual** (protótipo sintético), sem superestimar.
