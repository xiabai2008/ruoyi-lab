package com.ruoyi.web.lab;

import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.Map;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.expression.ExpressionParser;
import org.springframework.expression.common.TemplateParserContext;
import org.springframework.expression.spel.standard.SpelExpressionParser;
import org.springframework.expression.spel.support.StandardEvaluationContext;
import org.springframework.stereotype.Controller;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseBody;
import com.ruoyi.common.core.domain.AjaxResult;
import com.ruoyi.common.utils.StringUtils;
import com.ruoyi.framework.lab.LabMode;
import com.ruoyi.generator.domain.GenTable;
import com.ruoyi.generator.service.IGenTableService;

/**
 * 二开「内部运维开放接口」—— 代码生成预览。
 *
 * <p>二开背景：外部低代码平台需要不经登录直接拿到某张业务表的生成代码预览。
 * 该接口除返回官方 {@code GenController.preview} 的模板渲染结果外，还支持客户
 * 自定义「表名模板」：分表场景下表名里可以写 Spring 表达式（与 application.yml
 * 的 {@code ${...}} 写法一致），服务端用 SpEL 模板语法求值后再生成预览。</p>
 *
 * <p>漏洞点：{@code tableName} 查询参数被整体当作 SpEL 模板源码求值（模板注入）。
 * 例如 {@code tableName=sys_user_${7*7}} 会被求值为 {@code sys_user_49}。
 * 官方 RuoYi 4.6.2 的代码生成链路并没有这条求值路径（preview 只接收 tableId，
 * 表名取自库表记录，Velocity 1.7 也不解析 {@code ${7*7}}），因此该行为必须由
 * 二开代码引入才可能存在；详见 docs/D1/漏洞演示模块.md 的「限制」章节。</p>
 */
@Controller
@RequestMapping("/openapi/tool/gen")
public class LabOpenApiGenController
{
    private static final Logger log = LoggerFactory.getLogger(LabOpenApiGenController.class);

    private final LabMode labMode;

    private final IGenTableService genTableService;

    private final ExpressionParser expressionParser = new SpelExpressionParser();

    /** 与 Spring 占位符一致的 ${...} 模板分隔符 */
    private final TemplateParserContext templateParserContext = new TemplateParserContext("${", "}");

    public LabOpenApiGenController(LabMode labMode, IGenTableService genTableService)
    {
        this.labMode = labMode;
        this.genTableService = genTableService;
    }

    /**
     * 预览指定业务表生成的代码（开放接口）。
     *
     * @param tableId   业务表编号（与官方 /tool/gen/preview/{tableId} 一致）
     * @param tableName 可选：表名模板，按 SpEL 模板语法求值（真实表达式求值）
     */
    @GetMapping("/preview/{tableId}")
    @ResponseBody
    public AjaxResult preview(@PathVariable("tableId") Long tableId,
            @RequestParam(value = "tableName", required = false) String tableName)
    {
        if (!labMode.isVuln())
        {
            return AjaxResult.error("开放接口未启用");
        }
        Map<String, Object> data = new LinkedHashMap<String, Object>();
        data.put("tableId", tableId);
        if (StringUtils.isNotEmpty(tableName))
        {
            data.put("tableName", renderTableNameTemplate(tableName));
        }
        GenTable table = null;
        try
        {
            table = genTableService.selectGenTableById(tableId);
        }
        catch (RuntimeException e)
        {
            // 官方 GenTableServiceImpl.selectGenTableById 在记录不存在时会 NPE
            //（setTableFromOptions(null)），这里按「业务表未导入」处理，不中断预览。
            log.warn("[lab] 查询业务表不存在或失败，按未导入处理: {}", e.getMessage());
        }
        if (table != null)
        {
            // 真实代码生成链路：走官方 GenTableServiceImpl.previewCode（Velocity 渲染）
            data.put("templates", genTableService.previewCode(tableId));
        }
        else
        {
            data.put("templates", Collections.emptyMap());
            data.put("message", "业务表未导入，仅返回表名模板渲染结果");
        }
        return AjaxResult.success(data);
    }

    /**
     * 表名模板求值：SpEL 模板语法（{@code ${表达式}}），真实表达式求值而非字符串拼接。
     */
    private String renderTableNameTemplate(String template)
    {
        try
        {
            return expressionParser.parseExpression(template, templateParserContext)
                    .getValue(new StandardEvaluationContext(), String.class);
        }
        catch (Exception e)
        {
            log.warn("[lab] 表名模板求值失败: {}", e.getMessage());
            return template;
        }
    }
}
