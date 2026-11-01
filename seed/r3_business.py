#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R3 梧州市自来水有限公司 —— 组织架构 / 水表抄表业务数据 / 日志 种子脚本
=====================================================================
目标库：MySQL 127.0.0.1:13307 / ry_r3
说明：
  1. 重建 biz_meter_user / biz_meter / biz_reading / biz_payment 四张业务表；
  2. 重写部门树（100~128，27 个节点 3 层），员工（保留 admin 与 scanner_low）；
  3. 重建菜单「业务管理」及其子菜单、按钮权限，并给 role_id=1 补授权；
  4. 重灌登录日志与操作日志（近 30 天，无未来时间）；
  5. 可重复执行，完整 SQL 落盘到 seed/r3_business.sql。

用法：python seed/r3_business.py
"""
import calendar
import datetime as dt
import hashlib
import os
import random

import pymysql
from pymysql.converters import escape_string

DB = dict(host="127.0.0.1", port=13307, user="root", password="", database="ry_r3", charset="utf8mb4")

TODAY = dt.date.today()
NOW = dt.datetime.now().replace(microsecond=0)
SEED = 20261030
random.seed(SEED)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SQL_FILE = os.path.join(BASE_DIR, "r3_business.sql")

DEFAULT_SALT = "111111"
RY_SALT = "222222"


def pw_hash(login_name, password, salt):
    """RuoYi 4.x 口令算法：MD5(loginName + password + salt)。
    哈希里含登录名，绝不能复制 admin 的哈希。"""
    return hashlib.md5((login_name + password + salt).encode("utf-8")).hexdigest()


# ----------------------------------------------------------------------------
# 组织架构（27 个节点，3 层，ID 固定）
# ----------------------------------------------------------------------------
# (dept_id, parent_id, dept_name, order_num, leader)
DEPTS = [
    (100, 0, "梧州市自来水有限公司", 0, "陈国强"),
    (101, 100, "客服中心", 1, "黄秀兰"),
    (102, 100, "营业所", 2, "覃志强"),
    (103, 100, "管网运行部", 3, "蓝建国"),
    (104, 100, "水质检测中心", 4, "蒙丽娟"),
    (105, 100, "工程技术部", 5, "刘建华"),
    (106, 100, "财务部", 6, "钟丽华"),
    (107, 100, "稽查队", 7, "潘志文"),
    (110, 101, "热线服务班", 1, "周晓红"),
    (111, 101, "业务受理班", 2, "吴海燕"),
    (112, 102, "河东营业所", 1, "邓建国"),
    (113, 102, "河西营业所", 2, "韦小梅"),
    (114, 103, "调度室", 1, "苏文杰"),
    (115, 103, "抢修队", 2, "何志明"),
    (116, 103, "巡线班", 3, "唐国华"),
    (117, 104, "化验室", 1, "杨秀珍"),
    (118, 104, "采样组", 2, "陈志远"),
    (119, 105, "设计室", 1, "卢伟东"),
    (120, 105, "施工管理组", 2, "覃文强"),
    (121, 106, "会计组", 1, "何丽娟"),
    (122, 106, "出纳组", 2, "黄志辉"),
    (123, 107, "稽查一组", 1, "李海峰"),
    (124, 107, "稽查二组", 2, "韦国庆"),
    (125, 112, "河东收费班", 1, "李桂芳"),
    (126, 112, "河东抄表班", 2, "罗永强"),
    (127, 113, "河西收费班", 1, "农志刚"),
    (128, 113, "河西抄表班", 2, "甘海波"),
]
DEPT_NAME = {d[0]: d[2] for d in DEPTS}

# (user_id, 姓名, dept_id, 岗位, 性别)  性别：0男 1女
EMPLOYEES = [
    (2001, "陈国强", 100, "总经理", "0"),
    (2002, "李伟明", 100, "副总经理", "0"),
    (2003, "黄秀兰", 101, "客服中心主任", "1"),
    (2004, "周晓红", 110, "热线班长", "1"),
    (2005, "梁美玲", 110, "话务员", "1"),
    (2006, "吴海燕", 111, "业务受理员", "1"),
    (2007, "覃志强", 102, "营业所所长", "0"),
    (2008, "邓建国", 112, "河东营业所主任", "0"),
    (2009, "李桂芳", 125, "河东收费班长", "1"),
    (2010, "罗永强", 126, "河东抄表班长", "0"),
    (2011, "韦小梅", 113, "河西营业所主任", "1"),
    (2012, "农志刚", 127, "河西收费班长", "0"),
    (2013, "甘海波", 128, "河西抄表班长", "0"),
    (2014, "蓝建国", 103, "管网运行部部长", "0"),
    (2015, "苏文杰", 114, "调度值班长", "0"),
    (2016, "何志明", 115, "抢修队长", "0"),
    (2017, "唐国华", 116, "巡线员", "0"),
    (2018, "蒙丽娟", 104, "水质检测中心主任", "1"),
    (2019, "杨秀珍", 117, "化验员", "1"),
    (2020, "陈志远", 118, "采样员", "0"),
    (2021, "刘建华", 105, "工程技术部部长", "0"),
    (2022, "卢伟东", 119, "设计员", "0"),
    (2023, "钟丽华", 106, "财务部部长", "1"),
    (2024, "潘志文", 107, "稽查队长", "0"),
    (2025, "何丽娟", 121, "会计", "1"),
    (2026, "黄志辉", 122, "出纳", "0"),
    (2027, "覃文强", 120, "施工管理员", "0"),
    (2028, "李海峰", 123, "稽查员", "0"),
    (2029, "韦国庆", 124, "稽查员", "0"),
    (2030, "陈丽萍", 106, "会计", "1"),
]
# 工号规则：WZ0001 起顺序排
EMP_LOGIN = {e[0]: "WZ%04d" % (i + 1) for i, e in enumerate(EMPLOYEES)}

# ry（user_id=2）改造为真实员工，salt 保持 222222
RY_EMPLOYEE = (2, "黄伟成", 106, "会计", "0", "WZ0031")


def phone():
    return random.choice(["138", "139", "189"]) + "".join(random.choice("0123456789") for _ in range(8))


def email_for(login_name):
    return "%s@wzwater.com.cn" % login_name.lower()


# ----------------------------------------------------------------------------
# SQL 工具
# ----------------------------------------------------------------------------
def q(v):
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, dt.datetime):
        return "'%s'" % v.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(v, dt.date):
        return "'%s'" % v.isoformat()
    return "'%s'" % escape_string(str(v))


def insert_sql(table, rows, cols):
    chunks = []
    for i in range(0, len(rows), 40):
        part = rows[i:i + 40]
        values = ",\n".join("(" + ", ".join(q(r[c]) for c in cols) + ")" for r in part)
        chunks.append("INSERT INTO %s (%s) VALUES\n%s;" % (table, ", ".join(cols), values))
    return chunks


def at(d, h, m=0, s=0):
    return dt.datetime.combine(d, dt.time(h, m, s))


def month_start(offset):
    y = TODAY.year + (TODAY.month - 1 + offset) // 12
    m = (TODAY.month - 1 + offset) % 12 + 1
    return dt.date(y, m, 1)


# ----------------------------------------------------------------------------
# DDL
# ----------------------------------------------------------------------------
DDL = [
    "DROP TABLE IF EXISTS biz_payment",
    "DROP TABLE IF EXISTS biz_reading",
    "DROP TABLE IF EXISTS biz_meter",
    "DROP TABLE IF EXISTS biz_meter_user",
    """CREATE TABLE biz_meter_user (
  user_id bigint(20) NOT NULL AUTO_INCREMENT COMMENT '用水户ID',
  user_no varchar(32) NOT NULL COMMENT '用水户号',
  user_name varchar(100) NOT NULL COMMENT '户名',
  user_type varchar(10) DEFAULT '居民' COMMENT '用户类型（居民/商业/工业/公共）',
  phone varchar(20) DEFAULT NULL COMMENT '联系电话',
  address varchar(200) DEFAULT NULL COMMENT '用水地址',
  area varchar(10) DEFAULT NULL COMMENT '区域（河东/河西）',
  price_type varchar(20) DEFAULT NULL COMMENT '水价类别',
  status char(1) DEFAULT '0' COMMENT '状态（0正常 1停用 2销户）',
  open_date date DEFAULT NULL COMMENT '开户日期',
  create_by varchar(64) DEFAULT NULL COMMENT '创建者',
  create_time datetime DEFAULT NULL COMMENT '创建时间',
  update_by varchar(64) DEFAULT NULL COMMENT '更新者',
  update_time datetime DEFAULT NULL COMMENT '更新时间',
  remark varchar(500) DEFAULT NULL COMMENT '备注',
  PRIMARY KEY (user_id),
  UNIQUE KEY uk_biz_meter_user_no (user_no),
  KEY idx_biz_meter_user_name (user_name),
  KEY idx_biz_meter_user_area (area)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用水户档案'""",
    """CREATE TABLE biz_meter (
  meter_id bigint(20) NOT NULL AUTO_INCREMENT COMMENT '水表ID',
  meter_no varchar(32) NOT NULL COMMENT '水表表号',
  user_id bigint(20) DEFAULT NULL COMMENT '用水户ID',
  user_no varchar(32) DEFAULT NULL COMMENT '用水户号',
  user_name varchar(100) DEFAULT NULL COMMENT '户名',
  caliber varchar(10) DEFAULT NULL COMMENT '口径',
  meter_type varchar(20) DEFAULT NULL COMMENT '表型',
  install_date date DEFAULT NULL COMMENT '安装日期',
  install_addr varchar(200) DEFAULT NULL COMMENT '安装地址',
  last_reading decimal(12,2) DEFAULT '0.00' COMMENT '最新读数',
  last_read_date date DEFAULT NULL COMMENT '最新抄表日期',
  status char(1) DEFAULT '0' COMMENT '状态（0正常 1故障 2停用 3待换）',
  create_by varchar(64) DEFAULT NULL COMMENT '创建者',
  create_time datetime DEFAULT NULL COMMENT '创建时间',
  update_by varchar(64) DEFAULT NULL COMMENT '更新者',
  update_time datetime DEFAULT NULL COMMENT '更新时间',
  remark varchar(500) DEFAULT NULL COMMENT '备注',
  PRIMARY KEY (meter_id),
  UNIQUE KEY uk_biz_meter_no (meter_no),
  KEY idx_biz_meter_user (user_id),
  KEY idx_biz_meter_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='水表档案'""",
    """CREATE TABLE biz_reading (
  reading_id bigint(20) NOT NULL AUTO_INCREMENT COMMENT '抄表ID',
  reading_no varchar(32) NOT NULL COMMENT '抄表批次号',
  meter_no varchar(32) DEFAULT NULL COMMENT '水表表号',
  user_no varchar(32) DEFAULT NULL COMMENT '用水户号',
  user_name varchar(100) DEFAULT NULL COMMENT '户名',
  user_addr varchar(200) DEFAULT NULL COMMENT '用水地址',
  area varchar(10) DEFAULT NULL COMMENT '区域',
  period char(7) DEFAULT NULL COMMENT '账期（yyyy-MM）',
  read_date date DEFAULT NULL COMMENT '抄表日期',
  last_reading decimal(12,2) DEFAULT '0.00' COMMENT '上期读数',
  curr_reading decimal(12,2) DEFAULT '0.00' COMMENT '本期读数',
  usage_amount decimal(12,2) DEFAULT '0.00' COMMENT '用水量（吨）',
  read_type char(1) DEFAULT '0' COMMENT '抄表方式（0正常 1估抄 2换表 3补抄）',
  reader_name varchar(30) DEFAULT NULL COMMENT '抄表员',
  reader_id bigint(20) DEFAULT NULL COMMENT '抄表员工号',
  status char(1) DEFAULT '0' COMMENT '状态（0待复核 1已复核 2异常）',
  remark varchar(500) DEFAULT NULL COMMENT '备注',
  create_by varchar(64) DEFAULT NULL COMMENT '创建者',
  create_time datetime DEFAULT NULL COMMENT '创建时间',
  update_by varchar(64) DEFAULT NULL COMMENT '更新者',
  update_time datetime DEFAULT NULL COMMENT '更新时间',
  PRIMARY KEY (reading_id),
  UNIQUE KEY uk_biz_reading_no (reading_no),
  KEY idx_biz_reading_meter (meter_no),
  KEY idx_biz_reading_date (read_date),
  KEY idx_biz_reading_status (status),
  KEY idx_biz_reading_period (period)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='水表抄表记录'""",
    """CREATE TABLE biz_payment (
  payment_id bigint(20) NOT NULL AUTO_INCREMENT COMMENT '缴费ID',
  payment_no varchar(32) NOT NULL COMMENT '缴费单号',
  user_no varchar(32) DEFAULT NULL COMMENT '用水户号',
  user_name varchar(100) DEFAULT NULL COMMENT '户名',
  meter_no varchar(32) DEFAULT NULL COMMENT '水表表号',
  period char(7) DEFAULT NULL COMMENT '账期（yyyy-MM）',
  payable_amount decimal(12,2) DEFAULT '0.00' COMMENT '应收金额',
  paid_amount decimal(12,2) DEFAULT '0.00' COMMENT '实收金额',
  pay_type char(1) DEFAULT NULL COMMENT '缴费方式（0微信 1支付宝 2银行代扣 3营业厅 4自助机）',
  pay_date date DEFAULT NULL COMMENT '缴费日期',
  status char(1) DEFAULT '0' COMMENT '状态（0已缴 1欠费 2部分缴 3已退费）',
  operator varchar(30) DEFAULT NULL COMMENT '收费员',
  create_by varchar(64) DEFAULT NULL COMMENT '创建者',
  create_time datetime DEFAULT NULL COMMENT '创建时间',
  update_by varchar(64) DEFAULT NULL COMMENT '更新者',
  update_time datetime DEFAULT NULL COMMENT '更新时间',
  remark varchar(500) DEFAULT NULL COMMENT '备注',
  PRIMARY KEY (payment_id),
  UNIQUE KEY uk_biz_payment_no (payment_no),
  KEY idx_biz_payment_user (user_no),
  KEY idx_biz_payment_date (pay_date),
  KEY idx_biz_payment_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='水费缴费记录'""",
]

