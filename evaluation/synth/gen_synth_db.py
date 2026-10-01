"""
合成业务库生成器（泛化 + 性能实验用）

目的：
  1. 表名 / 字段名与 Chinook 完全不同（中性命名 t_a..t_f / f_xxx），
     外键拓扑为“电商订单”，让大模型无法套用对 Chinook 的记忆；
  2. 数据规模可通过 --scale 参数放大，用于多规模性能测试。

产物（默认 evaluation/synth/）：
  synth.db          合成 SQLite 库
  schema_synth.json 表结构（外键拓扑，供 BFS / 校验）
  aliases.json      中文别名语义层（中文词 -> 中性表 / 指标字段）

用法：
  python evaluation/synth/gen_synth_db.py --scale 1
"""

import argparse
import json
import random
import sqlite3
from pathlib import Path

SYNTH_DIR = Path(__file__).resolve().parent

DDL = [
    "CREATE TABLE t_f (id INTEGER PRIMARY KEY, f_area TEXT)",
    "CREATE TABLE t_e (id INTEGER PRIMARY KEY, f_label TEXT)",
    "CREATE TABLE t_a (id INTEGER PRIMARY KEY, f_name TEXT, "
    "f_region_id INTEGER REFERENCES t_f(id))",
    "CREATE TABLE t_d (id INTEGER PRIMARY KEY, f_title TEXT, f_price REAL, "
    "f_category_id INTEGER REFERENCES t_e(id))",
    "CREATE TABLE t_b (id INTEGER PRIMARY KEY, f_member_id INTEGER "
    "REFERENCES t_a(id), f_amount REAL, f_date TEXT)",
    "CREATE TABLE t_c (id INTEGER PRIMARY KEY, f_order_id INTEGER "
    "REFERENCES t_b(id), f_product_id INTEGER REFERENCES t_d(id), f_qty INTEGER)",
]

ALIASES = {
    "table_alias": {
        "会员": ["t_a"], "客户": ["t_a"], "顾客": ["t_a"],
        "订单": ["t_b"],
        "明细": ["t_c"],
        "商品": ["t_d"], "产品": ["t_d"],
        "类别": ["t_e"], "分类": ["t_e"],
        "地区": ["t_f"],
    },
    "metric_field": {
        "f_amount": ["金额", "消费", "总额", "订单额"],
        "f_qty": ["销量", "数量", "件数"],
    },
    "table_of_metric": {"f_amount": "t_b", "f_qty": "t_c"},
}

SURNAMES = list("王李张刘陈杨黄赵周吴徐孙马朱胡郭何林罗高")
GIVEN = list("伟芳娜敏静丽强磊军洋勇艳杰娟涛明超秀兰霞平刚桂英华")
AREAS = ["华北", "华东", "华南", "华中", "西南", "西北", "东北", "海外"]
CATS = ["电子产品", "服装鞋帽", "食品饮料", "图书文具", "家居日用",
        "美妆个护", "运动户外", "母婴玩具", "数码配件", "汽车用品"]
PRODUCT_WORDS = ["套装", "礼盒", "旗舰款", "经典款", "基础款", "升级款"]


def random_name(rng):
    return rng.choice(SURNAMES) + "".join(rng.sample(GIVEN, rng.randint(1, 2)))


def build(scale, seed=42):
    rng = random.Random(seed)

    n_members = 60 * scale
    n_products = 200 * scale
    n_orders = 400 * scale

    areas = AREAS
    cats = CATS

    members = [(i + 1, random_name(rng), rng.randint(1, len(areas)))
               for i in range(n_members)]
    products = []
    for i in range(n_products):
        cat = rng.randint(1, len(cats))
        title = cats[cat - 1][:2] + rng.choice(PRODUCT_WORDS) + str(i + 1)
        price = round(rng.uniform(5, 500), 2)
        products.append((i + 1, title, price, cat))

    orders = []
    lines = []
    line_id = 1
    for i in range(n_orders):
        member = rng.randint(1, n_members)
        year = rng.randint(2021, 2025)
        date = f"{year}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}"
        order_id = i + 1
        amount = 0.0
        for _ in range(rng.randint(1, 4)):
            product = rng.randint(1, n_products)
            qty = rng.randint(1, 5)
            price = products[product - 1][2]
            amount += price * qty
            lines.append((line_id, order_id, product, qty))
            line_id += 1
        orders.append((order_id, member, round(amount, 2), date))

    return areas, cats, members, products, orders, lines


def write_db(db_path, data):
    areas, cats, members, products, orders, lines = data
    conn = sqlite3.connect(db_path)
    try:
        for ddl in DDL:
            conn.execute(ddl)
        conn.executemany("INSERT INTO t_f VALUES (?,?)",
                         [(i + 1, a) for i, a in enumerate(areas)])
        conn.executemany("INSERT INTO t_e VALUES (?,?)",
                         [(i + 1, c) for i, c in enumerate(cats)])
        conn.executemany("INSERT INTO t_a VALUES (?,?,?)", members)
        conn.executemany("INSERT INTO t_d VALUES (?,?,?,?)", products)
        conn.executemany("INSERT INTO t_b VALUES (?,?,?,?)", orders)
        conn.executemany("INSERT INTO t_c VALUES (?,?,?,?)", lines)
        conn.commit()
    finally:
        conn.close()


def extract_schema(db_path, db_name):
    conn = sqlite3.connect(db_path)
    schema = {"database": db_name, "tables": {}}
    try:
        names = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        for name in names:
            cols = [{
                "name": r[1], "type": r[2], "notnull": bool(r[3]),
                "default": r[4], "primary_key": bool(r[5]),
            } for r in conn.execute(f'PRAGMA  table_info("{name}")')]
            fks = [{
                "from_column": r[3], "to_table": r[2], "to_column": r[4],
            } for r in conn.execute(f'PRAGMA foreign_key_list("{name}")')]
            schema["tables"][name] = {"columns": cols, "foreign_keys": fks}
    finally:
        conn.close()
    return schema


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scale", type=int, default=1)
    parser.add_argument("--out", type=Path, default=SYNTH_DIR / "synth.db")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    data = build(args.scale, args.seed)
    write_db(args.out, data)

    schema = extract_schema(args.out, f"synth_scale{args.scale}")
    schema_path = args.out.parent / "schema_synth.json"
    json.dump(schema, open(schema_path, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    alias_path = args.out.parent / "aliases.json"
    json.dump(ALIASES, open(alias_path, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    print(f"已生成合成库 scale={args.scale}: {args.out}")
    print("表行数:")
    conn = sqlite3.connect(args.out)
    for name in sorted(schema["tables"]):
        print(f"  {name}: {conn.execute(f'SELECT COUNT(*) FROM {name}').fetchone()[0]}")
    conn.close()


if __name__ == "__main__":
    main()
