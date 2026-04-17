<script setup lang="ts">
import type { DirectusUser } from "~/composables/useDirectus";

const directus = useDirectus();

type Status = "loading" | "login" | "ready" | "deleted";

const status = ref<Status>("loading");
const user = ref<DirectusUser | null>(null);
const error = ref<string | null>(null);
const info = ref<string | null>(null);

const email = ref("");
const password = ref("");
const loginBusy = ref(false);

const confirmOpen = ref(false);
const confirmText = ref("");
const deleteBusy = ref(false);

const canDelete = computed(() => confirmText.value.trim().toLowerCase() === "удалить");

async function loadMe(): Promise<void> {
  error.value = null;
  try {
    user.value = await directus.getMe();
    status.value = "ready";
  } catch (err) {
    user.value = null;
    if (directus.isAuthenticated()) {
      error.value = err instanceof Error ? err.message : "Не удалось получить профиль.";
    }
    status.value = "login";
  }
}

async function submitLogin(): Promise<void> {
  if (loginBusy.value) return;
  error.value = null;
  if (!email.value.trim() || !password.value) {
    error.value = "Введите email и пароль.";
    return;
  }
  loginBusy.value = true;
  try {
    await directus.login(email.value.trim(), password.value);
    password.value = "";
    await loadMe();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Не удалось войти.";
  } finally {
    loginBusy.value = false;
  }
}

async function logout(): Promise<void> {
  await directus.logout();
  user.value = null;
  status.value = "login";
  info.value = "Вы вышли из аккаунта.";
}

function openConfirm(): void {
  error.value = null;
  info.value = null;
  confirmText.value = "";
  confirmOpen.value = true;
}

function cancelConfirm(): void {
  if (deleteBusy.value) return;
  confirmOpen.value = false;
  confirmText.value = "";
}

async function confirmDelete(): Promise<void> {
  if (!canDelete.value || deleteBusy.value) return;
  error.value = null;
  deleteBusy.value = true;
  try {
    await directus.deleteAccount();
    confirmOpen.value = false;
    user.value = null;
    status.value = "deleted";
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Не удалось удалить аккаунт.";
  } finally {
    deleteBusy.value = false;
  }
}

onMounted(() => {
  if (directus.isAuthenticated()) {
    loadMe();
  } else {
    status.value = "login";
  }
});
</script>

<template>
  <main class="container">
    <nav class="crumbs">
      <NuxtLink to="/">← На главную</NuxtLink>
    </nav>

    <h1>Аккаунт</h1>

    <p v-if="info" class="info">{{ info }}</p>
    <p v-if="error" class="error">{{ error }}</p>

    <section v-if="status === 'loading'" class="card">
      <p>Загрузка…</p>
    </section>

    <section v-else-if="status === 'login'" class="card">
      <h2>Вход</h2>
      <p class="hint">
        Удаление аккаунта доступно только после входа. Используются учётные данные Directus.
      </p>
      <form @submit.prevent="submitLogin">
        <label>
          Email
          <input
            v-model="email"
            type="email"
            autocomplete="email"
            required
            :disabled="loginBusy"
          />
        </label>
        <label>
          Пароль
          <input
            v-model="password"
            type="password"
            autocomplete="current-password"
            required
            :disabled="loginBusy"
          />
        </label>
        <button type="submit" :disabled="loginBusy">
          {{ loginBusy ? "Входим…" : "Войти" }}
        </button>
      </form>
    </section>

    <section v-else-if="status === 'ready' && user" class="card">
      <h2>Профиль</h2>
      <dl class="profile">
        <dt>Email</dt>
        <dd>{{ user.email || "—" }}</dd>
        <dt>Имя</dt>
        <dd>{{ [user.first_name, user.last_name].filter(Boolean).join(" ") || "—" }}</dd>
        <dt>ID</dt>
        <dd><code>{{ user.id }}</code></dd>
      </dl>

      <div class="actions">
        <button type="button" class="secondary" @click="logout">Выйти</button>
        <button type="button" class="danger" @click="openConfirm">
          Удалить аккаунт
        </button>
      </div>

      <p class="hint">
        Удаление аккаунта — необратимая операция. Связанные данные, принадлежащие пользователю,
        могут быть удалены безвозвратно.
      </p>
    </section>

    <section v-else-if="status === 'deleted'" class="card">
      <h2>Аккаунт удалён</h2>
      <p>Ваш аккаунт был удалён. Вы вышли из системы.</p>
      <NuxtLink to="/" class="link-btn">Вернуться на главную</NuxtLink>
    </section>

    <div v-if="confirmOpen" class="modal-backdrop" role="dialog" aria-modal="true">
      <div class="modal">
        <h3>Подтвердите удаление</h3>
        <p>
          Это действие <strong>нельзя отменить</strong>. Для подтверждения введите слово
          <code>удалить</code> в поле ниже.
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
          <button type="button" class="secondary" :disabled="deleteBusy" @click="cancelConfirm">
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
.container {
  max-width: 640px;
  margin: 40px auto;
  padding: 0 16px;
  font-family: Inter, Arial, sans-serif;
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

label {
  display: block;
  margin-top: 12px;
  font-size: 14px;
  color: #374151;
}

input[type="email"],
input[type="password"],
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

button {
  margin-top: 16px;
  padding: 8px 14px;
  border-radius: 6px;
  border: 1px solid transparent;
  font-size: 14px;
  cursor: pointer;
}

button[type="submit"] {
  background: #2563eb;
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

.actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
}

.profile {
  display: grid;
  grid-template-columns: 120px 1fr;
  gap: 6px 12px;
  margin: 0 0 16px;
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

.info {
  color: #065f46;
  background: #ecfdf5;
  border: 1px solid #a7f3d0;
  padding: 8px 12px;
  border-radius: 6px;
  font-size: 14px;
}

.link-btn {
  display: inline-block;
  margin-top: 12px;
  color: #2563eb;
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
