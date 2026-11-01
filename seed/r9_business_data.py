#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R9 华电巡检管理系统 —— 业务表 + 演示数据种子脚本
=================================================
目标库：MySQL 127.0.0.1:13307 / ry_r9
说明：
  1. 仅创建/重建 insp_ 前缀的 4 张业务表，并写入字典、设备、计划、记录、缺陷、日志、公告；
  2. 可重复执行（先 DROP TABLE IF EXISTS，再重建；字典/公告先按业务键清理）；
  3. 生成 SQL 后通过 pymysql 执行，同时把完整 SQL 落盘到 seed/r9_business_data.sql 便于核查。

用法：python seed/r9_business_data.py
"""
import datetime as dt
import json
import os
import random

import pymysql
from pymysql.converters import escape_string

DB = dict(host="127.0.0.1", port=13307, user="root", password="", database="ry_r9", charset="utf8mb4")

TODAY = dt.date.today()
NOW = dt.datetime.now().replace(microsecond=0)
YEAR = TODAY.year
SEED = 20261029
random.seed(SEED)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SQL_FILE = os.path.join(BASE_DIR, "r9_business_data.sql")

# ----------------------------------------------------------------------------
# 基础字典
# ----------------------------------------------------------------------------
TENANT = "000000"

DEPT_NAME = {
    1000: "华电石家庄热电有限公司", 1001: "总经理办公室", 1002: "安全监察部",
    1003: "生产技术部", 1004: "运行部", 1005: "检修部", 1006: "燃料部",
    1007: "计划经营部", 1008: "财务部", 1009: "人力资源部",
    100401: "集控运行一值", 100402: "集控运行二值", 100403: "集控运行三值",
    100404: "化学运行班", 100405: "除灰运行班",
    100501: "汽机检修班", 100502: "锅炉检修班", 100503: "电气检修班",
    100504: "热控检修班", 100505: "综合检修班",
    100601: "输煤运行班", 100602: "煤场管理班",
}

# 巡检员角色（201）用户：user_id -> (账号, 姓名, 部门)
INSPECTORS = {
    2007: ("HD2007", "周文斌", 100401), 2008: ("HD2008", "吴晓东", 100401),
    2009: ("HD2009", "孙红梅", 100402), 2010: ("HD2010", "马晓丽", 100402),
    2011: ("HD2011", "朱建华", 100403), 2012: ("HD2012", "胡俊", 100403),
    2013: ("HD2013", "郭永强", 100404), 2014: ("HD2014", "何丽娟", 100404),
    2015: ("HD2015", "高峰", 100405),
    2017: ("HD2017", "罗军", 100501), 2018: ("HD2018", "郑海龙", 100501),
    2019: ("HD2019", "梁伟东", 100502), 2020: ("HD2020", "谢婷婷", 100502),
    2021: ("HD2021", "唐志刚", 100503), 2022: ("HD2022", "许文静", 100503),
    2023: ("HD2023", "韩磊", 100504), 2024: ("HD2024", "曹建平", 100504),
    2025: ("HD2025", "彭勇", 100505),
    2027: ("HD2027", "袁华", 100601), 2028: ("HD2028", "蒋伟", 100601),
    2029: ("HD2029", "杜文杰", 100602),
}

# 全部员工（含管理岗），用于登录日志
EMPLOYEES = dict(INSPECTORS)
EMPLOYEES.update({
    2001: ("HD2001", "王建国", 1001), 2002: ("HD2002", "张伟", 1002),
    2003: ("HD2003", "刘志强", 1002), 2004: ("HD2004", "陈国华", 1003),
    2005: ("HD2005", "杨海涛", 1003), 2006: ("HD2006", "赵鹏", 1004),
    2016: ("HD2016", "林小燕", 1005), 2026: ("HD2026", "董雪梅", 1006),
    2030: ("HD2030", "苏婉清", 1007), 2031: ("HD2031", "卢建华", 1008),
    2032: ("HD2032", "常丽", 1009),
})

# 设备检修/消缺责任人：按设备归属班组
ASSIGNEE = {
    100501: [2017, 2018], 100502: [2019, 2020], 100503: [2021, 2022],
    100504: [2023, 2024], 100601: [2027, 2028], 100505: [2025],
}

DEVICE_TYPE_NAME = {
    "01": "锅炉", "02": "汽轮机", "03": "发电机", "04": "变压器", "05": "给水泵",
    "06": "风机", "07": "磨煤机", "08": "换热设备", "09": "输煤设备", "10": "环保设备",
}
EXPECT_TYPE_COUNT = {"01": 2, "02": 2, "03": 2, "04": 8, "05": 6,
                     "06": 10, "07": 6, "08": 8, "09": 12, "10": 12}
CYCLE_DAYS = {"01": 1, "02": 1, "03": 1, "04": 1, "05": 7, "06": 7,
              "07": 7, "08": 30, "09": 30, "10": 30}


def q(v):
    """SQL 字面量。"""
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


def at(d, h, m=0, s=0):
    return dt.datetime.combine(d, dt.time(h, m, s))


def rand_dt(day, h1, h2):
    """当天 [h1,h2) 内的随机时间。"""
    return at(day, h1, 0) + dt.timedelta(minutes=random.randrange((h2 - h1) * 60))


# ----------------------------------------------------------------------------
# DDL
# ----------------------------------------------------------------------------
DDL = [
    "DROP TABLE IF EXISTS insp_device",
    """CREATE TABLE insp_device (
  device_id bigint(20) NOT NULL AUTO_INCREMENT COMMENT '设备ID',
  device_code varchar(64) NOT NULL COMMENT '设备编码',
  device_name varchar(100) NOT NULL COMMENT '设备名称',
  device_type char(2) NOT NULL COMMENT '设备类型（字典 insp_device_type）',
  model varchar(100) DEFAULT NULL COMMENT '规格型号',
  manufacturer varchar(100) DEFAULT NULL COMMENT '制造厂家',
  dept_id bigint(20) DEFAULT NULL COMMENT '所属班组',
  location varchar(200) DEFAULT NULL COMMENT '安装位置',
  install_date date DEFAULT NULL COMMENT '投运日期',
  status char(1) DEFAULT '0' COMMENT '状态（0运行 1备用 2检修 3停运）',
  rated_param varchar(200) DEFAULT NULL COMMENT '额定参数',
  last_inspect_time datetime DEFAULT NULL COMMENT '最近巡检时间',
  next_inspect_time datetime DEFAULT NULL COMMENT '下次巡检时间',
  remark varchar(500) DEFAULT NULL COMMENT '备注',
  tenant_id varchar(20) DEFAULT '000000' COMMENT '租户编号',
  create_dept bigint(20) DEFAULT NULL COMMENT '创建部门',
  create_by bigint(20) DEFAULT NULL COMMENT '创建者',
  create_time datetime DEFAULT NULL COMMENT '创建时间',
  update_by bigint(20) DEFAULT NULL COMMENT '更新者',
  update_time datetime DEFAULT NULL COMMENT '更新时间',
  del_flag char(1) DEFAULT '0' COMMENT '删除标志（0存在 1删除）',
  PRIMARY KEY (device_id),
  UNIQUE KEY uk_insp_device_code (device_code),
  KEY idx_insp_device_type (device_type),
  KEY idx_insp_device_dept (dept_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='设备台账'""",
    "DROP TABLE IF EXISTS insp_plan",
    """CREATE TABLE insp_plan (
  plan_id bigint(20) NOT NULL AUTO_INCREMENT COMMENT '计划ID',
  plan_code varchar(64) NOT NULL COMMENT '计划编码',
  plan_name varchar(100) NOT NULL COMMENT '计划名称',
  device_type char(2) NOT NULL COMMENT '设备类型（字典 insp_device_type）',
  inspect_cycle char(1) NOT NULL COMMENT '巡检周期（1日检 2周检 3月检）',
  inspector_id bigint(20) DEFAULT NULL COMMENT '巡检员',
  start_date date DEFAULT NULL COMMENT '开始日期',
  end_date date DEFAULT NULL COMMENT '结束日期',
  status char(1) DEFAULT '0' COMMENT '状态（0草稿 1执行中 2已结束）',
  inspect_items text COMMENT '巡检项清单（JSON数组）',
  remark varchar(500) DEFAULT NULL COMMENT '备注',
  tenant_id varchar(20) DEFAULT '000000' COMMENT '租户编号',
  create_dept bigint(20) DEFAULT NULL COMMENT '创建部门',
  create_by bigint(20) DEFAULT NULL COMMENT '创建者',
  create_time datetime DEFAULT NULL COMMENT '创建时间',
  update_by bigint(20) DEFAULT NULL COMMENT '更新者',
  update_time datetime DEFAULT NULL COMMENT '更新时间',
  del_flag char(1) DEFAULT '0' COMMENT '删除标志（0存在 1删除）',
  PRIMARY KEY (plan_id),
  UNIQUE KEY uk_insp_plan_code (plan_code),
  KEY idx_insp_plan_type (device_type),
  KEY idx_insp_plan_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='巡检计划'""",
    "DROP TABLE IF EXISTS insp_record",
    """CREATE TABLE insp_record (
  record_id bigint(20) NOT NULL AUTO_INCREMENT COMMENT '记录ID',
  record_code varchar(64) NOT NULL COMMENT '记录编码',
  plan_id bigint(20) DEFAULT NULL COMMENT '巡检计划ID',
  device_id bigint(20) NOT NULL COMMENT '设备ID',
  inspector_id bigint(20) DEFAULT NULL COMMENT '巡检员',
  inspect_time datetime NOT NULL COMMENT '巡检时间',
  result char(1) DEFAULT '0' COMMENT '巡检结果（0正常 1异常）',
  item_count int DEFAULT 0 COMMENT '巡检项数',
  abnormal_count int DEFAULT 0 COMMENT '异常项数',
  duration_min int DEFAULT 0 COMMENT '耗时（分钟）',
  remark varchar(500) DEFAULT NULL COMMENT '备注',
  tenant_id varchar(20) DEFAULT '000000' COMMENT '租户编号',
  create_dept bigint(20) DEFAULT NULL COMMENT '创建部门',
  create_by bigint(20) DEFAULT NULL COMMENT '创建者',
  create_time datetime DEFAULT NULL COMMENT '创建时间',
  update_by bigint(20) DEFAULT NULL COMMENT '更新者',
  update_time datetime DEFAULT NULL COMMENT '更新时间',
  del_flag char(1) DEFAULT '0' COMMENT '删除标志（0存在 1删除）',
  PRIMARY KEY (record_id),
  UNIQUE KEY uk_insp_record_code (record_code),
  KEY idx_insp_record_device (device_id),
  KEY idx_insp_record_inspector (inspector_id),
  KEY idx_insp_record_time (inspect_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='巡检记录'""",
    "DROP TABLE IF EXISTS insp_defect",
    """CREATE TABLE insp_defect (
  defect_id bigint(20) NOT NULL AUTO_INCREMENT COMMENT '缺陷ID',
  defect_code varchar(64) NOT NULL COMMENT '缺陷编码',
  device_id bigint(20) NOT NULL COMMENT '设备ID',
  title varchar(200) NOT NULL COMMENT '缺陷标题',
  level char(1) DEFAULT '1' COMMENT '缺陷等级（1一般 2重要 3紧急）',
  description varchar(1000) DEFAULT NULL COMMENT '缺陷描述',
  discoverer_id bigint(20) DEFAULT NULL COMMENT '发现人',
  discover_time datetime DEFAULT NULL COMMENT '发现时间',
  assignee_id bigint(20) DEFAULT NULL COMMENT '处理人',
  status char(1) DEFAULT '0' COMMENT '工单状态（0待处理 1处理中 2已闭环）',
  handle_desc varchar(1000) DEFAULT NULL COMMENT '处理说明',
  handle_time datetime DEFAULT NULL COMMENT '开始处理时间',
  close_time datetime DEFAULT NULL COMMENT '闭环时间',
  tenant_id varchar(20) DEFAULT '000000' COMMENT '租户编号',
  create_dept bigint(20) DEFAULT NULL COMMENT '创建部门',
  create_by bigint(20) DEFAULT NULL COMMENT '创建者',
  create_time datetime DEFAULT NULL COMMENT '创建时间',
  update_by bigint(20) DEFAULT NULL COMMENT '更新者',
  update_time datetime DEFAULT NULL COMMENT '更新时间',
  del_flag char(1) DEFAULT '0' COMMENT '删除标志（0存在 1删除）',
  PRIMARY KEY (defect_id),
  UNIQUE KEY uk_insp_defect_code (defect_code),
  KEY idx_insp_defect_device (device_id),
  KEY idx_insp_defect_status (status),
  KEY idx_insp_defect_time (discover_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='缺陷工单'""",
]

# ----------------------------------------------------------------------------
# 设备台账
# ----------------------------------------------------------------------------
DEVICE_DEFS = []


def dev(t, name, model, mfr, dept, loc, install, status, rated):
    DEVICE_DEFS.append((t, name, model, mfr, dept, loc, install, status, rated))


# 01 锅炉
dev("01", "#1锅炉", "HG-1025/17.5-YM", "东方锅炉股份有限公司", 100502,
    "#1机组锅炉房0米层", "2016-03-15", "0", "1025t/h 17.5MPa 540℃")
dev("01", "#2锅炉", "HG-1025/17.5-YM", "东方锅炉股份有限公司", 100502,
    "#2机组锅炉房0米层", "2016-09-20", "2", "1025t/h 17.5MPa 540℃")
# 02 汽轮机
dev("02", "#1汽轮机", "N300-16.7/538/538", "上海汽轮机厂有限公司", 100501,
    "#1机组汽机房12.6米层", "2016-03-15", "0", "300MW 16.7MPa 538℃/538℃")
dev("02", "#2汽轮机", "N300-16.7/538/538", "上海汽轮机厂有限公司", 100501,
    "#2机组汽机房12.6米层", "2016-09-20", "2", "300MW 16.7MPa 538℃/538℃")
# 03 发电机
dev("03", "#1发电机", "QFSN-300-2", "上海电机厂有限公司", 100503,
    "#1机组发电机平台12.6米层", "2016-04-10", "0", "300MW 20kV 50Hz")
dev("03", "#2发电机", "QFSN-300-2", "上海电机厂有限公司", 100503,
    "#2机组发电机平台12.6米层", "2016-10-05", "2", "300MW 20kV 50Hz")
# 04 变压器
dev("04", "主变#1", "SFP10-370000/220", "特变电工股份有限公司", 100503,
    "220kV升压站主变间隔", "2016-02-20", "0", "370MVA 220/20kV")
dev("04", "主变#2", "SFP10-370000/220", "特变电工股份有限公司", 100503,
    "220kV升压站主变间隔", "2016-08-15", "0", "370MVA 220/20kV")
dev("04", "厂用变#1", "SCB10-2000/20", "顺特电气设备有限公司", 100503,
    "#1机组厂用配电室", "2016-05-10", "0", "2000kVA 20/6kV")
dev("04", "厂用变#2", "SCB10-2000/20", "顺特电气设备有限公司", 100503,
    "#2机组厂用配电室", "2016-05-10", "0", "2000kVA 20/6kV")
dev("04", "厂用变#3", "SCB10-2000/20", "顺特电气设备有限公司", 100503,
    "#1机组厂用配电室", "2017-03-12", "1", "2000kVA 20/6kV")
dev("04", "厂用变#4", "SCB10-2000/20", "顺特电气设备有限公司", 100503,
    "#2机组厂用配电室", "2017-03-12", "1", "2000kVA 20/6kV")
dev("04", "启备变#1", "SFFZ10-40000/220", "西安西电变压器有限责任公司", 100503,
    "220kV升压站启备变区域", "2016-02-20", "1", "40000kVA 220/6kV")
dev("04", "启备变#2", "SFFZ10-40000/220", "西安西电变压器有限责任公司", 100503,
    "220kV升压站启备变区域", "2016-02-20", "0", "40000kVA 220/6kV")
# 05 给水泵
for unit, day, st_c in ((1, "2016-04-01", "1"), (2, "2016-10-10", "2")):
    for suffix, st in (("A", "0"), ("B", "0"), ("C", st_c)):
        dev("05", f"#%d机组给水泵%s" % (unit, suffix), "DG600-240", "上海电力修造总厂有限公司",
            100501, f"#{unit}机组汽机房0米层", day, st, "600t/h 24MPa 2980r/min")
# 06 风机
for unit, day in ((1, "2016-03-25"), (2, "2016-09-28")):
    for kind, pos, st_b in (("送风机", "送风机房", "1" if unit == 2 else "0"),
                            ("引风机", "引风机区域", "1" if unit == 2 else "0")):
        for suffix in ("A", "B"):
            st = st_b if suffix == "B" else "0"
            dev("06", f"#{unit}机组{kind}{suffix}", "FAF26.6-14-1", "上海鼓风机厂有限公司",
                100502, f"#{unit}机组{pos}", day, st, "1200000m³/h 1480r/min")
dev("06", "增压风机#1", "FAF26.6-14-1", "上海鼓风机厂有限公司", 100505,
    "脱硫增压风机房", "2017-06-18", "0", "900000m³/h 990r/min")
dev("06", "增压风机#2", "FAF26.6-14-1", "上海鼓风机厂有限公司", 100505,
    "脱硫增压风机房", "2017-06-18", "1", "900000m³/h 990r/min")
# 07 磨煤机
for i in range(1, 7):
    unit = 1 if i <= 3 else 2
    dev("07", f"#{i}磨煤机", "ZGM113G", "北京电力设备总厂有限公司", 100502,
        f"#{unit}机组锅炉房磨煤机层", "2016-05-08" if unit == 1 else "2016-11-12",
        "1" if i >= 5 else "0", "75t/h 380V")
# 08 换热设备
for i in (1, 2):
    dev("08", f"除氧器#{i}", "GC-1080/25", "上海动力设备有限公司", 100501,
        f"#{i}机组汽机房0米层", "2016-04-20" if i == 1 else "2016-10-22", "0",
        "1080t/h 0.49MPa 158℃")
for i in (1, 2):
    dev("08", f"凝汽器#{i}", "N-17000-1", "哈尔滨汽轮机厂有限责任公司", 100501,
        f"#{i}机组汽机房0米层", "2016-04-20" if i == 1 else "2016-10-22", "0",
        "17000m² 0.0049MPa")
for i in range(1, 5):
    unit = 1 if i <= 2 else 2
    dev("08", f"高加#{i}", "JG-1100-1", "上海动力设备有限公司", 100501,
        f"#{unit}机组汽机房12.6米层", "2016-06-15" if unit == 1 else "2016-12-18", "0",
        "1100m² 25MPa 275℃")
# 09 输煤设备
for i in range(1, 7):
    st = "3" if i == 6 else "0"
    dev("09", f"输煤皮带#{i}", "DTII-1200", "河北输送机械有限公司", 100601,
        f"输煤栈桥#{i}段", "2016-07-10", st, "1200mm 1500t/h")
for i in (1, 2):
    dev("09", f"斗轮机#{i}", "DQ1500/1500·35", "长春发电设备总厂", 100601,
        f"煤场#{i}号斗轮机轨道", "2016-08-05", "0", "1500t/h 35m")
for i in (1, 2):
    dev("09", f"翻车机#{i}", "FZ15-100", "大连重工装备集团有限公司", 100601,
        f"翻车机室#{i}号位", "2016-07-28", "0", "100t/辆 1500t/h")
for i in (1, 2):
    dev("09", f"碎煤机#{i}", "KRC12×21", "沈阳重型机械集团有限公司", 100601,
        f"输煤综合楼#{i}号碎煤机", "2016-08-18", "3" if i == 2 else "0", "800t/h")
# 10 环保设备
dev("10", "脱硫塔#1", "FGD-2×300MW", "北京国电龙源环保工程有限公司", 100505,
    "脱硫区域#1吸收塔", "2017-05-20", "0", "2×300MW 脱硫效率95%")
dev("10", "脱硫塔#2", "FGD-2×300MW", "北京国电龙源环保工程有限公司", 100505,
    "脱硫区域#2吸收塔", "2017-05-20", "2", "2×300MW 脱硫效率95%")
for i in (1, 2):
    dev("10", f"脱硝装置#{i}", "SCR-2×300MW", "东方电气集团东方锅炉股份有限公司", 100504,
        f"#{i}机组脱硝反应器区", "2017-06-10", "0", "NOx≤50mg/m³ 脱硝效率85%")
for i in range(1, 5):
    unit = 1 if i <= 2 else 2
    dev("10", f"电除尘#{i}", "2FAA-240", "浙江菲达环保科技股份有限公司", 100505,
        f"#{unit}机组电除尘区域", "2016-12-08", "0", "240m² 除尘效率99.8%")
for i in range(1, 5):
    unit = 1 if i <= 2 else 2
    dev("10", f"石膏脱水机#{i}", "DU-30m²/2500", "上海环保设备总厂", 100505,
        f"#{unit}机组石膏脱水间", "2017-07-15", "0", "30m² 25t/h")

assert len(DEVICE_DEFS) == 68, len(DEVICE_DEFS)


def build_devices():
    seq = {k: 0 for k in EXPECT_TYPE_COUNT}
    rows = []
    for idx, (t, name, model, mfr, dept, loc, install, status, rated) in enumerate(DEVICE_DEFS, 1):
        seq[t] += 1
        rows.append(dict(
            device_id=idx,
            device_code="HD-SB-%s-%03d" % (t, seq[t]),
            device_name=name, device_type=t, model=model, manufacturer=mfr,
            dept_id=dept, location=loc, install_date=dt.date.fromisoformat(install),
            status=status, rated_param=rated, remark=None, tenant_id=TENANT,
            create_dept=dept, create_by=1,
            create_time=at(dt.date.fromisoformat(install), 9, 30),
            update_by=None, update_time=None, del_flag="0",
        ))
    for t, n in EXPECT_TYPE_COUNT.items():
        got = sum(1 for r in rows if r["device_type"] == t)
        assert got == n, (t, got, n)
    st = {s: sum(1 for r in rows if r["status"] == s) for s in "0123"}
    assert st == {"0": 52, "1": 9, "2": 5, "3": 2}, st
    return rows


# ----------------------------------------------------------------------------
# 巡检计划
# ----------------------------------------------------------------------------
PLAN_DEFS = [
    ("锅炉本体日检计划", "01", "1", 2019,
     ["汽包水位", "炉膛负压", "过热器壁温", "省煤器出口烟温", "磨煤机出力", "烟道漏风"]),
    ("汽轮机本体日检计划", "02", "1", 2017,
     ["轴承温度", "振动值", "油位", "密封状况", "异响"]),
    ("发电机及励磁系统日检计划", "03", "1", 2021,
     ["定子温度", "转子振动", "励磁电流", "碳刷磨损", "冷却风温"]),
    ("主变及厂用变日检计划", "04", "1", 2022,
     ["油位", "油温", "绕组温度", "接头测温", "呼吸器硅胶"]),
    ("给水泵组周检计划", "05", "2", 2018,
     ["轴承温度", "振动值", "机械密封", "润滑油压", "运行电流"]),
    ("风机系统周检计划", "06", "2", 2020,
     ["轴承温度", "振动值", "油位", "风门开度", "异响"]),
    ("磨煤机制粉系统周检计划", "07", "2", 2019,
     ["磨辊磨损", "液压油压", "分离器转速", "石子煤排量", "油温"]),
    ("换热设备周检计划", "08", "2", 2017,
     ["水位", "压力", "端差", "疏水阀", "保温状况"]),
    ("输煤系统月度巡检计划", "09", "3", 2027,
     ["皮带跑偏", "托辊转动", "清扫器", "拉绳开关", "落煤管堵塞"]),
    ("环保设施月度巡检计划", "10", "3", 2025,
     ["浆液pH值", "循环泵电流", "烟气含氧量", "石膏含水率", "CEMS数据"]),
    ("电气设备绝缘及红外测温月检", "04", "3", 2021,
     ["绝缘电阻", "红外测温", "接头温度", "接地电阻"]),
    ("锅炉承压部件月度检查", "01", "3", 2023,
     ["壁温", "膨胀指示", "支吊架", "人孔门", "吹灰器"]),
]


def build_plans():
    rows = []
    for i, (name, dtype, cycle, inspector, items) in enumerate(PLAN_DEFS, 1):
        if i <= 8:
            start, end, status = TODAY - dt.timedelta(days=300), TODAY + dt.timedelta(days=60), "1"
        elif i in (9, 10):
            start, end, status = TODAY - dt.timedelta(days=60), TODAY - dt.timedelta(days=1), "2"
        elif i == 11:
            start, end, status = TODAY - dt.timedelta(days=300), TODAY - dt.timedelta(days=10), "2"
        else:
            start, end, status = TODAY + dt.timedelta(days=3), TODAY + dt.timedelta(days=93), "0"
        rows.append(dict(
            plan_id=i, plan_code="XJ-JH-%d-%03d" % (YEAR, i), plan_name=name,
            device_type=dtype, inspect_cycle=cycle, inspector_id=inspector,
            start_date=start, end_date=end, status=status,
            inspect_items=json.dumps(items, ensure_ascii=False),
            remark=None, tenant_id=TENANT, create_dept=INSPECTORS[inspector][2],
            create_by=1, create_time=at(start, 10, 0) - dt.timedelta(days=2),
            update_by=None, update_time=None, del_flag="0",
        ))
    assert sum(1 for p in rows if p["inspect_cycle"] == "1") == 4
    assert sum(1 for p in rows if p["inspect_cycle"] == "2") == 4
    assert sum(1 for p in rows if p["inspect_cycle"] == "3") == 4
    assert sum(1 for p in rows if p["status"] == "1") == 8
    assert sum(1 for p in rows if p["status"] == "2") == 3
    return rows


# ----------------------------------------------------------------------------
# 巡检记录
# ----------------------------------------------------------------------------
def build_records(devices, plans):
    days = [TODAY - dt.timedelta(days=i) for i in range(29, -1, -1)]
    counts = []
    for d in days:
        lo, hi = (15, 18) if d.weekday() < 5 else (12, 14)
        counts.append(random.randint(lo, hi))
    diff = 450 - sum(counts)
    guard = 0
    while diff != 0 and guard < 10000:
        guard += 1
        i = random.randrange(len(days))
        d = days[i]
        lo, hi = (15, 18) if d.weekday() < 5 else (12, 14)
        if diff > 0 and counts[i] < hi:
            counts[i] += 1
            diff -= 1
        elif diff < 0 and counts[i] > lo:
            counts[i] -= 1
            diff += 1
    assert sum(counts) == 450, sum(counts)

    active = {t: [d for d in devices if d["device_type"] == t and d["status"] in ("0", "1")]
              for t in EXPECT_TYPE_COUNT}
    windows = ((8, 10), (14, 16), (20, 22))
    rows = []
    for d, n in zip(days, counts):
        seq = 0
        for _ in range(n):
            valid = [p for p in plans if p["status"] != "0" and p["start_date"] <= d <= p["end_date"]]
            weights = [{"1": 5, "2": 2, "3": 1}[p["inspect_cycle"]] for p in valid]
            plan = random.choices(valid, weights=weights)[0]
            pool = active[plan["device_type"]] or devices
            device = random.choice(pool)
            h1, h2 = random.choice(windows)
            t = rand_dt(d, h1, h2)
            if t > NOW - dt.timedelta(minutes=5):
                t = NOW - dt.timedelta(minutes=random.randint(15, 180))
                if t.date() != d:
                    t = at(d, 0, 10)
            seq += 1
            rows.append(dict(
                record_id=len(rows) + 1,
                record_code="XJ%s%04d" % (d.strftime("%Y%m%d"), seq),
                plan_id=plan["plan_id"], device_id=device["device_id"],
                inspector_id=plan["inspector_id"], inspect_time=t,
                result="0", item_count=random.randint(4, 6),
                abnormal_count=0, duration_min=random.randint(15, 60),
                remark=None, tenant_id=TENANT, create_dept=device["dept_id"],
                create_by=plan["inspector_id"], create_time=t + dt.timedelta(minutes=20),
                update_by=None, update_time=None, del_flag="0",
            ))

    # 45 条异常，今天保底 2 条
    today_idx = [i for i, r in enumerate(rows) if r["inspect_time"].date() == TODAY]
    chosen = random.sample(today_idx, 2) if len(today_idx) >= 2 else today_idx[:]
    rest = [i for i in range(len(rows)) if i not in chosen]
    chosen += random.sample(rest, 45 - len(chosen))
    assert len(chosen) == 45, len(chosen)
    for i in chosen:
        r = rows[i]
        r["result"] = "1"
        r["abnormal_count"] = random.randint(1, min(2, r["item_count"]))
        r["remark"] = random.choice([
            "巡检发现设备异常，已登记缺陷并通知检修处理。",
            "现场检查发现参数偏离，已汇报值长。",
            "发现渗漏现象，已做临时处理并列入缺陷。",
        ])
    for r in rows:
        if r["result"] == "0" and random.random() < 0.25:
            r["remark"] = random.choice(["设备运行正常，参数稳定。", "巡检未见异常。", "现场清洁，无异音。"])
    assert sum(1 for r in rows if r["result"] == "1") == 45
    assert sum(1 for r in rows if r["inspect_time"].date() == TODAY) >= 12
    return rows


# ----------------------------------------------------------------------------
# 缺陷工单
# ----------------------------------------------------------------------------
ISSUES = {
    "01": [("省煤器出口烟温偏高", "I"), ("炉膛负压波动大", "G"), ("过热器管壁温度超限", "U"),
           ("空预器漏风率偏高", "I"), ("汽包水位计显示偏差", "G"), ("燃烧器喷口结焦", "G"),
           ("尾部烟道积灰严重", "G"), ("再热汽温偏低", "I")],
    "02": [("#3轴承振动超标（0.12mm）", "U"), ("高压缸胀差异常", "I"), ("主汽门卡涩", "U"),
           ("凝汽器真空下降", "I"), ("润滑油温偏高", "G"), ("轴封供汽压力低", "G"),
           ("DEH调速系统响应迟缓", "I")],
    "03": [("定子线圈温度偏高", "I"), ("碳刷打火", "I"), ("励磁变温升异常", "U"),
           ("冷却风温高", "G"), ("氢气纯度下降", "I"), ("定子冷却水流量低", "I")],
    "04": [("油位计渗油", "I"), ("本体油色谱乙炔超标", "U"), ("高压侧接头过热", "I"),
           ("冷却风机故障", "G"), ("有载调压机构异响", "G"), ("呼吸器硅胶变色", "G"),
           ("本体渗油", "G")],
    "05": [("机械密封泄漏", "I"), ("推力轴承温度高", "I"), ("电流波动", "G"),
           ("润滑油压低", "U"), ("出口压力下降", "G"), ("联轴器振动偏大", "G")],
    "06": [("轴承振动偏大", "I"), ("液压油站压力低", "I"), ("电机温度高", "G"),
           ("风门执行器卡涩", "G"), ("动叶调节失灵", "I"), ("轴承箱漏油", "G")],
    "07": [("液压油站压力波动", "I"), ("磨辊磨损超标", "G"), ("石子煤排量增大", "G"),
           ("出口温度低", "G"), ("分离器转速异常", "G"), ("减速机异响", "I")],
    "08": [("高加水位异常", "G"), ("除氧器溶氧超标", "I"), ("凝汽器端差增大", "I"),
           ("疏水阀内漏", "G"), ("人孔门泄漏", "G"), ("保温层破损", "G")],
    "09": [("段跑偏保护频繁动作", "U"), ("段托辊转动异响", "G"), ("段清扫器损坏", "G"),
           ("段拉绳开关误动作", "I"), ("段落煤管堵塞", "G"), ("段驱动滚筒轴承温度高", "I"),
           ("段导料槽衬板磨损", "G")],
    "10": [("浆液循环泵电流异常", "U"), ("浆液pH值偏低", "I"), ("电场电流偏低", "I"),
           ("滤布跑偏", "G"), ("氨逃逸偏高", "I"), ("灰斗堵灰", "G"),
           ("石膏含水率偏高", "G"), ("氧化风机振动偏大", "G")],
}

DEFECT_COUNT = {"01": 4, "02": 5, "03": 4, "04": 8, "05": 6,
                "06": 8, "07": 6, "08": 7, "09": 12, "10": 12}
MUST_INCLUDE = {
    "01": ("#1锅炉", "省煤器出口烟温偏高"),
    "02": ("#2汽轮机", "#3轴承振动超标（0.12mm）"),
    "04": ("主变#1", "油位计渗油"),
    "07": ("#3磨煤机", "液压油站压力波动"),
    "09": ("输煤皮带#4", "段跑偏保护频繁动作"),
    "10": ("脱硫塔#2", "浆液循环泵电流异常"),
}
# 同一类型下不同设备家族的缺陷现象
FAMILY_ISSUES = {
    "08": {
        "除氧器": [("溶氧超标", "I"), ("水位异常", "G"), ("再热汽源压力低", "G"), ("人孔门泄漏", "G")],
        "凝汽器": [("端差增大", "I"), ("真空下降", "I"), ("胶球清洗装置故障", "G"), ("水室人孔泄漏", "G")],
        "高加": [("水位异常", "G"), ("疏水阀内漏", "G"), ("管束泄漏", "I"), ("保温层破损", "G")],
    },
    "09": {
        "输煤皮带": [("段跑偏保护频繁动作", "U"), ("段托辊转动异响", "G"), ("段清扫器损坏", "G"),
                     ("段拉绳开关误动作", "I"), ("段落煤管堵塞", "G"), ("段驱动滚筒轴承温度高", "I"),
                     ("段导料槽衬板磨损", "G")],
        "斗轮机": [("回转机构异响", "I"), ("悬臂皮带跑偏", "G"), ("液压系统渗油", "G"), ("斗轮驱动电流偏高", "G")],
        "翻车机": [("液压系统渗油", "G"), ("靠车板动作卡涩", "G"), ("重车调车机异响", "G"), ("定位装置不准", "G")],
        "碎煤机": [("轴承温度高", "I"), ("锤头磨损超标", "G"), ("振动超标", "I"), ("落煤管堵塞", "G")],
    },
    "10": {
        "脱硫塔": [("浆液循环泵电流异常", "U"), ("浆液pH值偏低", "I"), ("石膏含水率偏高", "G"),
                   ("氧化风机振动偏大", "G"), ("浆液密度异常", "G")],
        "脱硝装置": [("氨逃逸偏高", "I"), ("催化剂层差压高", "G"), ("喷氨格栅堵塞", "G"), ("NOx排放浓度超标", "I")],
        "电除尘": [("电场电流偏低", "I"), ("灰斗堵灰", "G"), ("极板积灰", "G"), ("振打装置故障", "G")],
        "石膏脱水机": [("滤布跑偏", "G"), ("石膏含水率偏高", "G"), ("真空度不足", "G"), ("滤饼厚度不均", "G")],
    },
}


def issue_pool(dtype, device_name):
    for prefix, pool in FAMILY_ISSUES.get(dtype, {}).items():
        if device_name.startswith(prefix):
            return pool
    return ISSUES[dtype]
HANDLE_BY_TYPE = {
    "01": "停运相关风烟系统，清理受热面积灰并调整燃烧，处理后参数恢复正常。",
    "02": "调整轴封供汽及润滑油温，复测振动合格；更换磨损部件后试运正常。",
    "03": "清理碳刷及滑环，调整励磁参数，红外测温确认无过热。",
    "04": "处理渗漏点并补油，进行油色谱复测，确认乙炔含量恢复正常。",
    "05": "更换机械密封及轴承，调整联轴器中心，试运电流、振动正常。",
    "06": "清洗轴承箱并更换润滑油，校正执行机构，风机试运正常。",
    "07": "更换磨辊套并调整液压系统压力，石子煤排量恢复正常。",
    "08": "清理换热面并调整水位，处理疏水阀内漏，端差恢复正常。",
    "09": "调整皮带跑偏、更换损坏托辊及清扫器，空载试运正常。",
    "10": "清理堵灰并调整浆液pH值，更换滤布，环保参数恢复达标。",
}


def build_defects(devices):
    by_type = {t: [d for d in devices if d["device_type"] == t] for t in EXPECT_TYPE_COUNT}
    combos = []
    for t, need in DEFECT_COUNT.items():
        devs = by_type[t]
        picked = []
        used = set()
        if t in MUST_INCLUDE:
            dn, it = MUST_INCLUDE[t]
            sev = dict(issue_pool(t, dn)).get(it, "I")
            picked.append((dn, it, sev))
            used.add((dn, it))
        i = 0
        while len(picked) < need:
            d = devs[i % len(devs)]
            pool = issue_pool(t, d["device_name"])
            it, sev = pool[(i * 3 + len(picked)) % len(pool)]
            key = (d["device_name"], it)
            if key not in used:
                picked.append((d["device_name"], it, sev))
                used.add(key)
            i += 1
        for name, it, sev in picked:
            device = next(x for x in devs if x["device_name"] == name)
            title = name + it
            if not name.startswith("输煤皮带") and it.startswith("段"):
                title = name + it[1:]
            if name == "主变#1" and it == "油位计渗油":
                title = "#1主变油位计渗油"
            combos.append(dict(device=device, issue=it, title=title, sev=sev))
    assert len(combos) == 72, len(combos)

    rank = {"U": 0, "I": 1, "G": 2}
    combos.sort(key=lambda c: rank[c["sev"]])
    for i, c in enumerate(combos):
        c["level"] = "3" if i < 6 else ("2" if i < 22 else "1")

    statuses = ["0"] * 8 + ["1"] * 4 + ["2"] * 60
    random.shuffle(statuses)
    pending_i = [i for i, s in enumerate(statuses) if s == "0"]
    today_pending = set(random.sample(pending_i, 2))

    rows = []
    for i, c in enumerate(combos):
        st = statuses[i]
        device = c["device"]
        if st == "0":
            offset = 0 if i in today_pending else random.randint(1, 9)
            discover = NOW - dt.timedelta(days=offset)
            if offset == 0:
                discover = at(TODAY, random.randint(8, min(17, NOW.hour)), random.randint(0, 59))
                if discover > NOW - dt.timedelta(minutes=10):
                    discover = NOW - dt.timedelta(minutes=random.randint(20, 120))
            else:
                discover = at(TODAY - dt.timedelta(days=offset), random.randint(8, 20), random.randint(0, 59))
        elif st == "1":
            discover = at(TODAY - dt.timedelta(days=random.randint(2, 15)), random.randint(8, 20), random.randint(0, 59))
        else:
            discover = at(TODAY - dt.timedelta(days=random.randint(6, 42)), random.randint(8, 20), random.randint(0, 59))

        if st == "0":
            handle_time = close_time = None
            assignee = None
            handle_desc = None
            desc = "巡检发现%s，已登记缺陷并通知检修班组，等待安排处理。" % c["title"]
        elif st == "1":
            handle_time = discover + dt.timedelta(hours=random.randint(2, 24))
            if handle_time > NOW - dt.timedelta(hours=1):
                handle_time = NOW - dt.timedelta(hours=random.randint(1, 5))
            close_time = None
            assignee = random.choice(ASSIGNEE.get(device["dept_id"], [2019]))
            handle_desc = HANDLE_BY_TYPE[c["device"]["device_type"]]
            desc = "巡检发现%s，已安排%s处理，目前正在消缺。" % (
                c["title"], EMPLOYEES[assignee][1])
        else:
            handle_time = discover + dt.timedelta(hours=random.randint(2, 36))
            close_time = handle_time + dt.timedelta(hours=random.randint(1, 30))
            if close_time > NOW - dt.timedelta(minutes=30):
                shift = close_time - (NOW - dt.timedelta(hours=2))
                discover -= shift
                handle_time -= shift
                close_time -= shift
            assignee = random.choice(ASSIGNEE.get(device["dept_id"], [2019]))
            handle_desc = HANDLE_BY_TYPE[device["device_type"]]
            desc = "巡检发现%s，经检修处理并复测合格，缺陷已闭环。" % c["title"]

        rows.append(dict(
            defect_id=i + 1, defect_code=None, device_id=device["device_id"],
            title=c["title"], level=c["level"], description=desc,
            discoverer_id=random.choice(list(INSPECTORS.keys())),
            discover_time=discover, assignee_id=assignee, status=st,
            handle_desc=handle_desc, handle_time=handle_time, close_time=close_time,
            tenant_id=TENANT, create_dept=device["dept_id"],
            create_by=random.choice(list(INSPECTORS.keys())),
            create_time=discover + dt.timedelta(minutes=5),
            update_by=assignee, update_time=close_time or handle_time,
            del_flag="0",
        ))

    rows.sort(key=lambda r: r["discover_time"])
    counters = {}
    for r in rows:
        key = r["discover_time"].strftime("%Y%m%d")
        counters[key] = counters.get(key, 0) + 1
        r["defect_code"] = "QX%s%03d" % (key, counters[key])

    # 待办中保留一条紧急缺陷，便于首页红点/优先级演示
    pending = [r for r in rows if r["status"] == "0"]
    if not any(r["level"] == "3" for r in pending):
        target = next((r for r in pending if "机械密封" in r["title"]), pending[0])
        closed_urgent = next(r for r in rows if r["status"] == "2" and r["level"] == "3")
        old_level = target["level"]
        target["level"], closed_urgent["level"] = "3", old_level

    assert sum(1 for r in rows if r["level"] == "1") == 50
    assert sum(1 for r in rows if r["level"] == "2") == 16
    assert sum(1 for r in rows if r["level"] == "3") == 6
    assert sum(1 for r in rows if r["status"] == "0") == 8
    assert sum(1 for r in rows if r["status"] == "1") == 4
    assert sum(1 for r in rows if r["status"] == "2") == 60
    for r in rows:
        if r["status"] == "0":
            assert r["assignee_id"] is None and r["handle_time"] is None
    return rows


# ----------------------------------------------------------------------------
# 日志与公告
# ----------------------------------------------------------------------------
def build_logins():
    days = [TODAY - dt.timedelta(days=i) for i in range(29, -1, -1)]
    weights = [1.8 if d.weekday() < 5 else 0.7 for d in days]
    picks = random.choices(days, weights=weights, k=200)
    # 保证每天至少 2 条，从最拥挤的日期挪过来
    from collections import Counter
    cnt = Counter(picks)
    for d in days:
        while cnt[d] < 2:
            donor = max(days, key=lambda x: cnt[x])
            picks.remove(donor)
            cnt[donor] -= 1
            picks.append(d)
            cnt[d] += 1
    failed = set(random.sample(range(200), 20))

    # 登录账号权重：巡检员高，管理岗低；admin 少量
    users = list(EMPLOYEES.keys()) + [1]
    uw = [3 if u in INSPECTORS else 1 for u in EMPLOYEES] + [0.5]

    rows = []
    for i, d in enumerate(sorted(picks), 1):
        u = random.choices(users, weights=uw)[0]
        if u == 1:
            account, nick = "admin", "系统管理员"
        else:
            account, nick, _ = EMPLOYEES[u]
        r = random.random()
        if r < 0.34:
            t = rand_dt(d, 8, 9)
        elif r < 0.64:
            t = at(d, 13, 30) + dt.timedelta(minutes=random.randrange(60))
        elif r < 0.88:
            t = rand_dt(d, 7, 17)
        else:
            t = rand_dt(d, 18, 21)
        if t > NOW - dt.timedelta(minutes=1):
            t = NOW - dt.timedelta(minutes=random.randint(2, 90))
            if t.date() != d:
                t = at(d, 8, 30)
        ok = i not in failed
        rows.append(dict(
            info_id=i, tenant_id=TENANT, user_name=account, client_key=None,
            device_type="pc", ipaddr="10.18.%d.%d" % (random.randint(1, 20), random.randint(2, 250)),
            login_location="河北省石家庄市", browser=random.choice(["Chrome 120", "Edge 120", "Chrome 119"]),
            os="Windows 10", status="0" if ok else "1",
            msg="登录成功" if ok else "密码错误", login_time=t,
        ))
    assert sum(1 for r in rows if r["status"] == "0") == 180
    assert sum(1 for r in rows if r["status"] == "1") == 20
    return rows


OPER_MODULES = [
    ("设备台账", "/insp/device", "InspDeviceController", 0.30),
    ("巡检记录", "/insp/record", "InspRecordController", 0.24),
    ("缺陷工单", "/insp/defect", "InspDefectController", 0.24),
    ("巡检计划", "/insp/plan", "InspPlanController", 0.12),
    ("巡检看板", "/insp/dashboard", "InspDashboardController", 0.10),
]


def build_opers(logins):
    good = [l for l in logins if l["status"] == "0" and l["login_time"] < NOW - dt.timedelta(hours=1)
            and l["user_name"] != "admin"]
    actions = ["query"] * 120 + ["insert"] * 90 + ["update"] * 100 + ["export"] * 40
    random.shuffle(actions)
    rows = []
    for i, act in enumerate(actions, 1):
        login = random.choice(good)
        account = login["user_name"]
        uid = next(k for k, v in EMPLOYEES.items() if v[0] == account)
        nick, dept = EMPLOYEES[uid][1], EMPLOYEES[uid][2]
        t = login["login_time"] + dt.timedelta(minutes=random.randint(2, 110))
        if t > NOW - dt.timedelta(minutes=1):
            t = NOW - dt.timedelta(minutes=random.randint(2, 60))

        if act == "query":
            mods = OPER_MODULES
        elif act == "export":
            mods = [m for m in OPER_MODULES if m[0] in ("设备台账", "巡检记录", "缺陷工单")]
        else:
            mods = [m for m in OPER_MODULES if m[0] != "巡检看板"]
        title, url, ctrl, _ = random.choices(mods, weights=[m[3] for m in mods])[0]

        if act == "query":
            btype, method, req = 0, "list", "GET"
            param = json.dumps({"pageNum": random.randint(1, 5), "pageSize": 10,
                                "beginTime": (t - dt.timedelta(days=7)).strftime("%Y-%m-%d"),
                                "endTime": t.strftime("%Y-%m-%d")}, ensure_ascii=False)
            result = json.dumps({"code": 200, "msg": "查询成功", "total": random.randint(8, 68)}, ensure_ascii=False)
        elif act == "export":
            btype, method, req = 5, "export", "POST"
            param = json.dumps({"pageNum": 1, "pageSize": 10}, ensure_ascii=False)
            result = json.dumps({"code": 200, "msg": "导出成功"}, ensure_ascii=False)
        elif act == "insert":
            btype, method, req = 1, "add", "POST"
            param = json.dumps({"deviceCode": "HD-SB-06-011", "deviceName": "#2机组一次风机A",
                                "deviceType": "06", "deptId": 100502, "status": "0"}, ensure_ascii=False)
            result = json.dumps({"code": 200, "msg": "操作成功"}, ensure_ascii=False)
        else:
            btype, method, req = 2, "edit", "POST"
            param = json.dumps({"deviceId": random.randint(1, 68), "status": random.choice(["0", "1", "2"]),
                                "remark": "检修后状态更新"}, ensure_ascii=False)
            result = json.dumps({"code": 200, "msg": "操作成功"}, ensure_ascii=False)

        failed = act == "insert" and i % 57 == 0
        rows.append(dict(
            oper_id=i, tenant_id=TENANT, title=title, business_type=btype,
            method="com.ruoyi.insp.controller.%s.%s" % (ctrl, method),
            request_method=req, operator_type=1, oper_name=nick,
            dept_name=DEPT_NAME.get(dept, ""),
            oper_url="%s/%s" % (url, method) if act != "insert" else url,
            oper_ip=login["ipaddr"], oper_location="河北省石家庄市",
            oper_param=param[:4000], json_result=result,
            status=1 if failed else 0,
            error_msg="设备编码已存在" if failed else None,
            oper_time=t, cost_time=random.randint(12, 900),
        ))
    assert len(rows) == 350
    return rows


def build_notices():
    items = [
        ("关于开展 2026 年秋季安全生产大检查的通知", "1", 2,
         """<p>公司各部门：</p>
<p>为深入贯彻落实集团公司安全生产工作部署，切实做好 2026 年秋季安全生产工作，经公司研究，决定自 10 月 20 日至 11 月 20 日开展秋季安全生产大检查。</p>
<p><strong>一、检查重点</strong></p>
<p>1. 两台机组主辅设备运行工况及缺陷闭环情况；<br/>2. 锅炉、汽轮机、发电机及 220kV 升压站重点区域；<br/>3. 输煤系统、脱硫脱硝设施及重大危险源管控情况。</p>
<p><strong>二、工作要求</strong></p>
<p>各部门对照检查大纲开展自查，10 月 31 日前将自查问题清单报安全监察部。检查期间严格执行“两票三制”，确保人身和设备安全。</p>
<p style="text-align:right">华电石家庄热电有限公司 安全监察部<br/>2026 年 10 月 19 日</p>"""),
        ("#2机组C级检修计划（10月25日-11月8日）", "1", 4,
         """<p>各生产部门：</p>
<p>#2 机组 C 级检修定于 2026 年 10 月 25 日至 11 月 8 日进行，计划工期 15 天。</p>
<p><strong>主要检修项目：</strong>汽轮机揭缸检查、锅炉受热面防磨防爆检查、发电机抽转子检查、脱硫塔#2 浆液循环泵检修、主变预防性试验等。</p>
<p>检修期间 #1 机组单机运行，运行部要加强监盘和参数调整，严格执行单机运行安全措施；检修部要严格执行检修文件包和三级验收制度，确保检修质量与工期。</p>
<p style="text-align:right">生产技术部<br/>2026 年 10 月 21 日</p>"""),
        ("关于加强冬季供暖期设备巡检频次的通知", "1", 1,
         """<p>各运行、检修班组：</p>
<p>2026—2027 供暖期将于 11 月 1 日正式启动。为保障供热安全稳定，自 11 月 1 日起，锅炉、汽轮机、热网首站、给水泵等重点设备日检频次由每日 1 次调整为每日 2 次。</p>
<p>巡检人员要重点检查轴承温度、振动、油位及伴热系统投运情况，发现异常立即汇报值长并登记缺陷。夜间巡检须两人同行，做好防寒防冻措施。</p>
<p style="text-align:right">运行部<br/>2026 年 10 月 26 日</p>"""),
        ("华电巡检管理系统 V2.3 升级维护通知（10月28日 22:00-24:00）", "2", 3,
         """<p>系统用户：</p>
<p>为优化巡检计划、缺陷闭环及移动作业功能，华电巡检管理系统定于 2026 年 10 月 28 日 22:00 至 24:00 进行 V2.3 版本升级。</p>
<p>升级期间系统暂停访问，请提前保存正在填写的巡检记录和缺陷工单。升级完成后如遇登录异常，请联系信息中心（内线 8021）。</p>
<p style="text-align:right">信息中心<br/>2026 年 10 月 27 日</p>"""),
        ("第三季度设备缺陷分析报告已发布", "2", 5,
         """<p>各部门：</p>
<p>《2026 年第三季度设备缺陷分析报告》已编制完成并发布至公司知识库。</p>
<p>三季度共受理缺陷工单 68 项，已闭环 64 项，闭环率 94.1%。缺陷主要集中在锅炉受热面、输煤皮带及脱硫浆液系统。请各班组组织学习，举一反三，落实预防性检修措施。</p>
<p style="text-align:right">生产技术部<br/>2026 年 10 月 8 日</p>"""),
    ]
    rows = []
    for i, (title, ntype, days_ago, content) in enumerate(items, 1):
        rows.append(dict(
            notice_id=i, tenant_id=TENANT, notice_title=title, notice_type=ntype,
            notice_content=content, status="0", create_dept=1001, create_by=1,
            create_time=at(TODAY - dt.timedelta(days=days_ago), 10, 0),
            update_by=None, update_time=None, remark=None,
        ))
    return rows


# ----------------------------------------------------------------------------
# 字典
# ----------------------------------------------------------------------------
DICT_TYPES = [
    (200, "设备类型", "insp_device_type", "巡检设备类型"),
    (201, "巡检结果", "insp_result", "巡检记录结果"),
    (202, "缺陷等级", "insp_defect_level", "缺陷工单等级"),
    (203, "工单状态", "insp_defect_status", "缺陷工单处理状态"),
]
DICT_DATA = [
    ("01", "锅炉", "insp_device_type", "", 1), ("02", "汽轮机", "insp_device_type", "", 2),
    ("03", "发电机", "insp_device_type", "", 3), ("04", "变压器", "insp_device_type", "", 4),
    ("05", "给水泵", "insp_device_type", "", 5), ("06", "风机", "insp_device_type", "", 6),
    ("07", "磨煤机", "insp_device_type", "", 7), ("08", "换热设备", "insp_device_type", "", 8),
    ("09", "输煤设备", "insp_device_type", "", 9), ("10", "环保设备", "insp_device_type", "", 10),
    ("0", "正常", "insp_result", "success", 1), ("1", "异常", "insp_result", "danger", 2),
    ("1", "一般", "insp_defect_level", "info", 1), ("2", "重要", "insp_defect_level", "warning", 2),
    ("3", "紧急", "insp_defect_level", "danger", 3),
    ("0", "待处理", "insp_defect_status", "warning", 1), ("1", "处理中", "insp_defect_status", "primary", 2),
    ("2", "已闭环", "insp_defect_status", "success", 3),
]


def build_dicts():
    types = []
    for did, name, dtype, remark in DICT_TYPES:
        types.append(dict(dict_id=did, tenant_id=TENANT, dict_name=name, dict_type=dtype,
                          create_dept=1001, create_by=1, create_time=at(TODAY, 9, 0),
                          update_by=None, update_time=None, remark=remark))
    data = []
    for i, (val, label, dtype, cls, sort) in enumerate(DICT_DATA, 200):
        data.append(dict(dict_code=i, tenant_id=TENANT, dict_sort=sort, dict_label=label,
                         dict_value=val, dict_type=dtype, css_class=None, list_class=cls,
                         is_default="N", create_dept=1001, create_by=1,
                         create_time=at(TODAY, 9, 5), update_by=None, update_time=None,
                         remark=None))
    return types, data


# ----------------------------------------------------------------------------
# 写库
# ----------------------------------------------------------------------------
def insert_sql(table, rows, cols):
    chunks = []
    for i in range(0, len(rows), 40):
        part = rows[i:i + 40]
        values = ",\n".join("(" + ", ".join(q(r[c]) for c in cols) + ")" for r in part)
        chunks.append("INSERT INTO %s (%s) VALUES\n%s;" % (table, ", ".join(cols), values))
    return chunks


DEVICE_COLS = ["device_id", "device_code", "device_name", "device_type", "model", "manufacturer",
               "dept_id", "location", "install_date", "status", "rated_param", "last_inspect_time",
               "next_inspect_time", "remark", "tenant_id", "create_dept", "create_by", "create_time",
               "update_by", "update_time", "del_flag"]
PLAN_COLS = ["plan_id", "plan_code", "plan_name", "device_type", "inspect_cycle", "inspector_id",
             "start_date", "end_date", "status", "inspect_items", "remark", "tenant_id",
             "create_dept", "create_by", "create_time", "update_by", "update_time", "del_flag"]
RECORD_COLS = ["record_id", "record_code", "plan_id", "device_id", "inspector_id", "inspect_time",
               "result", "item_count", "abnormal_count", "duration_min", "remark", "tenant_id",
               "create_dept", "create_by", "create_time", "update_by", "update_time", "del_flag"]
DEFECT_COLS = ["defect_id", "defect_code", "device_id", "title", "level", "description",
               "discoverer_id", "discover_time", "assignee_id", "status", "handle_desc",
               "handle_time", "close_time", "tenant_id", "create_dept", "create_by",
               "create_time", "update_by", "update_time", "del_flag"]
LOGIN_COLS = ["info_id", "tenant_id", "user_name", "client_key", "device_type", "ipaddr",
              "login_location", "browser", "os", "status", "msg", "login_time"]
OPER_COLS = ["oper_id", "tenant_id", "title", "business_type", "method", "request_method",
             "operator_type", "oper_name", "dept_name", "oper_url", "oper_ip", "oper_location",
             "oper_param", "json_result", "status", "error_msg", "oper_time", "cost_time"]
NOTICE_COLS = ["notice_id", "tenant_id", "notice_title", "notice_type", "notice_content", "status",
               "create_dept", "create_by", "create_time", "update_by", "update_time", "remark"]
DICT_TYPE_COLS = ["dict_id", "tenant_id", "dict_name", "dict_type", "create_dept", "create_by",
                  "create_time", "update_by", "update_time", "remark"]
DICT_DATA_COLS = ["dict_code", "tenant_id", "dict_sort", "dict_label", "dict_value", "dict_type",
                  "css_class", "list_class", "is_default", "create_dept", "create_by",
                  "create_time", "update_by", "update_time", "remark"]


def main():
    devices = build_devices()
    plans = build_plans()
    records = build_records(devices, plans)

    # 设备最近/下次巡检时间由真实记录回填，保证台账与记录一致
    latest = {}
    for r in records:
        if r["device_id"] not in latest or r["inspect_time"] > latest[r["device_id"]]:
            latest[r["device_id"]] = r["inspect_time"]
    for d in devices:
        last = latest.get(d["device_id"])
        if last is None or last < NOW - dt.timedelta(days=7):
            last = NOW - dt.timedelta(days=random.randint(0, 6), hours=random.randint(1, 12))
        cycle = CYCLE_DAYS[d["device_type"]]
        nxt = last + dt.timedelta(days=cycle)
        if nxt <= NOW:
            nxt = NOW + dt.timedelta(hours=random.randint(4, 72))
        if nxt > NOW + dt.timedelta(days=7):
            nxt = NOW + dt.timedelta(days=random.randint(1, 6), hours=random.randint(0, 12))
        d["last_inspect_time"] = last.replace(microsecond=0)
        d["next_inspect_time"] = nxt.replace(microsecond=0)

    defects = build_defects(devices)
    logins = build_logins()
    opers = build_opers(logins)
    notices = build_notices()
    dict_types, dict_data = build_dicts()

    statements = []
    statements += DDL
    statements += [
        "DELETE FROM sys_dict_data WHERE dict_type IN ('insp_device_type','insp_result','insp_defect_level','insp_defect_status')",
        "DELETE FROM sys_dict_type WHERE dict_type IN ('insp_device_type','insp_result','insp_defect_level','insp_defect_status')",
        "DELETE FROM sys_notice",
        "DELETE FROM sys_logininfor",
        "DELETE FROM sys_oper_log",
    ]
    statements += insert_sql("sys_dict_type", dict_types, DICT_TYPE_COLS)
    statements += insert_sql("sys_dict_data", dict_data, DICT_DATA_COLS)
    statements += insert_sql("insp_device", devices, DEVICE_COLS)
    statements += insert_sql("insp_plan", plans, PLAN_COLS)
    statements += insert_sql("insp_record", records, RECORD_COLS)
    statements += insert_sql("insp_defect", defects, DEFECT_COLS)
    statements += insert_sql("sys_logininfor", logins, LOGIN_COLS)
    statements += insert_sql("sys_oper_log", opers, OPER_COLS)
    statements += insert_sql("sys_notice", notices, NOTICE_COLS)

    with open(SQL_FILE, "w", encoding="utf-8") as f:
        f.write("-- R9 华电巡检管理系统演示数据（由 seed/r9_business_data.py 生成）\n")
        f.write("SET NAMES utf8mb4;\nUSE ry_r9;\n\n")
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
    print("R9 巡检业务数据灌入完成")
    print("=" * 64)
    for t in ("insp_device", "insp_plan", "insp_record", "insp_defect",
              "sys_logininfor", "sys_oper_log", "sys_notice"):
        cur.execute("SELECT COUNT(*) FROM %s" % t)
        print("%-16s %s" % (t, cur.fetchone()[0]))

    print("\n设备类型分布：")
    cur.execute("SELECT device_type, COUNT(*) FROM insp_device GROUP BY device_type ORDER BY device_type")
    for r in cur.fetchall():
        print("  %s %-6s %s" % (r[0], DEVICE_TYPE_NAME[r[0]], r[1]))
    print("设备状态分布：")
    cur.execute("SELECT status, COUNT(*) FROM insp_device GROUP BY status ORDER BY status")
    for r in cur.fetchall():
        print("  %s %s" % ({"0": "运行", "1": "备用", "2": "检修", "3": "停运"}[r[0]], r[1]))
    print("最近 7 天巡检记录：")
    cur.execute("""SELECT DATE(inspect_time) d, COUNT(*) FROM insp_record
                   WHERE inspect_time >= %s GROUP BY DATE(inspect_time) ORDER BY d""",
                (TODAY - dt.timedelta(days=6),))
    for r in cur.fetchall():
        print("  %s  %s 条" % (r[0], r[1]))
    print("缺陷状态/等级：")
    cur.execute("SELECT status, level, COUNT(*) FROM insp_defect GROUP BY status, level ORDER BY status, level")
    for r in cur.fetchall():
        print("  状态%s 等级%s  %s" % (r[0], r[1], r[2]))
    print("\nSQL 文件：%s" % SQL_FILE)


if __name__ == "__main__":
    main()
