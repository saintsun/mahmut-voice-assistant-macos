#!/bin/bash
# Panelin JavaScript'ini sozdizimi acisindan denetler.
# Panel HTML'i Python string'i icinde yasadigi icin kacis karakterleri
# kolayca bozulabiliyor; bozulunca sayfadaki HIC bir dugme calismiyor
# ama hata hicbir yerde gorunmuyor. Her panel degisikliginden sonra calistir.
cd "$(dirname "$0")"
command -v node >/dev/null || { echo "node yok, denetim atlandı"; exit 0; }
PYTHONPATH=. ./.venv/bin/python - <<'PY' > /tmp/cv_panel.js
import re
from claudevoice.panel import PAGE
m = re.search(r"<script>(.*?)</script>", PAGE, re.S)
print(m.group(1) if m else "")
PY
if node --check /tmp/cv_panel.js 2>/tmp/cv_panel.err; then
  echo "✅ panel JavaScript sözdizimi temiz"
else
  echo "❌ panel JavaScript HATALI:"; cat /tmp/cv_panel.err; exit 1
fi
