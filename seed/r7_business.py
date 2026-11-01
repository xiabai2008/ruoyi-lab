#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R7 明德职业技术学院 选课管理 业务数据灌入脚本
=================================================
目标库：MySQL 127.0.0.1:13307 / ry_r7

1. 重建 5 张 biz_ 业务表（只 DROP biz_ 表，绝不动 sys_ 表结构）
2. 重写组织架构 sys_dept（100~250）、sys_user（admin / scanner_low / 30 名教职工）
3. 写入业务数据与日志数据，完整 SQL 落盘到 seed/r7_business.sql
4. 可重复执行（幂等）

用法：python seed/r7_business.py
"""
import datetime as dt
import os
import random

import pymysql
from pymysql.converters import escape_string

DB = dict(host="127.0.0.1", port=13307, user="root", password="", database="ry_r7", charset="utf8mb4")

NOW = dt.datetime.now().replace(microsecond=0)
SAFE_NOW = NOW - dt.timedelta(minutes=2)
TODAY = NOW.date()
SEED = 20261030
random.seed(SEED)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SQL_FILE = os.path.join(BASE_DIR, "r7_business.sql")
OUT = []

# ---------------------------------------------------------------------------
# 组织架构：20 个节点，3 层，ID 固定
# (dept_id, parent_id, ancestors, dept_name, order_num, leader)
# ---------------------------------------------------------------------------
DEPTS = [
    (100, 0, "0", "明德职业技术学院", 0, "罗建明"),
    (110, 100, "0,100", "教务处", 1, "陈慧敏"),
    (111, 110, "0,100,110", "教务科", 1, "黄志刚"),
    (112, 110, "0,100,110", "考务科", 2, "李文博"),
    (113, 110, "0,100,110", "教材科", 3, "郑海峰"),
    (120, 100, "0,100", "学生处", 2, "周晓琳"),
    (121, 120, "0,100,120", "学工科", 1, "何俊杰"),
    (122, 120, "0,100,120", "资助中心", 2, "冯丽萍"),
    (130, 100, "0,100", "招生办", 3, "邓国强"),
    (140, 100, "0,100", "财务处", 4, "曾宪明"),
    (150, 100, "0,100", "图书馆", 5, "蒋文军"),
    (160, 100, "0,100", "信息中心", 6, "蔡志伟"),
    (161, 160, "0,100,160", "网络运维组", 1, "潘永强"),
    (162, 160, "0,100,160", "系统开发组", 2, "唐小燕"),
    (200, 100, "0,100", "机电工程系", 7, "韦国华"),
    (210, 100, "0,100", "电子信息系", 8, "许海燕"),
    (220, 100, "0,100", "经济管理系", 9, "谭丽娟"),
    (230, 100, "0,100", "艺术设计系", 10, "莫晓雯"),
    (240, 100, "0,100", "汽车工程系", 11, "覃志强"),
    (250, 100, "0,100", "建筑工程系", 12, "黎建华"),
]
DEPT_NAME = {d[0]: d[3] for d in DEPTS}

# (user_id, 姓名, dept_id, 岗位, 性别 0男 1女)
EMPLOYEES = [
    (2001, "罗建明", 100, "院长", "0"),
    (2002, "陈慧敏", 110, "教务处处长", "1"),
    (2003, "黄志刚", 111, "教务科科长", "0"),
    (2004, "梁淑贞", 111, "教务干事", "1"),
    (2005, "李文博", 112, "考务科科长", "0"),
    (2006, "吴春燕", 112, "考务专员", "1"),
    (2007, "郑海峰", 113, "教材科科长", "0"),
    (2008, "周晓琳", 120, "学生处处长", "1"),
    (2009, "何俊杰", 121, "学工科科长", "0"),
    (2010, "冯丽萍", 122, "资助中心主任", "1"),
    (2011, "邓国强", 130, "招生办主任", "0"),
    (2012, "谢婉如", 130, "招生专员", "1"),
    (2013, "曾宪明", 140, "财务处处长", "0"),
    (2014, "彭雪梅", 140, "会计", "1"),
    (2015, "蒋文军", 150, "图书馆馆长", "0"),
    (2016, "苏惠芳", 150, "图书管理员", "1"),
    (2017, "蔡志伟", 160, "信息中心主任", "0"),
    (2018, "潘永强", 161, "网络运维工程师", "0"),
    (2019, "唐小燕", 162, "系统开发工程师", "1"),
    (2020, "韦国华", 200, "机电工程系主任", "0"),
    (2021, "梁志明", 200, "机电一体化教研室教师", "0"),
    (2022, "许海燕", 210, "电子信息系主任", "1"),
    (2023, "卢建华", 210, "应用电子教研室教师", "0"),
    (2024, "谭丽娟", 220, "经济管理系主任", "1"),
    (2025, "陆志刚", 220, "会计教研室教师", "0"),
    (2026, "莫晓雯", 230, "艺术设计系主任", "1"),
    (2027, "覃志强", 240, "汽车工程系主任", "0"),
    (2028, "石慧敏", 240, "汽车检测教研室教师", "1"),
    (2029, "黎建华", 250, "建筑工程系主任", "0"),
    (2030, "覃丽君", 250, "建筑工程教研室教师", "1"),
]

# 专业：code, name, dept_id, short
MAJORS = [
    ("ZY001", "机电一体化技术", 200, "机电"),
    ("ZY002", "数控技术", 200, "数控"),
    ("ZY003", "电子信息工程技术", 210, "电子"),
    ("ZY004", "计算机网络技术", 210, "网络"),
    ("ZY005", "大数据与会计", 220, "会计"),
    ("ZY006", "电子商务", 220, "电商"),
    ("ZY007", "视觉传达设计", 230, "视传"),
    ("ZY008", "环境艺术设计", 230, "环艺"),
    ("ZY009", "汽车检测与维修技术", 240, "汽检"),
    ("ZY010", "新能源汽车技术", 240, "新能"),
    ("ZY011", "建筑工程技术", 250, "建工"),
    ("ZY012", "工程造价", 250, "造价"),
]
MAJOR_DEPT = {m[0]: m[2] for m in MAJORS}

# 公共基础课 60 门
PUBLIC_COURSES = [
    "思想道德与法治", "毛泽东思想和中国特色社会主义理论体系概论", "习近平新时代中国特色社会主义思想概论",
    "形势与政策", "大学生心理健康教育", "马克思主义基本原理", "中国近现代史纲要",
    "国家安全教育", "劳动教育", "军事理论",
    "高职英语（一）", "高职英语（二）", "高职英语（三）", "实用英语听说", "职场英语",
    "商务英语", "英语应用文写作", "跨文化交际",
    "体育（一）", "体育（二）", "体育（三）", "体育（四）", "篮球选项课", "羽毛球选项课",
    "高等数学（一）", "高等数学（二）", "经济数学", "线性代数", "概率论与数理统计",
    "信息技术基础", "办公软件应用", "程序设计基础", "人工智能通识", "信息素养",
    "大学语文", "应用文写作", "中国传统文化", "美育鉴赏", "音乐欣赏", "美术鉴赏",
    "书法基础", "演讲与口才",
    "职业生涯规划", "就业指导", "创新创业基础", "创业实务", "职业素养",
    "沟通与团队协作", "时间管理", "职业生涯体验",
    "现代企业管理", "市场营销基础", "经济法基础", "统计学基础", "环境保护与可持续发展",
    "健康教育", "安全教育", "国防教育", "志愿服务与社会实践", "大学生社会责任",
]
assert len(PUBLIC_COURSES) == 60, len(PUBLIC_COURSES)

# 每个专业 10 门专业课
MAJOR_COURSES = {
    "ZY001": ["机械制图与CAD", "机械设计基础", "电工电子技术", "液压与气动技术", "电气控制与PLC应用",
              "数控编程与操作", "机械制造工艺", "工业机器人操作与编程", "机电设备故障诊断与维修", "机电一体化综合实训"],
    "ZY002": ["机械制图与测绘", "金属切削原理与刀具", "数控车削编程与加工", "数控铣削编程与加工",
              "CAD/CAM应用技术", "多轴加工技术", "数控机床电气控制", "数控机床装调与维护",
              "精密测量技术", "数控加工综合实训"],
    "ZY003": ["电路分析与应用", "模拟电子技术", "数字电子技术", "单片机原理与应用", "传感器与检测技术",
              "电子线路板设计与制作", "嵌入式系统应用", "电子产品生产工艺", "通信原理与设备",
              "电子产品设计与制作实训"],
    "ZY004": ["计算机网络基础", "网络综合布线", "路由交换技术", "Linux服务器配置", "网络安全技术",
              "数据库原理与应用", "Web前端开发技术", "网络工程设计与实施", "云计算平台运维",
              "网络系统集成实训"],
    "ZY005": ["基础会计", "财务会计实务", "成本核算与管理", "税费计算与申报", "财务管理",
              "审计基础与实务", "会计电算化", "大数据财务分析", "出纳实务", "会计综合模拟实训"],
    "ZY006": ["电子商务基础", "网络营销实务", "网店运营与管理", "商品摄影与图片处理", "电子商务数据分析",
              "移动电商运营", "客户服务与管理", "跨境电商实务", "电子商务物流", "电商运营综合实训"],
    "ZY007": ["设计素描与色彩", "平面构成与色彩构成", "图形创意设计", "字体设计与应用", "版式设计",
              "标志与VI设计", "包装设计", "广告设计与制作", "UI界面设计", "视觉传达综合实训"],
    "ZY008": ["建筑制图与识图", "手绘效果图表现技法", "室内设计原理", "装饰材料与施工工艺", "景观设计基础",
              "家具与陈设设计", "室内效果图制作", "装饰工程预算", "公共空间设计", "环境艺术设计综合实训"],
    "ZY009": ["汽车机械基础", "汽车构造", "汽车电气设备检修", "汽车发动机电控技术", "汽车底盘构造与维修",
              "汽车故障诊断技术", "汽车维护与保养", "汽车维修质量检验", "新能源汽车概论", "汽车检测维修综合实训"],
    "ZY010": ["新能源汽车高压安全与防护", "动力电池及管理系统", "驱动电机及控制技术", "新能源汽车电气系统检修",
              "新能源汽车底盘技术", "车载网络技术", "充电设施运行与维护", "新能源汽车故障诊断",
              "汽车智能制造技术", "新能源汽车综合实训"],
    "ZY011": ["建筑制图与CAD", "建筑材料", "建筑力学", "建筑结构", "建筑施工技术", "建筑工程测量",
              "建筑施工组织", "建筑工程质量验收", "装配式建筑施工", "建筑施工综合实训"],
    "ZY012": ["建筑识图与构造", "建筑工程计量与计价", "安装工程计量与计价", "工程招投标与合同管理",
              "工程造价软件应用", "工程项目管理", "工程经济学", "工程结算与审计", "BIM建模基础",
              "工程造价综合实训"],
}
# ---------------------------------------------------------------------------
# 基础设施
# ---------------------------------------------------------------------------
CONN = pymysql.connect(**DB)
CUR = CONN.cursor()


def q(v):
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, dt.datetime):
        return "'" + v.strftime("%Y-%m-%d %H:%M:%S") + "'"
    if isinstance(v, dt.date):
        return "'" + v.strftime("%Y-%m-%d") + "'"
    return "'" + escape_string(str(v)) + "'"


def run(sql, keep=True):
    CUR.execute(sql)
    if keep:
        OUT.append(sql.rstrip().rstrip(";") + ";")
    return CUR


def emit_insert(table, cols, rows, chunk=300):
    col_sql = ",".join(cols)
    for i in range(0, len(rows), chunk):
        part = rows[i:i + chunk]
        body = ",\n".join("(" + ",".join(q(v) for v in r) + ")" for r in part)
        run("INSERT INTO %s (%s) VALUES\n%s" % (table, col_sql, body))


def dt_in(start, end):
    total = int((end - start).total_seconds())
    return start + dt.timedelta(seconds=random.randint(0, max(total, 1)))


ADMIN_HASH = None


def load_admin_hash():
    global ADMIN_HASH
    CUR.execute("select password from sys_user where user_id=1")
    row = CUR.fetchone()
    if not row or not row[0]:
        raise RuntimeError("admin 账号不存在，无法复用 BCrypt 哈希")
    ADMIN_HASH = row[0]
    return ADMIN_HASH


# ---------------------------------------------------------------------------
# DDL
# ---------------------------------------------------------------------------
DDL = [
    """DROP TABLE IF EXISTS biz_enroll, biz_student, biz_teach_class, biz_course, biz_major""",
    """CREATE TABLE biz_major (
  major_id bigint NOT NULL AUTO_INCREMENT COMMENT '专业ID',
  major_code varchar(20) NOT NULL COMMENT '专业代码',
  major_name varchar(50) NOT NULL COMMENT '专业名称',
  dept_id bigint DEFAULT NULL COMMENT '所属系部ID',
  dept_name varchar(50) DEFAULT NULL COMMENT '所属系部',
  degree_type varchar(20) DEFAULT NULL COMMENT '培养层次',
  duration int DEFAULT 3 COMMENT '学制',
  enroll_year int DEFAULT NULL COMMENT '招生年份',
  status varchar(10) DEFAULT '招生中' COMMENT '状态',
  remark varchar(255) DEFAULT NULL,
  create_by varchar(64) DEFAULT '',
  create_time datetime DEFAULT NULL,
  update_by varchar(64) DEFAULT '',
  update_time datetime DEFAULT NULL,
  PRIMARY KEY (major_id),
  UNIQUE KEY uk_major_code (major_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='专业信息表'""",
    """CREATE TABLE biz_course (
  course_id bigint NOT NULL AUTO_INCREMENT COMMENT '课程ID',
  course_code varchar(20) NOT NULL COMMENT '课程编码',
  course_name varchar(80) NOT NULL COMMENT '课程名称',
  category varchar(20) DEFAULT NULL COMMENT '课程类别',
  credit decimal(3,1) DEFAULT NULL COMMENT '学分',
  hours int DEFAULT NULL COMMENT '学时',
  dept_id bigint DEFAULT NULL COMMENT '开课部门ID',
  dept_name varchar(50) DEFAULT NULL COMMENT '开课部门',
  status varchar(10) DEFAULT '开课' COMMENT '状态',
  remark varchar(255) DEFAULT NULL,
  create_by varchar(64) DEFAULT '',
  create_time datetime DEFAULT NULL,
  update_by varchar(64) DEFAULT '',
  update_time datetime DEFAULT NULL,
  PRIMARY KEY (course_id),
  UNIQUE KEY uk_course_code (course_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='课程信息表'""",
    """CREATE TABLE biz_teach_class (
  class_id bigint NOT NULL AUTO_INCREMENT COMMENT '教学班ID',
  class_code varchar(30) NOT NULL COMMENT '教学班编号',
  course_code varchar(20) DEFAULT NULL COMMENT '课程编码',
  course_name varchar(80) DEFAULT NULL COMMENT '课程名称',
  semester varchar(20) DEFAULT NULL COMMENT '学期',
  teacher_no varchar(20) DEFAULT NULL COMMENT '教师工号',
  teacher_name varchar(30) DEFAULT NULL COMMENT '教师姓名',
  classroom varchar(50) DEFAULT NULL COMMENT '上课教室',
  class_time varchar(50) DEFAULT NULL COMMENT '上课时间',
  capacity int DEFAULT 0 COMMENT '容量',
  enrolled_count int DEFAULT 0 COMMENT '已选人数',
  dept_id bigint DEFAULT NULL COMMENT '开课部门ID',
  dept_name varchar(50) DEFAULT NULL COMMENT '开课部门',
  status varchar(10) DEFAULT NULL COMMENT '状态',
  remark varchar(255) DEFAULT NULL,
  create_by varchar(64) DEFAULT '',
  create_time datetime DEFAULT NULL,
  update_by varchar(64) DEFAULT '',
  update_time datetime DEFAULT NULL,
  PRIMARY KEY (class_id),
  UNIQUE KEY uk_class_code (class_code),
  KEY idx_class_course (course_code),
  KEY idx_class_semester (semester)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='教学班信息表'""",
    """CREATE TABLE biz_student (
  student_id bigint NOT NULL AUTO_INCREMENT COMMENT '学生ID',
  student_no varchar(20) NOT NULL COMMENT '学号',
  student_name varchar(30) NOT NULL COMMENT '姓名',
  gender varchar(4) DEFAULT NULL COMMENT '性别',
  major_code varchar(20) DEFAULT NULL COMMENT '专业代码',
  major_name varchar(50) DEFAULT NULL COMMENT '专业名称',
  class_name varchar(50) DEFAULT NULL COMMENT '班级',
  grade_no int DEFAULT NULL COMMENT '年级',
  dept_id bigint DEFAULT NULL COMMENT '所属系部ID',
  dept_name varchar(50) DEFAULT NULL COMMENT '所属系部',
  phone varchar(11) DEFAULT NULL COMMENT '手机号',
  status varchar(10) DEFAULT '在读' COMMENT '状态',
  enroll_date date DEFAULT NULL COMMENT '入学日期',
  remark varchar(255) DEFAULT NULL,
  create_by varchar(64) DEFAULT '',
  create_time datetime DEFAULT NULL,
  update_by varchar(64) DEFAULT '',
  update_time datetime DEFAULT NULL,
  PRIMARY KEY (student_id),
  UNIQUE KEY uk_student_no (student_no),
  KEY idx_student_major (major_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='学生信息表'""",
    """CREATE TABLE biz_enroll (
  enroll_id bigint NOT NULL AUTO_INCREMENT COMMENT '选课ID',
  enroll_no varchar(30) NOT NULL COMMENT '选课单号',
  student_no varchar(20) DEFAULT NULL COMMENT '学号',
  student_name varchar(30) DEFAULT NULL COMMENT '学生姓名',
  class_code varchar(30) DEFAULT NULL COMMENT '教学班编号',
  course_code varchar(20) DEFAULT NULL COMMENT '课程编码',
  course_name varchar(80) DEFAULT NULL COMMENT '课程名称',
  teacher_name varchar(30) DEFAULT NULL COMMENT '开课教师',
  semester varchar(20) DEFAULT NULL COMMENT '学期',
  credit decimal(3,1) DEFAULT NULL COMMENT '学分',
  score decimal(4,1) DEFAULT NULL COMMENT '成绩',
  status varchar(10) DEFAULT NULL COMMENT '状态',
  enroll_time datetime DEFAULT NULL COMMENT '选课时间',
  dept_id bigint DEFAULT NULL COMMENT '学生所属系部ID',
  dept_name varchar(50) DEFAULT NULL COMMENT '学生所属系部',
  remark varchar(255) DEFAULT NULL,
  create_by varchar(64) DEFAULT '',
  create_time datetime DEFAULT NULL,
  update_by varchar(64) DEFAULT '',
  update_time datetime DEFAULT NULL,
  PRIMARY KEY (enroll_id),
  UNIQUE KEY uk_enroll_no (enroll_no),
  UNIQUE KEY uk_enroll_student_class (student_no, class_code),
  KEY idx_enroll_semester (semester),
  KEY idx_enroll_dept (dept_id),
  KEY idx_enroll_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='选课记录表'""",
]


def rebuild_tables():
    for ddl in DDL:
        run(ddl)


# ---------------------------------------------------------------------------
# 组织架构
# ---------------------------------------------------------------------------
def rebuild_org():
    run("DELETE FROM sys_dept WHERE dept_id BETWEEN 100 AND 250")

    rows = []
    for (dept_id, parent_id, ancestors, name, order_num, leader) in DEPTS:
        phone = "138%08d" % (77000000 + dept_id)
        email = "md%d@mingde-edu.cn" % dept_id
        rows.append((dept_id, parent_id, ancestors, name, order_num, leader, phone, email,
                     "0", "0", "admin", dt.datetime(2026, 8, 15, 9, 0, 0), "", None))
    emit_insert("sys_dept",
                ["dept_id", "parent_id", "ancestors", "dept_name", "order_num", "leader", "phone", "email",
                 "status", "del_flag", "create_by", "create_time", "update_by", "update_time"], rows)

    # 删除 ry 及其关联
    run("DELETE FROM sys_user_role WHERE user_id = 2")
    run("DELETE FROM sys_user_post WHERE user_id = 2")
    run("DELETE FROM sys_user WHERE user_id = 2")

    # admin / scanner_low
    run("UPDATE sys_user SET dept_id = 100, nick_name = '系统管理员' WHERE user_id = 1")
    run("UPDATE sys_user SET dept_id = 161 WHERE user_id = 100")

    run("DELETE FROM sys_user_role WHERE user_id BETWEEN 2001 AND 2030")
    run("DELETE FROM sys_user_post WHERE user_id BETWEEN 2001 AND 2030")
    run("DELETE FROM sys_user WHERE user_id BETWEEN 2001 AND 2030")

    urows = []
    urrows = []
    uprows = []
    for idx, (uid, name, dept_id, post, sex) in enumerate(EMPLOYEES):
        no = "MD%04d" % (idx + 1)
        phone = random.choice(["138", "139", "189"]) + "%08d" % (60000000 + idx * 137)
        email = "%s@mingde-edu.cn" % no.lower()
        created = dt.datetime(2026, 8, 20, 9, 0, 0)
        login_day = SAFE_NOW - dt.timedelta(days=random.randint(0, 12), minutes=random.randint(0, 600))
        login_ip = "10.20.30.%d" % random.randint(20, 200)
        urows.append((uid, dept_id, no, name, "00", email, phone, sex, "",
                      ADMIN_HASH, "0", "0", login_ip, login_day,
                      str(dept_id), created, "", None, post))
        urrows.append((uid, 2))
        uprows.append((uid, 4))

    emit_insert("sys_user",
                ["user_id", "dept_id", "user_name", "nick_name", "user_type", "email", "phonenumber", "sex",
                 "avatar", "password", "status", "del_flag", "login_ip", "login_date",
                 "create_by", "create_time", "update_by", "update_time", "remark"], urows)
    emit_insert("sys_user_role", ["user_id", "role_id"], urrows)
    emit_insert("sys_user_post", ["user_id", "post_id"], uprows)
# ---------------------------------------------------------------------------
# 姓名生成
# ---------------------------------------------------------------------------
SURNAMES = ["王", "李", "张", "刘", "陈", "杨", "赵", "黄", "周", "吴", "徐", "孙", "胡", "朱", "高", "林",
            "何", "郭", "马", "罗", "梁", "宋", "郑", "谢", "韩", "唐", "冯", "于", "董", "萧", "程", "曹",
            "袁", "邓", "许", "傅", "沈", "曾", "彭", "吕", "苏", "卢", "蒋", "蔡", "贾", "丁", "魏", "薛",
            "叶", "阎", "余", "潘", "杜", "戴", "夏", "钟", "汪", "田", "任", "姜", "范", "方", "石", "姚",
            "谭", "廖", "邹", "熊", "金", "陆", "郝", "孔", "白", "崔", "康", "毛", "邱", "秦", "江", "史",
            "顾", "侯", "邵", "孟", "龙", "万", "段", "雷", "钱", "汤", "尹", "黎", "易", "常", "武", "乔",
            "贺", "赖", "龚", "文"]
MALE_GIVEN = ["伟", "强", "磊", "军", "勇", "杰", "涛", "明", "超", "刚", "华", "文", "辉", "鹏", "宇",
              "浩", "凯", "健", "俊", "帆", "帅", "斌", "程", "昊", "然", "睿", "哲", "宁", "峰", "亮",
              "旭", "阳", "波", "海", "江", "林", "松", "柏", "鑫", "龙", "飞", "虎", "鹏飞", "俊杰",
              "志强", "建华", "文博", "国强", "海峰", "永强", "志伟", "建明", "子豪", "嘉豪", "浩然",
              "宇航", "泽宇", "天宇", "家豪", "俊豪", "明轩", "子轩", "博文", "思远", "宏宇", "振宇",
              "少华", "立新", "春生", "树林", "德明", "光明", "耀东", "建平", "卫东", "红军", "爱国",
              "建军", "利民", "学军", "晓明", "晓东", "晓峰", "晓宇", "小龙", "小刚", "大伟", "子健",
              "一鸣", "文轩", "皓轩", "梓豪", "锦程"]
FEMALE_GIVEN = ["芳", "娜", "敏", "静", "丽", "娟", "燕", "艳", "霞", "玲", "婷", "洁", "颖", "倩", "雪",
                "梅", "兰", "菊", "萍", "红", "琳", "悦", "欣", "怡", "佳", "璐", "瑶", "莹", "慧", "思",
                "薇", "蓉", "妍", "莉", "娇", "妮", "彤", "珂", "玥", "晴", "淑贞", "婉如", "春燕", "晓琳",
                "丽萍", "雪梅", "惠芳", "小燕", "丽娟", "晓雯", "慧敏", "丽君", "秀英", "桂英", "玉兰",
                "秀兰", "桂兰", "凤英", "玉梅", "秀珍", "红梅", "春梅", "冬梅", "小丽", "小红", "晓红",
                "晓燕", "晓芳", "晓静", "晓婷", "雅静", "雅琴", "梦瑶", "梦琪", "诗涵", "雨萱", "欣怡",
                "子涵", "佳怡", "嘉怡", "若彤", "可欣", "语嫣", "诗琪", "思琪", "梓涵", "雨欣"]
USED_NAMES = set()


def make_name(gender):
    pool = MALE_GIVEN if gender == "男" else FEMALE_GIVEN
    for _ in range(200):
        n = random.choice(SURNAMES) + random.choice(pool)
        if n not in USED_NAMES:
            USED_NAMES.add(n)
            return n
    suffix = 0
    while True:
        suffix += 1
        n = random.choice(SURNAMES) + random.choice(pool) + str(suffix)
        if n not in USED_NAMES:
            USED_NAMES.add(n)
            return n


# ---------------------------------------------------------------------------
# 专业 / 课程
# ---------------------------------------------------------------------------
COURSES = []          # dict: code,name,category,credit,hours,dept_id,dept_name,status,major
MAJOR_ROWS = []


def build_majors():
    stop = {2, 8}  # 数控技术、环境艺术设计 停招
    for i, (code, name, dept_id, short) in enumerate(MAJORS):
        status = "停招" if i in stop else "招生中"
        MAJOR_ROWS.append((i + 1, code, name, dept_id, DEPT_NAME[dept_id], "三年制专科", 3, 2026, status,
                           "%s%s专业" % (DEPT_NAME[dept_id], name), "admin",
                           dt.datetime(2026, 8, 18, 10, 0, 0), "", None))


def build_courses():
    create = dt.datetime(2026, 8, 18, 10, 30, 0)
    idx = 0
    for name in PUBLIC_COURSES:
        idx += 1
        hours, credit = random.choice([(32, 2.0), (48, 3.0), (32, 2.0), (16, 1.0)])
        COURSES.append(dict(code="KC%04d" % idx, name=name, category="公共基础", credit=credit, hours=hours,
                            dept_id=110, dept_name="教务处", major=None))
    for mi, (mcode, mname, dept_id, short) in enumerate(MAJORS):
        if mi in (0, 1):
            nb, nc, np_ = 5, 4, 1
        elif mi in (2, 3):
            nb, nc, np_ = 4, 5, 1
        else:
            nb, nc, np_ = 4, 4, 2
        names = MAJOR_COURSES[mcode]
        plan = [("专业基础", nb), ("专业核心", nc), ("实践教学", np_)]
        pos = 0
        for cat, cnt in plan:
            for _ in range(cnt):
                idx += 1
                if cat == "专业基础":
                    hours, credit = random.choice([(48, 3.0), (32, 2.0), (64, 4.0)])
                elif cat == "专业核心":
                    hours, credit = random.choice([(64, 4.0), (48, 3.0), (48, 3.0)])
                else:
                    hours, credit = random.choice([(32, 2.0), (16, 1.0), (64, 4.0)])
                COURSES.append(dict(code="KC%04d" % idx, name=names[pos], category=cat, credit=credit,
                                    hours=hours, dept_id=dept_id, dept_name=DEPT_NAME[dept_id], major=mcode))
                pos += 1
    assert idx == 180, idx
    stop_idx = set(random.sample(range(180), 12))
    for i, c in enumerate(COURSES):
        c["status"] = "停开" if i in stop_idx else "开课"
        c["create_time"] = create


def insert_majors():
    cols = ["major_id", "major_code", "major_name", "dept_id", "dept_name", "degree_type", "duration",
            "enroll_year", "status", "remark", "create_by", "create_time", "update_by", "update_time"]
    emit_insert("biz_major", cols, MAJOR_ROWS)


def insert_courses():
    cols = ["course_id", "course_code", "course_name", "category", "credit", "hours", "dept_id", "dept_name",
            "status", "remark", "create_by", "create_time", "update_by", "update_time"]
    rows = []
    for i, c in enumerate(COURSES):
        rows.append((i + 1, c["code"], c["name"], c["category"], c["credit"], c["hours"], c["dept_id"],
                     c["dept_name"], c["status"], "%s课程" % c["category"], "admin", c["create_time"], "", None))
    emit_insert("biz_course", cols, rows)


# ---------------------------------------------------------------------------
# 教学班
# ---------------------------------------------------------------------------
SEMESTERS = [("2025-2026-1", "25261", 100), ("2025-2026-2", "25262", 90), ("2026-2027-1", "26271", 50)]
TEACHER_POOL = {
    110: [2002, 2003, 2004, 2005, 2006, 2007],
    200: [2020, 2021],
    210: [2022, 2023],
    220: [2024, 2025],
    230: [2026],
    240: [2027, 2028],
    250: [2029, 2030],
}
EMP = {e[0]: e for e in EMPLOYEES}
CLASSES = []   # dict: course, semester, teacher_no, teacher_name, dept, capacity, enrolled


def build_classes():
    base = list(range(180))
    extra = random.sample(base, 60)
    picks = base + extra
    assert len(picks) == 240
    slots = []
    for sem, code, cnt in SEMESTERS:
        slots.extend([(sem, code)] * cnt)
    random.shuffle(slots)

    weekdays = ["周一", "周二", "周三", "周四", "周五"]
    periods = ["1-2节", "3-4节", "5-6节", "7-8节", "9-10节"]
    buildings = ["教学楼A", "教学楼B", "教学楼C", "实训楼"]
    seq = {"25261": 0, "25262": 0, "26271": 0}

    for i, ci in enumerate(picks):
        c = COURSES[ci]
        sem, sem_code = slots[i]
        seq[sem_code] += 1
        tid = random.choice(TEACHER_POOL[c["dept_id"]])
        emp = EMP[tid]
        CLASSES.append(dict(
            class_code="JX%sA%03d" % (sem_code, seq[sem_code]),
            course=c, semester=sem, teacher_no="MD%04d" % (tid - 2000),
            teacher_name=emp[1], dept_id=c["dept_id"], dept_name=c["dept_name"],
            classroom="%s-%d%02d" % (random.choice(buildings), random.randint(1, 5), random.randint(1, 15)),
            class_time="%s %s" % (random.choice(weekdays), random.choice(periods)),
            capacity=0, enrolled=0, status=""))


# ---------------------------------------------------------------------------
# 学生
# ---------------------------------------------------------------------------
MALE_CNT = [115, 110, 105, 95, 55, 70, 50, 55, 120, 115, 95, 35]
assert sum(MALE_CNT) == 1020, sum(MALE_CNT)
STUDENTS = []   # dict
USED_PHONE = set()


def make_phone():
    while True:
        p = random.choice(["138", "139", "189", "137", "158", "159"]) + "%08d" % random.randint(1, 99999999)
        if p not in USED_PHONE:
            USED_PHONE.add(p)
            return p


def build_students():
    for mi, (mcode, mname, dept_id, short) in enumerate(MAJORS):
        total_male = MALE_CNT[mi]
        per_grade = [total_male // 3] * 3
        for g in range(total_male % 3):
            per_grade[g] += 1
        for gi, grade in enumerate([2023, 2024, 2025]):
            flags = [True] * per_grade[gi] + [False] * (50 - per_grade[gi])
            random.shuffle(flags)
            for si in range(50):
                gender = "男" if flags[si] else "女"
                serial = si + 1
                class_no = (serial - 1) // 25 + 1
                STUDENTS.append(dict(
                    student_no="%02d%02d%04d" % (grade % 100, mi + 1, serial),
                    student_name=make_name(gender),
                    gender=gender, major_code=mcode, major_name=mname,
                    class_name="%02d%s%d班" % (grade % 100, short, class_no),
                    grade_no=grade, dept_id=dept_id, dept_name=DEPT_NAME[dept_id],
                    phone=make_phone(), status="在读",
                    enroll_date=dt.date(grade, 9, 1), remark="%s级全日制专科生" % grade))
    assert len(STUDENTS) == 1800
    idx = list(range(1800))
    random.shuffle(idx)
    for i in idx[:45]:
        STUDENTS[i]["status"] = "休学"
    for i in idx[45:80]:
        STUDENTS[i]["status"] = "退学"


def insert_students():
    cols = ["student_id", "student_no", "student_name", "gender", "major_code", "major_name", "class_name",
            "grade_no", "dept_id", "dept_name", "phone", "status", "enroll_date", "remark",
            "create_by", "create_time", "update_by", "update_time"]
    rows = []
    for i, s in enumerate(STUDENTS):
        rows.append((i + 1, s["student_no"], s["student_name"], s["gender"], s["major_code"], s["major_name"],
                     s["class_name"], s["grade_no"], s["dept_id"], s["dept_name"], s["phone"], s["status"],
                     s["enroll_date"], s["remark"], "admin", dt.datetime(2026, 8, 25, 9, 30, 0), "", None))
    emit_insert("biz_student", cols, rows)


# ---------------------------------------------------------------------------
# 选课
# ---------------------------------------------------------------------------
ENROLLS = []


def split_counts(total, n):
    base, rem = divmod(total, n)
    return [base + (1 if i < rem else 0) for i in range(n)]


def semester_window(sem):
    if sem == "2025-2026-1":
        return dt.datetime(2025, 9, 1, 8, 0, 0), dt.datetime(2025, 9, 30, 20, 0, 0)
    if sem == "2025-2026-2":
        return dt.datetime(2026, 2, 1, 8, 0, 0), dt.datetime(2026, 2, 28, 20, 0, 0)
    return dt.datetime(2026, 9, 1, 8, 0, 0), dt.datetime(2026, 10, 20, 20, 0, 0)


def build_enrolls():
    by_sem = {}
    for c in CLASSES:
        by_sem.setdefault(c["semester"], []).append(c)
    targets = {"2025-2026-1": 3000, "2025-2026-2": 2800, "2026-2027-1": 2200}

    all_major = {}
    for s in STUDENTS:
        all_major.setdefault(s["major_code"], []).append(s)

    for sem, total in targets.items():
        classes = by_sem[sem]
        counts = split_counts(total, len(classes))
        random.shuffle(classes)
        for c, n in zip(classes, counts):
            major = c["course"]["major"]
            pool = STUDENTS if major is None else all_major[major]
            picked = random.sample(pool, n)
            for st in picked:
                ENROLLS.append(dict(student=st, cls=c, semester=sem, status="已选",
                                    enroll_time=dt_in(*semester_window(sem)), score=None,
                                    remark=None))
    assert len(ENROLLS) == 8000, len(ENROLLS)

    cur = [e for e in ENROLLS if e["semester"] == "2026-2027-1"]
    old = [e for e in ENROLLS if e["semester"] != "2026-2027-1"]
    random.shuffle(cur)
    random.shuffle(old)
    for e in cur[:400]:
        e["status"] = "待审核"
        e["remark"] = "待任课教师审核"
    for e in old[:400]:
        e["status"] = "已退"
        e["remark"] = "学生申请退课"
    for e in ENROLLS:
        if e["status"] == "已选" and e["semester"] != "2026-2027-1":
            e["remark"] = "正常选课"

    # 成绩
    for e in ENROLLS:
        if e["status"] == "已选" and e["semester"] != "2026-2027-1" and random.random() < 0.85:
            e["score"] = round(random.uniform(45.0, 99.0), 1)

    # 已选人数
    for c in CLASSES:
        c["enrolled"] = 0
    for e in ENROLLS:
        if e["status"] == "已选":
            e["cls"]["enrolled"] += 1

    # 容量 / 状态
    cur_classes = [c for c in CLASSES if c["semester"] == "2026-2027-1" and c["enrolled"] >= 30]
    random.shuffle(cur_classes)
    full = set(id(c) for c in cur_classes[:6])
    for c in CLASSES:
        n = c["enrolled"]
        if id(c) in full:
            c["capacity"] = n
        else:
            c["capacity"] = min(120, max(30, n + random.randint(6, 30)))
        if c["enrolled"] >= c["capacity"]:
            c["status"] = "已满"
        elif c["semester"] == "2026-2027-1":
            c["status"] = "选课中"
        else:
            c["status"] = "已结课"


def insert_classes():
    cols = ["class_id", "class_code", "course_code", "course_name", "semester", "teacher_no", "teacher_name",
            "classroom", "class_time", "capacity", "enrolled_count", "dept_id", "dept_name", "status", "remark",
            "create_by", "create_time", "update_by", "update_time"]
    rows = []
    for i, c in enumerate(CLASSES):
        rows.append((i + 1, c["class_code"], c["course"]["code"], c["course"]["name"], c["semester"],
                     c["teacher_no"], c["teacher_name"], c["classroom"], c["class_time"], c["capacity"],
                     c["enrolled"], c["dept_id"], c["dept_name"], c["status"], "教学班",
                     "admin", dt.datetime(2025, 8, 28, 15, 0, 0), "", None))
    emit_insert("biz_teach_class", cols, rows)


def insert_enrolls():
    cols = ["enroll_id", "enroll_no", "student_no", "student_name", "class_code", "course_code", "course_name",
            "teacher_name", "semester", "credit", "score", "status", "enroll_time", "dept_id", "dept_name",
            "remark", "create_by", "create_time", "update_by", "update_time"]
    ordered = sorted(ENROLLS, key=lambda e: e["enroll_time"])
    rows = []
    for i, e in enumerate(ordered):
        c = e["cls"]
        st = e["student"]
        no = "XK%s%05d" % (e["enroll_time"].strftime("%Y%m%d"), i + 1)
        rows.append((i + 1, no, st["student_no"], st["student_name"], c["class_code"], c["course"]["code"],
                     c["course"]["name"], c["teacher_name"], e["semester"], c["course"]["credit"], e["score"],
                     e["status"], e["enroll_time"], st["dept_id"], st["dept_name"], e["remark"],
                     st["student_no"], e["enroll_time"], "", None))
    emit_insert("biz_enroll", cols, rows)


# ---------------------------------------------------------------------------
# 日志
# ---------------------------------------------------------------------------
def pick_day(weights):
    days = []
    for i in range(30, -1, -1):
        d = TODAY - dt.timedelta(days=i)
        w = weights(d)
        days.append((d, w))
    total = sum(w for _, w in days)
    r = random.uniform(0, total)
    acc = 0.0
    for d, w in days:
        acc += w
        if r <= acc:
            return d
    return days[-1][0]


def log_time(weights):
    d = pick_day(weights)
    t = dt.datetime(d.year, d.month, d.day, random.randint(8, 19), random.randint(0, 59),
                    random.randint(0, 59))
    if t > SAFE_NOW:
        t = SAFE_NOW - dt.timedelta(minutes=random.randint(1, 180))
    return t


def build_logs():
    run("DELETE FROM sys_logininfor")
    run("DELETE FROM sys_oper_log")
    names = [(e[2] and "MD%04d" % (i + 1), e[1], DEPT_NAME[e[2]]) for i, e in enumerate(EMPLOYEES)]
    names.append(("admin", "系统管理员", "明德职业技术学院"))
    names.append(("scanner_low", "运维支持", "网络运维组"))

    ip_pool = ["10.20.30.%d" % n for n in range(12, 240)] + ["192.168.30.%d" % n for n in range(11, 200)]
    locations = ["广西壮族自治区梧州市", "广西壮族自治区梧州市", "广西壮族自治区南宁市", "内网IP"]
    browsers = ["Chrome 120", "Chrome 124", "Edge 121", "Firefox 122", "Chrome 118"]
    oses = ["Windows 10", "Windows 11", "Windows 10", "macOS 14"]

    weekday_w = lambda d: 1.0 if d.weekday() < 5 else 0.22

    login_rows = []
    for i in range(280):
        uname, nick, dept = random.choice(names)
        fail = random.random() < 0.05
        login_rows.append((i + 1, uname, random.choice(ip_pool), random.choice(locations),
                           random.choice(browsers), random.choice(oses),
                           "1" if fail else "0",
                           "密码错误，请重新输入" if fail else "登录成功",
                           log_time(weekday_w)))
    emit_insert("sys_logininfor",
                ["info_id", "user_name", "ipaddr", "login_location", "browser", "os", "status", "msg", "login_time"],
                login_rows)

    biz_titles = [
        ("选课管理", 1, "com.ruoyi.web.controller.business.BizEnrollController.add", "POST", "/business/enroll"),
        ("选课管理", 0, "com.ruoyi.web.controller.business.BizEnrollController.list", "GET", "/business/enroll/list"),
        ("选课管理", 2, "com.ruoyi.web.controller.business.BizEnrollController.edit", "PUT", "/business/enroll"),
        ("选课管理", 5, "com.ruoyi.web.controller.business.BizEnrollController.export", "POST", "/business/enroll/export"),
        ("学生管理", 0, "com.ruoyi.web.controller.business.BizStudentController.list", "GET", "/business/student/list"),
        ("学生管理", 5, "com.ruoyi.web.controller.business.BizStudentController.export", "POST", "/business/student/export"),
        ("课程管理", 0, "com.ruoyi.web.controller.business.BizCourseController.list", "GET", "/business/course/list"),
        ("课程管理", 2, "com.ruoyi.web.controller.business.BizCourseController.edit", "PUT", "/business/course"),
        ("教学班管理", 0, "com.ruoyi.web.controller.business.BizTeachClassController.list", "GET", "/business/teachclass/list"),
        ("教学班管理", 2, "com.ruoyi.web.controller.business.BizTeachClassController.edit", "PUT", "/business/teachclass"),
        ("成绩录入", 2, "com.ruoyi.web.controller.business.BizEnrollController.edit", "PUT", "/business/enroll"),
    ]
    sys_titles = [
        ("用户管理", 1, "com.ruoyi.web.controller.system.SysUserController.add", "POST", "/system/user"),
        ("用户管理", 2, "com.ruoyi.web.controller.system.SysUserController.edit", "PUT", "/system/user"),
        ("用户管理", 0, "com.ruoyi.web.controller.system.SysUserController.list", "GET", "/system/user/list"),
        ("角色管理", 2, "com.ruoyi.web.controller.system.SysRoleController.edit", "PUT", "/system/role"),
        ("角色管理", 0, "com.ruoyi.web.controller.system.SysRoleController.list", "GET", "/system/role/list"),
        ("菜单管理", 1, "com.ruoyi.web.controller.system.SysMenuController.add", "POST", "/system/menu"),
        ("菜单管理", 2, "com.ruoyi.web.controller.system.SysMenuController.edit", "PUT", "/system/menu"),
    ]

    oper_rows = []
    for i in range(380):
        if random.random() < 0.72:
            title, btype, method, rmethod, url = random.choice(biz_titles)
        else:
            title, btype, method, rmethod, url = random.choice(sys_titles)
        uname, nick, dept = random.choice(names)
        fail = random.random() < 0.03
        if title == "选课管理" and btype == 1:
            param = '{"studentNo":"%s","classCode":"%s","semester":"2026-2027-1"}' % (
                random.choice(STUDENTS)["student_no"], random.choice(CLASSES)["class_code"])
        elif title == "成绩录入":
            param = '{"enrollId":%d,"score":%s}' % (random.randint(1, 8000), round(random.uniform(45, 99), 1))
        else:
            param = '{"pageNum":1,"pageSize":10}'
        oper_rows.append((i + 1, title, btype, method, rmethod, 1, uname, dept, url,
                          random.choice(ip_pool), random.choice(locations), param,
                          '{"code":500,"msg":"操作失败"}' if fail else '{"code":200,"msg":"操作成功"}',
                          1 if fail else 0, "系统异常，请稍后重试" if fail else "",
                          log_time(weekday_w), random.randint(12, 860)))
    emit_insert("sys_oper_log",
                ["oper_id", "title", "business_type", "method", "request_method", "operator_type", "oper_name",
                 "dept_name", "oper_url", "oper_ip", "oper_location", "oper_param", "json_result", "status",
                 "error_msg", "oper_time", "cost_time"], oper_rows)


# ---------------------------------------------------------------------------
# 菜单
# ---------------------------------------------------------------------------
MENU_IDS = [2000, 2010, 2011, 2012, 2013, 2020, 2021, 2022]


def rebuild_menus():
    # 品牌化：删除「若依官网」外链菜单
    run("DELETE FROM sys_menu WHERE menu_id = 4")
    run("DELETE FROM sys_menu WHERE menu_id BETWEEN 2000 AND 2022")

    now = dt.datetime(2026, 8, 16, 11, 0, 0)
    cols = ["menu_id", "menu_name", "parent_id", "order_num", "path", "component", "query", "route_name",
            "is_frame", "is_cache", "menu_type", "visible", "status", "perms", "icon",
            "create_by", "create_time", "update_by", "update_time", "remark"]
    rows = [
        (2000, "业务管理", 0, 4, "business", None, None, "", 1, 0, "M", "0", "0", "", "documentation",
         "admin", now, "", None, "选课业务管理目录"),
        (2010, "选课管理", 2000, 1, "enroll", "business/enroll/index", None, "", 1, 0, "C", "0", "0",
         "biz:enroll:list", "form", "admin", now, "", None, "学生选课记录管理"),
        (2011, "学生管理", 2000, 2, "student", "business/student/index", None, "", 1, 0, "C", "0", "0",
         "biz:student:list", "user", "admin", now, "", None, "在册学生信息管理"),
        (2012, "课程管理", 2000, 3, "course", "business/course/index", None, "", 1, 0, "C", "0", "0",
         "biz:course:list", "table", "admin", now, "", None, "课程库管理"),
        (2013, "教学班管理", 2000, 4, "teachclass", "business/teachclass/index", None, "", 1, 0, "C", "0", "0",
         "biz:teachclass:list", "list", "admin", now, "", None, "教学班开设管理"),
        (2020, "查询", 2010, 1, "", None, None, "", 1, 0, "F", "0", "0", "biz:enroll:query", "#",
         "admin", now, "", None, ""),
        (2021, "详情", 2010, 2, "", None, None, "", 1, 0, "F", "0", "0", "biz:enroll:detail", "#",
         "admin", now, "", None, ""),
        (2022, "导出", 2010, 3, "", None, None, "", 1, 0, "F", "0", "0", "biz:enroll:export", "#",
         "admin", now, "", None, ""),
    ]
    emit_insert("sys_menu", cols, rows)

    # 只给角色 1 补授权，只插不删
    for mid in MENU_IDS:
        run("INSERT INTO sys_role_menu (role_id, menu_id) SELECT 1, %d FROM DUAL "
            "WHERE NOT EXISTS (SELECT 1 FROM sys_role_menu WHERE role_id = 1 AND menu_id = %d)" % (mid, mid))


# ---------------------------------------------------------------------------
# 断言
# ---------------------------------------------------------------------------
def check():
    problems = []

    def scalar(sql):
        CUR.execute(sql)
        return CUR.fetchone()[0]

    expect = {"biz_major": 12, "biz_course": 180, "biz_teach_class": 240, "biz_student": 1800, "biz_enroll": 8000}
    for t, n in expect.items():
        got = scalar("select count(*) from %s" % t)
        if got != n:
            problems.append("%s 行数 %d != %d" % (t, got, n))

    dist = {
        "select category,count(*) from biz_course group by category":
            {"公共基础": 60, "专业基础": 50, "专业核心": 50, "实践教学": 20},
        "select semester,count(*) from biz_teach_class group by semester":
            {"2025-2026-1": 100, "2025-2026-2": 90, "2026-2027-1": 50},
        "select status,count(*) from biz_enroll group by status":
            {"已选": 7200, "已退": 400, "待审核": 400},
        "select status,count(*) from biz_student group by status":
            {"在读": 1720, "休学": 45, "退学": 35},
        "select status,count(*) from biz_major group by status":
            {"招生中": 10, "停招": 2},
        "select status,count(*) from biz_course group by status":
            {"开课": 168, "停开": 12},
    }
    for sql, want in dist.items():
        CUR.execute(sql)
        got = dict(CUR.fetchall())
        if got != want:
            problems.append("%s => %s != %s" % (sql, got, want))

    # 已选人数一致
    CUR.execute("""select count(*) from biz_teach_class c
                   where c.enrolled_count <> (select count(*) from biz_enroll e
                     where e.class_code = c.class_code and e.status='已选')""")
    bad = CUR.fetchone()[0]
    if bad:
        problems.append("enrolled_count 不一致的教学班 %d 个" % bad)

    # 无未来时间
    future_sql = {
        "sys_logininfor.login_time": "select count(*) from sys_logininfor where login_time > now()",
        "sys_oper_log.oper_time": "select count(*) from sys_oper_log where oper_time > now()",
        "biz_enroll.enroll_time": "select count(*) from biz_enroll where enroll_time > now()",
        "biz_enroll.create_time": "select count(*) from biz_enroll where create_time > now()",
        "biz_student.enroll_date": "select count(*) from biz_student where enroll_date > now()",
        "biz_course.create_time": "select count(*) from biz_course where create_time > now()",
        "biz_teach_class.create_time": "select count(*) from biz_teach_class where create_time > now()",
        "biz_major.create_time": "select count(*) from biz_major where create_time > now()",
        "sys_user.login_date": "select count(*) from sys_user where login_date > now()",
        "sys_user.create_time": "select count(*) from sys_user where create_time > now()",
        "sys_dept.create_time": "select count(*) from sys_dept where create_time > now()",
        "sys_menu.create_time": "select count(*) from sys_menu where create_time > now()",
    }
    for name, sql in future_sql.items():
        n = scalar(sql)
        if n:
            problems.append("NO_FUTURE 违规 %s 共 %d 行" % (name, n))

    # 当前学期成绩必须为空
    n = scalar("select count(*) from biz_enroll where semester='2026-2027-1' and score is not null")
    if n:
        problems.append("当前学期存在成绩 %d 行" % n)

    # 角色授权分布
    rm = {}
    CUR.execute("select role_id,count(*) from sys_role_menu group by role_id")
    for r, c in CUR.fetchall():
        rm[r] = c
    if rm.get(99) != 5:
        problems.append("role_id=99 授权行数 %s != 5" % rm.get(99))
    if rm.get(2) != 85:
        problems.append("role_id=2 授权行数 %s != 85" % rm.get(2))
    if rm.get(1) != 8:
        problems.append("role_id=1 授权行数 %s != 8" % rm.get(1))

    # 周末占比
    total = scalar("select count(*) from sys_logininfor")
    weekend = scalar("select count(*) from sys_logininfor where dayofweek(login_time) in (1,7)")
    if total and weekend / total > 0.12:
        problems.append("登录日志周末占比 %.2f%% > 12%%" % (weekend * 100.0 / total))
    total2 = scalar("select count(*) from sys_oper_log")
    weekend2 = scalar("select count(*) from sys_oper_log where dayofweek(oper_time) in (1,7)")
    if total2 and weekend2 / total2 > 0.15:
        problems.append("操作日志周末占比 %.2f%%" % (weekend2 * 100.0 / total2))

    # scanner_low 未被破坏
    CUR.execute("select dept_id,user_name,status,left(password,4) from sys_user where user_id=100")
    sl = CUR.fetchone()
    if not sl or sl[1] != "scanner_low" or sl[2] != "0" or sl[3] != "$2b$" or sl[0] != 161:
        problems.append("scanner_low 状态异常: %s" % (sl,))

    return problems


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def dump_sql():
    header = ["-- R7 明德职业技术学院 选课管理 业务数据",
              "-- generated at %s" % NOW.strftime("%Y-%m-%d %H:%M:%S"),
              "SET NAMES utf8mb4;", ""]
    with open(SQL_FILE, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(header))
        f.write("\n")
        for stmt in OUT:
            f.write(stmt)
            f.write("\n")


def main():
    load_admin_hash()
    rebuild_tables()
    rebuild_org()

    build_majors()
    insert_majors()
    build_courses()
    insert_courses()

    build_classes()
    build_students()
    insert_students()

    build_enrolls()
    insert_classes()
    insert_enrolls()

    build_logs()
    rebuild_menus()

    problems = check()
    if problems:
        CONN.rollback()
        print("[FAIL] 校验未通过：")
        for p in problems:
            print("  - " + p)
        raise SystemExit(1)

    CONN.commit()
    dump_sql()

    CUR.execute("select count(*) from biz_major")
    major_n = CUR.fetchone()[0]
    CUR.execute("select count(*) from biz_course")
    course_n = CUR.fetchone()[0]
    CUR.execute("select count(*) from biz_teach_class")
    class_n = CUR.fetchone()[0]
    CUR.execute("select count(*) from biz_student")
    student_n = CUR.fetchone()[0]
    CUR.execute("select count(*) from biz_enroll")
    enroll_n = CUR.fetchone()[0]
    CUR.execute("select count(*) from sys_logininfor")
    login_n = CUR.fetchone()[0]
    CUR.execute("select count(*) from sys_oper_log")
    oper_n = CUR.fetchone()[0]
    print("[OK] biz_major=%d biz_course=%d biz_teach_class=%d biz_student=%d biz_enroll=%d"
          % (major_n, course_n, class_n, student_n, enroll_n))
    print("[OK] sys_logininfor=%d sys_oper_log=%d sys_user=%d sys_dept=%d"
          % (login_n, oper_n, len(EMPLOYEES) + 2, len(DEPTS)))
    print("[OK] SQL => %s" % SQL_FILE)


if __name__ == "__main__":
    main()
