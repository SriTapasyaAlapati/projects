"""Generates web/static/img/<product_id>.svg - glossy, studio-style product renders (one per product).
Run: python3 tools_gen_images.py   (output is committed; only needed to regenerate)."""
import os, re, sys
sys.path.insert(0, os.path.dirname(__file__))
from catalog_service.products_data import ALL_PRODUCTS

OUT = os.path.join(os.path.dirname(__file__), "web", "static", "img")
os.makedirs(OUT, exist_ok=True)

# product_id -> (shape, body colour, accent colour for label text)
SPEC = {
 "P001": ("lipstick", "#A8402F", "#A8402F"), "P002": ("dropper", "#F2B632", "#B07A00"),
 "P003": ("tube", "#2E2E33", "#2E2E33"),     "P004": ("pump", "#F4F1EA", "#B07A00"),
 "P005": ("perfume", "#8E6BC9", "#5A3E96"),  "P006": ("pencil", "#1C1C1E", "#1C1C1E"),
 "P007": ("tube", "#F6AF45", "#C46A00"),     "P008": ("bottle", "#F4F4F4", "#2E7D6B"),
 "P009": ("compact", "#D9A88B", "#A06A4A"),  "P010": ("bottle", "#F7DCE6", "#C2457A"),
 "P011": ("spray", "#FFF3E2", "#E07A12"),    "P012": ("mascara", "#1C1C1E", "#1C1C1E"),
 "P013": ("dropper", "#E9F2FB", "#2F6FAE"),  "P014": ("bottle", "#9A5A2A", "#7A3F14"),
 "P015": ("pump", "#E6C2A5", "#9A5B34"),     "P016": ("tube", "#52BD7B", "#24803F"),
 "P017": ("can", "#E8F1F9", "#2F7FBF"),      "P018": ("bottle", "#F1ECFA", "#6B4CB8"),
 "P019": ("palette", "#E5B25D", "#E5B25D"),  "P020": ("jar", "#F7EAF1", "#A8497A"),
}

def _rgb(h): h = h.lstrip("#"); return [int(h[i:i+2], 16) for i in (0, 2, 4)]
def shade(h, f):
    r, g, b = _rgb(h)
    if f >= 1: return "#%02x%02x%02x" % tuple(int(v + (255 - v) * (f - 1)) for v in (r, g, b))
    return "#%02x%02x%02x" % tuple(int(v * f) for v in (r, g, b))

def short_name(name):
    n = re.sub(r"\b\d+\s?(ml|g)\b", "", name.split(" - ")[0], flags=re.I).strip().upper()
    words, lines, cur = n.split(), [], ""
    for w in words:
        if len(cur + " " + w) > 11 and cur: lines.append(cur); cur = w
        else: cur = (cur + " " + w).strip()
    lines.append(cur); return lines[:3]

def cyl(i, base):   # horizontal gradient that makes a flat shape read as a cylinder
    return (f"<linearGradient id='{i}' x1='0' x2='1'><stop offset='0' stop-color='{shade(base,.62)}'/>"
            f"<stop offset='.16' stop-color='{shade(base,.93)}'/><stop offset='.38' stop-color='{shade(base,1.35)}'/>"
            f"<stop offset='.6' stop-color='{base}'/><stop offset='1' stop-color='{shade(base,.55)}'/></linearGradient>")

def gloss(x, y, w, h, op=.55):   # vertical specular strip
    return (f"<rect x='{x}' y='{y}' width='{w}' height='{h}' rx='{w/2}' fill='url(#gl)' opacity='{op}'/>")

def label(cx, y, w, h, brand, lines, accent):
    t = "".join(f"<text x='{cx}' y='{y+h*0.5+ i*11 - (len(lines)-1)*5.5 + 6}' font-family='Arial' font-weight='700' font-size='8' text-anchor='middle' fill='{accent}'>{ln}</text>" for i, ln in enumerate(lines))
    return (f"<rect x='{cx-w/2}' y='{y}' width='{w}' height='{h}' rx='5' fill='#fff' opacity='.93'/>"
            f"<text x='{cx}' y='{y+11}' font-family='Arial' font-weight='700' font-size='6.5' letter-spacing='1' text-anchor='middle' fill='#777'>{brand}</text>{t}")

