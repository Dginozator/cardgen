<script setup lang="ts">
const { isAuthenticated } = useAuthSession();
const {
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
} = useGeneration();

// Form fields
const title = ref("");
const bullets = ref(["", "", ""]);
const productFile = ref<File | null>(null);
const fileInput = ref<HTMLInputElement | null>(null);
const dragOver = ref(false);

// Computed
const canGenerate = computed(
  () => selectedTemplate.value && productFile.value && !loading.value,
);

const aspectLabel = computed(() => {
  if (!selectedTemplate.value) return "";
  const { width, height } = selectedTemplate.value;
  if (width === height) return "1:1";
  if (width * 4 === height * 3) return "3:4";
  return `${width}:${height}`;
});

// Lifecycle
watch(isAuthenticated, (v) => { if (v) fetchTemplates(); }, { immediate: true });

// Handlers
function onFileChange(e: Event) {
  const input = e.target as HTMLInputElement;
  if (input.files?.[0]) productFile.value = input.files[0];
}

function onDrop(e: DragEvent) {
  dragOver.value = false;
  if (e.dataTransfer?.files?.[0]) {
    productFile.value = e.dataTransfer.files[0];
  }
}

function updateBullet(index: number, value: string) {
  bullets.value[index] = value;
}

function addBullet() {
  if (bullets.value.length < 6) bullets.value.push("");
}

function removeBullet(index: number) {
  bullets.value.splice(index, 1);
}

async function onGenerate() {
  if (!canGenerate.value) return;
  await startGeneration({
    title: title.value,
    bullets: bullets.value.filter((b) => b.trim()),
    productImage: productFile.value!,
  });
}

