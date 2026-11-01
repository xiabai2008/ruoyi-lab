#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R10 星图数据科技有限公司 · 星report 报表平台 —— 业务数据 / 组织 / 用户 / 菜单 / 日志种子脚本
=========================================================================================
目标库：MySQL 127.0.0.1:13307 / ry_r10

说明：
  1. 创建并填充 4 张报表平台业务表：biz_dataset / biz_report / biz_dashboard / biz_subscription；
  2. 重建星图数据科技有限公司组织架构（sys_depart）与 25 个演示员工（sys_user）；
  3. 仅 INSERT 新增「数据报表」菜单及管理员授权，不 DELETE 任何既有权限记录；
  4. 追加近 30 天登录日志与操作日志（sys_log）；
  5. 可重复执行：业务表按固定 id 覆盖，组织/用户按业务键 upsert，菜单按 url 去重。

用法：python seed/r10_business.py
"""
import datetime as dt
import hashlib
import os
import random
import uuid

import pymysql

DB = dict(host="127.0.0.1", port=13307, user="root", password="", database="ry_r10", charset="utf8mb4")

NOW = dt.datetime.now().replace(microsecond=0)
TODAY = NOW.date()
random.seed(20261030)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

COMPANY = "星图数据科技有限公司"
ROLE_ADMIN_ID = "f6817f48af4fb3af11b9e8bf182f618b"  # 管理员 admin
ROLE_OPS_ID = uuid.uuid5(uuid.NAMESPACE_DNS, "r10.report_ops").hex
SEED_TAG = "r10seed"


# ---------------------------------------------------------------------------
# PBEWithMD5AndDES（与 JeecgBoot PasswordUtil.encrypt 完全一致）
# ---------------------------------------------------------------------------
IP = [58, 50, 42, 34, 26, 18, 10, 2, 60, 52, 44, 36, 28, 20, 12, 4, 62, 54, 46, 38, 30, 22, 14, 6,
      64, 56, 48, 40, 32, 24, 16, 8, 57, 49, 41, 33, 25, 17, 9, 1, 59, 51, 43, 35, 27, 19, 11, 3,
      61, 53, 45, 37, 29, 21, 13, 5, 63, 55, 47, 39, 31, 23, 15, 7]
FP = [40, 8, 48, 16, 56, 24, 64, 32, 39, 7, 47, 15, 55, 23, 63, 31, 38, 6, 46, 14, 54, 22, 62, 30,
      37, 5, 45, 13, 53, 21, 61, 29, 36, 4, 44, 12, 52, 20, 60, 28, 35, 3, 43, 11, 51, 19, 59, 27,
      34, 2, 42, 10, 50, 18, 58, 26, 33, 1, 41, 9, 49, 17, 57, 25]
E = [32, 1, 2, 3, 4, 5, 4, 5, 6, 7, 8, 9, 8, 9, 10, 11, 12, 13, 12, 13, 14, 15, 16, 17, 16, 17, 18,
     19, 20, 21, 20, 21, 22, 23, 24, 25, 24, 25, 26, 27, 28, 29, 28, 29, 30, 31, 32, 1]
P = [16, 7, 20, 21, 29, 12, 28, 17, 1, 15, 23, 26, 5, 18, 31, 10, 2, 8, 24, 14, 32, 27, 3, 9, 19, 13, 30, 6, 22, 11, 4, 25]
PC1 = [57, 49, 41, 33, 25, 17, 9, 1, 58, 50, 42, 34, 26, 18, 10, 2, 59, 51, 43, 35, 27, 19, 11, 3,
       60, 52, 44, 36, 63, 55, 47, 39, 31, 23, 15, 7, 62, 54, 46, 38, 30, 22, 14, 6, 61, 53, 45, 37,
       29, 21, 13, 5, 28, 20, 12, 4]
PC2 = [14, 17, 11, 24, 1, 5, 3, 28, 15, 6, 21, 10, 23, 19, 12, 4, 26, 8, 16, 7, 27, 20, 13, 2,
       41, 52, 31, 37, 47, 55, 30, 40, 51, 45, 33, 48, 44, 49, 39, 56, 34, 53, 46, 42, 50, 36, 29, 32]
SHIFTS = [1, 1, 2, 2, 2, 2, 2, 2, 1, 2, 2, 2, 2, 2, 2, 1]
SBOX = [
    [14, 4, 13, 1, 2, 15, 11, 8, 3, 10, 6, 12, 5, 9, 0, 7, 0, 15, 7, 4, 14, 2, 13, 1, 10, 6, 12, 11, 9, 5, 3, 8,
     4, 1, 14, 8, 13, 6, 2, 11, 15, 12, 9, 7, 3, 10, 5, 0, 15, 12, 8, 2, 4, 9, 1, 7, 5, 11, 3, 14, 10, 0, 6, 13],
    [15, 1, 8, 14, 6, 11, 3, 4, 9, 7, 2, 13, 12, 0, 5, 10, 3, 13, 4, 7, 15, 2, 8, 14, 12, 0, 1, 10, 6, 9, 11, 5,
     0, 14, 7, 11, 10, 4, 13, 1, 5, 8, 12, 6, 9, 3, 2, 15, 13, 8, 10, 1, 3, 15, 4, 2, 11, 6, 7, 12, 0, 5, 14, 9],
    [10, 0, 9, 14, 6, 3, 15, 5, 1, 13, 12, 7, 11, 4, 2, 8, 13, 7, 0, 9, 3, 4, 6, 10, 2, 8, 5, 14, 12, 11, 15, 1,
     13, 6, 4, 9, 8, 15, 3, 0, 11, 1, 2, 12, 5, 10, 14, 7, 1, 10, 13, 0, 6, 9, 8, 7, 4, 15, 14, 3, 11, 5, 2, 12],
    [7, 13, 14, 3, 0, 6, 9, 10, 1, 2, 8, 5, 11, 12, 4, 15, 13, 8, 11, 5, 6, 15, 0, 3, 4, 7, 2, 12, 1, 10, 14, 9,
     10, 6, 9, 0, 12, 11, 7, 13, 15, 1, 3, 14, 5, 2, 8, 4, 3, 15, 0, 6, 10, 1, 13, 8, 9, 4, 5, 11, 12, 7, 2, 14],
    [2, 12, 4, 1, 7, 10, 11, 6, 8, 5, 3, 15, 13, 0, 14, 9, 14, 11, 2, 12, 4, 7, 13, 1, 5, 0, 15, 10, 3, 9, 8, 6,
     4, 2, 1, 11, 10, 13, 7, 8, 15, 9, 12, 5, 6, 3, 0, 14, 11, 8, 12, 7, 1, 14, 2, 13, 6, 15, 0, 9, 10, 4, 5, 3],
    [12, 1, 10, 15, 9, 2, 6, 8, 0, 13, 3, 4, 14, 7, 5, 11, 10, 15, 4, 2, 7, 12, 9, 5, 6, 1, 13, 14, 0, 11, 3, 8,
     9, 14, 15, 5, 2, 8, 12, 3, 7, 0, 4, 10, 1, 13, 11, 6, 4, 3, 2, 12, 9, 5, 15, 10, 11, 14, 1, 7, 6, 0, 8, 13],
    [4, 11, 2, 14, 15, 0, 8, 13, 3, 12, 9, 7, 5, 10, 6, 1, 13, 0, 11, 7, 4, 9, 1, 10, 14, 3, 5, 12, 2, 15, 8, 6,
     1, 4, 11, 13, 12, 3, 7, 14, 10, 15, 6, 8, 0, 5, 9, 2, 6, 11, 13, 8, 1, 4, 10, 7, 9, 5, 0, 15, 14, 2, 3, 12],
    [13, 2, 8, 4, 6, 15, 11, 1, 10, 9, 3, 14, 5, 0, 12, 7, 1, 15, 13, 8, 10, 3, 7, 4, 12, 5, 6, 11, 0, 14, 9, 2,
     7, 11, 4, 1, 9, 12, 14, 2, 0, 6, 10, 13, 15, 3, 5, 8, 2, 1, 14, 7, 4, 10, 8, 13, 15, 12, 9, 0, 3, 5, 6, 11],
]


def _bits(data):
    return [int(b) for byte in data for b in format(byte, "08b")]


def _from_bits(bs):
    return bytes(int("".join(map(str, bs[i:i + 8])), 2) for i in range(0, len(bs), 8))


def _permute(bs, table):
    return [bs[i - 1] for i in table]


def _key_schedule(key):
    kb = _permute(_bits(key), PC1)
    c, d = kb[:28], kb[28:]
    out = []
    for s in SHIFTS:
        c, d = c[s:] + c[:s], d[s:] + d[:s]
        out.append(_permute(c + d, PC2))
    return out


def _des_block(block, subkeys):
    b = _permute(_bits(block), IP)
    left, right = b[:32], b[32:]
    for k in subkeys:
        x = [a ^ c for a, c in zip(_permute(right, E), k)]
        s = []
        for i in range(8):
            chunk = x[i * 6:(i + 1) * 6]
            row = chunk[0] * 2 + chunk[5]
            col = chunk[1] * 8 + chunk[2] * 4 + chunk[3] * 2 + chunk[4]
            s.extend(int(v) for v in format(SBOX[i][row * 16 + col], "04b"))
        f = _permute(s, P)
        left, right = right, [a ^ c for a, c in zip(left, f)]
    return _from_bits(_permute(right + left, FP))


def _des_cbc_encrypt(key, iv, data):
    subkeys = _key_schedule(key)
    pad = 8 - len(data) % 8
    data += bytes([pad]) * pad
    out, prev = b"", iv
    for i in range(0, len(data), 8):
        blk = bytes(a ^ b for a, b in zip(data[i:i + 8], prev))
        prev = _des_block(blk, subkeys)
        out += prev
    return out


def jeecg_password(username, plain="123456", salt=None):
    """等价于 JeecgBoot PasswordUtil.encrypt(username, plain, salt)。"""
    if not salt:
        salt = hashlib.md5(("salt:" + username).encode()).hexdigest()[:8]
    t = hashlib.md5(plain.encode() + salt.encode()[:8]).digest()
    for _ in range(999):
        t = hashlib.md5(t).digest()
    return _des_cbc_encrypt(t[:8], t[8:16], username.encode("utf-8")).hex(), salt


# ---------------------------------------------------------------------------
# 基础工具
# ---------------------------------------------------------------------------
def near(days_ago, h1=8, h2=20):
    """近 N 天内的一个随机时间，绝不晚于当前时间。"""
    day = TODAY - dt.timedelta(days=days_ago)
    t = dt.datetime.combine(day, dt.time(random.randint(h1, max(h1, h2 - 1)), random.randint(0, 59), random.randint(0, 59)))
    if t > NOW:
        t = NOW - dt.timedelta(minutes=random.randint(1, 40))
    return max(t, NOW - dt.timedelta(days=90))


def day_time(day, h1=8, h2=21):
    t = dt.datetime.combine(day, dt.time(random.randint(h1, h2 - 1), random.randint(0, 59), random.randint(0, 59)))
    if t > NOW:
        t = NOW - dt.timedelta(minutes=random.randint(5, 55))
    return t


def after(created, max_days=12):
    t = created + dt.timedelta(minutes=random.randint(30, 60 * 24 * max_days))
    return min(t, NOW)


def st(v):
    return None if v is None else v.strftime("%Y-%m-%d %H:%M:%S")


# ---------------------------------------------------------------------------
# 业务数据
# ---------------------------------------------------------------------------
DATASET_NAMES = [
    "销售订单明细", "销售出库明细", "销售退货明细", "渠道销售日报", "门店销售月报", "电商订单宽表",
    "财务凭证流水", "总账科目余额", "应收账款账龄", "应付账款明细", "费用报销明细", "发票开具明细",
    "银行流水对账", "成本核算明细", "设备运行日报", "库存周转分析", "库存快照", "采购入库明细",
    "供应商履约评价", "物流轨迹明细", "生产工单明细", "质量检验记录", "能耗监测日报", "客户画像标签",
    "客户生命周期", "会员活跃分析", "客户投诉工单", "售后回访记录", "客户贡献度分层", "渠道投放效果",
    "员工花名册", "考勤打卡明细", "薪酬发放明细", "招聘漏斗分析", "培训完成记录", "绩效评分明细",
    "组织编制台账", "风险客户名单", "反欺诈交易明细", "合同履约台账", "合规检查记录", "信用评级明细",
    "逾期账户清单", "异常交易监控", "项目进度明细", "预算执行明细", "资产折旧明细", "门店经营日报",
    "经营指标汇总", "区域业绩达成", "产品销售排行", "客户满意度调研", "工单处理时效", "数据质量稽核",
    "主数据变更记录", "系统访问审计", "供应商准入档案", "商品价格变动", "促销活动效果", "资金计划执行",
]

REPORT_PERIODS = ["2026年Q3", "2026年10月", "2026年9月", "2026年8月", "2026年7月", "近30天", "本季度", "上月", "2026年上半年"]
REPORT_BASES = {
    1: ["营收看板", "各区域销售达成率", "重点客户贡献分析", "产品结构毛利分析"],
    2: ["应收账款账龄分析", "月度费用执行分析", "资金收支日报", "成本偏差分析"],
    3: ["库存周转天数分析", "订单履约时效分析", "设备运行效率分析", "供应链健康度分析"],
    4: ["月度人力成本趋势", "各部门编制执行情况", "员工流失率分析", "招聘渠道转化分析"],
    5: ["风险客户预警清单", "逾期账款风险分布", "异常交易监控分析", "合同履约风险分析"],
}

DASHBOARD_NAMES = [
    "集团经营驾驶舱", "销售团队日报看板", "供应链健康度监控", "财务共享中心看板", "人力资源驾驶舱",
    "客户成功运营看板", "数据资产治理看板", "电商大促实时看板", "华东区域经营看板", "华南区域经营看板",
    "华北区域经营看板", "西南区域经营看板", "渠道投放效果看板", "门店运营日报看板", "库存周转监控看板",
    "采购履约监控看板", "物流时效监控看板", "生产运营驾驶舱", "设备健康度看板", "质量风险监控看板",
    "应收账款监控看板", "费用预算执行看板", "资金日报看板", "薪酬成本分析看板", "招聘进度看板",
    "绩效达成看板", "培训运营看板", "风控预警驾驶舱", "合规检查看板", "合同履约看板",
    "供应商风险看板", "客户流失预警看板", "会员活跃分析看板", "售后工单看板", "项目交付看板",
    "数据质量看板", "系统运行监控看板", "能耗管理看板", "资产运营看板", "门店巡检看板",
]

CRON_EXPRS = [
    "0 0 9 * * ?", "0 30 18 ? * MON", "0 0 8 1 * ?", "0 0/30 8-20 * * ?", "0 15 10 ? * FRI",
    "0 0 7 * * ?", "0 45 17 * * ?", "0 0 6 ? * MON-FRI", "0 0 */2 * * ?", "0 20 9 ? * WED",
    "0 0 12 * * ?", "0 10 20 ? * SUN", "0 0 10 1,15 * ?", "0 5 8 * * MON-FRI", "0 30 16 * * ?",
]

# (username, realname, org_code, sex, identity)
USERS = [
    ("zhaolei", "赵磊", "A01A02A01", 1, 1),
    ("qianxiaowen", "钱晓雯", "A01A01", 2, 1),
    ("sunhao", "孙浩", "A01A02A02", 1, 1),
    ("lijingyi", "李静怡", "A01A03", 2, 1),
    ("zhoujianguo", "周建国", "A01A04", 1, 2),
    ("wumin", "吴敏", "A01A05", 2, 1),
    ("zhengkai", "郑凯", "A01A06", 1, 1),
    ("wangxue", "王雪", "A01A01", 2, 1),
    ("fenglei", "冯磊", "A01A02", 1, 2),
    ("chensiyuan", "陈思远", "A01A02A01", 1, 1),
    ("chutingting", "褚婷婷", "A01A02A01", 2, 1),
    ("weidong", "卫东", "A01A02A01", 1, 1),
    ("jiangwenbo", "蒋文博", "A01A02A02", 1, 1),
    ("shenjiayi", "沈佳怡", "A01A02A02", 2, 1),
    ("hanxuefeng", "韩雪峰", "A01A03", 1, 1),
    ("yangfan", "杨帆", "A01A03", 1, 1),
    ("zhulijuan", "朱丽娟", "A01A03", 2, 1),
    ("qinhao", "秦昊", "A01A04A01", 1, 1),
    ("youya", "尤雅", "A01A04A01", 2, 1),
    ("xuzhiqiang", "许志强", "A01A04A02", 1, 1),
    ("hemeiling", "何美玲", "A01A04A02", 2, 1),
    ("lvwenta", "吕文涛", "A01A05", 1, 1),
    ("shizhan", "施展", "A01A05", 1, 1),
    ("zhangpeng", "张鹏", "A01A06", 1, 1),
    ("konglinghui", "孔令辉", "A01A01", 1, 1),
]

DEPARTMENTS = [
    ("A01", None, COMPANY, 1, 0, "1"),
    ("A01A01", "A01", "产品部", 1, 1, "2"),
    ("A01A02", "A01", "研发部", 2, 0, "2"),
    ("A01A02A01", "A01A02", "平台组", 1, 1, "2"),
    ("A01A02A02", "A01A02", "数据组", 2, 1, "2"),
    ("A01A03", "A01", "数据部", 3, 1, "2"),
    ("A01A04", "A01", "销售部", 4, 0, "2"),
    ("A01A04A01", "A01A04", "华东大区", 1, 1, "2"),
    ("A01A04A02", "A01A04", "华南大区", 2, 1, "2"),
    ("A01A05", "A01", "客户成功部", 5, 1, "2"),
    ("A01A06", "A01", "运维部", 6, 1, "2"),
]

DDL = [
    """CREATE TABLE IF NOT EXISTS biz_dataset (
  id bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
  dataset_code varchar(32) NOT NULL COMMENT '数据集编码',
  dataset_name varchar(100) NOT NULL COMMENT '数据集名称',
  source_type tinyint NOT NULL DEFAULT 1 COMMENT '来源类型(1MySQL 2API 3Excel 4ClickHouse)',
  owner_id varchar(32) DEFAULT NULL COMMENT '负责人ID',
  owner_name varchar(50) DEFAULT NULL COMMENT '负责人姓名',
  row_count bigint DEFAULT 0 COMMENT '数据行数',
  refresh_cycle tinyint DEFAULT 3 COMMENT '刷新周期(1实时 2小时 3日 4周)',
  status tinyint DEFAULT 0 COMMENT '状态(0草稿 1已发布 2已下线)',
  last_refresh_time datetime DEFAULT NULL COMMENT '最近刷新时间',
  remark varchar(500) DEFAULT NULL COMMENT '备注',
  create_by varchar(32) DEFAULT NULL COMMENT '创建人',
  create_time datetime DEFAULT NULL COMMENT '创建时间',
  update_by varchar(32) DEFAULT NULL COMMENT '更新人',
  update_time datetime DEFAULT NULL COMMENT '更新时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_dataset_code (dataset_code),
  KEY idx_ds_source (source_type),
  KEY idx_ds_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='数据集'""",
    """CREATE TABLE IF NOT EXISTS biz_report (
  id bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
  report_code varchar(32) NOT NULL COMMENT '报表编码',
  report_name varchar(150) NOT NULL COMMENT '报表名称',
  dataset_id bigint DEFAULT NULL COMMENT '数据集ID',
  category tinyint DEFAULT NULL COMMENT '分类(1经营 2财务 3运营 4人力 5风控)',
  chart_type tinyint DEFAULT NULL COMMENT '图表类型(1表格 2折线 3柱状 4饼图 5地图)',
  owner_id varchar(32) DEFAULT NULL COMMENT '负责人ID',
  owner_name varchar(50) DEFAULT NULL COMMENT '负责人姓名',
  view_count bigint DEFAULT 0 COMMENT '浏览次数',
  status tinyint DEFAULT 0 COMMENT '状态(0草稿 1已发布 2已下线)',
  publish_time datetime DEFAULT NULL COMMENT '发布时间',
  remark varchar(500) DEFAULT NULL COMMENT '备注',
  create_by varchar(32) DEFAULT NULL COMMENT '创建人',
  create_time datetime DEFAULT NULL COMMENT '创建时间',
  update_by varchar(32) DEFAULT NULL COMMENT '更新人',
  update_time datetime DEFAULT NULL COMMENT '更新时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_report_code (report_code),
  KEY idx_rp_dataset (dataset_id),
  KEY idx_rp_category (category),
  KEY idx_rp_status (status),
  KEY idx_rp_publish (publish_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='报表'""",
    """CREATE TABLE IF NOT EXISTS biz_dashboard (
  id bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
  dashboard_code varchar(32) NOT NULL COMMENT '看板编码',
  dashboard_name varchar(150) NOT NULL COMMENT '看板名称',
  owner_id varchar(32) DEFAULT NULL COMMENT '负责人ID',
  owner_name varchar(50) DEFAULT NULL COMMENT '负责人姓名',
  layout_type tinyint DEFAULT 1 COMMENT '布局类型(1自由布局 2栅格布局 3大屏 4移动端)',
  widget_count int DEFAULT 0 COMMENT '组件数量',
  share_scope tinyint DEFAULT 1 COMMENT '共享范围(1私有 2部门 3全公司)',
  status tinyint DEFAULT 0 COMMENT '状态(0草稿 1已发布 2已下线)',
  remark varchar(500) DEFAULT NULL COMMENT '备注',
  create_by varchar(32) DEFAULT NULL COMMENT '创建人',
  create_time datetime DEFAULT NULL COMMENT '创建时间',
  update_by varchar(32) DEFAULT NULL COMMENT '更新人',
  update_time datetime DEFAULT NULL COMMENT '更新时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_dashboard_code (dashboard_code),
  KEY idx_db_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='看板'""",
    """CREATE TABLE IF NOT EXISTS biz_subscription (
  id bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
  subscription_code varchar(32) NOT NULL COMMENT '订阅编码',
  report_id bigint DEFAULT NULL COMMENT '报表ID',
  subscriber_id varchar(32) DEFAULT NULL COMMENT '订阅人ID',
  subscriber_name varchar(50) DEFAULT NULL COMMENT '订阅人姓名',
  channel tinyint DEFAULT 1 COMMENT '渠道(1邮件 2企业微信 3钉钉)',
  cron_expr varchar(64) DEFAULT NULL COMMENT '调度表达式',
  last_send_time datetime DEFAULT NULL COMMENT '最近发送时间',
  send_count bigint DEFAULT 0 COMMENT '发送次数',
  status tinyint DEFAULT 0 COMMENT '状态(0启用 1停用)',
  remark varchar(500) DEFAULT NULL COMMENT '备注',
  create_by varchar(32) DEFAULT NULL COMMENT '创建人',
  create_time datetime DEFAULT NULL COMMENT '创建时间',
  update_by varchar(32) DEFAULT NULL COMMENT '更新人',
  update_time datetime DEFAULT NULL COMMENT '更新时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_subscription_code (subscription_code),
  KEY idx_sub_report (report_id),
  KEY idx_sub_channel (channel),
  KEY idx_sub_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='报表订阅'""",
]


# ---------------------------------------------------------------------------
# 组织架构 / 用户
# ---------------------------------------------------------------------------
def seed_org(cur):
    cur.execute("SELECT id, org_code, del_flag FROM sys_depart")
    existing = {r[1]: r[0] for r in cur.fetchall()}
    ids = {}
    for code, parent, name, order, leaf, org_type in DEPARTMENTS:
        ids[code] = existing.get(code) or uuid.uuid5(uuid.NAMESPACE_DNS, "r10.depart." + code).hex

    for code, parent, name, order, leaf, org_type in DEPARTMENTS:
        dep_id = ids[code]
        parent_id = ids.get(parent) if parent else None
        values = (parent_id, name, order, org_type, code, "1", "0", "admin", st(near(88, 9, 17)), "admin",
                  st(near(20, 9, 17)), 0, leaf, dep_id)
        if code in existing:
            cur.execute(
                """UPDATE sys_depart SET parent_id=%s, depart_name=%s, depart_order=%s, org_type=%s, org_code=%s,
                   status=%s, del_flag=%s, create_by=%s, create_time=%s, update_by=%s, update_time=%s,
                   tenant_id=%s, iz_leaf=%s, org_category=%s WHERE id=%s""",
                (parent_id, name, order, org_type, code, "1", "0", "admin", st(near(88, 9, 17)), "admin",
                 st(near(20, 9, 17)), 0, leaf, "1" if code == "A01" else "2", dep_id),
            )
        else:
            cur.execute(
                """INSERT INTO sys_depart (id, parent_id, depart_name, depart_order, org_type, org_code, status,
                   del_flag, create_by, create_time, update_by, update_time, tenant_id, iz_leaf, org_category)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (dep_id, parent_id, name, order, org_type, code, "1", "0", "admin", st(near(88, 9, 17)),
                 "admin", st(near(20, 9, 17)), 0, leaf, "1" if code == "A01" else "2"),
            )

    # 旧演示组织/岗位：逻辑下线，不物理删除
    cur.execute("UPDATE sys_depart SET del_flag='1' WHERE org_code IN ('A02','A02A01','A02A02','A01A05A01')")
    return ids


def seed_users(cur, dept_ids):
    cur.execute("SELECT id, username, org_code, phone, email, work_no FROM sys_user")
    existing = {r[1]: r for r in cur.fetchall()}
    used_phone = {r[3] for r in existing.values() if r[3]}
    used_email = {r[4] for r in existing.values() if r[4]}
    used_workno = {r[5] for r in existing.values() if r[5]}
    user_ids = []

    for idx, (username, realname, org_code, sex, identity) in enumerate(USERS, start=1):
        work_no = "XT%04d" % idx
        uid = uuid.uuid5(uuid.NAMESPACE_DNS, "r10.user." + work_no).hex
        if username in existing:
            uid = existing[username][0]
        phone = "%s%08d" % (random.choice(["138", "139", "137", "136", "135", "133", "132", "131", "130"]), 10000000 + idx * 7919)
        while phone in used_phone:
            phone = "%s%08d" % (random.choice(["138", "139", "137", "136", "135", "133", "132", "131", "130"]), random.randint(10000000, 99999999))
        used_phone.add(phone)
        email = work_no.lower() + "@xingtu-data.com"
        while email in used_email:
            email = work_no.lower() + str(random.randint(1, 99)) + "@xingtu-data.com"
        used_email.add(email)
        if work_no in used_workno and username not in existing:
            work_no = "XT%04d" % (idx + 100)
        created = near(max(5, 85 - idx), 9, 18)
        pwd, salt = jeecg_password(username, "123456", hashlib.md5(work_no.encode()).hexdigest()[:8])
        dept_id = dept_ids[org_code]
        if username in existing:
            cur.execute(
                """UPDATE sys_user SET realname=%s, salt=%s, password=%s, email=%s, phone=%s, org_code=%s,
                   status=1, del_flag=0, work_no=%s, user_identity=%s, update_by='admin', update_time=%s
                   WHERE id=%s""",
                (realname, salt, pwd, email, phone, org_code, work_no, identity, st(after(created)), uid),
            )
        else:
            cur.execute(
                """INSERT INTO sys_user (id, username, realname, password, salt, sex, email, phone, org_code,
                   status, del_flag, work_no, user_identity, create_by, create_time, update_by, update_time)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,1,0,%s,%s,'admin',%s,'admin',%s)""",
                (uid, username, realname, pwd, salt, sex, email, phone, org_code, work_no, identity,
                 st(created), st(after(created))),
            )
        user_ids.append((uid, username, realname, dept_id, created))
        # 部门归属（一人一部门）
        cur.execute("DELETE FROM sys_user_depart WHERE user_id=%s", (uid,))
        cur.execute("INSERT INTO sys_user_depart (ID, user_id, dep_id) VALUES (%s,%s,%s)",
                    (uuid.uuid4().hex, uid, dept_id))

    # 历史 jeecg 演示账号：改名停用，不删除
    if "jeecg" in existing:
        jid = existing["jeecg"][0]
        cur.execute("""UPDATE sys_user SET username='xt_legacy', realname='历史演示账号', status=2,
                       org_code='A01A02A02', update_by='admin', update_time=%s
                       WHERE id=%s AND username='jeecg'""", (st(NOW), jid))
        cur.execute("UPDATE sys_user_depart SET dep_id=%s WHERE user_id=%s", (dept_ids["A01A02A02"], jid))

    # 报表运营角色 + 授权 + 角色成员
    cur.execute("SELECT id FROM sys_role WHERE role_code='report_ops'")
    row = cur.fetchone()
    if row:
        ROLE_OPS = row[0]
    else:
        cur.execute("""INSERT INTO sys_role (id, role_name, role_code, description, create_by, create_time, tenant_id)
                       VALUES (%s,'报表运营','report_ops','报表平台业务人员角色','admin',%s,0)""",
                    (ROLE_OPS_ID, st(near(80))))
    for uid, username, realname, dept_id, created in user_ids:
        cur.execute("SELECT id FROM sys_user_role WHERE user_id=%s AND role_id=%s", (uid, ROLE_OPS_ID))
        if not cur.fetchone():
            cur.execute("INSERT INTO sys_user_role (id,user_id,role_id,tenant_id) VALUES (%s,%s,%s,0)",
                        (uuid.uuid4().hex, uid, ROLE_OPS_ID))
    return user_ids


# ---------------------------------------------------------------------------
# 业务数据写入
# ---------------------------------------------------------------------------
def seed_business(cur, users):
    for t in ("biz_subscription", "biz_report", "biz_dashboard", "biz_dataset"):
        cur.execute("DELETE FROM " + t)

    # 60 个数据集
    names = list(DATASET_NAMES)[:60]
    datasets = []
    for i, name in enumerate(names, start=1):
        owner = random.choice(users)
        created = near(random.randint(5, 89), 9, 18)
        status = random.choices([0, 1, 2], [12, 75, 13])[0]
        last_refresh = None if status == 0 else near(random.randint(0, 29), 6, 22)
        ds = dict(
            id=i, code="DS2026%04d" % i, name=name, source=random.choices([1, 2, 3, 4], [65, 18, 12, 5])[0],
            owner=owner, rows=random.choice([1280, 5600, 12800, 46000, 128000, 960000, 3800000, 12600000]),
            cycle=random.choices([1, 2, 3, 4], [20, 30, 40, 10])[0], status=status,
            refresh=last_refresh, remark="%s数据同步任务，已纳入数据资产目录。" % name,
            created=created, updated=after(created),
        )
        datasets.append(ds)
        cur.execute(
            """INSERT INTO biz_dataset (id,dataset_code,dataset_name,source_type,owner_id,owner_name,row_count,
               refresh_cycle,status,last_refresh_time,remark,create_by,create_time,update_by,update_time)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'admin',%s,'admin',%s)""",
            (ds["id"], ds["code"], ds["name"], ds["source"], owner[0], owner[2], ds["rows"], ds["cycle"],
             ds["status"], st(ds["refresh"]), ds["remark"], st(ds["created"]), st(ds["updated"])),
        )

    # 180 张报表：60 张分布在近 30 天（保证趋势图每天有数），75 张 31~90 天，27 草稿，18 下线
    recent_days = [TODAY - dt.timedelta(days=i) for i in range(29, -1, -1)]
    reports = []
    seq = 0
    for category in range(1, 6):
        for period in REPORT_PERIODS:
            for base in REPORT_BASES[category]:
                seq += 1
                status = 1
                if seq <= 60:
                    publish = day_time(recent_days[(seq - 1) % 30])
                elif seq <= 135:
                    publish = near(random.randint(31, 90), 8, 21)
                elif seq <= 162:
                    status = 0
                    publish = None
                else:
                    status = 2
                    publish = near(random.randint(31, 90), 8, 21)
                created = (publish - dt.timedelta(days=random.randint(1, 10))) if publish else near(random.randint(3, 80), 9, 18)
                if created < NOW - dt.timedelta(days=90):
                    created = NOW - dt.timedelta(days=90) + dt.timedelta(minutes=random.randint(1, 600))
                owner = random.choice(users)
                report = dict(
                    id=seq, code="RP2026%04d" % seq, name="%s%s" % (period, base),
                    dataset=random.randint(1, 60), category=category, chart=random.choices([1, 2, 3, 4, 5], [30, 24, 26, 15, 5])[0],
                    owner=owner, views=0 if status == 0 else random.randint(30, 9800), status=status,
                    publish=publish, remark=("面向%s条线的%s分析报表。" % (["", "经营管理", "财务管理", "运营管理", "人力管理", "风险管理"][category], period)),
                    created=created, updated=after(created if not publish else publish, 3),
                )
                reports.append(report)

    for r in reports:
        cur.execute(
            """INSERT INTO biz_report (id,report_code,report_name,dataset_id,category,chart_type,owner_id,owner_name,
               view_count,status,publish_time,remark,create_by,create_time,update_by,update_time)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'admin',%s,'admin',%s)""",
            (r["id"], r["code"], r["name"], r["dataset"], r["category"], r["chart"], r["owner"][0], r["owner"][2],
             r["views"], r["status"], st(r["publish"]), r["remark"], st(r["created"]), st(r["updated"])),
        )

    # 40 个看板
    for i, name in enumerate(DASHBOARD_NAMES, start=1):
        owner = random.choice(users)
        created = near(random.randint(5, 89), 9, 18)
        status = random.choices([0, 1, 2], [15, 70, 15])[0]
        cur.execute(
            """INSERT INTO biz_dashboard (id,dashboard_code,dashboard_name,owner_id,owner_name,layout_type,
               widget_count,share_scope,status,remark,create_by,create_time,update_by,update_time)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'admin',%s,'admin',%s)""",
            (i, "DB2026%03d" % i, name, owner[0], owner[2], random.randint(1, 4),
             random.randint(4, 28), random.choices([1, 2, 3], [30, 45, 25])[0], status,
             "%s，支持移动端与大屏投放。" % name, st(created), st(after(created))),
        )

    # 200 个订阅
    for i in range(1, 201):
        user = random.choice(users)
        report = random.choice(reports)
        created = near(random.randint(5, 89), 9, 18)
        enabled = random.choices([0, 1], [82, 18])[0]
        cur.execute(
            """INSERT INTO biz_subscription (id,subscription_code,report_id,subscriber_id,subscriber_name,channel,
               cron_expr,last_send_time,send_count,status,remark,create_by,create_time,update_by,update_time)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'admin',%s,'admin',%s)""",
            (i, "SB2026%04d" % i, report["id"], user[0], user[2],
             random.choices([1, 2, 3], [45, 35, 20])[0], random.choice(CRON_EXPRS),
             st(near(random.randint(0, 29), 7, 21)), random.randint(1, 480), enabled,
             "按计划向订阅人推送《%s》。" % report["name"], st(created), st(after(created))),
        )

    return datasets, reports


# ---------------------------------------------------------------------------
# 菜单 / 授权
# ---------------------------------------------------------------------------
def next_permission_id(cur, used):
    cur.execute("SELECT MAX(CAST(id AS UNSIGNED)) FROM sys_permission WHERE id REGEXP '^[0-9]+$'")
    val = cur.fetchone()[0] or 1900000000000000000
    nid = int(val) + 1
    while str(nid) in used:
        nid += 1
    used.add(str(nid))
    return str(nid)


def ensure_menu(cur, used, parent_id, name, url, component, menu_type, perms, sort_no, icon, is_leaf):
    cur.execute("SELECT id FROM sys_permission WHERE url=%s AND name=%s AND del_flag=0 ORDER BY id LIMIT 1", (url, name))
    row = cur.fetchone()
    if row:
        pid = row[0]
        cur.execute("""UPDATE sys_permission SET parent_id=%s, component=%s, menu_type=%s, perms=%s,
                       sort_no=%s, icon=%s, is_route=1, is_leaf=%s, hidden=0, status='1', del_flag=0,
                       update_by='admin', update_time=%s WHERE id=%s""",
                    (parent_id, component, menu_type, perms, sort_no, icon, is_leaf, st(near(1)), pid))
        return pid
    pid = next_permission_id(cur, used)
    cur.execute(
        """INSERT INTO sys_permission (id,parent_id,name,url,component,is_route,menu_type,perms,perms_type,
           sort_no,always_show,icon,is_leaf,keep_alive,hidden,hide_tab,description,create_by,create_time,
           update_by,update_time,del_flag,rule_flag,status,internal_or_external)
           VALUES (%s,%s,%s,%s,%s,1,%s,%s,'0',%s,0,%s,%s,1,0,0,%s,'admin',%s,'admin',%s,0,0,'1',0)""",
        (pid, parent_id, name, url, component, menu_type, perms, sort_no, icon, is_leaf,
         name + "菜单", st(near(5)), st(near(1))),
    )
    return pid


def seed_menus(cur):
    used = set()
    cur.execute("SELECT id FROM sys_permission")
    used.update(r[0] for r in cur.fetchall())

    # 旧的“统计报表”目录与新的“数据报表”同 url(/report)，保留数据但隐藏，避免路由重复
    cur.execute("UPDATE sys_permission SET hidden=1 WHERE id='1447763172274495489'")
    # 下线演示/低代码/租户等与报表平台无关的导航，仅隐藏、不删除
    cur.execute("""UPDATE sys_permission SET hidden=1
                   WHERE url IN ('/comp','/page-demo','/online','/system','/tenant/setting','/mytenant')""")

    dir_id = ensure_menu(cur, used, None, "数据报表", "/report", "layouts/RouteView", 0, None, 1.50,
                         "ant-design:bar-chart-outlined", 0)
    dataset_id = ensure_menu(cur, used, dir_id, "数据集管理", "/report/dataset", "report/dataset/index", 1,
                             "report:dataset:list", 1.00, "ant-design:database-outlined", 1)
    report_id = ensure_menu(cur, used, dir_id, "报表管理", "/report/report", "report/report/index", 1,
                            "report:report:list", 2.00, "ant-design:fund-outlined", 1)
    subscription_id = ensure_menu(cur, used, dir_id, "订阅管理", "/report/subscription", "report/subscription/index", 1,
                                  "report:subscription:list", 3.00, "ant-design:mail-outlined", 1)

    # 去品牌化：只改名称，不删除既有菜单
    cur.execute("UPDATE sys_permission SET name='组件示例' WHERE name='Jeecg组件示例'")
    cur.execute("UPDATE sys_permission SET name='帮助中心' WHERE name='JEECG官网'")
    cur.execute("UPDATE sys_permission SET name='多报表样例' WHERE name='积木报表例子'")
    cur.execute("UPDATE sys_permission SET name='数据大屏样例' WHERE name='积木大屏案例'")
    cur.execute("UPDATE sys_permission SET name='工作台' WHERE id='1438108176273760258'")
    cur.execute("UPDATE sys_permission SET name='关于平台' WHERE id='1438108225451974658'")

    for role_id in (ROLE_ADMIN_ID, ROLE_OPS_ID):
        for pid in (dir_id, dataset_id, report_id, subscription_id):
            cur.execute("SELECT id FROM sys_role_permission WHERE role_id=%s AND permission_id=%s", (role_id, pid))
            if not cur.fetchone():
                cur.execute("""INSERT INTO sys_role_permission (id, role_id, permission_id, operate_date)
                               VALUES (%s,%s,%s,%s)""", (uuid.uuid4().hex, role_id, pid, st(near(2))))


# ---------------------------------------------------------------------------
# 日志
# ---------------------------------------------------------------------------
LOGIN_IPS = ["127.0.0.1", "10.20.8.%d", "10.20.9.%d", "192.168.30.%d", "172.18.4.%d"]
OPERATIONS = [
    ("数据集-新增", 2, "org.jeecg.modules.report.controller.ReportController.datasetList", "/report/dataset/list", "GET"),
    ("数据集-刷新", 2, "org.jeecg.modules.report.controller.ReportController.datasetList", "/report/dataset/list", "GET"),
    ("数据集-发布", 1, "org.jeecg.modules.report.controller.ReportController.datasetList", "/report/dataset/list", "GET"),
    ("报表-新增", 2, "org.jeecg.modules.report.controller.ReportController.reportList", "/report/report/list", "GET"),
    ("报表-编辑", 3, "org.jeecg.modules.report.controller.ReportController.reportList", "/report/report/list", "GET"),
    ("报表-发布", 3, "org.jeecg.modules.report.controller.ReportController.reportList", "/report/report/list", "GET"),
    ("报表-导出", 6, "org.jeecg.modules.report.controller.ReportController.reportList", "/report/report/list", "GET"),
    ("看板-新增", 2, "org.jeecg.modules.report.controller.ReportController.dashboardList", "/report/dashboard/list", "GET"),
    ("看板-分享", 3, "org.jeecg.modules.report.controller.ReportController.dashboardList", "/report/dashboard/list", "GET"),
    ("订阅-新增", 2, "org.jeecg.modules.report.controller.ReportController.subscriptionList", "/report/subscription/list", "GET"),
    ("订阅-启用", 3, "org.jeecg.modules.report.controller.ReportController.subscriptionList", "/report/subscription/list", "GET"),
    ("订阅-停用", 3, "org.jeecg.modules.report.controller.ReportController.subscriptionList", "/report/subscription/list", "GET"),
    ("订阅-立即发送", 5, "org.jeecg.modules.report.controller.ReportController.subscriptionList", "/report/subscription/list", "GET"),
    ("统计-总览查询", 1, "org.jeecg.modules.report.controller.ReportController.overview", "/report/stats/overview", "GET"),
]


def seed_logs(cur, users):
    cur.execute("DELETE FROM sys_log WHERE create_by=%s", (SEED_TAG,))

    def ip():
        tpl = random.choice(LOGIN_IPS)
        if "%d" in tpl:
            return tpl % random.randint(2, 250)
        return tpl

    all_users = [("admin", "管理员")] + [(u[1], u[2]) for u in users]
    rows = []
    for _ in range(180):
        username, realname = random.choice(all_users)
        t = near(random.randint(0, 29), 7, 22)
        rows.append((uuid.uuid4().hex, 1, "用户名: %s,登录成功！" % username, None, username, realname, ip(),
                     None, None, None, None, None, SEED_TAG, st(t)))
    for _ in range(320):
        username, realname = random.choice(all_users)
        content, otype, method, url, rtype = random.choice(OPERATIONS)
        t = near(random.randint(0, 29), 8, 21)
        rows.append((uuid.uuid4().hex, 2, content, otype, username, realname, ip(), method, url,
                     '{"pageNo":1,"pageSize":10}', rtype, random.randint(5, 860), SEED_TAG, st(t)))

    cur.executemany(
        """INSERT INTO sys_log (id,log_type,log_content,operate_type,userid,username,ip,method,request_url,
           request_param,request_type,cost_time,create_by,create_time)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        [(r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8], r[9], r[10], r[11], r[12], r[13]) for r in rows],
    )


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def main():
    conn = pymysql.connect(**DB, autocommit=False)
    try:
        with conn.cursor() as cur:
            for ddl in DDL:
                cur.execute(ddl)
            dept_ids = seed_org(cur)
            users = seed_users(cur, dept_ids)
            datasets, reports = seed_business(cur, users)
            seed_menus(cur)
            seed_logs(cur, users)
        conn.commit()

        with conn.cursor() as cur:
            for t in ("biz_dataset", "biz_report", "biz_dashboard", "biz_subscription"):
                cur.execute("SELECT COUNT(*) FROM " + t)
                print("%-16s %s" % (t, cur.fetchone()[0]))
            cur.execute("SELECT COUNT(*) FROM sys_depart WHERE del_flag='0' AND org_code LIKE 'A01%%'")
            print("sys_depart(A01) %s" % cur.fetchone()[0])
            cur.execute("SELECT COUNT(*) FROM sys_user WHERE work_no LIKE 'XT%%' AND del_flag=0")
            print("sys_user(XT)     %s" % cur.fetchone()[0])
            cur.execute("SELECT COUNT(*) FROM sys_permission WHERE url LIKE '/report/%%' AND del_flag=0")
            print("report menus     %s" % cur.fetchone()[0])
            cur.execute("SELECT COUNT(*) FROM sys_log WHERE log_type=1 AND create_time >= %s", (NOW - dt.timedelta(days=30),))
            print("login logs 30d   %s" % cur.fetchone()[0])
            cur.execute("SELECT COUNT(*) FROM sys_log WHERE log_type=2 AND create_time >= %s", (NOW - dt.timedelta(days=30),))
            print("oper  logs 30d   %s" % cur.fetchone()[0])
        print("R10 seed done at %s" % st(NOW))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
