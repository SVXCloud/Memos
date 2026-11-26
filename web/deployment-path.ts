import { readFileSync } from "node:fs";

export const basePath = readFileSync(new URL("../internal/deployment/base-path.txt", import.meta.url), "utf8").trim();
