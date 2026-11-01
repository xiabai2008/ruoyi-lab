package org.jeecg.modules.lab;

import org.jeecg.common.util.RedisUtil;
import org.jeecg.config.JeecgBaseConfig;
import org.springframework.boot.web.servlet.FilterRegistrationBean;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.Ordered;
import org.springframework.core.env.Environment;

import javax.servlet.DispatcherType;
import javax.sql.DataSource;

/**
 * R10 漏洞演示模块 —— 过滤器注册。
 *
 * <p>8 个历史漏洞端点里有 7 个已被 JeecgBoot / 积木报表自身的 Controller 占用
 * （/sys/login、/sys/dict/list、/sys/user/queryUserByDepId、/jmreport/list、
 * /jmreport/upload、/jmreport/testConnection、/jmreport/queryFieldBySql），
 * 若再声明 @RequestMapping 会在启动时报 "Ambiguous mapping" 直接失败。
 * 因此演示行为放在 Servlet Filter 里按「精确路径 + 精确方法」接管，
 * 未命中的请求原样放行，对 safe 模式和正常业务零影响。</p>
 *
 * <p>过滤器顺序在 Shiro/JWT 之前（HIGHEST_PRECEDENCE + 20），这样 vuln 模式下
 * 匿名请求可以在鉴权墙之前直接抵达演示逻辑。</p>
 */
@Configuration
public class LabModuleConfig {

    @Bean
    public FilterRegistrationBean<LabVulnerabilityFilter> labVulnerabilityFilterRegistration(
            DataSource dataSource,
            JeecgBaseConfig jeecgBaseConfig,
            Environment environment,
            RedisUtil redisUtil) {
        LabMode labMode = new LabMode(environment);
        LabVulnerabilityService service = new LabVulnerabilityService(
                dataSource, jeecgBaseConfig, environment, redisUtil);
        FilterRegistrationBean<LabVulnerabilityFilter> registration =
                new FilterRegistrationBean<>(new LabVulnerabilityFilter(labMode, service));
        registration.setName("labVulnerabilityFilter");
        registration.addUrlPatterns("/*");
        registration.setOrder(Ordered.HIGHEST_PRECEDENCE + 20);
        registration.setAsyncSupported(true);
        registration.setDispatcherTypes(DispatcherType.REQUEST, DispatcherType.ASYNC);
        return registration;
    }
}
