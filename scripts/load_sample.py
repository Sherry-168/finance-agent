"""把演示账单 CSV 导入本地 SQLite，验证「规则分类 + 元转分」链路。

输入字段对齐《项目方案设计文档》§8（江为的 demo 格式）：
    date,time,description,merchant,amount,payment_method
其中 amount 为「元」，category 由规则词典从 description+merchant 推断，source 记为 demo。

运行：python scripts/load_sample.py [csv_path]
"""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import dao  # noqa: E402
from logic.classify import classify  # noqa: E402
from logic.money import yuan_to_cents  # noqa: E402

CSV_PATH = Path(__file__).resolve().parent.parent / "data" / "sample_transactions.csv"


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else CSV_PATH
    conn = dao.connect()
    dao.init_db(conn)

    with path.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    n = 0
    for r in rows:
        if not r.get("date") or not r.get("amount"):
            continue
        record = {
            "amount_cents": yuan_to_cents(r["amount"]),
            "category": classify(f"{r.get('description', '')} {r.get('merchant', '')}"),
            "merchant": r.get("merchant") or None,
            "occurred_at": f"{r['date']} {r.get('time') or '00:00'}:00",
            "source": "demo",
            "raw_text": r.get("description"),
            "note": None,
            "confirmed": 1,
        }
        dao.add_record(conn, record)
        n += 1

    conn.close()
    print(f"已导入 {n} 条演示流水（分类由规则词典推断）")


if __name__ == "__main__":
    main()
