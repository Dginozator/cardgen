<script setup lang="ts">
const { login } = useDirectusAuth();
const router = useRouter();
const { saveToken, checkSession } = useAuthSession();

const email = ref("");
const password = ref("");
const loading = ref(false);
const error = ref("");
const token = ref("");

async function onSubmit() {
  error.value = "";
  token.value = "";
  loading.value = true;
  try {
    const response = await login(email.value, password.value);
    token.value = response?.data?.access_token || "";
    if (!token.value) {
      error.value = "Не удалось выполнить вход. Попробуйте позже.";
      return;
    }
    saveToken(token.value);
    await checkSession();
    await router.push("/profile");
  } catch {
    error.value = "Неверный email или пароль.";
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <main class="auth-page">
    <h1>Вход</h1>
    <form @submit.prevent="onSubmit">
      <label>
        Email
        <input v-model="email" type="email" required autocomplete="email" />
      </label>

      <label>
        Пароль
        <input
          v-model="password"
          type="password"
          required
          autocomplete="current-password"
        />
      </label>

      <button :disabled="loading" type="submit">
        {{ loading ? "Выполняем вход..." : "Войти" }}
      </button>
    </form>

    <p v-if="error" class="err">{{ error }}</p>
    <p v-if="token" class="ok">Вход выполнен, токен сохранен.</p>
    <textarea
      v-if="token"
      class="token-box"
      readonly
      :value="token"
      aria-label="Токен доступа"
    />
  </main>
</template>

<style scoped>
.auth-page {
  max-width: 420px;
  margin: 40px auto;
  padding: 0 16px;
}

form {
  display: grid;
  gap: 12px;
}

label {
  display: grid;
  gap: 6px;
}

input,
textarea {
  border: 1px solid #d1d5db;
  border-radius: 8px;
  padding: 10px 12px;
}

button {
  border: none;
  border-radius: 8px;
  padding: 10px 12px;
  background: #111827;
  color: #fff;
  cursor: pointer;
}

button:disabled {
  opacity: 0.65;
  cursor: wait;
}

.token-box {
  width: 100%;
  min-height: 80px;
  margin-top: 8px;
  font-size: 12px;
}

.ok {
  color: #047857;
}

.err {
  color: #b91c1c;
}
</style>