def build(kind, c, accent, brand, lines):
    d = f"<defs>{cyl('b', c)}{cyl('k', '#2a2a2e')}{cyl('m', '#c9a24a')}</defs>"
    if kind == "pump":
        return d + (f"<rect x='94' y='118' width='112' height='142' rx='34' fill='url(#b)'/>{gloss(106,132,12,108)}"
          f"<rect x='124' y='92' width='52' height='28' rx='3' fill='url(#b)'/>"
          + "".join(f"<line x1='{128+i*6}' y1='94' x2='{128+i*6}' y2='118' stroke='#000' opacity='.12'/>" for i in range(8)) +
          f"<rect x='143' y='68' width='14' height='26' fill='url(#b)'/><path d='M116 50 H178 Q190 50 190 58 V66 H116Z' fill='url(#b)'/>"
          f"<rect x='178' y='54' width='24' height='9' rx='4' fill='url(#b)'/>"
          + label(150, 160, 70, 62, brand, lines, accent))
    if kind == "dropper":
        return d + (f"<rect x='104' y='138' width='92' height='122' rx='20' fill='url(#b)'/>{gloss(114,150,10,92)}"
          f"<rect x='130' y='112' width='40' height='30' rx='3' fill='url(#m)'/><rect x='134' y='62' width='32' height='54' rx='15' fill='url(#k)'/>"
          f"<rect x='140' y='70' width='5' height='36' rx='2.5' fill='#fff' opacity='.35'/>"
          + label(150, 168, 66, 62, brand, lines, accent))
    if kind == "tube":
        return d + (f"<path d='M102 70 H198 L190 232 H110Z' fill='url(#b)'/><path d='M104 70 H196' stroke='#000' opacity='.15' stroke-width='3'/>"
          f"<rect x='112' y='232' width='76' height='24' rx='6' fill='url(#k)'/><rect x='122' y='52' width='56' height='20' rx='3' fill='url(#b)'/>"
          + "".join(f"<line x1='{126+i*6}' y1='54' x2='{126+i*6}' y2='70' stroke='#000' opacity='.18'/>" for i in range(9)) +
          f"{gloss(114,82,10,138,.5)}" + label(150, 118, 66, 70, brand, lines, accent))
    if kind == "jar":
        return d + (f"<rect x='84' y='160' width='132' height='96' rx='20' fill='url(#b)'/>{gloss(96,172,10,70)}"
          f"<rect x='90' y='122' width='120' height='44' rx='10' fill='url(#k)'/><rect x='100' y='128' width='8' height='30' rx='4' fill='#fff' opacity='.3'/>"
          + label(150, 182, 84, 56, brand, lines, accent))
    if kind == "perfume":
        return d + (f"<rect x='92' y='122' width='116' height='136' rx='12' fill='url(#b)' opacity='.92'/>"
          f"<rect x='100' y='178' width='100' height='72' rx='8' fill='{shade(c,1.15)}' opacity='.55'/>{gloss(102,134,12,112,.5)}"
          f"<rect x='132' y='98' width='36' height='26' fill='url(#m)'/><rect x='116' y='56' width='68' height='46' rx='8' fill='url(#m)'/>"
          f"<rect x='124' y='62' width='8' height='34' rx='4' fill='#fff' opacity='.4'/>" + label(150, 152, 70, 52, brand, lines, accent))
    if kind == "lipstick":
        return d + (f"<rect x='118' y='150' width='64' height='108' rx='8' fill='url(#k)'/><rect x='122' y='128' width='56' height='26' rx='3' fill='url(#m)'/>"
          f"<rect x='128' y='72' width='44' height='58' rx='4' fill='url(#b)'/><path d='M128 76 L128 52 Q150 28 172 52 L172 76Z' fill='url(#b)'/>"
          f"<rect x='134' y='52' width='6' height='38' rx='3' fill='#fff' opacity='.4'/><rect x='126' y='160' width='7' height='90' rx='3' fill='#fff' opacity='.3'/>"
          f"<text x='150' y='214' font-family='Arial' font-weight='700' font-size='7' letter-spacing='1' text-anchor='middle' fill='#c9a24a'>{brand}</text>")
    if kind == "pencil":
        return d + (f"<g transform='rotate(-35 150 150)'><rect x='132' y='38' width='36' height='176' rx='5' fill='url(#b)'/>"
          f"<rect x='132' y='38' width='36' height='26' rx='5' fill='url(#m)'/><path d='M132 214 H168 L150 252Z' fill='#e9cba3'/>"
          f"<path d='M143 234 H157 L150 252Z' fill='#222'/><rect x='137' y='70' width='5' height='130' rx='2' fill='#fff' opacity='.3'/></g>")
    if kind == "compact":
        return (f"<defs><radialGradient id='cm' cx='40%' cy='35%' r='75%'><stop offset='0' stop-color='{shade(c,1.4)}'/><stop offset='.6' stop-color='{c}'/>"
          f"<stop offset='1' stop-color='{shade(c,.6)}'/></radialGradient>{cyl('k','#2a2a2e')}</defs>"
          f"<circle cx='150' cy='150' r='92' fill='url(#k)'/><circle cx='150' cy='150' r='78' fill='url(#cm)'/>"
          f"<path d='M92 118 Q150 62 208 118' stroke='#fff' stroke-width='6' fill='none' opacity='.5' stroke-linecap='round'/>"
          f"<text x='150' y='158' font-family='Arial' font-weight='700' font-size='8' letter-spacing='1.5' text-anchor='middle' fill='#fff' opacity='.85'>{brand}</text>")
    if kind == "spray":
        return d + (f"<rect x='104' y='116' width='92' height='144' rx='24' fill='url(#b)'/>{gloss(114,130,11,110)}"
          f"<rect x='136' y='92' width='28' height='26' fill='url(#m)'/><rect x='122' y='58' width='56' height='36' rx='7' fill='url(#k)'/>"
          f"<rect x='172' y='66' width='26' height='9' rx='4' fill='url(#k)'/>" + label(150, 156, 66, 62, brand, lines, accent))
    if kind == "mascara":
        return d + (f"<rect x='120' y='118' width='60' height='142' rx='14' fill='url(#k)'/>{gloss(128,130,8,112,.4)}"
          f"<rect x='144' y='34' width='12' height='88' rx='3' fill='#555'/><rect x='134' y='30' width='32' height='26' rx='9' fill='url(#k)'/>"
          f"<text x='150' y='196' font-family='Arial' font-weight='700' font-size='6' letter-spacing='.8' text-anchor='middle' fill='#c9a24a'>{brand}</text>"
          f"<text x='150' y='208' font-family='Arial' font-size='6' text-anchor='middle' fill='#ddd'>MASCARA</text>")
    if kind == "can":
        return d + (f"<rect x='108' y='80' width='84' height='178' rx='16' fill='url(#b)'/><ellipse cx='150' cy='84' rx='42' ry='10' fill='{shade(c,.75)}'/>"
          f"<rect x='120' y='52' width='60' height='34' rx='8' fill='url(#k)'/>{gloss(118,96,11,150,.5)}" + label(150, 128, 70, 76, brand, lines, accent))
    if kind == "palette":
        cols = ["#F6D6A0", c, "#C98B4B", "#8A5A2B", "#F2B8A2", "#E89A7A"]
        pans = "".join(f"<circle cx='{112+(i%3)*38}' cy='{138+(i//3)*52}' r='16' fill='{cols[i]}'/><circle cx='{108+(i%3)*38}' cy='{133+(i//3)*52}' r='5' fill='#fff' opacity='.35'/>" for i in range(6))
        return (f"<defs>{cyl('k','#3a2b25')}</defs><rect x='78' y='84' width='144' height='138' rx='14' fill='#3a2b25'/>{pans}"
          f"<text x='150' y='214' font-family='Arial' font-weight='700' font-size='6.5' letter-spacing='1.2' text-anchor='middle' fill='#c9a24a'>{brand}</text>")
    # bottle (shampoo / toner / oil / conditioner)
    return d + (f"<rect x='104' y='104' width='92' height='156' rx='26' fill='url(#b)'/>{gloss(114,120,10,120)}"
      f"<rect x='132' y='80' width='36' height='28' rx='4' fill='url(#b)'/><rect x='122' y='54' width='56' height='30' rx='7' fill='url(#k)'/>"
      f"<rect x='128' y='60' width='6' height='18' rx='3' fill='#fff' opacity='.3'/>" + label(150, 146, 66, 72, brand, lines, accent))