# ----------------------------------------------------------------------------
# 用水户
# ----------------------------------------------------------------------------
SURNAMES = "李黄梁覃韦陈吴罗蒙甘蓝苏何唐杨刘卢钟潘陆周农邓莫林张谢曾廖石秦肖阮岑宁"
GIVEN = ["秀英", "桂英", "玉兰", "志强", "海波", "小燕", "丽娟", "建国", "国华", "伟明",
         "晓红", "美玲", "海燕", "永强", "小梅", "志刚", "文杰", "志明", "丽华", "秀珍",
         "志远", "建华", "伟东", "家强", "春梅", "秀兰", "德明", "少华", "锦华", "凤英",
         "国强", "桂芳", "永红", "水莲", "金凤", "树林", "启明", "达强", "光远", "庆华"]
ROADS = ["新兴一路", "新兴二路", "新兴三路", "中山路", "大学路", "文澜路", "西江路", "蝶山一路",
         "富民路", "龙山路", "红岭路", "三龙大道", "苍海大道", "桂江路", "鸳江路", "民主路",
         "和平路", "步埠路", "塘源路", "莲花山路", "京梧路", "新兴珠宝路"]
DISTRICTS = ["万秀区", "长洲区", "龙圩区", "蝶山区"]
BRANDS = ["兴隆", "恒达", "鑫源", "粤桂", "西江", "鸳江", "骑楼", "桂香", "家和", "金晖",
          "旺城", "长洲", "苍梧", "广源", "新辉", "福临", "万家", "顺达"]
