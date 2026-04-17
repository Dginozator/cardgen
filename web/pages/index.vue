<script setup lang="ts">
const config = useRuntimeConfig();
</script>

<template>
  <main class="container">
    <h1>Cardgen Frontend (Nuxt)</h1>
    <p>Deployment-ready skeleton for Dokploy with hidden upstream routing.</p>

    <section>
      <h2>Public API prefixes</h2>
      <ul>
        <li>Directus: <code>{{ config.public.directusBase }}/...</code></li>
        <li>n8n: <code>{{ config.public.n8nBase }}/...</code></li>
      </ul>
    </section>

    <section>
      <h2>Аккаунт</h2>
      <p>
        <NuxtLink to="/account">Управление аккаунтом</NuxtLink>
        — вход и удаление аккаунта.
      </p>
    </section>
  </main>
</template>

<style scoped>
.container {
  max-width: 760px;
  margin: 40px auto;
  padding: 0 16px;
  font-family: Inter, Arial, sans-serif;
}

h1 {
  margin-bottom: 12px;
}

section {
  margin-top: 20px;
}
</style>
