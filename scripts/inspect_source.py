"""Diagnóstico de leitura: perfil público e esquema do destino, sem credenciais."""

import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.extract import Extract


def main():
    ext = Extract(usar_mongo=False)
    rows = ext.baixar_demandas_api()
    counts = {
        key: collections.Counter(str(row.get(key)) for row in rows) for key in rows[0]
    }
    print(
        json.dumps(
            {
                "rows": len(rows),
                "fields": list(rows[0]),
                "categories": {
                    key: dict(counts[key])
                    for key in counts
                    if key in ("RPA", "SITUACAO", "GRUPOSERVICO_DESCRICAO")
                },
                "dates": {
                    key: [min(counts[key]), max(counts[key])]
                    for key in counts
                    if "DATA" in key
                },
                "missing": {
                    key: {
                        v: n
                        for v, n in counter.items()
                        if v.strip().upper()
                        in (
                            "",
                            "NONE",
                            "NULL",
                            "-",
                            "N/A",
                            "...",
                            "NAO INFORMADO",
                            "NÃO INFORMADO",
                        )
                    }
                    for key, counter in counts.items()
                },
                "exact_repeats": len(rows)
                - len({json.dumps(r, sort_keys=True) for r in rows}),
            },
            ensure_ascii=True,
            indent=2,
        )
    )
    target = Path(__file__).resolve().parents[1] / "data" / "source_diagnostic.json"
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