BIZ_KINDS = ["餐饮店", "超市", "宾馆", "商贸有限公司", "食品有限公司", "物业管理有限公司", "药房", "茶楼"]
IND_KINDS = ["机械制造有限公司", "化工有限公司", "建材有限公司", "造纸有限公司", "纺织有限公司", "食品加工有限公司"]
PUB_NAMES = ["梧州市第一中学", "梧州市第二中学", "梧州市人民医院", "梧州市中医院", "梧州市图书馆",
             "梧州市体育馆", "梧州市第一幼儿园", "梧州市公交有限责任公司", "梧州市万秀区人民政府",
             "梧州市长洲区街道办事处", "梧州市职业学院", "梧州市妇女儿童医院"]


def person_name():
    return random.choice(SURNAMES) + random.choice(GIVEN)


def build_meter_users():
    types = ["居民"] * 400 + ["商业"] * 70 + ["工业"] * 30 + ["公共"] * 20
    random.shuffle(types)
    pub_names = PUB_NAMES[:]
    random.shuffle(pub_names)
    used_names = set()
    rows = []
    for idx, utype in enumerate(types):
        uid = idx + 1
        if utype == "居民":
            while True:
                nm = person_name()
                if nm not in used_names:
                    used_names.add(nm)
                    break
        elif utype == "商业":
            nm = "梧州市%s区%s%s" % (random.choice(DISTRICTS), random.choice(BRANDS), random.choice(BIZ_KINDS))
        elif utype == "工业":
            nm = "梧州市%s%s" % (random.choice(BRANDS), random.choice(IND_KINDS))
        else:
            nm = pub_names.pop() if pub_names else "梧州市%s区%s" % (random.choice(DISTRICTS), random.choice(["社区卫生服务中心", "文化馆", "体育馆"]))
        area = random.choice(["河东", "河西"])
        if utype == "居民":
            price_type = "居民阶梯"
        elif utype == "公共":
            price_type = "特种用水"
        else:
            price_type = "非居民"
        open_day = TODAY - dt.timedelta(days=random.randint(60, 3600))
        st = "0"
        r = random.random()
        if r > 0.986:
            st = "2"
        elif r > 0.948:
            st = "1"
        rows.append(dict(
            user_id=uid, user_no="WZ%08d" % uid, user_name=nm, user_type=utype,
            phone=phone(), address="梧州市%s%s%d号" % (area, random.choice(ROADS), random.randint(1, 320)),
            area=area, price_type=price_type, status=st, open_date=open_day,
            create_by=random.choice(["admin", "WZ0007", "WZ0003"]),
            create_time=at(open_day, random.randint(8, 18), random.randint(0, 59)),
            update_by="admin", update_time=NOW - dt.timedelta(days=random.randint(1, 300)),
            remark=random.choice(["", "", "", "老旧小区", "一户一表改造", "重点用水户", "欠费催缴中"]),
        ))
    return rows


