package com.ruoyi.framework.lab;

import org.springframework.core.env.Environment;
import org.springframework.core.env.Profiles;
import org.springframework.stereotype.Component;

/**
 * D1 邕江物流运输管理系统（RuoYi 4.6.2 二开）—— 漏洞演示模块运行模式。
 *
 * <p>默认 <b>safe</b>：Shiro 过滤链、开放接口求值行为都保持「未开启」，
 * 站点等于没有该二开开放接口的授权面（接口存在但仅登录后可达，且不渲染模板）。</p>
 *
 * <p><b>vuln</b>：满足以下任一条件时开启，复刻两类真实二开疏漏：</p>
 * <ol>
 *   <li>JVM 参数 / 命令行参数 {@code -Dlab.mode=vuln} 或 {@code --lab.mode=vuln}；</li>
 *   <li>Spring profile 激活 {@code vuln}（如 {@code --spring.profiles.active=druid,prod,vuln}）。</li>
 * </ol>
 *
 * <p>开关只在运行期读取，safe 模式不改变 RuoYi 4.6.2 官方行为。</p>
 */
@Component
public class LabMode
{
    /** 模式配置项 */
    public static final String PROPERTY = "lab.mode";

    /** 安全模式：官方 Shiro 过滤链 + 开放接口不求值模板 */
    public static final String SAFE = "safe";

    /** 漏洞演示模式：/openapi/** 进 anon 白名单 + 开放接口按模板求值 */
    public static final String VULN = "vuln";

    private final Environment environment;

    public LabMode(Environment environment)
    {
        this.environment = environment;
    }

    /**
     * 当前模式。优先级：lab.mode 配置 > Spring profile vuln > 默认 safe。
     */
    public String current()
    {
        String value = environment.getProperty(PROPERTY, SAFE);
        if (value != null && VULN.equalsIgnoreCase(value.trim()))
        {
            return VULN;
        }
        if (environment.acceptsProfiles(Profiles.of(VULN)))
        {
            return VULN;
        }
        return SAFE;
    }

    public boolean isVuln()
    {
        return VULN.equals(current());
    }
}
