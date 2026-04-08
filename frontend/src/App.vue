<template>
  <main class="page">
    <div class="layout">
      <aside class="sidebar">
        <section class="card settings">
          <h3>Settings</h3>
          <div class="grid">
            <div class="field">
              <label for="sentryUrl">Sentry URL</label>
              <input id="sentryUrl" v-model.trim="form.sentry_url" placeholder="https://sentry.example.com" />
            </div>
            <div class="field">
              <label for="sentryOrg">Sentry org slug</label>
              <input id="sentryOrg" v-model.trim="form.sentry_org" placeholder="my-org" />
            </div>
            <div class="field">
              <label for="sentryProject">Sentry project slug</label>
              <input id="sentryProject" v-model.trim="form.sentry_project" placeholder="my-project" />
            </div>
            <div class="field">
              <label for="sentryToken">Sentry token</label>
              <input id="sentryToken" v-model.trim="form.sentry_token" type="password" placeholder="sntryu_..." />
            </div>
            <div class="field">
              <label for="openaiKey">OpenAI key</label>
              <input id="openaiKey" v-model.trim="form.openai_api_key" type="password" placeholder="sk-..." />
            </div>
            <div class="field">
              <label for="model">OpenAI model</label>
              <select id="model" v-model="form.model">
                <option>gpt-5-mini</option>
                <option>gpt-5.4-mini</option>
                <option>gpt-5.4</option>
                <option>gpt-5-nano</option>
              </select>
            </div>
            <div class="field">
              <label for="temperature">Temperature</label>
              <input id="temperature" v-model.number="form.temperature" type="number" min="0" max="2" step="0.1" />
            </div>
            <div class="field">
              <label for="limit">Issue limit</label>
              <input id="limit" v-model.number="form.limit" type="number" min="1" max="20" step="1" />
            </div>
          </div>

          <div class="grid" style="margin-top: 10px">
            <div class="field">
              <label for="passphrase">Passphrase for encrypted localStorage</label>
              <input id="passphrase" v-model="passphrase" type="password" placeholder="Set a passphrase" />
            </div>
          </div>

          <div class="toolbar">
            <button type="button" @click="saveEncrypted">Save Encrypted</button>
            <button class="secondary" type="button" @click="loadEncrypted">Load Encrypted</button>
            <button class="danger" type="button" @click="clearEncrypted">Clear Storage</button>
          </div>
          <div class="status" :class="statusKind">{{ status }}</div>
          <div class="muted">
            Sensitive fields are stored encrypted with PBKDF2 + AES-GCM in browser localStorage.
          </div>
        </section>
      </aside>

      <section class="content">
        <header class="hero card">
          <h1>Sentry Task Generator</h1>
        </header>

        <section class="card results">
          <h3>Task Generation</h3>
          <div class="toolbar">
            <button type="button" @click="runFlow">Fetch Sentry Issues + Generate Tasks</button>
          </div>
          <div class="status" :class="runStatusKind">{{ runStatus }}</div>

          <div v-if="tasks.length === 0" class="muted">No tasks generated yet.</div>
          <article v-for="(task, idx) in tasks" :key="idx" class="task">
            <h4>{{ idx + 1 }}. {{ task.title || "Untitled task" }}</h4>
            <pre>{{ task.description || "No description" }}</pre>
          </article>
        </section>
      </section>
    </div>
  </main>
</template>

<script setup>
import { reactive, ref } from "vue";

const STORAGE_KEY = "sentry_tasks_encrypted_settings_v1";
const ITERATIONS = 310000;

const showSettings = ref(true);
const passphrase = ref("");
const status = ref("");
const statusKind = ref("ok");
const runStatus = ref("");
const runStatusKind = ref("ok");
const tasks = ref([]);

const form = reactive({
  sentry_url: "",
  sentry_org: "",
  sentry_project: "",
  sentry_token: "",
  openai_api_key: "",
  model: "gpt-5.4-mini",
  temperature: 1,
  limit: 3,
});

function setStatus(text, kind = "ok") {
  status.value = text;
  statusKind.value = kind;
}

function setRunStatus(text, kind = "ok") {
  runStatus.value = text;
  runStatusKind.value = kind;
}

async function deriveAesKey(rawPassphrase, saltBytes) {
  const enc = new TextEncoder();
  const keyMaterial = await crypto.subtle.importKey(
    "raw",
    enc.encode(rawPassphrase),
    "PBKDF2",
    false,
    ["deriveKey"],
  );

  return crypto.subtle.deriveKey(
    {
      name: "PBKDF2",
      salt: saltBytes,
      iterations: ITERATIONS,
      hash: "SHA-256",
    },
    keyMaterial,
    { name: "AES-GCM", length: 256 },
    false,
    ["encrypt", "decrypt"],
  );
}