# ----------------------------------------------------------------------------
# 水表
# ----------------------------------------------------------------------------
CALIBERS = [("DN15", 45), ("DN20", 30), ("DN25", 10), ("DN40", 7), ("DN50", 4), ("DN80", 2), ("DN100", 2)]
METER_TYPES = ["旋翼式", "螺翼式", "超声波"]


def build_meters(users):
    caliber_list = [c for c, w in CALIBERS for _ in range(w)]
    rows = []
    mid = 0
    # 520 户各一块表
    for u in users:
        mid += 1
        install = u["open_date"] + dt.timedelta(days=random.randint(0, 20))
        if install > TODAY:
            install = TODAY - dt.timedelta(days=30)
        rows.append(dict(
            meter_id=mid, meter_no="WZSB%08d" % mid, user_id=u["user_id"], user_no=u["user_no"],
            user_name=u["user_name"], caliber=random.choice(caliber_list),
            meter_type=random.choices(METER_TYPES, weights=[70, 22, 8])[0],
            install_date=install, install_addr=u["address"],
            last_reading=0, last_read_date=None, status="0",
            create_by="admin", create_time=at(install, 9, random.randint(0, 59)),
            update_by="admin", update_time=NOW - dt.timedelta(days=random.randint(1, 200)),
            remark="",
        ))
    # 20 户商业用户再装一块（一商一住）
    biz = [u for u in users if u["user_type"] == "商业"]
    for u in biz[:20]:
        mid += 1
        install = u["open_date"] + dt.timedelta(days=random.randint(20, 200))
        if install > TODAY:
            install = TODAY - dt.timedelta(days=30)
        rows.append(dict(
            meter_id=mid, meter_no="WZSB%08d" % mid, user_id=u["user_id"], user_no=u["user_no"],
            user_name=u["user_name"], caliber=random.choice(["DN25", "DN40", "DN50"]),
            meter_type=random.choice(["螺翼式", "超声波"]),
            install_date=install, install_addr=u["address"] + "（经营用水）",
            last_reading=0, last_read_date=None, status="0",
            create_by="admin", create_time=at(install, 14, random.randint(0, 59)),
            update_by="admin", update_time=NOW - dt.timedelta(days=random.randint(1, 200)),
            remark="一表多户",
        ))
    # 状态分布：正常 / 故障 / 停用 / 待换
    for m in rows:
        r = random.random()
        if r > 0.975:
            m["status"] = "3"
            m["remark"] = "超期服役待更换"
        elif r > 0.955:
            m["status"] = "1"
            m["remark"] = "计量异常待检定"
        elif r > 0.935:
            m["status"] = "2"
            m["remark"] = "用户申请停用"
    return rows


# ----------------------------------------------------------------------------
# 抄表记录
# ----------------------------------------------------------------------------
READERS = [(2010, "罗永强"), (2013, "甘海波"), (2011, "韦小梅"), (2008, "邓建国")]
MONTH_COUNTS = [132, 135, 130, 138, 131, 134, 129, 137, 133, 136, 130, 135]


def usage_for(utype):
    if utype == "居民":
        return round(random.uniform(5, 35), 2)
    if utype == "商业":
        return round(random.uniform(30, 300), 2)
    if utype == "工业":
        return round(random.uniform(300, 3000), 2)
    return round(random.uniform(20, 500), 2)


