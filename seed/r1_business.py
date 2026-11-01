#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R1 藤县人民医院门诊管理系统 站点业务数据灌入脚本.

- 重建 biz_patient / biz_registration / biz_prescription / biz_drug
- 重写 21+ 部门、人员、菜单、角色菜单授权
- 重灌登录日志 / 操作日志
- 幂等：每次先 DROP / 覆盖，再生成
- 执行过的 SQL 全部落盘 seed/r1_business.sql
"""
import datetime as dt
import hashlib
import os
import random

import pymysql
from pymysql.converters import escape_string

DB = dict(host="127.0.0.1", port=13307, user="root", password="", database="ry_r1", charset="utf8mb4")

TODAY = dt.date.today()
NOW = dt.datetime.now().replace(microsecond=0)
SEED = 20261030
random.seed(SEED)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SQL_FILE = os.path.join(BASE_DIR, "r1_business.sql")

ADMIN_PASSWORD = "29c67a30398638269fe600f73a054934"
ADMIN_SALT = "111111"


def pw_hash(login_name, password, salt):
    """RuoYi 4.x 口令算法：MD5(loginName + password + salt)，必须逐账号算，不能复用别人的哈希。"""
    return hashlib.md5((login_name + password + salt).encode("utf-8")).hexdigest()

# ---------------------------------------------------------------------------
# 基础字典
# ---------------------------------------------------------------------------
SURNAMES = list(
    "赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜戚谢邹喻柏水窦章云苏潘葛"
    "奚范彭郎鲁韦昌马苗凤花方俞任袁柳鲍史唐费廉岑薛雷贺倪汤滕殷罗毕郝邬安常乐于时傅皮卞齐康"
    "伍余元卜顾孟平黄和穆萧尹姚邵汪祁毛禹狄米贝明臧计伏成戴谈宋茅庞熊纪舒屈项祝董梁杜阮蓝闵"
    "席季麻强贾路娄危江童颜郭梅盛林刁钟徐邱骆高夏蔡田樊胡凌霍虞万支柯管卢莫经房裘缪干解应宗"
    "丁宣邓郁单杭洪包诸左石崔吉钮龚程邢裴陆荣翁荀羊惠甄曲家封芮储靳松井段富巫乌焦巴弓牧隗山"
    "谷车侯全班仰秋仲伊宫宁仇栾暴甘厉戎祖武符刘景詹束龙叶幸司韶黎蓟薄印宿白怀蒲邰从鄂索咸籍"
    "赖卓蔺屠蒙池乔胥能苍双闻莘党翟谭贡劳姬申扶堵冉宰郦雍桑桂濮牛寿通边扈燕冀浦尚农温别庄晏"
    "柴瞿阎充慕连茹习宦艾鱼容向古易慎戈廖庾终暨居衡步都耿满弘匡国文寇广禄阙东欧沃利蔚越夔隆"
    "师巩聂晁融冷辛阚那简饶空曾沙养鞠须丰巢关蒯相查后荆红游竺权盖益桓"
)
GIVEN = [
    "伟", "芳", "娜", "秀英", "敏", "静", "丽", "强", "磊", "军", "洋", "勇", "艳", "杰", "娟",
    "涛", "明", "超", "秀兰", "霞", "平", "刚", "桂英", "建国", "志强", "海燕", "雪梅", "文斌",
    "振华", "小燕", "德明", "春华", "世杰", "秀英", "海清", "丽娟", "永芳", "国新", "伟东", "建平",
    "玉兰", "志明", "梅", "志勇", "海军", "小玲", "国强", "丽萍", "志刚", "春梅", "金凤", "家豪",
    "子涵", "雨欣", "浩然", "思远", "嘉怡", "梓轩", "欣怡", "俊杰", "雅婷", "宇航", "梦琪", "天佑",
]

TOWNS = ["藤州镇", "太平镇", "蒙江镇", "塘步镇", "埌南镇", "同心镇", "金鸡镇", "新庆镇",
         "象棋镇", "岭景镇", "天平镇", "濛江镇", "和平镇", "古龙镇", "东荣镇", "大黎镇", "宁康乡"]
VILLAGES = ["河东村", "河西村", "中和村", "平政村", "龙昌村", "三合村", "共和村", "安福村",
            "新塘村", "泗洲村", "长洲村", "古耙村", "旺国村", "雅瑶村", "石桥村", "沙冲村"]
BLOOD = ["A", "B", "O", "AB", "不详"]
INSURANCE = ["城镇职工医保", "城乡居民医保", "自费"]
ALLERGY = ["无", "无", "无", "青霉素过敏", "磺胺类药物过敏", "海鲜过敏", "花粉过敏", "头孢类药物过敏"]

# 门诊科室与医生
OUTPATIENT = [
    (105, "内科门诊", ["韦建军", "覃海燕", "李国强", "黄丽萍", "周文斌"]),
    (106, "外科门诊", ["梁志伟", "甘世杰", "陈志刚", "刘伟强"]),
    (107, "儿科门诊", ["卢小燕", "李梅", "周小玲", "覃雪梅"]),
    (108, "急诊科", ["黄德明", "吴海军", "覃志勇", "李春林"]),
]

DIAGNOSE = {
    "内科门诊": ["急性上呼吸道感染", "急性胃炎", "高血压2级", "2型糖尿病", "慢性支气管炎",
                 "冠状动脉粥样硬化性心脏病", "原发性高血压", "高脂血症"],
    "外科门诊": ["急性阑尾炎", "腹股沟疝", "软组织挫伤", "腰椎间盘突出症", "胆囊结石",
                 "甲状腺结节", "体表脓肿"],
    "儿科门诊": ["小儿支气管肺炎", "小儿腹泻病", "急性扁桃体炎", "手足口病", "小儿高热惊厥",
                 "过敏性紫癜", "小儿急性支气管炎"],
    "急诊科": ["急性胃肠炎", "头部外伤", "急性酒精中毒", "高热惊厥", "急性胸痛",
               "泌尿系结石", "急性荨麻疹"],
}

# 药品基础名（110 个），第二轮换厂家/规格凑满 220 条目录
DRUG_BASE = [
    ("阿莫西林胶囊", "抗生素", "0.25g*24粒", "盒", 12.80),
    ("头孢克肟分散片", "抗生素", "0.1g*12片", "盒", 28.50),
    ("头孢呋辛酯片", "抗生素", "0.25g*12片", "盒", 32.00),
    ("阿奇霉素分散片", "抗生素", "0.25g*6片", "盒", 26.80),
    ("左氧氟沙星片", "抗生素", "0.5g*7片", "盒", 24.60),
    ("克拉霉素胶囊", "抗生素", "0.25g*12粒", "盒", 19.90),
    ("甲硝唑片", "抗生素", "0.2g*100片", "瓶", 6.50),
    ("罗红霉素胶囊", "抗生素", "150mg*12粒", "盒", 15.80),
    ("磷霉素氨丁三醇散", "抗生素", "3g*1袋", "袋", 38.00),
    ("头孢拉定胶囊", "抗生素", "0.25g*24粒", "盒", 18.20),
    ("注射用头孢曲松钠", "抗生素", "1.0g*1支", "支", 9.80),
    ("注射用青霉素钠", "抗生素", "80万单位*1支", "支", 3.60),
    ("布洛芬缓释胶囊", "解热镇痛", "0.3g*20粒", "盒", 16.80),
    ("对乙酰氨基酚片", "解热镇痛", "0.5g*20片", "盒", 8.90),
    ("双氯芬酸钠缓释片", "解热镇痛", "75mg*10片", "盒", 14.50),
    ("塞来昔布胶囊", "解热镇痛", "0.2g*6粒", "盒", 42.00),
    ("洛索洛芬钠片", "解热镇痛", "60mg*12片", "盒", 21.30),
    ("吲哚美辛肠溶片", "解热镇痛", "25mg*100片", "瓶", 7.80),
    ("复方氨酚烷胺片", "解热镇痛", "12片", "盒", 9.50),
    ("布洛芬混悬液", "解热镇痛", "100ml", "瓶", 18.60),
    ("小儿氨酚黄那敏颗粒", "解热镇痛", "10袋", "盒", 12.40),
    ("尼美舒利颗粒", "解热镇痛", "50mg*10袋", "盒", 16.20),
    ("硝苯地平控释片", "心血管", "30mg*7片", "盒", 34.50),
    ("苯磺酸氨氯地平片", "心血管", "5mg*14片", "盒", 19.80),
    ("缬沙坦胶囊", "心血管", "80mg*7粒", "盒", 28.60),
    ("厄贝沙坦片", "心血管", "150mg*7片", "盒", 25.30),
    ("琥珀酸美托洛尔缓释片", "心血管", "47.5mg*7片", "盒", 22.80),
    ("富马酸比索洛尔片", "心血管", "5mg*10片", "盒", 20.10),
    ("卡托普利片", "心血管", "25mg*100片", "瓶", 6.80),
    ("马来酸依那普利片", "心血管", "10mg*16片", "盒", 15.60),
    ("阿托伐他汀钙片", "心血管", "20mg*7片", "盒", 36.90),
    ("瑞舒伐他汀钙片", "心血管", "10mg*7片", "盒", 41.20),
    ("辛伐他汀片", "心血管", "20mg*10片", "盒", 26.50),
    ("硝酸甘油片", "心血管", "0.5mg*100片", "瓶", 12.30),
    ("单硝酸异山梨酯缓释片", "心血管", "40mg*24片", "盒", 31.60),
    ("阿司匹林肠溶片", "心血管", "100mg*30片", "盒", 15.90),
    ("硫酸氢氯吡格雷片", "心血管", "75mg*7片", "盒", 45.80),
    ("华法林钠片", "心血管", "2.5mg*60片", "瓶", 23.40),
    ("呋塞米片", "心血管", "20mg*100片", "瓶", 8.60),
    ("螺内酯片", "心血管", "20mg*100片", "瓶", 11.20),
    ("氢氯噻嗪片", "心血管", "25mg*100片", "瓶", 5.90),
    ("地高辛片", "心血管", "0.25mg*100片", "瓶", 13.80),
    ("盐酸胺碘酮片", "心血管", "0.2g*24片", "盒", 29.50),
    ("奥美拉唑肠溶胶囊", "消化系统", "20mg*14粒", "盒", 22.60),
    ("兰索拉唑肠溶片", "消化系统", "15mg*14片", "盒", 33.40),
    ("雷贝拉唑钠肠溶片", "消化系统", "10mg*7片", "盒", 38.90),
    ("泮托拉唑钠肠溶胶囊", "消化系统", "40mg*7粒", "盒", 35.20),
    ("铝碳酸镁咀嚼片", "消化系统", "0.5g*20片", "盒", 18.70),
    ("枸橼酸铋钾胶囊", "消化系统", "0.3g*24粒", "盒", 21.40),
    ("多潘立酮片", "消化系统", "10mg*30片", "盒", 14.20),
    ("枸橼酸莫沙必利片", "消化系统", "5mg*24片", "盒", 27.80),
    ("蒙脱石散", "消化系统", "3g*10袋", "盒", 16.50),
    ("双歧杆菌四联活菌片", "消化系统", "0.5g*24片", "盒", 39.60),
    ("复方甘草片", "消化系统", "100片", "瓶", 9.80),
    ("消旋山莨菪碱片", "消化系统", "5mg*100片", "瓶", 6.20),
    ("乳果糖口服溶液", "消化系统", "100ml", "瓶", 32.50),
    ("开塞露", "消化系统", "20ml*10支", "盒", 8.40),
    ("连花清瘟胶囊", "中成药", "0.35g*24粒", "盒", 25.80),
    ("藿香正气水", "中成药", "10ml*10支", "盒", 12.60),
    ("板蓝根颗粒", "中成药", "10g*20袋", "袋", 15.20),
    ("银翘解毒片", "中成药", "0.5g*24片", "盒", 10.80),
    ("感冒灵颗粒", "中成药", "10g*9袋", "盒", 14.90),
    ("小柴胡颗粒", "中成药", "10g*10袋", "盒", 16.30),
    ("双黄连口服液", "中成药", "10ml*10支", "盒", 21.60),
    ("牛黄解毒片", "中成药", "0.3g*24片", "盒", 7.90),
    ("六味地黄丸", "中成药", "360丸", "瓶", 23.50),
    ("逍遥丸", "中成药", "200丸", "瓶", 18.40),
    ("复方丹参滴丸", "中成药", "180丸", "瓶", 36.80),
    ("麝香保心丸", "中成药", "42丸", "盒", 32.90),
    ("云南白药气雾剂", "外用药", "85g+30g", "盒", 46.50),
    ("正骨水", "外用药", "30ml", "瓶", 12.80),
    ("红花油", "外用药", "30ml", "瓶", 9.60),
    ("三九胃泰颗粒", "中成药", "20g*6袋", "盒", 17.80),
    ("香砂养胃丸", "中成药", "200丸", "瓶", 15.40),
    ("补中益气丸", "中成药", "200丸", "瓶", 19.20),
    ("金嗓子喉片", "中成药", "2g*12片", "盒", 8.80),
    ("急支糖浆", "中成药", "200ml", "瓶", 22.40),
    ("川贝枇杷膏", "中成药", "150ml", "瓶", 28.60),
    ("红霉素软膏", "外用药", "10g", "支", 3.80),
    ("莫匹罗星软膏", "外用药", "5g", "支", 18.90),
    ("复方醋酸地塞米松乳膏", "外用药", "20g", "支", 7.60),
    ("炉甘石洗剂", "外用药", "100ml", "瓶", 6.90),
    ("碘伏消毒液", "外用药", "500ml", "瓶", 11.50),
    ("过氧化氢溶液", "外用药", "500ml", "瓶", 5.80),
    ("云南白药膏", "外用药", "6.5cm*10cm*5片", "盒", 26.40),
    ("双氯芬酸二乙胺乳胶剂", "外用药", "20g", "支", 23.80),
    ("硝酸咪康唑乳膏", "外用药", "20g", "支", 12.20),
    ("曲安奈德益康唑乳膏", "外用药", "15g", "支", 16.70),
    ("盐酸二甲双胍片", "消化系统", "0.5g*20片", "盒", 9.60),
    ("格列美脲片", "消化系统", "2mg*10片", "盒", 18.30),
    ("阿卡波糖片", "消化系统", "50mg*30片", "盒", 42.60),
    ("精蛋白人胰岛素注射液", "消化系统", "300IU*1支", "支", 58.00),
    ("左甲状腺素钠片", "消化系统", "50ug*100片", "瓶", 24.50),
    ("甲巯咪唑片", "消化系统", "10mg*50片", "瓶", 16.80),
    ("别嘌醇片", "解热镇痛", "0.1g*100片", "瓶", 13.60),
    ("非布司他片", "解热镇痛", "40mg*14片", "盒", 48.20),
    ("碳酸钙D3片", "消化系统", "600mg*60片", "瓶", 35.40),
    ("维生素C片", "消化系统", "0.1g*100片", "瓶", 4.60),
    ("维生素B1片", "消化系统", "10mg*100片", "瓶", 3.90),
    ("叶酸片", "消化系统", "5mg*100片", "瓶", 6.80),
    ("琥珀酸亚铁片", "消化系统", "0.1g*24片", "盒", 21.90),
    ("氯化钾缓释片", "心血管", "0.5g*24片", "盒", 17.50),
    ("葡萄糖注射液", "消化系统", "5%*500ml", "瓶", 4.80),
    ("氯化钠注射液", "消化系统", "0.9%*500ml", "瓶", 3.90),
    ("地塞米松磷酸钠注射液", "抗生素", "5mg*1支", "支", 2.60),
    ("利巴韦林颗粒", "抗生素", "50mg*18袋", "盒", 11.70),
    ("磷酸奥司他韦胶囊", "抗生素", "75mg*10粒", "盒", 56.80),
    ("氯雷他定片", "解热镇痛", "10mg*6片", "盒", 14.40),
    ("盐酸西替利嗪片", "解热镇痛", "10mg*12片", "盒", 12.90),
    ("孟鲁司特钠片", "解热镇痛", "10mg*5片", "盒", 43.60),
    ("盐酸氨溴索口服溶液", "消化系统", "100ml", "瓶", 19.80),
    ("肺力咳合剂", "中成药", "150ml", "瓶", 26.90),
    ("沙丁胺醇气雾剂", "心血管", "100ug*200揿", "支", 27.40),
    ("布地奈德鼻喷雾剂", "外用药", "64ug*120喷", "支", 54.20),
    ("玻璃酸钠滴眼液", "外用药", "5ml", "支", 32.80),
    ("左氧氟沙星滴眼液", "外用药", "5ml", "支", 13.50),
]

MANUFACTURERS = [
    "华北制药股份有限公司", "哈药集团制药总厂", "石药集团欧意药业有限公司", "齐鲁制药有限公司",
    "扬子江药业集团有限公司", "广州白云山制药股份有限公司", "修正药业集团股份有限公司",
    "云南白药集团股份有限公司", "北京同仁堂制药厂", "华润三九医药股份有限公司",
    "丽珠医药集团股份有限公司", "江苏恒瑞医药股份有限公司", "正大天晴药业集团股份有限公司",
    "上海信谊药厂有限公司", "拜耳医药保健有限公司", "辉瑞制药有限公司",
    "阿斯利康制药有限公司", "诺和诺德(中国)制药有限公司", "北京双鹤药业股份有限公司",
    "天津中新药业集团股份有限公司",
]

# ---------------------------------------------------------------------------
# 组织架构
# ---------------------------------------------------------------------------
# (dept_id, parent_id, dept_name, ancestors, order_num, leader, phone, email)
DEPTS = [
    (100, 0, "藤县人民医院", "0", 0, "李建华", "0774-7282001", "yb@txrmyy.cn"),
    (101, 100, "院办公室", "0,100", 1, "黄志强", "0774-7282002", "yuanban@txrmyy.cn"),
    (102, 100, "医务科", "0,100", 2, "覃海燕", "0774-7282003", "yiwuke@txrmyy.cn"),
    (103, 100, "护理部", "0,100", 3, "李雪梅", "0774-7282004", "hulibu@txrmyy.cn"),
    (104, 100, "门诊部", "0,100", 4, "陈国强", "0774-7282005", "menzhen@txrmyy.cn"),
    (105, 104, "内科门诊", "0,100,104", 1, "韦建军", "0774-7282101", "neike@txrmyy.cn"),
    (106, 104, "外科门诊", "0,100,104", 2, "梁志伟", "0774-7282102", "waike@txrmyy.cn"),
    (107, 104, "儿科门诊", "0,100,104", 3, "卢小燕", "0774-7282103", "erke@txrmyy.cn"),
    (108, 104, "急诊科", "0,100,104", 4, "黄德明", "0774-7282120", "jizhen@txrmyy.cn"),
    (109, 100, "住院部", "0,100", 5, "吴春华", "0774-7282006", "zhuyuan@txrmyy.cn"),
    (110, 109, "内一科病区", "0,100,109", 1, "莫振华", "0774-7282201", "neiyi@txrmyy.cn"),
    (111, 109, "内二科病区", "0,100,109", 2, "周文斌", "0774-7282202", "neier@txrmyy.cn"),
    (112, 109, "外一科病区", "0,100,109", 3, "甘世杰", "0774-7282203", "waiyi@txrmyy.cn"),
    (113, 109, "妇产科病区", "0,100,109", 4, "何秀英", "0774-7282204", "fuchan@txrmyy.cn"),
    (114, 100, "药学部", "0,100", 6, "罗海清", "0774-7282007", "yaoxue@txrmyy.cn"),
    (115, 114, "门诊药房", "0,100,114", 1, "覃丽娟", "0774-7282301", "mzyf@txrmyy.cn"),
    (116, 114, "住院药房", "0,100,114", 2, "陈永芳", "0774-7282302", "zyyf@txrmyy.cn"),
    (117, 114, "药库", "0,100,114", 3, "李国新", "0774-7282303", "yaoku@txrmyy.cn"),
    (118, 100, "检验科", "0,100", 7, "梁伟东", "0774-7282008", "jianyan@txrmyy.cn"),
    (119, 100, "医学影像科", "0,100", 8, "黄建平", "0774-7282009", "yingxiang@txrmyy.cn"),
    (120, 100, "财务科", "0,100", 9, "苏玉兰", "0774-7282010", "caiwu@txrmyy.cn"),
    (121, 100, "信息科", "0,100", 10, "潘志明", "0774-7282011", "xinxike@txrmyy.cn"),
]
DEPT_NAME = {d[0]: d[2] for d in DEPTS}

# user_id, 姓名, dept_id, 岗位
EMPLOYEES = [
    (2001, "黄志强", 101, "院办公室主任"),
    (2002, "覃海燕", 102, "医务科科长"),
    (2003, "李雪梅", 103, "护理部主任"),
    (2004, "陈国强", 104, "门诊部主任"),
    (2005, "韦建军", 105, "内科主治医师"),
    (2006, "梁志伟", 106, "外科主治医师"),
    (2007, "卢小燕", 107, "儿科主治医师"),
    (2008, "黄德明", 108, "急诊科主任"),
    (2009, "吴春华", 109, "住院部主任"),
    (2010, "莫振华", 110, "内一科病区护士长"),
    (2011, "周文斌", 111, "内二科病区主治医师"),
    (2012, "甘世杰", 112, "外一科病区主治医师"),
    (2013, "何秀英", 113, "妇产科病区护士长"),
    (2014, "罗海清", 114, "药学部主任"),
    (2015, "覃丽娟", 115, "门诊药房药剂师"),
    (2016, "陈永芳", 116, "住院药房药剂师"),
    (2017, "李国新", 117, "药库管理员"),
    (2018, "梁伟东", 118, "检验科主管技师"),
    (2019, "黄建平", 119, "医学影像科主治医师"),
    (2020, "苏玉兰", 120, "财务科会计"),
    (2021, "潘志明", 121, "信息科工程师"),
    (2022, "李梅", 104, "门诊收费员"),
]

# ---------------------------------------------------------------------------
# 工具
# ---------------------------------------------------------------------------
conn = pymysql.connect(**DB)
cur = conn.cursor()
sql_out = open(SQL_FILE, "w", encoding="utf-8")
sql_out.write("-- 藤县人民医院门诊管理系统 业务数据脚本（脚本生成，请勿手工修改）\n")
sql_out.write("SET NAMES utf8mb4;\n")
sql_out.write("SET FOREIGN_KEY_CHECKS = 0;\n\n")


def run(sql):
    cur.execute(sql)
    sql_out.write(sql.rstrip().rstrip(";") + ";\n")


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
        return "'%s'" % v.strftime("%Y-%m-%d")
    return "'%s'" % escape_string(str(v))


def person_name():
    return random.choice(SURNAMES) + random.choice(GIVEN)


def mobile():
    return random.choice(["138", "139", "189", "188", "137"]) + "".join(
        random.choice("0123456789") for _ in range(8)
    )


def staff_mobile():
    return random.choice(["138", "189"]) + "".join(
        random.choice("0123456789") for _ in range(8)
    )


def id_card_no(birth, seq):
    body = "450422" + birth.strftime("%Y%m%d") + ("%03d" % seq)
    weights = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
    check = "10X98765432"
    total = sum(int(body[i]) * weights[i] for i in range(17))
    return body + check[total % 11]


def clamp_now(t):
    if t > NOW:
        return NOW - dt.timedelta(minutes=random.randint(1, 90))
    return t


def age_at(birth, on_date):
    years = on_date.year - birth.year - ((on_date.month, on_date.day) < (birth.month, birth.day))
    return max(1, years)


def rand_dt(on_date, h1=7, h2=18):
    t = dt.datetime.combine(on_date, dt.time(random.randint(h1, h2), random.randint(0, 59),
                                             random.randint(0, 59)))
    return clamp_now(t)


def json_str(obj):
    import json
    return json.dumps(obj, ensure_ascii=False)


def pick_dept(age):
    if age <= 14:
        return random.choices(OUTPATIENT, weights=[20, 5, 65, 10])[0]
    return random.choices(OUTPATIENT, weights=[42, 35, 0, 23])[0]


# ---------------------------------------------------------------------------
# 1. 建业务表
# ---------------------------------------------------------------------------
TABLES = {
    "biz_patient": """
