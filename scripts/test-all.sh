#!/usr/bin/env bash
# Bateria de regressão: roda as suítes unitárias de todos os módulos.
# (e2e/live fica em scripts/smoke-test.sh, contra a infra implantada.)
set -uo pipefail
cd "$(dirname "$0")/.."

# Python com pytest disponível (reusa o venv do orientador; fallback para python3).
PY="${TEST_PY:-orientador-academico/.venv/bin/python}"
[[ -x "$PY" ]] || PY="python3"

rc=0
run() { # <nome> <dir> [cwd]
  local name="$1" dir="$2" cwd="${3:-.}"
  echo "== $name ($dir) =="
  ( cd "$cwd" && "$OLDPWD/$PY" -m pytest "$dir" -q ) 2>&1 | tail -6
  local st=${PIPESTATUS[0]}
  [[ "$st" == "0" ]] && echo "   OK" || { echo "   FALHOU ($st)"; rc=1; }
}

# avaliacao (provas: discursiva/redação/objetiva/online) — pytest.ini/conftest do módulo
run "avaliacao" "tests" "avaliacao"
# orientador — venv próprio (tem as deps do módulo)
if [[ -x "orientador-academico/.venv/bin/python" ]]; then
  echo "== orientador (tests) =="
  ( cd orientador-academico && .venv/bin/python -m pytest tests -q ) 2>&1 | tail -6
  [[ ${PIPESTATUS[0]} == 0 ]] && echo "   OK" || { echo "   FALHOU"; rc=1; }
fi
# lms
run "lms" "lms"
# entrevistador — esqueleto (placeholder skipado até haver cobertura real)
run "interviewer" "tests" "interviewer"

echo ">> regressão: $([[ $rc == 0 ]] && echo TUDO VERDE || echo COM FALHAS)"
exit $rc