def build_readings(users, meters):
    meter_by_id = {m["meter_id"]: m for m in meters}
    user_by_id = {u["user_id"]: u for u in users}

    # 先生成（水表, 抄表日期）对
    pairs = []
    used = set()
    for offset in range(-11, 1):
        first = month_start(offset)
        y, mo = first.year, first.month
        last_day = calendar.monthrange(y, mo)[1]
        if y == TODAY.year and mo == TODAY.month:
            last_day = TODAY.day
        count = MONTH_COUNTS[offset + 11]
        for _ in range(count):
            m = random.choice(meters)
            day = random.randint(1, last_day)
            d = dt.date(y, mo, day)
            key = (m["meter_id"], d)
            if key in used:
                continue
            used.add(key)
            pairs.append((m["meter_id"], d))
    # 补齐（去重后可能少量缺失）
    while len(pairs) < 1600:
        offset = random.randint(-11, 0)
        first = month_start(offset)
        y, mo = first.year, first.month
        last_day = calendar.monthrange(y, mo)[1]
        if y == TODAY.year and mo == TODAY.month:
            last_day = TODAY.day
        m = random.choice(meters)
        d = dt.date(y, mo, random.randint(1, last_day))
        key = (m["meter_id"], d)
        if key in used:
            continue
        used.add(key)
        pairs.append((m["meter_id"], d))
    pairs = pairs[:1600]

    # 同一块表按日期递增读数
    pairs.sort(key=lambda x: (x[0], x[1]))
    counter = {}
    raw = []
    for meter_id, d in pairs:
        m = meter_by_id[meter_id]
        u = user_by_id.get(m["user_id"])
        utype = u["user_type"] if u else "居民"
        last = counter.get(meter_id, round(random.uniform(20, 2600), 2))
        usage = usage_for(utype)
        curr = round(last + usage, 2)
        counter[meter_id] = curr
        raw.append((m, u, d, last, curr, usage))

    # 按日期排序后编批次号
    raw.sort(key=lambda x: (x[2], x[0]["meter_id"]))
    seq = {}
    rows = []
    for i, (m, u, d, last, curr, usage) in enumerate(raw, 1):
        ym = d.strftime("%Y%m")
        seq[ym] = seq.get(ym, 0) + 1
        no = "CB%s-%04d" % (ym, seq[ym])
        reader_id, reader_name = random.choice(READERS)
        r = random.random()
        if r > 0.94:
            status = "2"
            remark = random.choice(["读数突增待核查", "表具倒走", "疑似漏水", "连续两月零用水"])
        elif r > 0.82:
            status = "0"
            remark = random.choice(["", "", "用户不在家", "待复核"])
        else:
            status = "1"
            remark = ""
        read_type = random.choices(["0", "1", "2", "3"], weights=[92, 5, 1.5, 1.5])[0]
        rt_remark = {"0": "", "1": "估抄", "2": "换表", "3": "补抄"}[read_type]
        created = at(d, random.randint(8, 17), random.randint(0, 59))
        if created > NOW:
            created = NOW - dt.timedelta(minutes=random.randint(5, 300))
        updated = at(d, random.randint(8, 18), random.randint(0, 59)) if status == "1" else None
        if updated is not None and updated > NOW:
            updated = NOW - dt.timedelta(minutes=random.randint(1, 120))
        rows.append(dict(
            reading_id=i, reading_no=no, meter_no=m["meter_no"], user_no=m["user_no"],
            user_name=m["user_name"], user_addr=m["install_addr"], area=u["area"] if u else "河东",
            period=d.strftime("%Y-%m"), read_date=d, last_reading=last, curr_reading=curr,
            usage_amount=usage, read_type=read_type, reader_name=reader_name, reader_id=reader_id,
            status=status, remark=remark or rt_remark,
            create_by=reader_name, create_time=created,
            update_by=reader_name if status == "1" else "",
            update_time=updated,
        ))

    # 回写水表最新读数
    latest = {}
    for m, u, d, last, curr, usage in raw:
        prev = latest.get(m["meter_id"])
        if prev is None or d >= prev[0]:
            latest[m["meter_id"]] = (d, curr)
    for m in meters:
        if m["meter_id"] in latest:
            d, curr = latest[m["meter_id"]]
            m["last_reading"] = curr
            m["last_read_date"] = d
    return rows


# ----------------------------------------------------------------------------
# 缴费记录
# ----------------------------------------------------------------------------
RATE = {
    "居民": (2.35, 1.10),
    "商业": (3.20, 1.40),
    "工业": (3.85, 1.60),
    "公共": (3.20, 1.40),
}
OPERATORS = ["李桂芳", "农志刚", "陈志远", "黄秀兰", "吴海燕"]


def build_payments(users, readings):
    user_by_no = {u["user_no"]: u for u in users}
    picks = random.sample(readings, 1300)
    picks.sort(key=lambda r: (r["read_date"], r["reading_id"]))
    seq = {}
    rows = []
    for i, r in enumerate(picks, 1):
        u = user_by_no.get(r["user_no"])
        utype = u["user_type"] if u else "居民"
        water_rate, sewage_rate = RATE.get(utype, RATE["居民"])
        payable = round(r["usage_amount"] * (water_rate + sewage_rate), 2)
        p = random.random()
        if p < 0.88:
            status = "0"
        elif p < 0.94:
            status = "1"
        elif p < 0.98:
            status = "2"
        else:
            status = "3"

        pay_date = r["read_date"] + dt.timedelta(days=random.randint(1, 18))
        if pay_date > TODAY:
            pay_date = TODAY
        if status == "1":
            paid = 0.0
            pay_date_val = None
            remark = "逾期未缴，已发送催缴短信"
        elif status == "2":
            paid = round(payable * random.uniform(0.3, 0.7), 2)
            pay_date_val = pay_date
            remark = "余额不足，部分缴纳"
        elif status == "3":
            paid = payable
            pay_date_val = pay_date
            remark = "重复缴费已退费"
        else:
            paid = payable
            pay_date_val = pay_date
            remark = ""

        ym = pay_date.strftime("%Y%m%d")
        seq[ym] = seq.get(ym, 0) + 1
        no = "JF%s%04d" % (ym, seq[ym])
        created = at(pay_date_val or r["read_date"], random.randint(8, 18), random.randint(0, 59))
        if created > NOW:
            created = NOW - dt.timedelta(minutes=random.randint(5, 300))
        updated = NOW - dt.timedelta(days=random.randint(0, 120), minutes=random.randint(0, 600))
        if updated > NOW:
            updated = NOW - dt.timedelta(minutes=random.randint(5, 300))
        rows.append(dict(
            payment_id=i, payment_no=no, user_no=r["user_no"], user_name=r["user_name"],
            meter_no=r["meter_no"], period=r["period"], payable_amount=payable, paid_amount=paid,
            pay_type=random.choices(["0", "1", "2", "3", "4"], weights=[42, 26, 18, 9, 5])[0],
            pay_date=pay_date_val, status=status, operator=random.choice(OPERATORS),
            create_by=random.choice(OPERATORS),
            create_time=created,
            update_by="admin", update_time=updated,
            remark=remark,
        ))
    return rows


# ----------------------------------------------------------------------------
# 部门 / 用户
# ----------------------------------------------------------------------------
def build_depts():
    rows = []
    for dept_id, parent_id, name, order_num, leader in DEPTS:
        if dept_id == 100:
            ancestors = "0"
        else:
            path = []
            p = parent_id
            while p != 0:
                path.append(str(p))
                p = next((d[1] for d in DEPTS if d[0] == p), 0)
            ancestors = "0," + ",".join(reversed(path))
        rows.append(dict(
            dept_id=dept_id, parent_id=parent_id, ancestors=ancestors, dept_name=name,
            order_num=order_num, leader=leader, phone=phone(),
            email="dept%d@wzwater.com.cn" % dept_id,
            status="0", del_flag="0", create_by="admin",
            create_time=NOW - dt.timedelta(days=2400), update_by="admin",
            update_time=NOW - dt.timedelta(days=120),
        ))
    return rows


