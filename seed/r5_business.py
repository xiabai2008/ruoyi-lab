#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R5 华投集团财务共享中心 —— 费用报销业务数据 / 组织架构 / 日志 种子脚本
=====================================================================
目标库：MySQL 127.0.0.1:13307 / ry_r5
说明：
  1. 重建 biz_expense / biz_voucher / biz_supplier / biz_budget 四张业务表；
  2. 重建 28 个节点的三级部门树，保留 admin 与 scanner_low，重建 30 名员工；
  3. 重建「业务管理」菜单及其子菜单、按钮权限，仅给 role_id=1 补授权；
  4. 重灌登录日志与操作日志（近 30 天，工作日多、无未来时间）；
  5. 可重复执行，完整 SQL 落盘到 seed/r5_business.sql。

用法：python seed/r5_business.py
"""
import datetime as dt
import hashlib
import os
import random

import pymysql
from pymysql.converters import escape_string

DB = dict(host="127.0.0.1", port=13307, user="root", password="", database="ry_r5", charset="utf8mb4")

TODAY = dt.date.today()
NOW = dt.datetime.now().replace(microsecond=0)
SEED = 20261030
random.seed(SEED)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SQL_FILE = os.path.join(BASE_DIR, "r5_business.sql")

DEFAULT_SALT = "111111"
RY_SALT = "222222"
DEFAULT_PASSWORD = "admin123"
DOMAIN = "huatou-fssc.com"


def pw_hash(login_name, password, salt):
    """RuoYi 4.x 口令算法：MD5(loginName + password + salt)。"""
    return hashlib.md5((login_name + password + salt).encode("utf-8")).hexdigest()


# ----------------------------------------------------------------------------
# 组织架构（28 个节点，3 层，ID 固定）
# ----------------------------------------------------------------------------
# (dept_id, parent_id, dept_name, order_num, leader)
DEPTS = [
    (100, 0, "华投集团财务共享中心", 0, "陈国华"),
    (110, 100, "应付组", 1, "黄志强"),
    (111, 100, "应收组", 2, "周雅琴"),
    (112, 100, "费用报销组", 3, "何俊杰"),
    (113, 100, "总账组", 4, "谢桂英"),
    (114, 100, "资金组", 5, "蒋文斌"),
    (115, 100, "税务组", 6, "潘国平"),
    (116, 100, "档案管理组", 7, "梁少华"),
    (117, 100, "运维支持组", 8, "谭晓东"),
    (118, 100, "综合管理组", 9, "覃志远"),
    (120, 110, "供应商核算小组", 1, "李慧敏"),
    (121, 110, "付款审核小组", 2, "吴建国"),
    (122, 111, "客户对账小组", 1, "郑海涛"),
    (123, 111, "收款核销小组", 2, "冯丽华"),
    (124, 112, "差旅报销小组", 1, "罗小燕"),
    (125, 112, "费用审核小组", 2, "邓伟明"),
    (126, 113, "月结小组", 1, "曾繁昌"),
    (127, 113, "报表编制小组", 2, "彭雪梅"),
    (128, 114, "银行结算小组", 1, "苏永强"),
    (129, 114, "资金计划小组", 2, "蔡丽萍"),
    (130, 115, "发票管理小组", 1, "唐美玲"),
    (131, 115, "纳税申报小组", 2, "韦志刚"),
    (132, 116, "电子档案小组", 1, "许春燕"),
    (133, 116, "纸质档案小组", 2, "卢建明"),
    (134, 117, "系统运维小组", 1, "陆文静"),
    (135, 117, "用户支持小组", 2, "莫海燕"),
    (136, 118, "行政人事小组", 1, "石红梅"),
    (137, 118, "综合事务小组", 2, "黎国庆"),
]
DEPT_NAME = {d[0]: d[2] for d in DEPTS}

# (user_id, 姓名, dept_id, 岗位, 性别)  性别：0男 1女
EMPLOYEES = [
    (2001, "陈国华", 100, "中心主任", "0"),
    (2002, "林淑芬", 100, "中心副主任", "1"),
    (2003, "黄志强", 110, "应付组组长", "0"),
    (2004, "李慧敏", 120, "供应商核算会计", "1"),
    (2005, "吴建国", 121, "付款审核专员", "0"),
    (2006, "周雅琴", 111, "应收组组长", "1"),
    (2007, "郑海涛", 122, "客户对账会计", "0"),
    (2008, "冯丽华", 123, "收款核销专员", "1"),
    (2009, "何俊杰", 112, "费用报销组组长", "0"),
    (2010, "罗小燕", 124, "差旅报销审核员", "1"),
    (2011, "邓伟明", 125, "费用审核专员", "0"),
    (2012, "谢桂英", 113, "总账组组长", "1"),
    (2013, "曾繁昌", 126, "月结会计", "0"),
    (2014, "彭雪梅", 127, "报表编制会计", "1"),
    (2015, "蒋文斌", 114, "资金组组长", "0"),
    (2016, "苏永强", 128, "银行结算专员", "0"),
    (2017, "蔡丽萍", 129, "资金计划专员", "1"),
    (2018, "潘国平", 115, "税务组组长", "0"),
    (2019, "唐美玲", 130, "发票管理专员", "1"),
    (2020, "韦志刚", 131, "纳税申报专员", "0"),
    (2021, "梁少华", 116, "档案管理组组长", "0"),
    (2022, "许春燕", 132, "电子档案管理员", "1"),
    (2023, "卢建明", 133, "纸质档案管理员", "0"),
    (2024, "谭晓东", 117, "运维支持组组长", "0"),
    (2025, "陆文静", 134, "系统运维工程师", "1"),
    (2026, "莫海燕", 135, "用户支持专员", "1"),
    (2027, "覃志远", 118, "综合管理组组长", "0"),
    (2028, "石红梅", 136, "行政人事专员", "1"),
    (2029, "黎国庆", 137, "综合事务专员", "0"),
    (2030, "覃丽娟", 112, "报销复核会计", "1"),
]
# 工号规则：HT0001 起顺序排（user_id 2001 -> HT0001，2030 -> HT0030）
EMP_LOGIN = {e[0]: "HT%04d" % (i + 1) for i, e in enumerate(EMPLOYEES)}

# ry（user_id=2，salt 保持 222222）改造为 2002 林淑芬
RY_USER_ID = 2
RY_EMPLOYEE = 2002


def phone():
    return random.choice(["138", "139", "189"]) + "".join(random.choice("0123456789") for _ in range(8))


def email_for(login_name):
    return "%s@%s" % (login_name.lower(), DOMAIN)


# ----------------------------------------------------------------------------
# 业务表结构
# ----------------------------------------------------------------------------
DDL = [
    "DROP TABLE IF EXISTS biz_voucher",
    "DROP TABLE IF EXISTS biz_expense",
    "DROP TABLE IF EXISTS biz_supplier",
    "DROP TABLE IF EXISTS biz_budget",
    """CREATE TABLE biz_expense (
  expense_id bigint(20) NOT NULL AUTO_INCREMENT COMMENT '报销单ID',
  expense_no varchar(32) NOT NULL COMMENT '报销单号',
  applicant varchar(30) NOT NULL COMMENT '申请人',
  apply_dept_id bigint(20) DEFAULT NULL COMMENT '申请部门ID',
  apply_dept varchar(50) DEFAULT NULL COMMENT '申请部门',
  expense_type varchar(20) DEFAULT NULL COMMENT '费用类型',
  amount decimal(12,2) DEFAULT '0.00' COMMENT '报销金额',
  invoice_count int(11) DEFAULT '0' COMMENT '发票张数',
  apply_date date DEFAULT NULL COMMENT '申请日期',
  status varchar(10) DEFAULT NULL COMMENT '状态（待审批 审批中 已通过 已驳回 已付款）',
  approver varchar(30) DEFAULT NULL COMMENT '审批人',
  approve_time datetime DEFAULT NULL COMMENT '审批时间',
  pay_time datetime DEFAULT NULL COMMENT '付款时间',
  project_name varchar(100) DEFAULT NULL COMMENT '项目名称',
  remark varchar(500) DEFAULT NULL COMMENT '备注',
  create_by varchar(64) DEFAULT NULL COMMENT '创建者',
  create_time datetime DEFAULT NULL COMMENT '创建时间',
  update_by varchar(64) DEFAULT NULL COMMENT '更新者',
  update_time datetime DEFAULT NULL COMMENT '更新时间',
  PRIMARY KEY (expense_id),
  UNIQUE KEY uk_biz_expense_no (expense_no),
  KEY idx_biz_expense_applicant (applicant),
  KEY idx_biz_expense_dept (apply_dept_id),
  KEY idx_biz_expense_status (status),
  KEY idx_biz_expense_date (apply_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='费用报销单'""",
    """CREATE TABLE biz_voucher (
  voucher_id bigint(20) NOT NULL AUTO_INCREMENT COMMENT '凭证分录ID',
  voucher_no varchar(32) NOT NULL COMMENT '凭证号',
  voucher_date date DEFAULT NULL COMMENT '凭证日期',
  period varchar(7) DEFAULT NULL COMMENT '会计期间',
  summary varchar(200) DEFAULT NULL COMMENT '摘要',
  subject_code varchar(20) DEFAULT NULL COMMENT '科目编码',
  subject_name varchar(50) DEFAULT NULL COMMENT '科目名称',
  direction char(1) DEFAULT NULL COMMENT '方向（借/贷）',
  debit_amount decimal(12,2) DEFAULT '0.00' COMMENT '借方金额',
  credit_amount decimal(12,2) DEFAULT '0.00' COMMENT '贷方金额',
  maker varchar(30) DEFAULT NULL COMMENT '制单人',
  auditor varchar(30) DEFAULT NULL COMMENT '审核人',
  status varchar(10) DEFAULT NULL COMMENT '状态（已记账 已审核 未审核）',
  remark varchar(500) DEFAULT NULL COMMENT '备注',
  create_by varchar(64) DEFAULT NULL COMMENT '创建者',
  create_time datetime DEFAULT NULL COMMENT '创建时间',
  update_by varchar(64) DEFAULT NULL COMMENT '更新者',
  update_time datetime DEFAULT NULL COMMENT '更新时间',
  PRIMARY KEY (voucher_id),
  KEY idx_biz_voucher_no (voucher_no),
  KEY idx_biz_voucher_period (period),
  KEY idx_biz_voucher_date (voucher_date),
  KEY idx_biz_voucher_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='记账凭证分录'""",
    """CREATE TABLE biz_supplier (
  supplier_id bigint(20) NOT NULL AUTO_INCREMENT COMMENT '供应商ID',
  supplier_code varchar(20) NOT NULL COMMENT '供应商编码',
  supplier_name varchar(100) NOT NULL COMMENT '供应商名称',
  tax_no varchar(30) DEFAULT NULL COMMENT '纳税人识别号',
  contact varchar(30) DEFAULT NULL COMMENT '联系人',
  phone varchar(20) DEFAULT NULL COMMENT '联系电话',
  category varchar(20) DEFAULT NULL COMMENT '供应商类别',
  credit_level char(1) DEFAULT NULL COMMENT '信用等级（A/B/C）',
  bank_name varchar(100) DEFAULT NULL COMMENT '开户银行',
  bank_account varchar(30) DEFAULT NULL COMMENT '银行账号',
  settle_type varchar(20) DEFAULT NULL COMMENT '结算方式',
  cooperate_status varchar(10) DEFAULT NULL COMMENT '合作状态',
  first_coop_date date DEFAULT NULL COMMENT '首次合作日期',
  remark varchar(500) DEFAULT NULL COMMENT '备注',
  create_by varchar(64) DEFAULT NULL COMMENT '创建者',
  create_time datetime DEFAULT NULL COMMENT '创建时间',
  update_by varchar(64) DEFAULT NULL COMMENT '更新者',
  update_time datetime DEFAULT NULL COMMENT '更新时间',
  PRIMARY KEY (supplier_id),
  UNIQUE KEY uk_biz_supplier_code (supplier_code),
  UNIQUE KEY uk_biz_supplier_taxno (tax_no),
  KEY idx_biz_supplier_name (supplier_name),
  KEY idx_biz_supplier_category (category)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='供应商档案'""",
    """CREATE TABLE biz_budget (
  budget_id bigint(20) NOT NULL AUTO_INCREMENT COMMENT '预算ID',
  budget_year int(11) DEFAULT NULL COMMENT '预算年度',
  dept_id bigint(20) DEFAULT NULL COMMENT '部门ID',
  dept_name varchar(50) DEFAULT NULL COMMENT '部门名称',
  subject varchar(20) DEFAULT NULL COMMENT '预算科目',
  budget_amount decimal(14,2) DEFAULT '0.00' COMMENT '预算金额',
  used_amount decimal(14,2) DEFAULT '0.00' COMMENT '已使用金额',
  remain_amount decimal(14,2) DEFAULT '0.00' COMMENT '剩余金额',
  execute_rate decimal(6,4) DEFAULT '0.0000' COMMENT '执行率',
  status varchar(10) DEFAULT NULL COMMENT '状态（执行中 已关闭）',
  remark varchar(500) DEFAULT NULL COMMENT '备注',
  create_by varchar(64) DEFAULT NULL COMMENT '创建者',
  create_time datetime DEFAULT NULL COMMENT '创建时间',
  update_by varchar(64) DEFAULT NULL COMMENT '更新者',
  update_time datetime DEFAULT NULL COMMENT '更新时间',
  PRIMARY KEY (budget_id),
  UNIQUE KEY uk_biz_budget_dept_subject (budget_year, dept_id, subject),
  KEY idx_biz_budget_dept (dept_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='部门费用预算'""",
]

# ----------------------------------------------------------------------------
# 基础字典
# ----------------------------------------------------------------------------
EXPENSE_TYPES = ["差旅费", "办公费", "业务招待费", "培训费", "通讯费", "车辆使用费", "会议费"]
TYPE_RANGE = {
    "差旅费": (800, 12000),
    "办公费": (100, 5000),
    "业务招待费": (500, 8000),
    "培训费": (1000, 15000),
    "通讯费": (80, 600),
    "车辆使用费": (300, 4000),
    "会议费": (800, 9000),
}
TYPE_WEIGHT = [0.30, 0.22, 0.12, 0.11, 0.11, 0.08, 0.06]

PROJECTS = [
    "2026年度费用共享平台运维", "集团总部差旅结算", "财务共享中心系统升级",
    "华投集团费用标准化项目", "共享中心凭证电子化改造", "集团司库系统对接",
    "2026年度预算编制专项", "供应商协同平台建设", "税务发票数字化项目",
    "集团总部办公耗材采购", "财务机器人流程自动化", "共享中心档案数字化",
]

EXPENSE_REMARKS = [
    "出差报销，附机票及住宿发票", "部门日常办公用品采购", "客户接待费用",
    "岗位技能培训费用", "月度通讯费补贴", "公务用车油费及过路费",
    "季度经营分析会会务费", "项目组集中办公费用", "",
]

VOUCHER_STATUS_PLAN = [("已记账", 350), ("已审核", 60), ("未审核", 40)]
EXPENSE_STATUS_PLAN = [("待审批", 35), ("审批中", 45), ("已通过", 260), ("已驳回", 45), ("已付款", 235)]

DEBIT_SUBJECTS = [
    ("660201", "管理费用-办公费"),
    ("660202", "管理费用-差旅费"),
    ("660203", "管理费用-业务招待费"),
    ("660204", "管理费用-培训费"),
    ("660205", "管理费用-通讯费"),
]
CREDIT_SUBJECTS = [
    ("100201", "银行存款"),
    ("1001", "库存现金"),
    ("220201", "应付账款"),
    ("222101", "应交税费-增值税"),
]

CITY_LIST = ["南宁", "柳州", "桂林", "梧州", "北海", "防城港", "钦州", "贵港", "玉林", "百色",
             "贺州", "河池", "来宾", "崇左", "广州", "深圳", "佛山", "东莞", "珠海", "中山"]
BRAND_LIST = ["华宏", "桂丰", "恒瑞", "金桥", "广源", "鑫达", "智联", "泓泰", "铭远", "盛邦",
              "泰和", "佳信", "联创", "博远", "立成", "万通", "嘉禾", "润泽", "天诚", "德昌",
              "卓越", "宏图", "兴华", "安泰", "康利", "顺达", "鹏程", "东方", "南方", "西部",
              "珠江", "粤港", "桂商", "邕江", "柳江", "漓江", "北部湾", "西江", "红水河", "银海"]
CATEGORY_SUFFIX = {
    "服务类": ["信息技术服务有限公司", "物业服务有限公司", "人力资源服务有限公司", "商务服务有限公司",
            "物流服务有限公司", "保洁服务有限公司"],
    "货物类": ["贸易有限公司", "商贸有限公司", "物资有限公司", "办公设备有限公司", "机电设备有限公司",
            "电子科技有限公司"],
    "工程类": ["建筑工程有限公司", "装饰工程有限公司", "市政工程有限公司", "机电安装工程有限公司"],
    "咨询类": ["管理咨询有限公司", "财务咨询有限公司", "税务师事务所有限公司", "工程咨询有限公司"],
}
CONTACTS = ["李经理", "黄主管", "覃女士", "韦先生", "陈经理", "梁主管", "罗女士", "杨先生",
            "刘经理", "周主管", "吴女士", "郑先生", "冯经理", "曾主管"]
BANKS = ["中国银行南宁分行", "中国工商银行柳州分行", "中国建设银行桂林分行", "中国农业银行梧州分行",
         "交通银行北海分行", "招商银行深圳分行", "广西北部湾银行营业部", "中国银行广州分行",
         "中国建设银行佛山分行", "中国农业银行玉林分行"]
SETTLE_TYPES = ["月结30天", "月结60天", "货到付款", "预付款"]

BUDGET_SUBJECTS = ["差旅费", "办公费", "业务招待费", "培训费", "通讯费", "车辆使用费"]
BUDGET_RANGE = {
    "差旅费": (300000, 800000),
    "办公费": (80000, 250000),
    "业务招待费": (50000, 200000),
    "培训费": (100000, 300000),
    "通讯费": (20000, 80000),
    "车辆使用费": (60000, 180000),
}
BUDGET_DEPTS = [100, 110, 111, 112, 113, 114, 115, 116, 117, 118]


def rand_date(start, end):
    return start + dt.timedelta(days=random.randint(0, (end - start).days))


def rand_dt(d, h1=9, h2=18):
    return dt.datetime.combine(d, dt.time(random.randint(h1, h2), random.randint(0, 59), random.randint(0, 59)))


# ----------------------------------------------------------------------------
# 部门 / 用户
# ----------------------------------------------------------------------------
def build_depts():
    rows = []
    parent_map = {d[0]: d[1] for d in DEPTS}
    for dept_id, parent_id, name, order_num, leader in DEPTS:
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
            order_num=order_num, leader=leader, phone=phone(),
            email="dept%d@%s" % (dept_id, DOMAIN),
            status="0", del_flag="0", create_by="admin",
            create_time=dt.datetime(2024, 3, 18, 9, 0, 0),
            update_by="admin", update_time=NOW - dt.timedelta(days=random.randint(30, 300)),
        ))
    return rows


def build_users():
    """返回 (user_id=2 的改造行, 其余员工行)。"""
    rows = []
    ry_row = None
    for uid, name, dept, post, sex in EMPLOYEES:
        login = EMP_LOGIN[uid]
        row = dict(
            user_id=RY_USER_ID if uid == RY_EMPLOYEE else uid,
            dept_id=dept, login_name=login, user_name=name, user_type="00",
            email=email_for(login), phonenumber=phone(), sex=sex, avatar="",
            password=pw_hash(login, DEFAULT_PASSWORD, RY_SALT if uid == RY_EMPLOYEE else DEFAULT_SALT),
            salt=RY_SALT if uid == RY_EMPLOYEE else DEFAULT_SALT,
            status="0", del_flag="0",
            login_ip="10.20.30.%d" % (20 + uid % 100),
            login_date=NOW - dt.timedelta(days=random.randint(0, 6), hours=random.randint(0, 8)),
            pwd_update_date=None, create_by=str(dept),
            create_time=dt.datetime(2024, 3, 1, 9, 0, 0) + dt.timedelta(days=random.randint(0, 300)),
            update_by="admin", update_time=NOW - dt.timedelta(days=random.randint(1, 90)),
            remark=post,
        )
        if uid == RY_EMPLOYEE:
            ry_row = row
        else:
            rows.append(row)
    return ry_row, rows


# ----------------------------------------------------------------------------
# 费用报销
# ----------------------------------------------------------------------------
def build_expenses():
    staff = [(e[1], e[2], DEPT_NAME[e[2]]) for e in EMPLOYEES]
    approvers = [e[1] for e in EMPLOYEES if e[2] in (110, 111, 112, 113, 114, 115, 116, 117, 118)
                 and "组长" in e[3]]
    approvers.append("林淑芬")

    statuses = []
    for name, cnt in EXPENSE_STATUS_PLAN:
        statuses.extend([name] * cnt)
    assert len(statuses) == 620
    random.shuffle(statuses)

    rows = []
    for idx, status in enumerate(statuses, 1):
        applicant, dept_id, dept_name = random.choice(staff)
        etype = random.choices(EXPENSE_TYPES, weights=TYPE_WEIGHT)[0]
        lo, hi = TYPE_RANGE[etype]
        amount = round(random.uniform(lo, hi), 2)

        if status == "已付款":
            apply_date = rand_date(dt.date(2025, 11, 1), TODAY - dt.timedelta(days=30))
        elif status in ("已通过", "已驳回"):
            apply_date = rand_date(dt.date(2025, 11, 1), TODAY - dt.timedelta(days=15))
        else:
            apply_date = rand_date(TODAY - dt.timedelta(days=20), TODAY - dt.timedelta(days=1))

        create_time = rand_dt(apply_date, 9, 17)
        if create_time > NOW:
            create_time = NOW - dt.timedelta(minutes=random.randint(5, 300))

        approver = approve_time = pay_time = None
        update_time = create_time
        if status != "待审批":
            approver = random.choice(approvers)
        if status in ("已通过", "已驳回", "已付款"):
            approve_date = apply_date + dt.timedelta(days=random.randint(1, 4))
            approve_time = rand_dt(approve_date, 9, 18)
            if approve_time > NOW:
                approve_time = NOW - dt.timedelta(minutes=random.randint(10, 300))
            update_time = approve_time
        if status == "已付款":
            pay_time = approve_time + dt.timedelta(days=random.randint(1, 6),
                                                   hours=random.randint(0, 6),
                                                   minutes=random.randint(0, 59))
            if pay_time > NOW:
                pay_time = NOW - dt.timedelta(minutes=random.randint(5, 200))
            update_time = pay_time
        if update_time > NOW:
            update_time = NOW - dt.timedelta(minutes=random.randint(5, 200))

        rows.append(dict(
            expense_id=idx,
            expense_no="BX%s%05d" % (apply_date.strftime("%Y%m"), idx),
            applicant=applicant, apply_dept_id=dept_id, apply_dept=dept_name,
            expense_type=etype, amount=amount, invoice_count=random.randint(1, 8),
            apply_date=apply_date, status=status, approver=approver,
            approve_time=approve_time, pay_time=pay_time,
            project_name=random.choice(PROJECTS), remark=random.choice(EXPENSE_REMARKS),
            create_by=applicant, create_time=create_time, update_by="admin", update_time=update_time,
        ))
    return rows


# ----------------------------------------------------------------------------
# 记账凭证（450 张 × 2 行）
# ----------------------------------------------------------------------------
def build_vouchers():
    periods = ["2026-05", "2026-06", "2026-07", "2026-08", "2026-09", "2026-10"]
    statuses = []
    for name, cnt in VOUCHER_STATUS_PLAN:
        statuses.extend([name] * cnt)
    assert len(statuses) == 450
    random.shuffle(statuses)

    rows = []
    vid = 0
    si = 0
    for period in periods:
        year, month = int(period[:4]), int(period[5:])
        for seq in range(1, 76):
            status = statuses[si]
            si += 1
            if period == "2026-10":
                vdate = rand_date(dt.date(year, month, 1), dt.date(year, month, 20))
            else:
                vdate = rand_date(dt.date(year, month, 1), dt.date(year, month, 27))
            amount = round(random.uniform(800, 50000), 2)
            dcode, dname = random.choice(DEBIT_SUBJECTS)
            ccode, cname = random.choice(CREDIT_SUBJECTS)
            voucher_no = "JZ-%s%04d" % (period.replace("-", ""), seq)
            maker = random.choice(["曾繁昌", "谢桂英", "谢桂英"])
            auditor = None if status == "未审核" else "谢桂英"
            summary = "%s费用报销结转" % random.choice(["办公", "差旅", "招待", "培训", "通讯"])
            ctime = rand_dt(vdate, 9, 18)
            if ctime > NOW:
                ctime = NOW - dt.timedelta(minutes=random.randint(5, 300))
            for direction, scode, sname, debit, credit in (
                    ("借", dcode, dname, amount, 0.0),
                    ("贷", ccode, cname, 0.0, amount)):
                vid += 1
                rows.append(dict(
                    voucher_id=vid, voucher_no=voucher_no, voucher_date=vdate, period=period,
                    summary=summary, subject_code=scode, subject_name=sname, direction=direction,
                    debit_amount=debit, credit_amount=credit, maker=maker, auditor=auditor,
                    status=status, remark="费用报销凭证",
                    create_by=maker, create_time=ctime, update_by=maker, update_time=ctime,
                ))
    return rows


# ----------------------------------------------------------------------------
# 供应商
# ----------------------------------------------------------------------------
def build_suppliers():
    categories = (["服务类"] * 60 + ["货物类"] * 55 + ["工程类"] * 20 + ["咨询类"] * 15)
    random.shuffle(categories)
    credits = ["A"] * 45 + ["B"] * 80 + ["C"] * 25
    random.shuffle(credits)
    coops = ["合作中"] * 120 + ["暂停合作"] * 20 + ["已终止"] * 10
    random.shuffle(coops)

    used_names = set()
    used_tax = set()
    rows = []
    for i in range(1, 151):
        category = categories[i - 1]
        while True:
            name = "%s%s%s" % (random.choice(CITY_LIST), random.choice(BRAND_LIST),
                               random.choice(CATEGORY_SUFFIX[category]))
            if name not in used_names:
                used_names.add(name)
                break
        while True:
            tax_no = "91" + "".join(random.choice("0123456789ABCDEFGHJKLMNPQRTUWXY") for _ in range(16))
            if tax_no not in used_tax:
                used_tax.add(tax_no)
                break
        if random.random() < 0.5:
            tel = phone()
        else:
            tel = "0771-%07d" % random.randint(1000000, 9999999)
        first_coop = rand_date(dt.date(2019, 1, 1), dt.date(2025, 12, 31))
        created = dt.datetime(2019, 3, 1, 9, 0, 0) + dt.timedelta(days=random.randint(0, 2400))
        if created > NOW:
            created = NOW - dt.timedelta(days=random.randint(1, 200))
        updated = created + dt.timedelta(days=random.randint(10, 600), hours=random.randint(0, 8))
        if updated > NOW:
            updated = NOW - dt.timedelta(days=random.randint(1, 100))
        rows.append(dict(
            supplier_id=i, supplier_code="GYS%04d" % i, supplier_name=name, tax_no=tax_no,
            contact=random.choice(CONTACTS), phone=tel, category=category,
            credit_level=credits[i - 1], bank_name=random.choice(BANKS),
            bank_account="".join(random.choice("0123456789") for _ in range(19)),
            settle_type=random.choice(SETTLE_TYPES), cooperate_status=coops[i - 1],
            first_coop_date=first_coop,
            remark="%s类供应商，%s" % (category[0:2], random.choice(["长期合作", "年度框架协议", "单次采购", "战略供应商"])),
            create_by="admin", create_time=created, update_by="admin", update_time=updated,
        ))
    return rows


# ----------------------------------------------------------------------------
# 预算
# ----------------------------------------------------------------------------
def build_budgets():
    rows = []
    bid = 0
    statuses = ["执行中"] * 50 + ["已关闭"] * 10
    random.shuffle(statuses)
    for dept_id in BUDGET_DEPTS:
        for subject in BUDGET_SUBJECTS:
            bid += 1
            lo, hi = BUDGET_RANGE[subject]
            budget = round(random.uniform(lo, hi), 2)
            rate = round(random.uniform(0.35, 0.92), 4)
            used = round(budget * rate, 2)
            remain = round(budget - used, 2)
            rows.append(dict(
                budget_id=bid, budget_year=2026, dept_id=dept_id, dept_name=DEPT_NAME[dept_id],
                subject=subject, budget_amount=budget, used_amount=used, remain_amount=remain,
                execute_rate=round(used / budget, 4), status=statuses[bid - 1],
                remark="2026年度部门费用预算",
                create_by="admin", create_time=dt.datetime(2025, 12, 18, 10, 0, 0),
                update_by="admin", update_time=NOW - dt.timedelta(days=random.randint(1, 120)),
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
IPS = ["10.20.30.%d", "192.168.30.%d"]


def build_logins(user_rows):
    staff = [(u["login_name"], u["user_name"], u["dept_id"]) for u in user_rows]
    staff += [("admin", "系统管理员", 100), ("scanner_low", "运维支持", 134)]
    picks = []
    for item in staff:
        picks.extend([item] * 4)
    while len(picks) < 260:
        picks.append(random.choice(staff))
    picks = picks[:260]
    random.shuffle(picks)
    rows = []
    for i, (login, name, dept) in enumerate(picks, 1):
        d = workday_day()
        t = dt.datetime.combine(d, dt.time(random.randint(8, 19), random.randint(0, 59), random.randint(0, 59)))
        if t > NOW:
            t = NOW - dt.timedelta(minutes=random.randint(5, 400))
        failed = random.random() < 0.05
        rows.append(dict(
            info_id=i, login_name=login,
            ipaddr=random.choice(IPS) % random.randint(2, 250),
            login_location="广西壮族自治区南宁市",
            browser=random.choice(BROWSERS), os=random.choice(OS_LIST),
            status="1" if failed else "0",
            msg="密码错误" if failed else "登录成功",
            login_time=t,
        ))
    return rows


OPER_TITLES = [
    ("费用报销", 0.30, "business.BizExpense", [
        ("list", "查询报销单列表", 0, "POST", "/business/expense/list"),
        ("detail", "查看报销单详情", 0, "GET", "/business/expense/detail/1024"),
        ("export", "导出报销单数据", 5, "POST", "/business/expense/export"),
    ]),
    ("报销审批", 0.18, "business.BizExpense", [
        ("list", "查询待审批报销单", 0, "POST", "/business/expense/list"),
        ("detail", "查看报销单详情", 0, "GET", "/business/expense/detail/2048"),
    ]),
    ("凭证录入", 0.15, "business.BizVoucher", [
        ("list", "查询记账凭证", 0, "POST", "/business/voucher/list"),
    ]),
    ("供应商管理", 0.12, "business.BizSupplier", [
        ("list", "查询供应商列表", 0, "POST", "/business/supplier/list"),
    ]),
    ("预算编制", 0.11, "business.BizBudget", [
        ("list", "查询预算列表", 0, "POST", "/business/budget/list"),
    ]),
    ("用户管理", 0.06, "system.SysUser", [
        ("list", "查询用户列表", 0, "POST", "/system/user/list"),
        ("edit", "修改用户信息", 2, "POST", "/system/user/edit"),
    ]),
    ("角色管理", 0.04, "system.SysRole", [
        ("list", "查询角色列表", 0, "POST", "/system/role/list"),
        ("edit", "修改角色信息", 2, "POST", "/system/role/edit"),
    ]),
    ("菜单管理", 0.04, "system.SysMenu", [
        ("list", "查询菜单列表", 0, "POST", "/system/menu/list"),
        ("edit", "修改菜单信息", 2, "POST", "/system/menu/edit"),
    ]),
]


def build_opers(user_rows):
    staff = [(u["user_name"], u["dept_id"]) for u in user_rows]
    weights = [t[1] for t in OPER_TITLES]
    rows = []
    for i in range(1, 421):
        title, _, ctrl, actions = random.choices(OPER_TITLES, weights=weights)[0]
        act, label, btype, req, url = random.choice(actions)
        d = workday_day()
        t = dt.datetime.combine(d, dt.time(random.randint(8, 19), random.randint(0, 59), random.randint(0, 59)))
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
            oper_location="广西壮族自治区南宁市",
            oper_param='{"pageNum":"1","pageSize":"10","orderByColumn":"createTime","isAsc":"desc"}',
            json_result='{"code":0,"msg":"操作成功"}' if not failed else '{"code":500,"msg":"操作失败"}',
            status=1 if failed else 0,
            error_msg="数据校验失败，请稍后重试" if failed else None,
            oper_time=t, cost_time=random.randint(20, 900),
        ))
    return rows


# ----------------------------------------------------------------------------
# 菜单
# ----------------------------------------------------------------------------
MENUS = [
    dict(menu_id=2000, menu_name="业务管理", parent_id=0, order_num=4, url="#", target="",
         menu_type="M", visible="0", is_refresh="1", perms="", icon="fa fa-cny"),
    dict(menu_id=2001, menu_name="费用报销", parent_id=2000, order_num=1, url="business/expense", target="",
         menu_type="C", visible="0", is_refresh="1", perms="biz:expense:list", icon="fa fa-credit-card"),
    dict(menu_id=2002, menu_name="凭证管理", parent_id=2000, order_num=2, url="business/voucher", target="",
         menu_type="C", visible="0", is_refresh="1", perms="biz:voucher:list", icon="fa fa-book"),
    dict(menu_id=2003, menu_name="供应商管理", parent_id=2000, order_num=3, url="business/supplier", target="",
         menu_type="C", visible="0", is_refresh="1", perms="biz:supplier:list", icon="fa fa-truck"),
    dict(menu_id=2004, menu_name="预算管理", parent_id=2000, order_num=4, url="business/budget", target="",
         menu_type="C", visible="0", is_refresh="1", perms="biz:budget:list", icon="fa fa-pie-chart"),
    dict(menu_id=2005, menu_name="查询", parent_id=2001, order_num=1, url="#", target="",
         menu_type="F", visible="0", is_refresh="1", perms="biz:expense:query", icon="#"),
    dict(menu_id=2006, menu_name="详情", parent_id=2001, order_num=2, url="#", target="",
         menu_type="F", visible="0", is_refresh="1", perms="biz:expense:detail", icon="#"),
    dict(menu_id=2007, menu_name="导出", parent_id=2001, order_num=3, url="#", target="",
         menu_type="F", visible="0", is_refresh="1", perms="biz:expense:export", icon="#"),
]
MENU_COLS = ["menu_id", "menu_name", "parent_id", "order_num", "url", "target", "menu_type",
             "visible", "is_refresh", "perms", "icon", "create_by", "create_time", "remark"]


def build_menus():
    rows = []
    for m in MENUS:
        r = dict(m)
        r.update(create_by="admin", create_time=dt.datetime(2025, 12, 1, 10, 0, 0), remark=None)
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


EXPENSE_COLS = ["expense_id", "expense_no", "applicant", "apply_dept_id", "apply_dept",
                "expense_type", "amount", "invoice_count", "apply_date", "status", "approver",
                "approve_time", "pay_time", "project_name", "remark", "create_by", "create_time",
                "update_by", "update_time"]
VOUCHER_COLS = ["voucher_id", "voucher_no", "voucher_date", "period", "summary", "subject_code",
                "subject_name", "direction", "debit_amount", "credit_amount", "maker", "auditor",
                "status", "remark", "create_by", "create_time", "update_by", "update_time"]
SUPPLIER_COLS = ["supplier_id", "supplier_code", "supplier_name", "tax_no", "contact", "phone",
                 "category", "credit_level", "bank_name", "bank_account", "settle_type",
                 "cooperate_status", "first_coop_date", "remark", "create_by", "create_time",
                 "update_by", "update_time"]
BUDGET_COLS = ["budget_id", "budget_year", "dept_id", "dept_name", "subject", "budget_amount",
               "used_amount", "remain_amount", "execute_rate", "status", "remark", "create_by",
               "create_time", "update_by", "update_time"]
DEPT_COLS = ["dept_id", "parent_id", "ancestors", "dept_name", "order_num", "leader", "phone",
             "email", "status", "del_flag", "create_by", "create_time", "update_by", "update_time"]
USER_COLS = ["user_id", "dept_id", "login_name", "user_name", "user_type", "email", "phonenumber",
             "sex", "avatar", "password", "salt", "status", "del_flag", "login_ip", "login_date",
             "pwd_update_date", "create_by", "create_time", "update_by", "update_time", "remark"]
LOGIN_COLS = ["info_id", "login_name", "ipaddr", "login_location", "browser", "os", "status", "msg", "login_time"]
OPER_COLS = ["oper_id", "title", "business_type", "method", "request_method", "operator_type",
             "oper_name", "dept_name", "oper_url", "oper_ip", "oper_location", "oper_param",
             "json_result", "status", "error_msg", "oper_time", "cost_time"]


def main():
    depts = build_depts()
    ry_row, staff = build_users()
    expenses = build_expenses()
    vouchers = build_vouchers()
    suppliers = build_suppliers()
    budgets = build_budgets()
    logins = build_logins(staff + [ry_row])
    opers = build_opers(staff + [ry_row])
    menus = build_menus()

    statements = []
    statements += DDL

    # ---- 组织架构 ----
    statements += [
        "DELETE FROM sys_dept WHERE dept_id BETWEEN 100 AND 137",
        "DELETE FROM sys_user WHERE user_id NOT IN (1, 100)",
        "DELETE FROM sys_user_role WHERE user_id NOT IN (1, 100)",
        "DELETE FROM sys_user_post WHERE user_id NOT IN (1, 100)",
        "UPDATE sys_user SET user_name = '系统管理员', dept_id = 100, email = 'admin@%s' WHERE user_id = 1" % DOMAIN,
        "UPDATE sys_user SET dept_id = 134 WHERE user_id = 100",
    ]
    statements += insert_sql("sys_dept", depts, DEPT_COLS)
    statements += insert_sql("sys_user", [ry_row] + staff, USER_COLS)

    user_roles = [dict(user_id=RY_USER_ID, role_id=2)]
    user_posts = [dict(user_id=RY_USER_ID, post_id=2)]
    for uid, name, dept, post, sex in EMPLOYEES:
        real_uid = RY_USER_ID if uid == RY_EMPLOYEE else uid
        if real_uid == RY_USER_ID:
            continue
        user_roles.append(dict(user_id=real_uid, role_id=2))
        if dept == 100 and "主任" in post:
            post_id = 1
        elif "组长" in post:
            post_id = 2
        elif "人事" in post:
            post_id = 3
        else:
            post_id = 4
        user_posts.append(dict(user_id=real_uid, post_id=post_id))
    statements += insert_sql("sys_user_role", user_roles, ["user_id", "role_id"])
    statements += insert_sql("sys_user_post", user_posts, ["user_id", "post_id"])

    statements += [
        "UPDATE sys_post SET post_name = '中心主任' WHERE post_id = 1",
        "UPDATE sys_post SET post_name = '部门负责人' WHERE post_id = 2",
        "UPDATE sys_post SET post_name = '人事专员' WHERE post_id = 3",
        "UPDATE sys_post SET post_name = '业务专员' WHERE post_id = 4",
    ]

    # ---- 菜单 ----
    statements += [
        "UPDATE sys_menu SET menu_name = '工作台', url = '/system/main', target = '', perms = '', "
        "icon = 'fa fa-home', order_num = 1, menu_type = 'C' WHERE menu_id = 4",
        "DELETE FROM sys_menu WHERE menu_id BETWEEN 2000 AND 2007",
    ]
    statements += insert_sql("sys_menu", menus, MENU_COLS)
    statements += [
        "INSERT INTO sys_role_menu (role_id, menu_id) SELECT 1, m.menu_id FROM sys_menu m "
        "WHERE m.menu_id BETWEEN 2000 AND 2007 AND NOT EXISTS "
        "(SELECT 1 FROM sys_role_menu rm WHERE rm.role_id = 1 AND rm.menu_id = m.menu_id)",
    ]

    # ---- 业务数据 ----
    statements += insert_sql("biz_expense", expenses, EXPENSE_COLS)
    statements += insert_sql("biz_voucher", vouchers, VOUCHER_COLS)
    statements += insert_sql("biz_supplier", suppliers, SUPPLIER_COLS)
    statements += insert_sql("biz_budget", budgets, BUDGET_COLS)

    # ---- 日志 ----
    statements += ["DELETE FROM sys_logininfor", "DELETE FROM sys_oper_log"]
    statements += insert_sql("sys_logininfor", logins, LOGIN_COLS)
    statements += insert_sql("sys_oper_log", opers, OPER_COLS)

    with open(SQL_FILE, "w", encoding="utf-8") as f:
        f.write("-- R5 华投集团财务共享中心费用报销演示数据（由 seed/r5_business.py 生成）\n")
        f.write("SET NAMES utf8mb4;\nUSE ry_r5;\n\n")
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
    ("sys_dept", "create_time"),
    ("sys_dept", "update_time"),
    ("biz_expense", "apply_date"),
    ("biz_expense", "create_time"),
    ("biz_expense", "approve_time"),
    ("biz_expense", "pay_time"),
    ("biz_expense", "update_time"),
    ("biz_voucher", "voucher_date"),
    ("biz_voucher", "create_time"),
    ("biz_voucher", "update_time"),
    ("biz_supplier", "first_coop_date"),
    ("biz_supplier", "create_time"),
    ("biz_supplier", "update_time"),
    ("biz_budget", "create_time"),
    ("biz_budget", "update_time"),
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
    cur.execute(sql, args)
    return cur.fetchone()[0]


def verify(conn):
    cur = conn.cursor()
    print("=" * 64)
    print("R5 华投集团财务共享中心费用报销数据灌入完成")
    print("=" * 64)
    for t in ("biz_expense", "biz_voucher", "biz_supplier", "biz_budget",
              "sys_dept", "sys_user", "sys_menu", "sys_logininfor", "sys_oper_log"):
        cur.execute("SELECT COUNT(1) FROM %s" % t)
        print("%-16s %s" % (t, cur.fetchone()[0]))

    errors = []
    expect = {"biz_expense": 620, "biz_voucher": 900, "biz_supplier": 150, "biz_budget": 60}
    for t, n in expect.items():
        actual = scalar(cur, "SELECT COUNT(1) FROM %s" % t)
        if actual != n:
            errors.append("%s 行数 %s != %s" % (t, actual, n))

    # 报销单
    for name, cnt in EXPENSE_STATUS_PLAN:
        actual = scalar(cur, "SELECT COUNT(1) FROM biz_expense WHERE status = %s", name)
        if actual != cnt:
            errors.append("报销单状态 %s 为 %s != %s" % (name, actual, cnt))
    if scalar(cur, "SELECT COUNT(DISTINCT expense_no) FROM biz_expense") != 620:
        errors.append("报销单号不唯一")
    if scalar(cur, "SELECT COUNT(1) FROM biz_expense WHERE status = '待审批' AND "
                   "(approver IS NOT NULL OR approve_time IS NOT NULL OR pay_time IS NOT NULL)"):
        errors.append("待审批报销单存在审批人/审批时间/付款时间")
    if scalar(cur, "SELECT COUNT(1) FROM biz_expense WHERE status = '审批中' AND "
                   "(approver IS NULL OR approve_time IS NOT NULL OR pay_time IS NOT NULL)"):
        errors.append("审批中报销单字段不合规")
    if scalar(cur, "SELECT COUNT(1) FROM biz_expense WHERE status = '已通过' AND "
                   "(approver IS NULL OR approve_time IS NULL OR pay_time IS NOT NULL)"):
        errors.append("已通过报销单字段不合规")
    if scalar(cur, "SELECT COUNT(1) FROM biz_expense WHERE status = '已驳回' AND "
                   "(approver IS NULL OR approve_time IS NULL OR pay_time IS NOT NULL)"):
        errors.append("已驳回报销单字段不合规")
    if scalar(cur, "SELECT COUNT(1) FROM biz_expense WHERE status = '已付款' AND "
                   "(approver IS NULL OR approve_time IS NULL OR pay_time IS NULL)"):
        errors.append("已付款报销单字段不全")
    if scalar(cur, "SELECT COUNT(1) FROM biz_expense WHERE approve_time IS NOT NULL AND approve_time < apply_date"):
        errors.append("存在审批时间早于申请日期的报销单")
    if scalar(cur, "SELECT COUNT(1) FROM biz_expense WHERE pay_time IS NOT NULL AND pay_time < approve_time"):
        errors.append("存在付款时间早于审批时间的报销单")
    if scalar(cur, "SELECT COUNT(1) FROM biz_expense e LEFT JOIN sys_user u ON u.user_name = e.applicant "
                   "WHERE u.user_id IS NULL"):
        errors.append("报销单存在表外申请人")
    if scalar(cur, "SELECT COUNT(1) FROM biz_expense e JOIN sys_user u ON u.user_name = e.applicant "
                   "WHERE u.dept_id <> e.apply_dept_id"):
        errors.append("报销单申请人部门与申请部门不一致")

    # 凭证
    cur.execute("SELECT voucher_no, SUM(debit_amount), SUM(credit_amount), COUNT(1) FROM biz_voucher "
                "GROUP BY voucher_no HAVING COUNT(1) <> 2 OR ABS(SUM(debit_amount) - SUM(credit_amount)) > 0.001")
    bad = cur.fetchall()
    if bad:
        errors.append("凭证借贷不平或行数不为 2：%s 张" % len(bad))
    if scalar(cur, "SELECT COUNT(DISTINCT voucher_no) FROM biz_voucher") != 450:
        errors.append("凭证号数量不是 450")
    for name, cnt in VOUCHER_STATUS_PLAN:
        actual = scalar(cur, "SELECT COUNT(DISTINCT voucher_no) FROM biz_voucher WHERE status = %s", name)
        if actual != cnt:
            errors.append("凭证状态 %s 为 %s != %s" % (name, actual, cnt))
    cur.execute("SELECT period, COUNT(DISTINCT voucher_no) FROM biz_voucher GROUP BY period ORDER BY period")
    for p, n in cur.fetchall():
        if n != 75:
            errors.append("期间 %s 凭证数 %s != 75" % (p, n))

    # 供应商
    for cat, cnt in (("服务类", 60), ("货物类", 55), ("工程类", 20), ("咨询类", 15)):
        actual = scalar(cur, "SELECT COUNT(1) FROM biz_supplier WHERE category = %s", cat)
        if actual != cnt:
            errors.append("供应商类别 %s 为 %s != %s" % (cat, actual, cnt))
    for lvl, cnt in (("A", 45), ("B", 80), ("C", 25)):
        actual = scalar(cur, "SELECT COUNT(1) FROM biz_supplier WHERE credit_level = %s", lvl)
        if actual != cnt:
            errors.append("信用等级 %s 为 %s != %s" % (lvl, actual, cnt))
    for st, cnt in (("合作中", 120), ("暂停合作", 20), ("已终止", 10)):
        actual = scalar(cur, "SELECT COUNT(1) FROM biz_supplier WHERE cooperate_status = %s", st)
        if actual != cnt:
            errors.append("合作状态 %s 为 %s != %s" % (st, actual, cnt))

    # 预算
    if scalar(cur, "SELECT COUNT(1) FROM biz_budget WHERE budget_year = 2026") != 60:
        errors.append("预算年度不是全部 2026")
    if scalar(cur, "SELECT COUNT(DISTINCT dept_id) FROM biz_budget") != 10:
        errors.append("预算部门数不是 10")
    if scalar(cur, "SELECT COUNT(DISTINCT subject) FROM biz_budget") != 6:
        errors.append("预算科目数不是 6")
    if scalar(cur, "SELECT COUNT(1) FROM biz_budget WHERE ABS(budget_amount - used_amount - remain_amount) > 0.01"):
        errors.append("预算剩余金额计算不一致")
    for st, cnt in (("执行中", 50), ("已关闭", 10)):
        actual = scalar(cur, "SELECT COUNT(1) FROM biz_budget WHERE status = %s", st)
        if actual != cnt:
            errors.append("预算状态 %s 为 %s != %s" % (st, actual, cnt))

    # 组织架构与账号
    if scalar(cur, "SELECT COUNT(1) FROM sys_dept WHERE dept_id BETWEEN 100 AND 137") != 28:
        errors.append("部门节点数不是 28")
    if scalar(cur, "SELECT COUNT(1) FROM sys_dept WHERE dept_id BETWEEN 100 AND 137 AND status = '0'") != 28:
        errors.append("存在非正常状态部门")
    if scalar(cur, "SELECT COUNT(1) FROM sys_dept d WHERE d.parent_id <> 0 AND NOT EXISTS "
                   "(SELECT 1 FROM sys_dept p WHERE p.dept_id = d.parent_id)") != 0:
        errors.append("存在父部门缺失的节点")
    if scalar(cur, "SELECT COUNT(1) FROM sys_user") < 20:
        errors.append("用户数不足 20")
    if scalar(cur, "SELECT dept_id FROM sys_user WHERE user_id = 100") != 134:
        errors.append("scanner_low 部门不是 134")
    if scalar(cur, "SELECT COUNT(1) FROM sys_user WHERE user_id = 100 AND salt = 'mtrx01' AND status = '0'") != 1:
        errors.append("scanner_low 账号关键字段被改动")
    if scalar(cur, "SELECT COUNT(1) FROM sys_role_menu WHERE role_id = 99") != 5:
        errors.append("role_id=99 授权数发生变化")
    if scalar(cur, "SELECT COUNT(1) FROM sys_role_menu WHERE role_id = 1") < 8:
        errors.append("role_id=1 未补齐业务菜单授权")

    # 密码算法逐账号校验
    cur.execute("SELECT login_name, password, salt FROM sys_user WHERE user_id <> 100")
    for login, pwd, salt in cur.fetchall():
        if pwd != pw_hash(login, DEFAULT_PASSWORD, salt):
            errors.append("账号 %s 口令哈希与算法不一致" % login)

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
    if scalar(cur, "SELECT COUNT(1) FROM sys_oper_log WHERE title IN ('费用报销','报销审批','凭证录入','供应商管理','预算编制')") < 200:
        errors.append("业务类操作日志偏少")

    for t, col in TIME_CHECK:
        n = scalar(cur, "SELECT COUNT(1) FROM %s WHERE %s > NOW()" % (t, col))
        if n:
            errors.append("NO_FUTURE 违规：%s.%s 有 %s 行" % (t, col, n))

    cur.execute("SELECT status, COUNT(1) FROM biz_expense GROUP BY status ORDER BY status")
    print("\n报销单状态分布：")
    for r in cur.fetchall():
        print("  %-4s %s" % (r[0], r[1]))

    cur.execute("SELECT category, COUNT(1) FROM biz_supplier GROUP BY category")
    print("\n供应商类别分布：")
    for r in cur.fetchall():
        print("  %-4s %s" % (r[0], r[1]))

    cur.execute("SELECT period, COUNT(DISTINCT voucher_no) FROM biz_voucher GROUP BY period ORDER BY period")
    print("\n凭证期间分布：")
    for r in cur.fetchall():
        print("  %s  %s" % (r[0], r[1]))

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
    print("\n[OK] 行数、状态分布、借贷平衡、时间巡检、口令哈希全部通过")


if __name__ == "__main__":
    main()
