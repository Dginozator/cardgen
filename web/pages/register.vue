<script setup lang="ts">
const { register } = useDirectusAuth();
const router = useRouter();

const email = ref("");
const password = ref("");
const loading = ref(false);
const success = ref("");
const error = ref("");

async function onSubmit() {
  success.value = "";
  error.value = "";
  loading.value = true;
  try {
    await register(email.value, password.value);
    success.value =
      "Если регистрация доступна для этого адреса, вы получите письмо с дальнейшими шагами.";
    setTimeout(() => {
      router.push("/login");
    }, 700);
  } catch {
    error.value = "Не удалось обработать запрос. Попробуйте позже.";
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <main class="auth-page">
    <h1>Регистрация</h1>
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
          minlength="8"
          autocomplete="new-password"
        />
      </label>

      <button :disabled="loading" type="submit">
        {{ loading ? "Отправка..." : "Зарегистрироваться" }}
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
