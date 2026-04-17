<script setup lang="ts">
const router = useRouter();
const { token, user, loadToken, checkSession, checking, clearSession } =
  useAuthSession();

const accessDenied = ref(false);

onMounted(async () => {
  loadToken();
  if (!token.value) {
    accessDenied.value = true;
    return;
  }
  const ok = await checkSession();
  if (!ok) {
    accessDenied.value = true;
  }
});

async function goLogin() {
  await router.push("/login");
}

async function onLogout() {
  clearSession();
  await router.push("/login");
}
</script>

<template>
  <main class="profile-page">
    <h1>Личный кабинет</h1>

    <p v-if="checking">Проверяем сессию...</p>

    <section v-else-if="!accessDenied" class="card">
      <p><strong>Email:</strong> {{ user?.email || "—" }}</p>
      <p><strong>ID:</strong> {{ user?.id || "—" }}</p>
      <p>
        <strong>Имя:</strong>
        {{ [user?.first_name, user?.last_name].filter(Boolean).join(" ") || "—" }}
      </p>
      <button type="button" @click="onLogout">Выйти</button>
    </section>

    <section v-else class="card">
      <p>Сессия не найдена или истекла. Войдите снова.</p>
      <button type="button" @click="goLogin">Перейти ко входу</button>
    </section>
  </main>
</template>

<style scoped>
.profile-page {
  max-width: 560px;
  margin: 40px auto;
  padding: 0 16px;
}

.card {
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 16px;
}

button {
  border: none;
  border-radius: 8px;
  padding: 10px 12px;
  background: #111827;
  color: #fff;
  cursor: pointer;
}
</style>
