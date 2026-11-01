# -*- coding: utf-8 -*-
"""R8 智谷园区运营平台业务数据（幂等）。

- 只写 ry_r8：4 张 biz_* 表 + 组织/用户/日志 + 业务菜单/角色授权
- 重复执行会先删除本脚本自己的数据再重建，不删除框架原有数据
- 同时落盘 seed/r8_business.sql
"""
import datetime as dt
import random
from decimal import Decimal
from pathlib import Path

import pymysql

ROOT = Path(__file__).resolve().parent.parent
SQL_OUT = ROOT / "seed" / "r8_business.sql"

DB = dict(host="127.0.0.1", port=13307, user="root", password="", database="ry_r8", charset="utf8mb4")
ADMIN_HASH = "$2a$10$7JB720yubVSZvUI0rEqK/.VqGOZTH.ulu33dHOiBE8ByOhJIrdAu2"
NOW = dt.datetime.now().replace(microsecond=0)
TODAY = NOW.date()
rnd = random.Random(20261031)

DDL = [
    """
    CREATE TABLE IF NOT EXISTS biz_enterprise (
      id BIGINT NOT NULL AUTO_INCREMENT,
      enterprise_name VARCHAR(120) NOT NULL,
      credit_code CHAR(18) NOT NULL,
      industry VARCHAR(32) NOT NULL,
      contact_name VARCHAR(32) NOT NULL,
      phone VARCHAR(32) NOT NULL,
      floor VARCHAR(16) NOT NULL,
      area DECIMAL(10,2) NOT NULL,
      status VARCHAR(16) NOT NULL,
      create_time DATETIME NOT NULL,
      PRIMARY KEY (id),
      UNIQUE KEY uk_biz_enterprise_credit (credit_code),
      KEY idx_biz_enterprise_status (status)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='入园企业'
    """,
    """
    CREATE TABLE IF NOT EXISTS biz_lease (
      id BIGINT NOT NULL AUTO_INCREMENT,
      contract_no VARCHAR(32) NOT NULL,
      enterprise_id BIGINT NOT NULL,
      start_date DATE NOT NULL,
      end_date DATE NOT NULL,
      monthly_rent DECIMAL(12,2) NOT NULL,
      deposit DECIMAL(12,2) NOT NULL,
      status VARCHAR(16) NOT NULL,
      create_time DATETIME NOT NULL,
      PRIMARY KEY (id),
      UNIQUE KEY uk_biz_lease_contract (contract_no),
      KEY idx_biz_lease_enterprise (enterprise_id),
      KEY idx_biz_lease_status (status)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='园区租约'
    """,
    """
    CREATE TABLE IF NOT EXISTS biz_energy (
      id BIGINT NOT NULL AUTO_INCREMENT,
      enterprise_id BIGINT NOT NULL,
      month CHAR(7) NOT NULL,
      electricity DECIMAL(10,2) NOT NULL,
      water DECIMAL(10,2) NOT NULL,
      cost DECIMAL(12,2) NOT NULL,
      read_time DATETIME NOT NULL,
      create_time DATETIME NOT NULL,
      PRIMARY KEY (id),
      UNIQUE KEY uk_biz_energy_ent_month (enterprise_id, month),
      KEY idx_biz_energy_month (month)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='企业能耗抄表'
    """,
    """
    CREATE TABLE IF NOT EXISTS biz_visit (
      id BIGINT NOT NULL AUTO_INCREMENT,
      visitor_name VARCHAR(32) NOT NULL,
      phone_masked VARCHAR(32) NOT NULL,
      enterprise_id BIGINT NOT NULL,
      visit_time DATETIME NOT NULL,
      leave_time DATETIME DEFAULT NULL,
      reason VARCHAR(120) NOT NULL,
      status VARCHAR(16) NOT NULL,
      create_time DATETIME NOT NULL,
      PRIMARY KEY (id),
      KEY idx_biz_visit_time (visit_time),
      KEY idx_biz_visit_enterprise (enterprise_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='园区访客登记'
    """,
]

