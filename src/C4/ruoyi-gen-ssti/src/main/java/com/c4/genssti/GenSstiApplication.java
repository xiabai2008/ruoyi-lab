package com.c4.genssti;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * 若依代码生成模块 SSTI 靶场。
 *
 * 真实漏洞成因
 * ============
 * 若依 4.x 的代码生成模块 `/tool/gen/preview/{tableId}` 会把表名/字段名拼进
 * Velocity 模板渲染（生成 mapper.xml / 实体类源码）。拼接点未做表达式过滤，
 * 于是路径或参数里的 `${...}` 会被模板引擎求值。
 *
 * 本靶场用**真实 Freemarker 引擎**复刻这一行为 —— 参数量级与真实若依一致：
 *   GET /tool/gen/preview/1?tableName=sys_user_${7*7}
 *   → 生成代码里出现 "49"
 *
 * 与 ruoyi_gen_rce 插件历史实现的关系
 * ===================================
 * 该插件原本有一条 `X-Ruoyi-Vuln: gen-ssti` 签名头快速路径 —— 那是给自建靶场
 * 开的后门，真实站点永远不会返回这个头。真实行为路径只会给 UNKNOWN。
 * 本靶场的作用就是让真实路径也能被测到。
 *
 * 鉴权：真实若依 /tool/gen/** 需要 tool:gen:preview 权限。本靶场**提供一个
 * 未鉴权的入口**（模拟权限注解配置不当 / 低权账号），让 SSTI 本身可测；
 * 鉴权拒绝的场景由 C4-4（jmreport）和 R10 覆盖。
 */
@SpringBootApplication
public class GenSstiApplication {

    public static void main(String[] args) {
        SpringApplication.run(GenSstiApplication.class, args);
    }
}
