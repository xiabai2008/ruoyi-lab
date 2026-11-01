package com.c4.jmreport;

import java.io.StringReader;
import java.io.StringWriter;
import java.util.HashMap;
import java.util.Map;

import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

import freemarker.template.Configuration;
import freemarker.template.Template;

/**
 * 复刻 JeecgBoot jmreport 的 /testConnection 数据源连接测试接口。
 *
 * 真实行为：把请求体里的 connUrl 当作 Freemarker 模板渲染（用于生成测试用 SQL）。
 * 漏洞点就是「用户可控字符串直接进模板引擎」。
 */
@RestController
public class TestConnectionController {

    /**
     * 与真实 jmreport 一致的 JDBC 表单结构。
     */
    public record TestConnectionRequest(
            String dbType, String dbName, String url,
            String userName, String password, String connUrl) {
    }

    private final Configuration freemarker;

    public TestConnectionController(Configuration freemarker) {
        this.freemarker = freemarker;
    }

    /**
     * 数据源连接测试。
     *
     * 真实 JeecgBoot 这里会先校验 Token；本靶场**不做鉴权**（这是漏洞成立的前提：
     * 积木报表默认匿名可达的历史问题）。鉴权拒绝的形态在 C4-5 里单独立站，
     * 让两个场景分别可测。
     */
    @PostMapping("/jeecg-boot/jmreport/testConnection")
    public Map<String, Object> testConnection(@RequestBody TestConnectionRequest req) {
        Map<String, Object> resp = new HashMap<>();
        String connUrl = req.connUrl() == null ? "" : req.connUrl();

        // ★ 漏洞点：用户可控输入直接交给模板引擎渲染。
        //   真实 jmreport 用 connUrl 拼测试 SQL，为了支持动态库名等场景走了模板渲染，
        //   但没有把 ${} 这类表达式语法过滤掉。
        String rendered;
        try {
            Template tmpl = new Template("connUrl", new StringReader(connUrl), freemarker);
            StringWriter out = new StringWriter();
            tmpl.process(new HashMap<>(), out);
            rendered = out.toString();
        } catch (Exception e) {
            // 模板语法错误时真实接口返回业务错误 JSON，不是 500 HTML —— 原样保留
            resp.put("success", false);
            resp.put("code", 500);
            resp.put("message", "连接失败：" + e.getMessage());
            return resp;
        }

        // 真实响应结构：校验通过后回 success + 渲染后的连接串
        resp.put("success", true);
        resp.put("code", 200);
        resp.put("message", "连接成功");
        // 把渲染结果回显出来 —— 这正是 ${7*7} 变成 49 的可见位置
        resp.put("connUrl", rendered);
        resp.put("dbType", req.dbType());
        return resp;
    }
}
