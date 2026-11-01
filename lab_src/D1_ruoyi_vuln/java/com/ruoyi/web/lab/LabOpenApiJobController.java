package com.ruoyi.web.lab;

import org.quartz.SchedulerException;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseBody;
import org.springframework.stereotype.Controller;
import com.ruoyi.common.constant.Constants;
import com.ruoyi.common.core.controller.BaseController;
import com.ruoyi.common.core.domain.AjaxResult;
import com.ruoyi.common.exception.job.TaskException;
import com.ruoyi.common.utils.StringUtils;
import com.ruoyi.framework.lab.LabMode;
import com.ruoyi.quartz.domain.SysJob;
import com.ruoyi.quartz.service.ISysJobService;
import com.ruoyi.quartz.util.CronUtils;

/**
 * 二开「内部运维开放接口」—— 定时任务维护。
 *
 * <p>二开背景：运维平台（外部调度系统）需要按改版前的老路径直接维护定时任务。
 * 二期把接口统一迁到 {@code /portal/openapi/**}，网关为兼容老调用保留了路径映射。
 * 该开放接口<b>没有</b> {@code @RequiresPermissions} 权限注解，只依赖 Shiro 的
 * {@code /** = user} 统一登录拦截 —— 这是漏洞成立的前提。</p>
 *
 * <p>漏洞版（{@code lab.mode=vuln}）下 {@code /openapi/**} 被加进 Shiro anon 白名单，
 * 匿名请求可直达本接口真实业务层（{@code ISysJobService}），对不存在的任务返回
 * AjaxResult 业务错误（如 {@code {"code":500,"msg":"任务不存在"}}），而不是登录页。</p>
 *
 * <p>safe 模式（默认）不开启白名单，匿名请求在 Shiro 层即被 302 到 /portal/auth/signin；
 * 即便带会话调用，本接口在 safe 模式也直接返回「未启用」而不会执行真实业务。</p>
 */
@Controller
@RequestMapping("/openapi/monitor/job")
public class LabOpenApiJobController extends BaseController
{
    private final LabMode labMode;

    private final ISysJobService jobService;

    public LabOpenApiJobController(LabMode labMode, ISysJobService jobService)
    {
        this.labMode = labMode;
        this.jobService = jobService;
    }

    /**
     * 修改并保存定时任务（开放接口）。
     *
     * <p>业务校验与官方 {@code SysJobController.editSave} 保持一致（Cron 合法性、rmi 调用
     * 目标拦截），随后调用真实服务层 {@link ISysJobService#updateJob}。</p>
     */
    @PostMapping("/edit")
    @ResponseBody
    public AjaxResult editSave(@Validated SysJob job) throws SchedulerException, TaskException
    {
        if (!labMode.isVuln())
        {
            return AjaxResult.error("开放接口未启用");
        }
        if (!CronUtils.isValid(job.getCronExpression()))
        {
            return AjaxResult.error("修改任务'" + job.getJobName() + "'失败，Cron表达式不正确");
        }
        else if (StringUtils.containsIgnoreCase(job.getInvokeTarget(), Constants.LOOKUP_RMI))
        {
            return AjaxResult.error("修改任务'" + job.getJobName() + "'失败，目标字符串不允许'rmi://'调用");
        }
        SysJob properties = jobService.selectJobById(job.getJobId());
        if (StringUtils.isNull(properties))
        {
            return AjaxResult.error("任务不存在");
        }
        return toAjax(jobService.updateJob(job));
    }
}
