import path from "node:path"
import { fileURLToPath } from "node:url"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"
const here = path.dirname(fileURLToPath(import.meta.url))
export default defineConfig({plugins:[react(),tailwindcss()],publicDir:path.resolve(here,"../.runtime/agent-deck/v1"),resolve:{alias:{"@":path.resolve(here,"./src")}}})
