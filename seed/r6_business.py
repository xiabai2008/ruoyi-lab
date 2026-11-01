#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R6 深圳市跨境通电子商务有限公司 订单管理演示数据灌入脚本
=====================================================================
目标库：MySQL 127.0.0.1:13307 / ry_r6
说明：
  1. 重建 biz_sku / biz_order / biz_inventory / biz_shipment 四张业务表
  2. 重建 23 个部门的组织架构，保留 admin 与 scanner_low，重建 30 名员工
  3. 重建业务菜单与 role_id=1 的授权（只插不删既有授权）
  4. 重写登录日志与操作日志（近 30 天，工作日多，无未来时间）
  5. 可重复执行，完整 SQL 落盘到 seed/r6_business.sql

用法：python seed/r6_business.py
"""
import datetime as dt
import os
import random

import pymysql
from pymysql.converters import escape_string

DB = dict(host="127.0.0.1", port=13307, user="root", password="", database="ry_r6", charset="utf8mb4")

TODAY = dt.date.today()
NOW = dt.datetime.now().replace(microsecond=0)
SAFE_NOW = NOW - dt.timedelta(minutes=2)
SEED = 20261030
random.seed(SEED)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SQL_FILE = os.path.join(BASE_DIR, "r6_business.sql")

DOMAIN = "kuajingtong.com"

# 复用 admin 现有 BCrypt 哈希（本库无 salt 列）
ADMIN_HASH = "$2a$10$7JB720yubVSZvUI0rEqK/.VqGOZTH.ulu33dHOiBE8ByOhJIrdAu2"

# ----------------------------------------------------------------------------
# 组织架构：23 个节点，3 层，ID 固定
# ----------------------------------------------------------------------------
# (dept_id, parent_id, dept_name, order_num)
DEPTS = [
    (100, 0, "深圳市跨境通电子商务有限公司", 0),
    (110, 100, "运营中心", 1),
    (111, 100, "采购部", 2),
    (112, 100, "仓储部", 3),
    (113, 100, "物流部", 4),
    (114, 100, "客服部", 5),
    (115, 100, "财务部", 6),
    (116, 100, "技术部", 7),
    (120, 110, "亚马逊运营组", 1),
    (121, 110, "东南亚运营组", 2),
    (122, 110, "独立站运营组", 3),
    (123, 111, "供应商开发组", 1),
    (124, 111, "采购执行组", 2),
    (125, 112, "深圳仓", 1),
    (126, 112, "东莞仓", 2),
    (127, 113, "头程运输组", 1),
    (128, 113, "尾程派送组", 2),
    (129, 114, "售前客服组", 1),
    (130, 114, "售后客服组", 2),
    (131, 115, "结算组", 1),
    (132, 115, "税务组", 2),
    (133, 116, "开发组", 1),
    (134, 116, "运维组", 2),
]
DEPT_NAME = {d[0]: d[2] for d in DEPTS}
DEPT_LEADER = {
    100: "陈志远", 110: "林嘉怡", 111: "何家明", 112: "谢婷婷", 113: "蔡建国",
    114: "韦志明", 115: "卢俊杰", 116: "莫嘉欣",
    120: "黄文杰", 121: "吴俊豪", 122: "郑凯文", 123: "罗丽君", 124: "邓志强",
    125: "曾伟业", 126: "蒋海涛", 127: "潘子豪", 128: "唐丽华", 129: "梁晓燕",
    130: "许文静", 131: "谭美琪", 132: "陆志辉", 133: "覃浩", 134: "石雨欣",
}

# (user_id, 姓名, dept_id, 岗位, 性别)
EMPLOYEES = [
    (2001, "陈志远", 100, "总经理", "0"),
    (2002, "林嘉怡", 110, "运营总监", "1"),
    (2003, "黄文杰", 120, "亚马逊运营主管", "0"),
    (2004, "李思敏", 120, "亚马逊运营专员", "1"),
    (2005, "吴俊豪", 121, "东南亚运营主管", "0"),
    (2006, "周晓彤", 121, "Shopee 运营专员", "1"),
    (2007, "郑凯文", 122, "独立站运营主管", "0"),
    (2008, "冯雅雯", 122, "独立站运营专员", "1"),
    (2009, "何家明", 111, "采购经理", "0"),
    (2010, "罗丽君", 123, "供应商开发主管", "1"),
    (2011, "邓志强", 124, "采购执行专员", "0"),
    (2012, "谢婷婷", 112, "仓储经理", "1"),
    (2013, "曾伟业", 125, "深圳仓主管", "0"),
    (2014, "彭美玲", 125, "仓管员", "1"),
    (2015, "蒋海涛", 126, "东莞仓主管", "0"),
    (2016, "苏婉婷", 126, "仓管员", "1"),
    (2017, "蔡建国", 113, "物流经理", "0"),
    (2018, "潘子豪", 127, "头程运输主管", "0"),
    (2019, "唐丽华", 128, "尾程派送专员", "1"),
    (2020, "韦志明", 114, "客服经理", "0"),
    (2021, "梁晓燕", 129, "售前客服主管", "1"),
    (2022, "许文静", 130, "售后客服专员", "1"),
    (2023, "卢俊杰", 115, "财务经理", "0"),
    (2024, "谭美琪", 131, "结算会计", "1"),
    (2025, "陆志辉", 132, "税务专员", "0"),
    (2026, "莫嘉欣", 116, "技术经理", "1"),
    (2027, "覃浩", 133, "开发工程师", "0"),
    (2028, "石雨欣", 134, "运维工程师", "1"),
    (2029, "黎志强", 110, "运营数据分析师", "0"),
    (2030, "覃丽婷", 130, "客服专员", "1"),
]
EMP_LOGIN = {e[0]: "KJ%04d" % (i + 1) for i, e in enumerate(EMPLOYEES)}
EMP_NAME = {e[0]: e[1] for e in EMPLOYEES}


def phone():
    return random.choice(["138", "139", "189"]) + "".join(random.choice("0123456789") for _ in range(8))


def email_for(login_name):
    return "%s@%s" % (login_name.lower(), DOMAIN)


# ----------------------------------------------------------------------------
# 业务表结构
# ----------------------------------------------------------------------------
DDL = [
    "DROP TABLE IF EXISTS biz_shipment",
    "DROP TABLE IF EXISTS biz_inventory",
    "DROP TABLE IF EXISTS biz_order",
    "DROP TABLE IF EXISTS biz_sku",
    """CREATE TABLE biz_sku (
  sku_id bigint(20) NOT NULL AUTO_INCREMENT COMMENT 'SKU主键',
  sku_code varchar(20) NOT NULL COMMENT 'SKU编码',
  product_name varchar(120) NOT NULL COMMENT '商品名称',
  category varchar(20) DEFAULT NULL COMMENT '商品品类',
  brand varchar(30) DEFAULT NULL COMMENT '品牌',
  cost_price decimal(10,2) DEFAULT '0.00' COMMENT '成本价',
  sale_price decimal(10,2) DEFAULT '0.00' COMMENT '销售价',
  weight_g int(11) DEFAULT NULL COMMENT '重量（克）',
  origin_country varchar(20) DEFAULT NULL COMMENT '原产国',
  status varchar(10) DEFAULT NULL COMMENT '状态（在售 停售 待上架）',
  launch_date date DEFAULT NULL COMMENT '上架日期',
  remark varchar(500) DEFAULT NULL COMMENT '备注',
  create_by varchar(64) DEFAULT NULL COMMENT '创建者',
  create_time datetime DEFAULT NULL COMMENT '创建时间',
  update_by varchar(64) DEFAULT NULL COMMENT '更新者',
  update_time datetime DEFAULT NULL COMMENT '更新时间',
  PRIMARY KEY (sku_id),
  UNIQUE KEY uk_biz_sku_code (sku_code),
  KEY idx_biz_sku_category (category),
  KEY idx_biz_sku_status (status),
  KEY idx_biz_sku_launch (launch_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='跨境通商品SKU'""",
    """CREATE TABLE biz_order (
  order_id bigint(20) NOT NULL AUTO_INCREMENT COMMENT '订单主键',
  order_no varchar(32) NOT NULL COMMENT '订单号',
  platform varchar(20) DEFAULT NULL COMMENT '销售平台',
  country varchar(20) DEFAULT NULL COMMENT '目的国',
  buyer_name varchar(50) DEFAULT NULL COMMENT '买家姓名',
  item_qty int(11) DEFAULT '0' COMMENT '商品件数',
  sku_count int(11) DEFAULT '0' COMMENT 'SKU数量',
  order_amount decimal(12,2) DEFAULT '0.00' COMMENT '订单金额',
  currency varchar(8) DEFAULT NULL COMMENT '币种',
  freight_amount decimal(12,2) DEFAULT '0.00' COMMENT '运费',
  status varchar(10) DEFAULT NULL COMMENT '订单状态',
  pay_time datetime DEFAULT NULL COMMENT '付款时间',
  ship_time datetime DEFAULT NULL COMMENT '发货时间',
  finish_time datetime DEFAULT NULL COMMENT '完成时间',
  sales_dept_id bigint(20) DEFAULT NULL COMMENT '销售部门ID',
  sales_dept varchar(50) DEFAULT NULL COMMENT '销售部门',
  owner varchar(30) DEFAULT NULL COMMENT '负责人',
  remark varchar(500) DEFAULT NULL COMMENT '备注',
  create_by varchar(64) DEFAULT NULL COMMENT '创建者',
  create_time datetime DEFAULT NULL COMMENT '创建时间（下单时间）',
  update_by varchar(64) DEFAULT NULL COMMENT '更新者',
  update_time datetime DEFAULT NULL COMMENT '更新时间',
  PRIMARY KEY (order_id),
  UNIQUE KEY uk_biz_order_no (order_no),
  KEY idx_biz_order_platform (platform),
  KEY idx_biz_order_country (country),
  KEY idx_biz_order_status (status),
  KEY idx_biz_order_create (create_time),
  KEY idx_biz_order_dept (sales_dept_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='跨境通订单'""",
    """CREATE TABLE biz_inventory (
  inventory_id bigint(20) NOT NULL AUTO_INCREMENT COMMENT '库存主键',
  sku_code varchar(20) NOT NULL COMMENT 'SKU编码',
  sku_name varchar(120) DEFAULT NULL COMMENT '商品名称',
  warehouse varchar(20) DEFAULT NULL COMMENT '仓库',
  total_qty int(11) DEFAULT '0' COMMENT '库存总量',
  available_qty int(11) DEFAULT '0' COMMENT '可用库存',
  locked_qty int(11) DEFAULT '0' COMMENT '锁定库存',
  safety_qty int(11) DEFAULT '0' COMMENT '安全库存',
  last_in_date date DEFAULT NULL COMMENT '最近入库日期',
  status varchar(10) DEFAULT NULL COMMENT '库存状态（正常 预警 缺货）',
  remark varchar(500) DEFAULT NULL COMMENT '备注',
  create_by varchar(64) DEFAULT NULL COMMENT '创建者',
  create_time datetime DEFAULT NULL COMMENT '创建时间',
  update_by varchar(64) DEFAULT NULL COMMENT '更新者',
  update_time datetime DEFAULT NULL COMMENT '更新时间',
  PRIMARY KEY (inventory_id),
  UNIQUE KEY uk_biz_inventory_sku (sku_code),
  KEY idx_biz_inventory_warehouse (warehouse),
  KEY idx_biz_inventory_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='跨境通库存'""",
    """CREATE TABLE biz_shipment (
  shipment_id bigint(20) NOT NULL AUTO_INCREMENT COMMENT '物流单主键',
  shipment_no varchar(32) NOT NULL COMMENT '物流单号',
  order_no varchar(32) NOT NULL COMMENT '订单号',
  carrier varchar(20) DEFAULT NULL COMMENT '承运商',
  tracking_no varchar(40) NOT NULL COMMENT '运单号',
  dest_country varchar(20) DEFAULT NULL COMMENT '目的国',
  warehouse varchar(20) DEFAULT NULL COMMENT '发货仓库',
  package_count int(11) DEFAULT '1' COMMENT '包裹数',
  weight_kg decimal(8,2) DEFAULT '0.00' COMMENT '重量（千克）',
  status varchar(10) DEFAULT NULL COMMENT '物流状态',
  ship_date date DEFAULT NULL COMMENT '发货日期',
  delivered_date date DEFAULT NULL COMMENT '签收日期',
  remark varchar(500) DEFAULT NULL COMMENT '备注',
  create_by varchar(64) DEFAULT NULL COMMENT '创建者',
  create_time datetime DEFAULT NULL COMMENT '创建时间',
  update_by varchar(64) DEFAULT NULL COMMENT '更新者',
  update_time datetime DEFAULT NULL COMMENT '更新时间',
  PRIMARY KEY (shipment_id),
  UNIQUE KEY uk_biz_shipment_no (shipment_no),
  UNIQUE KEY uk_biz_tracking_no (tracking_no),
  KEY idx_biz_shipment_order (order_no),
  KEY idx_biz_shipment_carrier (carrier),
  KEY idx_biz_shipment_status (status),
  KEY idx_biz_shipment_date (ship_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='跨境通物流单'""",
]


# ----------------------------------------------------------------------------
# SKU 字典
# ----------------------------------------------------------------------------
SKU_PLAN = [
    ("3C数码", "A", 90, ["KJTGO", "Voyager", "TechNest"],
     ["无线蓝牙耳机", "快充数据线", "磁吸充电宝", "便携蓝牙音箱", "智能手表", "手机支架",
      "USB-C 扩展坞", "无线鼠标", "机械键盘", "高清网络摄像头", "氮化镓充电器", "车载充电器",
      "骨传导耳机", "智能手环", "平板保护壳", "笔记本散热支架"],
     (35, 320), (80, 500)),
    ("家居日用", "B", 80, ["HomeEase", "KJTGO", "CozyLine"],
     ["折叠收纳箱", "记忆棉枕头", "香薰加湿器", "厨房收纳架", "不锈钢保温杯", "硅胶洗碗刷",
      "衣物收纳袋", "桌面置物架", "陶瓷餐具套装", "真空保鲜盒", "电动牙刷", "浴室置物架",
      "防滑地垫", "多功能衣架", "厨房刀具套装", "感应垃圾桶"],
     (18, 180), (120, 3000)),
    ("户外运动", "C", 60, ["Voyager", "TrailPeak", "KJTGO"],
     ["折叠露营椅", "户外帐篷", "登山背包", "便携睡袋", "运动水壶", "露营灯", "折叠桌",
      "瑜伽垫", "骑行手套", "户外防风打火机", "徒步登山杖", "野餐垫", "运动护膝", "钓鱼收纳包"],
     (40, 460), (200, 5000)),
    ("美妆个护", "D", 50, ["GlowMuse", "KJTGO", "PureLane"],
     ["化妆刷套装", "保湿面霜", "便携化妆镜", "洗发水", "护发精油", "补水面膜", "指甲护理套装",
      "电动修眉刀", "防晒喷雾", "洁面仪", "唇釉套装", "美妆蛋"],
     (25, 260), (80, 800)),
    ("母婴用品", "E", 45, ["BabyNest", "KJTGO", "LittleVoyager"],
     ["婴儿推车", "硅胶辅食碗", "儿童保温杯", "婴儿浴盆", "宝宝爬行垫", "儿童安全座椅",
      "婴儿湿巾", "奶瓶消毒器", "婴儿背带", "儿童餐具套装"],
     (30, 380), (150, 4500)),
    ("汽车配件", "F", 40, ["AutoMate", "KJTGO", "RoadPro"],
     ["车载手机支架", "汽车脚垫", "车载吸尘器", "轮胎充气泵", "汽车遮阳挡", "车载香薰",
      "行车记录仪", "汽车座套", "车载冰箱", "方向盘套"],
     (28, 520), (200, 4800)),
    ("宠物用品", "G", 35, ["PetNest", "KJTGO", "PawJoy"],
     ["宠物自动喂食器", "猫爬架", "宠物牵引绳", "宠物窝", "猫砂盆", "宠物饮水机",
      "宠物玩具球", "宠物梳毛刷", "宠物航空箱", "宠物尿垫"],
     (20, 300), (100, 3500)),
]

SPECS = ["标准版", "升级版", "Pro 版", "旗舰版", "轻享版", "加厚款", "便携款", "家用款",
         "2024 款", "2025 款", "黑色", "白色", "灰色", "蓝色", "大号", "中号", "小号",
         "双件装", "三件装", "礼盒装"]

SKU_CREATE_BY = ["陈志远", "林嘉怡", "何家明", "罗丽君", "邓志强"]


def build_skus():
    rows = []
    idx = 0
    for category, prefix, count, brands, bases, cost_rng, weight_rng in SKU_PLAN:
        used = set()
        for n in range(1, count + 1):
            idx += 1
            while True:
                name = "%s %s" % (random.choice(bases), random.choice(SPECS))
                if name not in used:
                    used.add(name)
                    break
            cost = round(random.uniform(*cost_rng), 2)
            sale = round(cost * random.uniform(1.6, 2.8), 2)
            launch = TODAY - dt.timedelta(days=random.randint(30, 1360))
            if launch < dt.date(2023, 1, 1):
                launch = dt.date(2023, 1, 1) + dt.timedelta(days=random.randint(0, 365))
            if launch > dt.date(2026, 9, 30):
                launch = dt.date(2026, 9, 30)
            ctime = dt.datetime.combine(launch, dt.time(random.randint(9, 18), random.randint(0, 59)))
            if ctime > SAFE_NOW:
                ctime = SAFE_NOW
            rows.append(dict(
                sku_id=idx, sku_code="KJ-%s%04d" % (prefix, n), product_name=name,
                category=category, brand=random.choice(brands), cost_price=cost, sale_price=sale,
                weight_g=random.randint(*weight_rng), origin_country="中国",
                status="在售", launch_date=launch,
                remark="%s系列，跨境专供" % random.choice(["热销", "新品", "常规", "主推"]),
                create_by=random.choice(SKU_CREATE_BY), create_time=ctime,
                update_by="admin", update_time=ctime + dt.timedelta(days=random.randint(1, 60)),
            ))
    # 状态分布：在售 340 / 停售 40 / 待上架 20
    statuses = ["在售"] * 340 + ["停售"] * 40 + ["待上架"] * 20
    random.shuffle(statuses)
    for r, st in zip(rows, statuses):
        r["status"] = st
        if r["update_time"] > SAFE_NOW:
            r["update_time"] = SAFE_NOW
    # 原产国：中国 340 / 越南 35 / 泰国 25
    origins = ["中国"] * 340 + ["越南"] * 35 + ["泰国"] * 25
    random.shuffle(origins)
    for r, o in zip(rows, origins):
        r["origin_country"] = o
    return rows


# ----------------------------------------------------------------------------
# 订单字典
# ----------------------------------------------------------------------------
PLATFORMS = [
    ("Amazon", 520, 120, ("黄文杰", "李思敏")),
    ("Shopee", 300, 121, ("吴俊豪", "周晓彤")),
    ("Lazada", 180, 121, ("吴俊豪", "周晓彤")),
    ("TikTok Shop", 220, 121, ("吴俊豪", "周晓彤")),
    ("eBay", 120, 122, ("郑凯文", "冯雅雯")),
    ("独立站", 160, 122, ("郑凯文", "冯雅雯")),
]
PLATFORM_PLAN = []
for _p, _cnt, _dept, _owners in PLATFORMS:
    PLATFORM_PLAN += [(_p, _dept, _owners)] * _cnt

COUNTRY_CURRENCY = [
    ("美国", "USD", (19, 899)),
    ("德国", "EUR", (15, 799)),
    ("英国", "GBP", (12, 699)),
    ("日本", "JPY", (1800, 98000)),
    ("新加坡", "SGD", (25, 1200)),
    ("马来西亚", "MYR", (60, 3800)),
    ("泰国", "THB", (500, 29000)),
    ("越南", "VND", (300000, 15000000)),
    ("菲律宾", "PHP", (800, 45000)),
    ("澳大利亚", "AUD", (25, 1300)),
]
COUNTRY_WEIGHT = [0.24, 0.12, 0.11, 0.10, 0.08, 0.08, 0.07, 0.07, 0.06, 0.07]

BUYER_NAMES = {
    "美国": ["Emily Carter", "Michael Johnson", "Sophia Miller", "Daniel Brown", "Olivia Davis",
             "Ethan Wilson", "Ava Martinez", "James Anderson", "Mia Taylor", "Noah Thomas"],
    "德国": ["Michael Braun", "Anna Schmidt", "Lukas Weber", "Sophie Fischer", "Felix Wagner",
             "Laura Becker", "Jonas Hoffmann", "Lea Schulz", "Tim Krause", "Nina Wolf"],
    "英国": ["Oliver Smith", "Charlotte Jones", "Harry Williams", "Amelia Brown", "George Taylor",
             "Isla Davies", "Jack Evans", "Grace Wilson", "Thomas Moore", "Freya Clark"],
    "日本": ["佐藤健太", "鈴木美咲", "高橋大輔", "田中由美", "伊藤翔太", "渡辺彩",
             "山本拓真", "中村結衣", "小林悠斗", "加藤さくら"],
    "新加坡": ["Wei Ming Tan", "Jia Hui Lim", "Marcus Lee", "Sarah Ng", "Daniel Koh",
               "Rachel Teo", "Kevin Chua", "Michelle Goh", "Ryan Ong", "Chloe Sim"],
    "马来西亚": ["Ahmad Faiz", "Nur Aisyah", "Lim Wei Jian", "Siti Sarah", "Tan Jia Min",
                 "Muhammad Irfan", "Chong Mei Ling", "Aina Zulkifli", "Lee Kai Wen", "Farah Nadia"],
    "泰国": ["Somchai Prasert", "Nattaya Srisuk", "Kittipong Chai", "Pimchanok Wong",
             "Anan Ratchada", "Siriporn Kaew", "Thanawat Boon", "Malee Sukhum", "Pongsak Dee", "Araya Porn"],
    "越南": ["Nguyen Van An", "Tran Thi Mai", "Le Minh Tuan", "Pham Thu Ha", "Hoang Quoc Bao",
             "Vu Ngoc Lan", "Dang Van Hung", "Bui Thanh Hoa", "Do Minh Khoa", "Ngo Thi Thu"],
    "菲律宾": ["Juan Dela Cruz", "Maria Santos", "Jose Reyes", "Angelica Bautista", "Carlo Garcia",
               "Bea Mendoza", "Mark Villanueva", "Liza Ramos", "Paolo Aquino", "Grace Lim"],
    "澳大利亚": ["Liam Wilson", "Chloe Thompson", "Noah Robinson", "Isabella Walker", "Jack Harris",
                 "Mia Campbell", "Lucas Stewart", "Ruby Mitchell", "Henry Cooper", "Zoe Turner"],
}

ORDER_REMARKS = [
    "客户备注：请使用环保包装", "加急订单，优先出库", "客户要求附赠感谢卡",
    "节假日促销订单", "需开具商业发票", "易碎品，注意防震包装", "",
    "客户已确认收货地址", "海外仓直发", "批量采购订单",
]

STATUS_PLAN = [("待付款", 60), ("待发货", 180), ("已发货", 240),
               ("已完成", 900), ("已取消", 80), ("退款中", 40)]

ORDER_COLS = ["order_id", "order_no", "platform", "country", "buyer_name", "item_qty", "sku_count",
              "order_amount", "currency", "freight_amount", "status", "pay_time", "ship_time",
              "finish_time", "sales_dept_id", "sales_dept", "owner", "remark", "create_by",
              "create_time", "update_by", "update_time"]


def build_orders():
    statuses = []
    for name, cnt in STATUS_PLAN:
        statuses.extend([name] * cnt)
    assert len(statuses) == 1500
    random.shuffle(statuses)

    platforms = list(PLATFORM_PLAN)
    random.shuffle(platforms)

    start = dt.date(2025, 11, 1)
    end = dt.date(2026, 10, 29)
    orders = []
    seq_by_day = {}

    for i, status in enumerate(statuses, 1):
        platform, dept_id, owners = platforms[i - 1]
        country, currency, amount_rng = random.choices(COUNTRY_CURRENCY, weights=COUNTRY_WEIGHT)[0]

        # 按状态限制最晚下单日，保证 pay/ship/finish 时间链不越界
        if status == "已完成":
            last_day = TODAY - dt.timedelta(days=26)
        elif status == "已发货":
            last_day = TODAY - dt.timedelta(days=10)
        elif status == "退款中":
            last_day = TODAY - dt.timedelta(days=3)
        elif status == "待发货":
            last_day = TODAY - dt.timedelta(days=1)
        else:
            last_day = TODAY
        last_day = min(last_day, end)
        d = start + dt.timedelta(days=random.randint(0, (last_day - start).days))
        create_time = dt.datetime.combine(d, dt.time(random.randint(8, 22), random.randint(0, 59),
                                                     random.randint(0, 59)))
        if create_time > SAFE_NOW:
            create_time = SAFE_NOW

        pay_time = ship_time = finish_time = None
        update_time = create_time
        if status in ("待发货", "已发货", "已完成", "退款中"):
            pay_time = create_time + dt.timedelta(minutes=random.randint(5, 60),
                                                  hours=random.randint(0, 35))
            if pay_time > SAFE_NOW:
                pay_time = SAFE_NOW - dt.timedelta(minutes=random.randint(1, 30))
            if pay_time < create_time:
                pay_time = create_time
            update_time = pay_time
        if status in ("已发货", "已完成"):
            ship_time = pay_time + dt.timedelta(days=random.randint(1, 5),
                                                hours=random.randint(0, 10))
            if ship_time > SAFE_NOW:
                ship_time = SAFE_NOW - dt.timedelta(hours=random.randint(1, 20))
            if ship_time < pay_time:
                ship_time = pay_time
            update_time = ship_time
        if status == "已完成":
            finish_time = ship_time + dt.timedelta(days=random.randint(2, 12),
                                                   hours=random.randint(0, 12))
            if finish_time > SAFE_NOW:
                finish_time = SAFE_NOW - dt.timedelta(minutes=random.randint(10, 500))
            if finish_time < ship_time:
                finish_time = ship_time
            update_time = finish_time
        if update_time > SAFE_NOW:
            update_time = SAFE_NOW

        seq_by_day[d] = seq_by_day.get(d, 0) + 1
        order_no = "KJ%s%05d" % (d.strftime("%Y%m%d"), seq_by_day[d])

        lo, hi = amount_rng
        amount = round(random.uniform(lo, hi), 2)
        freight = round(amount * random.uniform(0.0, 0.08), 2)
        qty = random.randint(1, 6)
        sku_cnt = random.randint(1, min(4, qty))

        orders.append(dict(
            order_id=i, order_no=order_no, platform=platform, country=country,
            buyer_name=random.choice(BUYER_NAMES[country]), item_qty=qty, sku_count=sku_cnt,
            order_amount=amount, currency=currency, freight_amount=freight, status=status,
            pay_time=pay_time, ship_time=ship_time, finish_time=finish_time,
            sales_dept_id=dept_id, sales_dept=DEPT_NAME[dept_id], owner=random.choice(owners),
            remark=random.choice(ORDER_REMARKS),
            create_by=random.choice(owners), create_time=create_time,
            update_by=random.choice(owners), update_time=update_time,
        ))
    return orders


# ----------------------------------------------------------------------------
# 库存
# ----------------------------------------------------------------------------
def build_inventory(skus):
    whs = ["深圳仓"] * 220 + ["东莞仓"] * 180
    random.shuffle(whs)
    statuses = ["正常"] * 300 + ["预警"] * 70 + ["缺货"] * 30
    random.shuffle(statuses)

    rows = []
    for i, (sku, wh, status) in enumerate(zip(skus, whs, statuses), 1):
        safety = random.randint(20, 200)
        if status == "缺货":
            total = 0
            locked = 0
            available = 0
        elif status == "预警":
            available = random.randint(0, safety - 1)
            locked = random.randint(0, 200)
            total = available + locked
            if total == 0:
                total = 1
                locked = 1
                available = 0
        else:
            total = random.randint(200, 3000)
            locked = random.randint(0, min(200, total))
            available = total - locked
            if available < safety:
                available = safety + random.randint(1, 300)
                total = available + locked
        last_in = TODAY - dt.timedelta(days=random.randint(0, 180))
        ctime = dt.datetime.combine(TODAY - dt.timedelta(days=random.randint(180, 700)),
                                    dt.time(random.randint(9, 18), random.randint(0, 59)))
        if ctime > SAFE_NOW:
            ctime = SAFE_NOW
        utime = dt.datetime.combine(last_in, dt.time(random.randint(9, 18), random.randint(0, 59)))
        if utime > SAFE_NOW:
            utime = SAFE_NOW
        rows.append(dict(
            inventory_id=i, sku_code=sku["sku_code"], sku_name=sku["product_name"],
            warehouse=wh, total_qty=total, available_qty=available, locked_qty=locked,
            safety_qty=safety, last_in_date=last_in, status=status,
            remark="%s库存，%s" % (wh, random.choice(["定期盘点", "正常周转", "待补货", "新品入仓"])),
            create_by="谢婷婷", create_time=ctime, update_by="曾伟业", update_time=utime,
        ))
    return rows


# ----------------------------------------------------------------------------
# 物流单
# ----------------------------------------------------------------------------
CARRIERS = ["DHL", "UPS", "FedEx", "顺丰国际", "燕文物流", "云途物流", "4PX递四方"]
SHIPPED_STATUS = ["待揽收", "已揽收", "运输中", "派送中", "异常"]


def tracking_no(used):
    while True:
        if random.random() < 0.5:
            t = "JD" + "".join(random.choice("0123456789") for _ in range(12))
        else:
            t = "1Z" + "".join(random.choice("0123456789ABCDEFGHJKLMNPQRSTUVWXYZ") for _ in range(16))
        if t not in used:
            used.add(t)
            return t


def build_shipments(orders):
    completed = [o for o in orders if o["status"] == "已完成"]
    shipped = [o for o in orders if o["status"] == "已发货"]
    assert len(completed) == 900 and len(shipped) == 240

    picked_shipped = random.sample(shipped, 60)
    plan = [(o, 1) for o in completed]
    for o in shipped:
        plan.append((o, 2 if o in picked_shipped else 1))

    used_tracking = set()
    raw = []
    for order, cnt in plan:
        for _ in range(cnt):
            pay_date = order["pay_time"].date() if order["pay_time"] else order["create_time"].date()
            ship_date = pay_date + dt.timedelta(days=random.randint(0, 2))
            if ship_date > TODAY:
                ship_date = TODAY
            if ship_date < pay_date:
                ship_date = pay_date
            if order["status"] == "已完成":
                status = "已签收"
                delivered = ship_date + dt.timedelta(days=random.randint(1, 10))
                if delivered > TODAY:
                    delivered = TODAY
                if delivered < ship_date:
                    delivered = ship_date
            else:
                status = random.choice(SHIPPED_STATUS)
                delivered = None
            ctime = dt.datetime.combine(ship_date, dt.time(random.randint(9, 19), random.randint(0, 59),
                                                           random.randint(0, 59)))
            if ctime > SAFE_NOW:
                ctime = SAFE_NOW
            utime = dt.datetime.combine(delivered, dt.time(random.randint(10, 20), random.randint(0, 59))) \
                if delivered else ctime
            if utime > SAFE_NOW:
                utime = SAFE_NOW
            raw.append(dict(
                order_no=order["order_no"], carrier=random.choice(CARRIERS),
                tracking_no=tracking_no(used_tracking), dest_country=order["country"],
                warehouse=random.choice(["深圳仓", "东莞仓"]), package_count=random.randint(1, 4),
                weight_kg=round(random.uniform(0.2, 25.0), 2), status=status,
                ship_date=ship_date, delivered_date=delivered,
                remark="%s" % random.choice(["标准物流", "经济小包", "专线物流", "海外仓发货", ""]),
                create_by=order["owner"], create_time=ctime,
                update_by=order["owner"], update_time=utime,
            ))

    # 按发货日期生成物流单号：FH + yyyyMMdd + 4 位序号
    raw.sort(key=lambda r: (r["ship_date"], r["order_no"]))
    day_seq = {}
    for i, r in enumerate(raw, 1):
        d = r["ship_date"]
        day_seq[d] = day_seq.get(d, 0) + 1
        r["shipment_id"] = i
        r["shipment_no"] = "FH%s%04d" % (d.strftime("%Y%m%d"), day_seq[d])
    return raw


# ----------------------------------------------------------------------------
# 部门 / 用户
# ----------------------------------------------------------------------------
def build_depts():
    rows = []
    parent_map = {d[0]: d[1] for d in DEPTS}
    for dept_id, parent_id, name, order_num in DEPTS:
        if dept_id == 100:
            ancestors = "0"
        else:
            path = []
            p = parent_id
            while p != 0:
                path.append(str(p))
                p = parent_map.get(p, 0)
            ancestors = "0," + ",".join(reversed(path))
        rows.append(dict(
            dept_id=dept_id, parent_id=parent_id, ancestors=ancestors, dept_name=name,
            order_num=order_num, leader=DEPT_LEADER.get(dept_id, ""), phone=phone(),
            email="dept%d@%s" % (dept_id, DOMAIN),
            status="0", del_flag="0", create_by="admin",
            create_time=dt.datetime(2024, 3, 18, 9, 0, 0),
            update_by="admin", update_time=NOW - dt.timedelta(days=random.randint(30, 300)),
        ))
    return rows


def build_users():
    rows = []
    for uid, name, dept, post, sex in EMPLOYEES:
        login = EMP_LOGIN[uid]
        created = dt.datetime(2024, 3, 1, 9, 0, 0) + dt.timedelta(days=random.randint(0, 300))
        rows.append(dict(
            user_id=uid, dept_id=dept, user_name=login, nick_name=name, user_type="00",
            email=email_for(login), phonenumber=phone(), sex=sex, avatar="",
            password=ADMIN_HASH, status="0", del_flag="0",
            login_ip="10.30.20.%d" % random.randint(2, 250),
            login_date=SAFE_NOW - dt.timedelta(days=random.randint(0, 6),
                                               hours=random.randint(0, 8),
                                               minutes=random.randint(0, 59)),
            pwd_update_date=NOW - dt.timedelta(days=random.randint(1, 89)),
            create_by=str(dept), create_time=created, update_by="admin",
            update_time=NOW - dt.timedelta(days=random.randint(1, 90)),
            remark=post,
        ))
    return rows


# ----------------------------------------------------------------------------
# 日志
# ----------------------------------------------------------------------------
def workday_day():
    """近 30 天；仅约 8% 概率落到周末。"""
    while True:
        d = TODAY - dt.timedelta(days=random.randint(0, 29))
        if d.weekday() >= 5 and random.random() > 0.08:
            continue
        return d


BROWSERS = ["Chrome 118", "Chrome 120", "Edge 118", "Firefox 115", "Chrome 119", "360SE 13"]
OS_LIST = ["Windows 10", "Windows 11", "Windows 10", "Windows 7", "macOS 12"]
IPS = ["10.30.20.%d", "192.168.20.%d"]
LOCATIONS = ["广东省深圳市", "广东省深圳市", "广东省东莞市", "广东省广州市"]


def build_logins():
    staff = [(e[2], e[1]) for e in EMPLOYEES]
    staff += [("admin", "系统管理员"), ("scanner_low", "运维支持")]
    picks = []
    for item in staff:
        picks.extend([item] * 6)
    while len(picks) < 300:
        picks.append(random.choice(staff))
    picks = picks[:300]
    random.shuffle(picks)

    rows = []
    for i, (login, name) in enumerate(picks, 1):
        d = workday_day()
        t = dt.datetime.combine(d, dt.time(random.randint(8, 19), random.randint(0, 59),
                                           random.randint(0, 59)))
        if t > SAFE_NOW:
            t = SAFE_NOW - dt.timedelta(minutes=random.randint(5, 400))
        failed = random.random() < 0.05
        rows.append(dict(
            info_id=i, user_name=login,
            ipaddr=random.choice(IPS) % random.randint(2, 250),
            login_location=random.choice(LOCATIONS),
            browser=random.choice(BROWSERS), os=random.choice(OS_LIST),
            status="1" if failed else "0",
            msg="密码错误" if failed else "登录成功",
            login_time=t,
        ))
    return rows


OPER_TITLES = [
    ("订单管理", 0.30, "business.BizOrder", [
        ("list", "查询订单列表", 0, "GET", "/business/order/list"),
        ("detail", "查看订单详情", 0, "GET", "/business/order/128"),
        ("export", "导出订单数据", 5, "POST", "/business/order/export"),
    ]),
    ("商品管理", 0.16, "business.BizSku", [
        ("list", "查询商品列表", 0, "GET", "/business/sku/list"),
        ("detail", "查看商品详情", 0, "GET", "/business/sku/64"),
    ]),
    ("库存盘点", 0.16, "business.BizInventory", [
        ("list", "查询库存列表", 0, "GET", "/business/inventory/list"),
        ("export", "导出库存数据", 5, "POST", "/business/inventory/export"),
    ]),
    ("物流发运", 0.14, "business.BizShipment", [
        ("list", "查询物流单列表", 0, "GET", "/business/shipment/list"),
        ("detail", "查看物流单详情", 0, "GET", "/business/shipment/256"),
    ]),
    ("客户服务", 0.10, "business.BizOrder", [
        ("list", "查询售后订单", 0, "GET", "/business/order/list"),
    ]),
    ("用户管理", 0.06, "system.SysUser", [
        ("list", "查询用户列表", 0, "GET", "/system/user/list"),
        ("edit", "修改用户信息", 2, "PUT", "/system/user"),
    ]),
    ("角色管理", 0.04, "system.SysRole", [
        ("list", "查询角色列表", 0, "GET", "/system/role/list"),
        ("edit", "修改角色信息", 2, "PUT", "/system/role"),
    ]),
    ("菜单管理", 0.04, "system.SysMenu", [
        ("list", "查询菜单列表", 0, "GET", "/system/menu/list"),
        ("edit", "修改菜单信息", 2, "PUT", "/system/menu"),
    ]),
]


def build_opers():
    staff = [(e[1], e[2]) for e in EMPLOYEES]
    weights = [t[1] for t in OPER_TITLES]
    rows = []
    for i in range(1, 401):
        title, _, ctrl, actions = random.choices(OPER_TITLES, weights=weights)[0]
        act, label, btype, req, url = random.choice(actions)
        d = workday_day()
        t = dt.datetime.combine(d, dt.time(random.randint(8, 19), random.randint(0, 59),
                                           random.randint(0, 59)))
        if t > SAFE_NOW:
            t = SAFE_NOW - dt.timedelta(minutes=random.randint(5, 400))
        name, dept = random.choice(staff)
        failed = random.random() < 0.03
        rows.append(dict(
            oper_id=i, title=title, business_type=btype,
            method="com.ruoyi.web.controller.%sController.%s" % (ctrl, act),
            request_method=req, operator_type=1, oper_name=name,
            dept_name=DEPT_NAME.get(dept, ""),
            oper_url=url, oper_ip=random.choice(IPS) % random.randint(2, 250),
            oper_location=random.choice(LOCATIONS),
            oper_param='{"pageNum":"1","pageSize":"10","orderByColumn":"createTime","isAsc":"desc"}',
            json_result='{"code":200,"msg":"操作成功"}' if not failed else '{"code":500,"msg":"操作失败"}',
            status=1 if failed else 0,
            error_msg="数据校验失败，请稍后重试" if failed else None,
            oper_time=t, cost_time=random.randint(20, 900),
        ))
    return rows


# ----------------------------------------------------------------------------
# 菜单
# ----------------------------------------------------------------------------
MENUS = [
    dict(menu_id=2000, menu_name="业务管理", parent_id=0, order_num=4, path="business",
         component=None, menu_type="M", perms="", icon="shopping"),
    dict(menu_id=2010, menu_name="订单管理", parent_id=2000, order_num=1, path="order",
         component="business/order/index", menu_type="C", perms="biz:order:list", icon="form"),
    dict(menu_id=2011, menu_name="商品管理", parent_id=2000, order_num=2, path="sku",
         component="business/sku/index", menu_type="C", perms="biz:sku:list", icon="goods"),
    dict(menu_id=2012, menu_name="库存管理", parent_id=2000, order_num=3, path="inventory",
         component="business/inventory/index", menu_type="C", perms="biz:inventory:list", icon="chart"),
    dict(menu_id=2013, menu_name="物流管理", parent_id=2000, order_num=4, path="shipment",
         component="business/shipment/index", menu_type="C", perms="biz:shipment:list", icon="guide"),
    dict(menu_id=2020, menu_name="查询", parent_id=2010, order_num=1, path="",
         component=None, menu_type="F", perms="biz:order:query", icon="#"),
    dict(menu_id=2021, menu_name="详情", parent_id=2010, order_num=2, path="",
         component=None, menu_type="F", perms="biz:order:detail", icon="#"),
    dict(menu_id=2022, menu_name="导出", parent_id=2010, order_num=3, path="",
         component=None, menu_type="F", perms="biz:order:export", icon="#"),
]
MENU_COLS = ["menu_id", "menu_name", "parent_id", "order_num", "path", "component", "query",
             "route_name", "is_frame", "is_cache", "menu_type", "visible", "status", "perms",
             "icon", "create_by", "create_time", "remark"]


def build_menus():
    rows = []
    for m in MENUS:
        r = dict(m)
        r.update(query=None, route_name=None, is_frame=1, is_cache=0,
                 visible="0", status="0", create_by="admin",
                 create_time=dt.datetime(2026, 1, 8, 10, 0, 0), remark="")
        rows.append(r)
    return rows


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


SKU_COLS = ["sku_id", "sku_code", "product_name", "category", "brand", "cost_price", "sale_price",
            "weight_g", "origin_country", "status", "launch_date", "remark", "create_by",
            "create_time", "update_by", "update_time"]
INV_COLS = ["inventory_id", "sku_code", "sku_name", "warehouse", "total_qty", "available_qty",
            "locked_qty", "safety_qty", "last_in_date", "status", "remark", "create_by",
            "create_time", "update_by", "update_time"]
SHIP_COLS = ["shipment_id", "shipment_no", "order_no", "carrier", "tracking_no", "dest_country",
             "warehouse", "package_count", "weight_kg", "status", "ship_date", "delivered_date",
             "remark", "create_by", "create_time", "update_by", "update_time"]
DEPT_COLS = ["dept_id", "parent_id", "ancestors", "dept_name", "order_num", "leader", "phone",
             "email", "status", "del_flag", "create_by", "create_time", "update_by", "update_time"]
USER_COLS = ["user_id", "dept_id", "user_name", "nick_name", "user_type", "email", "phonenumber",
             "sex", "avatar", "password", "status", "del_flag", "login_ip", "login_date",
             "pwd_update_date", "create_by", "create_time", "update_by", "update_time", "remark"]
LOGIN_COLS = ["info_id", "user_name", "ipaddr", "login_location", "browser", "os", "status",
              "msg", "login_time"]
OPER_COLS = ["oper_id", "title", "business_type", "method", "request_method", "operator_type",
             "oper_name", "dept_name", "oper_url", "oper_ip", "oper_location", "oper_param",
             "json_result", "status", "error_msg", "oper_time", "cost_time"]


def main():
    skus = build_skus()
    orders = build_orders()
    inventory = build_inventory(skus)
    shipments = build_shipments(orders)
    depts = build_depts()
    users = build_users()
    logins = build_logins()
    opers = build_opers()
    menus = build_menus()

    statements = []
    statements += DDL

    # ---- 组织架构 ----
    statements += [
        "DELETE FROM sys_dept WHERE dept_id BETWEEN 100 AND 134",
        "DELETE FROM sys_user_role WHERE user_id NOT IN (1, 100)",
        "DELETE FROM sys_user_post WHERE user_id NOT IN (1, 100)",
        "DELETE FROM sys_user WHERE user_id NOT IN (1, 100)",
        "UPDATE sys_user SET dept_id = 100, nick_name = '系统管理员', email = 'admin@%s' WHERE user_id = 1" % DOMAIN,
        "UPDATE sys_user SET dept_id = 134 WHERE user_id = 100",
    ]
    statements += insert_sql("sys_dept", depts, DEPT_COLS)
    statements += insert_sql("sys_user", users, USER_COLS)

    user_roles = [dict(user_id=e[0], role_id=2) for e in EMPLOYEES]
    user_posts = []
    for e in EMPLOYEES:
        uid, post = e[0], e[3]
        if "总经理" in post:
            post_id = 1
        elif "经理" in post or "总监" in post or "主管" in post:
            post_id = 2
        else:
            post_id = 4
        user_posts.append(dict(user_id=uid, post_id=post_id))
    statements += insert_sql("sys_user_role", user_roles, ["user_id", "role_id"])
    statements += insert_sql("sys_user_post", user_posts, ["user_id", "post_id"])

    statements += [
        "UPDATE sys_post SET post_name = '总经理', post_code = 'ceo' WHERE post_id = 1",
        "UPDATE sys_post SET post_name = '部门主管', post_code = 'manager' WHERE post_id = 2",
        "UPDATE sys_post SET post_name = '人力专员', post_code = 'hr' WHERE post_id = 3",
        "UPDATE sys_post SET post_name = '业务专员', post_code = 'staff' WHERE post_id = 4",
    ]

    # ---- 菜单（仅清理 2000~2022 自有区间，menu_id=4 外链删除）----
    statements += [
        "DELETE FROM sys_menu WHERE menu_id BETWEEN 2000 AND 2022",
        "DELETE FROM sys_menu WHERE menu_id = 4",
    ]
    statements += insert_sql("sys_menu", menus, MENU_COLS)
    statements += [
        "INSERT INTO sys_role_menu (role_id, menu_id) SELECT 1, m.menu_id FROM sys_menu m "
        "WHERE m.menu_id BETWEEN 2000 AND 2022 AND NOT EXISTS "
        "(SELECT 1 FROM sys_role_menu rm WHERE rm.role_id = 1 AND rm.menu_id = m.menu_id)",
    ]

    # ---- 业务数据 ----
    statements += insert_sql("biz_sku", skus, SKU_COLS)
    statements += insert_sql("biz_order", orders, ORDER_COLS)
    statements += insert_sql("biz_inventory", inventory, INV_COLS)
    statements += insert_sql("biz_shipment", shipments, SHIP_COLS)

    # ---- 日志 ----
    statements += ["DELETE FROM sys_logininfor", "DELETE FROM sys_oper_log"]
    statements += insert_sql("sys_logininfor", logins, LOGIN_COLS)
    statements += insert_sql("sys_oper_log", opers, OPER_COLS)

    with open(SQL_FILE, "w", encoding="utf-8") as f:
        f.write("-- R6 深圳市跨境通电子商务有限公司 订单管理演示数据（由 seed/r6_business.py 生成）\n")
        f.write("SET NAMES utf8mb4;\nUSE ry_r6;\n\n")
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


TIME_CHECK = [
    ("sys_logininfor", "login_time"),
    ("sys_oper_log", "oper_time"),
    ("sys_user", "login_date"),
    ("sys_user", "create_time"),
    ("sys_user", "update_time"),
    ("sys_user", "pwd_update_date"),
    ("sys_dept", "create_time"),
    ("sys_dept", "update_time"),
    ("biz_sku", "launch_date"),
    ("biz_sku", "create_time"),
    ("biz_sku", "update_time"),
    ("biz_order", "create_time"),
    ("biz_order", "pay_time"),
    ("biz_order", "ship_time"),
    ("biz_order", "finish_time"),
    ("biz_order", "update_time"),
    ("biz_inventory", "last_in_date"),
    ("biz_inventory", "create_time"),
    ("biz_inventory", "update_time"),
    ("biz_shipment", "ship_date"),
    ("biz_shipment", "delivered_date"),
    ("biz_shipment", "create_time"),
    ("biz_shipment", "update_time"),
]


def fix_future(conn):
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


def scalar(cur, sql, *args):
    if args:
        cur.execute(sql, args)
    else:
        cur.execute(sql)
    return cur.fetchone()[0]


def verify(conn):
    cur = conn.cursor()
    print("=" * 64)
    print("R6 深圳市跨境通电子商务有限公司 订单管理数据灌入完成")
    print("=" * 64)
    for t in ("biz_sku", "biz_order", "biz_inventory", "biz_shipment",
              "sys_dept", "sys_user", "sys_menu", "sys_logininfor", "sys_oper_log"):
        cur.execute("SELECT COUNT(1) FROM %s" % t)
        print("%-16s %s" % (t, cur.fetchone()[0]))

    errors = []
    expect = {"biz_sku": 400, "biz_order": 1500, "biz_inventory": 400, "biz_shipment": 1200}
    for t, n in expect.items():
        actual = scalar(cur, "SELECT COUNT(1) FROM %s" % t)
        if actual != n:
            errors.append("%s 行数 %s != %s" % (t, actual, n))

    # SKU
    if scalar(cur, "SELECT COUNT(DISTINCT sku_code) FROM biz_sku") != 400:
        errors.append("SKU 编码不唯一")
    for cat, cnt in (("3C数码", 90), ("家居日用", 80), ("户外运动", 60), ("美妆个护", 50),
                     ("母婴用品", 45), ("汽车配件", 40), ("宠物用品", 35)):
        actual = scalar(cur, "SELECT COUNT(1) FROM biz_sku WHERE category = %s", cat)
        if actual != cnt:
            errors.append("品类 %s 为 %s != %s" % (cat, actual, cnt))
    for st, cnt in (("在售", 340), ("停售", 40), ("待上架", 20)):
        actual = scalar(cur, "SELECT COUNT(1) FROM biz_sku WHERE status = %s", st)
        if actual != cnt:
            errors.append("SKU 状态 %s 为 %s != %s" % (st, actual, cnt))
    for oc, cnt in (("中国", 340), ("越南", 35), ("泰国", 25)):
        actual = scalar(cur, "SELECT COUNT(1) FROM biz_sku WHERE origin_country = %s", oc)
        if actual != cnt:
            errors.append("原产国 %s 为 %s != %s" % (oc, actual, cnt))
    if scalar(cur, "SELECT COUNT(1) FROM biz_sku WHERE sale_price < cost_price * 1.5 OR sale_price > cost_price * 3"):
        errors.append("存在售价不在成本价 1.6~2.8 倍区间的 SKU")
    if scalar(cur, "SELECT COUNT(1) FROM biz_sku WHERE product_name LIKE '%测试%' OR product_name LIKE '%示例%' "
                   "OR product_name REGEXP '商品[0-9]'"):
        errors.append("商品名称存在占位词")

    # 订单
    if scalar(cur, "SELECT COUNT(DISTINCT order_no) FROM biz_order") != 1500:
        errors.append("订单号不唯一")
    for st, cnt in STATUS_PLAN:
        actual = scalar(cur, "SELECT COUNT(1) FROM biz_order WHERE status = %s", st)
        if actual != cnt:
            errors.append("订单状态 %s 为 %s != %s" % (st, actual, cnt))
    for p, cnt, _dept, _owners in PLATFORMS:
        actual = scalar(cur, "SELECT COUNT(1) FROM biz_order WHERE platform = %s", p)
        if actual != cnt:
            errors.append("平台 %s 为 %s != %s" % (p, actual, cnt))
    if scalar(cur, "SELECT COUNT(1) FROM biz_order WHERE status = '待付款' AND "
                   "(pay_time IS NOT NULL OR ship_time IS NOT NULL OR finish_time IS NOT NULL)"):
        errors.append("待付款订单存在付款/发货/完成时间")
    if scalar(cur, "SELECT COUNT(1) FROM biz_order WHERE status = '已取消' AND "
                   "(pay_time IS NOT NULL OR ship_time IS NOT NULL OR finish_time IS NOT NULL)"):
        errors.append("已取消订单存在时间字段")
    if scalar(cur, "SELECT COUNT(1) FROM biz_order WHERE status = '待发货' AND "
                   "(pay_time IS NULL OR ship_time IS NOT NULL OR finish_time IS NOT NULL)"):
        errors.append("待发货订单字段不合规")
    if scalar(cur, "SELECT COUNT(1) FROM biz_order WHERE status = '退款中' AND "
                   "(pay_time IS NULL OR ship_time IS NOT NULL OR finish_time IS NOT NULL)"):
        errors.append("退款中订单字段不合规")
    if scalar(cur, "SELECT COUNT(1) FROM biz_order WHERE status = '已发货' AND "
                   "(pay_time IS NULL OR ship_time IS NULL OR finish_time IS NOT NULL)"):
        errors.append("已发货订单字段不合规")
    if scalar(cur, "SELECT COUNT(1) FROM biz_order WHERE status = '已完成' AND "
                   "(pay_time IS NULL OR ship_time IS NULL OR finish_time IS NULL)"):
        errors.append("已完成订单字段不全")
    for cond, msg in (
            ("pay_time < create_time", "付款时间早于下单时间"),
            ("ship_time < pay_time", "发货时间早于付款时间"),
            ("finish_time < ship_time", "完成时间早于发货时间")):
        if scalar(cur, "SELECT COUNT(1) FROM biz_order WHERE " + cond):
            errors.append("存在" + msg)
    if scalar(cur, "SELECT COUNT(1) FROM biz_order WHERE sales_dept_id NOT IN (120,121,122)"):
        errors.append("销售部门超出 120/121/122")
    if scalar(cur, "SELECT COUNT(1) FROM biz_order WHERE create_time < '2025-11-01' OR create_time > NOW()"):
        errors.append("订单下单时间超出近 12 个月或存在未来时间")
    if scalar(cur, "SELECT COUNT(1) FROM biz_order WHERE order_amount <= 0"):
        errors.append("订单金额存在非正值")

    # 库存
    if scalar(cur, "SELECT COUNT(DISTINCT sku_code) FROM biz_inventory") != 400:
        errors.append("库存 SKU 不唯一或不是 400 个")
    if scalar(cur, "SELECT COUNT(1) FROM biz_inventory i LEFT JOIN biz_sku s ON s.sku_code = i.sku_code "
                   "WHERE s.sku_id IS NULL"):
        errors.append("库存存在表外 SKU")
    if scalar(cur, "SELECT COUNT(1) FROM biz_inventory WHERE available_qty <> total_qty - locked_qty"):
        errors.append("可用库存不等于总量减锁定")
    if scalar(cur, "SELECT COUNT(1) FROM biz_inventory WHERE locked_qty > total_qty"):
        errors.append("锁定库存大于总量")
    if scalar(cur, "SELECT COUNT(1) FROM biz_inventory WHERE status = '缺货' AND (total_qty <> 0 OR available_qty <> 0)"):
        errors.append("缺货库存数量不为 0")
    if scalar(cur, "SELECT COUNT(1) FROM biz_inventory WHERE status = '预警' AND available_qty >= safety_qty"):
        errors.append("预警库存可用量不小于安全库存")
    if scalar(cur, "SELECT COUNT(1) FROM biz_inventory WHERE status = '正常' AND available_qty < safety_qty"):
        errors.append("正常库存可用量小于安全库存")
    for st, cnt in (("正常", 300), ("预警", 70), ("缺货", 30)):
        actual = scalar(cur, "SELECT COUNT(1) FROM biz_inventory WHERE status = %s", st)
        if actual != cnt:
            errors.append("库存状态 %s 为 %s != %s" % (st, actual, cnt))
    for wh, cnt in (("深圳仓", 220), ("东莞仓", 180)):
        actual = scalar(cur, "SELECT COUNT(1) FROM biz_inventory WHERE warehouse = %s", wh)
        if actual != cnt:
            errors.append("仓库 %s 为 %s != %s" % (wh, actual, cnt))

    # 物流单
    if scalar(cur, "SELECT COUNT(DISTINCT shipment_no) FROM biz_shipment") != 1200:
        errors.append("物流单号不唯一")
    if scalar(cur, "SELECT COUNT(DISTINCT tracking_no) FROM biz_shipment") != 1200:
        errors.append("运单号不唯一")
    if scalar(cur, "SELECT COUNT(1) FROM biz_shipment s LEFT JOIN biz_order o ON o.order_no = s.order_no "
                   "WHERE o.order_id IS NULL"):
        errors.append("物流单存在表外订单")
    if scalar(cur, "SELECT COUNT(1) FROM biz_shipment s JOIN biz_order o ON o.order_no = s.order_no "
                   "WHERE o.status NOT IN ('已发货','已完成')"):
        errors.append("物流单关联了非发货/完成订单")
    if scalar(cur, "SELECT COUNT(1) FROM biz_shipment s JOIN biz_order o ON o.order_no = s.order_no "
                   "WHERE s.dest_country <> o.country"):
        errors.append("物流单目的国与订单不一致")
    if scalar(cur, "SELECT COUNT(1) FROM biz_shipment WHERE ship_date < "
                   "(SELECT DATE(o.pay_time) FROM biz_order o WHERE o.order_no = biz_shipment.order_no)"):
        errors.append("物流单发货日期早于订单付款日期")
    if scalar(cur, "SELECT COUNT(1) FROM biz_shipment WHERE status = '已签收' AND delivered_date IS NULL"):
        errors.append("已签收物流单缺少签收日期")
    if scalar(cur, "SELECT COUNT(1) FROM biz_shipment WHERE status <> '已签收' AND delivered_date IS NOT NULL"):
        errors.append("未签收物流单存在签收日期")
    if scalar(cur, "SELECT COUNT(1) FROM biz_shipment WHERE delivered_date IS NOT NULL AND delivered_date < ship_date"):
        errors.append("签收日期早于发货日期")
    if scalar(cur, "SELECT COUNT(1) FROM biz_shipment s JOIN biz_order o ON o.order_no = s.order_no "
                   "WHERE o.status = '已完成' AND s.status <> '已签收'"):
        errors.append("已完成订单存在未签收物流单")
    if scalar(cur, "SELECT COUNT(1) FROM (SELECT order_no FROM biz_shipment GROUP BY order_no "
                   "HAVING COUNT(1) > 2) t"):
        errors.append("单个订单物流单超过 2 条")

    # 组织架构与账号
    if scalar(cur, "SELECT COUNT(1) FROM sys_dept WHERE dept_id BETWEEN 100 AND 134") != 23:
        errors.append("部门节点数不是 23")
    if scalar(cur, "SELECT COUNT(1) FROM sys_dept WHERE dept_id BETWEEN 100 AND 134 AND status = '0'") != 23:
        errors.append("存在非正常状态部门")
    if scalar(cur, "SELECT COUNT(1) FROM sys_dept d WHERE d.parent_id <> 0 AND NOT EXISTS "
                   "(SELECT 1 FROM sys_dept p WHERE p.dept_id = d.parent_id)") != 0:
        errors.append("存在父部门缺失的节点")
    if scalar(cur, "SELECT COUNT(1) FROM sys_dept WHERE dept_id = 125 AND ancestors = '0,100,112'") != 1:
        errors.append("125 部门 ancestors 不正确")
    if scalar(cur, "SELECT COUNT(1) FROM sys_user") != 32:
        errors.append("用户数不是 32（admin + scanner_low + 30 员工）")
    if scalar(cur, "SELECT dept_id FROM sys_user WHERE user_id = 100") != 134:
        errors.append("scanner_low 部门不是 134")
    if scalar(cur, "SELECT COUNT(1) FROM sys_user WHERE user_id = 100 AND status = '0' "
                   "AND password = '$2b$12$6qT3a.r2NqDYLSLZKXhTY.bu91Ce3A0Jco2OIBXSZC/n8f7ICGKh6'") != 1:
        errors.append("scanner_low 账号关键字段被改动")
    if scalar(cur, "SELECT COUNT(1) FROM sys_user WHERE user_id = 2") != 0:
        errors.append("ry 账号未删除")
    if scalar(cur, "SELECT COUNT(1) FROM sys_role_menu WHERE role_id = 99") != 5:
        errors.append("role_id=99 授权数发生变化")
    if scalar(cur, "SELECT COUNT(1) FROM sys_role_menu WHERE role_id = 1") != 8:
        errors.append("role_id=1 新业务菜单授权数不是 8")
    if scalar(cur, "SELECT COUNT(1) FROM sys_menu WHERE menu_id BETWEEN 2000 AND 2022") != 8:
        errors.append("新业务菜单不是 8 条")
    if scalar(cur, "SELECT COUNT(1) FROM sys_menu WHERE menu_name LIKE '%若依%' OR perms LIKE '%ruoyi%'") != 0:
        errors.append("菜单仍存在品牌字样")
    if scalar(cur, "SELECT COUNT(1) FROM sys_dept WHERE dept_name LIKE '%若依%'") != 0:
        errors.append("部门仍存在品牌字样")
    if scalar(cur, "SELECT COUNT(1) FROM sys_user WHERE nick_name LIKE '%若依%'") != 0:
        errors.append("用户昵称仍存在品牌字样")
    if scalar(cur, "SELECT COUNT(1) FROM sys_user WHERE user_id BETWEEN 2001 AND 2030 AND "
                   "password <> '$2a$10$7JB720yubVSZvUI0rEqK/.VqGOZTH.ulu33dHOiBE8ByOhJIrdAu2'") != 0:
        errors.append("员工口令哈希不一致")
    if scalar(cur, "SELECT COUNT(1) FROM sys_user WHERE user_id BETWEEN 2001 AND 2030 AND "
                   "pwd_update_date < DATE_SUB(NOW(), INTERVAL 90 DAY)") != 0:
        errors.append("员工密码更新时间超过 90 天")

    # 日志
    if scalar(cur, "SELECT COUNT(1) FROM sys_logininfor") < 200:
        errors.append("登录日志不足 200 条")
    if scalar(cur, "SELECT COUNT(1) FROM sys_oper_log") < 300:
        errors.append("操作日志不足 300 条")
    if scalar(cur, "SELECT COUNT(1) FROM sys_logininfor WHERE login_time < DATE_SUB(NOW(), INTERVAL 30 DAY)") != 0:
        errors.append("登录日志超出近 30 天")
    if scalar(cur, "SELECT COUNT(1) FROM sys_oper_log WHERE oper_time < DATE_SUB(NOW(), INTERVAL 30 DAY)") != 0:
        errors.append("操作日志超出近 30 天")
    weekend = scalar(cur, "SELECT COUNT(1) FROM sys_logininfor WHERE DAYOFWEEK(login_time) IN (1, 7)")
    total = scalar(cur, "SELECT COUNT(1) FROM sys_logininfor")
    ratio = weekend * 100.0 / total
    if ratio > 12:
        errors.append("登录日志周末占比 %.1f%% 超过 12%%" % ratio)

    for t, col in TIME_CHECK:
        n = scalar(cur, "SELECT COUNT(1) FROM %s WHERE %s > NOW()" % (t, col))
        if n:
            errors.append("NO_FUTURE 违规：%s.%s 有 %s 行" % (t, col, n))

    cur.execute("SELECT status, COUNT(1) FROM biz_order GROUP BY status")
    print("\n订单状态分布：")
    for r in cur.fetchall():
        print("  %-4s %s" % (r[0], r[1]))

    cur.execute("SELECT status, COUNT(1) FROM biz_inventory GROUP BY status")
    print("\n库存状态分布：")
    for r in cur.fetchall():
        print("  %-4s %s" % (r[0], r[1]))

    cur.execute("SELECT platform, COUNT(1) FROM biz_order GROUP BY platform ORDER BY COUNT(1) DESC")
    print("\n平台分布：")
    for r in cur.fetchall():
        print("  %-12s %s" % (r[0], r[1]))

    cur.execute("SELECT DATE_FORMAT(login_time, '%Y-%m') m, COUNT(1) FROM sys_logininfor GROUP BY m ORDER BY m")
    print("\n登录日志月份分布：")
    for r in cur.fetchall():
        print("  %s  %s" % (r[0], r[1]))
    print("\n周末登录占比：%.1f%%" % ratio)

    print("\nrole_id=1 业务菜单授权：%s 条" % scalar(cur, "SELECT COUNT(1) FROM sys_role_menu WHERE role_id = 1"))
    print("role_id=99 授权：%s 条" % scalar(cur, "SELECT COUNT(1) FROM sys_role_menu WHERE role_id = 99"))
    print("SQL 文件：%s" % SQL_FILE)

    if errors:
        print("\n[FAIL] 校验未通过：")
        for e in errors:
            print("  - " + e)
        raise AssertionError("；".join(errors))
    print("\n[OK] 行数、状态分布、时间巡检、账号与授权全部通过")


if __name__ == "__main__":
    main()
