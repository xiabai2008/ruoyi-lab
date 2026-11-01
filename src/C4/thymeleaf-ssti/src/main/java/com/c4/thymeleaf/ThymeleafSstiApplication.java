package com.c4.thymeleaf;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * Thymeleaf / SpEL 视图名注入靶场。
 *
 * 真实漏洞成因
 * ============
 * Spring MVC 把 URL 路径片段当**视图名**返回时（`return "redirect:" + path` 或
 * `return path;`），Thymeleaf 会解析视图名里的 `__${...}__` 前置处理器语法并用
 * SpEL 求值。于是路径里的表达式被执行 —— 这是 Thymeleaf SSTI 的经典形态
 * （CVE-2019-3799 spring-cloud-config 等一堆 Spring 生态 SSTI 的同一根因）。
 *
 * 本靶场用**真实 Thymeleaf 引擎 + SpEL** 求值，不是 marker 桩：
 *   GET /__%24%7B7*7%7D__::.x
 *   → 视图名被解析为 49 → 报错页里出现 49 + org.thymeleaf 异常栈
 *
 * 为什么用报错页而不是正常渲染
 * ============================
 * 真实场景里表达式求值成功但找不到对应模板，于是抛 TemplateInputException，
 * 异常栈里同时含求值结果 49 和 org.thymeleaf 字样 —— 这正是扫描器判定依赖的
 * 「49 + 引擎强特征」组合。靶场必须还原这个真实形态，而不是返回一个干净的 200。
 *
 * 不使用破坏性 payload（不执行系统命令），只做算术求值。
 */
@SpringBootApplication
public class ThymeleafSstiApplication {

    public static void main(String[] args) {
        SpringApplication.run(ThymeleafSstiApplication.class, args);
    }
}
