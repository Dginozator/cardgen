/**
 * Composable for template-based infographic generation.
 * Talks to the worker API (/api/w/).
 */

export type Template = {
  id: string;
  name: string;
  slug: string;
  category?: string;
  width: number;
  height: number;
  layout: Record<string, unknown>;
  preview?: string;
  is_active: boolean;
  output_format?: string;
  style_hints?: string;
};

export type TaskStatus =
  | "pending"
  | "processing"
  | "completed"
  | "failed";

export type Task = {
  ok: boolean;
  id: string;
  status: TaskStatus;
  result_image?: string | null;
  enhanced_prompt?: string | null;
  error_message?: string | null;
};

const POLL_INTERVAL = 2000;
const POLL_MAX_ATTEMPTS = 150; // 5 min

export function useGeneration() {
  const config = useRuntimeConfig();
  const session = useAuthSession();
  const base = (config.public.workerBase as string) || "/api/w";

  const templates = ref<Template[]>([]);
  const selectedTemplate = ref<Template | null>(null);
  const loading = ref(false);
  const error = ref("");
  const currentTask = ref<Task | null>(null);
  const resultBlobUrl = ref("");

  // ── Templates ──────────────────────────────────────────

  async function fetchTemplates() {
    error.value = "";
    try {
      const data = await $fetch<Template[]>(`${base}/templates`, {
        headers: { Authorization: `Bearer ${session.token.value}` },
      });
      templates.value = Array.isArray(data) ? data : [];
    } catch (e: unknown) {
      error.value = _extractError(e, "Не удалось загрузить шаблоны.");
    }
  }

  function selectTemplate(t: Template) {
    selectedTemplate.value = t;
  }

  // ── Generate ───────────────────────────────────────────

  async function startGeneration(opts: {
    title: string;
    bullets: string[];
    productImage: File;
  }) {
    error.value = "";
    currentTask.value = null;
    resultBlobUrl.value = "";
    loading.value = true;

    try {
      const formData = new FormData();
      formData.append("template_id", selectedTemplate.value!.id);
      formData.append("title", opts.title);
      formData.append("bullets_json", JSON.stringify(opts.bullets));
      formData.append("product_image", opts.productImage);

      const task = await $fetch<{ ok: boolean; task_id: string }>(
        `${base}/generate`,
        {
          method: "POST",
          body: formData,
          headers: { Authorization: `Bearer ${session.token.value}` },
        },
      );

      if (!task.ok || !task.task_id) {
        throw new Error("Сервер не вернул task_id");
      }

      // Start polling
      await _pollTask(task.task_id);
    } catch (e: unknown) {
      error.value = _extractError(e, "Ошибка генерации.");
    } finally {
      loading.value = false;
    }
  }

  // ── Polling ────────────────────────────────────────────

  async function _pollTask(taskId: string) {
    for (let i = 0; i < POLL_MAX_ATTEMPTS; i++) {
      await _sleep(POLL_INTERVAL);

      try {
        const task = await $fetch<Task>(`${base}/task/${taskId}`, {
          headers: { Authorization: `Bearer ${session.token.value}` },
        });
        currentTask.value = task;

        if (task.status === "completed") {
          await _loadResultImage(task);
          return;
        }
        if (task.status === "failed") {
          error.value = task.error_message || "Генерация завершилась ошибкой.";
          return;
        }
      } catch (e: unknown) {
        // Transient error — keep polling
        console.warn("poll error", e);
      }
    }
    error.value = "Таймаут ожидания результата.";
  }

  async function _loadResultImage(task: Task) {
    if (!task.result_image) return;
    const dBase = (config.public.directusBase as string) || "/api/d";
    try {
      const resp = await fetch(`${dBase}/assets/${task.result_image}`, {
        headers: { Authorization: `Bearer ${session.token.value}` },
      });
      if (!resp.ok) return;
      const blob = await resp.blob();
      if (resultBlobUrl.value) {
        URL.revokeObjectURL(resultBlobUrl.value);
      }
      resultBlobUrl.value = URL.createObjectURL(blob);
    } catch {
      // Ignore — user can download later
    }
  }

  // ── Helpers ────────────────────────────────────────────

  function reset() {
    currentTask.value = null;
    error.value = "";
    loading.value = false;
    if (resultBlobUrl.value) {
      URL.revokeObjectURL(resultBlobUrl.value);
    }
    resultBlobUrl.value = "";
  }

  return {
    templates,
    selectedTemplate,
    loading,
    error,
    currentTask,
    resultBlobUrl,
    fetchTemplates,
    selectTemplate,
    startGeneration,
    reset,
  };
}

// ── Util ─────────────────────────────────────────────────

function _sleep(ms: number) {
  return new Promise((r) => setTimeout(r, ms));
}

function _extractError(e: unknown, fallback: string): string {
  if (e && typeof e === "object" && "data" in e) {
    const d = (e as { data?: { detail?: string } }).data;
    if (d?.detail) return d.detail;
  }
  if (e instanceof Error) return e.message;
  return fallback;
}