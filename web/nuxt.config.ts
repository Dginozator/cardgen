export default defineNuxtConfig({
  ssr: false,
  devtools: { enabled: false },
  runtimeConfig: {
    public: {
      apiBase: process.env.NUXT_PUBLIC_API_BASE || "/api",
      directusBase: process.env.NUXT_PUBLIC_DIRECTUS_BASE || "/api/d",
      n8nBase: process.env.NUXT_PUBLIC_N8N_BASE || "/api/n",
      directusResetUrl: process.env.NUXT_PUBLIC_DIRECTUS_RESET_URL || "",
      directusVerifyUrl: process.env.NUXT_PUBLIC_DIRECTUS_VERIFY_URL || "",
    },
  },
});
