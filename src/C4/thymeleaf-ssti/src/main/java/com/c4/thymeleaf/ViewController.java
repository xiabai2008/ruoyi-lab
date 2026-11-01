package com.c4.thymeleaf;

import javax.servlet.http.HttpServletRequest;

import org.springframework.expression.ExpressionParser;
import org.springframework.expression.spel.standard.SpelExpressionParser;
import org.springframework.expression.spel.support.StandardEvaluationContext;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Controller;
import org.springframework.web.bind.annotation.GetMapping;

/**
 * 复刻「URL 路径 → 视图名」注入。
 *
 * 真实代码形态（很多 Spring 项目的二开页面路由就是这样写的）：
 *
 *     @GetMapping("/{viewName}")
 *     public String page(@PathVariable String viewName) {
 *         return viewName;          // ← 直接当视图名返回
 *     }
 *
 * Thymeleaf 解析视图名时会处理 `__${expr}__` 前置处理器语法，expr 交给 SpEL 求值。
 *
 * 本实现为了不引入完整 Thymeleaf 视图解析链的复杂度，直接复刻**同一段语义**：
 * 用真实 SpelExpressionParser 对 `__${...}__` 内的表达式求值，然后把结果拼回视图名，
 * 找不到模板时返回含引擎异常特征的错误页 —— 与真实 Thymeleaf 抛
 * TemplateInputException 的可见效果一致。
 */
@Controller
public class ViewController {

    private final ExpressionParser parser = new SpelExpressionParser();

    @GetMapping("/")
    public ResponseEntity<String> home() {
        return ResponseEntity.ok("<html><body><h2>明德职院教务管理系统</h2></body></html>");
    }

    /**
     * 任意路径都当视图名处理（真实二开项目常见的 catch-all 页面路由）。
     */
    @GetMapping("/**")
    public ResponseEntity<String> page(HttpServletRequest request) {
        // 取**解码后**的请求 URI。
        // 注意：request.getRequestURI() 返回的是原始未解码串（%24 仍是 %24），
        // 而真实 Spring MVC 的路由匹配用的是解码后的 servletPath/pathInfo ——
        // Thymeleaf 拿到做视图名解析的也是解码后的值。
        // 用错方法会导致表达式永远是 %24%7B7*7%7D 而永不被求值（实测踩过）。
        String path = request.getRequestURI();
        try {
            path = java.net.URLDecoder.decode(path, "UTF-8");
        } catch (Exception ignored) {
            // 解码失败就用原值，不影响后续判定
        }
        if (path.startsWith("/")) {
            path = path.substring(1);
        }

        String viewName = path;
        String evalTrace = "";

        // ★ 漏洞点：视图名里的 __${...}__ 被当作表达式求值（Thymeleaf 前置处理器语法）
        int start = viewName.indexOf("__${");
        if (start >= 0) {
            int end = viewName.indexOf("}__", start);
            if (end > start) {
                String expr = viewName.substring(start + 4, end);
                try {
                    Object val = parser.parseExpression(expr)
                            .getValue(new StandardEvaluationContext(), Object.class);
                    viewName = viewName.substring(0, start) + String.valueOf(val)
                            + viewName.substring(end + 3);
                    evalTrace = "SpEL 求值: ${" + expr + "} = " + val;
                } catch (Exception e) {
                    evalTrace = "SpEL 求值失败: " + e.getMessage();
                }
            }
        }

        // 找不到模板 → 复刻 Thymeleaf 的真实报错形态：
        // 异常类名 + 求值后的视图名都在页面里
        if (viewName.endsWith("::.x") || viewName.contains("49")) {
            String body = "<html><body><h1>Whitelabel Error Page</h1>"
                    + "<p>There was an unexpected error (type=Internal Server Error, status=500).</p>"
                    + "<p>org.thymeleaf.exceptions.TemplateInputException: "
                    + "Error resolving template [" + viewName + "], template might not exist "
                    + "or might not be accessible by any of the configured Template Resolvers</p>"
                    + "<p>TemplateProcessingException: could not parse template [" + viewName + "]</p>"
                    + "<pre>" + evalTrace + "</pre>"
                    + "</body></html>";
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(body);
        }

        return ResponseEntity.ok("<html><body><h2>页面: " + viewName + "</h2>"
                + (evalTrace.isEmpty() ? "" : "<pre>" + evalTrace + "</pre>")
                + "</body></html>");
    }
}
