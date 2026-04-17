<script setup lang="ts">
const router = useRouter();
const { token, user, loadToken, checkSession, checking, clearSession } =
  useAuthSession();
const { deleteAccount } = useDirectus();

type View = "checking" | "needs-login" | "ready" | "deleted";

const view = ref<View>("checking");
const error = ref<string | null>(null);

const confirmOpen = ref(false);
const confirmText = ref("");
const deleteBusy = ref(false);

const canDelete = computed(
  () => confirmText.value.trim().toLowerCase() === "удалить",
);

onMounted(async () => {
  loadToken();
  if (!token.value) {
    view.value = "needs-login";
    return;
  }
  const ok = await checkSession();
  view.value = ok ? "ready" : "needs-login";
});

async function goLogin() {
  await router.push("/login");
}

async function onLogout() {
  clearSession();
  view.value = "needs-login";
}

function openConfirm() {
  error.value = null;
  confirmText.value = "";
  confirmOpen.value = true;
}

function cancelConfirm() {
  if (deleteBusy.value) return;
  confirmOpen.value = false;
  confirmText.value = "";
}

async function confirmDelete() {
  if (!canDelete.value || deleteBusy.value) return;
  error.value = null;
  deleteBusy.value = true;
  try {
    await deleteAccount();
    confirmOpen.value = false;
    view.value = "deleted";
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Не удалось удалить аккаунт.";
  } finally {
    deleteBusy.value = false;
  }
}
</script>

<template>
  <main class="account-page">
    <nav class="crumbs">
      <NuxtLink to="/">← На главную</NuxtLink>
    </nav>

    <h1>Аккаунт</h1>

    <p v-if="checking && view === 'checking'">Проверяем сессию…</p>

    <section v-else-if="view === 'needs-login'" class="card">
      <p>Чтобы удалить аккаунт, нужно сначала войти.</p>
      <button type="button" @click="goLogin">Перейти ко входу</button>
    </section>

    <section v-else-if="view === 'ready'" class="card">
      <h2>Профиль</h2>
      <dl class="profile">
        <dt>Email</dt>
        <dd>{{ user?.email || "—" }}</dd>
        <dt>Имя</dt>
        <dd>
          {{
            [user?.first_name, user?.last_name].filter(Boolean).join(" ") || "—"
          }}
        </dd>
      </dl>

      <div class="actions">
        <button type="button" class="secondary" @click="onLogout">Выйти</button>
        <button type="button" class="danger" @click="openConfirm">
          Удалить аккаунт
        </button>
      </div>

      <p class="hint">
        Удаление аккаунта — необратимая операция. Связанные данные, принадлежащие
        пользователю, могут быть удалены безвозвратно.
      </p>
    </section>

    <section v-else-if="view === 'deleted'" class="card">
      <h2>Аккаунт удалён</h2>
      <p>Ваш аккаунт был удалён. Сессия завершена.</p>
      <NuxtLink to="/">Вернуться на главную</NuxtLink>
    </section>

    <div
      v-if="confirmOpen"
      class="modal-backdrop"
      role="dialog"
      aria-modal="true"
    >
      <div class="modal">
        <h3>Подтвердите удаление</h3>
        <p>
          Это действие <strong>нельзя отменить</strong>. Для подтверждения введите
          слово <code>удалить</code> в поле ниже.
        </p>
        <input
          v-model="confirmText"
          type="text"
          autocomplete="off"
          :disabled="deleteBusy"
          placeholder="удалить"
        />
        <p v-if="error" class="error">{{ error }}</p>
        <div class="actions">
          <button
            type="button"
            class="secondary"
            :disabled="deleteBusy"
            @click="cancelConfirm"
          >
            Отмена
          </button>
          <button
            type="button"
            class="danger"
            :disabled="!canDelete || deleteBusy"
            @click="confirmDelete"
          >
            {{ deleteBusy ? "Удаляем…" : "Удалить окончательно" }}
          </button>
        </div>
      </div>
    </div>
  </main>
</template>

<style scoped>
.account-page {
  max-width: 640px;
  margin: 40px auto;
  padding: 0 16px;
  color: #1f2937;
}

.crumbs {
  margin-bottom: 16px;
  font-size: 14px;
}

.crumbs a {
  color: #2563eb;
  text-decoration: none;
}

h1 {
  margin: 0 0 16px;
}

.card {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 20px;
  margin-top: 16px;
}

h2 {
  margin: 0 0 12px;
  font-size: 18px;
}

.hint {
  color: #6b7280;
  font-size: 14px;
  margin: 12px 0 0;
}

button {
  margin-top: 8px;
  padding: 8px 14px;
  border-radius: 8px;
  border: 1px solid transparent;
  font-size: 14px;
  cursor: pointer;
  background: #111827;
  color: #fff;
}

button.secondary {
  background: #fff;
  border-color: #d1d5db;
  color: #111827;
}

button.danger {
  background: #dc2626;
  color: #fff;
}

button[disabled] {
  opacity: 0.6;
  cursor: not-allowed;
}

input[type="text"] {
  display: block;
  width: 100%;
  box-sizing: border-box;
  margin-top: 4px;
  padding: 8px 10px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-size: 14px;
}

.actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
  margin-top: 12px;
}

.profile {
  display: grid;
  grid-template-columns: 120px 1fr;
  gap: 6px 12px;
  margin: 0 0 8px;
}

.profile dt {
  color: #6b7280;
  font-size: 13px;
}

.profile dd {
  margin: 0;
  font-size: 14px;
}

.error {
  color: #b91c1c;
  background: #fef2f2;
  border: 1px solid #fecaca;
  padding: 8px 12px;
  border-radius: 6px;
  font-size: 14px;
}

.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(17, 24, 39, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
  z-index: 50;
}

.modal {
  background: #fff;
  border-radius: 10px;
  padding: 20px;
  max-width: 440px;
  width: 100%;
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.2);
}

.modal h3 {
  margin: 0 0 12px;
}

.modal code {
  background: #f3f4f6;
  padding: 1px 4px;
  border-radius: 3px;
}
</style>
