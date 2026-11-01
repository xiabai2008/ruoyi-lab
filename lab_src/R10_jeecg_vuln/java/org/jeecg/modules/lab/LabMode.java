package org.jeecg.modules.lab;

import org.springframework.core.env.Environment;
import org.springframework.core.env.Profiles;

/**
 * R10 星图数据（JeecgBoot 3.6.3）漏洞演示模块 —— 运行模式开关。
 *
 * <p>默认 safe：保持 JeecgBoot 3.6.3 官方已修复行为，漏洞演示端点不生效；
 * vuln：满足以下任一条件时开启，由 {@link LabVulnerabilityFilter} 接管 8 个历史漏洞端点。</p>
 *
 * <ul>
 *   <li>JVM 参数 / 命令行参数 {@code -Dlab.mode=vuln} 或 {@code --lab.mode=vuln}</li>
 *   <li>Spring profile 激活 {@code vuln}（如 {@code --spring.profiles.active=dev,vuln}）</li>
 * </ul>
 *
 * <p>该开关只在运行期读取，不修改任何 JeecgBoot 官方配置，因此 safe 模式行为与原始 3.6.3 一致。</p>
 */
public class LabMode {

    /** 模式配置项（Spring Boot 命令行参数 --lab.mode=vuln 等价于 -Dlab.mode=vuln） */
    public static final String PROPERTY = "lab.mode";
    /** 安全模式：保持官方已修复行为 */
    public static final String SAFE = "safe";
    /** 漏洞演示模式：放行 8 个历史漏洞端点 */
    public static final String VULN = "vuln";

    private final Environment environment;

    public LabMode(Environment environment) {
        this.environment = environment;
    }

    /**
     * 当前模式。优先级：lab.mode 配置 > Spring profile vuln > 默认 safe。
     */
    public String current() {
        String value = environment.getProperty(PROPERTY, SAFE);
        if (value != null && VULN.equalsIgnoreCase(value.trim())) {
            return VULN;
        }
        if (environment.acceptsProfiles(Profiles.of(VULN))) {
            return VULN;
        }
        return SAFE;
    }

    public boolean isVuln() {
        return VULN.equals(current());
    }
}
