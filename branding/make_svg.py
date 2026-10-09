"""Исходник иконки JackBOTS: пишет icon.svg, icon-foreground.svg, icon-background.svg рядом с собой.

После правок: python branding/make_svg.py && node tools/build_icons.js
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
INK = "#22303f"

def defs():
    return f'''<defs>
  <linearGradient id="bg" x1="0" y1="0" x2="0.35" y2="1">
    <stop offset="0" stop-color="#ff7a45"/><stop offset=".55" stop-color="#f2405a"/><stop offset="1" stop-color="#c81f5a"/>
  </linearGradient>
  <radialGradient id="glow" cx=".3" cy=".18" r=".75">
    <stop offset="0" stop-color="#fff" stop-opacity=".45"/><stop offset=".6" stop-color="#fff" stop-opacity="0"/>
  </radialGradient>
  <linearGradient id="paper" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#fffdf6"/><stop offset="1" stop-color="#f3ead3"/>
  </linearGradient>
  <radialGradient id="ball" cx=".35" cy=".35" r=".7">
    <stop offset="0" stop-color="#fff6a8"/><stop offset=".5" stop-color="#ffd23a"/><stop offset="1" stop-color="#e59a00"/>
  </radialGradient>
  <filter id="drop" x="-20%" y="-20%" width="140%" height="150%">
    <feGaussianBlur in="SourceAlpha" stdDeviation="18"/><feOffset dy="26"/>
    <feComponentTransfer><feFuncA type="linear" slope=".38"/></feComponentTransfer>
    <feMerge><feMergeNode/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>
  <clipPath id="sq"><rect width="1024" height="1024" rx="230"/></clipPath>
</defs>'''

def background(rounded=True):
    lines = "".join(f'<line x1="0" y1="{y}" x2="1024" y2="{y}"/>' for y in range(96, 1024, 88))
    body = f'''<rect width="1024" height="1024" fill="url(#bg)"/>
  <g stroke="#fff" stroke-opacity=".10" stroke-width="6">{lines}</g>
  <line x1="150" y1="0" x2="150" y2="1024" stroke="#ffd0d0" stroke-opacity=".28" stroke-width="8"/>
  <rect width="1024" height="1024" fill="url(#glow)"/>'''
    return f'<g clip-path="url(#sq)">{body}</g>' if rounded else body

def robot():
    # Робот-стикер: голова из бумаги, обводка «ручкой», скотч, антенна.
    return f'''<g filter="url(#drop)">
  <g transform="rotate(-7 512 560)">
    <line x1="512" y1="300" x2="512" y2="200" stroke="{INK}" stroke-width="34" stroke-linecap="round"/>
    <circle cx="512" cy="178" r="56" fill="url(#ball)" stroke="{INK}" stroke-width="30"/>
    <circle cx="492" cy="160" r="14" fill="#fff" opacity=".9"/>
    <rect x="196" y="470" width="80" height="170" rx="34" fill="#ffd23a" stroke="{INK}" stroke-width="30"/>
    <rect x="748" y="470" width="80" height="170" rx="34" fill="#ffd23a" stroke="{INK}" stroke-width="30"/>
    <rect x="252" y="300" width="520" height="480" rx="110" fill="url(#paper)" stroke="{INK}" stroke-width="36"/>
    <rect x="320" y="400" width="384" height="230" rx="80" fill="{INK}"/>
    <circle cx="420" cy="508" r="52" fill="#7ff0ff"/>
    <circle cx="604" cy="508" r="52" fill="#7ff0ff"/>
    <circle cx="436" cy="490" r="18" fill="#fff"/>
    <circle cx="620" cy="490" r="18" fill="#fff"/>
    <path d="M386 664 Q512 668 638 664 Q630 770 512 772 Q394 770 386 664 Z" fill="{INK}" stroke="{INK}" stroke-width="22" stroke-linejoin="round"/>
    <path d="M440 735 Q512 690 584 735 Q552 768 512 768 Q472 768 440 735 Z" fill="#ff5c7a"/>
    <rect x="420" y="664" width="184" height="30" rx="10" fill="#fff"/>
    <circle cx="330" cy="690" r="30" fill="#ff9db5" opacity=".75"/>
    <circle cx="694" cy="690" r="30" fill="#ff9db5" opacity=".75"/>
  </g>
  <rect x="190" y="286" width="230" height="74" fill="#ffe27a" fill-opacity=".86" transform="rotate(-32 305 323)"/>
  <rect x="610" y="742" width="230" height="74" fill="#ffe27a" fill-opacity=".86" transform="rotate(-32 725 779)"/>
</g>'''

def svg(content, size=1024):
    """Полный SVG-документ 1024×1024."""
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 1024 1024">{defs()}{content}</svg>'

(HERE / "icon.svg").open("w").write(svg(background() + robot()))
(HERE / "icon-background.svg").open("w").write(svg(background(rounded=False)))
# Адаптивная иконка: безопасная зона 66% — уменьшаем робота вокруг центра.
(HERE / "icon-foreground.svg").open("w").write(svg(f'<g transform="translate(512 530) scale(.84) translate(-512 -512)">{robot()}</g>'))
