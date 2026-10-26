# Avisos de terceiros (Third-Party Notices)

Este projeto usa bibliotecas e frameworks de código aberto. Abaixo estão as licenças e
atribuições correspondentes. Os textos completos das licenças estão nos links oficiais e/ou
nos arquivos `LICENSE`/`NOTICE`/`LICENSE-3RD-PARTY.txt` distribuídos com cada pacote.

> As bibliotecas são usadas **como estão** (sem modificação). Este arquivo cumpre a
> obrigação de atribuição das licenças permissivas (MIT, BSD, Apache-2.0) e sinaliza o
> componente LGPL embarcado pelo OpenCV.

## Servido ao navegador (frontend)

| Componente | Versão | Licença | Observação |
|---|---|---|---|
| **OpenCV.js** | 4.9.0 | Apache-2.0 (+ terceiros) | Servido em `/opencv.js` (via CloudFront). OMR e QR no navegador. Inclui componentes de terceiros do OpenCV. |

- OpenCV — https://github.com/opencv/opencv (Apache-2.0): https://github.com/opencv/opencv/blob/4.x/LICENSE

## Runtime backend (worker / agentes / API)

| Componente | Licença | Projeto / licença |
|---|---|---|
| **opencv-python-headless** | Apache-2.0 **+ terceiros (inclui FFmpeg LGPL-2.1+)** | https://github.com/opencv/opencv-python — ver `LICENSE.txt` e `LICENSE-3RD-PARTY.txt` |
| **NumPy** | BSD-3-Clause | https://github.com/numpy/numpy/blob/main/LICENSE.txt |
| **boto3** / **botocore** | Apache-2.0 | https://github.com/boto/boto3/blob/develop/LICENSE |
| **Pydantic** | MIT | https://github.com/pydantic/pydantic/blob/main/LICENSE |
| **Strands Agents** (`strands-agents`) | Apache-2.0 | https://github.com/strands-agents/sdk-python |
| **Bedrock AgentCore SDK / starter toolkit** | Apache-2.0 | https://github.com/aws/bedrock-agentcore-sdk-python |

### OpenCV (opencv-python-headless) — componentes de terceiros / FFmpeg (LGPL)

O wheel do `opencv-python-headless` redistribui o binário do OpenCV (Apache-2.0) e
bibliotecas de terceiros, entre elas **FFmpeg (LGPL-2.1 ou posterior)** e codecs de imagem
(libjpeg-turbo, libpng, libwebp, libtiff, OpenJPEG — licenças permissivas tipo BSD/zlib). A
lista completa e os textos estão em `LICENSE-3RD-PARTY.txt` dentro do pacote instalado
(`cv2/`) e em:

- https://github.com/opencv/opencv-python/blob/4.x/LICENSE-3RD-PARTY.txt
- FFmpeg (LGPL-2.1+): https://www.ffmpeg.org/legal.html

Uso neste projeto: apenas leitura de **imagem estática** e **QR** (não usamos vídeo). O
FFmpeg vem embarcado no wheel oficial e é mantido sem modificação (uso via biblioteca
dinâmica), preservando a possibilidade de substituição exigida pela LGPL.

## Ferramentas de desenvolvimento / build (não vão para o produto em execução)

| Componente | Licença | Projeto |
|---|---|---|
| **AWS CDK** (`aws-cdk-lib`) | Apache-2.0 | https://github.com/aws/aws-cdk |
| **diagrams** (mingrammer) | MIT | https://github.com/mingrammer/diagrams |
| **pytest** | MIT | https://github.com/pytest-dev/pytest |
| **qrcode** (uso só em teste local) | BSD-3-Clause | https://github.com/lincolnloop/python-qrcode |

Observações:
- O diagrama de arquitetura usa ícones oficiais da AWS (via `diagrams`), que são **marcas
  registradas da Amazon** — usados apenas em documentação, sem relicenciamento.
- Serviços gerenciados da AWS (Lambda, S3, DynamoDB, SQS, CloudFront, Cognito, WAF, Bedrock,
  AgentCore) são consumidos como serviço, não redistribuídos — regidos pelos termos da AWS.
- Ícones/emojis na interface são caracteres Unicode (sem licença de software).

_Versões exatas do backend/agentes: ver `backend/*/requirements.txt` e `agents/requirements.txt`.
Infra: `infra/requirements.txt`._
