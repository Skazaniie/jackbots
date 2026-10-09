// Generates all icons from branding/*.svg. Needs Node 18+ and sharp: `npm i sharp`, then `node tools/build_icons.js`.
// Writes: branding/jackbots.ico (exe), branding/icon-512.png (README), web/favicon.svg, android/.../mipmap-*.
const fs = require('fs');
const path = require('path');
const sharp = require('sharp');

const ROOT = path.resolve(__dirname, '..');
const BRAND = path.join(ROOT, 'branding');
const RES = path.join(ROOT, 'android/app/src/main/res');
const svg = name => fs.readFileSync(path.join(BRAND, name));
const png = (name, size) => sharp(svg(name), { density: 72 * size / 1024 * 4 }).resize(size, size).png().toBuffer();

// ICO with PNGs inside (Windows Vista+): header, directory, then the images.
function ico(images) {
  const head = Buffer.alloc(6 + 16 * images.length);
  head.writeUInt16LE(1, 2);
  head.writeUInt16LE(images.length, 4);
  let offset = head.length;
  images.forEach(({ size, data }, i) => {
    const e = 6 + 16 * i;
    head.writeUInt8(size >= 256 ? 0 : size, e);
    head.writeUInt8(size >= 256 ? 0 : size, e + 1);
    head.writeUInt16LE(1, e + 4);
    head.writeUInt16LE(32, e + 6);
    head.writeUInt32LE(data.length, e + 8);
    head.writeUInt32LE(offset, e + 12);
    offset += data.length;
  });
  return Buffer.concat([head, ...images.map(i => i.data)]);
}

const write = (file, data) => {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, data);
  console.log('  ' + path.relative(ROOT, file));
};

(async () => {
  const sizes = [16, 24, 32, 48, 64, 128, 256];
  write(path.join(BRAND, 'jackbots.ico'), ico(await Promise.all(sizes.map(async size => ({ size, data: await png('icon.svg', size) })))));
  write(path.join(BRAND, 'icon-512.png'), await png('icon.svg', 512));
  fs.copyFileSync(path.join(BRAND, 'icon.svg'), path.join(ROOT, 'web/favicon.svg'));
  console.log('  web/favicon.svg');

  // Android: a regular 48dp icon and 108dp adaptive layers for each density.
  const density = { mdpi: 1, hdpi: 1.5, xhdpi: 2, xxhdpi: 3, xxxhdpi: 4 };
  for (const [name, k] of Object.entries(density)) {
    const dir = path.join(RES, 'mipmap-' + name);
    write(path.join(dir, 'ic_launcher.png'), await png('icon.svg', 48 * k));
    write(path.join(dir, 'ic_launcher_foreground.png'), await png('icon-foreground.svg', 108 * k));
    write(path.join(dir, 'ic_launcher_background.png'), await png('icon-background.svg', 108 * k));
  }
  write(path.join(RES, 'mipmap-anydpi-v26/ic_launcher.xml'),
    '<?xml version="1.0" encoding="utf-8"?>\n' +
    '<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">\n' +
    '    <background android:drawable="@mipmap/ic_launcher_background" />\n' +
    '    <foreground android:drawable="@mipmap/ic_launcher_foreground" />\n' +
    '</adaptive-icon>\n');
})().catch(err => { console.error(err); process.exit(1); });