PLACES = [
    "南宁", "广西", "邕城", "绿城", "五象", "青秀",
    "西乡塘", "江南", "良庆", "武鸣", "横州", "宾阳",
]
# 90 个品牌词，180 条企业每个品牌最多出现 2 次
BRANDS = [
    "瀚海", "绿洲", "跨境", "云栖", "恒锐", "博远", "华芯", "启航", "汇通", "光谷",
    "新元", "锐驰", "智谷", "壮乡", "邕江", "东盟", "八桂", "青山", "蓝湾", "金桥",
    "星河", "远景", "中科", "华南", "桂能", "绿源", "天骄", "德胜", "嘉禾", "瑞丰",
    "鑫源", "联创", "众诚", "卓越", "鼎盛", "宏图", "兴业", "泰和", "安泰", "正邦",
    "海纳", "百川", "千寻", "万象", "三祺", "五洲", "九州", "四海", "天成", "地源",
    "人和", "政通", "锦绣", "春晖", "秋实", "夏荷", "冬青", "木棉", "朱槿", "凤凰",
    "麒麟", "龙腾", "虎跃", "鹏程", "鸿运", "福瑞", "祥云", "紫荆", "红树", "白鹭",
    "银滩", "涠洲", "德天", "明仕", "左江", "右江", "红水", "柳江", "漓江", "桂江",
    "西江", "北部", "钦州", "铁山", "防城", "东兴", "凭祥", "龙州", "大新", "靖西",
]
SUFFIXES = ["有限公司", "股份有限公司"]
INDUSTRIES = ["电子信息", "生物医药", "现代物流", "商贸服务", "新材料", "其他"]
INDUSTRY_COUNTS = [54, 27, 36, 27, 22, 14]  # 30% / 15% / 20% / 15% / 12% / 8%
INDUSTRY_WORDS = {
    "电子信息": ["智能科技", "电子信息", "数字科技"],
    "生物医药": ["生物医药", "生物科技", "医药科技"],
    "现代物流": ["供应链", "现代物流", "智慧物流"],
    "商贸服务": ["商贸", "商贸服务", "数字创意"],
    "新材料": ["新材料", "新材科技", "环保材料"],
    "其他": ["节能环保", "数字创意", "科技服务"],
}
CREDIT_CHARS = "0123456789ABCDEFGHJKLMNPQRTUWXY"
CONTACTS = [
    "黄志强", "李美玲", "韦建国", "梁晓燕", "覃海峰", "农丽娟", "陆文斌", "蓝晓梅", "蒙志刚", "杨雪梅",
    "卢建华", "周敏", "吴国平", "郑丽萍", "冯志远", "陈晓红", "禤文杰", "何美芳", "罗志勇", "钟丽华",
    "徐海波", "苏晓静", "莫国强", "唐小燕", "覃志明", "李红梅", "韦海涛", "黄丽娟", "梁建国", "农晓峰",
]
REGION_CODES = [
    "450102", "450103", "450105", "450107", "450108", "450109",
    "450110", "450123", "450124", "450125", "450202", "450203",
    "450204", "450205", "450321", "450322", "450323", "450324",
]
REASONS = ["业务洽谈", "合同签署", "设备维护", "财务对账", "面试应聘", "参观考察", "项目对接", "物流提货"]
CENTERS = [
    ("园区运营中心", "黄志强"), ("招商服务中心", "李美玲"), ("企业服务中心", "韦建国"),
    ("物业服务中心", "梁晓燕"), ("能源管理中心", "覃海峰"), ("安全保卫中心", "农丽娟"),
]
GROUPS = [
    ("综合管理组", 2001, "陆文斌"), ("招商一组", 2002, "蓝晓梅"), ("招商二组", 2002, "蒙志刚"),
    ("企业服务组", 2003, "杨雪梅"), ("物业维修组", 2004, "卢建华"), ("能源抄表组", 2005, "周敏"),
    ("安保巡逻组", 2006, "吴国平"), ("客户服务组", 2003, "郑丽萍"), ("数据运营组", 2001, "冯志远"),
    ("财务结算组", 2001, "陈晓红"),
]
USERS = [
    "黄志强", "李美玲", "韦建国", "梁晓燕", "覃海峰", "农丽娟", "陆文斌", "蓝晓梅", "蒙志刚", "杨雪梅",
    "卢建华", "周敏", "吴国平", "郑丽萍", "冯志远", "陈晓红", "禤文杰", "何美芳", "罗志勇", "钟丽华",
    "徐海波", "苏晓静", "莫国强", "唐小燕", "覃志明", "李红梅", "韦海涛", "黄丽娟",
]


