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
      "Reset link requested. Check your email inbox and open the link.";
  } catch (e) {
    error.value =
      (e as { message?: string }).message || "Failed to request password reset.";
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <main class="auth-page">
    <h1>Reset password</h1>
    <p class="hint">Request a password reset link from Directus.</p>
    <form @submit.prevent="onSubmit">
      <label>
        Email
        <input v-model="email" type="email" required autocomplete="email" />
      </label>

      <button :disabled="loading" type="submit">
        {{ loading ? "Requesting..." : "Send reset link" }}
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