CREATE TABLE `biz_patient` (
  `patient_id` bigint NOT NULL AUTO_INCREMENT COMMENT '患者ID',
  `patient_no` varchar(20) NOT NULL COMMENT '病历号',
  `name` varchar(50) NOT NULL COMMENT '患者姓名',
  `gender` char(2) DEFAULT '男' COMMENT '性别',
  `birth_date` date DEFAULT NULL COMMENT '出生日期',
  `id_card` varchar(18) DEFAULT NULL COMMENT '身份证号',
  `phone` varchar(20) DEFAULT NULL COMMENT '联系电话',
  `address` varchar(255) DEFAULT NULL COMMENT '家庭住址',
  `blood_type` varchar(8) DEFAULT '不详' COMMENT '血型',
  `insurance_type` varchar(20) DEFAULT '自费' COMMENT '医保类型',
  `allergy_history` varchar(255) DEFAULT '无' COMMENT '过敏史',
  `first_visit_date` date DEFAULT NULL COMMENT '首次就诊日期',
  `status` char(1) DEFAULT '0' COMMENT '状态（0正常 1归档）',
  `create_by` varchar(64) DEFAULT '' COMMENT '创建者',
  `create_time` datetime DEFAULT NULL COMMENT '创建时间',
  `update_by` varchar(64) DEFAULT '' COMMENT '更新者',
  `update_time` datetime DEFAULT NULL COMMENT '更新时间',
  `remark` varchar(500) DEFAULT NULL COMMENT '备注',
  PRIMARY KEY (`patient_id`),
  UNIQUE KEY `uk_patient_no` (`patient_no`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='患者档案'
""",
    "biz_registration": """
CREATE TABLE `biz_registration` (
  `reg_id` bigint NOT NULL AUTO_INCREMENT COMMENT '挂号ID',
  `reg_no` varchar(20) NOT NULL COMMENT '挂号单号',
  `patient_id` bigint DEFAULT NULL COMMENT '患者ID',
  `patient_no` varchar(20) DEFAULT NULL COMMENT '病历号',
  `patient_name` varchar(50) DEFAULT NULL COMMENT '患者姓名',
  `gender` char(2) DEFAULT NULL COMMENT '性别',
  `age` int DEFAULT NULL COMMENT '年龄',
  `dept_id` bigint DEFAULT NULL COMMENT '科室ID',
  `dept_name` varchar(50) DEFAULT NULL COMMENT '科室名称',
  `doctor_name` varchar(50) DEFAULT NULL COMMENT '接诊医生',
  `reg_type` varchar(20) DEFAULT '普通号' COMMENT '挂号类型',
  `visit_date` date DEFAULT NULL COMMENT '就诊日期',
  `visit_time` varchar(10) DEFAULT '上午' COMMENT '就诊时段',
  `reg_fee` decimal(5,2) DEFAULT '0.00' COMMENT '挂号费',
  `pay_type` varchar(20) DEFAULT '自费' COMMENT '支付方式',
  `status` char(1) DEFAULT '0' COMMENT '状态（0待就诊 1就诊中 2已完成 3已退号）',
  `create_by` varchar(64) DEFAULT '' COMMENT '创建者',
  `create_time` datetime DEFAULT NULL COMMENT '创建时间',
  `update_by` varchar(64) DEFAULT '' COMMENT '更新者',
  `update_time` datetime DEFAULT NULL COMMENT '更新时间',
  `remark` varchar(500) DEFAULT NULL COMMENT '备注',
  PRIMARY KEY (`reg_id`),
  UNIQUE KEY `uk_reg_no` (`reg_no`),
  KEY `idx_visit_date` (`visit_date`),
  KEY `idx_patient_id` (`patient_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='门诊挂号'
""",
    "biz_prescription": """
CREATE TABLE `biz_prescription` (
  `presc_id` bigint NOT NULL AUTO_INCREMENT COMMENT '处方ID',
  `presc_no` varchar(20) NOT NULL COMMENT '处方号',
  `reg_id` bigint DEFAULT NULL COMMENT '挂号ID',
  `reg_no` varchar(20) DEFAULT NULL COMMENT '挂号单号',
  `patient_name` varchar(50) DEFAULT NULL COMMENT '患者姓名',
  `dept_name` varchar(50) DEFAULT NULL COMMENT '科室名称',
  `doctor_name` varchar(50) DEFAULT NULL COMMENT '开方医生',
  `diagnose` varchar(100) DEFAULT NULL COMMENT '诊断',
  `drug_count` int DEFAULT '0' COMMENT '药品数量',
  `total_amount` decimal(10,2) DEFAULT '0.00' COMMENT '处方金额',
  `presc_date` date DEFAULT NULL COMMENT '开方日期',
  `status` char(1) DEFAULT '0' COMMENT '状态（0待发药 1已发药 2已退药）',
  `create_by` varchar(64) DEFAULT '' COMMENT '创建者',
  `create_time` datetime DEFAULT NULL COMMENT '创建时间',
  `update_by` varchar(64) DEFAULT '' COMMENT '更新者',
  `update_time` datetime DEFAULT NULL COMMENT '更新时间',
  `remark` varchar(500) DEFAULT NULL COMMENT '备注',
  PRIMARY KEY (`presc_id`),
  UNIQUE KEY `uk_presc_no` (`presc_no`),
  KEY `idx_presc_date` (`presc_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='处方记录'
""",
    "biz_drug": """
CREATE TABLE `biz_drug` (
  `drug_id` bigint NOT NULL AUTO_INCREMENT COMMENT '药品ID',
  `drug_code` varchar(20) NOT NULL COMMENT '药品编码',
  `drug_name` varchar(100) NOT NULL COMMENT '药品名称',
  `spec` varchar(100) DEFAULT NULL COMMENT '规格',
  `unit` varchar(10) DEFAULT '盒' COMMENT '单位',
  `category` varchar(20) DEFAULT NULL COMMENT '分类',
  `manufacturer` varchar(100) DEFAULT NULL COMMENT '生产企业',
  `price` decimal(10,2) DEFAULT '0.00' COMMENT '单价',
  `stock` int DEFAULT '0' COMMENT '库存',
  `safety_stock` int DEFAULT '0' COMMENT '安全库存',
  `status` char(1) DEFAULT '0' COMMENT '状态（0正常 1停用）',
  `create_by` varchar(64) DEFAULT '' COMMENT '创建者',
  `create_time` datetime DEFAULT NULL COMMENT '创建时间',
  `update_by` varchar(64) DEFAULT '' COMMENT '更新者',
  `update_time` datetime DEFAULT NULL COMMENT '更新时间',
  `remark` varchar(500) DEFAULT NULL COMMENT '备注',
  PRIMARY KEY (`drug_id`),
  UNIQUE KEY `uk_drug_code` (`drug_code`),
  KEY `idx_drug_name` (`drug_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='药品目录'
""",
}

for name in ["biz_patient", "biz_registration", "biz_prescription", "biz_drug"]:
    run("DROP TABLE IF EXISTS `%s`" % name)
    run(TABLES[name].strip())

# ---------------------------------------------------------------------------
# 2. 患者 300
# ---------------------------------------------------------------------------
patients = []
for i in range(1, 301):
    gender = random.choice(["男", "女"])
    age = random.randint(1, 92)
    birth_year = TODAY.year - age
    birth = dt.date(birth_year, random.randint(1, 12), random.randint(1, 28))
    first_visit = TODAY - dt.timedelta(days=random.randint(0, 1100))
    create = clamp_now(dt.datetime.combine(first_visit, dt.time(random.randint(8, 17),
                                                                random.randint(0, 59))))
    update = clamp_now(create + dt.timedelta(days=random.randint(0, 200),
                                             minutes=random.randint(0, 600)))
    if update < create:
        update = create
    town = random.choice(TOWNS)
    address = "藤县%s%s%d号" % (town, random.choice(VILLAGES), random.randint(1, 180))
    patients.append(dict(
        patient_id=i,
        patient_no="BL2026%06d" % i,
        name=person_name(),
        gender=gender,
        birth=birth,
        id_card=id_card_no(birth, random.randint(1, 999)),
        phone=mobile(),
        address=address,
        blood=random.choice(BLOOD),
        insurance=random.choices(INSURANCE, weights=[35, 50, 15])[0],
        allergy=random.choice(ALLERGY),
        first_visit=first_visit,
        status="1" if random.random() < 0.08 else "0",
        create=create,
        update=update,
        remark="" if random.random() < 0.7 else "建档患者",
    ))

for p in patients:
    run("INSERT INTO biz_patient(patient_id,patient_no,name,gender,birth_date,id_card,phone,address,"
        "blood_type,insurance_type,allergy_history,first_visit_date,status,create_by,create_time,"
        "update_by,update_time,remark) VALUES (%d,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)" % (
            p["patient_id"], q(p["patient_no"]), q(p["name"]), q(p["gender"]), q(p["birth"]),
            q(p["id_card"]), q(p["phone"]), q(p["address"]), q(p["blood"]), q(p["insurance"]),
            q(p["allergy"]), q(p["first_visit"]), q(p["status"]), q("admin"), q(p["create"]),
            q("admin"), q(p["update"]), q(p["remark"])))

# ---------------------------------------------------------------------------
# 3. 挂号 900（近 12 个月 792 + 未来 7 天待就诊 108）
# ---------------------------------------------------------------------------
START = TODAY - dt.timedelta(days=365)
all_days = []
d = START
while d <= TODAY:
    all_days.append(d)
    d += dt.timedelta(days=1)
weekdays = [x for x in all_days if x.weekday() < 5]
weekends = [x for x in all_days if x.weekday() >= 5]

counts = {x: 3 for x in weekdays}
target_hist = 792
extra = target_hist - sum(counts.values())
random.shuffle(weekends)
wi = 0
while extra > 0 and wi < len(weekends):
    add = min(extra, random.randint(1, 2))
    counts[weekends[wi]] = add
    extra -= add
    wi += 1
# 今天补到 27 条（就诊中），从其他工作日各减 1 条
counts[TODAY] = counts.get(TODAY, 0) + 24
others = [x for x in weekdays if x != TODAY]
random.shuffle(others)
for x in others[:24]:
    counts[x] -= 1

slots = []
for day, c in counts.items():
    slots.extend([day] * c)
assert len(slots) == target_hist, len(slots)
random.shuffle(slots)

today_slots = [x for x in slots if x == TODAY]
assert len(today_slots) >= 27, len(today_slots)
today_set = set(random.sample(range(len(today_slots)), 27))
in_progress_dates = [today_slots[i] for i in today_set]

status_pool = ["2"] * 630 + ["3"] * 135
random.shuffle(status_pool)
reg_seq = {}
registrations = []


def next_reg_no(day):
    key = day.strftime("%Y%m%d")
    seq = reg_seq.get(key, 0) + 1
    reg_seq[key] = seq
    return "GH%s%04d" % (key, seq)


pool_i = 0
for day in slots:
    p = random.choice(patients)
    reg_age = age_at(p["birth"], day)
    dept_id, dept_name, doctors = pick_dept(reg_age)
    if dept_name == "急诊科":
        reg_type = "急诊号"
        fee = 15.00
    else:
        reg_type = random.choices(["普通号", "专家号"], weights=[75, 25])[0]
        fee = 8.00 if reg_type == "普通号" else 30.00
    if day == TODAY:
        status = "1"
    else:
        status = status_pool[pool_i]
        pool_i += 1
    visit_time = random.choices(["上午", "下午"], weights=[60, 40])[0]
    create = rand_dt(day)
    if status == "2":
        update = clamp_now(create + dt.timedelta(minutes=random.randint(20, 300)))
    elif status == "3":
        update = clamp_now(create + dt.timedelta(minutes=random.randint(5, 120)))
    else:
        update = create
    if update < create:
        update = create
    registrations.append(dict(
        reg_id=len(registrations) + 1,
        reg_no=next_reg_no(day),
        patient=p,
        age=age_at(p["birth"], day),
        dept_id=dept_id,
        dept_name=dept_name,
        doctor=random.choice(doctors),
        reg_type=reg_type,
        visit_date=day,
        visit_time=visit_time,
        fee=fee,
        pay_type=random.choices(["医保", "微信", "支付宝", "自费"], weights=[45, 25, 15, 15])[0],
        status=status,
        create=create,
        update=update,
        remark="退号：患者临时取消" if status == "3" else "",
    ))

# 待就诊 108 条，今天 ~ 未来 7 天
future_days = [TODAY + dt.timedelta(days=i) for i in range(8)]
pending_days = random.choices(future_days, weights=[6, 18, 18, 14, 12, 10, 8, 6], k=108)
for day in pending_days:
    p = random.choice(patients)
    reg_age = age_at(p["birth"], day)
    dept_id, dept_name, doctors = pick_dept(reg_age)
    if dept_name == "急诊科":
        reg_type = "急诊号"
        fee = 15.00
    else:
        reg_type = random.choices(["普通号", "专家号"], weights=[75, 25])[0]
        fee = 8.00 if reg_type == "普通号" else 30.00
    create = clamp_now(NOW - dt.timedelta(hours=random.randint(1, 70), minutes=random.randint(0, 59)))
    registrations.append(dict(
        reg_id=len(registrations) + 1,
        reg_no=next_reg_no(day),
        patient=p,
        age=age_at(p["birth"], day),
        dept_id=dept_id,
        dept_name=dept_name,
        doctor=random.choice(doctors),
        reg_type=reg_type,
        visit_date=day,
        visit_time=random.choices(["上午", "下午"], weights=[65, 35])[0],
        fee=fee,
        pay_type=random.choices(["医保", "微信", "支付宝", "自费"], weights=[40, 27, 18, 15])[0],
        status="0",
        create=create,
        update=create,
        remark="",
    ))

# 挂号按日期排序后写库，保证主键与日期顺序自然
registrations.sort(key=lambda r: (r["visit_date"], r["reg_no"]))
for idx, r in enumerate(registrations, start=1):
    r["reg_id"] = idx
    run("INSERT INTO biz_registration(reg_id,reg_no,patient_id,patient_no,patient_name,gender,age,"
        "dept_id,dept_name,doctor_name,reg_type,visit_date,visit_time,reg_fee,pay_type,status,"
        "create_by,create_time,update_by,update_time,remark) VALUES "
        "(%d,%s,%d,%s,%s,%s,%d,%d,%s,%s,%s,%s,%s,%.2f,%s,%s,%s,%s,%s,%s,%s)" % (
            r["reg_id"], q(r["reg_no"]), r["patient"]["patient_id"], q(r["patient"]["patient_no"]),
            q(r["patient"]["name"]), q(r["patient"]["gender"]), r["age"], r["dept_id"],
            q(r["dept_name"]), q(r["doctor"]), q(r["reg_type"]), q(r["visit_date"]),
            q(r["visit_time"]), r["fee"], q(r["pay_type"]), q(r["status"]), q("admin"),
            q(r["create"]), q("admin"), q(r["update"]), q(r["remark"])))

# ---------------------------------------------------------------------------
# 4. 处方 650（仅落在已完成挂号日期）
# ---------------------------------------------------------------------------
completed = [r for r in registrations if r["status"] == "2"]
assert len(completed) == 630, len(completed)
presc_seq = {}
prescriptions = []
for i in range(650):
    reg = random.choice(completed)
    day = reg["visit_date"]
    key = day.strftime("%Y%m%d")
    seq = presc_seq.get(key, 0) + 1
    presc_seq[key] = seq
    create = clamp_now(dt.datetime.combine(day, dt.time(random.randint(8, 17), random.randint(0, 59),
                                                         random.randint(0, 59))))
    status = random.choices(["1", "0", "2"], weights=[85, 10, 5])[0]
    update = clamp_now(create + dt.timedelta(minutes=random.randint(10, 180)))
    if update < create:
        update = create
    prescriptions.append(dict(
        presc_id=i + 1,
        presc_no="CF%s%04d" % (key, seq),
        reg_id=reg["reg_id"],
        reg_no=reg["reg_no"],
        patient_name=reg["patient"]["name"],
        dept_name=reg["dept_name"],
        doctor=reg["doctor"],
        diagnose=random.choice(DIAGNOSE[reg["dept_name"]]),
        drug_count=random.randint(1, 6),
        amount=round(random.uniform(12.5, 420.0), 2),
        presc_date=day,
        status=status,
        create=create,
        update=update,
        remark="已退药：患者要求" if status == "2" else "",
    ))

for r in prescriptions:
    run("INSERT INTO biz_prescription(presc_id,presc_no,reg_id,reg_no,patient_name,dept_name,"
        "doctor_name,diagnose,drug_count,total_amount,presc_date,status,create_by,create_time,"
        "update_by,update_time,remark) VALUES (%d,%s,%d,%s,%s,%s,%s,%s,%d,%.2f,%s,%s,%s,%s,%s,%s,%s)" % (
            r["presc_id"], q(r["presc_no"]), r["reg_id"], q(r["reg_no"]), q(r["patient_name"]),
            q(r["dept_name"]), q(r["doctor"]), q(r["diagnose"]), r["drug_count"], r["amount"],
            q(r["presc_date"]), q(r["status"]), q("admin"), q(r["create"]), q("admin"),
            q(r["update"]), q(r["remark"])))

# ---------------------------------------------------------------------------
# 5. 药品 220
# ---------------------------------------------------------------------------
drugs = []
low_stock_index = set(random.sample(range(220), 24))
for i in range(220):
    base = DRUG_BASE[i % len(DRUG_BASE)]
    name, category, spec, unit, price = base
    safety = random.choice([30, 40, 50, 60, 80, 100, 120])
    if i in low_stock_index:
        stock = random.randint(0, safety - 1)
    else:
        stock = random.randint(safety, 800)
    create = clamp_now(NOW - dt.timedelta(days=random.randint(30, 900)))
    update = clamp_now(create + dt.timedelta(days=random.randint(1, 120)))
    if update < create:
        update = create
    drugs.append(dict(
        drug_id=i + 1,
        drug_code="YP%04d" % (i + 1),
        name=name,
        spec=spec,
        unit=unit,
        category=category,
        manufacturer=random.choice(MANUFACTURERS),
        price=round(price * random.uniform(0.85, 1.25), 2),
        stock=stock,
        safety=safety,
        status="1" if random.random() < 0.04 else "0",
        create=create,
        update=update,
        remark="库存预警" if stock < safety else "",
    ))

for r in drugs:
    run("INSERT INTO biz_drug(drug_id,drug_code,drug_name,spec,unit,category,manufacturer,price,"
        "stock,safety_stock,status,create_by,create_time,update_by,update_time,remark) VALUES "
        "(%d,%s,%s,%s,%s,%s,%s,%.2f,%d,%d,%s,%s,%s,%s,%s,%s)" % (
            r["drug_id"], q(r["drug_code"]), q(r["name"]), q(r["spec"]), q(r["unit"]),
            q(r["category"]), q(r["manufacturer"]), r["price"], r["stock"], r["safety"],
            q(r["status"]), q("admin"), q(r["create"]), q("admin"), q(r["update"]), q(r["remark"])))

# ---------------------------------------------------------------------------
# 6. 组织架构：部门
# ---------------------------------------------------------------------------
run("DELETE FROM sys_dept")
for d in DEPTS:
    run("INSERT INTO sys_dept(dept_id,parent_id,ancestors,dept_name,order_num,leader,phone,email,"
        "status,del_flag,create_by,create_time,update_by,update_time) VALUES "
        "(%d,%d,%s,%s,%d,%s,%s,%s,'0','0','admin',NOW(),'',NULL)" % (
            d[0], d[1], q(d[3]), q(d[2]), d[4], q(d[5]), q(d[6].replace("-", "")), q(d[7])))

# ---------------------------------------------------------------------------
# 7. 用户
# ---------------------------------------------------------------------------
run("UPDATE sys_user SET user_name='系统管理员', dept_id=100, email='admin@txrmyy.cn', "
    "phonenumber='13877450001', password='%s', salt='%s', status='0', del_flag='0', "
    "remark='信息科系统管理员', update_time=NOW() WHERE user_id=1" % (ADMIN_PASSWORD, ADMIN_SALT))
run("UPDATE sys_user SET user_name='覃伟明', dept_id=102, email='ry@txrmyy.cn', "
    "phonenumber='13877450002', password='%s', salt='%s', status='0', del_flag='0', "
    "remark='医务科干事', update_time=NOW() WHERE user_id=2" % (ADMIN_PASSWORD, ADMIN_SALT))
run("UPDATE sys_user SET dept_id=121, status='0', del_flag='0', update_time=NOW() WHERE user_id=100")
run("DELETE FROM sys_user WHERE user_id >= 2000")
run("DELETE FROM sys_user_role WHERE user_id >= 2000")

for uid, name, dept_id, post in EMPLOYEES:
    login = "TX%04d" % (uid - 2000)
    run("INSERT INTO sys_user(user_id,dept_id,login_name,user_name,user_type,email,phonenumber,sex,"
        "avatar,password,salt,status,del_flag,login_ip,login_date,pwd_update_date,create_by,"
        "create_time,update_by,update_time,remark) VALUES "
        "(%d,%d,%s,%s,'00',%s,%s,'%s','','%s','%s','0','0','127.0.0.1',%s,%s,'admin',%s,'',NULL,%s)" % (
            uid, dept_id, q(login), q(name), q("%s@txrmyy.cn" % login.lower()), q(staff_mobile()),
            random.choice(["0", "1"]), pw_hash(login, "admin123", ADMIN_SALT), ADMIN_SALT,
            q(clamp_now(NOW - dt.timedelta(days=random.randint(1, 90)))),
            q(clamp_now(NOW - dt.timedelta(days=random.randint(30, 300)))),
            q(clamp_now(NOW - dt.timedelta(days=random.randint(90, 700)))), q(post)))
    run("INSERT INTO sys_user_role(user_id,role_id) VALUES (%d,2)" % uid)

# ---------------------------------------------------------------------------
# 8. 菜单 / 角色菜单
# ---------------------------------------------------------------------------
run("DELETE FROM sys_menu WHERE menu_id >= 2000")
run("UPDATE sys_menu SET menu_name='院内OA', url='http://oa.txrmyy.cn', target='menuBlank', "
    "order_num=8, icon='fa fa-external-link' WHERE menu_id=4")

MENUS = [
    (2000, "业务管理", 0, 4, "#", "", "M", "0", "", "fa fa-hospital-o"),
    (2001, "门诊挂号", 2000, 1, "/business/registration", "", "C", "0", "biz:registration:view", "fa fa-stethoscope"),
    (2002, "患者档案", 2000, 2, "/business/patient", "", "C", "0", "biz:patient:view", "fa fa-id-card-o"),
    (2003, "药品目录", 2000, 3, "/business/drug", "", "C", "0", "biz:drug:view", "fa fa-medkit"),
    (2004, "处方记录", 2000, 4, "/business/prescription", "", "C", "0", "biz:prescription:view", "fa fa-file-text-o"),
    (2010, "挂号查询", 2001, 1, "#", "", "F", "0", "biz:registration:list", "#"),
    (2011, "挂号详情", 2001, 2, "#", "", "F", "0", "biz:registration:detail", "#"),
    (2012, "挂号导出", 2001, 3, "#", "", "F", "0", "biz:registration:export", "#"),
    (2013, "患者查询", 2002, 1, "#", "", "F", "0", "biz:patient:list", "#"),
    (2014, "药品查询", 2003, 1, "#", "", "F", "0", "biz:drug:list", "#"),
    (2015, "处方查询", 2004, 1, "#", "", "F", "0", "biz:prescription:list", "#"),
]
for m in MENUS:
    run("INSERT INTO sys_menu(menu_id,menu_name,parent_id,order_num,url,target,menu_type,visible,"
        "perms,icon,create_by,create_time,update_by,update_time,remark) VALUES "
        "(%d,%s,%d,%d,%s,%s,%s,%s,%s,%s,'admin',NOW(),'',NULL,%s)" % (
            m[0], q(m[1]), m[2], m[3], q(m[4]), q(m[5]), q(m[6]), q(m[7]), q(m[8]), q(m[9]),
            q("藤县人民医院门诊业务菜单")))

for role_id in (1, 2):
    run("INSERT INTO sys_role_menu(role_id, menu_id) SELECT %d, menu_id FROM sys_menu "
        "WHERE menu_id >= 2000 AND NOT EXISTS (SELECT 1 FROM sys_role_menu rm "
        "WHERE rm.role_id=%d AND rm.menu_id=sys_menu.menu_id)" % (role_id, role_id))

# ---------------------------------------------------------------------------
# 9. 登录日志 / 操作日志
# ---------------------------------------------------------------------------
LOGIN_NAMES = ["admin"] + ["TX%04d" % i for i in range(1, 23)]


def time_pool(total, days=30, weekend_ratio=0.12):
    weekdays, weekends = [], []
    for i in range(days):
        day = TODAY - dt.timedelta(days=i)
        (weekends if day.weekday() >= 5 else weekdays).append(day)
    n_weekend = int(round(total * weekend_ratio))
    n_weekday = total - n_weekend
    picks = [random.choice(weekdays) for _ in range(n_weekday)]
    picks += [random.choice(weekends) for _ in range(n_weekend)]
    result = []
    for day in picks:
        t = dt.datetime.combine(day, dt.time(random.randint(7, 21), random.randint(0, 59),
                                             random.randint(0, 59)))
        result.append(clamp_now(t))
    result.sort()
    return result


run("DELETE FROM sys_logininfor")
BROWSERS = ["Chrome 120", "Chrome 121", "Edge 120", "Firefox 121", "360SE", "IE 11"]
OSES = ["Windows 10", "Windows 11", "Windows 7", "Windows Server 2016"]
login_times = time_pool(240)
fail_idx = set(random.sample(range(240), 12))
for i, t in enumerate(login_times):
    name = random.choice(LOGIN_NAMES)
    ip = random.choice(["192.168.10.", "10.10.20."]) + str(random.randint(2, 250))
    failed = i in fail_idx
    run("INSERT INTO sys_logininfor(login_name,ipaddr,login_location,browser,os,status,msg,login_time) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)" % (
            q(name), q(ip), q("广西梧州市藤县"), q(random.choice(BROWSERS)), q(random.choice(OSES)),
            q("1" if failed else "0"), q("密码错误" if failed else "登录成功"), q(t)))

run("DELETE FROM sys_oper_log")
OPER_TEMPLATES = [
    ("门诊挂号", 1, "com.ruoyi.web.controller.business.RegistrationController.add()", "POST", "/business/registration/add", '{"patientName":"%s","deptName":"%s","regType":"普通号"}'),
    ("门诊挂号", 2, "com.ruoyi.web.controller.business.RegistrationController.edit()", "POST", "/business/registration/edit", '{"regNo":"%s","status":"2"}'),
    ("门诊挂号", 0, "com.ruoyi.web.controller.business.RegistrationController.list()", "POST", "/business/registration/list", '{"pageNum":1,"pageSize":10}'),
    ("门诊挂号", 6, "com.ruoyi.web.controller.business.RegistrationController.export()", "POST", "/business/registration/export", '{"deptName":"内科门诊"}'),
    ("患者档案", 1, "com.ruoyi.web.controller.business.PatientController.add()", "POST", "/business/patient/add", '{"name":"%s","gender":"%s"}'),
    ("患者档案", 2, "com.ruoyi.web.controller.business.PatientController.edit()", "POST", "/business/patient/edit", '{"patientNo":"%s"}'),
    ("患者档案", 0, "com.ruoyi.web.controller.business.PatientController.list()", "POST", "/business/patient/list", '{"pageNum":1,"pageSize":10}'),
    ("药品目录", 1, "com.ruoyi.web.controller.business.DrugController.add()", "POST", "/business/drug/add", '{"drugName":"%s"}'),
    ("药品目录", 2, "com.ruoyi.web.controller.business.DrugController.edit()", "POST", "/business/drug/edit", '{"drugCode":"YP0001","stock":200}'),
    ("药品目录", 0, "com.ruoyi.web.controller.business.DrugController.list()", "POST", "/business/drug/list", '{"pageNum":1,"pageSize":10}'),
    ("处方发药", 2, "com.ruoyi.web.controller.business.PrescriptionController.dispense()", "POST", "/business/prescription/dispense", '{"prescNo":"%s"}'),
    ("处方发药", 0, "com.ruoyi.web.controller.business.PrescriptionController.list()", "POST", "/business/prescription/list", '{"status":"0"}'),
    ("系统管理", 1, "com.ruoyi.web.controller.system.SysUserController.add()", "POST", "/system/user/add", '{"loginName":"%s"}'),
    ("系统管理", 2, "com.ruoyi.web.controller.system.SysDeptController.edit()", "POST", "/system/dept/edit", '{"deptId":105}'),
    ("系统管理", 0, "com.ruoyi.web.controller.system.SysUserController.list()", "POST", "/system/user/list", '{"pageNum":1,"pageSize":10}'),
]
DEPS = [DEPT_NAME[d[2]] for d in EMPLOYEES]
oper_times = time_pool(350)
fail_op = set(random.sample(range(350), 7))
for i, t in enumerate(oper_times):
    title, btype, method, req, url, param_tpl = random.choice(OPER_TEMPLATES)
    emp = random.choice(EMPLOYEES)
    login = "TX%04d" % (emp[0] - 2000)
    ip = random.choice(["192.168.10.", "10.10.20."]) + str(random.randint(2, 250))
    cnt = param_tpl.count("%s")
    if cnt >= 2:
        param = param_tpl % (random.choice([p["name"] for p in patients]), random.choice(["男", "女"]))
    elif cnt == 1:
        param = param_tpl % random.choice([p["name"] for p in patients])
    else:
        param = param_tpl
    if param_tpl.count("%s") == 1 and "drugName" in param_tpl:
        param = param_tpl % random.choice([x[0] for x in DRUG_BASE])
    if param_tpl.count("%s") == 1 and "regNo" in param_tpl:
        param = param_tpl % random.choice([r["reg_no"] for r in registrations])
    if param_tpl.count("%s") == 1 and "prescNo" in param_tpl:
        param = param_tpl % random.choice([r["presc_no"] for r in prescriptions])
    if param_tpl.count("%s") == 1 and "patientNo" in param_tpl:
        param = param_tpl % random.choice([p["patient_no"] for p in patients])
    if param_tpl.count("%s") == 1 and "loginName" in param_tpl:
        param = param_tpl % login
    failed = i in fail_op
    run("INSERT INTO sys_oper_log(title,business_type,method,request_method,operator_type,"
        "oper_name,dept_name,oper_url,oper_ip,oper_location,oper_param,json_result,status,"
        "error_msg,oper_time) VALUES (%s,%d,%s,%s,1,%s,%s,%s,%s,%s,%s,%s,%d,%s,%s)" % (
            q(title), btype, q(method), q(req), q(login), q(DEPT_NAME[emp[2]]), q(url), q(ip),
            q("广西梧州市藤县"), q(param), q('{"msg":"操作成功","code":0}'),
            1 if failed else 0, q("操作失败：参数校验未通过" if failed else ""), q(t)))

# ---------------------------------------------------------------------------
# 10. 自校验
# ---------------------------------------------------------------------------
checks = {}
for t in ["biz_patient", "biz_registration", "biz_prescription", "biz_drug"]:
    cur.execute("SELECT COUNT(*) FROM %s" % t)
    checks[t] = cur.fetchone()[0]
assert checks["biz_patient"] == 300, checks
assert checks["biz_registration"] == 900, checks
assert checks["biz_prescription"] == 650, checks
assert checks["biz_drug"] == 220, checks

for t in ["biz_patient", "biz_registration", "biz_prescription", "biz_drug"]:
    cur.execute("SELECT MAX(create_time), MAX(update_time) FROM %s" % t)
    mc, mu = cur.fetchone()
    assert mc is None or mc <= NOW, (t, "create_time", mc, NOW)
    assert mu is None or mu <= NOW, (t, "update_time", mu, NOW)

cur.execute("SELECT COUNT(*) FROM biz_registration WHERE visit_date > CURDATE() AND status <> '0'")
assert cur.fetchone()[0] == 0
cur.execute("SELECT COUNT(*) FROM biz_registration WHERE visit_date > DATE_ADD(CURDATE(), INTERVAL 7 DAY)")
assert cur.fetchone()[0] == 0
cur.execute("SELECT COUNT(*) FROM biz_prescription p LEFT JOIN biz_registration r ON p.reg_id=r.reg_id "
            "WHERE r.status <> '2' OR p.presc_date <> r.visit_date OR p.presc_date > CURDATE()")
assert cur.fetchone()[0] == 0
cur.execute("SELECT COUNT(*) FROM biz_drug WHERE stock < safety_stock")
low = cur.fetchone()[0]
assert low >= 15, low
cur.execute("SELECT COUNT(*) FROM sys_logininfor")
login_count = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM sys_oper_log")
oper_count = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM sys_logininfor WHERE DAYOFWEEK(login_time) IN (1,7)")
login_weekend = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM sys_oper_log WHERE DAYOFWEEK(oper_time) IN (1,7)")
oper_weekend = cur.fetchone()[0]
assert login_count >= 150 and login_weekend <= login_count * 0.15
assert oper_count >= 250 and oper_weekend <= oper_count * 0.15
cur.execute("SELECT COUNT(*) FROM sys_dept")
dept_count = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM sys_user")
user_count = cur.fetchone()[0]

sql_out.write("\nSET FOREIGN_KEY_CHECKS = 1;\n")
sql_out.close()
conn.commit()

print("=" * 62)
print("业务表行数: patient=%d registration=%d prescription=%d drug=%d" % (
    checks["biz_patient"], checks["biz_registration"], checks["biz_prescription"], checks["biz_drug"]))
print("库存预警(低于安全库存): %d" % low)
print("部门数=%d 用户数=%d 登录日志=%d 操作日志=%d" % (dept_count, user_count, login_count, oper_count))
print("登录日志周末占比=%.1f%% 操作日志周末占比=%.1f%%" % (
    login_weekend * 100.0 / login_count, oper_weekend * 100.0 / oper_count))
print("SQL 已落盘: %s" % SQL_FILE)
print("=" * 62)
