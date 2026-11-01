#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R2 广西顺捷物流有限公司 —— 组织架构 / 业务数据 / 日志 种子脚本
=============================================================
目标库：MySQL 127.0.0.1:13307 / ry_r2
说明：
  1. 重建 biz_customer / biz_vehicle / biz_driver / biz_waybill 四张业务表；
  2. 重写部门树（100~116）、员工（保留 admin 与 scanner_low）、角色关联；
  3. 重建菜单「业务管理」及其子菜单、按钮权限，并授权 role_id=1；
  4. 重灌登录日志与操作日志；
  5. 可重复执行，完整 SQL 落盘到 seed/r2_business.sql。

用法：python seed/r2_business.py
"""
import calendar
import datetime as dt
import hashlib
import os
import random

import pymysql
from pymysql.converters import escape_string

DB = dict(host="127.0.0.1", port=13307, user="root", password="", database="ry_r2", charset="utf8mb4")

TODAY = dt.date.today()
NOW = dt.datetime.now().replace(microsecond=0)
SEED = 20261030
random.seed(SEED)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SQL_FILE = os.path.join(BASE_DIR, "r2_business.sql")

ADMIN_PASSWORD = "29c67a30398638269fe600f73a054934"
ADMIN_SALT = "111111"


def pw_hash(login_name, password, salt):
    """RuoYi 4.x 口令算法：MD5(loginName + password + salt)。
    不能直接复用 admin 的哈希，哈希里含登录名，换个账号就登不上。"""
    return hashlib.md5((login_name + password + salt).encode("utf-8")).hexdigest()

# ----------------------------------------------------------------------------
# 组织架构
# ----------------------------------------------------------------------------
# (dept_id, parent_id, dept_name, order_num, leader)
DEPTS = [
    (100, 0, "广西顺捷物流有限公司", 0, "周建国"),
    (101, 100, "总经办", 1, "周建国"),
    (102, 100, "运营中心", 2, "李文彬"),
    (103, 102, "调度室", 1, "黄志远"),
    (104, 102, "车队", 2, "甘国华"),
    (105, 104, "长途车队", 1, "陆家明"),
    (106, 104, "短途车队", 2, "蓝志强"),
    (107, 102, "仓储部", 3, "罗永红"),
    (108, 107, "南宁仓", 1, "农春梅"),
    (109, 107, "柳州仓", 2, "邓丽萍"),
    (110, 100, "客服部", 3, "苏婉婷"),
    (111, 110, "客服一组", 1, "苏婉婷"),
    (112, 100, "财务部", 4, "唐国平"),
    (113, 112, "结算组", 1, "周敏"),
    (114, 112, "成本核算组", 2, "何丽"),
    (115, 100, "安全部", 5, "杨志刚"),
    (116, 115, "车辆安全组", 1, "张海峰"),
]
DEPT_NAME = {d[0]: d[2] for d in DEPTS}

# user_id, 姓名, dept_id, 岗位
EMPLOYEES = [
    (2001, "周建国", 101, "总经理"),
    (2002, "陈立", 101, "副总经理"),
    (2003, "李文彬", 102, "运营总监"),
    (2004, "黄志远", 103, "调度主管"),
    (2005, "梁伟成", 103, "调度员"),
    (2006, "韦晓东", 103, "调度员"),
    (2007, "覃海涛", 103, "调度员"),
    (2008, "甘国华", 104, "车队长"),
    (2009, "陆家明", 105, "长途车队队长"),
    (2010, "蓝志强", 106, "短途车队队长"),
    (2011, "罗永红", 107, "仓储经理"),
    (2012, "农春梅", 108, "南宁仓主管"),
    (2013, "邓丽萍", 109, "柳州仓主管"),
    (2014, "蒙小燕", 108, "仓管员"),
    (2015, "黄海生", 109, "仓管员"),
    (2016, "苏婉婷", 110, "客服主管"),
    (2017, "李春燕", 111, "客服专员"),
    (2018, "吴婷婷", 111, "客服专员"),
    (2019, "唐国平", 112, "财务经理"),
    (2020, "周敏", 113, "会计"),
    (2021, "何丽", 114, "出纳"),
    (2022, "杨志刚", 115, "安全主管"),
    (2023, "张海峰", 116, "安全员"),
]

# ry 改造为运营中心运营专员（user_id=2），工号排在 23 名员工之后
RY_EMPLOYEE = (2, "李伟", 102, "运营专员")

SURNAMES = "赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜戚谢邹喻柏水窦章云苏潘葛奚范彭郎鲁韦昌马苗凤花方俞任袁柳唐罗薛伍余米贝姚孟高夏蔡田樊胡凌霍虞万支柯昝管卢莫经房裘缪干解应宗丁宣邓郁单杭洪包诸左石崔吉龚程嵇邢裴陆荣翁荀羊於惠甄曲家封芮羿储靳汲邴糜松井段富巫乌焦巴弓牧隗山谷车侯宓蓬全郗班仰秋仲伊宫宁仇栾暴甘钭厉戎祖武符刘景詹束龙叶幸司韶郜黎蓟薄印宿白怀蒲邰从鄂索咸籍赖卓蔺屠蒙池乔阴胥能苍双闻莘党翟谭贡劳逄姬申扶堵冉宰郦雍却璩桑桂濮牛寿通边扈燕冀郏浦尚农温别庄晏柴瞿阎充慕连茹习宦艾鱼容向古易慎戈廖庾终暨居衡步都耿满弘匡国文寇广禄阙东欧殳沃利蔚越夔隆师巩厍聂晁勾敖融冷訾辛阚那简饶空曾毋沙乜养鞠须丰巢关蒯相查后荆红游竺权逯盖益桓公".replace("\n", "")
GIVEN = ["建国", "志强", "海涛", "伟", "军", "明", "华", "文", "杰", "勇", "平", "刚", "强", "斌", "辉",
         "丽", "燕", "娜", "敏", "静", "婷", "芳", "梅", "霞", "玲", "秀英", "桂兰", "春梅", "小燕", "丽萍"]


def person_name():
    return random.choice(SURNAMES) + random.choice(GIVEN)


def phone():
    return random.choice(["138", "139", "189"]) + "".join(random.choice("0123456789") for _ in range(8))


def email_for(login_name):
    return "%s@shunjie-logistics.cn" % login_name.lower()


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
    "DROP TABLE IF EXISTS biz_waybill",
    "DROP TABLE IF EXISTS biz_vehicle",
    "DROP TABLE IF EXISTS biz_driver",
    "DROP TABLE IF EXISTS biz_customer",
    """CREATE TABLE biz_customer (
  customer_id bigint(20) NOT NULL AUTO_INCREMENT COMMENT '客户ID',
  customer_code varchar(32) NOT NULL COMMENT '客户编号',
  customer_name varchar(100) NOT NULL COMMENT '客户名称',
  contact_name varchar(30) DEFAULT NULL COMMENT '联系人',
  contact_phone varchar(20) DEFAULT NULL COMMENT '联系电话',
  address varchar(200) DEFAULT NULL COMMENT '联系地址',
  credit_level char(1) DEFAULT 'B' COMMENT '信用等级（A/B/C）',
  contract_no varchar(50) DEFAULT NULL COMMENT '合同编号',
  status char(1) DEFAULT '0' COMMENT '状态（0正常 1停用）',
  create_by varchar(64) DEFAULT NULL COMMENT '创建者',
  create_time datetime DEFAULT NULL COMMENT '创建时间',
  update_by varchar(64) DEFAULT NULL COMMENT '更新者',
  update_time datetime DEFAULT NULL COMMENT '更新时间',
  remark varchar(500) DEFAULT NULL COMMENT '备注',
  PRIMARY KEY (customer_id),
  UNIQUE KEY uk_biz_customer_code (customer_code),
  KEY idx_biz_customer_name (customer_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='客户档案'""",
    """CREATE TABLE biz_vehicle (
  vehicle_id bigint(20) NOT NULL AUTO_INCREMENT COMMENT '车辆ID',
  plate_no varchar(16) NOT NULL COMMENT '车牌号',
  vehicle_type varchar(30) DEFAULT NULL COMMENT '车型',
  load_capacity decimal(8,2) DEFAULT NULL COMMENT '核定载重（吨）',
  owner_dept_id bigint(20) DEFAULT NULL COMMENT '所属车队',
  driver_id bigint(20) DEFAULT NULL COMMENT '主驾司机',
  status char(1) DEFAULT '0' COMMENT '状态（0空闲 1在途 2维修）',
  buy_date date DEFAULT NULL COMMENT '购置日期',
  insurance_expire date DEFAULT NULL COMMENT '保险到期日',
  create_by varchar(64) DEFAULT NULL COMMENT '创建者',
  create_time datetime DEFAULT NULL COMMENT '创建时间',
  update_by varchar(64) DEFAULT NULL COMMENT '更新者',
  update_time datetime DEFAULT NULL COMMENT '更新时间',
  remark varchar(500) DEFAULT NULL COMMENT '备注',
  PRIMARY KEY (vehicle_id),
  UNIQUE KEY uk_biz_vehicle_plate (plate_no),
  KEY idx_biz_vehicle_dept (owner_dept_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='车辆台账'""",
    """CREATE TABLE biz_driver (
  driver_id bigint(20) NOT NULL AUTO_INCREMENT COMMENT '司机ID',
  driver_no varchar(32) NOT NULL COMMENT '司机工号',
  driver_name varchar(30) NOT NULL COMMENT '司机姓名',
  gender varchar(4) DEFAULT '男' COMMENT '性别',
  phone varchar(20) DEFAULT NULL COMMENT '手机号',
  id_card varchar(18) DEFAULT NULL COMMENT '身份证号',
  license_no varchar(32) DEFAULT NULL COMMENT '驾驶证号',
  license_type varchar(4) DEFAULT 'A2' COMMENT '准驾车型（A2/B2）',
  license_expire date DEFAULT NULL COMMENT '驾驶证有效期',
  hire_date date DEFAULT NULL COMMENT '入职日期',
  dept_id bigint(20) DEFAULT NULL COMMENT '所属车队',
  status char(1) DEFAULT '0' COMMENT '状态（0在职 1休假 2离职）',
  create_by varchar(64) DEFAULT NULL COMMENT '创建者',
  create_time datetime DEFAULT NULL COMMENT '创建时间',
  update_by varchar(64) DEFAULT NULL COMMENT '更新者',
  update_time datetime DEFAULT NULL COMMENT '更新时间',
  remark varchar(500) DEFAULT NULL COMMENT '备注',
  PRIMARY KEY (driver_id),
  UNIQUE KEY uk_biz_driver_no (driver_no),
  KEY idx_biz_driver_dept (dept_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='司机档案'""",
    """CREATE TABLE biz_waybill (
  waybill_id bigint(20) NOT NULL AUTO_INCREMENT COMMENT '运单ID',
  waybill_no varchar(32) NOT NULL COMMENT '运单号',
  customer_id bigint(20) DEFAULT NULL COMMENT '客户ID',
  vehicle_id bigint(20) DEFAULT NULL COMMENT '车辆ID',
  driver_id bigint(20) DEFAULT NULL COMMENT '司机ID',
  origin_city varchar(30) DEFAULT NULL COMMENT '始发地',
  dest_city varchar(30) DEFAULT NULL COMMENT '目的地',
  cargo_name varchar(50) DEFAULT NULL COMMENT '货物名称',
  cargo_weight decimal(10,2) DEFAULT NULL COMMENT '货物重量（吨）',
  freight_amount decimal(12,2) DEFAULT NULL COMMENT '运费金额',
  status char(1) DEFAULT '0' COMMENT '状态（0待调度 1已调度 2运输中 3已签收 4异常 5已取消）',
  plan_send_time datetime DEFAULT NULL COMMENT '计划发运时间',
  actual_send_time datetime DEFAULT NULL COMMENT '实际发运时间',
  plan_arrive_time datetime DEFAULT NULL COMMENT '计划到达时间',
  actual_arrive_time datetime DEFAULT NULL COMMENT '实际到达时间',
  sign_man varchar(30) DEFAULT NULL COMMENT '签收人',
  create_by varchar(64) DEFAULT NULL COMMENT '创建者',
  create_time datetime DEFAULT NULL COMMENT '创建时间',
  update_by varchar(64) DEFAULT NULL COMMENT '更新者',
  update_time datetime DEFAULT NULL COMMENT '更新时间',
  remark varchar(500) DEFAULT NULL COMMENT '备注',
  PRIMARY KEY (waybill_id),
  UNIQUE KEY uk_biz_waybill_no (waybill_no),
  KEY idx_biz_waybill_customer (customer_id),
  KEY idx_biz_waybill_status (status),
  KEY idx_biz_waybill_create (create_time),
  KEY idx_biz_waybill_plan (plan_send_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='运单台账'""",
]

# ----------------------------------------------------------------------------
# 客户
# ----------------------------------------------------------------------------
CITY_BRAND = ["南宁", "柳州", "桂林", "梧州", "北海", "防城港", "钦州", "贵港", "玉林", "百色",
              "贺州", "河池", "来宾", "崇左", "广州", "深圳", "佛山", "东莞", "中山", "珠海",
              "昆明", "曲靖", "玉溪", "大理"]
BRANDS = ["恒达", "鑫源", "桂通", "联发", "兴业", "昌盛", "宏泰", "金桥", "顺发", "华晨",
          "正大", "万通", "瑞丰", "天成", "嘉禾", "远大", "中盛", "新辉", "德昌", "富源"]
INDUSTRIES = ["机械制造", "建材", "食品", "商贸", "物流", "化工", "电子科技", "包装材料", "农业开发", "供应链管理"]
ROADS = ["大道", "工业路", "产业园", "物流园", "商贸城", "开发区", "路", "街"]


def build_customers():
    combos = [(c, b, i) for c in CITY_BRAND for b in BRANDS for i in INDUSTRIES]
    random.shuffle(combos)
    rows = []
    for idx in range(180):
        city, brand, industry = combos[idx]
        name = "%s%s%s有限公司" % (city, brand, industry)
        code = "KH%04d" % (idx + 1)
        credit = random.choices(["A", "B", "C"], weights=[35, 55, 10])[0]
        st = "0" if idx < 170 else "1"
        created = NOW - dt.timedelta(days=random.randint(40, 1080), hours=random.randint(0, 8))
        rows.append(dict(
            customer_id=idx + 1, customer_code=code, customer_name=name,
            contact_name=person_name(), contact_phone=phone(),
            address="%s市%s%d号%s" % (city, random.choice(ROADS), random.randint(1, 288), random.choice(["", "3栋", "A座"])),
            credit_level=credit, contract_no="HT%d%04d" % (random.randint(2019, 2026), idx + 1),
            status=st, create_by="admin", create_time=created,
            update_by="admin", update_time=created + dt.timedelta(days=random.randint(1, 60)),
            remark=random.choice(["长期合作客户", "月结客户", "现结客户", "重点客户", "新开发客户", ""]),
        ))
    return rows


# ----------------------------------------------------------------------------
# 司机
# ----------------------------------------------------------------------------
def build_drivers():
    statuses = ["0"] * 52 + ["1"] * 6 + ["2"] * 2
    random.shuffle(statuses)
    rows = []
    for idx in range(60):
        did = idx + 1
        dept = random.choice([104, 105, 105, 106, 106])
        birth = dt.date(random.randint(1970, 1992), random.randint(1, 12), random.randint(1, 28))
        id_card = "4501%02d%04d%02d%02d%04d" % (random.randint(1, 30), birth.year, birth.month, birth.day,
                                               random.randint(1, 9999))
        hire = TODAY - dt.timedelta(days=random.randint(120, 2600))
        rows.append(dict(
            driver_id=did, driver_no="DRV%04d" % did, driver_name=person_name(),
            gender="男" if random.random() < 0.92 else "女", phone=phone(),
            id_card=id_card, license_no="4501%011d" % random.randint(1, 99999999999),
            license_type=random.choices(["A2", "B2"], weights=[70, 30])[0],
            license_expire=TODAY + dt.timedelta(days=random.randint(120, 1700)),
            hire_date=hire, dept_id=dept, status=statuses[idx],
            create_by="admin", create_time=at(hire, 9, random.randint(0, 59)),
            update_by="admin", update_time=at(TODAY - dt.timedelta(days=random.randint(1, 200)), 16, 0),
            remark=random.choice(["熟悉云贵线路", "熟悉两广线路", "危险品运输资质", "冷链运输经验", ""]),
        ))
    return rows


# ----------------------------------------------------------------------------
# 车辆
# ----------------------------------------------------------------------------
PLATE_CHARS = "ABCDEFGHJKLMNPQRSTUVWXYZ0123456789"
VEHICLE_TYPES = [
    ("9.6米厢式", 18.0), ("13米高栏", 30.0), ("17.5米平板", 35.0),
    ("冷链车", 15.0), ("罐式车", 25.0),
]


def build_vehicles(drivers):
    statuses = ["0"] * 20 + ["1"] * 20 + ["2"] * 5
    random.shuffle(statuses)
    plates = set()
    rows = []
    for idx in range(45):
        vid = idx + 1
        while True:
            plate = random.choice(["桂A", "桂B"]) + "".join(random.choice(PLATE_CHARS) for _ in range(5))
            if plate not in plates:
                plates.add(plate)
                break
        vtype, cap = random.choice(VEHICLE_TYPES)
        buy = TODAY - dt.timedelta(days=random.randint(60, 2100))
        rows.append(dict(
            vehicle_id=vid, plate_no=plate, vehicle_type=vtype,
            load_capacity=round(cap + random.choice([0, 0, 0.5, -0.5]), 2),
            owner_dept_id=random.choice([105, 105, 106, 106, 104]),
            driver_id=drivers[idx]["driver_id"] if idx < len(drivers) else None,
            status=statuses[idx], buy_date=buy,
            insurance_expire=TODAY + dt.timedelta(days=random.randint(20, 400)),
            create_by="admin", create_time=at(buy, 10, 30),
            update_by="admin", update_time=at(TODAY - dt.timedelta(days=random.randint(1, 90)), 15, 20),
            remark=random.choice(["已安装GPS", "已安装北斗定位", "年检合格", "二级维护到期已保养", ""]),
        ))
    return rows


# ----------------------------------------------------------------------------
# 运单
# ----------------------------------------------------------------------------
CITIES = ["南宁", "柳州", "桂林", "梧州", "北海", "防城港", "钦州", "贵港", "玉林", "百色",
          "贺州", "河池", "来宾", "崇左", "广州", "深圳", "佛山", "东莞", "中山", "珠海",
          "昆明", "曲靖", "玉溪", "大理"]
CARGOS = ["钢材", "水泥", "化肥", "大米", "白糖", "柑橘", "木材", "纸浆", "汽车配件", "家用电器",
          "食品饮料", "建材瓷砖", "塑料粒子", "铝锭", "锰矿", "饲料", "日用百货", "机械设备"]
DISPATCHERS = ["黄志远", "梁伟成", "韦晓东", "覃海涛"]


def build_waybills(customers, vehicles):
    statuses = ["0"] * 96 + ["1"] * 120 + ["2"] * 144 + ["3"] * 744 + ["4"] * 60 + ["5"] * 36
    random.shuffle(statuses)
    rows = []
    seq_by_date = {}
    i = 0
    for m in range(-11, 1):
        first = month_start(m)
        y, mo = first.year, first.month
        last_day = calendar.monthrange(y, mo)[1]
        if y == TODAY.year and mo == TODAY.month:
            last_day = TODAY.day
        for _ in range(100):
            day = random.randint(1, last_day)
            created = at(dt.date(y, mo, day), random.randint(6, 21), random.randint(0, 59), random.randint(0, 59))
            if created > NOW:
                created = NOW - dt.timedelta(minutes=random.randint(10, 600))
            date_key = created.strftime("%Y%m%d")
            seq_by_date[date_key] = seq_by_date.get(date_key, 0) + 1
            no = "SJ%s%04d" % (date_key, seq_by_date[date_key])

            customer = random.choice(customers)
            vehicle = random.choice(vehicles)
            driver_id = vehicle["driver_id"] or random.randint(1, 60)
            origin, dest = random.sample(CITIES, 2)
            status = statuses[i]
            plan_send = created + dt.timedelta(hours=random.randint(2, 48), minutes=random.randint(0, 59))
            transit = random.randint(8, 60)
            plan_arrive = plan_send + dt.timedelta(hours=transit, minutes=random.randint(0, 59))
            actual_send = None
            actual_arrive = None
            sign_man = None
            remark = ""
            if status in ("2", "3", "4"):
                actual_send = plan_send + dt.timedelta(hours=random.randint(-2, 8), minutes=random.randint(-40, 40))
            if status == "3":
                actual_arrive = plan_arrive + dt.timedelta(hours=random.randint(-4, 10), minutes=random.randint(0, 59))
                if actual_arrive <= plan_send:
                    actual_arrive = plan_send + dt.timedelta(hours=transit + 2)
                sign_man = person_name()
                remark = random.choice(["", "客户验收无误", "回单已回收", "货损理赔完成"])
            elif status == "4":
                remark = random.choice(["车辆故障，转运处理", "高速封路延误", "货物破损待理赔", "客户拒收，等待协调"])
            elif status == "5":
                remark = random.choice(["客户取消订单", "运力不足取消", "重复下单取消"])

            rows.append(dict(
                waybill_id=i + 1, waybill_no=no,
                customer_id=customer["customer_id"], vehicle_id=vehicle["vehicle_id"], driver_id=driver_id,
                origin_city=origin, dest_city=dest,
                cargo_name=random.choice(CARGOS), cargo_weight=round(random.uniform(2, 35), 2),
                freight_amount=round(random.uniform(300, 15800), 2), status=status,
                plan_send_time=plan_send, actual_send_time=actual_send,
                plan_arrive_time=plan_arrive, actual_arrive_time=actual_arrive, sign_man=sign_man,
                create_by=random.choice(DISPATCHERS), create_time=created,
                update_by=random.choice(DISPATCHERS),
                update_time=actual_arrive or actual_send or plan_send,
                remark=remark,
            ))
            i += 1
    return rows


# ----------------------------------------------------------------------------
# 员工 / 部门 / 用户
# ----------------------------------------------------------------------------
def build_users():
    rows = []
    # ry -> 李伟
    uid, name, dept, post = RY_EMPLOYEE
    rows.append(dict(
        user_id=uid, dept_id=dept, login_name="SJ0024", user_name=name, user_type="00",
        email=email_for("SJ0024"), phonenumber=phone(), sex="1", avatar="",
        password=pw_hash("SJ0024", "admin123", ADMIN_SALT), salt=ADMIN_SALT, status="0", del_flag="0",
        login_ip="192.168.10.24", login_date=NOW - dt.timedelta(hours=6),
        pwd_update_date=None, create_by="admin", create_time=NOW - dt.timedelta(days=640),
        update_by="admin", update_time=NOW - dt.timedelta(days=30), remark=post,
    ))
    for idx, (uid, name, dept, post) in enumerate(EMPLOYEES):
        login = "SJ%04d" % (idx + 1)
        sex = "1" if name in ("农春梅", "邓丽萍", "蒙小燕", "苏婉婷", "李春燕", "吴婷婷", "周敏", "何丽") else "0"
        rows.append(dict(
            user_id=uid, dept_id=dept, login_name=login, user_name=name, user_type="00",
            email=email_for(login), phonenumber=phone(), sex=sex, avatar="",
            password=pw_hash(login, "admin123", ADMIN_SALT), salt=ADMIN_SALT, status="0", del_flag="0",
            login_ip="192.168.10.%d" % (100 + uid % 100), login_date=NOW - dt.timedelta(days=random.randint(0, 20)),
            pwd_update_date=None, create_by="admin",
            create_time=NOW - dt.timedelta(days=random.randint(30, 1200), hours=random.randint(0, 8)),
            update_by="admin", update_time=NOW - dt.timedelta(days=random.randint(1, 60)), remark=post,
        ))
    return rows


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
            email="dept%d@shunjie-logistics.cn" % dept_id,
            status="0", del_flag="0", create_by="admin",
            create_time=NOW - dt.timedelta(days=1800), update_by="admin",
            update_time=NOW - dt.timedelta(days=90),
        ))
    return rows


# ----------------------------------------------------------------------------
# 日志
# ----------------------------------------------------------------------------
def workday_day():
    while True:
        d = TODAY - dt.timedelta(days=random.randint(0, 29))
        if d.weekday() >= 5 and random.random() < 0.62:
            continue
        return d


BROWSERS = ["Chrome 118", "Chrome 120", "Edge 118", "Firefox 115", "Chrome 119"]
OS_LIST = ["Windows 10", "Windows 11", "Windows 10", "Windows 7", "macOS 12"]
IPS = ["192.168.10.%d", "10.20.30.%d"]


def build_logins(user_rows):
    staff = [(u["login_name"], u["user_name"], u["dept_id"]) for u in user_rows]
    staff += [("admin", "系统管理员", 101), ("scanner_low", "运维支持", 105)]
    picks = []
    for item in staff:
        picks.extend([item] * 4)
    while len(picks) < 240:
        picks.append(random.choice(staff))
    picks = picks[:240]
    random.shuffle(picks)
    rows = []
    for i, (login, name, dept) in enumerate(picks, 1):
        d = workday_day()
        t = at(d, random.randint(8, 19), random.randint(0, 59), random.randint(0, 59))
        if t > NOW:
            t = NOW - dt.timedelta(minutes=random.randint(5, 400))
        failed = random.random() < 0.06
        rows.append(dict(
            info_id=i, login_name=login,
            ipaddr=random.choice(IPS) % random.randint(2, 250),
            login_location="广西壮族自治区南宁市" if random.random() < 0.7 else "广西壮族自治区柳州市",
            browser=random.choice(BROWSERS), os=random.choice(OS_LIST),
            status="1" if failed else "0",
            msg="密码错误" if failed else "登录成功",
            login_time=t,
        ))
    return rows


OPER_TITLES = [
    ("运单管理", 0.40, "business.Waybill", [
        ("list", "查询运单列表", 0, "POST", "/business/waybill/list", 0),
        ("detail", "查看运单详情", 0, "GET", "/business/waybill/detail", 0),
        ("export", "导出运单数据", 5, "POST", "/business/waybill/export", 0),
        ("dispatch", "调度运单", 2, "POST", "/business/waybill/dispatch", 0),
    ]),
    ("车辆管理", 0.16, "business.Vehicle", [
        ("list", "查询车辆列表", 0, "POST", "/business/vehicle/list", 0),
        ("detail", "查看车辆详情", 0, "GET", "/business/vehicle/detail", 0),
    ]),
    ("司机管理", 0.12, "business.Driver", [
        ("list", "查询司机列表", 0, "POST", "/business/driver/list", 0),
        ("detail", "查看司机档案", 0, "GET", "/business/driver/detail", 0),
    ]),
    ("客户管理", 0.12, "business.Customer", [
        ("list", "查询客户列表", 0, "POST", "/business/customer/list", 0),
        ("detail", "查看客户档案", 0, "GET", "/business/customer/detail", 0),
    ]),
    ("用户管理", 0.08, "system.SysUser", [
        ("list", "查询用户列表", 0, "POST", "/system/user/list", 0),
        ("edit", "修改用户信息", 2, "POST", "/system/user/edit", 0),
    ]),
    ("角色管理", 0.06, "system.SysRole", [
        ("list", "查询角色列表", 0, "POST", "/system/role/list", 0),
        ("edit", "修改角色信息", 2, "POST", "/system/role/edit", 0),
    ]),
    ("菜单管理", 0.06, "system.SysMenu", [
        ("list", "查询菜单列表", 0, "POST", "/system/menu/list", 0),
        ("edit", "修改菜单信息", 2, "POST", "/system/menu/edit", 0),
    ]),
]


def build_opers(user_rows):
    staff = [(u["user_name"], u["dept_id"]) for u in user_rows]
    names = [t[0] for t in OPER_TITLES]
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
        failed = random.random() < 0.04
        rows.append(dict(
            oper_id=i, title=title, business_type=btype,
            method="com.ruoyi.web.controller.%sController.%s" % (ctrl, act),
            request_method=req, operator_type=1, oper_name=name,
            dept_name=DEPT_NAME.get(dept, ""),
            oper_url=url, oper_ip=random.choice(IPS) % random.randint(2, 250),
            oper_location="广西壮族自治区南宁市",
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
         menu_type="M", visible="0", is_refresh="1", perms="", icon="fa fa-truck"),
    dict(menu_id=2001, menu_name="运单管理", parent_id=2000, order_num=1, url="/business/waybill", target="",
         menu_type="C", visible="0", is_refresh="1", perms="biz:waybill:list", icon="fa fa-file-text-o"),
    dict(menu_id=2002, menu_name="车辆管理", parent_id=2000, order_num=2, url="/business/vehicle", target="",
         menu_type="C", visible="0", is_refresh="1", perms="biz:vehicle:list", icon="fa fa-truck"),
    dict(menu_id=2003, menu_name="司机管理", parent_id=2000, order_num=3, url="/business/driver", target="",
         menu_type="C", visible="0", is_refresh="1", perms="biz:driver:list", icon="fa fa-id-card-o"),
    dict(menu_id=2004, menu_name="客户管理", parent_id=2000, order_num=4, url="/business/customer", target="",
         menu_type="C", visible="0", is_refresh="1", perms="biz:customer:list", icon="fa fa-users"),
    dict(menu_id=2005, menu_name="查询", parent_id=2001, order_num=1, url="#", target="",
         menu_type="F", visible="0", is_refresh="1", perms="biz:waybill:query", icon="#"),
    dict(menu_id=2006, menu_name="详情", parent_id=2001, order_num=2, url="#", target="",
         menu_type="F", visible="0", is_refresh="1", perms="biz:waybill:detail", icon="#"),
    dict(menu_id=2007, menu_name="导出", parent_id=2001, order_num=3, url="#", target="",
         menu_type="F", visible="0", is_refresh="1", perms="biz:waybill:export", icon="#"),
]
MENU_COLS = ["menu_id", "menu_name", "parent_id", "order_num", "url", "target", "menu_type",
             "visible", "is_refresh", "perms", "icon", "create_by", "create_time", "remark"]


def build_menus():
    rows = []
    for m in MENUS:
        r = dict(m)
        r.update(create_by="admin", create_time=NOW - dt.timedelta(days=120), remark=None)
        rows.append(r)
    return rows


# ----------------------------------------------------------------------------
# 写库
# ----------------------------------------------------------------------------
CUSTOMER_COLS = ["customer_id", "customer_code", "customer_name", "contact_name", "contact_phone",
                 "address", "credit_level", "contract_no", "status", "create_by", "create_time",
                 "update_by", "update_time", "remark"]
VEHICLE_COLS = ["vehicle_id", "plate_no", "vehicle_type", "load_capacity", "owner_dept_id", "driver_id",
                "status", "buy_date", "insurance_expire", "create_by", "create_time", "update_by",
                "update_time", "remark"]
DRIVER_COLS = ["driver_id", "driver_no", "driver_name", "gender", "phone", "id_card", "license_no",
               "license_type", "license_expire", "hire_date", "dept_id", "status", "create_by",
               "create_time", "update_by", "update_time", "remark"]
WAYBILL_COLS = ["waybill_id", "waybill_no", "customer_id", "vehicle_id", "driver_id", "origin_city",
                "dest_city", "cargo_name", "cargo_weight", "freight_amount", "status", "plan_send_time",
                "actual_send_time", "plan_arrive_time", "actual_arrive_time", "sign_man", "create_by",
                "create_time", "update_by", "update_time", "remark"]
DEPT_COLS = ["dept_id", "parent_id", "ancestors", "dept_name", "order_num", "leader", "phone", "email",
             "status", "del_flag", "create_by", "create_time", "update_by", "update_time"]
USER_COLS = ["user_id", "dept_id", "login_name", "user_name", "user_type", "email", "phonenumber", "sex",
             "avatar", "password", "salt", "status", "del_flag", "login_ip", "login_date",
             "pwd_update_date", "create_by", "create_time", "update_by", "update_time", "remark"]
LOGIN_COLS = ["info_id", "login_name", "ipaddr", "login_location", "browser", "os", "status", "msg", "login_time"]
OPER_COLS = ["oper_id", "title", "business_type", "method", "request_method", "operator_type", "oper_name",
             "dept_name", "oper_url", "oper_ip", "oper_location", "oper_param", "json_result", "status",
             "error_msg", "oper_time"]


def main():
    customers = build_customers()
    drivers = build_drivers()
    vehicles = build_vehicles(drivers)
    waybills = build_waybills(customers, vehicles)
    depts = build_depts()
    users = build_users()
    logins = build_logins(users)
    opers = build_opers(users)
    menus = build_menus()

    statements = []
    statements += DDL

    # ---- 组织架构 ----
    statements += [
        "DELETE FROM sys_dept WHERE dept_id BETWEEN 100 AND 116",
        "DELETE FROM sys_user WHERE user_id = 2 OR user_id BETWEEN 2001 AND 2023",
        "DELETE FROM sys_user_role WHERE user_id = 2 OR user_id BETWEEN 2001 AND 2023",
        "DELETE FROM sys_user_post WHERE user_id = 2 OR user_id BETWEEN 2001 AND 2023",
        "UPDATE sys_user SET user_name = '系统管理员', email = 'admin@shunjie-logistics.cn', "
        "phonenumber = '13877001001', remark = '系统管理员' WHERE user_id = 1",
    ]
    statements += insert_sql("sys_dept", depts, DEPT_COLS)
    statements += insert_sql("sys_user", users, USER_COLS)

    user_roles = [dict(user_id=2, role_id=2)]
    user_posts = [dict(user_id=2, post_id=2)]
    for uid, name, dept, post in EMPLOYEES:
        user_roles.append(dict(user_id=uid, role_id=2))
        if uid == 2001:
            post_id = 1
        elif post in ("副总经理", "运营总监", "调度主管", "车队长", "长途车队队长", "短途车队队长",
                      "仓储经理", "南宁仓主管", "柳州仓主管", "客服主管", "财务经理", "安全主管", "总经理"):
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
        "DELETE FROM sys_role_menu WHERE menu_id = 4 OR menu_id BETWEEN 2000 AND 2007",
        "DELETE FROM sys_menu WHERE menu_id = 4 OR menu_id BETWEEN 2000 AND 2007",
    ]
    statements += insert_sql("sys_menu", menus, MENU_COLS)
    role_menus = [dict(role_id=1, menu_id=m["menu_id"]) for m in MENUS]
    statements += insert_sql("sys_role_menu", role_menus, ["role_id", "menu_id"])

    # ---- 业务数据 ----
    statements += insert_sql("biz_customer", customers, CUSTOMER_COLS)
    statements += insert_sql("biz_driver", drivers, DRIVER_COLS)
    statements += insert_sql("biz_vehicle", vehicles, VEHICLE_COLS)
    statements += insert_sql("biz_waybill", waybills, WAYBILL_COLS)

    # ---- 日志 ----
    statements += ["DELETE FROM sys_logininfor", "DELETE FROM sys_oper_log"]
    statements += insert_sql("sys_logininfor", logins, LOGIN_COLS)
    statements += insert_sql("sys_oper_log", opers, OPER_COLS)

    with open(SQL_FILE, "w", encoding="utf-8") as f:
        f.write("-- R2 广西顺捷物流有限公司演示数据（由 seed/r2_business.py 生成）\n")
        f.write("SET NAMES utf8mb4;\nUSE ry_r2;\n\n")
        f.write(";\n\n".join(s.rstrip(";") for s in statements))
        f.write(";\n")

    conn = pymysql.connect(**DB, autocommit=False)
    try:
        cur = conn.cursor()
        cur.execute("SET NAMES utf8mb4")
        for stmt in statements:
            cur.execute(stmt)
        conn.commit()
        verify(conn)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def verify(conn):
    cur = conn.cursor()
    print("=" * 64)
    print("R2 广西顺捷物流有限公司数据灌入完成")
    print("=" * 64)
    for t in ("biz_customer", "biz_vehicle", "biz_driver", "biz_waybill",
              "sys_dept", "sys_user", "sys_menu", "sys_logininfor", "sys_oper_log"):
        cur.execute("SELECT COUNT(*) FROM %s" % t)
        print("%-16s %s" % (t, cur.fetchone()[0]))

    cur.execute("SELECT status, COUNT(*) FROM biz_waybill GROUP BY status ORDER BY status")
    names = {"0": "待调度", "1": "已调度", "2": "运输中", "3": "已签收", "4": "异常", "5": "已取消"}
    print("\n运单状态分布：")
    for r in cur.fetchall():
        print("  %-6s %s" % (names.get(r[0], r[0]), r[1]))

    cur.execute("""SELECT DATE_FORMAT(create_time, '%Y-%m') m, COUNT(*) FROM biz_waybill
                   GROUP BY m ORDER BY m""")
    print("\n近 12 个月运单量：")
    for r in cur.fetchall():
        print("  %s  %s" % (r[0], r[1]))

    cur.execute("SELECT COUNT(*) FROM sys_user WHERE dept_id BETWEEN 100 AND 116")
    print("\n部门内用户：%s" % cur.fetchone()[0])
    print("SQL 文件：%s" % SQL_FILE)


if __name__ == "__main__":
    main()
