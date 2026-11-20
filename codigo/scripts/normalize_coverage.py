"""Normaliza rutas de reportes Cobertura XML para SonarQube en monorepo Atenta."""

from __future__ import annotations

import pathlib
import sys
import xml.etree.ElementTree as ET


def normalize_coverage_xml(xml_path: pathlib.Path, service_rel_dir: str) -> None:
    """Reescribe `<sources>` y prefija cada `<class filename>` desde la raíz del repo."""
    tree = ET.parse(xml_path)
    root = tree.getroot()
    prefix = service_rel_dir.strip("/").replace("\\", "/")

    sources_el = root.find("sources")
    if sources_el is not None:
        sources_el.clear()
        src_node = ET.SubElement(sources_el, "source")
        src_node.text = "."

    updated = 0
    for cls in root.iter("class"):
        filename = (cls.attrib.get("filename") or "").replace("\\", "/").lstrip("./")
        if not filename:
            continue
        if filename.startswith(f"{prefix}/"):
            continue
        if filename.startswith("src/"):
            cls.set("filename", f"{prefix}/{filename}")
        else:
            cls.set("filename", f"{prefix}/src/{filename}")
        updated += 1

    tree.write(xml_path, encoding="utf-8", xml_declaration=True)
    print(f"Normalized {updated} class path(s) in {xml_path} -> prefix='{prefix}'")


def main() -> int:
    if len(sys.argv) != 3:
        print(
            "Usage: python normalize_coverage.py <coverage_xml_path> <service_rel_dir>",
            file=sys.stderr,
        )
        return 2
    xml_path = pathlib.Path(sys.argv[1]).resolve()
    if not xml_path.is_file():
        print(f"Coverage XML file not found: {xml_path}", file=sys.stderr)
        return 1
    normalize_coverage_xml(xml_path, sys.argv[2])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
