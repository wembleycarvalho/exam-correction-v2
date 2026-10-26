const LABELS: Record<string, { text: string; cls: string }> = {
  enviando: { text: 'Enviando', cls: 'badge-upload' },
  processando: { text: 'Processando', cls: 'badge-proc' },
  revisar: { text: 'Revisar', cls: 'badge-review' },
  pronto: { text: 'Pronto', cls: 'badge-ready' },
  erro: { text: 'Erro', cls: 'badge-error' },
};

export default function StatusBadge({ status }: { status: string }) {
  const info = LABELS[status] || { text: status, cls: 'badge-proc' };
  return <span className={`badge ${info.cls}`}>{info.text}</span>;
}