def svg(p):
    kind, c, accent = SPEC[p["product_id"]]
    body = build(kind, c, accent, p["brand"].upper(), short_name(p["name"]))
    return ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 300 300' width='300' height='300'>"
            "<defs><radialGradient id='bg' cx='50%' cy='40%' r='75%'><stop offset='0' stop-color='#ffffff'/><stop offset='1' stop-color='#eceaf0'/></radialGradient>"
            "<linearGradient id='gl' x1='0' x2='1'><stop offset='0' stop-color='#fff' stop-opacity='0'/><stop offset='.5' stop-color='#fff'/><stop offset='1' stop-color='#fff' stop-opacity='0'/></linearGradient>"
            "<radialGradient id='sh' cx='50%' cy='50%' r='50%'><stop offset='0' stop-color='#000' stop-opacity='.28'/><stop offset='1' stop-color='#000' stop-opacity='0'/></radialGradient></defs>"
            "<rect width='300' height='300' fill='url(#bg)'/><ellipse cx='150' cy='264' rx='84' ry='11' fill='url(#sh)'/>"
            f"{body}</svg>")

for p in ALL_PRODUCTS:
    open(os.path.join(OUT, p["product_id"] + ".svg"), "w").write(svg(p))
print(f"wrote {len(ALL_PRODUCTS)} images to {OUT}")