def q(value):
    if value is None:
        return "NULL"
    if isinstance(value, (int, float, Decimal)):
        return str(value)
    if isinstance(value, dt.datetime):
        return "'%s'" % value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, dt.date):
        return "'%s'" % value.strftime("%Y-%m-%d")
    text = str(value).replace("\\", "\\\\").replace("'", "\\'")
    return "'%s'" % text


def rand_dt(start, end):
    delta = int((end - start).total_seconds())
    return start + dt.timedelta(seconds=rnd.randint(0, max(delta, 1)))


def credit_code():
    return "91" + rnd.choice(REGION_CODES) + "".join(rnd.choices(CREDIT_CHARS, k=10))


def gen_enterprises():
    rows = []
    statuses = ["在驻"] * 140 + ["退租"] * 25 + ["待入驻"] * 15
    rnd.shuffle(statuses)
    industry_pool = []
    for name, count in zip(INDUSTRIES, INDUSTRY_COUNTS):
        industry_pool.extend([name] * count)
    names = set()
    codes = set()
    brand_counts = {}
    for i in range(180):
        place = PLACES[(i + (i // len(BRANDS)) * 5) % len(PLACES)]
        brand = BRANDS[i % len(BRANDS)]
        category = industry_pool[i]
        words = INDUSTRY_WORDS[category]
        word = words[(i + (i // len(BRANDS))) % len(words)]
        suffix = SUFFIXES[1] if i % 7 == 0 else SUFFIXES[0]
        name = place + brand + word + suffix
        if name in names:
            raise RuntimeError("企业名重复: %s" % name)
        names.add(name)
        brand_counts[brand] = brand_counts.get(brand, 0) + 1
        if brand_counts[brand] > 2:
            raise RuntimeError("品牌词超过 2 次: %s" % brand)
        code = credit_code()
        while code in codes:
            code = credit_code()
        codes.add(code)
        area = round(rnd.uniform(80, 1200), 2)
        created = rand_dt(dt.datetime(2025, 1, 5, 9, 0), NOW - dt.timedelta(days=20))
        rows.append((
            2001 + i, name, code, category, CONTACTS[i % len(CONTACTS)],
            "13%d%08d" % (rnd.choice([8, 9, 5, 7]), rnd.randint(0, 99999999)),
            "%s座%02dF-%02d" % (rnd.choice("ABCD"), rnd.randint(1, 18), rnd.randint(1, 20)),
            area, statuses[i], created,
        ))
    if len(names) != 180:
        raise RuntimeError("企业名不是 180 条唯一: %d" % len(names))
    return rows


def gen_leases(enterprises):
    rows = []
    by_id = {row[0]: row for row in enterprises}
    for i in range(260):
        if i < 180:
            ent = enterprises[i]
        else:
            ent = enterprises[rnd.randrange(180)]
        ent_id = ent[0]
        area = ent[7]
        start = rand_dt(dt.datetime(2025, 1, 1, 9, 0), dt.datetime(2026, 9, 30, 17, 0)).date()
        end = start + dt.timedelta(days=rnd.randint(365, 1095))
        if end < TODAY:
            status = "到期"
        elif end <= TODAY + dt.timedelta(days=180):
            status = "续签中"
        else:
            status = "生效"
        rent = Decimal(str(round(area * rnd.uniform(35, 80), 2)))
        deposit = (rent * 3).quantize(Decimal("0.01"))
        created = dt.datetime.combine(start, dt.time(rnd.randint(9, 17), rnd.randint(0, 59)))
        created = max(dt.datetime(2025, 1, 1, 9, 0), created - dt.timedelta(days=rnd.randint(1, 20)))
        if created > NOW:
            created = NOW - dt.timedelta(days=rnd.randint(1, 20))
        rows.append((3001 + i, "ZZ-%s-%04d" % (start.strftime("%Y"), i + 1), ent_id, start, end, rent, deposit, status, created))
    return rows


def gen_energy(enterprises):
    rows = []
    months = ["2026-%02d" % m for m in range(1, 11)]
    for idx in range(150):
        ent = enterprises[idx]
        ent_id, area = ent[0], ent[7]
        for month in months:
            m = int(month[-2:])
            season = 1.35 if 6 <= m <= 9 else (1.05 if m == 10 else 1.0)
            electricity = Decimal(str(round(area * 1.15 * season * rnd.uniform(0.85, 1.18), 2)))
            water = Decimal(str(round(area * 0.05 * rnd.uniform(0.8, 1.2), 2)))
            cost = (electricity * Decimal("0.82") + water * Decimal("3.60")).quantize(Decimal("0.01"))
            read_day = 30 if m == 10 else 28
            read_time = dt.datetime(2026, m, read_day, 18, 0)
            if read_time > NOW:
                read_time = NOW - dt.timedelta(hours=2)
            rows.append((4001 + len(rows), ent_id, month, electricity, water, cost, read_time, read_time))
    return rows


def gen_visits(enterprises):
    rows = []
    start = dt.date(2026, 5, 1)
    days = []
    while start <= dt.date(2026, 10, 30):
        days.append(start)
        start += dt.timedelta(days=1)
    weighted = []
    for day in days:
        weighted.extend([day] * (2 if day.weekday() < 5 else 1))
    for i in range(800):
        day = rnd.choice(weighted)
        visit = dt.datetime.combine(day, dt.time(rnd.randint(8, 16), rnd.choice([0, 10, 20, 30, 40, 50])))
        leave = visit + dt.timedelta(minutes=rnd.randint(30, 180))
        if leave > NOW:
            leave = NOW - dt.timedelta(minutes=rnd.randint(1, 30))
        status = "在访" if leave >= NOW - dt.timedelta(hours=2) else "已离开"
        ent = enterprises[rnd.randrange(180)]
        rows.append((
            5001 + i, rnd.choice(CONTACTS), "1%d****%04d" % (rnd.choice([38, 39, 58, 77]), rnd.randint(0, 9999)),
            ent[0], visit, leave, rnd.choice(REASONS), status, visit - dt.timedelta(minutes=rnd.randint(5, 90)),
        ))
    return rows


def gen_depts():
    rows = [(2001 + i, 100, "0,100", name, i + 1, leader, "138%08d" % rnd.randint(0, 99999999), "", "0", "0", "admin", dt.datetime(2025, 3, 1, 9, 0)) for i, (name, leader) in enumerate(CENTERS)]
    for i, (name, parent, leader) in enumerate(GROUPS):
        rows.append((2007 + i, parent, "0,100,%d" % parent, name, i + 1, leader, "138%08d" % rnd.randint(0, 99999999), "", "0", "0", "admin", dt.datetime(2025, 3, 1, 9, 30)))
    return rows


def gen_users():
    rows = []
    for i in range(28):
        dept = 2001 + (i % 16)
        created = rand_dt(dt.datetime(2025, 1, 10, 9, 0), dt.datetime(2026, 6, 30, 18, 0))
        rows.append((
            2001 + i, dept, "ZG%04d" % (i + 1), USERS[i], "00", "zg%04d@zhigu.example" % (i + 1),
            "138%08d" % rnd.randint(0, 99999999), str(rnd.randint(0, 1)), "", ADMIN_HASH, "0", "0",
            "10.20.30.%d" % rnd.randint(20, 80), created, created, "admin", created, "", None, None,
        ))
    return rows


def gen_login_logs(users):
    rows = []
    names = [u[2] for u in users]
    for i in range(280):
        day = rnd.choice([d for d in (dt.date(2026, 10, 1) + dt.timedelta(days=k) for k in range(30)) if d.weekday() < 5] * 4 + [d for d in (dt.date(2026, 10, 1) + dt.timedelta(days=k) for k in range(30)) if d.weekday() >= 5])
        ts = dt.datetime.combine(day, dt.time(rnd.randint(8, 18), rnd.randint(0, 59)))
        if ts > NOW:
            ts = NOW - dt.timedelta(minutes=rnd.randint(5, 120))
        ok = rnd.random() < 0.86
        rows.append((6001 + i, rnd.choice(names), "10.20.30.%d" % rnd.randint(20, 90), "0" if ok else "1", "登录成功" if ok else "密码错误", ts))
    return rows


def gen_oper_logs(users):
    rows = []
    titles = ["企业入驻", "租约管理", "能耗抄表", "访客登记", "用户管理", "部门管理", "菜单管理", "角色管理"]
    urls = ["/system/business/enterprises", "/system/business/leases", "/system/business/energies", "/system/business/visits", "/system/user", "/system/dept", "/system/menu", "/system/role"]
    for i in range(380):
        day = rnd.choice([d for d in (dt.date(2026, 10, 1) + dt.timedelta(days=k) for k in range(30)) if d.weekday() < 5] * 5 + [d for d in (dt.date(2026, 10, 1) + dt.timedelta(days=k) for k in range(30)) if d.weekday() >= 5])
        ts = dt.datetime.combine(day, dt.time(rnd.randint(8, 18), rnd.randint(0, 59)))
        if ts > NOW:
            ts = NOW - dt.timedelta(minutes=rnd.randint(5, 180))
        idx = rnd.randrange(len(titles))
        user = users[rnd.randrange(len(users))]
        rows.append((7001 + i, titles[idx], rnd.randint(1, 3), "com.ruoyi.system.controller.BizController", "GET" if idx < 4 else "POST", 1, user[3], "智谷园区运营中心", urls[idx], "10.20.30.%d" % rnd.randint(20, 90), "广西南宁", "", '{"code":200,"msg":"操作成功"}', 0, "", ts, rnd.randint(20, 900)))
    return rows


def insert(conn, table, columns, rows, dump):
    if not rows:
        return
    placeholders = ",".join(["%s"] * len(columns))
    sql = "INSERT INTO %s (%s) VALUES (%s)" % (table, ",".join(columns), placeholders)
    with conn.cursor() as cur:
        cur.executemany(sql, rows)
    dump.append("INSERT INTO %s (%s) VALUES" % (table, ",".join(columns)))
    dump.append(",\n".join("(" + ",".join(q(v) for v in row) + ")" for row in rows) + ";")


def _dump_table(cur, lines, table, where="", ignore=False):
    cur.execute("SELECT * FROM %s %s" % (table, where))
    columns = [item[0] for item in cur.description]
    rows = cur.fetchall()
    if not rows:
        return
    prefix = "INSERT IGNORE" if ignore else "INSERT"
    lines.append("%s INTO %s (%s) VALUES" % (prefix, table, ",".join(columns)))
    lines.append(",\n".join("(" + ",".join(q(v) for v in row) + ")" for row in rows) + ";")


def dump_database():
    """按当前库内容落盘，确保 names/credits 更新后 SQL 文件同步。"""
    conn = pymysql.connect(**DB)
    lines = ["SET NAMES utf8mb4;", "USE ry_r8;"]
    try:
        with conn.cursor() as cur:
            for ddl in DDL:
                lines.append(ddl.strip() + ";")
            for table in ("biz_enterprise", "biz_lease", "biz_energy", "biz_visit"):
                lines.append("DELETE FROM %s;" % table)
                _dump_table(cur, lines, table)
            for table, where in (
                ("sys_dept", "WHERE dept_id BETWEEN 2001 AND 2016"),
                ("sys_user", "WHERE user_id BETWEEN 2001 AND 2028"),
                ("sys_user_role", "WHERE user_id BETWEEN 2001 AND 2028"),
                ("sys_logininfor", "WHERE info_id BETWEEN 6001 AND 6280"),
                ("sys_oper_log", "WHERE oper_id BETWEEN 7001 AND 7380"),
            ):
                lines.append("DELETE FROM %s %s;" % (table, where))
                _dump_table(cur, lines, table, where)
            _dump_table(cur, lines, "sys_menu", "WHERE menu_id BETWEEN 2000 AND 2007", ignore=True)
            _dump_table(
                cur, lines, "sys_role_menu",
                "WHERE role_id=1 AND menu_id BETWEEN 2000 AND 2007", ignore=True,
            )
    finally:
        conn.close()
    SQL_OUT.parent.mkdir(parents=True, exist_ok=True)
    SQL_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    enterprises = gen_enterprises()
    leases = gen_leases(enterprises)
    energy = gen_energy(enterprises)
    visits = gen_visits(enterprises)
    depts = gen_depts()
    users = gen_users()
    login_logs = gen_login_logs(users)
    oper_logs = gen_oper_logs(users)

    conn = pymysql.connect(**DB, autocommit=False)
    dump = ["SET NAMES utf8mb4;", "USE ry_r8;"]
    try:
        with conn.cursor() as cur:
            for ddl in DDL:
                cur.execute(ddl)
                dump.append(ddl.strip() + ";")
            cur.execute("SELECT COUNT(*) FROM biz_enterprise")
            existing = cur.fetchone()[0]
            if existing >= len(enterprises):
                # 返工模式：只更新企业名称与信用代码，不动租约/能耗/访客及其外键
                cur.executemany(
                    "UPDATE biz_enterprise SET enterprise_name=%s, credit_code=%s, industry=%s WHERE id=%s",
                    [(row[1], row[2], row[3], row[0]) for row in enterprises],
                )
                conn.commit()
                dump_database()
                print("UPDATED_ENTERPRISE_ONLY enterprise=%d" % len(enterprises))
                print("SQL=%s" % SQL_OUT)
                return
            for table in ("biz_enterprise", "biz_lease", "biz_energy", "biz_visit"):
                cur.execute("DELETE FROM %s" % table)
                dump.append("DELETE FROM %s;" % table)
            insert(conn, "biz_enterprise", ["id", "enterprise_name", "credit_code", "industry", "contact_name", "phone", "floor", "area", "status", "create_time"], enterprises, dump)
            insert(conn, "biz_lease", ["id", "contract_no", "enterprise_id", "start_date", "end_date", "monthly_rent", "deposit", "status", "create_time"], leases, dump)
            insert(conn, "biz_energy", ["id", "enterprise_id", "month", "electricity", "water", "cost", "read_time", "create_time"], energy, dump)
            insert(conn, "biz_visit", ["id", "visitor_name", "phone_masked", "enterprise_id", "visit_time", "leave_time", "reason", "status", "create_time"], visits, dump)

            cur.execute("DELETE FROM sys_user_role WHERE user_id BETWEEN 2001 AND 2028")
            cur.execute("DELETE FROM sys_user WHERE user_id BETWEEN 2001 AND 2028")
            cur.execute("DELETE FROM sys_dept WHERE dept_id BETWEEN 2001 AND 2016")
            cur.execute("DELETE FROM sys_logininfor WHERE info_id BETWEEN 6001 AND 6280")
            cur.execute("DELETE FROM sys_oper_log WHERE oper_id BETWEEN 7001 AND 7380")
            dump.extend([
                "DELETE FROM sys_user_role WHERE user_id BETWEEN 2001 AND 2028;",
                "DELETE FROM sys_user WHERE user_id BETWEEN 2001 AND 2028;",
                "DELETE FROM sys_dept WHERE dept_id BETWEEN 2001 AND 2016;",
                "DELETE FROM sys_logininfor WHERE info_id BETWEEN 6001 AND 6280;",
                "DELETE FROM sys_oper_log WHERE oper_id BETWEEN 7001 AND 7380;",
            ])
            insert(conn, "sys_dept", ["dept_id", "parent_id", "ancestors", "dept_name", "order_num", "leader", "phone", "email", "status", "del_flag", "create_by", "create_time"], depts, dump)
            insert(conn, "sys_user", ["user_id", "dept_id", "user_name", "nick_name", "user_type", "email", "phonenumber", "sex", "avatar", "password", "status", "del_flag", "login_ip", "login_date", "pwd_update_date", "create_by", "create_time", "update_by", "update_time", "remark"], users, dump)
            insert(conn, "sys_user_role", ["user_id", "role_id"], [(u[0], 2) for u in users], dump)
            insert(conn, "sys_logininfor", ["info_id", "user_name", "ipaddr", "status", "msg", "access_time"], login_logs, dump)
            insert(conn, "sys_oper_log", ["oper_id", "title", "business_type", "method", "request_method", "operator_type", "oper_name", "dept_name", "oper_url", "oper_ip", "oper_location", "oper_param", "json_result", "status", "error_msg", "oper_time", "cost_time"], oper_logs, dump)

            now = dt.datetime(2026, 10, 31, 9, 0)
            menus = [
                (2000, "业务管理", 0, 5, "business", None, None, "Business", 1, 0, "M", "0", "0", None, "el-icon-office-building", "admin", now, "", None, "园区业务管理"),
                (2001, "企业入驻", 2000, 1, "enterprise", "business/enterprise/index", None, "BusinessEnterprise", 1, 0, "C", "0", "0", "business:enterprise:list", "el-icon-office-building", "admin", now, "", None, ""),
                (2002, "租约管理", 2000, 2, "lease", "business/lease/index", None, "BusinessLease", 1, 0, "C", "0", "0", "business:lease:list", "el-icon-document", "admin", now, "", None, ""),
                (2003, "能耗抄表", 2000, 3, "energy", "business/energy/index", None, "BusinessEnergy", 1, 0, "C", "0", "0", "business:energy:list", "el-icon-odometer", "admin", now, "", None, ""),
                (2004, "访客登记", 2000, 4, "visit", "business/visit/index", None, "BusinessVisit", 1, 0, "C", "0", "0", "business:visit:list", "el-icon-user", "admin", now, "", None, ""),
                (2005, "企业查询", 2001, 1, "", None, None, "BusinessEnterpriseQuery", 1, 0, "F", "0", "0", "business:enterprise:list", "#", "admin", now, "", None, ""),
                (2006, "租约查询", 2002, 1, "", None, None, "BusinessLeaseQuery", 1, 0, "F", "0", "0", "business:lease:list", "#", "admin", now, "", None, ""),
                (2007, "能耗查询", 2003, 1, "", None, None, "BusinessEnergyQuery", 1, 0, "F", "0", "0", "business:energy:list", "#", "admin", now, "", None, ""),
            ]
            menu_cols = ["menu_id", "menu_name", "parent_id", "order_num", "path", "component", "query", "route_name", "is_frame", "is_cache", "menu_type", "visible", "status", "perms", "icon", "create_by", "create_time", "update_by", "update_time", "remark"]
            for row in menus:
                qmarks = ",".join(["%s"] * len(menu_cols))
                cur.execute("INSERT IGNORE INTO sys_menu (%s) VALUES (%s)" % (",".join(menu_cols), qmarks), row)
            dump.append("INSERT IGNORE INTO sys_menu (%s) VALUES" % ",".join(menu_cols))
            dump.append(",\n".join("(" + ",".join(q(v) for v in row) + ")" for row in menus) + ";")
            for menu_id in range(2000, 2008):
                cur.execute("INSERT IGNORE INTO sys_role_menu (role_id, menu_id) VALUES (1, %s)", (menu_id,))
            dump.append("INSERT IGNORE INTO sys_role_menu (role_id, menu_id) VALUES " + ",".join("(1,%d)" % i for i in range(2000, 2008)) + ";")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    dump_database()
    print("OK enterprise=%d lease=%d energy=%d visit=%d dept=%d user=%d login=%d oper=%d" % (
        len(enterprises), len(leases), len(energy), len(visits), len(depts), len(users), len(login_logs), len(oper_logs)))
    print("SQL=%s" % SQL_OUT)


if __name__ == "__main__":
    main()
