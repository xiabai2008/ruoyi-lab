-- R9 华电巡检管理系统 · 巡检管理菜单
-- 目标库：ry_r9（MySQL 127.0.0.1:13307）
-- Plus 版 sys_menu 额外列：query_param / is_frame / is_cache / create_dept
SET NAMES utf8mb4;

START TRANSACTION;

DELETE FROM sys_role_menu WHERE menu_id BETWEEN 3000 AND 3049;
DELETE FROM sys_menu WHERE menu_id BETWEEN 3000 AND 3049;

INSERT INTO sys_menu
  (menu_id, menu_name, parent_id, order_num, path, component, query_param, is_frame, is_cache,
   menu_type, visible, status, perms, icon, create_dept, create_by, create_time, remark)
VALUES
  (3000, '巡检管理', 0,    4, 'inspect', '',                     '', 1, 0, 'M', '0', '0', '',                   'monitor',       1000, 1, NOW(), '巡检业务目录'),
  (3010, '设备台账', 3000, 1, 'device',  'inspect/device/index', '', 1, 0, 'C', '0', '0', 'inspect:device:list', 'server',        1000, 1, NOW(), '设备台账查询'),
  (3020, '巡检记录', 3000, 2, 'record',  'inspect/record/index', '', 1, 0, 'C', '0', '0', 'inspect:record:list', 'documentation', 1000, 1, NOW(), '巡检记录查询'),
  (3030, '缺陷工单', 3000, 3, 'defect',  'inspect/defect/index', '', 1, 0, 'C', '0', '0', 'inspect:defect:list', 'bug',           1000, 1, NOW(), '缺陷工单查询'),
  (3040, '巡检计划', 3000, 4, 'plan',    'inspect/plan/index',   '', 1, 0, 'C', '0', '0', 'inspect:plan:list',   'date',          1000, 1, NOW(), '巡检计划查询');

INSERT INTO sys_role_menu (role_id, menu_id)
VALUES (1, 3000), (1, 3010), (1, 3020), (1, 3030), (1, 3040);

COMMIT;
