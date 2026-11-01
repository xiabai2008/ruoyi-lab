package com.c4.mqdashboard;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * RocketMQ Dashboard 未授权访问靶场。
 *
 * 真实背景：rocketmq-console-ng（现名 rocketmq-dashboard）官方发布版**默认不带任何鉴权**。
 * 企业内网部署时几乎没人额外加登录，于是控制台直接暴露在 8080/8081。
 * 这是 RocketMQ Dashboard 未授权（CVE-2023-33246 相关暴露面）的实际成因。
 *
 * 本靶场刻意还原三件事：
 *   1. 无鉴权 —— 访问 / 直接进控制台，不跳登录页
 *   2. 页面含 RocketMQ 专有标识 —— 标题、导航、JS 变量里都有 rocketmq / mqnamesrv
 *   3. 有真实可操作的集群/主题/消费者数据 —— 不是空壳页面
 *
 * 不还原的：真实的消息收发链路（需要 NameServer + Broker，本靶场只测「未授权可达」这一层）。
 */
@SpringBootApplication
public class MqDashboardApplication {

    public static void main(String[] args) {
        SpringApplication.run(MqDashboardApplication.class, args);
    }
}
