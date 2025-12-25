# Enterprise RAG Frontend 💻✨

> The "Modern Executive" interface for the Enterprise RAG system. A high-performance React application focusing on traceability, data visualization, and seamless user interaction.

## 🎨 Design System: "Modern Executive"

The UI is built on a custom design language defined in `index.css`:
- **Primary Color**: Neon Indigo (`#6366f1`) - Used for primary actions and focus states.
- **Secondary Color**: Emerald Teal (`#10b981`) - Used for success states and relevance scoring.
- **Backgrounds**: Deep Obsidian (`#0f172a`) and Slate Gunmetal (`#1e293b`) for depth.
- **Effects**: Heavy use of **Glassmorphism** (blur + translucency) and subtle glow animations.
- **Typography**: Inter (Google Fonts) for clean, professional readability.

## 📂 Project Structure

```bash
frontend/
├── src/
│   ├── api/
│   │   ├── client.ts       # Axios instance with Auth interceptors
│   │   └── services.ts     # Typed API methods (Auth, RAG, Uploads)
│   ├── components/
│   │   ├── ChatInterface.tsx  # Core chat UI with streaming support
│   │   ├── SourceDrawer.tsx   # Slide-out panel for citation review
│   │   └── ProtectedRoute.tsx # Auth guard wrapper
│   ├── pages/
│   │   ├── Dashboard.tsx   # Main application shell
│   │   ├── Login.tsx       # Dual-auth login page (Google + Email)
│   │   ├── Signup.tsx      # OTP-based registration wizard
│   │   └── Documents.tsx   # Drag-and-drop ingestion manager
│   ├── hooks/
│   │   └── useAuth.tsx     # Global Auth Context (Provider pattern)
│   └── styles/             # Component-specific CSS modules
```

## ✨ Key Components

### 1. Chat Interface (`ChatInterface.tsx`)
- **Thinking Indicator**: Visualizes the RAG backend steps (Searching → Reranking → Generating).
- **Citation Parsing**: Automatically detects `[Source X]` patterns in AI text and converts them into interactive badges.
- **Markdown Support**: Renders rich text, lists, and code blocks.

### 2. Source Drawer (`SourceDrawer.tsx`)
- **Interactive Review**: Clicking a citation opens this drawer.
- **Relevance Scoring**: Color-coded badges (Green/Amber/Gray) showing how relevant a chunk was to the query.
- **Content Preview**: Expandable accordion view to see the raw text used by the AI.

### 3. Document Manager (`Documents.tsx`)
- **Smart Upload**: `FormData` handling with automatic boundary detection.
- **Status Tracking**: Real-time feedback on file processing and chunking status.

## 🔐 Authentication Flow

The frontend handles complex auth states using `useAuth` hook:
1. **Initial Load**: Checks `localStorage` for `access_token`.
2. **Login**:
   - **Google**: Redirects to backend OAuth URL.
   - **Email**: Hashed password exchange.
3. **Session Expiry**: Axios interceptor (`api/client.ts`) automatically detects `401 Unauthorized` and redirects to login.

## 🚀 Development scripts

```bash
# Install dependencies
npm install

# Start local dev server (port 5173)
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

## 📦 Environment Variables

Create a `.env` file in this directory if needed, though most config defaults to `localhost:8000`:
```env
VITE_API_URL=http://localhost:8000
```