def build_users():
    rows = []
    # ry -> 黄伟成（salt 222222 保持不动，哈希按 222222 重算）
    uid, name, dept, post, sex, login = RY_EMPLOYEE
    rows.append(dict(
        user_id=uid, dept_id=dept, login_name=login, user_name=name, user_type="00",
        email=email_for(login), phonenumber=phone(), sex=sex, avatar="",
        password=pw_hash(login, "admin123", RY_SALT), salt=RY_SALT, status="0", del_flag="0",
        login_ip="192.168.30.31", login_date=NOW - dt.timedelta(hours=9),
        pwd_update_date=None, create_by="admin", create_time=NOW - dt.timedelta(days=1500),
        update_by="admin", update_time=NOW - dt.timedelta(days=20), remark=post,
    ))
    for user_id, name, dept, post, sex in EMPLOYEES:
        login = EMP_LOGIN[user_id]
        rows.append(dict(
            user_id=user_id, dept_id=dept, login_name=login, user_name=name, user_type="00",
            email=email_for(login), phonenumber=phone(), sex=sex, avatar="",
            password=pw_hash(login, "admin123", DEFAULT_SALT), salt=DEFAULT_SALT,
            status="0", del_flag="0",
            login_ip="10.30.20.%d" % (20 + user_id % 100),
            login_date=NOW - dt.timedelta(days=random.randint(0, 6), hours=random.randint(0, 8)),
            pwd_update_date=None, create_by="admin",
            create_time=NOW - dt.timedelta(days=random.randint(120, 2600), hours=random.randint(0, 8)),
            update_by="admin", update_time=NOW - dt.timedelta(days=random.randint(1, 90)),
            remark=post,
        ))
    return rows


# ----------------------------------------------------------------------------
# 日志
# ----------------------------------------------------------------------------
def workday_day():
    while True:
        d = TODAY - dt.timedelta(days=random.randint(0, 29))
        if d.weekday() >= 5 and random.random() < 0.80:
            continue
        return d


BROWSERS = ["Chrome 118", "Chrome 120", "Edge 118", "Firefox 115", "Chrome 119", "360SE 13"]
OS_LIST = ["Windows 10", "Windows 11", "Windows 10", "Windows 7", "macOS 12"]
IPS = ["10.30.20.%d", "192.168.30.%d"]


def build_logins(user_rows):
    staff = [(u["login_name"], u["user_name"], u["dept_id"]) for u in user_rows]
    staff += [("admin", "系统管理员", 100), ("scanner_low", "运维支持", 114)]
    picks = []
    for item in staff:
        picks.extend([item] * 4)
    while len(picks) < 220:
        picks.append(random.choice(staff))
    picks = picks[:220]
    random.shuffle(picks)
    rows = []
    for i, (login, name, dept) in enumerate(picks, 1):
        d = workday_day()
        t = at(d, random.randint(8, 19), random.randint(0, 59), random.randint(0, 59))
        if t > NOW:
            t = NOW - dt.timedelta(minutes=random.randint(5, 400))
        failed = random.random() < 0.05
        rows.append(dict(
            info_id=i, login_name=login,
            ipaddr=random.choice(IPS) % random.randint(2, 250),
            login_location="广西壮族自治区梧州市",
            browser=random.choice(BROWSERS), os=random.choice(OS_LIST),
            status="1" if failed else "0",
            msg="密码错误" if failed else "登录成功",
            login_time=t,
        ))
    return rows


OPER_TITLES = [
    ("水表抄表", 0.40, "business.Reading", [
        ("list", "查询抄表记录", 0, "POST", "/business/reading/list", 0),
        ("detail", "查看抄表详情", 0, "GET", "/business/reading/detail", 0),
        ("export", "导出抄表数据", 5, "POST", "/business/reading/export", 0),
    ]),
    ("用水户管理", 0.20, "business.MeterUser", [
        ("list", "查询用水户列表", 0, "POST", "/business/meteruser/list", 0),
    ]),
    ("水表档案", 0.16, "business.Meter", [
        ("list", "查询水表档案", 0, "POST", "/business/meter/list", 0),
    ]),
    ("缴费管理", 0.14, "business.Payment", [
        ("list", "查询缴费记录", 0, "POST", "/business/payment/list", 0),
    ]),
    ("用户管理", 0.04, "system.SysUser", [
        ("list", "查询用户列表", 0, "POST", "/system/user/list", 0),
        ("edit", "修改用户信息", 2, "POST", "/system/user/edit", 0),
    ]),
    ("角色管理", 0.03, "system.SysRole", [
        ("list", "查询角色列表", 0, "POST", "/system/role/list", 0),
        ("edit", "修改角色信息", 2, "POST", "/system/role/edit", 0),
    ]),
    ("菜单管理", 0.03, "system.SysMenu", [
        ("list", "查询菜单列表", 0, "POST", "/system/menu/list", 0),
        ("edit", "修改菜单信息", 2, "POST", "/system/menu/edit", 0),
    ]),
]


def build_opers(user_rows):
    staff = [(u["user_name"], u["dept_id"]) for u in user_rows]
    weights = [t[1] for t in OPER_TITLES]
    rows = []
    for i in range(1, 361):
        title, _, ctrl, actions = random.choices(OPER_TITLES, weights=weights)[0]
        act, label, btype, req, url, _ = random.choice(actions)
        d = workday_day()
        t = at(d, random.randint(8, 19), random.randint(0, 59), random.randint(0, 59))
        if t > NOW:
            t = NOW - dt.timedelta(minutes=random.randint(5, 400))
        name, dept = random.choice(staff)
        failed = random.random() < 0.03
        rows.append(dict(
            oper_id=i, title=title, business_type=btype,
            method="com.ruoyi.web.controller.%sController.%s" % (ctrl, act),
            request_method=req, operator_type=1, oper_name=name,
            dept_name=DEPT_NAME.get(dept, ""),
            oper_url=url, oper_ip=random.choice(IPS) % random.randint(2, 250),
            oper_location="广西壮族自治区梧州市",
            oper_param='{"pageNum":"1","pageSize":"10","orderByColumn":"createTime","isAsc":"desc"}',
            json_result='{"code":0,"msg":"操作成功"}' if not failed else '{"code":500,"msg":"操作失败"}',
            status=1 if failed else 0,
            error_msg="数据校验失败，请稍后重试" if failed else None,
            oper_time=t,
        ))
    return rows


