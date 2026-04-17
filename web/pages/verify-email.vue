<script setup lang="ts">
const route = useRoute();
const router = useRouter();
const { verifyRegistrationEmail } = useDirectusAuth();

const status = ref<"loading" | "invalid" | "error">("loading");

function tokenFromRoute(): string {
  const raw = route.query.token;
  if (Array.isArray(raw)) {
    return typeof raw[0] === "string" ? raw[0] : "";
  }
  return typeof raw === "string" ? raw : "";
}

onMounted(async () => {
  const token = tokenFromRoute();
  if (!token) {
    status.value = "invalid";
    return;
  }
  const result = await verifyRegistrationEmail(token);
  if (result === "success") {
    await router.replace("/verify-success");
    return;
  }
  status.value = result === "invalid" ? "invalid" : "error";
});
</script>

<template>
  <main class="auth-page">
    <template v-if="status === 'loading'">
      <h1>Подтверждение email</h1>
      <p>Подождите, проверяем ссылку...</p>
    </template>

    <template v-else-if="status === 'invalid'">
      <h1>Ссылка недействительна</h1>
      <p>Ссылка устарела или уже была использована.</p>
      <NuxtLink class="link" to="/register">К регистрации</NuxtLink>
    </template>

    <template v-else>
      <h1>Не удалось подтвердить</h1>
      <p>Попробуйте позже или запросите письмо повторно.</p>
      <NuxtLink class="link" to="/register">К регистрации</NuxtLink>
    </template>
  </main>
</template>

<style scoped>
.auth-page {
  max-width: 420px;
  margin: 40px auto;
  padding: 0 16px;
}

.link {
  display: inline-block;
  margin-top: 12px;
  color: #111827;
}
</style>
