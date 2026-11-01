package com.c4.jmreport;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * JeecgBoot jmreport 报表 Freemarker 模板注入靶场。
 *
 * 真实漏洞成因
 * ============
 * JeecgBoot 的积木报表（jmreport）「数据源连接测试」接口 /jmreport/testConnection
 * 会把请求里的 connUrl 直接拼进 Freemarker 模板渲染，用于生成测试 SQL。
 * 拼接点未做转义，于是 connUrl 中的 ${...} 会被模板引擎求值 —— 这就是 SSTI。
 *
 * 本靶场用**真实 Freemarker 引擎**求值，不是靠特定 marker 字符串：
 *   connUrl = "jdbc:mysql://h/db?query=${7*7}"
 *   → 模板渲染 → 响应里出现 "49"
 *
 * 这与「靶场返回约定 marker、插件匹配 marker」的签名靶场有本质区别：
 * 扫描器必须真的构造出会被求值的表达式才可能命中，无法靠猜字符串过。
 *
 * 刻意保留的真实行为
 * ==================
 * 未带 Token 时返回的真实 JeecgBoot 响应是 **HTTP 200 + `{"code":500,..."Token校验失败"}`**，
 * 不是 401/403。这个反直觉的形态是「测不到 ≠ 不存在」这类缺陷的温床，
 * 靶场必须原样保留，否则就是在迁就扫描器。
 */
@SpringBootApplication
public class JmreportSstiApplication {

    public static void main(String[] args) {
        SpringApplication.run(JmreportSstiApplication.class, args);
    }
}