# ----------------------------------------------------------------------------
# 菜单
# ----------------------------------------------------------------------------
MENUS = [
    dict(menu_id=2000, menu_name="业务管理", parent_id=0, order_num=4, url="#", target="",
         menu_type="M", visible="0", is_refresh="1", perms="", icon="fa fa-tint"),
    dict(menu_id=2001, menu_name="水表抄表", parent_id=2000, order_num=1, url="/business/reading", target="",
         menu_type="C", visible="0", is_refresh="1", perms="biz:reading:list", icon="fa fa-dashboard"),
    dict(menu_id=2002, menu_name="用水户管理", parent_id=2000, order_num=2, url="/business/meteruser", target="",
         menu_type="C", visible="0", is_refresh="1", perms="biz:meteruser:list", icon="fa fa-users"),
    dict(menu_id=2003, menu_name="水表档案", parent_id=2000, order_num=3, url="/business/meter", target="",
         menu_type="C", visible="0", is_refresh="1", perms="biz:meter:list", icon="fa fa-tachometer"),
    dict(menu_id=2004, menu_name="缴费记录", parent_id=2000, order_num=4, url="/business/payment", target="",
         menu_type="C", visible="0", is_refresh="1", perms="biz:payment:list", icon="fa fa-cny"),
    dict(menu_id=2005, menu_name="查询", parent_id=2001, order_num=1, url="#", target="",
         menu_type="F", visible="0", is_refresh="1", perms="biz:reading:query", icon="#"),
    dict(menu_id=2006, menu_name="详情", parent_id=2001, order_num=2, url="#", target="",
         menu_type="F", visible="0", is_refresh="1", perms="biz:reading:detail", icon="#"),
    dict(menu_id=2007, menu_name="导出", parent_id=2001, order_num=3, url="#", target="",
         menu_type="F", visible="0", is_refresh="1", perms="biz:reading:export", icon="#"),
]
MENU_COLS = ["menu_id", "menu_name", "parent_id", "order_num", "url", "target", "menu_type",
             "visible", "is_refresh", "perms", "icon", "create_by", "create_time", "remark"]


def build_menus():
    rows = []
    for m in MENUS:
        r = dict(m)
        r.update(create_by="admin", create_time=NOW - dt.timedelta(days=200), remark=None)
        rows.append(r)
    return rows


# ----------------------------------------------------------------------------
# 写库
# ----------------------------------------------------------------------------
METER_USER_COLS = ["user_id", "user_no", "user_name", "user_type", "phone", "address", "area",
                   "price_type", "status", "open_date", "create_by", "create_time", "update_by",
                   "update_time", "remark"]
METER_COLS = ["meter_id", "meter_no", "user_id", "user_no", "user_name", "caliber", "meter_type",
              "install_date", "install_addr", "last_reading", "last_read_date", "status",
              "create_by", "create_time", "update_by", "update_time", "remark"]
READING_COLS = ["reading_id", "reading_no", "meter_no", "user_no", "user_name", "user_addr", "area",
                "period", "read_date", "last_reading", "curr_reading", "usage_amount", "read_type",
                "reader_name", "reader_id", "status", "remark", "create_by", "create_time",
                "update_by", "update_time"]
PAYMENT_COLS = ["payment_id", "payment_no", "user_no", "user_name", "meter_no", "period",
                "payable_amount", "paid_amount", "pay_type", "pay_date", "status", "operator",
                "create_by", "create_time", "update_by", "update_time", "remark"]
DEPT_COLS = ["dept_id", "parent_id", "ancestors", "dept_name", "order_num", "leader", "phone",
             "email", "status", "del_flag", "create_by", "create_time", "update_by", "update_time"]
USER_COLS = ["user_id", "dept_id", "login_name", "user_name", "user_type", "email", "phonenumber",
             "sex", "avatar", "password", "salt", "status", "del_flag", "login_ip", "login_date",
             "pwd_update_date", "create_by", "create_time", "update_by", "update_time", "remark"]
LOGIN_COLS = ["info_id", "login_name", "ipaddr", "login_location", "browser", "os", "status", "msg", "login_time"]
OPER_COLS = ["oper_id", "title", "business_type", "method", "request_method", "operator_type",
             "oper_name", "dept_name", "oper_url", "oper_ip", "oper_location", "oper_param",
             "json_result", "status", "error_msg", "oper_time"]


