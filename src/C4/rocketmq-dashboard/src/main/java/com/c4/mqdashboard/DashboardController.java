package com.c4.mqdashboard;

import java.util.List;
import java.util.Map;

import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.ResponseBody;

/**
 * 复刻 rocketmq-console-ng 的真实路由结构。
 *
 * 关键点（决定扫描器能不能命中）：
 *   - 控制台挂在 **根路径 /**，不是 /rocketmq/ 也不是 /dashboard/
 *     （真实 rocketmq-dashboard 是独立 Web 应用，默认 context-path 为空）
 *   - 页面标题含 "RocketMQ Dashboard"
 *   - 导航里含 mqnamesrv / NameServer / Broker 等专有词
 *   - /cluster/list.json 等接口返回真实结构
 *
 * 这正是多数扫描器探 /rocketmq/ 会漏判的原因：它们猜的是路径前缀，
 * 而真实部署就在根上。
 */
@Controller
public class DashboardController {

    /** 控制台首页 —— 无鉴权直接渲染 */
    @GetMapping("/")
    public String index(Model model) {
        model.addAttribute("namesrvAddr", "10.20.30.41:9876;10.20.30.42:9876");
        model.addAttribute("clusterName", "rocketmq-cluster-prod");
        model.addAttribute("version", "4.9.4");
        model.addAttribute("topics", List.of(
                Map.of("name", "TBW102", "readQueueNums", 8, "perm", 6),
                Map.of("name", "SELF_TEST_TOPIC", "readQueueNums", 1, "perm", 6),
                Map.of("name", "order_create_topic", "readQueueNums", 16, "perm", 6),
                Map.of("name", "order_pay_notify", "readQueueNums", 8, "perm", 6),
                Map.of("name", "inventory_sync", "readQueueNums", 4, "perm", 6)));
        model.addAttribute("brokers", List.of(
                Map.of("addr", "10.20.30.41:10911", "brokerName", "broker-a", "id", 0),
                Map.of("addr", "10.20.30.42:10911", "brokerName", "broker-b", "id", 0)));
        return "index";
    }

    /** 真实 dashboard 的集群接口（前端异步拉取） */
    @GetMapping("/cluster/list.json")
    @ResponseBody
    public Map<String, Object> clusterList() {
        return Map.of(
                "data", List.of(
                        Map.of("brokerName", "broker-a", "brokerAddrs", Map.of("0", "10.20.30.41:10911"),
                                "cluster", "rocketmq-cluster-prod"),
                        Map.of("brokerName", "broker-b", "brokerAddrs", Map.of("0", "10.20.30.42:10911"),
                                "cluster", "rocketmq-cluster-prod")),
                "status", 0);
    }

    @GetMapping("/topic/list.query")
    @ResponseBody
    public Map<String, Object> topicList() {
        return Map.of("data", Map.of("topicList", List.of("TBW102", "order_create_topic", "order_pay_notify")),
                "status", 0);
    }

    /** mqnamesrv 信息接口：扫描器惯用的专有标识之一 */
    @GetMapping("/namesrv/addr")
    @ResponseBody
    public Map<String, Object> namesrvAddr() {
        return Map.of("data", "10.20.30.41:9876;10.20.30.42:9876", "status", 0);
    }
}