function startOver() {
  reset();
  title.value = "";
  bullets.value = ["", "", ""];
  productFile.value = null;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} Б`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} КБ`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} МБ`;
}
</script>

<template>
  <main class="gen-page">
    <!-- Auth guard -->
    <p v-if="!isAuthenticated" class="auth-msg">
      <NuxtLink to="/login">Войдите</NuxtLink>, чтобы генерировать инфографику.
    </p>

    <template v-else>

      <!-- ── Step 1: Template selection ── -->
      <section v-if="!selectedTemplate && !loading && !resultBlobUrl" class="step">
        <h2>Выберите шаблон</h2>
        <div v-if="templates.length === 0" class="empty">
          Шаблоны не найдены. Убедитесь, что Directus запущен и коллекция templates заполнена.
        </div>
        <div class="template-grid">
          <div
            v-for="t in templates"
            :key="t.id"
            class="template-card"
            @click="selectTemplate(t)"
          >
            <div class="thumb">
              <span class="dims">{{ t.width }}×{{ t.height }}</span>
              <span class="ratio">{{ t.width === t.height ? '1:1' : '3:4' }}</span>
            </div>
            <div class="info">
              <strong>{{ t.name }}</strong>
              <span v-if="t.category" class="cat">{{ t.category }}</span>
            </div>
          </div>
        </div>
      </section>

      <!-- ── Step 2: Fill form ── -->
      <section v-if="selectedTemplate && !loading && !resultBlobUrl && !error" class="step">
        <div class="step-header">
          <button class="back" @click="selectedTemplate = null">← Шаблоны</button>
          <h2>{{ selectedTemplate.name }} <span class="dims-badge">{{ aspectLabel }}</span></h2>
        </div>

        <form class="gen-form" @submit.prevent="onGenerate">
          <!-- Product image upload -->
          <div
            class="upload-zone"
            :class="{ dragover: dragOver, hasfile: productFile }"
            @dragover.prevent="dragOver = true"
            @dragleave="dragOver = false"
            @drop.prevent="onDrop"
            @click="fileInput?.click()"
          >
            <input
              ref="fileInput"
              type="file"
              accept="image/jpeg,image/png,image/webp"
              hidden
              @change="onFileChange"
            />
            <template v-if="!productFile">
              <span class="upload-icon">📷</span>
              <p>Перетащите фото товара или нажмите для выбора</p>
              <p class="hint">JPEG, PNG, WEBP — до 10 МБ</p>
            </template>
            <template v-else>
              <span class="upload-icon">✅</span>
              <p>{{ productFile.name }} ({{ formatBytes(productFile.size) }})</p>
              <button type="button" class="remove-file" @click.stop="productFile = null">Удалить</button>
            </template>
          </div>

          <!-- Title -->
          <div class="field">
            <label>Название товара</label>
            <input v-model="title" type="text" placeholder="Например: Беспроводные наушники Sony WH-1000XM5" />
          </div>

          <!-- Bullets -->
          <div class="field">
            <label>Характеристики (буллеты)</label>
            <div v-for="(b, i) in bullets" :key="i" class="bullet-row">
              <span class="bullet-num">✓</span>
              <input
                :value="b"
                type="text"
                :placeholder="`Характеристика ${i + 1}`"
                @input="updateBullet(i, ($event.target as HTMLInputElement).value)"
              />
              <button v-if="bullets.length > 1" type="button" class="remove-bullet" @click="removeBullet(i)">×</button>
            </div>
            <button v-if="bullets.length < 6" type="button" class="add-bullet" @click="addBullet">+ Добавить</button>
          </div>

          <button type="submit" class="btn-generate" :disabled="!canGenerate">
            Сгенерировать
          </button>
        </form>
      </section>

      <!-- ── Loading state ── -->
      <section v-if="loading" class="step loading">
        <div class="spinner" />
        <h2>Генерация инфографики…</h2>
        <p v-if="currentTask" class="status-text">
          Статус: {{ currentTask.status === 'processing' ? 'обработка' : 'ожидание' }}
        </p>
        <p class="hint">Это может занять 30–60 секунд</p>
      </section>

      <!-- ── Error ── -->
      <section v-if="error && !loading" class="step error-section">
        <h2>Ошибка</h2>
        <p class="error-text">{{ error }}</p>
        <button class="btn-generate" @click="startOver">Попробовать снова</button>
      </section>

      <!-- ── Result ── -->
      <section v-if="resultBlobUrl && !loading" class="step result">
        <h2>Готово!</h2>
        <div class="result-image">
          <img :src="resultBlobUrl" alt="Сгенерированная инфографика" />
        </div>
        <div class="result-actions">
          <a :href="resultBlobUrl" download="infographic.png" class="btn-generate">Скачать PNG</a>
          <button class="btn-secondary" @click="startOver">Сгенерировать ещё</button>
        </div>
      </section>

    </template>
  </main>
</template>

<style scoped>
.gen-page {
  max-width: 900px;
  margin: 20px auto;
  padding: 0 16px 60px;
}

.auth-msg {
  margin-top: 30px;
  font-size: 16px;
}

/* ── Step common ── */
.step {
  margin-top: 24px;
}
.step-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}
.step-header h2 {
  margin: 0;
}
.back {
  border: 1px solid #d1d5db;
  border-radius: 6px;
  background: #fff;
  padding: 4px 10px;
  cursor: pointer;
  font-size: 14px;
}
.dims-badge {
  font-size: 13px;
  font-weight: 400;
  color: #6b7280;
  margin-left: 6px;
}

/* ── Template grid ── */
.template-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 16px;
  margin-top: 16px;
}
.template-card {
  border: 2px solid #e5e7eb;
  border-radius: 12px;
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s;
  overflow: hidden;
}
.template-card:hover {
  border-color: #3b82f6;
  box-shadow: 0 2px 8px rgba(59, 130, 246, 0.15);
}
.thumb {
  aspect-ratio: 3/4;
  background: linear-gradient(135deg, #1a1a2e, #0f3460);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  color: #fff;
  font-size: 14px;
}
.ratio {
  background: rgba(255,255,255,0.15);
  border-radius: 4px;
  padding: 2px 8px;
  font-size: 12px;
}
.info {
  padding: 10px 12px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.cat {
  font-size: 12px;
  color: #6b7280;
}
.empty {
  color: #6b7280;
  margin-top: 12px;
}

/* ── Form ── */
.gen-form {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

/* Upload zone */
.upload-zone {
  border: 2px dashed #d1d5db;
  border-radius: 12px;
  padding: 32px 20px;
  text-align: center;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
}
.upload-zone:hover,
.upload-zone.dragover {
  border-color: #3b82f6;
  background: #eff6ff;
}
.upload-zone.hasfile {
  border-color: #10b981;
  background: #ecfdf5;
}
.upload-icon {
  font-size: 32px;
}
.hint {
  font-size: 13px;
  color: #9ca3af;
  margin-top: 6px;
}
.remove-file {
  margin-top: 8px;
  font-size: 13px;
  color: #ef4444;
  background: none;
  border: none;
  cursor: pointer;
  text-decoration: underline;
}

/* Fields */
.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.field label {
  font-weight: 600;
  font-size: 14px;
}
.field input[type="text"] {
  border: 1px solid #d1d5db;
  border-radius: 8px;
  padding: 10px 12px;
  font-size: 15px;
}
.bullet-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.bullet-num {
  color: #4fc3f7;
  font-weight: 700;
}
.bullet-row input {
  flex: 1;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  padding: 8px 10px;
  font-size: 14px;
}
.remove-bullet {
  border: none;
  background: none;
  color: #9ca3af;
  font-size: 18px;
  cursor: pointer;
}
.add-bullet {
  align-self: flex-start;
  font-size: 13px;
  color: #3b82f6;
  background: none;
  border: none;
  cursor: pointer;
  margin-top: 4px;
}

/* Generate button */
.btn-generate {
  display: inline-block;
  background: #3b82f6;
  color: #fff;
  border: none;
  border-radius: 8px;
  padding: 12px 24px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  text-align: center;
  text-decoration: none;
  transition: background 0.15s;
}
.btn-generate:hover:not(:disabled) {
  background: #2563eb;
}
.btn-generate:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.btn-secondary {
  background: #fff;
  color: #3b82f6;
  border: 1px solid #3b82f6;
  border-radius: 8px;
  padding: 12px 24px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
}

/* ── Loading ── */
.loading {
  text-align: center;
  padding: 60px 0;
}
.spinner {
  width: 48px;
  height: 48px;
  border: 4px solid #e5e7eb;
  border-top-color: #3b82f6;
  border-radius: 50%;
  margin: 0 auto 20px;
  animation: spin 0.8s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}
.status-text {
  font-size: 14px;
  color: #6b7280;
}

/* ── Error ── */
.error-section {
  text-align: center;
  padding: 40px 0;
}
.error-text {
  color: #ef4444;
  background: #fef2f2;
  border-radius: 8px;
  padding: 12px;
  margin: 12px 0 20px;
}

/* ── Result ── */
.result {
  text-align: center;
}
.result-image {
  max-width: 450px;
  margin: 20px auto;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 4px 20px rgba(0,0,0,0.1);
}
.result-image img {
  display: block;
  width: 100%;
  height: auto;
}
.result-actions {
  display: flex;
  gap: 12px;
  justify-content: center;
  margin-top: 20px;
}
</style>
</task_progress>
- [x] Worker: compositor.py (Pillow layout renderer)
- [x] Worker: pipeline, directus_client, routerai_client, main.py (FastAPI)
- [x] Worker: Dockerfile, requirements.txt
- [x] Docker Compose: worker service + nginx route
- [ ] Directus schema via MCP (templates, generation_tasks collections + seed templates)
- [x] Nuxt page /generate + composable useGeneration.ts
- [ ] Integration testing
</task_progress>
</write_to_file>