def main():
    users = build_meter_users()
    meters = build_meters(users)
    readings = build_readings(users, meters)
    payments = build_payments(users, readings)
    depts = build_depts()
    staff = build_users()
    logins = build_logins(staff)
    opers = build_opers(staff)
    menus = build_menus()

    statements = []
    statements += DDL

    # ---- 组织架构 ----
    statements += [
        "DELETE FROM sys_dept WHERE dept_id BETWEEN 100 AND 128",
        "DELETE FROM sys_user WHERE user_id = 2 OR user_id BETWEEN 2001 AND 2030",
        "DELETE FROM sys_user_role WHERE user_id = 2 OR user_id BETWEEN 2001 AND 2030",
        "DELETE FROM sys_user_post WHERE user_id = 2 OR user_id BETWEEN 2001 AND 2030",
        "UPDATE sys_user SET user_name = '系统管理员', dept_id = 100, email = 'admin@wzwater.com.cn', "
        "phonenumber = '13877400101', remark = '系统管理员' WHERE user_id = 1",
        "UPDATE sys_user SET dept_id = 114 WHERE user_id = 100",
    ]
    statements += insert_sql("sys_dept", depts, DEPT_COLS)
    statements += insert_sql("sys_user", staff, USER_COLS)

    user_roles = [dict(user_id=2, role_id=2)]
    user_posts = [dict(user_id=2, post_id=4)]
    for uid, name, dept, post, sex in EMPLOYEES:
        user_roles.append(dict(user_id=uid, role_id=2))
        if uid == 2001:
            post_id = 1
        elif post in ("副总经理", "客服中心主任", "营业所所长", "河东营业所主任", "河西营业所主任",
                      "管网运行部部长", "水质检测中心主任", "工程技术部部长", "财务部部长", "稽查队长",
                      "调度值班长", "抢修队长", "热线班长", "河东收费班长", "河东抄表班长",
                      "河西收费班长", "河西抄表班长", "施工管理员"):
            post_id = 2
        else:
            post_id = 4
        user_posts.append(dict(user_id=uid, post_id=post_id))
    statements += insert_sql("sys_user_role", user_roles, ["user_id", "role_id"])
    statements += insert_sql("sys_user_post", user_posts, ["user_id", "post_id"])

    statements += [
        "UPDATE sys_post SET post_name = '总经理' WHERE post_id = 1",
        "UPDATE sys_post SET post_name = '部门经理' WHERE post_id = 2",
        "UPDATE sys_post SET post_name = '人事专员' WHERE post_id = 3",
        "UPDATE sys_post SET post_name = '普通员工' WHERE post_id = 4",
    ]

    # ---- 菜单 ----
    statements += [
        "UPDATE sys_menu SET menu_name = '公司首页', url = '/system/main', target = '', perms = '', "
        "icon = 'fa fa-home', order_num = 1 WHERE menu_id = 4",
        "DELETE FROM sys_menu WHERE menu_id BETWEEN 2000 AND 2007",
    ]
    statements += insert_sql("sys_menu", menus, MENU_COLS)
    statements += [
        "INSERT INTO sys_role_menu (role_id, menu_id) SELECT 1, m.menu_id FROM sys_menu m "
        "WHERE m.menu_id BETWEEN 2000 AND 2007 AND NOT EXISTS "
        "(SELECT 1 FROM sys_role_menu rm WHERE rm.role_id = 1 AND rm.menu_id = m.menu_id)",
    ]

    # ---- 业务数据 ----
    statements += insert_sql("biz_meter_user", users, METER_USER_COLS)
    statements += insert_sql("biz_meter", meters, METER_COLS)
    statements += insert_sql("biz_reading", readings, READING_COLS)
    statements += insert_sql("biz_payment", payments, PAYMENT_COLS)

    # ---- 日志 ----
    statements += ["DELETE FROM sys_logininfor", "DELETE FROM sys_oper_log"]
    statements += insert_sql("sys_logininfor", logins, LOGIN_COLS)
    statements += insert_sql("sys_oper_log", opers, OPER_COLS)

    with open(SQL_FILE, "w", encoding="utf-8") as f:
        f.write("-- R3 梧州市自来水有限公司演示数据（由 seed/r3_business.py 生成）\n")
        f.write("SET NAMES utf8mb4;\nUSE ry_r3;\n\n")
        f.write(";\n\n".join(s.rstrip(";") for s in statements))
        f.write(";\n")

    conn = pymysql.connect(**DB, autocommit=False)
    try:
        cur = conn.cursor()
        cur.execute("SET NAMES utf8mb4")
        for stmt in statements:
            cur.execute(stmt)
        conn.commit()
        fix_future(conn)
        verify(conn)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# 时间字段巡检表
TIME_CHECK = [
    ("sys_logininfor", "login_time"),
    ("sys_oper_log", "oper_time"),
    ("sys_user", "login_date"),
    ("sys_user", "create_time"),
    ("sys_user", "update_time"),
    ("biz_meter_user", "create_time"),
    ("biz_meter_user", "update_time"),
    ("biz_meter", "create_time"),
    ("biz_meter", "update_time"),
    ("biz_reading", "create_time"),
    ("biz_reading", "update_time"),
    ("biz_payment", "create_time"),
    ("biz_payment", "update_time"),
    ("biz_reading", "read_date"),
    ("biz_payment", "pay_date"),
]


def fix_future(conn):
    """断言无未来时间行；有则 UPDATE 到 NOW() 以内。"""
    cur = conn.cursor()
    fixed = 0
    for table, col in TIME_CHECK:
        cur.execute("SELECT COUNT(1) FROM %s WHERE %s > NOW()" % (table, col))
        n = cur.fetchone()[0]
        if n:
            print("[WARN] %s.%s 存在 %s 条未来时间，修正中" % (table, col, n))
            cur.execute("UPDATE %s SET %s = NOW() WHERE %s > NOW()" % (table, col, col))
            fixed += n
    conn.commit()
    if fixed:
        print("[OK] 已修正未来时间行：%s" % fixed)
    else:
        print("[OK] 时间巡检通过：无未来时间行")


def verify(conn):
    cur = conn.cursor()
    print("=" * 64)
    print("R3 梧州市自来水有限公司数据灌入完成")
    print("=" * 64)
    for t in ("biz_meter_user", "biz_meter", "biz_reading", "biz_payment",
              "sys_dept", "sys_user", "sys_menu", "sys_logininfor", "sys_oper_log"):
        cur.execute("SELECT COUNT(1) FROM %s" % t)
        print("%-16s %s" % (t, cur.fetchone()[0]))

    cur.execute("SELECT status, COUNT(1) FROM biz_reading GROUP BY status ORDER BY status")
    names = {"0": "待复核", "1": "已复核", "2": "异常"}
    print("\n抄表状态分布：")
    for r in cur.fetchall():
        print("  %-6s %s" % (names.get(r[0], r[0]), r[1]))

    cur.execute("""SELECT DATE_FORMAT(read_date, '%Y-%m') m, COUNT(1) FROM biz_reading
                   GROUP BY m ORDER BY m""")
    print("\n近 12 个月抄表量：")
    for r in cur.fetchall():
        print("  %s  %s" % (r[0], r[1]))

    cur.execute("SELECT COUNT(1) FROM sys_user WHERE dept_id BETWEEN 100 AND 128")
    print("\n部门内用户：%s" % cur.fetchone()[0])
    print("SQL 文件：%s" % SQL_FILE)


if __name__ == "__main__":
    main()
