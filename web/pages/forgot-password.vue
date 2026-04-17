<script setup lang="ts">
const { requestPasswordReset } = useDirectusAuth();

const email = ref("");
const loading = ref(false);
const success = ref("");
const error = ref("");

async function onSubmit() {
  success.value = "";
  error.value = "";
  loading.value = true;
  try {
    await requestPasswordReset(email.value);
    success.value =
      "Если аккаунт с таким email существует, мы отправили письмо для сброса пароля.";
  } catch {
    error.value = "Не удалось обработать запрос. Попробуйте позже.";
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <main class="auth-page">
    <h1>Сброс пароля</h1>
    <p class="hint">Запросите ссылку для сброса пароля.</p>
    <form @submit.prevent="onSubmit">
      <label>
        Email
        <input v-model="email" type="email" required autocomplete="email" />
      </label>

      <button :disabled="loading" type="submit">
        {{ loading ? "Отправка..." : "Отправить ссылку" }}
      </button>
    </form>

    <p v-if="success" class="ok">{{ success }}</p>
    <p v-if="error" class="err">{{ error }}</p>
  </main>
</template>

<style scoped>
.auth-page {
  max-width: 420px;
  margin: 40px auto;
  padding: 0 16px;
}

.hint {
  color: #374151;
}

form {
  display: grid;
  gap: 12px;
}

label {
  display: grid;
  gap: 6px;
}

input {
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

.ok {
  color: #047857;
}

.err {
  color: #b91c1c;
}
</style>
