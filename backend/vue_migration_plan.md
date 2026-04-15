# Migrate Frontend to Vue (No Build Step)

We will migrate the frontend implementation from a built React app into a simple Vue 3 app utilizing the Vue CDN without any build steps. Flask will be updated to serve it directly from the `backend/public` directory.

## Proposed Changes

### Backend Configuration

Currently, Flask is configured to serve the frontend from `frontend/dist`. We will update `settings.py` so the single source of truth points to a newly created `public` folder inside the `backend` directory.

#### settings.py
Update `frontend_dir` resolution:
```python
base_dir = Path(__file__).resolve().parent.parent
frontend_dir = base_dir / "public"
frontend_assets_dir = frontend_dir / "assets"
```

### Static Vue Setup in Backend

We will add a simple, no-build-step Vue application using ES modules directly into `backend/public`.

#### backend/public/index.html
The entry point that will be served directly by Flask on any unrecognized route like `/`.
It will include:
- A `div#app` for mounting Vue.
- `<script type="importmap">` to map Vue to the CDN version so we can `import { createApp } from 'vue'`.
- `<link rel="stylesheet" href="/style.css">`.
- `<script type="module" src="/app.js"></script>` to run the Vue application.

#### backend/public/app.js
Bootstrap the Vue application using the Composition API:
```javascript
import { createApp, ref } from 'vue';

const App = {
  setup() {
    const message = ref("Hello from Vue without a build step!");
    return { message };
  },
  template: `
    <div>
      <h1>{{ message }}</h1>
      <p>This is served directly via Flask.</p>
    </div>
  `
};

createApp(App).mount('#app');
```

#### backend/public/style.css
Basic vanilla styling following the requested aesthetic rules for clean UI, dark mode, and vibrant layouts.

## Verification Plan

### Manual Verification
1. Restart the Flask backend.
2. Navigate to `http://localhost:8000/`.
3. Verify that the new Vue interface correctly loads and hydrates without any build tooling needed.
4. Verify that page reloads on other paths (e.g. `http://localhost:8000/some-route`) render the `index.html` successfully and Vue takes over handling the UI.
