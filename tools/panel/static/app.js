/* 若依靶场管理平台 —— 免构建单页（Vue 3 + Element Plus 本地 vendor） */
(function () {
  "use strict";

  const { createApp, ref, reactive, computed, onMounted, onBeforeUnmount, watch, nextTick } = Vue;
  const { ElMessage, ElMessageBox } = ElementPlus;

  const STATE_LABELS = {
    RUNNING: "运行中",
    STARTING: "启动中",
    STOPPING: "停止中",
    QUEUED: "排队中",
    DEGRADED: "异常",
    STOPPED: "已停止",
    BROKEN: "故障",
    NOT_READY: "未就绪",
    UNKNOWN: "未知",
  };
  const BUILD_LABELS = { ready: "就绪", partial: "部分就绪", unbuilt: "未构建", absent: "缺失" };
  const GROUP_RANK = { site: 0, holdout: 1, component: 2, middleware: 3, special: 4, infra: 5, extra: 6 };
  const FINISHED = ["success", "partial", "failed", "cancelled"];

  const app = createApp({
    setup() {
      const labRoot = ref("");
      const targets = ref([]);
      const groups = ref([]);
      const environment = ref([]);
      const statusMap = ref({});
      const activeMap = ref({});
      const operations = ref([]);
      const scannedAt = ref("");
      const statusAt = ref("");
      const statusDuration = ref(null);
      const loading = ref(false);
      const initialLoading = ref(true);
      const scanning = ref(false);
      const cleaning = ref(false);
      const search = ref("");
      const activeGroup = ref("all");
      const onlyRunning = ref(false);
      const onlyProblem = ref(false);
      const groupBusy = ref("");
      const busyTargets = reactive({});
      const theme = ref(localStorage.getItem("panel-theme") || "dark");
      const themeStyle = ref(localStorage.getItem("panel-style") || "steady");
      const sseConnected = ref(false);
      const now = ref(Date.now());

      const drawerOpen = ref(false);
      const detailId = ref("");
      const detailTab = ref("overview");
      const detailTabs = [
        { key: "overview", label: "概览" },
        { key: "build", label: "构建检查" },
        { key: "deps", label: "依赖与说明" },
        { key: "logs", label: "运行日志" },
      ];
      const detailLogs = reactive({ files: [], note: "" });

      const historyOpen = ref(false);
      const currentOp = ref(null);
      const showLog = ref(false);
      const autoScroll = ref(true);
      const logEl = ref(null);
      const opLogs = reactive({});

      let eventSource = null;
      let statusTimer = null;
      let clockTimer = null;
      let destroyed = false;

      // ── 基础状态访问 ──

      function statusOf(t) {
        return statusMap.value[t.id] || t.status || {};
      }

      function stateOf(t) {
        const s = statusOf(t);
        const op = activeMap.value[t.id] || s.operation_state;
        if (op) return op;
        if (t.pair_id) {
          const other = targets.value.find((x) => x.pair_id === t.pair_id && x.id !== t.id);
          if (other) {
            const os = activeMap.value[other.id] || statusOf(other).operation_state;
            if (os) return os;
          }
        }
        return s.display_state || "UNKNOWN";
      }

      function stateLabel(t) {
        return STATE_LABELS[stateOf(t)] || "未知";
      }

      function buildLabel(s) {
        return BUILD_LABELS[s] || s || "未知";
      }

      function canStart(t) {
        if (busyTargets[t.id]) return false;
        const st = stateOf(t);
        if (["RUNNING", "STARTING", "STOPPING", "QUEUED"].includes(st)) return false;
        return ["ready", "partial"].includes(t.build && t.build.state);
      }

      function canStop(t) {
        if (busyTargets[t.id]) return false;
        if (!t.stop_enabled) return false;
        const st = stateOf(t);
        if (["RUNNING", "DEGRADED", "BROKEN"].includes(st)) return true;
        // Nginx 没跑时，conf 还开着的目标会显示“已停止”，但停止动作仍然
        // 有意义：它会把 conf 改回 .disabled，避免下次启动 Nginx 时意外暴露。
        const s = statusOf(t);
        return st === "STOPPED" && !!(t.conf_name && s.conf_enabled);
      }

      function isOperating(t, state) {
        return stateOf(t) === state;
      }

      // ── 聚合 / 过滤 ──

      const groupTabs = computed(() => {
        const tabs = [{ key: "all", label: "全部", count: targets.value.length, note: "", targets: [], start_targets: [] }];
        for (const g of groups.value) tabs.push({ ...g, count: (g.targets || []).length });
        return tabs;
      });

      const currentGroup = computed(() => groupTabs.value.find((g) => g.key === activeGroup.value) || groupTabs.value[0]);

      const filteredTargets = computed(() => {
        let list = targets.value.slice();
        if (activeGroup.value !== "all") {
          const g = groups.value.find((x) => x.key === activeGroup.value);
          const allowed = new Set(g ? g.targets : []);
          list = list.filter((t) => allowed.has(t.id));
        }
        const q = search.value.trim().toLowerCase();
        if (q) {
          list = list.filter((t) =>
            [t.id, t.name, t.business, String(t.entry || ""), String(t.backend || "")]
              .join(" ")
              .toLowerCase()
              .includes(q)
          );
        }
        if (onlyRunning.value) list = list.filter((t) => stateOf(t) === "RUNNING");
        if (onlyProblem.value) list = list.filter((t) => ["DEGRADED", "BROKEN", "NOT_READY"].includes(stateOf(t)));
        list.sort((a, b) => {
          const ga = GROUP_RANK[a.group] ?? 9;
          const gb = GROUP_RANK[b.group] ?? 9;
          if (ga !== gb) return ga - gb;
          return String(a.id).localeCompare(String(b.id), undefined, { numeric: true });
        });
        return list;
      });

      const summaryStats = computed(() => {
        const c = { running: 0, degraded: 0, stopped: 0, notready: 0, operating: 0 };
        for (const t of targets.value) {
          const st = stateOf(t);
          if (st === "RUNNING") c.running++;
          else if (st === "DEGRADED" || st === "BROKEN") c.degraded++;
          else if (st === "STOPPED") c.stopped++;
          else if (st === "NOT_READY") c.notready++;
          else if (["STARTING", "STOPPING", "QUEUED"].includes(st)) c.operating++;
        }
        return [
          { key: "running", label: "运行中", value: c.running, hint: "探针通过" },
          { key: "degraded", label: "异常", value: c.degraded, hint: "入口/后端/探针异常" },
          { key: "stopped", label: "已停止", value: c.stopped, hint: "人为停止或未启动" },
          { key: "notready", label: "未就绪", value: c.notready, hint: "构建产物不完整" },
          { key: "operating", label: "操作中", value: c.operating, hint: "排队/启动/停止" },
        ];
      });

      const statusAgeText = computed(() => {
        if (!statusAt.value) return "状态检测中...";
        const ts = Date.parse(statusAt.value);
        if (!ts) return "状态检测中...";
        const sec = Math.max(0, Math.floor((now.value - ts) / 1000));
        if (sec < 60) return `状态更新 ${sec}s 前`;
        return `状态更新 ${Math.floor(sec / 60)}m 前`;
      });

      const statusStale = computed(() => {
        if (!statusAt.value) return false;
        const ts = Date.parse(statusAt.value);
        return !!ts && now.value - ts > 30000;
      });

      // ── 操作坞 ──

      const activeOp = computed(() => {
        return (
          operations.value.find((o) => o.status === "running") ||
          operations.value.find((o) => o.status === "queued") ||
          null
        );
      });

      const dockOp = computed(() => activeOp.value || currentOp.value);
      const currentLogs = computed(() => {
        if (!dockOp.value) return [];
        return opLogs[dockOp.value.id] || [];
      });
      const queuedOps = computed(() =>
        operations.value.filter((o) => o.status === "queued" && o.id !== (dockOp.value && dockOp.value.id))
      );
      const dockStatus = computed(() => {
        const op = dockOp.value;
        if (!op) return "QUEUED";
        if (op.status === "queued") return "QUEUED";
        if (op.status === "running") return op.action === "start" ? "STARTING" : "STOPPING";
        if (op.status === "success") return "RUNNING";
        if (op.status === "partial") return "DEGRADED";
        if (op.status === "failed") return "BROKEN";
        return "STOPPED";
      });
      const dockStatusLabel = computed(() => {
        const op = dockOp.value;
        if (!op) return "";
        return {
          queued: "排队中",
          running: "执行中",
          success: "完成",
          partial: "部分成功",
          failed: "失败",
          cancelled: "已取消",
        }[op.status] || op.status;
      });

      function isOpActive(op) {
        return !!op && (op.status === "queued" || op.status === "running");
      }

      function historyPill(op) {
        if (op.status === "success") return "RUNNING";
        if (op.status === "partial") return "DEGRADED";
        if (op.status === "failed") return "BROKEN";
        if (op.status === "running") return op.action === "start" ? "STARTING" : "STOPPING";
        return "STOPPED";
      }

      function historyLabel(status) {
        return (
          { queued: "排队中", running: "执行中", success: "完成", partial: "部分成功", failed: "失败", cancelled: "已取消" }[
            status
          ] || status
        );
      }

      function stepIcon(status) {
        return { success: "✓", failed: "✕", running: "▶", skipped: "–", queued: "·" }[status] || "·";
      }

      // ── 网络 ──

      async function api(url, options = {}) {
        const headers = { "X-Lab-Panel": "1", ...(options.headers || {}) };
        const opts = { cache: "no-store", ...options, headers };
        if (opts.body !== undefined && typeof opts.body !== "string") {
          headers["Content-Type"] = "application/json";
          opts.body = JSON.stringify(opts.body);
        }
        const res = await fetch(url, opts);
        const text = await res.text();
        let data = null;
        if (text) {
          try {
            data = JSON.parse(text);
          } catch {
            data = text;
          }
        }
        if (!res.ok) {
          const detail = data && data.detail !== undefined ? data.detail : data;
          const message =
            typeof detail === "string" ? detail : (detail && detail.message) || res.statusText || "请求失败";
          const err = new Error(message);
          err.status = res.status;
          err.data = data;
          throw err;
        }
        return data;
      }

      function handleApiError(err) {
        const detail = err && err.data && err.data.detail;
        if (detail && typeof detail === "object" && detail.message) ElMessage.error(detail.message);
        else if (typeof detail === "string") ElMessage.error(detail);
        else ElMessage.error((err && err.message) || "请求失败");
      }

      function applyTargetsPayload(data) {
        if (!data) return;
        if (data.lab_root) labRoot.value = data.lab_root;
        if (Array.isArray(data.targets)) targets.value = data.targets;
        if (Array.isArray(data.groups)) groups.value = data.groups;
        if (Array.isArray(data.environment)) environment.value = data.environment;
        if (data.scanned_at !== undefined) scannedAt.value = data.scanned_at || "";
        if (data.status_at) statusAt.value = data.status_at;
        if (data.status_duration_ms !== undefined) statusDuration.value = data.status_duration_ms;
        if (data.active) activeMap.value = data.active;
        if (Array.isArray(data.operations)) mergeOperations(data.operations);
      }

      async function fetchTargets(silent) {
        try {
          const data = await api("/api/targets");
          applyTargetsPayload(data);
        } catch (err) {
          if (!silent) handleApiError(err);
        } finally {
          initialLoading.value = false;
        }
      }

      async function fetchStatus(silent) {
        try {
          const data = await api("/api/status");
          if (data.snapshot) {
            statusMap.value = data.snapshot.states || {};
            statusAt.value = data.snapshot.generated_at || statusAt.value;
            statusDuration.value = data.snapshot.duration_ms;
          }
          if (data.active) activeMap.value = data.active;
          if (Array.isArray(data.operations)) mergeOperations(data.operations);
        } catch (err) {
          if (!silent) handleApiError(err);
        } finally {
          initialLoading.value = false;
        }
      }

      async function refreshAll() {
        loading.value = true;
        try {
          await Promise.all([fetchTargets(false), fetchStatus(false)]);
        } finally {
          loading.value = false;
        }
      }

      async function rescan() {
        if (scanning.value) return;
        scanning.value = true;
        try {
          const data = await api("/api/scan", { method: "POST" });
          applyTargetsPayload(data);
          ElMessage.success(`已扫描 ${targets.value.length} 个管理对象`);
        } catch (err) {
          handleApiError(err);
        } finally {
          scanning.value = false;
        }
      }

      async function cleanZombies() {
        if (cleaning.value) return;
        cleaning.value = true;
        try {
          const data = await api("/api/clean", { method: "POST" });
          handleSubmitted(data.operation);
        } catch (err) {
          handleApiError(err);
        } finally {
          cleaning.value = false;
        }
      }

      // ── 操作提交 ──

      function mergeOperations(list) {
        for (const op of list) upsertOperation(op, false);
      }

      function upsertOperation(op, notify) {
        if (!op || !op.id) return;
        const idx = operations.value.findIndex((x) => x.id === op.id);
        if (idx >= 0) operations.value[idx] = op;
        else operations.value.unshift(op);
        operations.value.sort((a, b) => String(b.created_at || "").localeCompare(String(a.created_at || "")));
        if (operations.value.length > 20) operations.value = operations.value.slice(0, 20);
        if (currentOp.value && currentOp.value.id === op.id) currentOp.value = op;
        const cur = currentOp.value;
        const isActive = ["queued", "running"].includes(op.status);
        if (isActive && (!cur || FINISHED.includes(cur.status))) {
          currentOp.value = op;
        }
        if (notify && op.status === "queued") ElMessage.info(`已加入队列：${op.title}`);
      }

      function handleSubmitted(op) {
        if (!op) return;
        applyActiveOp(op);
        upsertOperation(op, false);
        currentOp.value = op;
        showLog.value = true;
        ElMessage.success(`已提交：${op.title}`);
        window.setTimeout(() => loadOperation(op.id), 700);
      }

      function applyActiveOp(op) {
        if (!op || !op.units) return;
        const map = { ...activeMap.value };
        const finished = FINISHED.includes(op.status);
        for (const unit of op.units) {
          if (!unit || !unit.target) continue;
          if (finished) {
            delete map[unit.target];
          } else {
            map[unit.target] =
              op.status === "queued" ? "QUEUED" : unit.action === "start" ? "STARTING" : "STOPPING";
          }
        }
        activeMap.value = map;
      }

      async function loadOperation(opId) {
        try {
          const op = await api(`/api/operations/${encodeURIComponent(opId)}`);
          if (op && op.id) {
            upsertOperation(op, false);
            if (Array.isArray(op.logs)) opLogs[op.id] = op.logs.slice(-2000);
            if (dockOp.value && dockOp.value.id === op.id) scrollLog();
          }
        } catch {
          /* 操作历史丢失不阻塞 UI */
        }
      }

      function appendLog(opId, line) {
        if (!opId) return;
        if (!opLogs[opId]) opLogs[opId] = [];
        opLogs[opId].push(line);
        if (opLogs[opId].length > 2000) opLogs[opId].splice(0, 500);
        if (dockOp.value && dockOp.value.id === opId && autoScroll.value) scrollLog();
      }

      function scrollLog() {
        nextTick(() => {
          if (logEl.value) logEl.value.scrollTop = logEl.value.scrollHeight;
        });
      }

      function openOperation(op) {
        if (!op) return;
        historyOpen.value = false;
        currentOp.value = op;
        showLog.value = true;
        if (op.status === "queued" || op.status === "running" || !(opLogs[op.id] || []).length) loadOperation(op.id);
      }

      async function cancelOp(op) {
        if (!op || !op.cancellable) return;
        try {
          await api(`/api/operations/${encodeURIComponent(op.id)}/cancel`, { method: "POST" });
          ElMessage.success("已取消排队");
        } catch (err) {
          handleApiError(err);
        }
      }

      function dismissDock() {
        if (dockOp.value && isOpActive(dockOp.value)) return;
        currentOp.value = null;
        showLog.value = false;
      }

      // ── 单站启停 ──

      const RUNNING_STATES = ["RUNNING"];

      function dependencyRunning(depId) {
        const dep = targets.value.find((x) => x.id === depId);
        return dep ? RUNNING_STATES.includes(stateOf(dep)) : false;
      }

      async function startTarget(t) {
        if (!canStart(t)) return;
        const deps = (t.dependencies || []).filter((d) => !dependencyRunning(d));
        if (deps.length) {
          try {
            await ElMessageBox.confirm(
              `启动 ${t.id} 会先自动启动依赖：${deps.join("、")}。继续？`,
              "启动依赖",
              { confirmButtonText: "继续启动", cancelButtonText: "取消", type: "info" }
            );
          } catch {
            return;
          }
        }
        busyTargets[t.id] = true;
        try {
          const data = await api(`/api/targets/${encodeURIComponent(t.id)}/start`, { method: "POST" });
          handleSubmitted(data.operation);
        } catch (err) {
          const detail = err && err.data && err.data.detail;
          if (detail && detail.code === "r8_conflicts") {
            try {
              await ElMessageBox.confirm(
                `R8 是独占型，需要先停止以下靶场：\n${detail.conflicts.join("、")}\n\n是否停止它们并启动 R8？`,
                "R8 独占启动",
                { confirmButtonText: "停止并启动 R8", cancelButtonText: "取消", type: "warning" }
              );
            } catch {
              return;
            }
            try {
              const data = await api(`/api/targets/R8/start?stop_conflicts=1`, { method: "POST" });
              handleSubmitted(data.operation);
            } catch (err2) {
              handleApiError(err2);
            }
            return;
          }
          if (detail && detail.code === "r8_memory") {
            try {
              await ElMessageBox.confirm(
                `当前可用物理内存约 ${detail.available_mb} MB，低于建议的 3200 MB。仍要启动 R8？`,
                "内存不足",
                { confirmButtonText: "仍要启动", cancelButtonText: "取消", type: "warning" }
              );
            } catch {
              return;
            }
            try {
              const data = await api(`/api/targets/R8/start?ignore_memory=1`, { method: "POST" });
              handleSubmitted(data.operation);
            } catch (err2) {
              handleApiError(err2);
            }
            return;
          }
          handleApiError(err);
        } finally {
          busyTargets[t.id] = false;
        }
      }

      async function stopTarget(t) {
        if (!canStop(t)) return;
        const dependents = (t.dependents || []).filter((d) => dependencyRunning(d));
        if (dependents.length) {
          try {
            await ElMessageBox.confirm(
              `停止 ${t.id} 会让以下依赖它的靶场异常：${dependents.join("、")}。仍要继续？`,
              "影响依赖方",
              { confirmButtonText: "继续停止", cancelButtonText: "取消", type: "warning" }
            );
          } catch {
            return;
          }
        }
        busyTargets[t.id] = true;
        try {
          const data = await api(`/api/targets/${encodeURIComponent(t.id)}/stop`, { method: "POST" });
          handleSubmitted(data.operation);
        } catch (err) {
          handleApiError(err);
        } finally {
          busyTargets[t.id] = false;
        }
      }

      // ── 分组 / 全部 ──

      async function startGroup(g) {
        if (!g) return;
        const ids = g.start_targets || [];
        if (!ids.length) {
          ElMessage.info("该分组没有可批量启动的目标");
          return;
        }
        const extra = g.key === "site" ? "\n\n站点组会依次启动多座靶场，内存占用会明显上升。" : "";
        try {
          await ElMessageBox.confirm(
            `将依次启动：${ids.join("、")}${extra}`,
            `启动分组：${g.label}`,
            { confirmButtonText: "开始启动", cancelButtonText: "取消", type: "warning" }
          );
        } catch {
          return;
        }
        groupBusy.value = g.key;
        try {
          const data = await api(`/api/groups/${encodeURIComponent(g.key)}/start`, { method: "POST" });
          handleSubmitted(data.operation);
        } catch (err) {
          handleApiError(err);
        } finally {
          groupBusy.value = "";
        }
      }

      async function stopGroup(g) {
        if (!g) return;
        const ids = g.stop_targets || g.targets || [];
        if (!ids.length) return;
        try {
          await ElMessageBox.confirm(
            `将依次停止：${ids.join("、")}。\n\n共享依赖（如 R2、C2-1b、C4-1）会按顺序先停下游。`,
            `停止分组：${g.label}`,
            { confirmButtonText: "开始停止", cancelButtonText: "取消", type: "warning" }
          );
        } catch {
          return;
        }
        groupBusy.value = g.key;
        try {
          const data = await api(`/api/groups/${encodeURIComponent(g.key)}/stop`, { method: "POST" });
          handleSubmitted(data.operation);
        } catch (err) {
          handleApiError(err);
        } finally {
          groupBusy.value = "";
        }
      }

      async function confirmStopAll() {
        try {
          await ElMessageBox.confirm(
            "将停止所有站点、组件、中间件和特殊形态，并关闭 Nginx。\n\nMySQL 和 Redis 会保留运行，避免影响其他本地环境。",
            "全部停止",
            { confirmButtonText: "确认全部停止", cancelButtonText: "取消", type: "warning" }
          );
        } catch {
          return;
        }
        try {
          const data = await api("/api/actions/stop-all", { method: "POST", body: { confirm: true } });
          handleSubmitted(data.operation);
        } catch (err) {
          handleApiError(err);
        }
      }

      // ── 详情 ──

      const detailTarget = computed(() => targets.value.find((t) => t.id === detailId.value) || null);
      const detailTitle = computed(() => (detailTarget.value ? `${detailTarget.value.id} · ${detailTarget.value.name}` : "靶场详情"));

      function openDetail(t) {
        detailId.value = t.id;
        detailTab.value = "overview";
        drawerOpen.value = true;
        detailLogs.files = [];
        detailLogs.note = "";
        loadDetailLogs(t.id);
      }

      function openTargetById(id) {
        const t = targets.value.find((x) => x.id === id);
        if (t) openDetail(t);
      }

      async function loadDetailLogs(tid) {
        detailLogs.files = [];
        detailLogs.note = "";
        try {
          const data = await api(`/api/targets/${encodeURIComponent(tid)}/log?lines=300`);
          detailLogs.files = data.files || [];
          detailLogs.note = data.note || "";
        } catch (err) {
          detailLogs.note = (err && err.message) || "读取日志失败";
        }
      }

      function probeText(t) {
        if (!t.probe) return "仅端口监测";
        return `${t.probe.path} → ${(t.probe.expect || []).join(" / ")}`;
      }

      function credText(c) {
        if (!c) return "";
        if (!c.username) return c.password ? `${c.label}：${c.password}` : c.label;
        return c.password ? `${c.username} / ${c.password}` : `${c.username}（空密码）`;
      }

      async function copy(text) {
        if (!text) return;
        try {
          await navigator.clipboard.writeText(String(text));
          ElMessage.success("已复制");
        } catch {
          const ta = document.createElement("textarea");
          ta.value = String(text);
          ta.style.position = "fixed";
          ta.style.opacity = "0";
          document.body.appendChild(ta);
          ta.select();
          try {
            document.execCommand("copy");
            ElMessage.success("已复制");
          } catch {
            ElMessage.error("复制失败");
          }
          ta.remove();
        }
      }

      function openUrl(t) {
        if (!t || !t.url) return;
        if (/^https?:/i.test(t.url)) window.open(t.url, "_blank", "noopener");
        else copy(t.url);
      }

      // ── 日志导出 ──

      function downloadLog() {
        const op = dockOp.value;
        if (!op) return;
        const text = (opLogs[op.id] || []).join("\n");
        const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `${op.id}.log`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
      }

      function copyLog() {
        copy((opLogs[dockOp.value ? dockOp.value.id : ""] || []).join("\n"));
      }

      // ── SSE ──

      function subscribeEvents() {
        try {
          eventSource = new EventSource("/api/events");
          eventSource.onopen = () => {
            sseConnected.value = true;
          };
          eventSource.onerror = () => {
            sseConnected.value = false;
          };
          eventSource.onmessage = (ev) => {
            let payload;
            try {
              payload = JSON.parse(ev.data);
            } catch {
              return;
            }
            handleEvent(payload);
          };
        } catch {
          sseConnected.value = false;
        }
      }

      function handleEvent(ev) {
        if (!ev || !ev.type) return;
        if (ev.type === "op") {
          upsertOperation(ev.op, false);
          if (ev.op) applyActiveOp(ev.op);
          if (ev.op && FINISHED.includes(ev.op.status)) {
            window.setTimeout(() => fetchStatus(true), 400);
          }
          return;
        }
        if (ev.type === "log") {
          appendLog(ev.op_id, ev.line);
          return;
        }
        if (ev.type === "toast") {
          const type = ev.level === "error" ? "error" : ev.level === "warning" ? "warning" : "success";
          ElMessage({ message: ev.message, type, duration: 4500 });
        }
      }

      // ── 轮询 / 主题 / 生命周期 ──

      async function statusLoop() {
        if (destroyed) return;
        if (!document.hidden) await fetchStatus(true);
        statusTimer = window.setTimeout(statusLoop, 5000);
      }

      function applyTheme() {
        document.documentElement.className =
          (theme.value === "dark" ? "dark" : "light") +
          (themeStyle.value === "steady" ? " style-steady" : "");
        localStorage.setItem("panel-theme", theme.value);
        localStorage.setItem("panel-style", themeStyle.value);
      }

      function setMode(mode) {
        theme.value = mode;
        applyTheme();
      }

      function setStyle(styleName) {
        themeStyle.value = styleName;
        applyTheme();
      }

      function onVisibility() {
        if (!document.hidden) fetchStatus(true);
      }

      watch(showLog, (v) => {
        if (v) scrollLog();
      });
      watch(
        () => (dockOp.value ? dockOp.value.id : ""),
        () => {
          if (showLog.value) scrollLog();
        }
      );

      onMounted(async () => {
        applyTheme();
        subscribeEvents();
        await refreshAll();
        statusTimer = window.setTimeout(statusLoop, 5000);
        clockTimer = window.setInterval(() => {
          now.value = Date.now();
        }, 1000);
        document.addEventListener("visibilitychange", onVisibility);
      });

      onBeforeUnmount(() => {
        destroyed = true;
        if (eventSource) eventSource.close();
        if (statusTimer) window.clearTimeout(statusTimer);
        if (clockTimer) window.clearInterval(clockTimer);
        document.removeEventListener("visibilitychange", onVisibility);
      });

      return {
        // state
        labRoot,
        targets,
        environment,
        operations,
        scannedAt,
        statusDuration,
        loading,
        initialLoading,
        scanning,
        cleaning,
        search,
        activeGroup,
        onlyRunning,
        onlyProblem,
        groupBusy,
        theme,
        themeStyle,
        sseConnected,
        drawerOpen,
        detailTab,
        detailTabs,
        detailLogs,
        historyOpen,
        currentOp,
        showLog,
        autoScroll,
        logEl,
        // computed
        groupTabs,
        currentGroup,
        filteredTargets,
        summaryStats,
        statusAgeText,
        statusStale,
        dockOp,
        dockStatus,
        dockStatusLabel,
        currentLogs,
        queuedOps,
        detailTarget,
        detailTitle,
        // methods
        statusOf,
        stateOf,
        stateLabel,
        buildLabel,
        canStart,
        canStop,
        isOperating,
        isOpActive,
        historyPill,
        historyLabel,
        stepIcon,
        refreshAll,
        rescan,
        cleanZombies,
        startTarget,
        stopTarget,
        startGroup,
        stopGroup,
        confirmStopAll,
        cancelOp,
        dismissDock,
        openOperation,
        openDetail,
        openTargetById,
        loadDetailLogs,
        probeText,
        credText,
        copy,
        openUrl,
        downloadLog,
        copyLog,
        setMode,
        setStyle,
      };
    },
  });

  app.use(ElementPlus);
  app.mount("#app");
})();
