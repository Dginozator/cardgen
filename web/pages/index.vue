<script setup lang="ts">
const config = useRuntimeConfig();
</script>

<template>
  <main class="container">
    <h1>Сценарии авторизации Cardgen (SPA)</h1>
    <p>
      Приложение работает как SPA: переходы и отправка форм выполняются без
      перезагрузки страницы, а запросы идут через скрытые proxy-маршруты.
    </p>

    <section>
      <h2>Публичные префиксы API</h2>
      <ul>
        <li>Directus: <code>{{ config.public.directusBase }}/...</code></li>
        <li>n8n: <code>{{ config.public.n8nBase }}/...</code></li>
      </ul>
    </section>

    <section>
      <h2>Сценарии</h2>
      <ul>
        <li><NuxtLink to="/register">Регистрация</NuxtLink></li>
        <li>
          Подтверждение email — ссылка из письма ведёт на
          <code>/verify-email?token=...</code>
        </li>
        <li><NuxtLink to="/verify-success">Страница «Email подтверждён»</NuxtLink> (после успешной проверки)</li>
        <li><NuxtLink to="/login">Вход</NuxtLink></li>
        <li><NuxtLink to="/forgot-password">Запрос сброса пароля</NuxtLink></li>
        <li><NuxtLink to="/reset-password">Установка нового пароля</NuxtLink></li>
      </ul>
    </section>
  </main>
</template>

<style scoped>
.container {
  max-width: 760px;
  margin: 40px auto;
  padding: 0 16px;
}

h1 {
  margin-bottom: 12px;
}

section {
  margin-top: 20px;
}

ul {
  line-height: 1.8;
}
</style>
