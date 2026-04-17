<script setup lang="ts">
const router = useRouter();
const { user, isAuthenticated, loadToken, checkSession, clearSession } =
  useAuthSession();

onMounted(async () => {
  loadToken();
  await checkSession();
});

async function onLogout() {
  clearSession();
  await router.push("/login");
}
</script>

<template>
  <div class="app-shell">
    <header class="top-nav">
      <NuxtLink to="/">Cardgen: авторизация</NuxtLink>
      <nav>
        <NuxtLink to="/register">Регистрация</NuxtLink>
        <NuxtLink to="/login">Вход</NuxtLink>
        <NuxtLink to="/forgot-password">Сброс пароля</NuxtLink>
        <NuxtLink v-if="isAuthenticated" to="/profile">Профиль</NuxtLink>
        <button v-if="isAuthenticated" type="button" class="logout" @click="onLogout">
          Выйти
        </button>
      </nav>
    </header>
    <p v-if="isAuthenticated && user?.email" class="session-chip">
      Сессия: {{ user.email }}
    </p>
    <NuxtPage />
  </div>
</template>

<style scoped>
.app-shell {
  min-height: 100vh;
  font-family: Inter, Arial, sans-serif;
  color: #111827;
}

.top-nav {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 20px;
  border-bottom: 1px solid #e5e7eb;
}

.top-nav nav {
  display: flex;
  gap: 14px;
  align-items: center;
}

a {
  color: #111827;
  text-decoration: none;
}

a.router-link-active {
  font-weight: 700;
}

.logout {
  border: 1px solid #d1d5db;
  border-radius: 8px;
  background: #fff;
  padding: 6px 10px;
  cursor: pointer;
}

.session-chip {
  margin: 10px 20px 0;
  color: #4b5563;
  font-size: 13px;
}
</style>
