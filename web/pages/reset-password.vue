<script setup lang="ts">
const { resetPassword } = useDirectusAuth();
const route = useRoute();
const router = useRouter();

const token = ref("");
const password = ref("");
const loading = ref(false);
const error = ref("");

onMounted(() => {
  const qToken = route.query.token;
  if (typeof qToken === "string") {
    token.value = qToken;
  }
});

async function onSubmit() {
  error.value = "";
  loading.value = true;
  try {
    await resetPassword(token.value, password.value);
    router.push("/reset-success");
  } catch (e) {
    error.value = (e as { message?: string }).message || "Reset failed.";
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <main class="auth-page">
    <h1>Set new password</h1>
    <p class="hint">
      Open this page from the link in email or paste your reset token manually.
    </p>

    <form @submit.prevent="onSubmit">
      <label>
        Reset token
        <input v-model="token" type="text" required />
      </label>

      <label>
        New password
        <input v-model="password" type="password" required minlength="8" />
      </label>

      <button :disabled="loading" type="submit">
        {{ loading ? "Updating..." : "Update password" }}
      </button>
    </form>

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

.err {
  color: #b91c1c;
}
</style>
