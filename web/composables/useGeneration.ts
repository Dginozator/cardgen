/**
 * Composable for template-based infographic generation.
 *
 * Flow: client → Directus (create task + upload file) → worker (process) → Directus (poll status).
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
  const { ensureFreshToken } = session;
  const directus = useDirectus();
  const workerBase = (config.public.workerBase as string) || "/api/w";
  const directusBase = (config.public.directusBase as string) || "/api/d";

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
      await ensureFreshToken();
      const data = await $fetch<Template[]>(`${workerBase}/templates`, {
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
      await ensureFreshToken();

      // 1. Upload product image to Directus
      const fileRecord = await directus.uploadFile(opts.productImage);
      const fileId = fileRecord.id;
      if (!fileId) throw new Error("Не удалось загрузить изображение.");

      // 2. Create generation_task directly in Directus
      const task = await directus.createTask({
        template: selectedTemplate.value!.id,
        input_data: {
          product_image_file_id: fileId,
          title: opts.title,
          bullets: opts.bullets,
        },
      });
      const taskId = task.id as string;
      if (!taskId) throw new Error("Сервер не вернул task_id");

      // 3. Trigger worker to process the task
      await $fetch<{ ok: boolean }>(`${workerBase}/process/${taskId}`, {
        method: "POST",
      });

      // 4. Start polling Directus for status
      await _pollTask(taskId);
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
        const raw = await directus.getTask(taskId);
        const task: Task = {
          ok: true,
          id: (raw.id as string) || taskId,
          status: (raw.status as TaskStatus) || "pending",
          result_image: (raw.result_image as string) || null,
          enhanced_prompt: (raw.enhanced_prompt as string) || null,
          error_message: (raw.error_message as string) || null,
        };
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
    try {
      await ensureFreshToken();
      const resp = await fetch(`${directusBase}/assets/${task.result_image}`, {
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
