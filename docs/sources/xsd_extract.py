"""Extract element list and enumerations from the SEC CMBS asset-data XSD.

Usage: py -3 -I xsd_extract.py <cmbs_xsd> <out_csv> <out_enum_md>
Reads the XSD as plain text (no network, no imports from the data dir).
"""
import csv
import re
import sys

xsd_path, out_csv, out_md = sys.argv[1], sys.argv[2], sys.argv[3]
text = open(xsd_path, encoding="utf-8").read()

# ---- simple types (enumerations) ----
enums = {}
for m in re.finditer(r'<xs:simpleType name="([A-Z_]+)">(.*?)</xs:simpleType>', text, re.S):
    name, body = m.group(1), m.group(2)
    doc_m = re.search(r"<xs:documentation>(.*?)</xs:documentation>", body, re.S)
    doc = " ".join(doc_m.group(1).split()) if doc_m else ""
    values = re.findall(r'<xs:enumeration value="([^"]+)"/>', body)
    item_m = re.match(r"Item ([0-9a-z()]+)", doc)
    item = "Item " + item_m.group(1) if item_m else ""
    listing = doc.split("Enumerated values and descriptions:", 1)[-1].strip()
    # split at ", <value>: " boundaries using the known enumeration values
    alt = "|".join(sorted((re.escape(v) for v in set(values)), key=len, reverse=True))
    parts = re.split(r"(?:^|,\s+)(" + alt + r"):\s", listing)
    pairs = []
    # parts = ['', v1, d1, v2, d2, ...]
    for i in range(1, len(parts) - 1, 2):
        pairs.append((parts[i], parts[i + 1].strip().rstrip(",").strip()))
    desc_by_val = {}
    for v, d in pairs:
        desc_by_val.setdefault(v, d)  # first description wins (ARM index lists 98 twice)
    enums[name] = {"item": item, "values": values, "desc": desc_by_val, "doc": doc}

# ---- elements with their preceding comment ----
def block(type_name):
    m = re.search(r'<xs:complexType name="%s">(.*?)</xs:complexType>' % type_name, text, re.S)
    return m.group(1)

def human_type(t):
    base = t.split(":")[-1]
    if base in enums:
        return "code (%s)" % base
    mapping = {
        "DECIMAL_TYPE20_8": "decimal(20,8)",
        "INTEGER_TYPE_8_A": "integer (max 8 digits)",
        "DATE_TYPE": "date MM-DD-YYYY",
        "TRUE_FALSE_TYPE": "boolean true/false",
        "PROPERTY_TYPE": "container (repeatable property group)",
    }
    if base in mapping:
        return mapping[base]
    sm = re.match(r"STRING_(\d+)_TYPE", base)
    if sm:
        return "string(max %s)" % sm.group(1)
    return base

rows = []
pat = re.compile(
    r"(?:<!--\s*(.*?)\s*-->\s*)?<xs:element name=\"([^\"]+)\" type=\"([^\"]+)\"([^/]*)/>", re.S
)
for parent, tname in (("assets", "ASSET_TYPE"), ("property", "PROPERTY_TYPE")):
    for m in pat.finditer(block(tname)):
        comment, name, typ, attrs = m.group(1) or "", m.group(2), m.group(3), m.group(4)
        comment = " ".join(comment.split())
        im = re.match(r"(Item [0-9a-z()]+)\s*-\s*(.*)", comment)
        if im:
            item, desc = im.group(1), im.group(2)
        else:
            item, desc = "", comment
        dt = human_type(typ)
        if 'maxOccurs="unbounded"' in attrs:
            dt += " [repeatable]"
        if 'minOccurs="1"' in attrs:
            dt += " [mandatory]"
        rows.append(
            {
                "element": name,
                "parent": parent,
                "schedule_al_item": item,
                "datatype": dt,
                "description_short": desc,
            }
        )

# order: assets elements in schema order, with property block inserted where it sits
asset_rows = [r for r in rows if r["parent"] == "assets"]
prop_rows = [r for r in rows if r["parent"] == "property"]
ordered = []
for r in asset_rows:
    ordered.append(r)
    if r["element"] == "property":
        ordered.extend(prop_rows)

with open(out_csv, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(
        f, fieldnames=["element", "parent", "schedule_al_item", "datatype", "description_short"]
    )
    w.writeheader()
    w.writerows(ordered)

# usage map: which element uses which enum type
uses = {}
for r in ordered:
    m = re.match(r"code \(([A-Z_]+)\)", r["datatype"])
    if m:
        uses.setdefault(m.group(1), []).append((r["element"], r["parent"], r["schedule_al_item"]))

with open(out_md, "w", encoding="utf-8") as f:
    for name in sorted(enums):
        e = enums[name]
        f.write("#### %s\n\n" % name)
        for el, par, it in uses.get(name, []):
            f.write("- Used by `%s` (parent `%s`), element comment: %s\n" % (el, par, it))
        f.write("- XSD type documentation cites: %s\n\n" % e["item"])
        f.write("| Code | Meaning (verbatim from XSD) |\n|---|---|\n")
        for v in e["values"]:
            f.write("| `%s` | %s |\n" % (v, e["desc"].get(v, "(no description in XSD)")))
        f.write("\n")

print("elements:", len(ordered), "assets:", len(asset_rows), "property:", len(prop_rows))
print("enum types:", len(enums))
for name in sorted(enums):
    missing = [v for v in enums[name]["values"] if v not in enums[name]["desc"]]
    if missing:
        print("MISSING DESC", name, missing)
