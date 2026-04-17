<script setup lang="ts">
const config = useRuntimeConfig();
</script>

<template>
  <main class="container">
    <h1>Cardgen Auth Flows (SPA)</h1>
    <p>
      Frontend works as a single-page app and calls Directus auth endpoints
      through hidden proxy routes.
    </p>

    <section>
      <h2>Public API prefixes</h2>
      <ul>
        <li>Directus: <code>{{ config.public.directusBase }}/...</code></li>
        <li>n8n: <code>{{ config.public.n8nBase }}/...</code></li>
      </ul>
    </section>

    <section>
      <h2>Auth scenarios</h2>
      <ul>
        <li><NuxtLink to="/register">Registration</NuxtLink></li>
        <li><NuxtLink to="/login">Authorization</NuxtLink></li>
        <li><NuxtLink to="/forgot-password">Reset request</NuxtLink></li>
        <li>
          <NuxtLink to="/reset-password">Password reset by token</NuxtLink>
        </li>
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
