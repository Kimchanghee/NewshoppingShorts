import { readdir, stat } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const MAX_JS_CHUNK_BYTES = 500_000;
const scriptDirectory = path.dirname(fileURLToPath(import.meta.url));
const assetsDirectory = path.resolve(scriptDirectory, "..", "dist", "assets");

const assetNames = await readdir(assetsDirectory);
const javascriptAssets = assetNames.filter((name) => name.endsWith(".js")).sort();

if (javascriptAssets.length === 0) {
  throw new Error(`No JavaScript chunks found in ${assetsDirectory}`);
}

const oversizedAssets = [];
for (const assetName of javascriptAssets) {
  const assetPath = path.join(assetsDirectory, assetName);
  const assetSize = (await stat(assetPath)).size;
  if (assetSize > MAX_JS_CHUNK_BYTES) {
    oversizedAssets.push(`${assetName} (${assetSize} bytes)`);
  }
}

if (oversizedAssets.length > 0) {
  throw new Error(
    `JavaScript chunks exceed ${MAX_JS_CHUNK_BYTES} bytes: ${oversizedAssets.join(", ")}`,
  );
}

console.log(
  `Verified ${javascriptAssets.length} JavaScript chunks at or below ${MAX_JS_CHUNK_BYTES} bytes.`,
);
