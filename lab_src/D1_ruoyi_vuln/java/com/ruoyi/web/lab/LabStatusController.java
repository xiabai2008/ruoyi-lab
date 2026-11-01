package com.ruoyi.web.lab;

import java.util.LinkedHashMap;
import java.util.Map;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import com.ruoyi.framework.lab.LabMode;

/**
 * 漏洞演示模块 —— 运行模式自检端点。
 *
 * <p>{@code GET /lab/status} 在 Shiro 过滤链里被固定放行（无论 safe/vuln），
 * 只返回当前模式，不涉及任何业务数据，供启停脚本与验收脚本确认运行态。</p>
 */
@RestController
@RequestMapping("/lab")
public class LabStatusController
{
    private final LabMode labMode;

    public LabStatusController(LabMode labMode)
    {
        this.labMode = labMode;
    }

    @GetMapping("/status")
    public Map<String, Object> status()
    {
        Map<String, Object> body = new LinkedHashMap<String, Object>();
        body.put("site", "D1");
        body.put("labMode", labMode.current());
        return body;
    }
}
