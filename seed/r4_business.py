#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R4 梧州市长洲区教育局 —— 学籍管理业务数据 / 组织架构 / 日志 种子脚本
=====================================================================
目标库：MySQL 127.0.0.1:13307 / ry_r4
说明：
  1. 重建 biz_school / biz_class / biz_student / biz_score 四张业务表；
  2. 重建 26 个节点的部门树，保留 admin 与 scanner_low，重建 30 名员工；
  3. 重建「业务管理」菜单及其子菜单、按钮权限，仅给 role_id=1 补授权；
  4. 重灌登录日志与操作日志（近 30 天，工作日多、无未来时间）；
  5. 可重复执行，完整 SQL 落盘到 seed/r4_business.sql。

用法：python seed/r4_business.py
"""
import datetime as dt
import hashlib
import os
import random

import pymysql
from pymysql.converters import escape_string

DB = dict(host="127.0.0.1", port=13307, user="root", password="", database="ry_r4", charset="utf8mb4")

TODAY = dt.date.today()
NOW = dt.datetime.now().replace(microsecond=0)
SEED = 20261030
random.seed(SEED)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SQL_FILE = os.path.join(BASE_DIR, "r4_business.sql")

DEFAULT_SALT = "111111"
RY_SALT = "222222"
DEFAULT_PASSWORD = "admin123"


def pw_hash(login_name, password, salt):
    """RuoYi 4.x 口令算法：MD5(loginName + password + salt)。"""
    return hashlib.md5((login_name + password + salt).encode("utf-8")).hexdigest()


# ----------------------------------------------------------------------------
# 组织架构（26 个节点，3 层，ID 固定）
# ----------------------------------------------------------------------------
# (dept_id, parent_id, dept_name, order_num, leader)
DEPTS = [
    (100, 0, "梧州市长洲区教育局", 0, "罗建平"),
    (101, 100, "办公室", 1, "陈丽华"),
    (102, 100, "基础教育科", 2, "李国强"),
    (103, 100, "人事科", 3, "覃海涛"),
    (104, 100, "财务科", 4, "蒙伟"),
    (105, 100, "督导室", 5, "卢建华"),
    (106, 100, "教研室", 6, "吴文静"),
    (110, 100, "长洲中学", 7, "潘玉兰"),
    (111, 100, "新兴路小学", 8, "刘伟东"),
    (112, 100, "大塘小学", 9, "陈桂芳"),
    (113, 100, "倒水镇中心小学", 10, "甘秀珍"),
    (114, 100, "长地小学", 11, "李凤"),
    (115, 100, "正阳小学", 12, "黄德明"),
    (116, 100, "龙新小学", 13, "周永强"),
    (117, 100, "泗洲小学", 14, "罗小红"),
    (120, 101, "综合档案室", 1, "韦晓东"),
    (121, 101, "政务服务中心", 2, "周敏"),
    (122, 102, "学籍管理组", 1, "黄小燕"),
    (123, 102, "招生管理组", 2, "邓志明"),
    (124, 103, "师训组", 1, "苏丽娟"),
    (125, 104, "会计核算中心", 1, "农秀英"),
    (126, 106, "学科教研组", 1, "钟志刚"),
    (130, 110, "长洲中学教务处", 1, "何建军"),
    (131, 110, "长洲中学政教处", 2, "唐红梅"),
    (132, 111, "新兴路小学教导处", 1, "杨小玲"),
    (133, 112, "大塘小学教导处", 1, "梁志强"),
    (134, 113, "倒水镇中心小学教导处", 1, "韦国强"),
]
DEPT_NAME = {d[0]: d[2] for d in DEPTS}

# (user_id, 姓名, dept_id, 岗位, 性别)  性别：0男 1女
EMPLOYEES = [
    (2001, "罗建平", 100, "局长", "0"),
    (2002, "梁俊杰", 100, "副局长", "0"),
    (2003, "陈丽华", 101, "办公室主任", "1"),
    (2004, "韦晓东", 120, "档案管理员", "0"),
    (2005, "周敏", 121, "政务服务窗口员", "1"),
    (2006, "李国强", 102, "基础教育科科长", "0"),
    (2007, "黄小燕", 122, "学籍管理员", "1"),
    (2008, "邓志明", 123, "招生管理员", "0"),
    (2009, "覃海涛", 103, "人事科科长", "0"),
    (2010, "苏丽娟", 124, "师训干事", "1"),
    (2011, "蒙伟", 104, "财务科科长", "0"),
    (2012, "农秀英", 125, "会计", "1"),
    (2013, "卢建华", 105, "督导室主任", "0"),
    (2014, "吴文静", 106, "教研室主任", "1"),
    (2015, "钟志刚", 126, "语文教研员", "0"),
    (2016, "潘玉兰", 110, "长洲中学校长", "1"),
    (2017, "何建军", 130, "长洲中学教务主任", "0"),
    (2018, "唐红梅", 131, "长洲中学政教主任", "1"),
    (2019, "刘伟东", 111, "新兴路小学校长", "0"),
    (2020, "杨小玲", 132, "新兴路小学教导主任", "1"),
    (2021, "陈桂芳", 112, "大塘小学校长", "1"),
    (2022, "梁志强", 133, "大塘小学教导主任", "0"),
    (2023, "甘秀珍", 113, "倒水镇中心小学校长", "1"),
    (2024, "韦国强", 134, "倒水镇中心小学教导主任", "0"),
    (2025, "李凤", 114, "长地小学校长", "1"),
    (2026, "黄德明", 115, "正阳小学校长", "0"),
    (2027, "周永强", 116, "龙新小学校长", "0"),
    (2028, "罗小红", 117, "泗洲小学校长", "1"),
    (2029, "覃丽", 105, "督学", "1"),
    (2030, "邓文", 106, "数学教研员", "0"),
]
# 工号规则：CZ0001 起顺序排（user_id 2001 -> CZ0001，2030 -> CZ0030）
EMP_LOGIN = {e[0]: "CZ%04d" % (i + 1) for i, e in enumerate(EMPLOYEES)}

# ry（user_id=2，salt 保持 222222）改造为真实员工
RY_EMPLOYEE = (2, "严志辉", 122, "学籍管理员", "0", "CZ0031")


def phone():
    return random.choice(["138", "139", "189"]) + "".join(random.choice("0123456789") for _ in range(8))


def email_for(login_name):
    return "%s@czjy.gov.cn" % login_name.lower()


# ----------------------------------------------------------------------------
# 业务表结构
# ----------------------------------------------------------------------------
DDL = [
    "DROP TABLE IF EXISTS biz_score",
    "DROP TABLE IF EXISTS biz_student",
    "DROP TABLE IF EXISTS biz_class",
    "DROP TABLE IF EXISTS biz_school",
    """CREATE TABLE biz_school (
  school_id bigint(20) NOT NULL AUTO_INCREMENT COMMENT '学校ID',
  school_code varchar(20) NOT NULL COMMENT '学校代码',
  school_name varchar(100) NOT NULL COMMENT '学校名称',
  school_type varchar(30) DEFAULT NULL COMMENT '学校类型',
  address varchar(200) DEFAULT NULL COMMENT '学校地址',
  principal varchar(30) DEFAULT NULL COMMENT '校长',
  phone varchar(20) DEFAULT NULL COMMENT '联系电话',
  class_count int(11) DEFAULT '0' COMMENT '班级数',
  student_count int(11) DEFAULT '0' COMMENT '学生数',
  teacher_count int(11) DEFAULT '0' COMMENT '教师数',
  build_date date DEFAULT NULL COMMENT '建校日期',
  status char(1) DEFAULT '0' COMMENT '状态（0正常 1停办）',
  create_by varchar(64) DEFAULT NULL COMMENT '创建者',
  create_time datetime DEFAULT NULL COMMENT '创建时间',
  update_by varchar(64) DEFAULT NULL COMMENT '更新者',
  update_time datetime DEFAULT NULL COMMENT '更新时间',
  remark varchar(500) DEFAULT NULL COMMENT '备注',
  PRIMARY KEY (school_id),
  UNIQUE KEY uk_biz_school_code (school_code),
  KEY idx_biz_school_name (school_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='学校信息'""",
    """CREATE TABLE biz_class (
  class_id bigint(20) NOT NULL AUTO_INCREMENT COMMENT '班级ID',
  class_code varchar(32) NOT NULL COMMENT '班级编码',
  class_name varchar(50) NOT NULL COMMENT '班级名称',
  school_id bigint(20) NOT NULL COMMENT '学校ID',
  school_name varchar(100) DEFAULT NULL COMMENT '学校名称',
  grade varchar(20) DEFAULT NULL COMMENT '年级',
  grade_no int(11) DEFAULT NULL COMMENT '年级序号',
  head_teacher varchar(30) DEFAULT NULL COMMENT '班主任',
  student_count int(11) DEFAULT '0' COMMENT '班级人数',
  classroom varchar(50) DEFAULT NULL COMMENT '教室',
  status char(1) DEFAULT '0' COMMENT '状态（0正常 1撤销）',
  create_by varchar(64) DEFAULT NULL COMMENT '创建者',
  create_time datetime DEFAULT NULL COMMENT '创建时间',
  update_by varchar(64) DEFAULT NULL COMMENT '更新者',
  update_time datetime DEFAULT NULL COMMENT '更新时间',
  remark varchar(500) DEFAULT NULL COMMENT '备注',
  PRIMARY KEY (class_id),
  UNIQUE KEY uk_biz_class_code (class_code),
  KEY idx_biz_class_school (school_id),
  KEY idx_biz_class_grade (grade_no)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='班级信息'""",
    """CREATE TABLE biz_student (
  student_id bigint(20) NOT NULL AUTO_INCREMENT COMMENT '学生ID',
  student_no varchar(32) NOT NULL COMMENT '学籍号',
  student_name varchar(30) NOT NULL COMMENT '姓名',
  gender char(1) DEFAULT '0' COMMENT '性别（0男 1女）',
  birth_date date DEFAULT NULL COMMENT '出生日期',
  id_card varchar(18) DEFAULT NULL COMMENT '身份证号',
  school_id bigint(20) DEFAULT NULL COMMENT '学校ID',
  school_name varchar(100) DEFAULT NULL COMMENT '学校名称',
  class_id bigint(20) DEFAULT NULL COMMENT '班级ID',
  class_name varchar(50) DEFAULT NULL COMMENT '班级名称',
  grade varchar(20) DEFAULT NULL COMMENT '年级',
  grade_no int(11) DEFAULT NULL COMMENT '年级序号',
  enroll_date date DEFAULT NULL COMMENT '入学日期',
  guardian varchar(30) DEFAULT NULL COMMENT '监护人',
  guardian_phone varchar(11) DEFAULT NULL COMMENT '监护人电话',
  address varchar(200) DEFAULT NULL COMMENT '家庭住址',
  status char(1) DEFAULT '0' COMMENT '状态（0在读 1休学 2转出 3毕业）',
  audit_status char(1) DEFAULT '1' COMMENT '审核状态（0待审核 1已通过 2已退回）',
  create_by varchar(64) DEFAULT NULL COMMENT '创建者',
  create_time datetime DEFAULT NULL COMMENT '创建时间',
  update_by varchar(64) DEFAULT NULL COMMENT '更新者',
  update_time datetime DEFAULT NULL COMMENT '更新时间',
  remark varchar(500) DEFAULT NULL COMMENT '备注',
  PRIMARY KEY (student_id),
  UNIQUE KEY uk_biz_student_no (student_no),
  UNIQUE KEY uk_biz_student_idcard (id_card),
  KEY idx_biz_student_name (student_name),
  KEY idx_biz_student_school (school_id),
  KEY idx_biz_student_class (class_id),
  KEY idx_biz_student_audit (audit_status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='学生学籍信息'""",
    """CREATE TABLE biz_score (
  score_id bigint(20) NOT NULL AUTO_INCREMENT COMMENT '成绩ID',
  exam_no varchar(32) NOT NULL COMMENT '考试编号',
  student_no varchar(32) DEFAULT NULL COMMENT '学籍号',
  student_name varchar(30) DEFAULT NULL COMMENT '姓名',
  school_id bigint(20) DEFAULT NULL COMMENT '学校ID',
  school_name varchar(100) DEFAULT NULL COMMENT '学校名称',
  class_id bigint(20) DEFAULT NULL COMMENT '班级ID',
  class_name varchar(50) DEFAULT NULL COMMENT '班级名称',
  grade varchar(20) DEFAULT NULL COMMENT '年级',
  subject varchar(20) DEFAULT NULL COMMENT '科目',
  exam_name varchar(100) DEFAULT NULL COMMENT '考试名称',
  exam_date date DEFAULT NULL COMMENT '考试日期',
  score decimal(5,1) DEFAULT '0.0' COMMENT '分数',
  full_score decimal(5,1) DEFAULT '100.0' COMMENT '满分',
  score_level char(1) DEFAULT NULL COMMENT '等级（A/B/C/D）',
  class_rank int(11) DEFAULT NULL COMMENT '班级排名',
  term varchar(20) DEFAULT NULL COMMENT '学期',
  create_by varchar(64) DEFAULT NULL COMMENT '创建者',
  create_time datetime DEFAULT NULL COMMENT '创建时间',
  update_by varchar(64) DEFAULT NULL COMMENT '更新者',
  update_time datetime DEFAULT NULL COMMENT '更新时间',
  remark varchar(500) DEFAULT NULL COMMENT '备注',
  PRIMARY KEY (score_id),
  KEY idx_biz_score_exam (exam_no),
  KEY idx_biz_score_student (student_no),
  KEY idx_biz_score_class (class_id),
  KEY idx_biz_score_subject (subject),
  KEY idx_biz_score_date (exam_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='学生成绩'""",
]

# ----------------------------------------------------------------------------
# 学校
# ----------------------------------------------------------------------------
# (school_id, code, name, type, address, principal, phone, class_count, student_count, teacher_count, build_date)
SCHOOLS = [
    (1, "CZ001", "长洲中学", "初级中学", "长洲区新兴二路18号", "潘玉兰", "0774-3821001", 12, 336, 86, dt.date(1998, 9, 1)),
    (2, "CZ002", "新兴路小学", "完全小学", "长洲区新兴一路66号", "刘伟东", "0774-3821002", 18, 468, 74, dt.date(2001, 9, 1)),
    (3, "CZ003", "大塘小学", "完全小学", "长洲区大塘路12号", "陈桂芳", "0774-3821003", 18, 450, 71, dt.date(1996, 9, 1)),
    (4, "CZ004", "倒水镇中心小学", "完全小学", "长洲区倒水镇正阳街8号", "甘秀珍", "0774-3821004", 15, 375, 62, dt.date(1995, 9, 1)),
    (5, "CZ005", "长地小学", "完全小学", "长洲区长地路35号", "李凤", "0774-3821005", 9, 207, 38, dt.date(2004, 9, 1)),
    (6, "CZ006", "正阳小学", "完全小学", "长洲区正阳路21号", "黄德明", "0774-3821006", 9, 216, 40, dt.date(2007, 9, 1)),
    (7, "CZ007", "龙新小学", "完全小学", "长洲区龙新路9号", "周永强", "0774-3821007", 9, 198, 36, dt.date(2010, 9, 1)),
    (8, "CZ008", "泗洲小学", "完全小学", "长洲区泗洲岛洲头路6号", "罗小红", "0774-3821008", 6, 150, 29, dt.date(2012, 9, 1)),
]

# 各校年级班级分配，合计必须等于班级数
GRADE_PLAN = {
    1: {7: 4, 8: 4, 9: 4},
    2: {1: 3, 2: 3, 3: 3, 4: 3, 5: 3, 6: 3},
    3: {1: 3, 2: 3, 3: 3, 4: 3, 5: 3, 6: 3},
    4: {1: 3, 2: 3, 3: 2, 4: 2, 5: 2, 6: 3},
    5: {1: 2, 2: 2, 3: 1, 4: 1, 5: 1, 6: 2},
    6: {1: 1, 2: 2, 3: 2, 4: 1, 5: 2, 6: 1},
    7: {1: 1, 2: 2, 3: 1, 4: 2, 5: 1, 6: 2},
    8: {1: 1, 2: 1, 3: 1, 4: 1, 5: 1, 6: 1},
}

GRADE_CN = {1: "一年级", 2: "二年级", 3: "三年级", 4: "四年级", 5: "五年级",
            6: "六年级", 7: "七年级", 8: "八年级", 9: "九年级"}

SURNAMES = "李黄梁覃韦陈吴罗蒙甘蓝苏何唐杨刘卢钟潘陆周农邓莫林张谢曾廖石秦肖阮岑宁"
MALE_GIVEN = ["建平", "俊杰", "晓东", "国强", "志明", "海涛", "伟东", "志刚", "德明", "永强",
              "文杰", "家强", "少华", "锦华", "树林", "启明", "达强", "光远", "庆华", "海峰",
              "志远", "伟明", "国华", "建华", "海波", "永红", "伟成", "明辉", "宇航", "浩然",
              "子轩", "俊宇", "嘉豪", "天佑", "泽宇", "梓豪", "博文", "思远", "文豪", "志强"]
FEMALE_GIVEN = ["丽华", "小燕", "秀英", "玉兰", "丽娟", "文静", "红梅", "桂芳", "秀珍", "小玲",
                "凤", "小红", "覃丽", "春梅", "秀兰", "桂英", "美玲", "海燕", "小梅", "永红",
                "水莲", "金凤", "晓红", "丽萍", "雅婷", "雨欣", "诗涵", "梦琪", "佳怡", "思琪",
                "欣怡", "子涵", "梓涵", "静怡", "丽娜", "慧敏", "晓燕", "雪梅", "春燕", "秀梅"]
ROADS = ["新兴二路", "新兴一路", "新兴三路", "大塘路", "正阳路", "龙新路", "长地路", "泗洲岛洲头路",
         "西堤路", "富民路", "中山路", "文澜路", "西江路", "红岭路", "三龙大道", "苍海大道",
         "桂江路", "鸳江路", "民主路", "和平路", "步埠路", "塘源路", "莲花山路", "京梧路"]


def person_name(gender=None):
    if gender is None:
        gender = random.choice(["0", "1"])
    given = MALE_GIVEN if gender == "0" else FEMALE_GIVEN
    return random.choice(SURNAMES) + random.choice(given)


def class_allocation():
    base_count = {s[0]: s[8] // s[7] for s in SCHOOLS}
    result = {}
    for s in SCHOOLS:
        sid, cnt = s[0], s[7]
        plan = []
        for g, n in sorted(GRADE_PLAN[sid].items()):
            plan.extend([g] * n)
        result[sid] = plan
    return base_count, result


def build_schools():
    rows = []
    for sid, code, name, stype, addr, principal, ph, cc, sc, tc, bdate in SCHOOLS:
        rows.append(dict(
            school_id=sid, school_code=code, school_name=name, school_type=stype,
            address=addr, principal=principal, phone=ph, class_count=cc,
            student_count=sc, teacher_count=tc, build_date=bdate, status="0",
            create_by="admin", create_time=dt.datetime(2024, 3, 12, 9, 20, 0),
            update_by="admin", update_time=NOW - dt.timedelta(days=random.randint(30, 300)),
            remark="区属公办学校",
        ))
    return rows


def build_classes():
    base_count, alloc = class_allocation()
    rows = []
    cid = 0
    for s in SCHOOLS:
        sid, code, name = s[0], s[1], s[2]
        per = base_count[sid]
        seq_by_grade = {}
        used_teachers = set()
        for g in alloc[sid]:
            seq_by_grade[g] = seq_by_grade.get(g, 0) + 1
            cid += 1
            while True:
                ht = person_name()
                if ht not in used_teachers:
                    used_teachers.add(ht)
                    break
            building = "教学楼A" if g >= 7 else "教学楼B"
            room = "%s-%d%02d" % (building, ((cid - 1) % 4) + 1, ((cid - 1) % 12) + 1)
            created = dt.datetime(2024, 8, 25, 10, 0, 0) + dt.timedelta(days=random.randint(0, 20))
            rows.append(dict(
                class_id=cid, class_code="%s%02d%02d" % (code, g, seq_by_grade[g]),
                class_name="%s%d班" % (GRADE_CN[g], seq_by_grade[g]), school_id=sid,
                school_name=name, grade=GRADE_CN[g], grade_no=g, head_teacher=ht,
                student_count=per, classroom=room, status="0", create_by="admin",
                create_time=created, update_by="admin",
                update_time=NOW - dt.timedelta(days=random.randint(10, 200)), remark="",
            ))
    return rows


# ----------------------------------------------------------------------------
# 学生
# ----------------------------------------------------------------------------
def enroll_year(grade_no):
    if grade_no <= 6:
        return 2026 - (grade_no - 1)
    return 2026 - (grade_no - 7)


def birth_range(grade_no):
    by = 2020 - (grade_no - 1)
    return dt.date(by - 1, 9, 1), dt.date(by, 8, 31)


def rand_date(start, end):
    return start + dt.timedelta(days=random.randint(0, (end - start).days))


def id_card_check(first17):
    weights = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
    codes = "10X98765432"
    total = sum(int(first17[i]) * weights[i] for i in range(17))
    return first17 + codes[total % 11]


def build_students(classes):
    rows = []
    seq = 0
    used_cards = set()
    for c in classes:
        for _ in range(c["student_count"]):
            seq += 1
            g = c["grade_no"]
            gender = "0" if random.random() < 0.52 else "1"
            name = person_name(gender)
            bstart, bend = birth_range(g)
            bdate = rand_date(bstart, bend)
            while True:
                first17 = "450405" + bdate.strftime("%Y%m%d") + "".join(random.choice("0123456789") for _ in range(3))
                card = id_card_check(first17)
                if card not in used_cards:
                    used_cards.add(card)
                    break
            ey = enroll_year(g)
            enroll = dt.date(ey, 9, 1)
            r = random.random()
            if r < 0.02:
                status = "1"
            elif r < 0.05:
                status = "2"
            elif g == 9 and r < 0.17:
                status = "3"
            else:
                status = "0"
            guardian = name[0] + random.choice(MALE_GIVEN + FEMALE_GIVEN)
            created = dt.datetime.combine(enroll, dt.time(random.randint(8, 17), random.randint(0, 59), random.randint(0, 59)))
            created += dt.timedelta(days=random.randint(0, 30))
            if created > NOW:
                created = NOW - dt.timedelta(days=random.randint(0, 20), minutes=random.randint(0, 600))
            updated = created + dt.timedelta(days=random.randint(1, 120), minutes=random.randint(0, 600))
            if updated > NOW:
                updated = NOW - dt.timedelta(minutes=random.randint(5, 600))
            rows.append(dict(
                student_id=seq, student_no="GX%d%06d" % (ey, seq), student_name=name,
                gender=gender, birth_date=bdate, id_card=card, school_id=c["school_id"],
                school_name=c["school_name"], class_id=c["class_id"], class_name=c["class_name"],
                grade=c["grade"], grade_no=g, enroll_date=enroll, guardian=guardian,
                guardian_phone=phone(),
                address="长洲区%s%d号" % (random.choice(ROADS), random.randint(1, 360)),
                status=status, audit_status="1", create_by="admin", create_time=created,
                update_by="admin", update_time=updated, remark="",
            ))

    # 审核状态：待审核固定 40 条（用于首页待办），已退回固定 15 条
    idx = list(range(len(rows)))
    pending = set(random.sample(idx, 40))
    rest = [i for i in idx if i not in pending]
    returned = set(random.sample(rest, 15))
    for i in pending:
        rows[i]["audit_status"] = "0"
        rows[i]["create_time"] = NOW - dt.timedelta(days=random.randint(0, 12),
                                                    hours=random.randint(0, 10),
                                                    minutes=random.randint(0, 59))
        rows[i]["update_time"] = None
    for i in returned:
        rows[i]["audit_status"] = "2"
    return rows


# ----------------------------------------------------------------------------
# 成绩
# ----------------------------------------------------------------------------
MAIN_SUBJECTS = ["语文", "数学", "英语"]
EXTRA_SUBJECTS = ["物理", "化学", "科学", "道德与法治"]


def score_level(v):
    if v >= 85:
        return "A"
    if v >= 70:
        return "B"
    if v >= 60:
        return "C"
    return "D"


def clamp_score(mean):
    return round(min(100.0, max(35.0, random.gauss(mean, 12))), 1)


def build_scores(students):
    rows = []
    sid = 0
    exam_seq = {}

    def next_exam_no(ym, key):
        if key not in exam_seq:
            exam_seq[key] = len(exam_seq) + 1
        return "EX%s%05d" % (ym, exam_seq[key])

    main_date = dt.date(2026, 6, 26)
    for st in students:
        for subj in MAIN_SUBJECTS:
            sid += 1
            created = dt.datetime.combine(main_date + dt.timedelta(days=random.randint(1, 7)),
                                          dt.time(random.randint(8, 18), random.randint(0, 59)))
            if created > NOW:
                created = NOW - dt.timedelta(minutes=random.randint(10, 600))
            rows.append(dict(
                score_id=sid, exam_no=next_exam_no("202606", (st["school_id"], subj)),
                student_no=st["student_no"], student_name=st["student_name"],
                school_id=st["school_id"], school_name=st["school_name"],
                class_id=st["class_id"], class_name=st["class_name"], grade=st["grade"],
                subject=subj, exam_name="2025-2026学年第二学期期末统测", exam_date=main_date,
                score=clamp_score(78), full_score=100.0, score_level=None, class_rank=0,
                term="2025-2026-2", create_by="admin", create_time=created,
                update_by="admin", update_time=created, remark="",
            ))

    pool = [s for s in students if s["grade_no"] in (6, 9)]
    used = set()
    i = 0
    while len(rows) < 8000:
        st = pool[i % len(pool)]
        subj = EXTRA_SUBJECTS[i % len(EXTRA_SUBJECTS)]
        i += 1
        if (st["student_id"], subj) in used:
            continue
        used.add((st["student_id"], subj))
        sid += 1
        edate = rand_date(dt.date(2026, 9, 15), dt.date(2026, 10, 25))
        created = dt.datetime.combine(edate + dt.timedelta(days=random.randint(1, 6)),
                                      dt.time(random.randint(8, 18), random.randint(0, 59)))
        if created > NOW:
            created = NOW - dt.timedelta(minutes=random.randint(10, 600))
        rows.append(dict(
            score_id=sid, exam_no=next_exam_no(edate.strftime("%Y%m"), (st["school_id"], subj, edate.month)),
            student_no=st["student_no"], student_name=st["student_name"],
            school_id=st["school_id"], school_name=st["school_name"],
            class_id=st["class_id"], class_name=st["class_name"], grade=st["grade"],
            subject=subj, exam_name="2026学年第一学期学科抽测", exam_date=edate,
            score=clamp_score(74), full_score=100.0, score_level=None, class_rank=0,
            term="2026-2027-1", create_by="admin", create_time=created,
            update_by="admin", update_time=created, remark="",
        ))
    rows = rows[:8000]

    for r in rows:
        r["score_level"] = score_level(r["score"])

    groups = {}
    for r in rows:
        groups.setdefault((r["class_id"], r["subject"], r["exam_no"]), []).append(r)
    for items in groups.values():
        items.sort(key=lambda x: (-x["score"], x["score_id"]))
        for rank, r in enumerate(items, 1):
            r["class_rank"] = rank
    return rows


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
            email="dept%d@czjy.gov.cn" % dept_id,
            status="0", del_flag="0", create_by="admin",
            create_time=dt.datetime(2024, 2, 20, 9, 0, 0),
            update_by="admin", update_time=NOW - dt.timedelta(days=random.randint(30, 300)),
        ))
    return rows


def build_users():
    rows = []
    uid, name, dept, post, sex, login = RY_EMPLOYEE
    rows.append(dict(
        user_id=uid, dept_id=dept, login_name=login, user_name=name, user_type="00",
        email=email_for(login), phonenumber=phone(), sex=sex, avatar="",
        password=pw_hash(login, DEFAULT_PASSWORD, RY_SALT), salt=RY_SALT, status="0", del_flag="0",
        login_ip="192.168.32.31", login_date=NOW - dt.timedelta(hours=9),
        pwd_update_date=None, create_by="admin", create_time=dt.datetime(2024, 8, 20, 9, 10, 0),
        update_by="admin", update_time=NOW - dt.timedelta(days=20), remark=post,
    ))
    for user_id, name, dept, post, sex in EMPLOYEES:
        login = EMP_LOGIN[user_id]
        rows.append(dict(
            user_id=user_id, dept_id=dept, login_name=login, user_name=name, user_type="00",
            email=email_for(login), phonenumber=phone(), sex=sex, avatar="",
            password=pw_hash(login, DEFAULT_PASSWORD, DEFAULT_SALT), salt=DEFAULT_SALT,
            status="0", del_flag="0",
            login_ip="10.32.10.%d" % (20 + user_id % 100),
            login_date=NOW - dt.timedelta(days=random.randint(0, 6), hours=random.randint(0, 8)),
            pwd_update_date=None, create_by=str(dept),
            create_time=dt.datetime(2024, 2, 26, 9, 0, 0) + dt.timedelta(days=random.randint(0, 300)),
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
IPS = ["10.32.10.%d", "192.168.32.%d"]


def build_logins(user_rows):
    staff = [(u["login_name"], u["user_name"], u["dept_id"]) for u in user_rows]
    staff += [("admin", "系统管理员", 100), ("scanner_low", "运维支持", 122)]
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
            login_location="广西壮族自治区梧州市",
            browser=random.choice(BROWSERS), os=random.choice(OS_LIST),
            status="1" if failed else "0",
            msg="密码错误" if failed else "登录成功",
            login_time=t,
        ))
    return rows


OPER_TITLES = [
    ("学籍管理", 0.32, "business.BizStudent", [
        ("list", "查询学籍列表", 0, "POST", "/business/student/list"),
        ("detail", "查看学籍详情", 0, "GET", "/business/student/detail/1024"),
        ("export", "导出学籍数据", 5, "POST", "/business/student/export"),
    ]),
    ("学生档案", 0.22, "business.BizStudent", [
        ("list", "查询学生档案", 0, "POST", "/business/student/list"),
        ("detail", "查看学生档案", 0, "GET", "/business/student/detail/2048"),
    ]),
    ("班级管理", 0.13, "business.BizClass", [
        ("list", "查询班级列表", 0, "POST", "/business/class/list"),
    ]),
    ("成绩录入", 0.15, "business.BizScore", [
        ("list", "查询成绩记录", 0, "POST", "/business/score/list"),
        ("export", "导出成绩数据", 5, "POST", "/business/score/export"),
    ]),
    ("学校管理", 0.04, "business.BizSchool", [
        ("list", "查询学校列表", 0, "POST", "/business/school/list"),
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
            oper_location="广西壮族自治区梧州市",
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
         menu_type="M", visible="0", is_refresh="1", perms="", icon="fa fa-graduation-cap"),
    dict(menu_id=2001, menu_name="学籍管理", parent_id=2000, order_num=1, url="business/student", target="",
         menu_type="C", visible="0", is_refresh="1", perms="biz:student:list", icon="fa fa-users"),
    dict(menu_id=2002, menu_name="学校管理", parent_id=2000, order_num=2, url="business/school", target="",
         menu_type="C", visible="0", is_refresh="1", perms="biz:school:list", icon="fa fa-university"),
    dict(menu_id=2003, menu_name="班级管理", parent_id=2000, order_num=3, url="business/class", target="",
         menu_type="C", visible="0", is_refresh="1", perms="biz:class:list", icon="fa fa-table"),
    dict(menu_id=2004, menu_name="成绩管理", parent_id=2000, order_num=4, url="business/score", target="",
         menu_type="C", visible="0", is_refresh="1", perms="biz:score:list", icon="fa fa-bar-chart"),
    dict(menu_id=2005, menu_name="查询", parent_id=2001, order_num=1, url="#", target="",
         menu_type="F", visible="0", is_refresh="1", perms="biz:student:query", icon="#"),
    dict(menu_id=2006, menu_name="详情", parent_id=2001, order_num=2, url="#", target="",
         menu_type="F", visible="0", is_refresh="1", perms="biz:student:detail", icon="#"),
    dict(menu_id=2007, menu_name="导出", parent_id=2001, order_num=3, url="#", target="",
         menu_type="F", visible="0", is_refresh="1", perms="biz:student:export", icon="#"),
]
MENU_COLS = ["menu_id", "menu_name", "parent_id", "order_num", "url", "target", "menu_type",
             "visible", "is_refresh", "perms", "icon", "create_by", "create_time", "remark"]


def build_menus():
    rows = []
    for m in MENUS:
        r = dict(m)
        r.update(create_by="admin", create_time=dt.datetime(2024, 7, 1, 10, 0, 0), remark=None)
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


SCHOOL_COLS = ["school_id", "school_code", "school_name", "school_type", "address", "principal",
               "phone", "class_count", "student_count", "teacher_count", "build_date", "status",
               "create_by", "create_time", "update_by", "update_time", "remark"]
CLASS_COLS = ["class_id", "class_code", "class_name", "school_id", "school_name", "grade",
              "grade_no", "head_teacher", "student_count", "classroom", "status", "create_by",
              "create_time", "update_by", "update_time", "remark"]
STUDENT_COLS = ["student_id", "student_no", "student_name", "gender", "birth_date", "id_card",
                "school_id", "school_name", "class_id", "class_name", "grade", "grade_no",
                "enroll_date", "guardian", "guardian_phone", "address", "status", "audit_status",
                "create_by", "create_time", "update_by", "update_time", "remark"]
SCORE_COLS = ["score_id", "exam_no", "student_no", "student_name", "school_id", "school_name",
              "class_id", "class_name", "grade", "subject", "exam_name", "exam_date", "score",
              "full_score", "score_level", "class_rank", "term", "create_by", "create_time",
              "update_by", "update_time", "remark"]
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
    schools = build_schools()
    classes = build_classes()
    students = build_students(classes)
    scores = build_scores(students)
    depts = build_depts()
    staff = build_users()
    logins = build_logins(staff)
    opers = build_opers(staff)
    menus = build_menus()

    statements = []
    statements += DDL

    # ---- 组织架构 ----
    statements += [
        "DELETE FROM sys_dept WHERE dept_id BETWEEN 100 AND 134",
        "DELETE FROM sys_user WHERE user_id NOT IN (1, 100)",
        "DELETE FROM sys_user_role WHERE user_id NOT IN (1, 100)",
        "DELETE FROM sys_user_post WHERE user_id NOT IN (1, 100)",
        "UPDATE sys_user SET user_name = '系统管理员', dept_id = 100 WHERE user_id = 1",
        "UPDATE sys_user SET dept_id = 122, email = 'scanner_low@czjy.gov.cn', "
        "phonenumber = '13877400102' WHERE user_id = 100",
    ]
    statements += insert_sql("sys_dept", depts, DEPT_COLS)
    statements += insert_sql("sys_user", staff, USER_COLS)

    user_roles = [dict(user_id=2, role_id=2)]
    user_posts = [dict(user_id=2, post_id=4)]
    for uid, name, dept, post, sex in EMPLOYEES:
        user_roles.append(dict(user_id=uid, role_id=2))
        if uid == 2001:
            post_id = 1
        elif any(k in post for k in ("局长", "科长", "主任", "校长", "督导室")):
            post_id = 2
        else:
            post_id = 4
        user_posts.append(dict(user_id=uid, post_id=post_id))
    statements += insert_sql("sys_user_role", user_roles, ["user_id", "role_id"])
    statements += insert_sql("sys_user_post", user_posts, ["user_id", "post_id"])

    statements += [
        "UPDATE sys_post SET post_name = '局长' WHERE post_id = 1",
        "UPDATE sys_post SET post_name = '科室负责人' WHERE post_id = 2",
        "UPDATE sys_post SET post_name = '人事专员' WHERE post_id = 3",
        "UPDATE sys_post SET post_name = '教职工' WHERE post_id = 4",
    ]

    # ---- 菜单 ----
    statements += [
        "UPDATE sys_menu SET menu_name = '工作台', url = '/system/main', target = '', perms = '', "
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
    statements += insert_sql("biz_school", schools, SCHOOL_COLS)
    statements += insert_sql("biz_class", classes, CLASS_COLS)
    statements += insert_sql("biz_student", students, STUDENT_COLS)
    statements += insert_sql("biz_score", scores, SCORE_COLS)

    # ---- 日志 ----
    statements += ["DELETE FROM sys_logininfor", "DELETE FROM sys_oper_log"]
    statements += insert_sql("sys_logininfor", logins, LOGIN_COLS)
    statements += insert_sql("sys_oper_log", opers, OPER_COLS)

    with open(SQL_FILE, "w", encoding="utf-8") as f:
        f.write("-- R4 梧州市长洲区教育局学籍管理演示数据（由 seed/r4_business.py 生成）\n")
        f.write("SET NAMES utf8mb4;\nUSE ry_r4;\n\n")
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
    ("biz_school", "build_date"),
    ("biz_school", "create_time"),
    ("biz_school", "update_time"),
    ("biz_class", "create_time"),
    ("biz_class", "update_time"),
    ("biz_student", "birth_date"),
    ("biz_student", "enroll_date"),
    ("biz_student", "create_time"),
    ("biz_student", "update_time"),
    ("biz_score", "exam_date"),
    ("biz_score", "create_time"),
    ("biz_score", "update_time"),
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
    print("R4 梧州市长洲区教育局学籍管理数据灌入完成")
    print("=" * 64)
    for t in ("biz_school", "biz_class", "biz_student", "biz_score",
              "sys_dept", "sys_user", "sys_menu", "sys_logininfor", "sys_oper_log"):
        cur.execute("SELECT COUNT(1) FROM %s" % t)
        print("%-16s %s" % (t, cur.fetchone()[0]))

    errors = []
    expect = {"biz_school": 8, "biz_class": 96, "biz_student": 2400, "biz_score": 8000}
    for t, n in expect.items():
        actual = scalar(cur, "SELECT COUNT(1) FROM %s" % t)
        if actual != n:
            errors.append("%s 行数 %s != %s" % (t, actual, n))

    if scalar(cur, "SELECT COUNT(1) FROM biz_student WHERE audit_status = '0'") != 40:
        errors.append("待审核学籍不是 40 条")
    if scalar(cur, "SELECT COUNT(1) FROM biz_student WHERE audit_status = '2'") != 15:
        errors.append("已退回学籍不是 15 条")
    if scalar(cur, "SELECT COUNT(1) FROM biz_student WHERE status = '3' AND grade_no <> 9") != 0:
        errors.append("非九年级出现毕业状态")
    if scalar(cur, "SELECT COUNT(DISTINCT student_no) FROM biz_student") != 2400:
        errors.append("学籍号不唯一")
    if scalar(cur, "SELECT COUNT(DISTINCT id_card) FROM biz_student") != 2400:
        errors.append("身份证号不唯一")
    if scalar(cur, "SELECT SUM(student_count) FROM biz_school") != 2400:
        errors.append("学校学生数合计不是 2400")
    if scalar(cur, "SELECT SUM(class_count) FROM biz_school") != 96:
        errors.append("学校班级数合计不是 96")

    for t, col in TIME_CHECK:
        n = scalar(cur, "SELECT COUNT(1) FROM %s WHERE %s > NOW()" % (t, col))
        if n:
            errors.append("NO_FUTURE 违规：%s.%s 有 %s 行" % (t, col, n))

    # 班级人数与学校人数一致
    cur.execute("""SELECT s.school_id, s.student_count, SUM(c.student_count)
                   FROM biz_school s JOIN biz_class c ON c.school_id = s.school_id
                   GROUP BY s.school_id, s.student_count""")
    for row in cur.fetchall():
        if row[1] != row[2]:
            errors.append("学校 %s 班级人数合计 %s != 学生数 %s" % (row[0], row[2], row[1]))

    cur.execute("SELECT status, COUNT(1) FROM biz_student GROUP BY status ORDER BY status")
    names = {"0": "在读", "1": "休学", "2": "转出", "3": "毕业"}
    print("\n学籍状态分布：")
    for r in cur.fetchall():
        print("  %-4s %s" % (names.get(r[0], r[0]), r[1]))

    cur.execute("SELECT audit_status, COUNT(1) FROM biz_student GROUP BY audit_status ORDER BY audit_status")
    audit_names = {"0": "待审核", "1": "已通过", "2": "已退回"}
    print("\n审核状态分布：")
    for r in cur.fetchall():
        print("  %-4s %s" % (audit_names.get(r[0], r[0]), r[1]))

    cur.execute("SELECT term, COUNT(1) FROM biz_score GROUP BY term ORDER BY term")
    print("\n成绩学期分布：")
    for r in cur.fetchall():
        print("  %s  %s" % (r[0], r[1]))

    cur.execute("SELECT DATE_FORMAT(login_time, '%Y-%m') m, COUNT(1) FROM sys_logininfor GROUP BY m ORDER BY m")
    print("\n登录日志月份分布：")
    for r in cur.fetchall():
        print("  %s  %s" % (r[0], r[1]))

    cur.execute("SELECT COUNT(1) FROM sys_logininfor WHERE DAYOFWEEK(login_time) IN (1, 7)")
    weekend = cur.fetchone()[0]
    total = scalar(cur, "SELECT COUNT(1) FROM sys_logininfor")
    print("\n周末登录占比：%.1f%%" % (weekend * 100.0 / total))

    print("\nrole_id=1 业务菜单授权：%s 条" % scalar(cur, "SELECT COUNT(1) FROM sys_role_menu WHERE role_id = 1"))
    print("role_id=99 授权：%s 条" % scalar(cur, "SELECT COUNT(1) FROM sys_role_menu WHERE role_id = 99"))
    print("SQL 文件：%s" % SQL_FILE)

    if errors:
        print("\n[FAIL] 校验未通过：")
        for e in errors:
            print("  - " + e)
        raise AssertionError("；".join(errors))
    print("\n[OK] 行数、审核状态、时间巡检、班级人数全部通过")


if __name__ == "__main__":
    main()
