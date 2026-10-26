"""
Gera metadata do edital do vestibular existente e copia o PDF para output.
- Copia docs/edital_vestibular_2026_2.pdf -> output/apostilas/publico/
- Cria metadata JSON com tipo=publico, categoria=vestibular

Uso: python3 scripts/gerar_edital_vestibular.py
"""
import json
import os
import shutil

OUTPUT_DIR = os.path.join('output', 'apostilas', 'publico')
SOURCE_PDF = os.path.join('docs', 'edital_vestibular_2026_2.pdf')
DEST_PDF = os.path.join(OUTPUT_DIR, 'edital_vestibular_2026_2.pdf')
METADATA_FILE = os.path.join(OUTPUT_DIR, 'edital_vestibular_2026_2.pdf.metadata.json')

def main():
    # Garante que o diretorio existe
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Copia o PDF do edital
    if not os.path.exists(SOURCE_PDF):
        print(f'ERRO: PDF fonte nao encontrado: {SOURCE_PDF}')
        return

    shutil.copy2(SOURCE_PDF, DEST_PDF)
    print(f'PDF copiado: {SOURCE_PDF} -> {DEST_PDF}')

    # Cria metadata JSON
    metadata = {
        "metadataAttributes": {
            "tipo": "publico",
            "categoria": "vestibular"
        }
    }

    with open(METADATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    print(f'Metadata criado: {METADATA_FILE}')

    print('\nDone! Edital do vestibular pronto para upload.')

if __name__ == '__main__':
    main()
