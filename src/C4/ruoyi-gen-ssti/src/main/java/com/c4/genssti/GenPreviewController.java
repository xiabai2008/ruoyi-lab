package com.c4.genssti;

import java.io.StringReader;
import java.io.StringWriter;
import java.util.HashMap;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import freemarker.template.Configuration;
import freemarker.template.Template;

/**
 * 复刻若依 4.x 的代码生成预览接口。
 *
 * 真实若依（GenController#preview）:
 *   @GetMapping("/preview/{tableId}")
 *   public AjaxResult preview(@PathVariable("tableId") Long tableId) {
 *       GenTable table = genTableService.selectGenTableById(tableId);
 *       Map<String, String> dataMap = genTableService.prepareContext(table);
 *       String templateZip = genTableService.downloadCode(...);  // ← 走 Velocity 渲染
 *   }
 *
 * 漏洞点：tableName / comments 等字段来自用户提交（GenController#editSave），
 * 渲染时直接进模板，未过滤 ${}。
 */
@RestController
public class GenPreviewController {

    private final Configuration freemarker;

    public GenPreviewController(Configuration freemarker) {
        this.freemarker = freemarker;
    }

    /**
     * 代码生成预览。
     *
     * 接受 path 变量 tableId + 可选 tableName（真实若依里 tableName 来自库中记录，
     * 但可通过 /tool/gen/edit 的 editSave 写入任意值 —— 这里直接用 query 参数
     * 复刻同样的「用户可控值进模板」）。
     */
    @GetMapping("/tool/gen/preview/{tableId}")
    public String preview(
            @PathVariable("tableId") String tableId,
            @RequestParam(value = "tableName", required = false) String tableName) {

        String name = tableName == null ? "sys_user" : tableName;

        // ★ 漏洞点：用户可控的 tableName 直接拼进模板源码。
        //   真实若依在 Velocity 里用它生成 Mapper XML / Entity 类名。
        String templateSrc = "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
                + "<mapper namespace=\"com.ruoyi.system.mapper." + name + "Mapper\">\n"
                + "    <resultMap type=\"com.ruoyi.system.domain." + name + "\" id=\"BaseResultMap\"/>\n"
                + "    <!-- tableId=" + tableId + " table=" + name + " -->\n"
                + "</mapper>";

        try {
            Template tmpl = new Template("Mapper", new StringReader(templateSrc), freemarker);
            StringWriter out = new StringWriter();
            tmpl.process(new HashMap<String, Object>(), out);
            return out.toString();
        } catch (Exception e) {
            // 模板语法错误时真实若依抛 ServiceException，页面显示错误
            return "<?xml version=\"1.0\"?><!-- 生成失败: " + e.getMessage() + " -->";
        }
    }

    /** 代码生成模块首页（真实若依返回表格列表页，这里给最小占位） */
    @GetMapping("/tool/gen")
    public String index() {
        return "<html><body><h2>代码生成</h2><table id=\"bootstrap-table\"></table></body></html>";
    }

    /** 编辑页（真实若依返回 editable 表单） */
    @GetMapping("/tool/gen/edit")
    public String edit() {
        return "<html><body><h2>修改生成配置</h2>"
                + "<form action=\"/tool/gen/edit\" method=\"post\">"
                + "<input name=\"tableName\" value=\"sys_user\"/></form></body></html>";
    }
}
