-- R10 星图数据：组织结构收尾
-- 1) 清掉 JeecgBoot 自带的演示租户「北京卓尔互动」及其下级
-- 2) 清掉被误建成部门的「研发经理」（org_type=3 是岗位，不是部门）
-- 3) 补 6 个三级小组，让部门树 ≥15 节点且三层结构完整
-- 4) 修正 org_code 写成部门名的那条脏数据

USE ry_r10;
SET NAMES utf8mb4;

-- ---------- 1. 清演示租户 ----------
DELETE FROM sys_depart WHERE org_code = 'A02' OR org_code LIKE 'A02%';
-- 对应部门下的用户挪回公司本部，避免出现孤儿 org_code
UPDATE sys_user SET org_code = 'A01' WHERE org_code = 'A02' OR org_code LIKE 'A02%';

-- ---------- 2. 清误建的「研发经理」部门 ----------
DELETE FROM sys_depart WHERE id = '63775228b7b041a99825f79760590b7d';

-- ---------- 3. 补三级小组 ----------
INSERT INTO sys_depart
  (id, parent_id, depart_name, depart_name_en, depart_name_abbr, depart_order,
   description, org_category, org_type, org_code, mobile, fax, address, memo,
   status, del_flag, qywx_identifier, create_by, create_time, update_by, update_time,
   tenant_id, iz_leaf)
VALUES
  ('1830000000000000101', '26fe283d23625b1589d5e35e948c8d94', '产品设计组', 'Product Design', '设计组', 1,
   '负责报表产品交互与视觉设计', '1', '2', 'A01A01A01', NULL, NULL, '北京市海淀区中关村软件园', NULL,
   '1', '0', NULL, 'admin', '2024-03-12 09:20:00', NULL, NULL, 0, 1),
  ('1830000000000000102', '26fe283d23625b1589d5e35e948c8d94', '用户研究组', 'User Research', '用研组', 2,
   '负责客户访谈、需求调研与可用性测试', '1', '2', 'A01A01A02', NULL, NULL, '北京市海淀区中关村软件园', NULL,
   '1', '0', NULL, 'admin', '2024-03-12 09:22:00', NULL, NULL, 0, 1),
  ('1830000000000000103', '4f1765520d6346f9bd9c79e2479e5b12', '数据仓库组', 'Data Warehouse', '数仓组', 1,
   '负责数据集接入、ETL 调度与指标口径治理', '1', '2', 'A01A03A01', NULL, NULL, '北京市海淀区中关村软件园', NULL,
   '1', '0', NULL, 'admin', '2024-03-12 09:25:00', NULL, NULL, 0, 1),
  ('1830000000000000104', '4f1765520d6346f9bd9c79e2479e5b12', '算法组', 'Algorithm', '算法组', 2,
   '负责报表智能洞察与异常检测模型', '1', '2', 'A01A03A02', NULL, NULL, '北京市海淀区中关村软件园', NULL,
   '1', '0', NULL, 'admin', '2024-03-12 09:27:00', NULL, NULL, 0, 1),
  ('1830000000000000105', '1582683631414632450', 'SRE 组', 'SRE', 'SRE组', 1,
   '负责平台稳定性、容量与发布', '1', '2', 'A01A06A01', NULL, NULL, '北京市海淀区中关村软件园', NULL,
   '1', '0', NULL, 'admin', '2024-03-12 09:30:00', NULL, NULL, 0, 1),
  ('1830000000000000106', '1582683631414632450', '安全合规组', 'Security & Compliance', '安全组', 2,
   '负责数据安全、权限审计与等保合规', '1', '2', 'A01A06A02', NULL, NULL, '北京市海淀区中关村软件园', NULL,
   '1', '0', NULL, 'admin', '2024-03-12 09:32:00', NULL, NULL, 0, 1);

-- ---------- 4. 修正脏数据 ----------
UPDATE sys_user SET org_code = 'A01A03' WHERE org_code = '财务部';

-- ---------- 5. 把部分人员下沉到小组，避免小组空编 ----------
-- 产品部 3 人 -> 产品设计组 2 / 用户研究组 1
UPDATE sys_user SET org_code = 'A01A01A01'
 WHERE org_code = 'A01A01' ORDER BY username LIMIT 2;
UPDATE sys_user SET org_code = 'A01A01A02'
 WHERE org_code = 'A01A01' ORDER BY username LIMIT 1;
-- 数据部 4 人 -> 数仓组 2 / 算法组 2
UPDATE sys_user SET org_code = 'A01A03A01'
 WHERE org_code = 'A01A03' ORDER BY username LIMIT 2;
UPDATE sys_user SET org_code = 'A01A03A02'
 WHERE org_code = 'A01A03' ORDER BY username LIMIT 2;
-- 运维部 2 人 -> SRE 1 / 安全合规 1
UPDATE sys_user SET org_code = 'A01A06A01'
 WHERE org_code = 'A01A06' ORDER BY username LIMIT 1;
UPDATE sys_user SET org_code = 'A01A06A02'
 WHERE org_code = 'A01A06' ORDER BY username LIMIT 1;

SELECT org_code, depart_name, IFNULL(parent_id,'(root)') AS pid, org_type
FROM sys_depart ORDER BY org_code;