function bytesToBase64(bytes) {
  let str = "";
  for (const b of bytes) {
    str += String.fromCharCode(b);
  }
  return btoa(str);
}

function base64ToBytes(base64) {
  const str = atob(base64);
  const out = new Uint8Array(str.length);
  for (let i = 0; i < str.length; i += 1) {
    out[i] = str.charCodeAt(i);
  }
  return out;
}

async function encryptSettings(payload, rawPassphrase) {
  const salt = crypto.getRandomValues(new Uint8Array(16));
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const key = await deriveAesKey(rawPassphrase, salt);
  const plainBytes = new TextEncoder().encode(JSON.stringify(payload));
  const encrypted = await crypto.subtle.encrypt(
    { name: "AES-GCM", iv },
    key,
    plainBytes,
  );

  return {
    version: 1,
    salt: bytesToBase64(salt),
    iv: bytesToBase64(iv),
    data: bytesToBase64(new Uint8Array(encrypted)),
  };
}

async function decryptSettings(payload, rawPassphrase) {
  const key = await deriveAesKey(rawPassphrase, base64ToBytes(payload.salt));
  const plain = await crypto.subtle.decrypt(
    { name: "AES-GCM", iv: base64ToBytes(payload.iv) },
    key,
    base64ToBytes(payload.data),
  );

  return JSON.parse(new TextDecoder().decode(plain));
}

async function saveEncrypted() {
  if (!passphrase.value) {
    setStatus("Passphrase is required for encryption", "warn");
    return;
  }

  try {
    const encrypted = await encryptSettings(form, passphrase.value);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(encrypted));
    setStatus("Encrypted settings saved", "ok");
  } catch (err) {
    setStatus(`Cannot save settings: ${err.message}`, "err");
  }
}

async function loadEncrypted() {
  if (!passphrase.value) {
    setStatus("Passphrase is required for decryption", "warn");
    return;
  }

  const raw = localStorage.getItem(STORAGE_KEY);
  if (!raw) {
    setStatus("No encrypted settings found", "warn");
    return;
  }

  try {
    const payload = JSON.parse(raw);
    const decrypted = await decryptSettings(payload, passphrase.value);
    Object.assign(form, decrypted);
    setStatus("Settings loaded", "ok");
  } catch (err) {
    setStatus(`Cannot decrypt settings: ${err.message}`, "err");
  }
}

function clearEncrypted() {
  localStorage.removeItem(STORAGE_KEY);
  setStatus("Encrypted storage cleared", "ok");
}

async function fetchSentryIssues() {
  const endpoint = `${form.sentry_url.replace(/\/$/, "")}/api/0/projects/${encodeURIComponent(form.sentry_org)}/${encodeURIComponent(form.sentry_project)}/issues/`;
  const response = await fetch(endpoint, {
    method: "GET",
    headers: {
      Authorization: `Bearer ${form.sentry_token}`,
      "Content-Type": "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(`Sentry request failed: ${response.status}`);
  }

  const issues = await response.json();
  return Array.isArray(issues) ? issues.slice(0, form.limit) : [];
}

async function generateTasks(issues) {
  const response = await fetch("/api/tasks/generate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      openai_api_key: form.openai_api_key,
      model: form.model,
      temperature: form.temperature,
      issues,
    }),
  });

  if (!response.ok) {
    let details = "";
    try {
      const body = await response.json();
      details = body.detail || body.error || "";
    } catch {
      details = "unknown API error";
    }
    throw new Error(`API request failed: ${response.status} ${details}`);
  }

  return response.json();
}

async function runFlow() {
  if (
    !form.sentry_url ||
    !form.sentry_org ||
    !form.sentry_project ||
    !form.sentry_token ||
    !form.openai_api_key
  ) {
    setRunStatus("Fill all required settings first", "warn");
    return;
  }

  tasks.value = [];
  setRunStatus("Fetching Sentry issues...", "ok");

  try {
    const issues = await fetchSentryIssues();
    if (!issues.length) {
      setRunStatus("No Sentry issues found for the selected scope", "warn");
      return;
    }

    setRunStatus("Generating tasks through API...", "ok");
    const generated = await generateTasks(issues);
    tasks.value = generated.tasks || [];
    setRunStatus(`Done. Generated ${tasks.value.length} task(s).`, "ok");
  } catch (err) {
    setRunStatus(`Flow failed: ${err.message}`, "err");
  }
}
</script>
